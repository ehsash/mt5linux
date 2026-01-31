"""Wine installation and prefix management."""

import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console

console = Console()


def install_wine_staging(on_status: Optional[Callable[[str], None]] = None) -> bool:
    """Install Wine Staging from WineHQ. Requires sudo."""

    def status(msg: str) -> None:
        if on_status:
            on_status(msg)
        else:
            console.print(f"  {msg}")

    commands = [
        (
            ["sudo", "dpkg", "--add-architecture", "i386"],
            "Enabling 32-bit architecture",
        ),
        (
            ["sudo", "mkdir", "-pm755", "/etc/apt/keyrings"],
            "Creating keyrings directory",
        ),
        (
            [
                "sudo",
                "wget",
                "-O",
                "/etc/apt/keyrings/winehq-archive.key",
                "https://dl.winehq.org/wine-builds/winehq.key",
            ],
            "Downloading WineHQ key",
        ),
        (
            [
                "sudo",
                "wget",
                "-NP",
                "/etc/apt/sources.list.d/",
                "https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources",
            ],
            "Adding WineHQ repository",
        ),
        (["sudo", "apt-get", "update"], "Updating package list"),
        (
            [
                "sudo",
                "apt-get",
                "install",
                "-y",
                "--install-recommends",
                "winehq-staging",
            ],
            "Installing Wine Staging",
        ),
    ]

    for cmd, description in commands:
        status(description)
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            console.print(f"[red]Failed: {description}[/red]")
            return False

    return True


def create_wine_prefix(prefix_path: Path) -> bool:
    """Initialize a Wine prefix."""
    prefix_path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix_path)
    env["WINEARCH"] = "win64"

    # Unset WAYLAND_DISPLAY for better compatibility
    env.pop("WAYLAND_DISPLAY", None)

    try:
        subprocess.run(
            ["wineboot", "--init"],
            env=env,
            check=True,
            capture_output=True,
            timeout=120,
        )
        return True
    except subprocess.CalledProcessError:
        return False
    except subprocess.TimeoutExpired:
        return False


def install_python_in_wine(
    prefix_path: Path,
    python_version: str = "3.12.8",
) -> bool:
    """Download and install Python in Wine prefix."""
    downloads_dir = prefix_path / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    installer_name = f"python-{python_version}-amd64.exe"
    installer_path = downloads_dir / installer_name

    # Download if not present
    if not installer_path.exists():
        url = f"https://www.python.org/ftp/python/{python_version}/{installer_name}"
        console.print(f"  Downloading Python {python_version}...")
        try:
            urllib.request.urlretrieve(url, installer_path)
        except Exception as e:
            console.print(f"[red]Download failed: {e}[/red]")
            return False

    # Install silently
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix_path)
    env["WINEARCH"] = "win64"
    env.pop("WAYLAND_DISPLAY", None)

    console.print("  Installing Python (silent mode)...")
    try:
        subprocess.run(
            [
                "wine",
                str(installer_path),
                "/quiet",
                "InstallAllUsers=0",
                "PrependPath=1",
                "Include_test=0",
                "TargetDir=C:\\Python312",
            ],
            env=env,
            check=True,
            capture_output=True,
            timeout=300,
        )
        return True
    except subprocess.CalledProcessError:
        return False
    except subprocess.TimeoutExpired:
        return False


def install_packages_in_wine(prefix_path: Path, python_exe: Path) -> bool:
    """Install required packages in Wine Python."""
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix_path)
    env["WINEARCH"] = "win64"
    env.pop("WAYLAND_DISPLAY", None)

    packages = ["rpyc==5.0.1", "MetaTrader5"]

    for package in packages:
        console.print(f"  Installing {package}...")
        try:
            subprocess.run(
                ["wine", str(python_exe), "-m", "pip", "install", package],
                env=env,
                check=True,
                capture_output=True,
                timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            console.print(f"[yellow]Warning: Failed to install {package}[/yellow]")

    return True


MT5_SETUP_URL = (
    "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
)
WEBVIEW2_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"


def detect_display_mode() -> str:
    """Detect current display mode: 'wayland', 'xorg', or 'server'."""
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "server"
    elif os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    else:
        return "xorg"


def _install_webview2(
    installer_path: Path,
    env: dict,
    display_mode: str,
) -> bool:
    """Install WebView2 runtime in Wine.

    Runs interactively (silent mode hangs under Wine).
    Uses virtual desktop on Wayland for compatibility.
    """
    install_env = env.copy()

    console.print("[yellow]  Complete the WebView2 installer wizard...[/yellow]")

    try:
        if display_mode == "wayland":
            # Use virtual desktop for Wayland compatibility
            install_env.pop("WAYLAND_DISPLAY", None)
            subprocess.run(
                [
                    "wine",
                    "explorer",
                    "/desktop=WebView2,800x600",
                    str(installer_path),
                ],
                env=install_env,
            )
        else:
            subprocess.run(
                ["wine", str(installer_path)],
                env=install_env,
            )
        console.print("[green]  WebView2 installed[/green]")
        return True
    except Exception as e:
        console.print(f"[red]  WebView2 install failed: {e}[/red]")
        return False


def install_mt5_terminal(prefix_path: Path) -> bool:
    """Download and install MetaTrader 5 terminal.

    This function launches the MT5 installer GUI.
    On Wayland, uses XWayland with virtual desktop for input compatibility.

    Returns True if installation completed (terminal64.exe exists).
    """
    downloads_dir = prefix_path / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix_path)
    env["WINEARCH"] = "win64"

    display_mode = detect_display_mode()

    # Check display availability
    if display_mode == "server" and not os.environ.get("DISPLAY"):
        console.print("[red]No display available.[/red]")
        console.print("Please connect via ThinLinc first, then run setup() again.")
        return False

    # Download MT5 installer
    mt5_installer = downloads_dir / "mt5setup.exe"
    if not mt5_installer.exists():
        console.print("  Downloading MT5 installer...")
        try:
            urllib.request.urlretrieve(MT5_SETUP_URL, mt5_installer)
        except Exception as e:
            console.print(f"[red]Download failed: {e}[/red]")
            return False

    # Download WebView2 runtime (required for MT5 web features)
    webview2_installer = downloads_dir / "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
    if not webview2_installer.exists():
        console.print("  Downloading WebView2 runtime...")
        try:
            urllib.request.urlretrieve(WEBVIEW2_URL, webview2_installer)
        except Exception as e:
            console.print(f"[yellow]WebView2 download failed: {e}[/yellow]")

    # Configure Wine for Windows 10 emulation
    console.print("  Configuring Wine for Windows 10...")
    subprocess.run(
        [
            "wine",
            "reg",
            "add",
            "HKEY_CURRENT_USER\\Software\\Wine",
            "/v",
            "Version",
            "/t",
            "REG_SZ",
            "/d",
            "win10",
            "/f",
        ],
        env=env,
        capture_output=True,
    )

    # Install WebView2 (required for MT5)
    if webview2_installer.exists():
        console.print("  Installing WebView2 runtime...")
        if not _install_webview2(webview2_installer, env, display_mode):
            console.print("[red]WebView2 installation failed - cannot proceed[/red]")
            return False
    else:
        console.print("[red]WebView2 installer not found - cannot proceed[/red]")
        return False

    # Launch MT5 installer based on display mode
    if display_mode == "wayland":
        console.print("  Wayland detected - using XWayland with virtual desktop...")
        console.print("  (This fixes mouse/keyboard input issues)")

        # Unset WAYLAND_DISPLAY to force X11 driver via XWayland
        env.pop("WAYLAND_DISPLAY", None)

        # Configure Wine for XWayland compatibility (per ArchWiki)
        subprocess.run(
            [
                "wine",
                "reg",
                "add",
                "HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver",
                "/v",
                "UseTakeFocus",
                "/t",
                "REG_SZ",
                "/d",
                "N",
                "/f",
            ],
            env=env,
            capture_output=True,
        )

        # Run with virtual desktop
        console.print("[bold]Launching MT5 installer...[/bold]")
        console.print(
            "[yellow]Complete the installation wizard in the popup window.[/yellow]"
        )
        console.print(
            "[yellow]DO NOT change the installation path - use the default.[/yellow]"
        )

        subprocess.run(
            [
                "wine",
                "explorer",
                "/desktop=MT5Install,1280x1024",
                str(mt5_installer),
            ],
            env=env,
        )
    else:
        # Standard X11 mode
        console.print("[bold]Launching MT5 installer...[/bold]")
        console.print(
            "[yellow]Complete the installation wizard in the popup window.[/yellow]"
        )
        console.print(
            "[yellow]DO NOT change the installation path - use the default.[/yellow]"
        )

        subprocess.run(
            ["wine", str(mt5_installer)],
            env=env,
        )

    # Check if MT5 was installed
    return _wait_for_mt5_installation(prefix_path)


def _wait_for_mt5_installation(prefix_path: Path, timeout_seconds: int = 300) -> bool:
    """Wait for MT5 terminal to be installed.

    Polls for terminal64.exe existence.
    """
    import time

    console.print("  Waiting for MT5 installation to complete...")

    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        # Check if terminal64.exe exists
        mt5_exe = list(prefix_path.glob("drive_c/**/terminal64.exe"))
        if mt5_exe:
            console.print("[green]✓ MT5 terminal detected[/green]")
            return True

        # Check if installer is still running
        result = subprocess.run(
            ["pgrep", "-f", "mt5setup.exe"],
            capture_output=True,
        )
        if result.returncode != 0:
            # Installer finished, final check
            time.sleep(3)
            mt5_exe = list(prefix_path.glob("drive_c/**/terminal64.exe"))
            if mt5_exe:
                console.print("[green]✓ MT5 terminal detected[/green]")
                return True
            else:
                console.print(
                    "[yellow]MT5 installer closed but terminal not found.[/yellow]"
                )
                return False

        time.sleep(5)

    console.print("[yellow]Timeout waiting for MT5 installation.[/yellow]")
    return False
