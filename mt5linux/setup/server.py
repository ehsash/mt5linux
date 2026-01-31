"""Server environment detection and setup (ThinLinc, X server)."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


def is_server_environment() -> bool:
    """Detect if running on a headless server (no display)."""
    return not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")


def is_thinlinc_installed() -> bool:
    """Check if ThinLinc server is installed."""
    return subprocess.run(["which", "tlwebadm"], capture_output=True).returncode == 0


def is_xserver_installed() -> bool:
    """Check if X server is installed."""
    return subprocess.run(["which", "Xorg"], capture_output=True).returncode == 0


def get_server_ip() -> Optional[str]:
    """Get server IP address for ThinLinc connection instructions."""
    try:
        result = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, check=True
        )
        ips = result.stdout.strip().split()
        return ips[0] if ips else None
    except subprocess.CalledProcessError:
        return None


def install_xserver_and_desktop() -> bool:
    """Install X server and XFCE desktop environment."""
    console.print("[bold]Installing X server and XFCE desktop...[/bold]")

    packages = [
        "xorg",
        "xserver-xorg",
        "xfce4",
        "xfce4-goodies",
        "lightdm",
        "dbus-x11",
    ]

    try:
        subprocess.run(
            ["sudo", "apt-get", "update"],
            check=True,
        )
        subprocess.run(
            ["sudo", "apt-get", "install", "-y"] + packages,
            check=True,
        )
        subprocess.run(
            ["sudo", "systemctl", "enable", "lightdm"],
            check=True,
        )
        console.print("[green]✓ X server and XFCE installed[/green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to install X server: {e}[/red]")
        return False


def install_thinlinc_server() -> bool:
    """Install ThinLinc server for remote desktop access.

    This function downloads ThinLinc, then launches the interactive installer
    for the user to complete manually.
    """
    console.print("[bold]Installing ThinLinc server...[/bold]")

    thinlinc_version = "4.17.0"
    download_dir = Path("/tmp/thinlinc-install")
    download_dir.mkdir(parents=True, exist_ok=True)

    thinlinc_url = (
        f"https://www.cendio.com/downloads/server/tl-{thinlinc_version}-server.zip"
    )
    zip_file = download_dir / f"tl-{thinlinc_version}-server.zip"

    try:
        # Download ThinLinc
        if not zip_file.exists():
            console.print(f"  Downloading ThinLinc {thinlinc_version}...")
            subprocess.run(
                ["wget", "-q", "--show-progress", "-O", str(zip_file), thinlinc_url],
                check=True,
            )

        # Extract
        console.print("  Extracting ThinLinc...")
        subprocess.run(
            ["unzip", "-o", "-q", str(zip_file), "-d", str(download_dir)],
            check=True,
        )

        # Show instructions and wait for user
        install_dir = download_dir / f"tl-{thinlinc_version}-server"
        console.print("\n[bold cyan]" + "=" * 70 + "[/bold cyan]")
        console.print("[bold]ThinLinc Interactive Installation[/bold]")
        console.print("[bold cyan]" + "=" * 70 + "[/bold cyan]\n")

        console.print("The ThinLinc installer will now launch.")
        console.print("Please answer the questions in the installer.\n")
        console.print("[yellow]Recommended settings:[/yellow]")
        console.print("  - Accept defaults for most questions")
        console.print("  - Desktop environment: XFCE (will be configured automatically)\n")

        console.print("[bold]Press Enter to launch the installer...[/bold]")
        input()

        # Launch installer interactively
        console.print("\n[bold]Launching ThinLinc installer...[/bold]\n")
        result = subprocess.run(
            ["sudo", str(install_dir / "install-server")],
            # No capture_output - let user interact directly
        )

        if result.returncode != 0:
            console.print(f"\n[red]Installer exited with code {result.returncode}[/red]")
            return False

        # Configure for XFCE
        console.print("\n[bold]Configuring ThinLinc for XFCE...[/bold]")
        result = subprocess.run(
            ["sudo", "/opt/thinlinc/bin/tl-config", "/vsmagent/default_session=startxfce4"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[yellow]Warning: tl-config failed: {result.stderr}[/yellow]")

        # Enable and start services
        console.print("  Enabling ThinLinc services...")
        for service in ["tlwebadm", "vsmserver", "vsmagent"]:
            subprocess.run(
                ["sudo", "systemctl", "enable", service],
                capture_output=True,
            )
            subprocess.run(
                ["sudo", "systemctl", "restart", service],  # Use restart to apply config
                capture_output=True,
            )

        # Verify configuration was applied
        verify_result = subprocess.run(
            ["grep", "default_session", "/opt/thinlinc/etc/conf.d/vsmagent.hconf"],
            capture_output=True,
            text=True,
        )
        if "startxfce4" in verify_result.stdout:
            console.print("  ✓ XFCE configured as default session")
        else:
            console.print("  [yellow]⚠ Could not verify XFCE configuration[/yellow]")

        console.print("[green]✓ ThinLinc server installed and configured[/green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to install ThinLinc: {e}[/red]")
        return False


def show_thinlinc_instructions(server_ip: Optional[str] = None) -> None:
    """Display instructions for connecting via ThinLinc."""
    if not server_ip:
        server_ip = get_server_ip() or "<server-ip>"

    username = os.environ.get("USER", "<username>")

    console.print("\n[bold cyan]" + "=" * 70 + "[/bold cyan]")
    console.print("[bold]SERVER SETUP COMPLETE - RECONNECTION REQUIRED[/bold]")
    console.print("[bold cyan]" + "=" * 70 + "[/bold cyan]\n")

    console.print("[yellow]Next steps:[/yellow]\n")

    console.print("[bold]1. Download ThinLinc Client[/bold]")
    console.print("   https://www.cendio.com/thinlinc/download\n")

    console.print("[bold]2. Connect to this server[/bold]")
    console.print(f"   Server:   {server_ip}")
    console.print(f"   Username: {username}")
    console.print("   Password: <your Linux password>\n")

    console.print("[bold]3. After connecting via ThinLinc:[/bold]")
    console.print("   Open a terminal and run:")
    console.print(f"   [cyan]cd {Path.cwd()}[/cyan]")
    console.print("   [cyan]python -c 'import mt5linux; mt5linux.setup()'[/cyan]\n")

    console.print("[yellow]Alternative: Web browser[/yellow]")
    console.print(f"   https://{server_ip}:300/\n")

    console.print("[bold cyan]" + "=" * 70 + "[/bold cyan]\n")
