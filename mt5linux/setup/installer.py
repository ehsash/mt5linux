"""Installation functions for mt5linux dependencies."""

import json
import os
import platform
import re
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
except ImportError:
    Console = None  # type: ignore
    Progress = None  # type: ignore

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from mt5linux.detection import (ComponentInfo, DetectionResult, detect_mt5,
                                detect_python_windows, detect_wine,
                                detect_ydotool)

try:
    from mt5linux.security import download_file_secure, verify_download
except ImportError:
    download_file_secure = None  # type: ignore
    verify_download = None  # type: ignore

# Constants
WINDOWS_PYTHON_VERSION = "3.11.9"

# Initialize rich console if available
_console = Console() if Console else None


@dataclass
class InstallationResult:
    """Result of an installation operation."""

    component: str
    success: bool
    installed: bool  # True if installed, False if skipped (already installed)
    path: Optional[str] = None
    version: Optional[str] = None
    error: Optional[str] = None
    recovery_suggestion: Optional[str] = None


def _check_sudo_access() -> bool:
    """
    Check if the current user has sudo access (passwordless).

    Note: This checks for passwordless sudo. If passwordless sudo is not available,
    we can still use sudo by prompting the user for their password.

    Returns:
        True if user has passwordless sudo access, False otherwise
    """
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _configure_sudo_timeout(timeout_minutes: int = 15) -> bool:
    """
    Configure sudo password timeout to extend the duration before re-prompting.

    This creates a sudoers.d file to set timestamp_timeout, which extends
    how long sudo remembers the password after authentication.

    Args:
        timeout_minutes: Number of minutes before sudo re-prompts for password (default: 15)

    Returns:
        True if configuration was successful, False otherwise
    """
    logger.info(f"Configuring sudo password timeout to {timeout_minutes} minutes...")

    # Check if we can write to sudoers.d (requires sudo)
    sudoers_d_dir = "/etc/sudoers.d"
    config_file = os.path.join(sudoers_d_dir, "mt5linux-timeout")

    # First, check if sudo credentials are already cached (non-interactive check)
    # Then prompt for password if needed and we have a terminal
    try:
        # Check if sudo works without password (credentials already cached)
        check_cached = subprocess.run(
            ["sudo", "-n", "true"],
            timeout=5,
            capture_output=True,
        )
        if check_cached.returncode != 0:
            # Credentials not cached - need to prompt user
            import sys
            if sys.stdin.isatty():
                # We have a terminal, prompt for password
                # Use os.system() to ensure proper terminal interaction
                # (subprocess.run may not properly connect stdin in all contexts)
                if _console:
                    _console.print(
                        "  [yellow]Sudo password required for installation...[/yellow]"
                    )
                # Static command - safe to use os.system
                exit_code = os.system("sudo -v")  # nosec: static command
                if exit_code != 0:
                    logger.warning("Failed to cache sudo credentials")
                    return False
            else:
                # No terminal available - tell user to run sudo first
                logger.warning(
                    "No terminal available for sudo password prompt. "
                    "Please run 'sudo -v' in a terminal first to cache credentials."
                )
                if _console:
                    _console.print(
                        "  [red]No terminal for sudo prompt. Run 'sudo -v' first.[/red]"
                    )
                return False
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning(f"Could not validate sudo credentials: {e}")
        return False

    # Check if configuration already exists and matches
    try:
        # Now sudo credentials are cached, these won't prompt again
        check_result = subprocess.run(
            ["sudo", "test", "-f", config_file],
            timeout=5,
        )
        if check_result.returncode == 0:
            # File exists, read it with sudo
            read_result = subprocess.run(
                ["sudo", "cat", config_file],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if read_result.returncode == 0:
                existing_content = read_result.stdout
                if f"timestamp_timeout={timeout_minutes}" in existing_content:
                    logger.info(
                        f"Sudo timeout already configured to {timeout_minutes} minutes"
                    )
                    return True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Could not check existing sudo timeout config: {e}")

    # Create the sudoers configuration
    # Use Defaults with timestamp_timeout
    config_content = f"""# Sudo password timeout configuration for mt5linux
# This extends sudo password timeout to {timeout_minutes} minutes
# Generated automatically by mt5linux setup

Defaults timestamp_timeout={timeout_minutes}
"""

    try:
        # Write to a temporary file first
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".tmp"
        ) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(config_content)

        # Validate the sudoers file syntax before installing
        logger.info("Validating sudoers configuration syntax...")
        validate_result = subprocess.run(
            ["sudo", "visudo", "-c", "-f", tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if validate_result.returncode != 0:
            logger.warning(f"Sudoers validation failed: {validate_result.stderr}")
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return False

        # Copy the validated file to sudoers.d
        logger.info(f"Installing sudo timeout configuration to {config_file}...")
        install_result = subprocess.run(
            ["sudo", "cp", tmp_path, config_file],
            timeout=10,
        )

        # Set proper permissions (sudoers.d files should be 0440)
        if install_result.returncode == 0:
            subprocess.run(
                ["sudo", "chmod", "0440", config_file],
                timeout=5,
            )
            logger.info(
                f"Sudo password timeout configured to {timeout_minutes} minutes"
            )
            if _console:
                _console.print(
                    f"  [green]Sudo password timeout extended to {timeout_minutes} minutes[/green]"
                )
        else:
            logger.warning("Failed to install sudo timeout configuration")
            return False

        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        return True

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, Exception) as e:
        logger.warning(f"Could not configure sudo timeout: {e}")
        # Clean up temp file if it exists
        try:
            if "tmp_path" in locals():
                os.unlink(tmp_path)
        except OSError:
            pass
        return False


def _get_wine_path(
    wine_path: Optional[str] = None,
) -> Tuple[Optional[str], Optional[InstallationResult]]:
    """
    Get Wine path, detecting if not provided.

    Args:
        wine_path: Optional Wine executable path

    Returns:
        Tuple of (wine_path, error_result). If wine_path is None, error_result contains the error.
    """
    if wine_path:
        return wine_path, None

    wine_info = detect_wine()
    if not wine_info.found:
        error_msg = "Wine not found. Install Wine first."
        logger.error(error_msg)
        error_result = InstallationResult(
            component="wine",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Install Wine first using install_wine()",
        )
        return None, error_result

    return wine_info.path, None


def _fetch_windows_python_metadata(version: str) -> Dict[str, any]:
    """
    Fetch Windows Python metadata from python.org JSON API.

    Args:
        version: Python version (e.g., "3.11.9")

    Returns:
        Dictionary with 'url' and 'sha256' for the 64-bit installer

    Raises:
        Exception if metadata cannot be fetched or parsed
    """
    json_url = f"https://www.python.org/ftp/python/{version}/windows-{version}.json"
    logger.info(f"Fetching Windows Python metadata from {json_url}")

    try:
        if requests:
            response = requests.get(json_url, timeout=30)
            response.raise_for_status()
            metadata = response.json()
        else:
            # Fallback to urllib if requests not available
            with urllib.request.urlopen(json_url, timeout=30) as response:
                metadata = json.loads(response.read().decode())

        # Find the 64-bit Python installer entry
        # The JSON provides .zip files, but we need the .exe installer
        # Construct the .exe URL and signature URLs from the version
        exe_url = (
            f"https://www.python.org/ftp/python/{version}/python-{version}-amd64.exe"
        )
        signature_url = f"https://www.python.org/ftp/python/{version}/python-{version}-amd64.exe.asc"

        # Python.org provides GPG signature files (.asc) for .exe installers
        # We can use GPG verification instead of SHA256
        # Return URL and signature URL for GPG verification
        logger.info(f"Using Windows Python 64-bit installer: {exe_url}")
        logger.info(f"GPG signature available at: {signature_url}")
        return {"url": exe_url, "sha256": None, "signature_url": signature_url}
    except Exception as e:
        logger.error(f"Failed to fetch Windows Python metadata: {e}")
        raise


def _detect_linux_distribution() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Detect Linux distribution, package manager, and codename.

    Returns:
        Tuple of (distribution_id, package_manager, codename) or (None, None, None) if unknown
    """
    try:
        codename = None
        dist_id = None
        package_manager = None

        # Try /etc/os-release first (most reliable)
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as f:
                content = f.read()
                # Extract distribution ID
                for line in content.split("\n"):
                    if line.startswith("ID="):
                        dist_id = line.split("=", 1)[1].strip().strip('"').lower()
                    elif line.startswith("VERSION_CODENAME="):
                        codename = line.split("=", 1)[1].strip().strip('"').lower()
                    elif line.startswith("UBUNTU_CODENAME="):
                        codename = line.split("=", 1)[1].strip().strip('"').lower()

                # Determine package manager
                if dist_id in ["ubuntu", "debian", "linuxmint", "mint"]:
                    package_manager = "apt"
                    if dist_id == "linuxmint":
                        dist_id = "ubuntu"  # Mint uses Ubuntu repositories
                elif dist_id == "fedora":
                    package_manager = "dnf"
                elif dist_id in ["rhel", "centos"]:
                    package_manager = "yum"

        # Fallback to platform if needed
        if not dist_id:
            dist = (
                platform.linux_distribution()[0].lower()
                if hasattr(platform, "linux_distribution")
                else None
            )
            if dist:
                if any(x in dist for x in ["ubuntu", "debian", "mint"]):
                    dist_id = (
                        "ubuntu" if "ubuntu" in dist or "mint" in dist else "debian"
                    )
                    package_manager = "apt"
                elif "fedora" in dist:
                    dist_id = "fedora"
                    package_manager = "dnf"

        if dist_id and package_manager:
            logger.info(
                f"Detected distribution: {dist_id}, package manager: {package_manager}, codename: {codename}"
            )
            return (dist_id, package_manager, codename)

        logger.warning("Could not detect Linux distribution")
        return (None, None, None)
    except Exception as e:
        logger.warning(f"Error detecting Linux distribution: {e}")
        return (None, None, None)


def _disable_wine_debugger_detection(
    wine_path: str, wine_prefix: Optional[str] = None
) -> bool:
    """
    Disable Wine's debugger detection to prevent "debugger detected" errors.

    Wine has anti-debugging features that can detect debuggers (gdb, strace, etc.)
    and refuse to run applications. This function disables that check.

    Args:
        wine_path: Path to Wine executable
        wine_prefix: Optional Wine prefix path

    Returns:
        True if successful, False otherwise
    """
    logger.info("Disabling Wine debugger detection...")

    # Set up environment
    env = os.environ.copy()
    if wine_prefix:
        env["WINEPREFIX"] = wine_prefix
    env["WINEDEBUG"] = "-all"

    try:
        # Method 1: Initialize Wine prefix first if it doesn't exist
        # This ensures the registry is available
        if wine_prefix and not os.path.exists(os.path.join(wine_prefix, "system.reg")):
            logger.debug("Initializing Wine prefix for debugger detection fix...")
            try:
                init_result = subprocess.run(
                    [wine_path, "wineboot", "--init"],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    stdin=subprocess.DEVNULL,
                )
                if init_result.returncode != 0:
                    logger.debug(
                        f"Wine prefix initialization had issues: {init_result.stderr}"
                    )
            except Exception as e:
                logger.debug(f"Wine prefix initialization failed: {e}")

        # Method 2: Set registry key to disable debugger detection
        # Try the Wine-specific debug registry key first
        reg_keys = [
            "HKEY_LOCAL_MACHINE\\Software\\Wine\\Debug",
            "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Services\\WineDebugger",
        ]

        for reg_key in reg_keys:
            try:
                # Try to set a registry value that disables debugger checks
                # Setting "Debugger" to empty or "0" can help
                result = subprocess.run(
                    [
                        wine_path,
                        "reg",
                        "add",
                        reg_key,
                        "/v",
                        "Debugger",
                        "/t",
                        "REG_SZ",
                        "/d",
                        "",
                        "/f",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    stdin=subprocess.DEVNULL,
                )

                if result.returncode == 0:
                    logger.info(
                        f"Wine debugger detection disabled via registry key: {reg_key}"
                    )
                    return True
            except Exception as e:
                logger.debug(f"Failed to set registry key {reg_key}: {e}")
                continue

        # Method 3: If registry methods fail, log a warning but continue
        # The environment variable WINEDEBUG=-all should help suppress some issues
        logger.debug(
            "Registry methods for disabling debugger detection failed, continuing with WINEDEBUG=-all"
        )
        return True

    except Exception as e:
        logger.warning(f"Could not disable Wine debugger detection: {e}")
        # Non-fatal, continue anyway - WINEDEBUG=-all should still help
        return False


def _configure_wine_virtual_desktop(
    wine_path: str,
    wine_prefix: str,
    resolution: str = "1920x1080",
) -> bool:
    """
    Configure Wine virtual desktop mode.

    On Wayland, Wine runs through XWayland, but mouse cursor and keyboard input
    are often broken. Enabling Wine's virtual desktop mode fixes input handling
    by creating a dedicated Wine-managed window that captures events correctly.

    Args:
        wine_path: Path to Wine executable
        wine_prefix: Wine prefix path
        resolution: Virtual desktop resolution (default: 1920x1080)

    Returns:
        True if configured successfully, False otherwise
    """
    logger.info(
        f"Configuring Wine virtual desktop ({resolution}) for input compatibility"
    )

    env = os.environ.copy()
    env["WINEPREFIX"] = wine_prefix
    env["WINEDEBUG"] = "-all"

    try:
        # Set the desktop resolution
        result = subprocess.run(
            [
                wine_path,
                "reg",
                "add",
                "HKCU\\Software\\Wine\\Explorer\\Desktops",
                "/v",
                "Default",
                "/t",
                "REG_SZ",
                "/d",
                resolution,
                "/f",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            logger.warning(f"Failed to set virtual desktop resolution: {result.stderr}")
            return False

        # Activate the virtual desktop
        result = subprocess.run(
            [
                wine_path,
                "reg",
                "add",
                "HKCU\\Software\\Wine\\Explorer",
                "/v",
                "Desktop",
                "/t",
                "REG_SZ",
                "/d",
                "Default",
                "/f",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            logger.warning(f"Failed to activate virtual desktop: {result.stderr}")
            return False

        logger.info("Wine virtual desktop configured successfully")
        return True

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning(f"Failed to configure Wine virtual desktop: {e}")
        return False


def _install_wine_packages(wine_path: str, wine_prefix: Optional[str] = None) -> bool:
    """
    Install Wine packages (mono, gecko) automatically.

    Args:
        wine_path: Path to Wine executable
        wine_prefix: Optional Wine prefix path

    Returns:
        True if successful, False otherwise
    """
    logger.info("Installing Wine packages (mono, gecko)...")

    # Disable Wine debugger detection to prevent "debugger detected" errors
    _disable_wine_debugger_detection(wine_path, wine_prefix)

    # Set up environment
    env = os.environ.copy()
    if wine_prefix:
        env["WINEPREFIX"] = wine_prefix
    # Prevent Wine from prompting for mono/gecko
    env["WINEDLLOVERRIDES"] = "mscoree,mshtml="

    # Try winetricks first (most reliable)
    winetricks_path = shutil.which("winetricks")
    if winetricks_path:
        try:
            logger.info("Using winetricks to install mono and gecko...")
            # Suppress winetricks warnings about 64-bit WINEPREFIX and wow64 mode
            # These are just warnings, not errors, and can be safely ignored
            # Use -q for quiet mode and ensure no stdin to prevent any prompts
            result = subprocess.run(
                [winetricks_path, "-q", "mono", "gecko"],
                env=env,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes
                stdin=subprocess.DEVNULL,  # Ensure no stdin input
            )
            if result.returncode == 0:
                logger.info("Wine packages installed successfully via winetricks")
                return True
            else:
                # Check if it's just warnings (which are non-fatal)
                stderr_lower = result.stderr.lower() if result.stderr else ""
                if "warning" in stderr_lower and (
                    "64-bit" in stderr_lower or "wow64" in stderr_lower
                ):
                    # These are just warnings about 64-bit prefix, installation may have succeeded
                    logger.info(
                        "Wine packages installation completed (warnings about 64-bit prefix can be ignored)"
                    )
                    return True
                logger.warning(f"winetricks failed: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.warning(f"winetricks execution failed: {e}")

    # Fallback: Initialize Wine prefix which will trigger package installation
    # Wine will auto-download mono/gecko if configured properly
    try:
        logger.info("Initializing Wine prefix to trigger package installation...")
        result = subprocess.run(
            [wine_path, "wineboot", "--init"],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("Wine prefix initialized, packages should be available")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning(f"Wine prefix initialization failed: {e}")

    logger.warning("Could not install Wine packages automatically")
    return False


def _check_ydotoold_running() -> bool:
    """
    Check if ydotoold daemon is currently running.

    Uses multiple methods to detect the process:
    1. pgrep -x ydotoold (exact match)
    2. ps aux | grep ydotoold (broader search)
    3. Check for ydotoold in process list

    Returns:
        True if daemon is running, False otherwise
    """
    # Method 1: pgrep (exact match)
    try:
        result = subprocess.run(
            ["pgrep", "-x", "ydotoold"],
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Method 2: ps + grep (broader search, handles process name variations)
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and "ydotoold" in result.stdout:
            # Filter out grep itself
            lines = [
                line
                for line in result.stdout.split("\n")
                if "ydotoold" in line and "grep" not in line
            ]
            if lines:
                return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Method 3: Check process list via /proc
    try:
        # List all processes and check for ydotoold
        proc_dir = "/proc"
        if os.path.exists(proc_dir):
            for pid in os.listdir(proc_dir):
                if not pid.isdigit():
                    continue
                try:
                    cmdline_path = os.path.join(proc_dir, pid, "cmdline")
                    if os.path.exists(cmdline_path):
                        with open(cmdline_path, "rb") as f:
                            cmdline = f.read().decode("utf-8", errors="ignore")
                            if "ydotoold" in cmdline:
                                return True
                except (OSError, IOError):
                    continue
    except (OSError, IOError):
        pass

    return False


def _start_ydotoold_daemon() -> bool:
    """
    Start the ydotoold daemon if it's not already running.

    Tries multiple methods:
    1. systemctl start ydotoold (if systemd is available)
    2. Run ydotoold directly as a background process

    Returns:
        True if daemon was started or is already running, False otherwise
    """
    # First check if ydotoold is already running
    if _check_ydotoold_running():
        logger.info("ydotoold daemon is already running")
        return True

    # Check if sudo credentials are available before attempting sudo operations
    try:
        check_cached = subprocess.run(
            ["sudo", "-n", "true"],
            timeout=5,
            capture_output=True,
        )
        if check_cached.returncode != 0:
            # Credentials not cached - check if we have a terminal
            import sys
            if sys.stdin.isatty():
                if _console:
                    _console.print(
                        "  [yellow]Sudo password required for ydotoold...[/yellow]"
                    )
                # Static command - safe to use os.system for proper terminal interaction
                exit_code = os.system("sudo -v")  # nosec: static command
                if exit_code != 0:
                    logger.warning("Failed to cache sudo credentials for ydotoold")
                    return False
            else:
                logger.warning(
                    "Sudo credentials not cached and no terminal available. "
                    "Run 'sudo -v' first or start ydotoold manually."
                )
                return False
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning(f"Could not check sudo credentials for ydotoold: {e}")
        return False

    # Try to start via systemctl first (preferred method, but only if service exists)
    try:
        # Check if the service exists first
        check_service = subprocess.run(
            ["systemctl", "list-unit-files", "--type=service", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        service_exists = False
        if check_service.returncode == 0 and "ydotoold.service" in check_service.stdout:
            service_exists = True

        if service_exists:
            logger.info("Attempting to start ydotoold daemon via systemctl...")
            result = subprocess.run(
                ["sudo", "systemctl", "start", "ydotoold"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Wait and retry checking multiple times (daemon may take time to start)
                for attempt in range(5):
                    time.sleep(
                        1 + attempt * 0.5
                    )  # Increasing wait: 1s, 1.5s, 2s, 2.5s, 3s
                    if _check_ydotoold_running():
                        logger.info(
                            "ydotoold daemon started successfully via systemctl"
                        )
                        return True
                logger.warning(
                    "systemctl start succeeded but daemon not detected after retries"
                )
            else:
                # Check if it's a "service not found" error - if so, skip to direct execution
                if (
                    "not found" in result.stderr.lower()
                    or "Unit.*not found" in result.stderr
                ):
                    logger.info(
                        "ydotoold systemd service not found, will try direct execution"
                    )
                else:
                    logger.warning(f"systemctl start failed: {result.stderr}")
        else:
            logger.info(
                "ydotoold systemd service not available, will try direct execution"
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"systemctl check failed: {e}, will try direct execution")

    # Fallback: try to run ydotoold directly
    ydotoold_path = shutil.which("ydotoold")
    if not ydotoold_path:
        logger.warning("ydotoold executable not found in PATH")
        return False

    try:
        logger.info(f"Attempting to start ydotoold daemon directly: {ydotoold_path}")
        # Run ydotoold in background (requires sudo for input device access)
        # Don't use start_new_session as it breaks sudo credential inheritance
        # Use stdin=DEVNULL to detach from input while keeping terminal access for sudo
        process = subprocess.Popen(
            ["sudo", ydotoold_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,  # Capture stderr to check for errors
            stdin=subprocess.DEVNULL,  # Detach from stdin
        )

        # Give it a moment to start
        time.sleep(0.5)

        # Check if process immediately failed
        if process.poll() is not None:
            # Process exited immediately - likely an error
            stderr_output = (
                process.stderr.read().decode("utf-8", errors="ignore")
                if process.stderr
                else ""
            )
            logger.warning(
                f"ydotoold process exited immediately with code {process.returncode}"
            )
            if stderr_output:
                logger.warning(f"ydotoold stderr: {stderr_output[:200]}")
            return False

        # Wait and retry checking multiple times (process may take time to initialize)
        for attempt in range(5):
            time.sleep(1 + attempt * 0.5)  # Increasing wait: 1s, 1.5s, 2s, 2.5s, 3s

            # Check if process is still alive
            if process.poll() is not None:
                # Process died
                stderr_output = (
                    process.stderr.read().decode("utf-8", errors="ignore")
                    if process.stderr
                    else ""
                )
                logger.warning(
                    f"ydotoold process exited with code {process.returncode}"
                )
                if stderr_output:
                    logger.warning(f"ydotoold stderr: {stderr_output[:200]}")
                return False

            # Check if daemon is detected by name
            if _check_ydotoold_running():
                logger.info("ydotoold daemon started successfully (direct execution)")
                return True

        # Process is still running but not detected by name - assume success
        if process.poll() is None:
            logger.info(
                "ydotoold process is running (detected via process status, name detection may be delayed)"
            )
            return True
        else:
            logger.warning(f"ydotoold process exited with code: {process.returncode}")
            return False

    except (FileNotFoundError, OSError) as e:
        logger.warning(f"Failed to start ydotoold directly: {e}")
        return False

    # Final check - maybe it started but our detection missed it
    if _check_ydotoold_running():
        logger.info("ydotoold daemon is running (detected on final check)")
        return True

    logger.warning("Could not start ydotoold daemon automatically")
    return False


def _install_mt5_wine_dependencies(
    wine_path: str, wine_prefix: Optional[str] = None
) -> bool:
    """
    Install additional Wine dependencies required for MT5.

    MT5 requires:
    - Visual C++ runtimes (vcrun2010, vcrun2012, vcrun2013, vcrun2015)
    - Core fonts for better UI rendering
    - MSXML for XML parsing

    Args:
        wine_path: Path to Wine executable
        wine_prefix: Optional Wine prefix path

    Returns:
        True if successful, False otherwise
    """
    logger.info("Installing MT5-specific Wine dependencies...")

    # Set up environment
    env = os.environ.copy()
    if wine_prefix:
        env["WINEPREFIX"] = wine_prefix
    env["WINEDLLOVERRIDES"] = "mscoree,mshtml="

    # Ensure DISPLAY is set for Wayland
    if not env.get("DISPLAY"):
        wayland_display = os.environ.get("WAYLAND_DISPLAY")
        xdg_session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if wayland_display or xdg_session_type == "wayland":
            env["DISPLAY"] = ":0"  # XWayland default
            logger.info("Setting DISPLAY=:0 for Wayland")

    winetricks_path = shutil.which("winetricks")
    if not winetricks_path:
        logger.warning("winetricks not found, skipping MT5 dependencies")
        return False

    # Install Visual C++ runtimes (required by MT5)
    # MT5 typically needs vcrun2010, vcrun2012, vcrun2013, and vcrun2015
    vcrun_packages = ["vcrun2010", "vcrun2012", "vcrun2013", "vcrun2015"]

    # Also install core fonts for better UI rendering
    # winhttp is CRITICAL for MT5 - enables HTTPS downloads from MetaQuotes servers
    additional_packages = ["corefonts", "winhttp"]

    all_packages = vcrun_packages + additional_packages

    try:
        logger.info(
            f"Installing MT5 dependencies via winetricks: {', '.join(all_packages)}"
        )
        # Use -q for quiet mode
        result = subprocess.run(
            [winetricks_path, "-q"] + all_packages,
            env=env,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes (VC++ runtimes can take a while)
            stdin=subprocess.DEVNULL,
        )

        if result.returncode == 0:
            logger.info("MT5 Wine dependencies installed successfully")
            return True
        else:
            # Check if it's just warnings
            stderr_lower = result.stderr.lower() if result.stderr else ""
            if "warning" in stderr_lower:
                logger.info(
                    "MT5 dependencies installation completed (warnings can be ignored)"
                )
                return True
            logger.warning(
                f"winetricks MT5 dependencies installation had issues: {result.stderr[:500]}"
            )
            # Continue anyway - some packages might have installed
            return True
    except subprocess.TimeoutExpired:
        logger.warning("MT5 dependencies installation timed out, continuing anyway")
        return True  # Continue - some packages might have installed
    except Exception as e:
        logger.warning(f"Failed to install MT5 dependencies: {e}, continuing anyway")
        return True  # Non-fatal - continue installation


def install_wine(
    detection_result: Optional[DetectionResult] = None,
) -> InstallationResult:
    """
    Install Wine using system package manager (apt for Ubuntu).

    Args:
        detection_result: Optional DetectionResult to check if Wine is already installed

    Returns:
        InstallationResult with installation status
    """
    logger.info("Starting Wine installation")

    # Check if Wine is already installed
    if detection_result:
        if detection_result.wine.found:
            logger.info(f"Wine already installed at {detection_result.wine.path}")
            return InstallationResult(
                component="wine",
                success=True,
                installed=False,  # Skipped - already installed
                path=detection_result.wine.path,
                version=detection_result.wine.version,
            )
    else:
        # Re-detect to be sure
        wine_info = detect_wine()
        if wine_info.found:
            logger.info(f"Wine already installed at {wine_info.path}")
            return InstallationResult(
                component="wine",
                success=True,
                installed=False,
                path=wine_info.path,
                version=wine_info.version,
            )

    # Check sudo access
    if not _check_sudo_access():
        error_msg = "Sudo access required to install Wine"
        logger.error(error_msg)
        return InstallationResult(
            component="wine",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Run with sudo or ensure user has sudo access",
        )

    # Detect distribution to set up WineHQ repository correctly
    dist_id, package_manager, codename = _detect_linux_distribution()

    # Install Wine Staging from WineHQ repository
    try:
        # Only support apt-based systems (Ubuntu/Debian) for WineHQ repository
        if package_manager != "apt":
            error_msg = (
                f"WineHQ repository only supports Ubuntu/Debian. Detected: {dist_id}"
            )
            logger.error(error_msg)
            return InstallationResult(
                component="wine",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Install Wine manually or use a supported distribution (Ubuntu/Debian)",
            )

        # Step 1: Enable 32-bit architecture (required for WineHQ)
        if _console:
            _console.print("  [cyan]Enabling 32-bit architecture...[/cyan]")
        logger.info("Enabling 32-bit architecture for WineHQ...")
        arch_result = subprocess.run(
            ["sudo", "dpkg", "--add-architecture", "i386"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if arch_result.returncode != 0:
            logger.warning(
                f"dpkg --add-architecture failed (may already be enabled): {arch_result.stderr}"
            )

        # Step 2: Create keyrings directory and add WineHQ GPG key
        if _console:
            _console.print("  [cyan]Adding WineHQ repository key...[/cyan]")
        logger.info("Adding WineHQ GPG key...")

        # Create keyrings directory
        subprocess.run(
            ["sudo", "mkdir", "-pm755", "/etc/apt/keyrings"],
            capture_output=True,
            timeout=10,
        )

        # Download and add GPG key
        key_url = "https://dl.winehq.org/wine-builds/winehq.key"
        key_path = "/etc/apt/keyrings/winehq-archive.key"

        try:
            if requests:
                key_response = requests.get(key_url, timeout=30)
                key_response.raise_for_status()
                key_data = key_response.content
            else:
                with urllib.request.urlopen(key_url, timeout=30) as response:
                    key_data = response.read()

            # Import key using gpg --dearmor
            gpg_process = subprocess.run(
                ["sudo", "gpg", "--dearmor", "-o", key_path],
                input=key_data,
                capture_output=True,
                timeout=30,
            )
            if gpg_process.returncode != 0:
                error_msg = f"Failed to add WineHQ GPG key: {gpg_process.stderr}"
                logger.error(error_msg)
                return InstallationResult(
                    component="wine",
                    success=False,
                    installed=False,
                    error=error_msg,
                    recovery_suggestion="Check internet connection and gpg availability",
                )
            logger.info("WineHQ GPG key added successfully")
        except Exception as e:
            error_msg = f"Failed to download/add WineHQ GPG key: {e}"
            logger.error(error_msg)
            return InstallationResult(
                component="wine",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and try again",
            )

        # Step 3: Add WineHQ repository
        if _console:
            _console.print("  [cyan]Adding WineHQ repository...[/cyan]")
        logger.info("Adding WineHQ repository...")

        # Determine repository URL based on distribution
        repo_url = None
        if dist_id == "ubuntu":
            if codename:
                # Map Ubuntu codenames to repository paths
                codename_map = {
                    "noble": "noble",
                    "jammy": "jammy",
                    "focal": "focal",
                    "bionic": "bionic",
                }
                if codename in codename_map:
                    repo_url = f"https://dl.winehq.org/wine-builds/ubuntu/dists/{codename_map[codename]}/winehq-{codename_map[codename]}.sources"
                else:
                    # Try to use codename directly
                    repo_url = f"https://dl.winehq.org/wine-builds/ubuntu/dists/{codename}/winehq-{codename}.sources"
            if not repo_url:
                # Fallback to jammy (Ubuntu 22.04)
                logger.warning(
                    "Could not determine Ubuntu codename, using jammy (22.04)"
                )
                repo_url = "https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources"
        elif dist_id == "debian":
            if codename:
                codename_map = {
                    "bookworm": "bookworm",
                    "bullseye": "bullseye",
                    "buster": "buster",
                }
                if codename in codename_map:
                    repo_url = f"https://dl.winehq.org/wine-builds/debian/dists/{codename_map[codename]}/winehq-{codename_map[codename]}.sources"
                else:
                    repo_url = f"https://dl.winehq.org/wine-builds/debian/dists/{codename}/winehq-{codename}.sources"
            if not repo_url:
                # Fallback to bookworm (Debian 12)
                logger.warning(
                    "Could not determine Debian codename, using bookworm (12)"
                )
                repo_url = "https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources"

        if not repo_url:
            error_msg = f"Could not determine WineHQ repository URL for {dist_id}"
            logger.error(error_msg)
            return InstallationResult(
                component="wine",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Install Wine manually or check distribution compatibility",
            )

        # Download repository sources file
        sources_path = f"/etc/apt/sources.list.d/winehq-{codename or 'default'}.sources"
        try:
            if requests:
                repo_response = requests.get(repo_url, timeout=30)
                repo_response.raise_for_status()
                repo_content = repo_response.text
            else:
                with urllib.request.urlopen(repo_url, timeout=30) as response:
                    repo_content = response.read().decode()

            # Ensure the repository file references the correct keyring path
            # Modern .sources files should have: Signed-By=/etc/apt/keyrings/winehq-archive.key
            if "Signed-By" not in repo_content:
                # Add Signed-By line if missing (for older format files)
                lines = repo_content.split("\n")
                updated_lines = []
                for line in lines:
                    updated_lines.append(line)
                    if line.strip().startswith(
                        "URIs="
                    ) and "Signed-By" not in "\n".join(updated_lines):
                        # Add Signed-By after URIs line
                        updated_lines.append(f"Signed-By={key_path}")
                repo_content = "\n".join(updated_lines)

            # Write repository file
            with open("/tmp/winehq.sources", "w") as f:
                f.write(repo_content)

            copy_result = subprocess.run(
                ["sudo", "cp", "/tmp/winehq.sources", sources_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if copy_result.returncode != 0:
                error_msg = f"Failed to add WineHQ repository: {copy_result.stderr}"
                logger.error(error_msg)
                return InstallationResult(
                    component="wine",
                    success=False,
                    installed=False,
                    error=error_msg,
                    recovery_suggestion="Check sudo permissions and try again",
                )
            logger.info(f"WineHQ repository added: {sources_path}")

            # Clean up temp file
            try:
                os.remove("/tmp/winehq.sources")
            except OSError:
                pass
        except Exception as e:
            error_msg = f"Failed to download/add WineHQ repository: {e}"
            logger.error(error_msg)
            return InstallationResult(
                component="wine",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and try again",
            )

        # Step 4: Update package list
        if _console:
            _console.print("  [cyan]Updating package list...[/cyan]")
        logger.info("Updating package list with WineHQ repository...")
        update_result = subprocess.run(
            ["sudo", "apt", "update"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )
        if update_result.returncode != 0:
            error_msg = f"apt update failed: {update_result.stderr}"
            logger.error(error_msg)
            return InstallationResult(
                component="wine",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and apt configuration",
            )

        # Step 5: Check if default wine package is installed and remove it if needed
        # WineHQ's winehq-staging conflicts with the default wine package
        check_wine_result = subprocess.run(
            ["dpkg", "-l", "wine"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if check_wine_result.returncode == 0 and "wine" in check_wine_result.stdout:
            logger.info("Default wine package detected, removing to avoid conflicts...")
            if _console:
                _console.print(
                    "  [yellow]Removing default wine package (will install WineHQ Staging)...[/yellow]"
                )
            remove_result = subprocess.run(
                ["sudo", "apt", "remove", "--purge", "-y", "wine", "wine*"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if remove_result.returncode != 0:
                logger.warning(
                    f"Failed to remove default wine package: {remove_result.stderr}"
                )
                logger.warning("Continuing with WineHQ installation anyway...")

        # Step 6: Install Wine Staging
        if _console:
            _console.print(
                "  [cyan]Installing Wine Staging from WineHQ (this may take several minutes)...[/cyan]"
            )
        logger.info("Installing Wine Staging from WineHQ repository...")
        install_result = subprocess.run(
            ["sudo", "apt", "install", "--install-recommends", "-y", "winehq-staging"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes timeout
        )
        if install_result.returncode != 0:
            error_msg = f"Wine Staging installation failed: {install_result.stderr}"
            logger.error(error_msg)
            # Check if it's a conflict error
            if (
                "wine" in install_result.stderr.lower()
                and "conflict" in install_result.stderr.lower()
            ):
                recovery = (
                    "Wine package conflict detected. Try manually removing the default wine package first: "
                    "sudo apt remove --purge wine wine* && sudo apt autoremove"
                )
            else:
                recovery = "Check apt logs: /var/log/apt/history.log"
            return InstallationResult(
                component="wine",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion=recovery,
            )

        # Verify installation
        if _console:
            _console.print("  [cyan]Verifying Wine installation...[/cyan]")
        wine_info = detect_wine()
        if wine_info.found:
            if _console:
                _console.print(
                    f"  [bold green]Wine installed successfully:[/bold green] {wine_info.version}"
                )
            logger.info(f"Wine successfully installed at {wine_info.path}")
            return InstallationResult(
                component="wine",
                success=True,
                installed=True,
                path=wine_info.path,
                version=wine_info.version,
            )
        else:
            error_msg = "Wine installation completed but verification failed"
            logger.error(error_msg)
            return InstallationResult(
                component="wine",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Try running 'wine --version' manually to verify installation",
            )

    except subprocess.TimeoutExpired as e:
        error_msg = f"Wine installation timed out: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="wine",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Installation may still be in progress. Check system processes.",
        )
    except (FileNotFoundError, OSError) as e:
        error_msg = f"Error during Wine installation: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="wine",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Ensure apt is available and system is up to date",
        )


def install_windows_python(
    wine_path: Optional[str] = None,
    wine_prefix: Optional[str] = None,
    detection_result: Optional[DetectionResult] = None,
) -> InstallationResult:
    """
    Install Windows Python via Wine.

    Args:
        wine_path: Path to Wine executable (optional, will detect if not provided)
        wine_prefix: Optional Wine prefix path (defaults to .mt5 in current directory)
        detection_result: Optional DetectionResult to check if Windows Python is already installed

    Returns:
        InstallationResult with installation status
    """
    logger.info("Starting Windows Python installation")

    # Check if Windows Python is already installed
    if detection_result:
        if detection_result.python_windows.found:
            logger.info(
                f"Windows Python already installed at {detection_result.python_windows.path}"
            )
            return InstallationResult(
                component="python-windows",
                success=True,
                installed=False,  # Skipped - already installed
                path=detection_result.python_windows.path,
                version=detection_result.python_windows.version,
            )
    else:
        # Re-detect to be sure
        wine_path_result, error_result = _get_wine_path(wine_path)
        if error_result:
            return error_result
        wine_path = wine_path_result

        python_info = detect_python_windows(wine_path)
        if python_info.found:
            logger.info(f"Windows Python already installed at {python_info.path}")
            return InstallationResult(
                component="python-windows",
                success=True,
                installed=False,
                path=python_info.path,
                version=python_info.version,
            )

    # Get Wine path if not provided
    wine_path_result, error_result = _get_wine_path(wine_path)
    if error_result:
        return error_result
    wine_path = wine_path_result

    installer_path = "/tmp/python-installer.exe"

    try:
        # Fetch metadata from JSON
        if _console:
            _console.print(
                f"  [cyan]Fetching Windows Python {WINDOWS_PYTHON_VERSION} metadata...[/cyan]"
            )
        try:
            metadata = _fetch_windows_python_metadata(WINDOWS_PYTHON_VERSION)
            python_url = metadata["url"]
            python_sha256 = metadata.get("sha256")  # May be None
            signature_url = metadata.get("signature_url")  # GPG signature URL
        except Exception as e:
            error_msg = f"Failed to fetch Windows Python metadata: {e}"
            logger.error(error_msg)
            if _console:
                _console.print(f"  [bold red]Error:[/bold red] {error_msg}")
            return InstallationResult(
                component="python-windows",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and try again",
            )

        # Download file and GPG signature, then verify using GPG
        if _console:
            _console.print(
                f"  [cyan]Downloading Windows Python {WINDOWS_PYTHON_VERSION} installer...[/cyan]"
            )
        logger.info(f"Downloading Windows Python installer from {python_url}...")

        try:
            # Download file directly
            urllib.request.urlretrieve(python_url, installer_path)
            logger.info("Windows Python installer downloaded successfully")
        except Exception as e:
            error_msg = f"Failed to download Windows Python installer: {e}"
            logger.error(error_msg)
            if _console:
                _console.print(f"  [bold red]Download failed:[/bold red] {error_msg}")
            return InstallationResult(
                component="python-windows",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and try again",
            )

        # Verify using GPG signature if available
        # Note: signature_url is set from metadata above
        if signature_url and verify_download is not None:
            if _console:
                _console.print("  [cyan]Downloading GPG signature...[/cyan]")
            signature_path = installer_path + ".asc"
            try:
                urllib.request.urlretrieve(signature_url, signature_path)
                logger.info("GPG signature downloaded successfully")

                # Extract and import GPG key IDs from the signature file dynamically
                def extract_key_ids_from_signature(sig_path: str) -> List[str]:
                    """Extract key IDs from a GPG signature file."""
                    key_ids = []
                    try:
                        # First, check if the signature file is valid by reading it
                        with open(sig_path, "rb") as f:
                            sig_data = f.read()
                        if not sig_data or len(sig_data) < 100:
                            logger.warning(
                                f"Signature file seems too small: {len(sig_data)} bytes"
                            )
                            return []

                        # Use gpg --list-packets to extract key ID from signature
                        # Try without --no-default-keyring first to see if we get better output
                        result = subprocess.run(
                            ["gpg", "--list-packets", sig_path],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if result.returncode == 0 and result.stdout:
                            logger.debug(
                                f"GPG list-packets output: {result.stdout[:500]}"
                            )
                            # Parse output for key IDs (format: "keyid" or "issuer keyid")
                            # Look for patterns like "keyid 64E628F8D684696D" or "issuer keyid 64E628F8D684696D"
                            matches = re.findall(
                                r"(?:issuer\s+)?keyid\s+([0-9A-F]{16,40})",
                                result.stdout,
                                re.IGNORECASE,
                            )
                            key_ids.extend(matches)
                            # Also look for key IDs in hex format (16 or 40 chars)
                            hex_matches = re.findall(
                                r"\b([0-9A-F]{16,40})\b", result.stdout
                            )
                            # Filter to reasonable key ID lengths (16 chars for short, 40 for full fingerprint)
                            key_ids.extend(
                                [
                                    k
                                    for k in hex_matches
                                    if len(k) in [16, 40] and k not in key_ids
                                ]
                            )
                        elif result.stderr:
                            logger.debug(
                                f"GPG list-packets stderr: {result.stderr[:500]}"
                            )

                        # If that didn't work, try with --no-default-keyring
                        if not key_ids:
                            result2 = subprocess.run(
                                [
                                    "gpg",
                                    "--list-packets",
                                    "--no-default-keyring",
                                    "--keyring",
                                    "/dev/null",
                                    sig_path,
                                ],
                                capture_output=True,
                                text=True,
                                timeout=10,
                            )
                            if result2.returncode == 0 and result2.stdout:
                                matches = re.findall(
                                    r"(?:issuer\s+)?keyid\s+([0-9A-F]{16,40})",
                                    result2.stdout,
                                    re.IGNORECASE,
                                )
                                key_ids.extend(matches)
                                hex_matches = re.findall(
                                    r"\b([0-9A-F]{16,40})\b", result2.stdout
                                )
                                key_ids.extend(
                                    [
                                        k
                                        for k in hex_matches
                                        if len(k) in [16, 40] and k not in key_ids
                                    ]
                                )
                    except Exception as e:
                        logger.debug(f"Could not extract key IDs from signature: {e}")
                    return list(set(key_ids))  # Remove duplicates

                def import_gpg_key_from_keyservers(key_id: str) -> bool:
                    """Import a GPG key from keyservers."""
                    keyservers = [
                        "keyserver.ubuntu.com",
                        "pgp.mit.edu",
                        "keys.openpgp.org",
                        "hkps://keyserver.ubuntu.com",
                    ]
                    for keyserver in keyservers:
                        try:
                            if _console:
                                _console.print(
                                    f"  [cyan]Importing GPG key {key_id} from {keyserver}...[/cyan]"
                                )
                            import_result = subprocess.run(
                                [
                                    "gpg",
                                    "--keyserver",
                                    keyserver,
                                    "--recv-keys",
                                    key_id,
                                ],
                                capture_output=True,
                                text=True,
                                timeout=30,
                            )
                            if import_result.returncode == 0:
                                logger.info(
                                    f"GPG key {key_id} imported successfully from {keyserver}"
                                )
                                return True
                            else:
                                logger.debug(
                                    f"Failed to import key {key_id} from {keyserver}: {import_result.stderr}"
                                )
                        except Exception as e:
                            logger.debug(f"Error importing from {keyserver}: {e}")
                            continue
                    return False

                # Check signature file is valid before extracting keys
                try:
                    sig_size = os.path.getsize(signature_path)
                    if sig_size < 100:
                        logger.error(f"Signature file too small: {sig_size} bytes")
                        raise ValueError(
                            f"Signature file appears invalid (size: {sig_size} bytes)"
                        )
                    logger.info(f"Signature file size: {sig_size} bytes")
                except Exception as e:
                    logger.error(f"Could not read signature file: {e}")
                    raise

                # Extract key IDs from the signature file
                if _console:
                    _console.print(
                        "  [cyan]Extracting GPG key information from signature...[/cyan]"
                    )
                key_ids = extract_key_ids_from_signature(signature_path)
                logger.info(f"Extracted key IDs from signature: {key_ids}")

                if not key_ids:
                    # Fallback: Try to verify first and extract key ID from error message
                    logger.info(
                        "Could not extract key IDs from signature, attempting verification to identify missing key..."
                    )
                    try:
                        import gnupg

                        if gnupg:
                            gpg = gnupg.GPG()
                            with open(installer_path, "rb") as f:
                                verified = gpg.verify_file(f, str(signature_path))
                            logger.info(
                                f"GPG verification attempt status: {verified.status}"
                            )
                            if not verified.valid and verified.status:
                                # Parse error message for key ID (format: "no public key" followed by key ID)
                                key_match = re.search(
                                    r"([0-9A-F]{16,40})", verified.status, re.IGNORECASE
                                )
                                if key_match:
                                    key_ids = [key_match.group(1)]
                                    logger.info(
                                        f"Extracted key ID from verification error: {key_ids[0]}"
                                    )
                                # Also try to get key ID from stderr if available
                                if (
                                    not key_ids
                                    and hasattr(verified, "stderr")
                                    and verified.stderr
                                ):
                                    key_match = re.search(
                                        r"([0-9A-F]{16,40})",
                                        verified.stderr,
                                        re.IGNORECASE,
                                    )
                                    if key_match:
                                        key_ids = [key_match.group(1)]
                                        logger.info(
                                            f"Extracted key ID from stderr: {key_ids[0]}"
                                        )
                    except Exception as e:
                        logger.debug(f"Could not extract key ID from verification: {e}")

                # Import extracted keys
                if key_ids:
                    logger.info(
                        f"Found {len(key_ids)} key ID(s) in signature: {key_ids}"
                    )
                    for key_id in key_ids:
                        # Check if key is already imported
                        try:
                            import gnupg

                            if gnupg:
                                gpg = gnupg.GPG()
                                keys = gpg.list_keys()
                                imported_fingerprints = [
                                    str(key.get("fingerprint", "")) for key in keys
                                ]
                                key_imported = any(
                                    key_id.upper() in fp.upper()
                                    for fp in imported_fingerprints
                                )

                                if not key_imported:
                                    if import_gpg_key_from_keyservers(key_id):
                                        if _console:
                                            _console.print(
                                                f"  [green]✓[/green] GPG key {key_id} imported"
                                            )
                                    else:
                                        logger.warning(
                                            f"Failed to import GPG key {key_id} from any keyserver"
                                        )
                                        if _console:
                                            _console.print(
                                                f"  [yellow]Warning:[/yellow] Could not import key {key_id}"
                                            )
                                else:
                                    logger.debug(f"GPG key {key_id} already imported")
                        except Exception as e:
                            logger.warning(
                                f"Could not check/import GPG key {key_id}: {e}"
                            )
                else:
                    logger.warning(
                        "Could not extract key IDs from signature - verification may fail"
                    )
                    if _console:
                        _console.print(
                            "  [yellow]Warning:[/yellow] Could not determine required GPG key"
                        )

                if _console:
                    _console.print(
                        "  [cyan]Verifying file integrity with GPG...[/cyan]"
                    )

                # Verify using GPG signature - REQUIRED for security
                verification_result = verify_download(
                    installer_path,
                    signature_path=signature_path,
                    checksum_path=None,
                    require_gpg=True,  # GPG verification is required
                    require_sha256=False,
                )

                if not verification_result.success:
                    error_msg = f"GPG verification failed: {verification_result.error}"
                    logger.error(error_msg)
                    if _console:
                        _console.print(
                            f"  [bold red]Security verification failed:[/bold red] {verification_result.error}"
                        )
                    # Clean up files
                    try:
                        os.remove(installer_path)
                        os.remove(signature_path)
                    except OSError:
                        pass
                    return InstallationResult(
                        component="python-windows",
                        success=False,
                        installed=False,
                        error=error_msg,
                        recovery_suggestion=verification_result.recovery_suggestion
                        or (
                            "Import Python.org GPG keys manually: "
                            "gpg --keyserver keyserver.ubuntu.com --recv-keys B26995E310250568 0D96DF3DDB286922 7ED10B6531D7C8E1"
                        ),
                    )

                if _console:
                    _console.print("  [bold green]GPG signature verified[/bold green]")
                logger.info("Windows Python installer verified successfully with GPG")

                # Clean up signature file
                try:
                    os.remove(signature_path)
                except OSError:
                    pass
            except Exception as e:
                logger.warning(f"Could not download or verify GPG signature: {e}")
                if _console:
                    _console.print(
                        "  [yellow]Warning:[/yellow] GPG verification skipped"
                    )
                logger.info(
                    "Windows Python installer downloaded (GPG verification unavailable)"
                )
        else:
            # GPG verification not available - proceed without verification but log warning
            if not signature_url:
                logger.warning(
                    "GPG signature URL not available - proceeding without file verification"
                )
            else:
                logger.warning(
                    "GPG verification module not available - proceeding without file verification"
                )
            if _console:
                _console.print(
                    "  [yellow]Warning:[/yellow] File verification skipped (GPG not available)"
                )
            logger.info("Windows Python installer downloaded (without verification)")

        if _console:
            _console.print(
                "  [cyan]Installing Windows Python via Wine (this may take several minutes)...[/cyan]"
            )

        # Set up Wine prefix (.mt5 in current directory)
        if not wine_prefix:
            wine_prefix = os.path.join(os.getcwd(), ".mt5")
        os.makedirs(wine_prefix, exist_ok=True)

        # Disable Wine debugger detection to prevent "debugger detected" errors
        _disable_wine_debugger_detection(wine_path, wine_prefix)

        # Set up environment for Wine
        env = os.environ.copy()
        env["WINEPREFIX"] = wine_prefix
        # Prevent Wine from prompting for mono/gecko
        env["WINEDLLOVERRIDES"] = "mscoree,mshtml="
        # Work around for advapi32.dll.SystemFunction036 - use native DLL
        # This function is used for cryptographic operations, native DLL might work better
        if "WINEDLLOVERRIDES" in env:
            env["WINEDLLOVERRIDES"] += ",advapi32=native"
        else:
            env["WINEDLLOVERRIDES"] = "advapi32=native"

        # Initialize Wine prefix if needed (this may help with compatibility)
        logger.info("Initializing Wine prefix if needed...")
        try:
            init_result = subprocess.run(
                [wine_path, "wineboot", "--init"],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if init_result.returncode != 0:
                logger.warning(
                    f"Wine prefix initialization had issues: {init_result.stderr}"
                )
        except Exception as e:
            logger.warning(f"Wine prefix initialization failed: {e}, continuing anyway")

        # Execute installer via Wine
        logger.info("Installing Windows Python via Wine...")
        logger.info(f"Using Wine prefix: {wine_prefix}")

        install_result = subprocess.run(
            [
                wine_path,
                installer_path,
                "/quiet",
                "InstallAllUsers=1",
                "PrependPath=1",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes timeout
        )

        # Clean up installer
        try:
            os.remove(installer_path)
        except OSError:
            pass

        # Verify installation - sometimes Wine shows errors but installation succeeds
        if _console:
            _console.print("  [cyan]Verifying Windows Python installation...[/cyan]")
        python_info = detect_python_windows(wine_path, wine_prefix)

        if python_info.found:
            # Installation succeeded - ignore Wine return code if Python is detected
            if install_result.returncode != 0:
                logger.warning(
                    f"Wine returned error code {install_result.returncode}, but Python was installed successfully"
                )
                logger.warning(
                    f"Wine stderr: {install_result.stderr[:500]}"
                )  # Log first 500 chars
            if _console:
                _console.print(
                    f"  [bold green]Windows Python installed successfully:[/bold green] {python_info.version}"
                )
            logger.info(f"Windows Python successfully installed at {python_info.path}")
            return InstallationResult(
                component="python-windows",
                success=True,
                installed=True,
                path=python_info.path,
                version=python_info.version,
            )
        else:
            # Installation failed - check if it's due to Wine errors
            if install_result.returncode != 0:
                error_msg = (
                    f"Windows Python installation failed: {install_result.stderr}"
                )
                logger.error(error_msg)
                # Check if it's the known advapi32.dll.SystemFunction036 issue
                if "SystemFunction036" in install_result.stderr:
                    recovery = (
                        "This is a known Wine compatibility issue with cryptographic functions. "
                        "Try updating Wine to the latest version, or use a different Wine prefix. "
                        "You can also try installing Python manually in the .mt5 Wine prefix."
                    )
                else:
                    recovery = "Check Wine logs and ensure Wine is properly configured"
                return InstallationResult(
                    component="python-windows",
                    success=False,
                    installed=False,
                    error=error_msg,
                    recovery_suggestion=recovery,
                )
            else:
                error_msg = (
                    "Windows Python installation completed but verification failed"
                )
                logger.error(error_msg)
                return InstallationResult(
                    component="python-windows",
                    success=False,
                    installed=False,
                    error=error_msg,
                    recovery_suggestion="Check Wine prefix for Python installation",
                )

    except subprocess.TimeoutExpired as e:
        error_msg = f"Windows Python installation timed out: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="python-windows",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Installation may still be in progress. Check Wine processes.",
        )
    except (FileNotFoundError, OSError) as e:
        error_msg = f"Error during Windows Python installation: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="python-windows",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Check internet connection and Wine configuration",
        )


def install_mt5_platform(
    wine_path: Optional[str] = None,
    wine_prefix: Optional[str] = None,
    detection_result: Optional[DetectionResult] = None,
) -> InstallationResult:
    """
    Install MetaTrader5 platform via Wine (our own Python implementation inspired by mt5linux.sh).

    Args:
        wine_path: Path to Wine executable (optional, will detect if not provided)
        wine_prefix: Optional Wine prefix path
        detection_result: Optional DetectionResult to check if MT5 platform is already installed

    Returns:
        InstallationResult with installation status
    """
    logger.info("Starting MetaTrader5 platform installation")

    # Cache sudo credentials early - needed for ydotoold and other operations
    if _console:
        _console.print(
            "  [cyan]Configuring sudo password timeout (15 minutes)...[/cyan]"
        )
    _configure_sudo_timeout(timeout_minutes=15)

    # Check if MT5 platform is already installed
    if detection_result:
        if detection_result.mt5.found:
            logger.info(
                f"MetaTrader5 platform already installed at {detection_result.mt5.path}"
            )
            return InstallationResult(
                component="mt5-platform",
                success=True,
                installed=False,  # Skipped - already installed
                path=detection_result.mt5.path,
            )

    # Get Wine path if not provided
    wine_path_result, error_result = _get_wine_path(wine_path)
    if error_result:
        return error_result
    wine_path = wine_path_result

    # Get Wine prefix - default to .mt5 in current working directory
    if not wine_prefix:
        wine_prefix = os.path.join(os.getcwd(), ".mt5")

    # Ensure Wine prefix exists
    os.makedirs(wine_prefix, exist_ok=True)

    # Check if we're on Wayland
    # Note: Wine applications on Wayland run through XWayland automatically, which should handle input.
    # ydotool is optional and only needed for automation, not for basic Wine functionality.
    wayland_display = os.environ.get("WAYLAND_DISPLAY")
    xdg_session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    is_wayland = wayland_display is not None or xdg_session_type == "wayland"

    # Also check detection_result if available
    if detection_result and detection_result.display_system == "wayland":
        is_wayland = True

    if is_wayland:
        logger.info(
            "Wayland environment detected - Wine will run through XWayland automatically"
        )
        if _console:
            _console.print(
                "  [cyan]Wayland detected - Wine will use XWayland for display and input[/cyan]"
            )

        # Optionally check for ydotool (for automation, not required for basic functionality)
        ydotool_info = detect_ydotool()
        if not ydotool_info.found:
            # Try to install ydotool automatically (optional, for automation only)
            logger.info(
                "ydotool not found - attempting automatic installation via apt (optional for automation)..."
            )
            if _console:
                _console.print(
                    "  [dim]Installing ydotool for Wayland automation (optional, sudo password will be requested)...[/dim]"
                )

            try:
                # Update package list
                logger.info(
                    "Updating apt package list (sudo password may be required)..."
                )
                update_result = subprocess.run(
                    ["sudo", "apt-get", "update", "-qq"],
                    timeout=60,
                )
                if update_result.returncode != 0:
                    logger.warning(
                        f"apt-get update failed (return code: {update_result.returncode})"
                    )

                # Install ydotool and ydotoold
                logger.info(
                    "Installing ydotool via apt-get (sudo password will be requested if needed)..."
                )
                install_result = subprocess.run(
                    ["sudo", "apt-get", "install", "-y", "ydotool", "ydotoold"],
                    timeout=120,
                )

                if install_result.returncode == 0:
                    logger.info("ydotool installed successfully")
                    if _console:
                        _console.print(
                            "  [bold green]ydotool installed successfully[/bold green]"
                        )
                    # Re-detect ydotool
                    ydotool_info = detect_ydotool()
                    # Try to start ydotoold daemon if not running
                    if ydotool_info.found:
                        if _console:
                            _console.print(
                                "  [cyan]Starting ydotoold daemon (sudo password may be requested)...[/cyan]"
                            )
                        if _start_ydotoold_daemon():
                            if _console:
                                _console.print(
                                    "  [bold green]ydotoold daemon started successfully[/bold green]"
                                )
                        else:
                            if _console:
                                _console.print(
                                    "  [yellow]Could not start ydotoold automatically - you may need to start it manually[/yellow]"
                                )
                                _console.print(
                                    "  [dim]Start with: sudo systemctl start ydotoold (or run: sudo ydotoold)[/dim]"
                                )
                else:
                    logger.info(
                        "ydotool installation failed or skipped - not required for basic Wine functionality"
                    )
                    if _console:
                        _console.print(
                            "  [dim]ydotool installation skipped (not required for basic functionality)[/dim]"
                        )
            except (subprocess.TimeoutExpired, Exception) as e:
                logger.info(
                    f"ydotool installation skipped: {e} - not required for basic Wine functionality"
                )

        # Log ydotool status and start daemon if needed
        if ydotool_info.found and ydotool_info.path:
            logger.info(f"ydotool available: {ydotool_info.path} (for automation)")
            if _console:
                _console.print(
                    f"  [green]ydotool available:[/green] {ydotool_info.path} (for automation)"
                )

            # Check if daemon is running and start it if not
            try:
                daemon_check = subprocess.run(
                    ["pgrep", "-x", "ydotoold"],
                    capture_output=True,
                    timeout=2,
                )
                if daemon_check.returncode != 0:
                    # Daemon not running, try to start it
                    if _console:
                        _console.print(
                            "  [cyan]Starting ydotoold daemon (sudo password may be requested)...[/cyan]"
                        )
                    if _start_ydotoold_daemon():
                        if _console:
                            _console.print(
                                "  [bold green]ydotoold daemon started successfully[/bold green]"
                            )
                    else:
                        if _console:
                            _console.print(
                                "  [yellow]Could not start ydotoold automatically - you may need to start it manually[/yellow]"
                            )
                            _console.print(
                                "  [dim]Start with: sudo systemctl start ydotoold (or run: sudo ydotoold)[/dim]"
                            )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        else:
            logger.info("ydotool not available - Wine will still work through XWayland")
            if _console:
                _console.print(
                    "  [dim]ydotool not available (optional for automation only)[/dim]"
                )

    # Install Wine packages (mono, gecko) if needed
    if _console:
        _console.print("  [cyan]Installing Wine packages (mono, gecko)...[/cyan]")
    _install_wine_packages(wine_path, wine_prefix)

    # Install additional Wine dependencies for MT5
    # MT5 requires Visual C++ runtimes and other dependencies
    if _console:
        _console.print(
            "  [cyan]Installing additional Wine dependencies for MT5...[/cyan]"
        )
    _install_mt5_wine_dependencies(wine_path, wine_prefix)

    # URLs from official mt5linux.sh script
    # https://download.terminal.free/cdn/web/metaquotes.software.corp/mt5/mt5linux.sh
    mt5_installer_url = (
        "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
    )
    mt5_installer_path = "/tmp/mt5setup.exe"

    try:
        # Disable Wine debugger detection to prevent "debugger detected" errors
        _disable_wine_debugger_detection(wine_path, wine_prefix)

        # Set up base environment for Wine
        env = os.environ.copy()
        env["WINEPREFIX"] = wine_prefix
        env["DEBIAN_FRONTEND"] = "noninteractive"
        # Suppress Wine debug messages for cleaner output
        env["WINEDEBUG"] = "-all"
        # Set DLL overrides for MT5 (prevent Wine from prompting for mono/gecko)
        env["WINEDLLOVERRIDES"] = "mscoree,mshtml="

        # Step 0: Initialize Wine prefix first (required before configuration)
        if _console:
            _console.print("  [cyan]Initializing Wine prefix...[/cyan]")
        logger.info("Initializing Wine prefix...")
        try:
            init_result = subprocess.run(
                [wine_path, "wineboot", "--init"],
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                stdin=subprocess.DEVNULL,
            )
            if init_result.returncode == 0:
                logger.info("Wine prefix initialized successfully")
            else:
                logger.warning(
                    f"Wine prefix initialization had issues: {init_result.stderr}"
                )
        except Exception as e:
            logger.warning(f"Wine prefix initialization failed: {e}, continuing anyway")

        # Set up display for MT5 installation
        # Always use Xvfb on :99 for headless automated installation
        # This prevents Wine from rendering on the user's real display
        # (important on Wayland where XWayland would show on user's screen)
        xvfb_path = shutil.which("Xvfb")
        display_num = None
        xvfb_process = None

        if xvfb_path:
            # Use Xvfb for headless operation - this works on both X11 and Wayland
            # On Wayland, this avoids Wine rendering on the user's XWayland display
            try:
                display_num = ":99"
                logger.info(
                    f"Starting virtual display {display_num} for MT5 installation..."
                )
                xvfb_process = subprocess.Popen(
                    [
                        xvfb_path,
                        display_num,
                        "-screen",
                        "0",
                        "1024x768x24",
                        "-ac",
                        "+extension",
                        "GLX",
                        "+extension",
                        "RANDR",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(3)
                env["DISPLAY"] = display_num
                logger.info(f"Virtual display {display_num} started and configured")
                if _console:
                    _console.print(
                        f"  [cyan]Using virtual display {display_num} for headless installation[/cyan]"
                    )
            except Exception as e:
                logger.warning(f"Could not start virtual display: {e}")
                # Fall back to existing DISPLAY if Xvfb fails
                if os.environ.get("DISPLAY"):
                    env["DISPLAY"] = os.environ["DISPLAY"]
                    logger.info(f"Falling back to existing DISPLAY={env['DISPLAY']}")
                else:
                    logger.warning("No DISPLAY available - MT5 GUI installer may fail")
        elif os.environ.get("DISPLAY"):
            # No Xvfb but DISPLAY is set - use it (may show on user's screen)
            env["DISPLAY"] = os.environ["DISPLAY"]
            logger.info(f"Xvfb not available, using existing DISPLAY={env['DISPLAY']}")
            if _console:
                _console.print(
                    "  [yellow]Xvfb not installed - using existing display (may show on screen)[/yellow]"
                )
        else:
            logger.warning(
                "No DISPLAY available and no Xvfb - MT5 GUI installer may fail"
            )

        # Step 1: Configure Wine prefix to Windows 11 (as per mt5linux.sh)
        # Note: The official script uses "win11" (lowercase, no equals sign)
        if _console:
            _console.print("  [cyan]Configuring Wine prefix for Windows 11...[/cyan]")
        logger.info("Configuring Wine prefix to Windows 11 mode...")
        try:
            # Find winecfg - it's usually in the same directory as wine or in PATH
            winecfg_path = shutil.which("winecfg")
            if not winecfg_path:
                # Try to find it relative to wine_path
                wine_dir = os.path.dirname(wine_path)
                potential_winecfg = os.path.join(wine_dir, "winecfg")
                if os.path.exists(potential_winecfg):
                    winecfg_path = potential_winecfg

            if winecfg_path:
                # Use "-v win11" format (space, not equals, lowercase) as per official script
                winecfg_result = subprocess.run(
                    [winecfg_path, "-v", "win11"],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    stdin=subprocess.DEVNULL,
                )
                if winecfg_result.returncode == 0:
                    logger.info("Wine prefix configured for Windows 11")
                else:
                    logger.warning(
                        f"winecfg returned non-zero: {winecfg_result.stderr}"
                    )
            else:
                logger.warning("winecfg not found, skipping Windows 11 configuration")
        except Exception as e:
            logger.warning(
                f"Could not configure Wine to Windows 11: {e}, continuing anyway"
            )

        # NOTE: Wine virtual desktop mode is NOT configured during installation
        # because /auto mode is non-interactive. Virtual desktop will be configured
        # later during the MT5 configuration pause when user interaction is needed.

        # Skip WebView2 - it's not essential for MT5 core trading functionality
        # WebView2 is only needed for web browser features within MT5
        # Installing it on Wine/headless causes timeouts and issues
        logger.info("Skipping WebView2 Runtime (not required for trading functionality)")

        # Step 4: Download MT5 installer with retry logic
        if _console:
            _console.print("  [cyan]Downloading MT5 installer...[/cyan]")
        logger.info(f"Downloading MT5 installer from {mt5_installer_url}...")

        download_success = False
        for download_attempt in range(3):
            try:
                urllib.request.urlretrieve(mt5_installer_url, mt5_installer_path)
                logger.info("MT5 installer downloaded successfully")
                download_success = True
                break
            except urllib.error.URLError as e:
                logger.warning(f"MT5 download attempt {download_attempt + 1} failed: {e}")
                if download_attempt < 2:
                    if _console:
                        _console.print(
                            f"  [yellow]Download failed, retrying ({download_attempt + 2}/3)...[/yellow]"
                        )
                    time.sleep(2)  # Brief delay before retry

        if not download_success:
            error_msg = f"Failed to download MT5 installer after 3 attempts from {mt5_installer_url}"
            logger.error(error_msg)
            return InstallationResult(
                component="mt5-platform",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and try again. You can also download MT5 manually from https://www.metatrader5.com/",
            )

        # Use the mt5_installer_path for the retry loop
        installer_path = mt5_installer_path

        # Retry logic: try up to 3 times if installation times out (>10 minutes)
        max_retries = 3
        install_result = None
        last_error = None

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                if _console:
                    _console.print(
                        f"  [yellow]Retrying MT5 installation (attempt {attempt}/{max_retries})...[/yellow]"
                    )
                logger.info(
                    f"Retrying MT5 installation (attempt {attempt}/{max_retries})"
                )
                # Re-download installer for retry
                try:
                    if _console:
                        _console.print("  [cyan]Re-downloading MT5 installer...[/cyan]")
                    urllib.request.urlretrieve(mt5_installer_url, installer_path)
                    logger.info("MT5 installer re-downloaded for retry")
                except Exception as e:
                    logger.warning(
                        f"Failed to re-download installer: {e}, using existing file"
                    )
            else:
                if _console:
                    _console.print(
                        "  [cyan]Installing MT5 platform via Wine (this may take several minutes)...[/cyan]"
                    )
                logger.info("Installing MT5 platform via Wine...")

            # Run installer in silent mode (as per official mt5linux.sh script)
            # The official script uses /S flag for silent installation
            # /S = Silent mode, no user interaction, installs to default location
            # Note: Some MT5 installers may require /SILENT or /VERYSILENT instead
            logger.info(
                f"Running MT5 installer in silent mode (attempt {attempt}/{max_retries})..."
            )
            logger.info(f"Installer path: {installer_path}")
            logger.info(f"Wine prefix: {wine_prefix}")

            # Verify installer exists before running
            if not os.path.exists(installer_path):
                error_msg = f"MT5 installer not found at {installer_path}"
                logger.error(error_msg)
                if attempt < max_retries:
                    continue
                else:
                    return InstallationResult(
                        component="mt5-platform",
                        success=False,
                        installed=False,
                        error=error_msg,
                        recovery_suggestion="Installer file missing. Check download and file permissions.",
                    )

            try:
                # Run Wine directly - on Wayland, Wine automatically uses XWayland for display and input
                # No wrapper needed - XWayland handles input forwarding automatically
                installer_cmd = [
                    wine_path,
                    installer_path,
                ]
                logger.info(
                    f"Running MT5 installer with Wine (will use XWayland on Wayland): {' '.join(installer_cmd)}"
                )

                # Launch MT5 installer with /auto flag for unattended installation
                # The /auto flag is officially supported by MetaQuotes for automated deployment
                # See: https://www.metatrader5.com/en/terminal/help/start_advanced/installation
                logger.info(
                    "Launching MT5 installer with /auto flag for unattended installation..."
                )
                if _console:
                    _console.print(
                        "  [cyan]Installing MT5 in unattended mode (/auto)...[/cyan]"
                    )

                # Add /auto flag to installer command
                auto_cmd = installer_cmd + ["/auto"]
                logger.info(f"Running: {' '.join(auto_cmd)}")

                process = subprocess.Popen(
                    auto_cmd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                # Poll for MT5 installation completion (check every 5 seconds, max 10 minutes)
                # With /auto flag, installation typically completes in 2-5 minutes
                max_wait_seconds = 600
                poll_interval = 5
                elapsed = 0
                mt5_detected = False

                while elapsed < max_wait_seconds:
                    time.sleep(poll_interval)
                    elapsed += poll_interval

                    # Check if installer process exited
                    if process.poll() is not None:
                        logger.info(
                            f"MT5 installer process exited with code {process.returncode}"
                        )
                        break

                    # Check if MT5 was installed (terminal64.exe exists)
                    temp_check = detect_mt5(wine_path, wine_prefix)
                    if temp_check.found:
                        logger.info(f"MT5 installation detected at {temp_check.path}")
                        mt5_detected = True
                        # Terminate installer if still running (cleanup windows)
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                process.kill()
                        break

                    # Progress update every minute
                    if elapsed % 60 == 0:
                        minutes = elapsed // 60
                        logger.info(
                            f"Waiting for MT5 installation... ({minutes} min elapsed)"
                        )
                        if _console:
                            _console.print(
                                f"  [dim]Still installing... ({minutes} min)[/dim]"
                            )

                # Check if we timed out
                if (
                    elapsed >= max_wait_seconds
                    and not mt5_detected
                    and process.poll() is None
                ):
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise subprocess.TimeoutExpired(
                        cmd=auto_cmd, timeout=max_wait_seconds
                    )

                # Build install_result for downstream verification
                try:
                    stdout_data, stderr_data = process.communicate(timeout=5)
                except Exception:
                    stdout_data, stderr_data = b"", b""

                install_result = subprocess.CompletedProcess(
                    args=auto_cmd,
                    returncode=(
                        process.returncode if process.returncode is not None else 0
                    ),
                    stdout=(
                        stdout_data.decode("utf-8", errors="ignore")
                        if isinstance(stdout_data, bytes)
                        else ""
                    ),
                    stderr=(
                        stderr_data.decode("utf-8", errors="ignore")
                        if isinstance(stderr_data, bytes)
                        else ""
                    ),
                )

                # Success - break out of retry loop
                break
            except subprocess.TimeoutExpired:
                last_error = f"MT5 installation timed out after 10 minutes (attempt {attempt}/{max_retries})"
                logger.warning(last_error)
                if attempt < max_retries:
                    if _console:
                        _console.print(
                            "  [yellow]Installation timed out, will retry automatically...[/yellow]"
                        )
                    # Clean up any partial installation before retry
                    try:
                        # Kill any hanging Wine processes
                        if xvfb_process:
                            try:
                                xvfb_process.terminate()
                            except Exception:
                                pass
                    except Exception as e:
                        logger.debug(f"Error during cleanup before retry: {e}")
                    continue
                else:
                    # Last attempt also timed out
                    error_msg = f"MT5 installation timed out after {max_retries} attempts (each >10 minutes)"
                    logger.error(error_msg)
                    # Clean up virtual display
                    if xvfb_process:
                        try:
                            xvfb_process.terminate()
                            xvfb_process.wait(timeout=5)
                        except Exception:
                            try:
                                xvfb_process.kill()
                            except Exception:
                                pass
                    # Clean up installer
                    try:
                        os.remove(installer_path)
                    except OSError:
                        pass
                    return InstallationResult(
                        component="mt5-platform",
                        success=False,
                        installed=False,
                        error=error_msg,
                        recovery_suggestion="MT5 installation is taking too long. Check system resources and Wine configuration.",
                    )
            except Exception as e:
                last_error = f"MT5 installation failed with error: {e}"
                logger.error(last_error)
                if attempt < max_retries:
                    if _console:
                        _console.print(
                            "  [yellow]Installation failed, will retry automatically...[/yellow]"
                        )
                    continue
                else:
                    # Last attempt also failed
                    error_msg = (
                        f"MT5 installation failed after {max_retries} attempts: {e}"
                    )
                    # Clean up virtual display
                    if xvfb_process:
                        try:
                            xvfb_process.terminate()
                            xvfb_process.wait(timeout=5)
                        except Exception:
                            try:
                                xvfb_process.kill()
                            except Exception:
                                pass
                    # Clean up installer
                    try:
                        os.remove(installer_path)
                    except OSError:
                        pass
                    return InstallationResult(
                        component="mt5-platform",
                        success=False,
                        installed=False,
                        error=error_msg,
                        recovery_suggestion="Check Wine logs and ensure Wine is properly configured",
                    )

        # Clean up virtual display if we started it
        if xvfb_process:
            try:
                xvfb_process.terminate()
                xvfb_process.wait(timeout=5)
                logger.info("Virtual display stopped")
            except Exception as e:
                logger.warning(f"Error stopping virtual display: {e}")
                try:
                    xvfb_process.kill()
                except Exception:
                    pass

        # No ydotool process to clean up - Wine runs directly through XWayland

        # Clean up installer
        try:
            os.remove(installer_path)
        except OSError:
            pass

        # Verify installation
        if _console:
            _console.print("  [cyan]Verifying MT5 platform installation...[/cyan]")

        # Wait a bit more for any background installation processes to complete
        logger.info("Waiting for installation processes to complete...")
        time.sleep(3)

        # Log installation result details for debugging
        if install_result:
            logger.info(f"MT5 installer return code: {install_result.returncode}")
            if install_result.stdout:
                logger.info(f"MT5 installer stdout: {install_result.stdout[:2000]}")
            if install_result.stderr:
                logger.info(f"MT5 installer stderr: {install_result.stderr[:2000]}")

        # Check for MT5 installation in multiple locations
        logger.info(f"Checking for MT5 installation in prefix: {wine_prefix}")
        mt5_info = detect_mt5(wine_path, wine_prefix)

        # If not found, try checking common installation paths directly
        if not mt5_info.found:
            logger.info(
                "MT5 not found via detection, checking common paths directly..."
            )
            common_paths = [
                os.path.join(
                    wine_prefix,
                    "drive_c",
                    "Program Files",
                    "MetaTrader 5",
                    "terminal64.exe",
                ),
                os.path.join(
                    wine_prefix,
                    "drive_c",
                    "Program Files (x86)",
                    "MetaTrader 5",
                    "terminal64.exe",
                ),
                os.path.join(
                    wine_prefix,
                    "drive_c",
                    "Program Files",
                    "MetaTrader 5",
                    "terminal.exe",
                ),
                os.path.join(
                    wine_prefix,
                    "drive_c",
                    "Program Files (x86)",
                    "MetaTrader 5",
                    "terminal.exe",
                ),
            ]
            for path in common_paths:
                if os.path.exists(path):
                    logger.info(f"Found MT5 at: {path}")
                    mt5_info = ComponentInfo(found=True, path=path)
                    break
        if mt5_info.found:
            if _console:
                _console.print(
                    f"  [bold green]MT5 platform installed successfully:[/bold green] {mt5_info.path}"
                )
            logger.info(f"MT5 platform successfully installed at {mt5_info.path}")
            return InstallationResult(
                component="mt5-platform",
                success=True,
                installed=True,
                path=mt5_info.path,
            )
        else:
            # Installation might have succeeded but detection failed, or installer returned non-zero
            if install_result and install_result.returncode == 0:
                logger.warning(
                    "MT5 installer completed with return code 0 but verification failed"
                )
                # Log more details for debugging
                if install_result.stderr:
                    logger.warning(
                        f"Installer stderr (may contain useful info): {install_result.stderr[:500]}"
                    )
                return InstallationResult(
                    component="mt5-platform",
                    success=True,  # Assume success if installer returned 0
                    installed=True,
                    error="Installation completed but verification failed",
                    recovery_suggestion="Check MT5 installation manually in Wine prefix",
                )
            else:
                # Installation failed - provide detailed error information
                error_details = []
                if install_result:
                    error_details.append(f"Return code: {install_result.returncode}")
                    if install_result.stderr:
                        error_details.append(
                            f"Error output: {install_result.stderr[:500]}"
                        )
                    if install_result.stdout:
                        error_details.append(f"Output: {install_result.stdout[:500]}")
                elif last_error:
                    error_details.append(f"Error: {last_error}")

                error_msg = f"MT5 installation failed: {'; '.join(error_details)}"
                logger.error(error_msg)

                # Provide more specific recovery suggestions based on error
                recovery = "Check Wine logs and ensure Wine is properly configured"
                if install_result and install_result.stderr:
                    stderr_lower = install_result.stderr.lower()
                    if "debugger" in stderr_lower:
                        recovery = "Wine detected a debugger. Ensure no debuggers (gdb, strace) are attached."
                    elif "timeout" in stderr_lower or "timed out" in stderr_lower:
                        recovery = "Installation timed out. Try increasing timeout or check system resources."
                    elif "wine" in stderr_lower and "error" in stderr_lower:
                        recovery = "Wine error detected. Check Wine version and configuration. Try: wine --version"

                return InstallationResult(
                    component="mt5-platform",
                    success=False,
                    installed=False,
                    error=error_msg,
                    recovery_suggestion=recovery,
                )

    except (FileNotFoundError, OSError, urllib.error.URLError) as e:
        error_msg = f"Error during MT5 platform installation: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="mt5-platform",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Check internet connection and Wine configuration",
        )


def install_mt5_library(
    wine_path: Optional[str] = None,
    python_windows_path: Optional[str] = None,
    detection_result: Optional[DetectionResult] = None,
) -> InstallationResult:
    """
    Install MetaTrader5 library on Windows Python.

    Args:
        wine_path: Path to Wine executable (optional, will detect if not provided)
        python_windows_path: Path to Windows Python executable (optional)
        detection_result: Optional DetectionResult to check if MT5 is already installed

    Returns:
        InstallationResult with installation status
    """
    logger.info("Starting MetaTrader5 library installation")

    # Check if MT5 is already installed
    if detection_result:
        if detection_result.mt5.found:
            logger.info(f"MetaTrader5 already installed at {detection_result.mt5.path}")
            return InstallationResult(
                component="mt5",
                success=True,
                installed=False,  # Skipped - already installed
                path=detection_result.mt5.path,
            )

    # Get Wine path if not provided
    if not wine_path:
        wine_info = detect_wine()
        if not wine_info.found:
            error_msg = "Wine not found. Install Wine first."
            logger.error(error_msg)
            return InstallationResult(
                component="mt5",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Install Wine first using install_wine()",
            )
        wine_path = wine_info.path

    # Get Windows Python path if not provided
    if not python_windows_path:
        python_info = detect_python_windows(wine_path)
        if not python_info.found:
            error_msg = "Windows Python not found. Install Windows Python first."
            logger.error(error_msg)
            return InstallationResult(
                component="mt5",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Install Windows Python first using install_windows_python()",
            )
        python_windows_path = python_info.path

    # Install MetaTrader5 library via pip
    try:
        if _console:
            _console.print("  [cyan]Installing MetaTrader5 library via pip...[/cyan]")
        logger.info("Installing MetaTrader5 library via pip...")
        install_result = subprocess.run(
            [wine_path, python_windows_path, "-m", "pip", "install", "MetaTrader5"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )

        if install_result.returncode != 0:
            error_msg = f"MetaTrader5 installation failed: {install_result.stderr}"
            logger.error(error_msg)
            return InstallationResult(
                component="mt5",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and pip availability",
            )

        # Verify installation
        verify_result = subprocess.run(
            [
                wine_path,
                python_windows_path,
                "-c",
                "import MetaTrader5; print(MetaTrader5.__version__)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if verify_result.returncode == 0:
            version = verify_result.stdout.strip()
            if _console:
                _console.print(
                    f"  [bold green]MetaTrader5 installed successfully:[/bold green] {version}"
                )
            logger.info(f"MetaTrader5 successfully installed, version: {version}")
            return InstallationResult(
                component="mt5",
                success=True,
                installed=True,
                version=version,
            )
        else:
            error_msg = "MetaTrader5 installation completed but verification failed"
            logger.error(error_msg)
            return InstallationResult(
                component="mt5",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Try importing MetaTrader5 manually to verify",
            )

    except subprocess.TimeoutExpired as e:
        error_msg = f"MetaTrader5 installation timed out: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="mt5",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Check internet connection and try again",
        )
    except (FileNotFoundError, OSError) as e:
        error_msg = f"Error during MetaTrader5 installation: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="mt5",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Check Wine and Windows Python configuration",
        )


def install_rpyc(
    wine_path: Optional[str] = None,
    python_windows_path: Optional[str] = None,
    detection_result: Optional[DetectionResult] = None,
) -> InstallationResult:
    """
    Install rpyc on Windows Python.

    Args:
        wine_path: Path to Wine executable (optional, will detect if not provided)
        python_windows_path: Path to Windows Python executable (optional)
        detection_result: Optional DetectionResult to check if rpyc is already installed

    Returns:
        InstallationResult with installation status
    """
    logger.info("Starting rpyc installation")

    # Check if rpyc is already installed
    if detection_result:
        if detection_result.rpyc.found:
            logger.info(
                f"rpyc already installed, version: {detection_result.rpyc.version}"
            )
            return InstallationResult(
                component="rpyc",
                success=True,
                installed=False,  # Skipped - already installed
                version=detection_result.rpyc.version,
            )

    # Get Wine path if not provided
    if not wine_path:
        wine_info = detect_wine()
        if not wine_info.found:
            error_msg = "Wine not found. Install Wine first."
            logger.error(error_msg)
            return InstallationResult(
                component="rpyc",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Install Wine first using install_wine()",
            )
        wine_path = wine_info.path

    # Get Windows Python path if not provided
    if not python_windows_path:
        python_info = detect_python_windows(wine_path)
        if not python_info.found:
            error_msg = "Windows Python not found. Install Windows Python first."
            logger.error(error_msg)
            return InstallationResult(
                component="rpyc",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Install Windows Python first using install_windows_python()",
            )
        python_windows_path = python_info.path

    # Install rpyc via pip
    try:
        if _console:
            _console.print("  [cyan]Installing rpyc via pip...[/cyan]")
        logger.info("Installing rpyc via pip...")
        install_result = subprocess.run(
            [wine_path, python_windows_path, "-m", "pip", "install", "rpyc"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )

        if install_result.returncode != 0:
            error_msg = f"rpyc installation failed: {install_result.stderr}"
            logger.error(error_msg)
            return InstallationResult(
                component="rpyc",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and pip availability",
            )

        # Verify installation
        verify_result = subprocess.run(
            [
                wine_path,
                python_windows_path,
                "-c",
                "import rpyc; print(rpyc.__version__)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if verify_result.returncode == 0:
            version = verify_result.stdout.strip()
            if _console:
                _console.print(
                    f"  [bold green]rpyc installed successfully:[/bold green] {version}"
                )
            logger.info(f"rpyc successfully installed, version: {version}")
            return InstallationResult(
                component="rpyc",
                success=True,
                installed=True,
                version=version,
            )
        else:
            error_msg = "rpyc installation completed but verification failed"
            logger.error(error_msg)
            return InstallationResult(
                component="rpyc",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Try importing rpyc manually to verify",
            )

    except subprocess.TimeoutExpired as e:
        error_msg = f"rpyc installation timed out: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="rpyc",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Check internet connection and try again",
        )
    except (FileNotFoundError, OSError) as e:
        error_msg = f"Error during rpyc installation: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="rpyc",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Check Wine and Windows Python configuration",
        )


def install_missing_components(
    detection_result: DetectionResult,
    wine_prefix: Optional[str] = None,
) -> List[InstallationResult]:
    """
    Install all missing components based on detection results.

    Installs components in order: Wine → Windows Python → MT5 Platform → MT5 Library → rpyc

    Args:
        detection_result: DetectionResult from environment detection (not mutated)
        wine_prefix: Optional Wine prefix path (defaults to .mt5 in current directory)

    Returns:
        List of InstallationResult for each component
    """
    logger.info("Starting installation of missing components")
    results: List[InstallationResult] = []

    # Configure sudo password timeout to 15 minutes to avoid repeated password prompts
    # This is especially useful during long installations
    if _console:
        _console.print(
            "  [cyan]Configuring sudo password timeout (15 minutes)...[/cyan]"
        )
    _configure_sudo_timeout(timeout_minutes=15)

    # Create a copy of detection result to avoid mutating the input
    # We'll track Wine and Python paths from installation results instead
    wine_path: Optional[str] = (
        detection_result.wine.path if detection_result.wine.found else None
    )
    python_windows_path: Optional[str] = (
        detection_result.python_windows.path
        if detection_result.python_windows.found
        else None
    )

    # Use provided wine_prefix or try to extract from detection
    if not wine_prefix:
        # Try to extract wine prefix from detection
        # Wine prefix is the directory CONTAINING drive_c
        if detection_result.mt5.found and detection_result.mt5.path:
            mt5_path = detection_result.mt5.path
            if "drive_c" in mt5_path:
                drive_c_idx = mt5_path.find("/drive_c/")
                if drive_c_idx != -1:
                    wine_prefix = mt5_path[:drive_c_idx]

        # Default to .mt5 in current working directory if not found
        if not wine_prefix:
            wine_prefix = os.path.join(os.getcwd(), ".mt5")

    logger.info(f"Using Wine prefix: {wine_prefix}")

    # Install Wine if missing
    if "wine" in detection_result.missing_components:
        logger.info("Installing Wine...")
        wine_result = install_wine(detection_result)
        results.append(wine_result)
        if not wine_result.success:
            logger.error("Wine installation failed, stopping installation")
            return results
        # Track Wine path from result
        if wine_result.path:
            wine_path = wine_result.path

    # Install Windows Python if missing
    if "python-windows" in detection_result.missing_components:
        logger.info("Installing Windows Python...")
        python_result = install_windows_python(
            wine_path,
            wine_prefix,
            detection_result,
        )
        results.append(python_result)
        if not python_result.success:
            logger.error("Windows Python installation failed, stopping installation")
            return results
        # Track Python path from result
        if python_result.path:
            python_windows_path = python_result.path

    # Install MT5 platform if missing (before MT5 library)
    if "mt5" in detection_result.missing_components and not detection_result.mt5.found:
        logger.info("Installing MetaTrader5 platform...")
        mt5_platform_result = install_mt5_platform(
            wine_path,
            wine_prefix,
            detection_result,
        )
        results.append(mt5_platform_result)
        if not mt5_platform_result.success:
            logger.warning(
                "MT5 platform installation failed, continuing with other components"
            )
        # Update detection result if platform was installed
        if mt5_platform_result.success and mt5_platform_result.path:
            detection_result.mt5.found = True
            detection_result.mt5.path = mt5_platform_result.path

    # Install MT5 library if missing (separate from platform)
    # Note: MT5 library is the Python package, platform is the executable
    # We check if Windows Python is available for library installation
    if python_windows_path and "mt5" in detection_result.missing_components:
        logger.info("Installing MetaTrader5 library...")
        mt5_library_result = install_mt5_library(
            wine_path,
            python_windows_path,
            detection_result,
        )
        results.append(mt5_library_result)
        if not mt5_library_result.success:
            logger.warning(
                "MT5 library installation failed, continuing with other components"
            )

    # Install rpyc if missing
    if "rpyc" in detection_result.missing_components:
        logger.info("Installing rpyc...")
        rpyc_result = install_rpyc(
            wine_path,
            python_windows_path,
            detection_result,
        )
        results.append(rpyc_result)
        if not rpyc_result.success:
            logger.warning("rpyc installation failed, continuing")

    logger.info(f"Installation complete: {len(results)} components processed")
    return results
