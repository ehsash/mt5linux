"""RPyC systemd service management."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


def create_systemd_service(
    project_path: Path,
    port: int,
    python_exe: Path,
    wine_prefix: Path,
) -> bool:
    """Create and enable systemd user service for RPyC."""
    service_name = f"mt5-rpyc-{project_path.name}"
    service_dir = Path.home() / ".config/systemd/user"
    service_dir.mkdir(parents=True, exist_ok=True)
    service_file = service_dir / f"{service_name}.service"

    # Convert to Windows path for Wine
    # e.g., /home/user/.mt5/drive_c/Python312/python.exe -> C:\Python312\python.exe
    drive_c_str = str(python_exe)
    if "drive_c" in drive_c_str:
        win_path_part = drive_c_str.split("drive_c")[1]
        python_win_path = "C:" + win_path_part.replace("/", "\\")
    else:
        python_win_path = str(python_exe)

    # rpyc 5.x removed rpyc.bin.rpyc_classic - use inline Python to start server
    rpyc_start_code = (
        "from rpyc.utils.server import ThreadedServer;"
        "from rpyc.core.service import ClassicService;"
        f"ThreadedServer(ClassicService,hostname='localhost',port={port}).start()"
    )

    # Use current DISPLAY from environment (important for ThinLinc sessions)
    # ThinLinc typically uses :10.0 or higher, not :0
    current_display = os.environ.get("DISPLAY", ":0")

    service_content = f"""[Unit]
Description=MT5 RPyC Server for {project_path.name}
After=graphical-session.target

[Service]
Type=simple
Environment="WINEPREFIX={wine_prefix}"
Environment="WINEARCH=win64"
Environment="DISPLAY={current_display}"
WorkingDirectory={project_path}
ExecStart=/usr/bin/wine "{python_win_path}" -c "{rpyc_start_code}"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""

    service_file.write_text(service_content)

    # Reload systemd
    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        return False

    # Enable service
    try:
        subprocess.run(
            ["systemctl", "--user", "enable", service_name],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        return False

    return True


def start_service(project_path: Path) -> bool:
    """Start the RPyC service."""
    service_name = f"mt5-rpyc-{project_path.name}"

    try:
        subprocess.run(
            ["systemctl", "--user", "start", service_name],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def stop_service(project_path: Path) -> bool:
    """Stop the RPyC service."""
    service_name = f"mt5-rpyc-{project_path.name}"

    try:
        subprocess.run(
            ["systemctl", "--user", "stop", service_name],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def restart_service(project_path: Path) -> bool:
    """Restart the RPyC service."""
    service_name = f"mt5-rpyc-{project_path.name}"

    try:
        subprocess.run(
            ["systemctl", "--user", "restart", service_name],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_service_status(project_path: Path) -> Optional[str]:
    """Get service status."""
    service_name = f"mt5-rpyc-{project_path.name}"

    try:
        result = subprocess.run(
            ["systemctl", "--user", "status", service_name],
            capture_output=True,
            text=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None
