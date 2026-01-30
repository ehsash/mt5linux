"""Process detection and management module for mt5linux.

This module provides functionality to detect running rpyc server and MT5 processes,
and to start the rpyc server automatically when needed.

Process detection uses psutil for cross-platform process enumeration.
Detection must complete within 2 seconds (NFR8) with 100% accuracy (NFR19).
Server startup reliability must be >95% (NFR21).
"""

import os
import re
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Dict, List, Optional, Union

# Server startup retry configuration
STARTUP_MAX_RETRIES = 5
STARTUP_RETRY_DELAY = 1.0  # seconds
SOCKET_VERIFY_TIMEOUT = 2.0  # seconds

# Virtual display configuration for headless operation
VIRTUAL_DISPLAY = ":99"
VIRTUAL_DISPLAY_RESOLUTION = "1920x1080x24"

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

if TYPE_CHECKING:
    import logging as _logging

    from loguru import Logger as _LoguruLogger

    LoggerType = Union[_LoguruLogger, _logging.Logger]

try:
    from loguru import logger
except ImportError:
    # Fallback to standard logging if loguru not available
    import logging

    logger: "LoggerType" = logging.getLogger(__name__)  # type: ignore[no-redef]

# Import config module for host/port/prefix settings
try:
    from mt5linux.config import get_config
except ImportError:
    get_config = None  # type: ignore


class MT5LinuxError(Exception):
    """Base exception class for all mt5linux errors.

    All custom exceptions in the mt5linux package should inherit from this
    class to enable consistent error handling and filtering.
    """

    pass


class ProcessError(MT5LinuxError):
    """Base exception for process-related errors.

    Raised when process detection, startup, or management operations fail.
    """

    pass


class PythonNotFoundError(ProcessError):
    """Raised when Windows Python executable cannot be found in Wine prefix.

    This exception is raised when the system cannot locate a valid Python
    installation within the configured Wine prefix. The error message includes
    actionable guidance for resolution.
    """

    pass


class RpycServerError(ProcessError):
    """Raised when rpyc server startup fails.

    This exception is raised when the system fails to start the rpyc server
    via Wine. The error message includes context about what went wrong and
    suggestions for resolution.
    """

    pass


class MT5LaunchError(ProcessError):
    """Raised when MT5 launch fails.

    This exception indicates that the system failed to launch MetaTrader5
    via Wine. The error message includes troubleshooting suggestions.

    Common causes:
        - MT5 not installed in Wine prefix
        - Wine prefix not configured or invalid
        - MT5 executable not found in expected locations
        - Wine not installed or accessible
        - MT5 failed to start within timeout period

    Example:
        >>> raise MT5LaunchError(
        ...     "MetaTrader5 terminal not found in Wine prefix: .mt5. "
        ...     "Ensure MT5 is installed. Run 'mt5linux setup' to install."
        ... )
    """

    pass


# Process name patterns for detection
PYTHON_PROCESS_NAMES = frozenset({"python.exe", "pythonw.exe", "python3.exe", "python"})
MT5_PROCESS_NAMES = frozenset(
    {"terminal64.exe", "terminal.exe", "metatrader5.exe", "metatrader.exe"}
)
RPYC_CMDLINE_PATTERNS = frozenset(
    {"rpyc", "rpyc_server", "rpyc.utils.server", "SlaveService"}
)


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    """Information about a detected process.

    Attributes:
        pid: Process ID.
        name: Process name (e.g., 'python.exe', 'terminal64.exe').
        status: Process status (e.g., 'running', 'sleeping').
        cmdline: Optional command-line arguments used to start the process.
    """

    pid: int
    name: str
    status: str
    cmdline: Optional[List[str]] = None


class ProcessManager:
    """Manages process detection for rpyc server and MT5.

    This class provides methods to detect running processes by name and
    command-line arguments, supporting automatic process management in
    the mt5linux library.

    Process detection completes within 2 seconds (NFR8) with 100% accuracy (NFR19).
    All detection methods return None on failure and do not raise exceptions.

    Example:
        >>> manager = ProcessManager()
        >>> rpyc_proc = manager.find_rpyc_server()
        >>> if rpyc_proc:
        ...     print(f"rpyc server running: PID {rpyc_proc.pid}")
    """

    def __init__(self) -> None:
        """Initialize ProcessManager."""
        if psutil is None:
            logger.warning("psutil not available, process detection will not work")

        # Lifecycle manager (initialized on first use via start_lifecycle_management)
        # Type is mt5linux.lifecycle.LifecycleManager but we use Any to avoid circular import
        self._lifecycle_manager: Optional[Any] = None

        # Track Xvfb process for virtual display
        self._xvfb_process: Optional[subprocess.Popen[bytes]] = None

        # Track if env file has been loaded
        self._env_loaded: bool = False

    def _load_env_file(self) -> None:
        """Load environment variables from ~/.env file.

        Reads MT5 credentials (MT5_LOGIN, MT5_PASSWORD, MT5_SERVER) from
        the user's ~/.env file and sets them in os.environ.

        This is called automatically when starting MT5 to ensure credentials
        are available for command-line login, bypassing MT5's credential
        persistence issues under Wine.

        Note:
            - Only loads the file once per ProcessManager instance
            - Silently ignores missing or unreadable files
            - Only loads MT5_* variables for security
        """
        if self._env_loaded:
            return

        env_path = Path.home() / ".env"
        if not env_path.exists():
            logger.debug("~/.env file not found, skipping credential load")
            self._env_loaded = True
            return

        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue
                    # Only load MT5_* variables for security
                    if line.startswith("MT5_") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip()
                        # Remove quotes if present
                        if value and value[0] in ('"', "'") and value[-1] == value[0]:
                            value = value[1:-1]
                        os.environ[key] = value
                        if key != "MT5_PASSWORD":
                            logger.debug(f"Loaded {key} from ~/.env")
                        else:
                            logger.debug("Loaded MT5_PASSWORD from ~/.env")
            self._env_loaded = True
            logger.info("Loaded MT5 credentials from ~/.env")
        except Exception as e:
            logger.warning(f"Could not read ~/.env: {e}")
            self._env_loaded = True

    def find_rpyc_server(self, port: Optional[int] = None) -> Optional[ProcessInfo]:
        """Find running rpyc server process.

        Searches for Python processes that appear to be running an rpyc server
        by checking process names and command-line arguments.

        Args:
            port: If specified, only return server listening on this port.
                  If None, returns any rpyc server found.

        Returns:
            ProcessInfo if rpyc server process found, None otherwise.

        Note:
            - Detection completes within 2 seconds (NFR8)
            - Returns None on any error (does not raise exceptions)
            - Matches python.exe, pythonw.exe, python3.exe process names
            - Matches 'rpyc' patterns in command-line arguments
        """
        if psutil is None:
            logger.debug("psutil not available, cannot detect rpyc server")
            return None

        logger.debug(f"Searching for rpyc server process (port={port})")
        try:
            result = self._find_process_by_criteria(
                name_matches=PYTHON_PROCESS_NAMES,
                cmdline_patterns=RPYC_CMDLINE_PATTERNS,
                require_cmdline_match=True,
            )
            if result is None:
                return None

            # If port filter specified, check if this server is on that port
            if port is not None:
                cmdline_str = " ".join(result.cmdline)
                # Look for port=NNNNN pattern in command line
                if f"port={port}" not in cmdline_str:
                    logger.debug(
                        f"Found rpyc server PID={result.pid} but not on port {port}"
                    )
                    return None

            return result
        except Exception as e:
            logger.debug(f"Error during rpyc server detection: {e}")
            return None

    def find_mt5(self) -> Optional[ProcessInfo]:
        """Find running MetaTrader 5 process.

        Searches for MT5 processes by checking process names.

        Returns:
            ProcessInfo if MT5 process found, None otherwise.

        Note:
            - Detection completes within 2 seconds (NFR8)
            - Detection accuracy is 100% (NFR19)
            - Returns None on any error (does not raise exceptions)
            - Matches terminal64.exe, terminal.exe, metatrader5.exe, metatrader.exe
        """
        if psutil is None:
            logger.debug("psutil not available, cannot detect MT5")
            return None

        logger.debug("Searching for MT5 process")
        try:
            return self._find_process_by_criteria(
                name_matches=MT5_PROCESS_NAMES,
                cmdline_patterns=None,
                require_cmdline_match=False,
            )
        except Exception as e:
            logger.debug(f"Error during MT5 detection: {e}")
            return None

    def _find_process_by_criteria(
        self,
        name_matches: frozenset,
        cmdline_patterns: Optional[frozenset],
        require_cmdline_match: bool,
    ) -> Optional[ProcessInfo]:
        """Find process matching specified criteria.

        Args:
            name_matches: Set of process names to match (case-insensitive).
            cmdline_patterns: Set of patterns to search for in command-line.
            require_cmdline_match: If True, cmdline must match patterns.

        Returns:
            ProcessInfo if matching process found, None otherwise.
        """
        candidates: List[ProcessInfo] = []

        try:
            for proc in psutil.process_iter(["pid", "name", "status", "cmdline"]):
                try:
                    info = proc.info
                    proc_name = info.get("name", "")
                    if not proc_name:
                        continue

                    # Check process name match (case-insensitive)
                    if proc_name.lower() not in name_matches:
                        continue

                    cmdline = info.get("cmdline") or []
                    cmdline_str = " ".join(cmdline).lower()

                    # Check cmdline patterns if required
                    if require_cmdline_match and cmdline_patterns:
                        if not any(
                            pattern in cmdline_str for pattern in cmdline_patterns
                        ):
                            continue

                    # Found a match
                    process_info = ProcessInfo(
                        pid=info.get("pid", 0),
                        name=proc_name,
                        status=info.get("status", "unknown"),
                        cmdline=cmdline if cmdline else None,
                    )
                    candidates.append(process_info)
                    logger.debug(
                        f"Found matching process: PID={process_info.pid}, name={process_info.name}"
                    )

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ) as e:
                    # Process disappeared or inaccessible during iteration
                    logger.debug(f"Process inaccessible during iteration: {e}")
                    continue

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.debug(f"Process iteration error: {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected error during process iteration: {e}")
            return None

        if not candidates:
            logger.debug("No matching process found")
            return None

        # Return most relevant process (highest PID = newest)
        if len(candidates) > 1:
            logger.debug(
                f"Multiple matching processes found ({len(candidates)}), selecting newest"
            )
            candidates.sort(key=lambda p: p.pid, reverse=True)

        selected = candidates[0]
        logger.info(f"Selected process: PID={selected.pid}, name={selected.name}")
        return selected

    def find_windows_python(self) -> str:
        """Find Windows Python executable in Wine prefix.

        Searches for python.exe in common installation locations within the
        configured Wine prefix. Prefers newer Python versions when multiple
        installations are found.

        Returns:
            Path to python.exe as a string.

        Raises:
            PythonNotFoundError: If no Python installation is found.

        Note:
            Search order:
            1. drive_c/Python*/python.exe (direct Python installation)
            2. drive_c/Program Files/Python*/python.exe
            3. drive_c/Program Files (x86)/Python*/python.exe
            4. drive_c/users/*/AppData/Local/Programs/Python/Python*/python.exe
        """
        wine_prefix = self._get_wine_prefix()
        if not wine_prefix:
            raise PythonNotFoundError(
                "Wine prefix not configured. Run 'mt5linux setup' first or set "
                "wine.prefix_path in config."
            )

        prefix_path = Path(wine_prefix)
        drive_c = prefix_path / "drive_c"

        if not drive_c.exists():
            raise PythonNotFoundError(
                f"Wine prefix drive_c not found at {drive_c}. "
                "Ensure Wine is properly initialized."
            )

        # Search patterns in order of preference
        search_patterns = [
            drive_c / "Python*" / "python.exe",
            drive_c / "Program Files" / "Python*" / "python.exe",
            drive_c / "Program Files (x86)" / "Python*" / "python.exe",
        ]

        # Also search user AppData locations
        users_dir = drive_c / "users"
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                if user_dir.is_dir():
                    search_patterns.append(
                        user_dir
                        / "AppData"
                        / "Local"
                        / "Programs"
                        / "Python"
                        / "Python*"
                        / "python.exe"
                    )

        # Find all matching python.exe files
        found_pythons: List[Path] = []
        for pattern in search_patterns:
            pattern_str = str(pattern)
            if "*" in pattern_str:
                # Use glob from the drive_c directory with relative pattern
                try:
                    # Make pattern relative to drive_c for consistent globbing
                    rel_pattern = str(pattern).replace(str(drive_c) + "/", "")
                    for match in drive_c.glob(rel_pattern):
                        if match.exists() and match.is_file():
                            found_pythons.append(match)
                except (OSError, ValueError):
                    continue

        if not found_pythons:
            raise PythonNotFoundError(
                f"No Windows Python installation found in Wine prefix: {wine_prefix}. "
                "Please install Python for Windows in the Wine prefix. "
                "You can download it from https://www.python.org/downloads/windows/"
            )

        # Sort by version (prefer newer versions)
        def extract_version(path: Path) -> tuple:
            """Extract Python version from path for sorting."""
            path_str = str(path)
            # Look for patterns like Python311, Python39, etc.
            match = re.search(r"Python(\d+)", path_str)
            if match:
                version_str = match.group(1)
                # Convert to tuple for proper sorting (e.g., "311" -> (3, 11))
                if len(version_str) >= 2:
                    major = int(version_str[0])
                    minor = int(version_str[1:])
                    return (major, minor)
            return (0, 0)

        found_pythons.sort(key=extract_version, reverse=True)
        selected = found_pythons[0]

        logger.info(f"Found Windows Python: {selected}")
        return str(selected)

    def start_rpyc_server(self) -> ProcessInfo:
        """Start rpyc server on Windows Python via Wine.

        Checks if an rpyc server is already running on the configured port
        and returns its info if so. Otherwise, starts a new rpyc server.

        Returns:
            ProcessInfo for the running rpyc server (existing or newly started).

        Raises:
            PythonNotFoundError: If Windows Python cannot be found.
            RpycServerError: If server fails to start.

        Note:
            - Uses configuration from mt5linux.config module
            - Default host: localhost, default port: 18812
            - Server startup reliability target: >95% (NFR21)
        """
        # Get configuration first so we can check for server on correct port
        config = get_config() if get_config is not None else None
        if config:
            host = config.server.host
            port = config.server.port
            wine_prefix = config.wine.prefix_path
        else:
            host = "localhost"
            port = 18812
            wine_prefix = None

        # Check if server is already running on the configured port
        existing = self.find_rpyc_server(port=port)
        if existing:
            logger.info(
                f"rpyc server already running on port {port}: "
                f"PID={existing.pid}, using existing instance"
            )
            return existing

        logger.info(f"rpyc server not running on port {port}, starting new instance")

        logger.debug(
            f"Configuration: host={host}, port={port}, wine_prefix={wine_prefix}"
        )

        # Find Windows Python
        python_exe = self.find_windows_python()

        # Build the rpyc server startup command
        # Use inline Python code to start ThreadedServer (similar to __main__.py pattern)
        server_code = (
            "from rpyc.utils.server import ThreadedServer; "
            "from rpyc.core.service import SlaveService; "
            f"server = ThreadedServer(SlaveService, hostname='{host}', port={port}, "
            "reuse_addr=True, ipv6=False, authenticator=None, auto_register=False); "
            "server.start()"
        )

        wine_cmd = ["wine", python_exe, "-c", server_code]

        # Start virtual display for headless operation
        xvfb_started = self.start_xvfb()

        # Setup environment with WINEPREFIX
        env = os.environ.copy()
        wine_prefix_path = self._get_wine_prefix()
        if wine_prefix_path:
            env["WINEPREFIX"] = wine_prefix_path

        # Use virtual display if Xvfb is running - prevents Wine GUI on user's screen
        if xvfb_started or self.find_xvfb():
            env["DISPLAY"] = VIRTUAL_DISPLAY
            # Force X11 mode - unset Wayland variables
            env.pop("WAYLAND_DISPLAY", None)
            env.pop("XDG_SESSION_TYPE", None)
            logger.info(f"rpyc server will use virtual display {VIRTUAL_DISPLAY}")

        logger.debug(f"Starting rpyc server with command: {' '.join(wine_cmd)}")

        try:
            process = subprocess.Popen(
                wine_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                start_new_session=True,  # Detach from terminal
            )
        except OSError as e:
            logger.error(f"Failed to start Wine process: {e}")
            raise RpycServerError(
                f"Failed to start rpyc server via Wine: {e}. "
                "Ensure Wine is installed and accessible."
            ) from e

        # Verify server started successfully with retries
        for attempt in range(STARTUP_MAX_RETRIES):
            # Check if process exited immediately (failure)
            exit_code = process.poll()
            if exit_code is not None and exit_code != 0:
                stderr_output = self._drain_pipe(process.stderr)
                self._drain_pipe(process.stdout)  # Drain stdout too
                logger.error(
                    f"rpyc server process exited with code {exit_code}: {stderr_output}"
                )
                raise RpycServerError(
                    f"rpyc server failed to start (exit code {exit_code}). "
                    f"Error: {stderr_output or 'unknown error'}. "
                    "Check that rpyc is installed in the Wine Python environment."
                )

            # Check if server is now running (process detection + socket verification)
            server_process = self.find_rpyc_server()
            if server_process and self._verify_port_listening(host, port):
                logger.info(
                    f"rpyc server started successfully: PID={server_process.pid}, "
                    f"listening on {host}:{port}"
                )
                return server_process

            # Wait before retry
            if attempt < STARTUP_MAX_RETRIES - 1:
                logger.debug(
                    f"Waiting for rpyc server to start "
                    f"(attempt {attempt + 1}/{STARTUP_MAX_RETRIES})"
                )
                time.sleep(STARTUP_RETRY_DELAY)

        # All retries exhausted - drain pipes before raising
        self._drain_pipe(process.stderr)
        self._drain_pipe(process.stdout)
        logger.error("rpyc server failed to start after all retries")
        raise RpycServerError(
            f"rpyc server did not start within "
            f"{STARTUP_MAX_RETRIES * STARTUP_RETRY_DELAY} seconds. "
            "The process may have started but is not responding. "
            f"Check that port {port} is not already in use."
        )

    def _drain_pipe(self, pipe: Optional[IO[bytes]]) -> str:
        """Drain a subprocess pipe to prevent blocking.

        Args:
            pipe: A subprocess PIPE (stdout or stderr) or None.

        Returns:
            The decoded pipe contents, or empty string if pipe is None/empty.
        """
        if pipe is None:
            return ""
        try:
            content = pipe.read()
            if content:
                return content.decode("utf-8", errors="replace")
        except (IOError, OSError, ValueError):
            # IOError/OSError: pipe closed or broken
            # ValueError: I/O operation on closed file
            pass
        return ""

    def _verify_port_listening(self, host: str, port: int) -> bool:
        """Verify that a port is accepting connections.

        Args:
            host: The host address to connect to.
            port: The port number to check.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            with socket.create_connection(
                (host, port), timeout=SOCKET_VERIFY_TIMEOUT
            ) as sock:
                sock.close()
                return True
        except (socket.timeout, socket.error, OSError):
            return False

    def _get_wine_prefix(self) -> Optional[str]:
        """Get Wine prefix path from configuration or default location.

        Returns:
            Wine prefix path or None if not configured.
        """
        # Try to get from config
        config = get_config() if get_config is not None else None
        if config and config.wine.prefix_path:
            return config.wine.prefix_path

        # Fallback to .mt5 in current working directory
        default_prefix = Path.cwd() / ".mt5"
        if default_prefix.exists():
            return str(default_prefix)

        return None

    def find_mt5_executable(self) -> str:
        """Find MT5 terminal executable in Wine prefix.

        Searches for terminal64.exe in common installation locations within the
        configured Wine prefix. Prefers the Program Files location over
        Program Files (x86).

        Returns:
            Path to terminal64.exe as a string.

        Raises:
            MT5LaunchError: If MT5 executable not found or Wine prefix
                not configured.

        Note:
            Search order (first match wins):
            1. drive_c/Program Files/MetaTrader 5/terminal64.exe
            2. drive_c/Program Files (x86)/MetaTrader 5/terminal64.exe
        """
        wine_prefix = self._get_wine_prefix()
        if not wine_prefix:
            raise MT5LaunchError(
                "Wine prefix not configured. Run 'mt5linux setup' first or set "
                "wine.prefix_path in config."
            )

        prefix_path = Path(wine_prefix)
        mt5_paths = [
            prefix_path
            / "drive_c"
            / "Program Files"
            / "MetaTrader 5"
            / "terminal64.exe",
            prefix_path
            / "drive_c"
            / "Program Files (x86)"
            / "MetaTrader 5"
            / "terminal64.exe",
        ]

        for path in mt5_paths:
            if path.exists():
                logger.info(f"Found MT5 executable: {path}")
                return str(path)

        raise MT5LaunchError(
            f"MetaTrader5 terminal not found in Wine prefix: {wine_prefix}. "
            "Ensure MT5 is installed in the Wine prefix. "
            "Run 'mt5linux setup' to install MT5."
        )

    def find_xvfb(self) -> Optional[ProcessInfo]:
        """Find running Xvfb process on the virtual display.

        Returns:
            ProcessInfo if Xvfb is running on VIRTUAL_DISPLAY, None otherwise.
        """
        if psutil is None:
            return None

        try:
            for proc in psutil.process_iter(["pid", "name", "status", "cmdline"]):
                try:
                    info = proc.info
                    name = info.get("name", "")
                    cmdline = info.get("cmdline") or []

                    if name.lower() == "xvfb" and VIRTUAL_DISPLAY in cmdline:
                        return ProcessInfo(
                            pid=info["pid"],
                            name=name,
                            status=info.get("status", "unknown"),
                            cmdline=cmdline,
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug(f"Error detecting Xvfb: {e}")

        return None

    def start_xvfb(self) -> bool:
        """Start Xvfb virtual display if not already running.

        Starts Xvfb on VIRTUAL_DISPLAY (:99) for headless MT5 operation.
        If Xvfb is already running on that display, returns True without
        starting a new instance.

        Returns:
            True if Xvfb is running (either started or already running),
            False if Xvfb couldn't be started.

        Note:
            - Xvfb must be installed (apt install xvfb)
            - Uses VIRTUAL_DISPLAY_RESOLUTION for screen size
            - The process is tracked in self._xvfb_process for cleanup
        """
        # Check if already running
        existing = self.find_xvfb()
        if existing:
            logger.info(
                f"Xvfb already running on {VIRTUAL_DISPLAY}: PID={existing.pid}"
            )
            return True

        # Find Xvfb executable
        xvfb_path = shutil.which("Xvfb")
        if not xvfb_path:
            logger.warning("Xvfb not found - MT5 may display on user's screen")
            return False

        # Start Xvfb
        try:
            self._xvfb_process = subprocess.Popen(
                [
                    xvfb_path,
                    VIRTUAL_DISPLAY,
                    "-screen",
                    "0",
                    VIRTUAL_DISPLAY_RESOLUTION,
                    "-ac",  # Disable access control
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            # Give Xvfb time to initialize
            time.sleep(0.5)

            # Verify it's running
            if self._xvfb_process.poll() is None:
                logger.info(
                    f"Started Xvfb on {VIRTUAL_DISPLAY}: PID={self._xvfb_process.pid}"
                )
                return True
            else:
                logger.warning(
                    f"Xvfb exited immediately with code {self._xvfb_process.returncode}"
                )
                return False
        except Exception as e:
            logger.warning(f"Failed to start Xvfb: {e}")
            return False

    def stop_xvfb(self) -> None:
        """Stop the Xvfb process if we started it.

        Only stops Xvfb if it was started by this ProcessManager instance.
        Does not affect Xvfb processes started elsewhere.
        """
        if self._xvfb_process is not None:
            try:
                self._xvfb_process.terminate()
                self._xvfb_process.wait(timeout=5)
                logger.info("Stopped Xvfb virtual display")
            except subprocess.TimeoutExpired:
                self._xvfb_process.kill()
                logger.warning("Forcefully killed Xvfb")
            except Exception as e:
                logger.warning(f"Error stopping Xvfb: {e}")
            finally:
                self._xvfb_process = None

    def start_mt5(self) -> ProcessInfo:
        """Start MT5 terminal via Wine on virtual display.

        Checks if MT5 is already running and returns its info if so.
        Otherwise, starts Xvfb virtual display (if available) and launches
        MT5 via Wine on that display.

        Returns:
            ProcessInfo for the running MT5 process (existing or newly started).

        Raises:
            MT5LaunchError: If MT5 cannot be found or launched.

        Note:
            - Uses configuration from mt5linux.config module for Wine prefix
            - Starts Xvfb on :99 for headless operation (if Xvfb available)
            - Launches MT5 in a detached session (start_new_session=True)
            - Waits for MT5 to be ready after launch
            - Auto-launch reliability target: >95% (NFR20)
        """
        # Check if already running
        existing = self.find_mt5()
        if existing:
            logger.info(f"MT5 already running: PID={existing.pid}")
            return existing

        logger.info("MT5 not running, starting new instance")

        # Start virtual display for headless operation
        xvfb_started = self.start_xvfb()

        # Find executable
        mt5_exe = self.find_mt5_executable()

        # Build Wine command with /portable flag
        # Portable mode keeps all MT5 data (config, profiles, login state)
        # in the terminal's installation folder rather than AppData
        wine_cmd = ["wine", mt5_exe, "/portable"]

        # Load MT5 credentials from ~/.env file
        # This bypasses MT5's "deleted due security" issue under Wine
        self._load_env_file()

        # Get credentials from environment (loaded from ~/.env or set directly)
        mt5_login = os.environ.get("MT5_LOGIN")
        mt5_password = os.environ.get("MT5_PASSWORD")
        mt5_server = os.environ.get("MT5_SERVER")

        if mt5_login:
            wine_cmd.append(f"/login:{mt5_login}")
            logger.info(f"Using MT5 login from environment: {mt5_login}")
        if mt5_password:
            wine_cmd.append(f"/password:{mt5_password}")
            logger.info("Using MT5 password from environment")
        if mt5_server:
            wine_cmd.append(f"/server:{mt5_server}")
            logger.info(f"Using MT5 server from environment: {mt5_server}")

        # Setup environment
        env = os.environ.copy()
        wine_prefix = self._get_wine_prefix()
        if wine_prefix:
            env["WINEPREFIX"] = wine_prefix

        # Use virtual display if Xvfb is running
        if xvfb_started or self.find_xvfb():
            env["DISPLAY"] = VIRTUAL_DISPLAY
            # Force X11 mode - unset Wayland variables to prevent Wine from
            # using XWayland on the user's display instead of our Xvfb
            env.pop("WAYLAND_DISPLAY", None)
            env.pop("XDG_SESSION_TYPE", None)
            logger.info(f"Using virtual display {VIRTUAL_DISPLAY} for MT5 (X11 mode)")
        else:
            logger.warning(
                "Xvfb not available - MT5 will display on current screen "
                "(install xvfb for headless operation)"
            )

        logger.debug(f"Starting MT5 with command: {' '.join(wine_cmd)}")
        logger.debug(f"Environment: DISPLAY={env.get('DISPLAY', 'not set')}")

        try:
            # Process reference unused - we use process detection to wait for ready
            subprocess.Popen(
                wine_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                start_new_session=True,
            )
        except OSError as e:
            logger.error(f"Failed to start Wine process: {e}")
            raise MT5LaunchError(
                f"Failed to launch MT5 via Wine: {e}. "
                "Ensure Wine is installed and accessible."
            ) from e

        # Wait for MT5 to be ready
        return self._wait_for_mt5_ready()

    def _wait_for_mt5_ready(self, timeout: float = 30.0) -> ProcessInfo:
        """Wait for MT5 process to become ready.

        Polls for MT5 process until it is detected and in 'running' status,
        or until timeout is reached.

        Args:
            timeout: Maximum time to wait in seconds. Default is 30 seconds.

        Returns:
            ProcessInfo for the ready MT5 process.

        Raises:
            MT5LaunchError: If MT5 doesn't become ready within timeout.

        Note:
            - Uses STARTUP_RETRY_DELAY between polls
            - Process must be in 'running' status to be considered ready
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            mt5_process = self.find_mt5()
            if mt5_process and mt5_process.status == "running":
                logger.info(f"MT5 ready: PID={mt5_process.pid}")
                return mt5_process

            time.sleep(STARTUP_RETRY_DELAY)

        # Timeout reached
        logger.error("MT5 did not start within timeout")
        raise MT5LaunchError(
            f"MT5 did not become ready within {timeout} seconds. "
            "Check Wine logs for errors. Ensure MT5 is properly installed."
        )

    # =========================================================================
    # Lifecycle Management Integration (Story 2.3)
    # =========================================================================

    def start_lifecycle_management(
        self,
        check_interval: float = 5.0,
    ) -> None:
        """Start lifecycle management for the rpyc server.

        Initializes and starts a LifecycleManager that monitors server health
        and automatically restarts the server if it crashes.

        Args:
            check_interval: Interval between health checks in seconds.
                Default is 5.0 seconds.

        Note:
            - Only one LifecycleManager can be active at a time
            - Call stop_lifecycle_management() to stop monitoring
            - Recovery success rate target is >95% (NFR13)
        """
        from mt5linux.lifecycle import LifecycleManager

        if self._lifecycle_manager is None:
            self._lifecycle_manager = LifecycleManager(
                self,
                check_interval=check_interval,
            )

        self._lifecycle_manager.start_monitoring()
        logger.info("Lifecycle management started")

    def stop_lifecycle_management(self) -> None:
        """Stop lifecycle management for the rpyc server.

        Stops the background monitoring thread gracefully. If no lifecycle
        manager is active, this method does nothing.
        """
        if self._lifecycle_manager is not None:
            self._lifecycle_manager.stop_monitoring()
            logger.info("Lifecycle management stopped")

    def get_lifecycle_status(self) -> Optional[Dict[str, Any]]:
        """Get current lifecycle management status.

        Returns the status of the lifecycle manager including monitoring
        state, current PID, failure counts, and restart counts.

        Returns:
            Dictionary with lifecycle status, or None if lifecycle
            management is not active.
        """
        if self._lifecycle_manager is None:
            return None

        return self._lifecycle_manager.get_status()

    def start_mt5_lifecycle(self, check_interval: float = 5.0) -> None:
        """Start MT5 lifecycle management.

        Initializes the lifecycle manager if needed and ensures MT5 is running.
        This integrates MT5 launch with the existing rpyc server lifecycle
        management.

        Args:
            check_interval: Interval between health checks in seconds.
                Default is 5.0 seconds.

        Note:
            - Creates LifecycleManager if not already initialized
            - Ensures MT5 is running via lifecycle manager
            - Coordinates with rpyc server lifecycle
        """
        from mt5linux.lifecycle import LifecycleManager

        if self._lifecycle_manager is None:
            self._lifecycle_manager = LifecycleManager(
                self,
                check_interval=check_interval,
            )

        # Ensure MT5 is running
        self._lifecycle_manager.ensure_mt5_running()
        logger.info("MT5 lifecycle management started")

    def get_mt5_status(self) -> Optional[Dict[str, Any]]:
        """Get current MT5 status from lifecycle manager.

        Returns MT5-specific status including the tracked MT5 PID.

        Returns:
            Dictionary with MT5 status including:
                - mt5_pid: Currently tracked MT5 process ID
                - monitoring_active: True if lifecycle monitoring is running
            Returns None if lifecycle management is not active.
        """
        if self._lifecycle_manager is None:
            return None

        # Get base lifecycle status
        status = self._lifecycle_manager.get_status()

        # Add MT5-specific fields
        status["mt5_pid"] = self._lifecycle_manager._mt5_pid

        return status
