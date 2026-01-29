"""Process detection and management module for mt5linux.

This module provides functionality to detect running rpyc server and MT5 processes,
and to start the rpyc server automatically when needed.

Process detection uses psutil for cross-platform process enumeration.
Detection must complete within 2 seconds (NFR8) with 100% accuracy (NFR19).
Server startup reliability must be >95% (NFR21).
"""

import os
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, List, Optional, Union

# Server startup retry configuration
STARTUP_MAX_RETRIES = 5
STARTUP_RETRY_DELAY = 1.0  # seconds
SOCKET_VERIFY_TIMEOUT = 2.0  # seconds

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

    def find_rpyc_server(self) -> Optional[ProcessInfo]:
        """Find running rpyc server process.

        Searches for Python processes that appear to be running an rpyc server
        by checking process names and command-line arguments.

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

        logger.debug("Searching for rpyc server process")
        try:
            return self._find_process_by_criteria(
                name_matches=PYTHON_PROCESS_NAMES,
                cmdline_patterns=RPYC_CMDLINE_PATTERNS,
                require_cmdline_match=True,
            )
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

        Checks if an rpyc server is already running and returns its info if so.
        Otherwise, starts a new rpyc server using the configured host and port.

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
        # Check if server is already running
        existing = self.find_rpyc_server()
        if existing:
            logger.info(
                f"rpyc server already running: PID={existing.pid}, using existing instance"
            )
            return existing

        logger.info("rpyc server not running, starting new instance")

        # Get configuration
        config = get_config() if get_config is not None else None
        if config:
            host = config.server.host
            port = config.server.port
            wine_prefix = config.wine.prefix_path
        else:
            host = "localhost"
            port = 18812
            wine_prefix = None

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

        # Setup environment with WINEPREFIX
        env = os.environ.copy()
        wine_prefix_path = self._get_wine_prefix()
        if wine_prefix_path:
            env["WINEPREFIX"] = wine_prefix_path

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
        except Exception:
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
