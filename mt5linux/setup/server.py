"""Server environment detection and setup (ThinLinc, X server)."""

import os
import pty
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


def _run_with_pty(command: list[str]) -> int:
    """Run a command with a pseudo-TTY to satisfy isatty() checks.

    Returns the exit code of the command.
    """
    import select
    import sys

    def read_output(fd: int) -> bytes:
        """Read available output from file descriptor."""
        try:
            return os.read(fd, 1024)
        except OSError:
            return b""

    # Spawn the process with a pseudo-TTY
    pid, master_fd = pty.fork()

    if pid == 0:
        # Child process - execute the command
        os.execvp(command[0], command)
    else:
        # Parent process - handle I/O and wait for completion
        try:
            while True:
                # Check if there's data to read
                ready, _, _ = select.select([master_fd], [], [], 0.1)

                if ready:
                    try:
                        data = read_output(master_fd)
                        if data:
                            sys.stdout.buffer.write(data)
                            sys.stdout.buffer.flush()
                    except OSError:
                        break

                # Check if child has exited
                pid_result, status = os.waitpid(pid, os.WNOHANG)
                if pid_result != 0:
                    # Child has exited
                    # Read any remaining output
                    while True:
                        try:
                            data = read_output(master_fd)
                            if not data:
                                break
                            sys.stdout.buffer.write(data)
                            sys.stdout.buffer.flush()
                        except OSError:
                            break

                    os.close(master_fd)

                    if os.WIFEXITED(status):
                        return os.WEXITSTATUS(status)
                    elif os.WIFSIGNALED(status):
                        return 128 + os.WTERMSIG(status)
                    return 1
        except Exception:
            os.close(master_fd)
            raise


def install_thinlinc_server() -> bool:
    """Install ThinLinc server for remote desktop access."""
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

        # Install with pseudo-TTY for automated mode
        install_dir = download_dir / f"tl-{thinlinc_version}-server"
        console.print("  Running ThinLinc installer...")

        exit_code = _run_with_pty([
            "sudo",
            str(install_dir / "install-server"),
            "-a",  # Automated mode - accepts defaults
        ])

        if exit_code != 0:
            raise subprocess.CalledProcessError(exit_code, "install-server")

        # Configure for XFCE
        subprocess.run(
            ["sudo", "tl-config", "/vsmagent/default_session", "startxfce4"],
            capture_output=True,
        )

        # Enable and start services
        for service in ["tlwebadm", "vsmserver", "vsmagent"]:
            subprocess.run(
                ["sudo", "systemctl", "enable", service],
                capture_output=True,
            )
            subprocess.run(
                ["sudo", "systemctl", "start", service],
                capture_output=True,
            )

        console.print("[green]✓ ThinLinc server installed[/green]")
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
