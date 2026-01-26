"""Environment detection module for mt5linux setup automation."""

import glob
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Literal, Optional, List

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

try:
    from loguru import logger
except ImportError:
    # Fallback to standard logging if loguru not available
    import logging

    logger = logging.getLogger(__name__)


@dataclass
class ComponentInfo:
    """Information about a detected component."""

    found: bool
    path: Optional[str] = None
    version: Optional[str] = None


@dataclass
class DetectionResult:
    """Comprehensive environment detection results."""

    environment_type: Literal["remote", "local"]
    display_system: Literal["x11", "wayland", "none"]
    wine: ComponentInfo
    python_system: ComponentInfo
    python_windows: ComponentInfo
    mt5: ComponentInfo
    rpyc: ComponentInfo
    thinlinc: ComponentInfo = field(default_factory=lambda: ComponentInfo(found=False))
    x11_server: ComponentInfo = field(default_factory=lambda: ComponentInfo(found=False))
    window_manager: ComponentInfo = field(default_factory=lambda: ComponentInfo(found=False))
    xyphir: ComponentInfo = field(default_factory=lambda: ComponentInfo(found=False))
    missing_components: List[str] = field(default_factory=list)
    installation_plan: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Generate missing components list and installation plan after initialization."""
        self.missing_components = []
        self.installation_plan = []

        if not self.wine.found:
            self.missing_components.append("wine")
            self.installation_plan.append("Install Wine via system package manager")

        if not self.python_system.found:
            self.missing_components.append("python-system")
            self.installation_plan.append("Install system Python (should already be present)")

        if not self.python_windows.found:
            self.missing_components.append("python-windows")
            self.installation_plan.append("Install Windows Python via Wine")

        if not self.mt5.found:
            self.missing_components.append("mt5")
            self.installation_plan.append("Install MetaTrader5 via Wine")

        if not self.rpyc.found:
            self.missing_components.append("rpyc")
            self.installation_plan.append("Install rpyc in Windows Python")

        # Remote components (only check if remote environment)
        if self.environment_type == "remote":
            if not self.thinlinc.found:
                self.missing_components.append("thinlinc")
                self.installation_plan.append("Install ThinLinc for remote GUI access")
            if not self.x11_server.found:
                self.missing_components.append("x11-server")
                self.installation_plan.append("Install X11 server (Xvfb) for remote display")
            if not self.window_manager.found:
                self.missing_components.append("window-manager")
                self.installation_plan.append("Install lightweight window manager (openbox)")


def detect_environment_type() -> Literal["remote", "local"]:
    """
    Detect whether the system is running on a remote server or local desktop.

    Returns:
        "remote" if SSH connection or ThinLinc detected, "local" otherwise
    """
    logger.debug("Starting environment type detection")
    # Check SSH connection
    ssh_connection = os.environ.get("SSH_CONNECTION")
    ssh_client = os.environ.get("SSH_CLIENT")

    if ssh_connection or ssh_client:
        logger.info(f"Detected remote environment via SSH: CONNECTION={ssh_connection}, CLIENT={ssh_client}")
        return "remote"

    # Check for ThinLinc processes
    if psutil:
        try:
            for proc in psutil.process_iter(["name"]):
                proc_name = proc.info.get("name", "").lower()
                if "thinlinc" in proc_name or "tlclient" in proc_name:
                    logger.info(f"Detected remote environment via ThinLinc process: {proc_name}")
                    return "remote"
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug(f"Error checking ThinLinc processes: {e}")
            pass

    # Check DISPLAY for remote X11 forwarding (e.g., "localhost:10.0")
    display = os.environ.get("DISPLAY", "")
    if display and ":" in display:
        # Check if it's a forwarded display (not :0.0 which is typically local)
        parts = display.split(":")
        if len(parts) > 1 and parts[0] not in ("", "unix"):
            try:
                display_num = int(parts[1].split(".")[0])
                if display_num >= 10:  # Typically forwarded displays are >= 10
                    logger.info(f"Detected remote environment via X11 forwarding: DISPLAY={display}")
                    return "remote"
            except (ValueError, IndexError) as e:
                logger.debug(f"Error parsing DISPLAY variable '{display}': {e}")

    logger.info("Detected local environment")
    return "local"


def detect_display_system() -> Literal["x11", "wayland", "none"]:
    """
    Detect the display system (X11, Wayland, or none).

    Returns:
        "x11" if X11 detected, "wayland" if Wayland detected, "none" otherwise
    """
    logger.debug("Starting display system detection")
    # Check for Wayland first (more specific)
    wayland_display = os.environ.get("WAYLAND_DISPLAY")
    if wayland_display:
        logger.info(f"Detected Wayland display system: WAYLAND_DISPLAY={wayland_display}")
        return "wayland"

    # Check for X11
    display = os.environ.get("DISPLAY")
    if display:
        # Check if X11 socket exists (optional verification)
        # For now, if DISPLAY is set, assume X11
        logger.info(f"Detected X11 display system: DISPLAY={display}")
        return "x11"

    logger.info("No display system detected (headless/server mode)")
    return "none"


def detect_wine() -> ComponentInfo:
    """
    Detect Wine installation.

    Returns:
        ComponentInfo with found status, path, and version if available
    """
    logger.debug("Starting Wine detection")
    wine_path = shutil.which("wine")
    if not wine_path:
        logger.info("Wine not found in PATH")
        return ComponentInfo(found=False)

    # Validate wine_path is executable
    if not os.access(wine_path, os.X_OK):
        logger.warning(f"Wine found at {wine_path} but not executable")
        return ComponentInfo(found=False)

    # Try to get Wine version
    version: Optional[str] = None
    try:
        result = subprocess.run(
            ["wine", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            logger.info(f"Wine detected: path={wine_path}, version={version}")
        else:
            logger.warning(f"Wine version check failed with return code {result.returncode}")
    except subprocess.TimeoutExpired:
        logger.warning("Wine version check timed out")
    except (FileNotFoundError, OSError) as e:
        logger.warning(f"Error checking Wine version: {e}")

    return ComponentInfo(found=True, path=wine_path, version=version)


def detect_python_system() -> ComponentInfo:
    """
    Detect system Python installation.

    Returns:
        ComponentInfo with found status, path, and version if available
    """
    logger.debug("Starting system Python detection")
    python_path = shutil.which("python3") or shutil.which("python")
    if not python_path:
        logger.info("System Python not found in PATH")
        return ComponentInfo(found=False)

    # Try to get Python version
    version: Optional[str] = None
    try:
        result = subprocess.run(
            [python_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            logger.info(f"System Python detected: path={python_path}, version={version}")
        else:
            logger.warning(f"Python version check failed with return code {result.returncode}")
    except subprocess.TimeoutExpired:
        logger.warning("Python version check timed out")
    except (FileNotFoundError, OSError) as e:
        logger.warning(f"Error checking Python version: {e}")

    return ComponentInfo(found=True, path=python_path, version=version)


def detect_python_windows(wine_path: Optional[str] = None, wine_prefix: Optional[str] = None) -> ComponentInfo:
    """
    Detect Windows Python installation via Wine.

    Args:
        wine_path: Path to Wine executable (optional, will detect if not provided)

    Returns:
        ComponentInfo with found status, path, and version if available
    """
    if not wine_path:
        wine_path = shutil.which("wine")
        if not wine_path:
            return ComponentInfo(found=False)

    # Use provided prefix first, then fall back to common locations
    wine_prefixes = []
    if wine_prefix and os.path.isdir(wine_prefix):
        wine_prefixes.append(wine_prefix)
    wine_prefixes.extend([
        os.path.join(os.getcwd(), ".mt5"),  # Default mt5linux prefix
        os.path.expanduser("~/.wine"),
        os.path.join(os.getcwd(), ".wine"),
    ])

    # Check for Python in common Wine locations
    python_paths = [
        "drive_c/Python*/python.exe",
        "drive_c/Python*/python3.exe",
        "drive_c/Program Files/Python*/python.exe",
        "drive_c/Program Files/Python*/python3.exe",
    ]

    logger.debug(f"Starting Windows Python detection via Wine: {wine_path}")
    for prefix in wine_prefixes:
        if not os.path.isdir(prefix):
            logger.debug(f"Wine prefix not found: {prefix}")
            continue

        for python_pattern in python_paths:
            full_pattern = os.path.join(prefix, python_pattern)
            try:
                matches = glob.glob(full_pattern)
            except Exception as e:
                logger.warning(f"Error globbing Python pattern '{full_pattern}': {e}")
                continue

            if matches:
                python_exe = matches[0]
                # Validate wine_path is executable before using it
                if not os.access(wine_path, os.X_OK):
                    logger.warning(f"Wine path {wine_path} is not executable")
                    continue

                # Try to get version
                version: Optional[str] = None
                try:
                    result = subprocess.run(
                        [wine_path, python_exe, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        version = result.stdout.strip()
                        logger.info(f"Windows Python detected: path={python_exe}, version={version}")
                    else:
                        logger.warning(f"Windows Python version check failed with return code {result.returncode}")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Windows Python version check timed out for {python_exe}")
                except (FileNotFoundError, OSError) as e:
                    logger.warning(f"Error checking Windows Python version: {e}")

                return ComponentInfo(found=True, path=python_exe, version=version)

    logger.info("Windows Python not found in Wine prefixes")

    return ComponentInfo(found=False)


def detect_mt5(wine_path: Optional[str] = None, wine_prefix: Optional[str] = None) -> ComponentInfo:
    """
    Detect MetaTrader5 installation.

    Args:
        wine_path: Path to Wine executable (optional, will detect if not provided)

    Returns:
        ComponentInfo with found status and path if available
    """
    logger.debug("Starting MetaTrader5 detection")
    if not wine_path:
        wine_path = shutil.which("wine")
        if not wine_path:
            logger.info("Wine not found, cannot detect MT5")
            return ComponentInfo(found=False)

    # Use provided prefix first, then fall back to common locations
    wine_prefixes = []
    if wine_prefix and os.path.isdir(wine_prefix):
        wine_prefixes.append(wine_prefix)
    wine_prefixes.extend([
        os.path.join(os.getcwd(), ".mt5"),  # Default mt5linux prefix
        os.path.expanduser("~/.wine"),
        os.path.join(os.getcwd(), ".wine"),
    ])

    mt5_paths = [
        "drive_c/Program Files/MetaTrader 5/terminal64.exe",
        "drive_c/Program Files (x86)/MetaTrader 5/terminal64.exe",
    ]

    for prefix in wine_prefixes:
        if not os.path.isdir(prefix):
            logger.debug(f"Wine prefix not found: {prefix}")
            continue

        for mt5_path in mt5_paths:
            full_path = os.path.join(prefix, mt5_path)
            if os.path.isfile(full_path):
                logger.info(f"MetaTrader5 detected: path={full_path}")
                return ComponentInfo(found=True, path=full_path)

    logger.info("MetaTrader5 not found in Wine prefixes")
    return ComponentInfo(found=False)


def detect_rpyc(wine_path: Optional[str] = None, python_windows_path: Optional[str] = None) -> ComponentInfo:
    """
    Detect rpyc installation in Windows Python.

    Args:
        wine_path: Path to Wine executable (optional, will detect if not provided)
        python_windows_path: Path to Windows Python executable (optional)

    Returns:
        ComponentInfo with found status and version if available
    """
    logger.debug("Starting rpyc detection")
    if not wine_path:
        wine_path = shutil.which("wine")
        if not wine_path:
            logger.info("Wine not found, cannot detect rpyc")
            return ComponentInfo(found=False)

    # Validate wine_path is executable
    if not os.access(wine_path, os.X_OK):
        logger.warning(f"Wine path {wine_path} is not executable")
        return ComponentInfo(found=False)

    # If Python Windows path not provided, try to detect it
    if not python_windows_path:
        python_info = detect_python_windows(wine_path)
        if not python_info.found or not python_info.path:
            logger.info("Windows Python not found, cannot detect rpyc")
            return ComponentInfo(found=False)
        python_windows_path = python_info.path

    # Try to import rpyc and get version
    version: Optional[str] = None
    try:
        result = subprocess.run(
            [wine_path, python_windows_path, "-c", "import rpyc; print(rpyc.__version__)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            logger.info(f"rpyc detected: path={python_windows_path}, version={version}")
            return ComponentInfo(found=True, path=python_windows_path, version=version)
        else:
            logger.warning(f"rpyc import check failed with return code {result.returncode}: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.warning("rpyc import check timed out")
    except (FileNotFoundError, OSError) as e:
        logger.warning(f"Error checking rpyc: {e}")

    logger.info("rpyc not found in Windows Python")
    return ComponentInfo(found=False)


def detect_thinlinc() -> ComponentInfo:
    """
    Detect ThinLinc installation.

    Returns:
        ComponentInfo with found status, path, and version if available
    """
    logger.debug("Starting ThinLinc detection")

    # Check for thinlinc-server executable
    thinlinc_server = shutil.which("thinlinc-server")
    if thinlinc_server:
        logger.info(f"ThinLinc server detected: path={thinlinc_server}")
        return ComponentInfo(found=True, path=thinlinc_server)

    # Check for tlclient executable
    tlclient = shutil.which("tlclient")
    if tlclient:
        logger.info(f"ThinLinc client detected: path={tlclient}")
        return ComponentInfo(found=True, path=tlclient)

    # Check for ThinLinc installation directory
    thinlinc_dirs = [
        "/opt/thinlinc",
        "/usr/local/thinlinc",
        os.path.expanduser("~/thinlinc"),
    ]
    for thinlinc_dir in thinlinc_dirs:
        if os.path.isdir(thinlinc_dir):
            logger.info(f"ThinLinc installation directory detected: {thinlinc_dir}")
            return ComponentInfo(found=True, path=thinlinc_dir)

    # Check for ThinLinc processes (already done in detect_environment_type, but check again)
    if psutil:
        try:
            for proc in psutil.process_iter(["name"]):
                proc_name = proc.info.get("name", "").lower()
                if "thinlinc" in proc_name or "tlclient" in proc_name:
                    logger.info(f"ThinLinc process detected: {proc_name}")
                    return ComponentInfo(found=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug(f"Error checking ThinLinc processes: {e}")

    logger.info("ThinLinc not found")
    return ComponentInfo(found=False)


def detect_x11_server() -> ComponentInfo:
    """
    Detect X11 server installation (Xvfb or X server).

    Returns:
        ComponentInfo with found status and path if available
    """
    logger.debug("Starting X11 server detection")

    # Check for Xvfb (virtual framebuffer X server)
    xvfb_path = shutil.which("Xvfb")
    if xvfb_path:
        # Try to get version
        version: Optional[str] = None
        try:
            result = subprocess.run(
                [xvfb_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Extract version from output (format: "Xvfb X.Org X Server 1.20.13")
                output_lines = result.stdout.split("\n")
                if output_lines:
                    version = output_lines[0].strip()
                logger.info(f"Xvfb detected: path={xvfb_path}, version={version}")
            else:
                logger.info(f"Xvfb detected: path={xvfb_path}")
        except subprocess.TimeoutExpired:
            logger.warning("Xvfb version check timed out")
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Error checking Xvfb version: {e}")

        return ComponentInfo(found=True, path=xvfb_path, version=version)

    # Check for standard X server as fallback
    x_server = shutil.which("X")
    if x_server:
        logger.info(f"X server detected: path={x_server}")
        return ComponentInfo(found=True, path=x_server)

    logger.info("X11 server not found")
    return ComponentInfo(found=False)


def detect_window_manager() -> ComponentInfo:
    """
    Detect lightweight window manager installation (openbox, fluxbox, jwm).

    Returns:
        ComponentInfo with found status, path, and version if available
    """
    logger.debug("Starting window manager detection")

    # Check for common lightweight window managers (in order of preference)
    window_managers = [
        ("openbox", "openbox"),
        ("fluxbox", "fluxbox"),
        ("jwm", "jwm"),
    ]

    for wm_name, wm_executable in window_managers:
        wm_path = shutil.which(wm_executable)
        if wm_path:
            # Try to get version
            version: Optional[str] = None
            try:
                result = subprocess.run(
                    [wm_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    logger.info(f"{wm_name} detected: path={wm_path}, version={version}")
                else:
                    logger.info(f"{wm_name} detected: path={wm_path}")
            except subprocess.TimeoutExpired:
                logger.warning(f"{wm_name} version check timed out")
            except (FileNotFoundError, OSError) as e:
                logger.warning(f"Error checking {wm_name} version: {e}")

            return ComponentInfo(found=True, path=wm_path, version=version)

    logger.info("Window manager not found")
    return ComponentInfo(found=False)


def detect_xyphir() -> ComponentInfo:
    """
    Detect xyphir installation for Wayland GUI automation.

    Returns:
        ComponentInfo with found status, path, and version if available
    """
    logger.debug("Starting xyphir detection")
    xyphir_path = shutil.which("xyphir")
    if not xyphir_path:
        logger.info("xyphir not found in PATH")
        return ComponentInfo(found=False)

    # Validate xyphir_path is executable
    if not os.access(xyphir_path, os.X_OK):
        logger.warning(f"xyphir found at {xyphir_path} but not executable")
        return ComponentInfo(found=False)

    # Try to get version
    version: Optional[str] = None
    try:
        result = subprocess.run(
            [xyphir_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            logger.info(f"xyphir detected: path={xyphir_path}, version={version}")
        else:
            # Try alternative version flag
            result = subprocess.run(
                [xyphir_path, "-v"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"xyphir detected: path={xyphir_path}, version={version}")
            else:
                logger.info(f"xyphir detected: path={xyphir_path} (version check failed)")
    except subprocess.TimeoutExpired:
        logger.warning("xyphir version check timed out")
    except (FileNotFoundError, OSError) as e:
        logger.warning(f"Error checking xyphir version: {e}")

    return ComponentInfo(found=True, path=xyphir_path, version=version)


def detect_environment(wine_prefix: Optional[str] = None) -> DetectionResult:
    """
    Perform comprehensive environment detection.

    Detects:
    - Environment type (remote/local)
    - Display system (X11/Wayland/none)
    - Wine installation
    - System Python installation
    - Windows Python installation (via Wine)
    - MetaTrader5 installation
    - rpyc installation
    - ThinLinc installation (remote only)
    - X11 server installation (remote only)
    - Window manager installation (remote only)
    - xyphir installation (local Wayland only)

    Args:
        wine_prefix: Optional Wine prefix path to use for detection (from saved config)

    Returns:
        DetectionResult with all detection information, including missing components
        and installation plan
    """
    logger.info("Starting comprehensive environment detection")
    # Detect environment type and display system
    environment_type = detect_environment_type()
    display_system = detect_display_system()

    # Detect components
    wine = detect_wine()
    python_system = detect_python_system()
    python_windows = detect_python_windows(wine.path if wine.found else None, wine_prefix)
    mt5 = detect_mt5(wine.path if wine.found else None, wine_prefix)
    rpyc = detect_rpyc(
        wine.path if wine.found else None,
        python_windows.path if python_windows.found else None,
    )

    # Detect remote components (only if remote environment)
    thinlinc = ComponentInfo(found=False)
    x11_server = ComponentInfo(found=False)
    window_manager = ComponentInfo(found=False)
    if environment_type == "remote":
        thinlinc = detect_thinlinc()
        x11_server = detect_x11_server()
        window_manager = detect_window_manager()

    # Detect xyphir (only if local environment with Wayland)
    xyphir = ComponentInfo(found=False)
    if environment_type == "local" and display_system == "wayland":
        xyphir = detect_xyphir()

    # Create result (missing_components and installation_plan will be auto-generated)
    result = DetectionResult(
        environment_type=environment_type,
        display_system=display_system,
        wine=wine,
        python_system=python_system,
        python_windows=python_windows,
        mt5=mt5,
        rpyc=rpyc,
        thinlinc=thinlinc,
        x11_server=x11_server,
        window_manager=window_manager,
        xyphir=xyphir,
    )

    logger.info(
        f"Environment detection complete: type={environment_type}, display={display_system}, "
        f"missing={len(result.missing_components)} components"
    )
    return result
