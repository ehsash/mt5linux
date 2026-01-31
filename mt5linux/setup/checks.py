"""State detection for MT5 setup."""

from dataclasses import dataclass
from pathlib import Path
import shutil
import socket
import subprocess
from typing import Optional

from .config import get_config


@dataclass
class SetupState:
    """Current state of MT5 installation."""

    # System
    wine_installed: bool = False
    wine_version: Optional[str] = None

    # Wine prefix
    wine_prefix_exists: bool = False
    wine_prefix_path: Optional[Path] = None

    # Python in Wine
    python_in_wine: bool = False
    python_wine_path: Optional[Path] = None
    rpyc_installed_wine: bool = False

    # MT5
    mt5_installed: bool = False
    mt5_exe_path: Optional[Path] = None

    # RPyC service
    rpyc_port: int = 18812
    rpyc_service_exists: bool = False
    rpyc_service_name: Optional[str] = None
    rpyc_service_running: bool = False
    rpyc_port_responding: bool = False

    # Config
    config_exists: bool = False


def check_wine_installed() -> tuple[bool, Optional[str]]:
    """Check if Wine is installed and get version."""
    wine_path = shutil.which("wine")
    if not wine_path:
        return False, None

    try:
        result = subprocess.run(
            ["wine", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version = result.stdout.strip() if result.returncode == 0 else None
        return True, version
    except Exception:
        return False, None


def check_wine_prefix(prefix_path: Path) -> bool:
    """Check if Wine prefix exists and is initialized."""
    return (prefix_path / "drive_c").is_dir()


def find_python_in_wine(prefix_path: Path) -> Optional[Path]:
    """Find Python executable in Wine prefix."""
    possible_paths = [
        prefix_path / "drive_c/Python312/python.exe",
        prefix_path / "drive_c/Python311/python.exe",
        prefix_path / "drive_c/Python310/python.exe",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    # Search for python.exe
    drive_c = prefix_path / "drive_c"
    if drive_c.exists():
        for python_exe in drive_c.rglob("python.exe"):
            if "Python3" in str(python_exe):
                return python_exe

    return None


def find_mt5_terminal(prefix_path: Path) -> Optional[Path]:
    """Find MT5 terminal executable in Wine prefix."""
    drive_c = prefix_path / "drive_c"
    if not drive_c.exists():
        return None

    for terminal in drive_c.rglob("terminal64.exe"):
        return terminal

    return None


def check_port_responding(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a port is responding to connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_systemd_service(service_name: str) -> tuple[bool, bool]:
    """Check if systemd user service exists and is running."""
    service_path = Path.home() / f".config/systemd/user/{service_name}.service"
    exists = service_path.exists()

    if not exists:
        return False, False

    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        running = result.stdout.strip() == "active"
        return True, running
    except Exception:
        return exists, False


def check_all(project_path: Path) -> SetupState:
    """Perform all checks and return current state."""
    state = SetupState()

    # Check config
    config = get_config(project_path)
    state.config_exists = config is not None

    # Determine paths
    if config:
        wine_prefix = config.wine_prefix
        state.rpyc_port = config.rpyc_port
    else:
        wine_prefix = project_path / ".mt5"
        state.rpyc_port = 18812

    state.wine_prefix_path = wine_prefix

    # Check Wine
    state.wine_installed, state.wine_version = check_wine_installed()

    # Check Wine prefix
    state.wine_prefix_exists = check_wine_prefix(wine_prefix)

    # Check Python in Wine
    if state.wine_prefix_exists:
        python_path = find_python_in_wine(wine_prefix)
        state.python_in_wine = python_path is not None
        state.python_wine_path = python_path

    # Check MT5
    if state.wine_prefix_exists:
        mt5_path = find_mt5_terminal(wine_prefix)
        state.mt5_installed = mt5_path is not None
        state.mt5_exe_path = mt5_path

    # Check RPyC service
    service_name = f"mt5-rpyc-{project_path.name}"
    state.rpyc_service_name = service_name
    state.rpyc_service_exists, state.rpyc_service_running = check_systemd_service(
        service_name
    )

    # Check RPyC port
    state.rpyc_port_responding = check_port_responding("localhost", state.rpyc_port)

    return state
