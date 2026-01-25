"""Remote environment installation functions for mt5linux."""

import os
import shutil
import subprocess
from typing import List, Optional

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

try:
    from typer import echo
except ImportError:
    # Fallback if typer not available
    def echo(message: str) -> None:
        print(message)

from mt5linux.detection import DetectionResult, detect_thinlinc, detect_x11_server, detect_window_manager
from mt5linux.setup.installer import InstallationResult, _check_sudo_access


def _verify_remote_gui_access(
    detection_result: DetectionResult, installation_results: List[InstallationResult]
) -> None:
    """
    Verify that remote GUI access is functional after installation.

    Args:
        detection_result: DetectionResult with component information
        installation_results: List of installation results
    """
    # Check if X11 server is available (required for GUI access)
    x11_available = False
    for result in installation_results:
        if result.component == "x11-server" and result.success:
            x11_available = True
            break

    # Also check detection result for already-installed X11 server
    if not x11_available and detection_result.x11_server.found:
        x11_available = True

    if x11_available:
        # Verify X11 server can start (basic functional check)
        x11_path = detection_result.x11_server.path
        if not x11_path:
            # Try to find it from installation results
            for result in installation_results:
                if result.component == "x11-server" and result.path:
                    x11_path = result.path
                    break

        if x11_path:
            try:
                # Test that Xvfb can start (dry run with help flag)
                test_result = subprocess.run(
                    [x11_path, "-help"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if test_result.returncode in (0, 1):  # Help typically exits with 1
                    logger.info("X11 server functional verification passed")
                else:
                    logger.warning(f"X11 server verification returned unexpected code: {test_result.returncode}")
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                logger.warning(f"X11 server functional verification failed: {e}")


def install_thinlinc(detection_result: Optional[DetectionResult] = None) -> InstallationResult:
    """
    Install ThinLinc for remote GUI access.

    Args:
        detection_result: Optional DetectionResult to check if ThinLinc is already installed

    Returns:
        InstallationResult with installation status
    """
    logger.info("Starting ThinLinc installation")

    # Check if ThinLinc is already installed
    if detection_result:
        if detection_result.thinlinc.found:
            logger.info(f"ThinLinc already installed at {detection_result.thinlinc.path}")
            return InstallationResult(
                component="thinlinc",
                success=True,
                installed=False,  # Skipped - already installed
                path=detection_result.thinlinc.path,
            )
    else:
        # Re-detect to be sure
        thinlinc_info = detect_thinlinc()
        if thinlinc_info.found:
            logger.info(f"ThinLinc already installed at {thinlinc_info.path}")
            return InstallationResult(
                component="thinlinc",
                success=True,
                installed=False,
                path=thinlinc_info.path,
            )

    # TODO (Story 1.8): Use secure download mechanism when available
    # For now, provide instructions for manual installation
    echo("  ThinLinc installation requires manual setup...")
    logger.warning("Secure download (Story 1.8) not yet available - ThinLinc requires manual installation")
    error_msg = (
        "ThinLinc installation requires manual setup. "
        "Please download ThinLinc from https://www.cendio.com/thinlinc/download "
        "and follow the installation instructions."
    )
    echo(f"  ⚠️  {error_msg}")
    logger.error(error_msg)
    return InstallationResult(
        component="thinlinc",
        success=False,
        installed=False,
        error=error_msg,
        recovery_suggestion=(
            "Download ThinLinc from https://www.cendio.com/thinlinc/download "
            "and install manually. Once installed, run setup again to verify."
        ),
    )


def install_x11_server(detection_result: Optional[DetectionResult] = None) -> InstallationResult:
    """
    Install X11 server (Xvfb) for remote display.

    Args:
        detection_result: Optional DetectionResult to check if X11 server is already installed

    Returns:
        InstallationResult with installation status
    """
    logger.info("Starting X11 server installation")

    # Check if X11 server is already installed
    if detection_result:
        if detection_result.x11_server.found:
            logger.info(f"X11 server already installed at {detection_result.x11_server.path}")
            return InstallationResult(
                component="x11-server",
                success=True,
                installed=False,  # Skipped - already installed
                path=detection_result.x11_server.path,
                version=detection_result.x11_server.version,
            )
    else:
        # Re-detect to be sure
        x11_info = detect_x11_server()
        if x11_info.found:
            logger.info(f"X11 server already installed at {x11_info.path}")
            return InstallationResult(
                component="x11-server",
                success=True,
                installed=False,
                path=x11_info.path,
                version=x11_info.version,
            )

    # Check sudo access
    if not _check_sudo_access():
        error_msg = "Sudo access required to install X11 server"
        logger.error(error_msg)
        return InstallationResult(
            component="x11-server",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Run with sudo or ensure user has sudo access",
        )

    # Install Xvfb via apt
    # Note: Each installation function runs its own apt update for independence
    # This allows functions to be called individually without dependencies
    try:
        echo("  Updating package list...")
        logger.info("Updating package list...")
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
                component="x11-server",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and apt configuration",
            )

        echo("  Installing Xvfb (X11 virtual framebuffer)...")
        logger.info("Installing Xvfb...")
        install_result = subprocess.run(
            ["sudo", "apt", "install", "-y", "xvfb"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes timeout
        )
        if install_result.returncode != 0:
            error_msg = f"Xvfb installation failed: {install_result.stderr}"
            logger.error(error_msg)
            return InstallationResult(
                component="x11-server",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check apt logs: /var/log/apt/history.log",
            )

        # Verify installation
        echo("  Verifying X11 server installation...")
        x11_info = detect_x11_server()
        if x11_info.found:
            echo(f"  ✓ X11 server installed successfully: {x11_info.path}")
            logger.info(f"X11 server successfully installed at {x11_info.path}")
            return InstallationResult(
                component="x11-server",
                success=True,
                installed=True,
                path=x11_info.path,
                version=x11_info.version,
            )
        else:
            error_msg = "X11 server installation completed but verification failed"
            logger.error(error_msg)
            return InstallationResult(
                component="x11-server",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Try running 'Xvfb -version' manually to verify installation",
            )

    except subprocess.TimeoutExpired as e:
        error_msg = f"X11 server installation timed out: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="x11-server",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Installation may still be in progress. Check system processes.",
        )
    except (FileNotFoundError, OSError) as e:
        error_msg = f"Error during X11 server installation: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="x11-server",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Ensure apt is available and system is up to date",
        )


def install_window_manager(detection_result: Optional[DetectionResult] = None) -> InstallationResult:
    """
    Install lightweight window manager (openbox) for remote GUI.

    Args:
        detection_result: Optional DetectionResult to check if window manager is already installed

    Returns:
        InstallationResult with installation status
    """
    logger.info("Starting window manager installation")

    # Check if window manager is already installed
    if detection_result:
        if detection_result.window_manager.found:
            logger.info(f"Window manager already installed at {detection_result.window_manager.path}")
            return InstallationResult(
                component="window-manager",
                success=True,
                installed=False,  # Skipped - already installed
                path=detection_result.window_manager.path,
                version=detection_result.window_manager.version,
            )
    else:
        # Re-detect to be sure
        wm_info = detect_window_manager()
        if wm_info.found:
            logger.info(f"Window manager already installed at {wm_info.path}")
            return InstallationResult(
                component="window-manager",
                success=True,
                installed=False,
                path=wm_info.path,
                version=wm_info.version,
            )

    # Check sudo access
    if not _check_sudo_access():
        error_msg = "Sudo access required to install window manager"
        logger.error(error_msg)
        return InstallationResult(
            component="window-manager",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Run with sudo or ensure user has sudo access",
        )

    # Install openbox via apt
    # Note: Each installation function runs its own apt update for independence
    # This allows functions to be called individually without dependencies
    try:
        echo("  Updating package list...")
        logger.info("Updating package list...")
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
                component="window-manager",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and apt configuration",
            )

        echo("  Installing openbox (lightweight window manager)...")
        logger.info("Installing openbox...")
        install_result = subprocess.run(
            ["sudo", "apt", "install", "-y", "openbox"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes timeout
        )
        if install_result.returncode != 0:
            error_msg = f"openbox installation failed: {install_result.stderr}"
            logger.error(error_msg)
            return InstallationResult(
                component="window-manager",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check apt logs: /var/log/apt/history.log",
            )

        # Verify installation
        echo("  Verifying window manager installation...")
        wm_info = detect_window_manager()
        if wm_info.found:
            echo(f"  ✓ Window manager installed successfully: {wm_info.path}")
            logger.info(f"Window manager successfully installed at {wm_info.path}")
            return InstallationResult(
                component="window-manager",
                success=True,
                installed=True,
                path=wm_info.path,
                version=wm_info.version,
            )
        else:
            error_msg = "Window manager installation completed but verification failed"
            logger.error(error_msg)
            return InstallationResult(
                component="window-manager",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Try running 'openbox --version' manually to verify installation",
            )

    except subprocess.TimeoutExpired as e:
        error_msg = f"Window manager installation timed out: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="window-manager",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Installation may still be in progress. Check system processes.",
        )
    except (FileNotFoundError, OSError) as e:
        error_msg = f"Error during window manager installation: {e}"
        logger.error(error_msg)
        return InstallationResult(
            component="window-manager",
            success=False,
            installed=False,
            error=error_msg,
            recovery_suggestion="Ensure apt is available and system is up to date",
        )


def install_remote_components(detection_result: DetectionResult) -> List[InstallationResult]:
    """
    Install all missing remote components based on detection results.

    Installs components in order: X11 server → window manager → ThinLinc

    Args:
        detection_result: DetectionResult from environment detection (not mutated)

    Returns:
        List of InstallationResult for each component
    """
    logger.info("Starting installation of remote components")

    # Only execute if remote environment
    if detection_result.environment_type != "remote":
        logger.info("Not a remote environment, skipping remote component installation")
        return []

    results: List[InstallationResult] = []

    # Install X11 server if missing
    if "x11-server" in detection_result.missing_components:
        logger.info("Installing X11 server...")
        x11_result = install_x11_server(detection_result)
        results.append(x11_result)
        if not x11_result.success:
            logger.warning("X11 server installation failed, continuing with other components")

    # Install window manager if missing
    if "window-manager" in detection_result.missing_components:
        logger.info("Installing window manager...")
        wm_result = install_window_manager(detection_result)
        results.append(wm_result)
        if not wm_result.success:
            logger.warning("Window manager installation failed, continuing with other components")

    # Install ThinLinc if missing (may fail due to manual installation requirement)
    if "thinlinc" in detection_result.missing_components:
        logger.info("Installing ThinLinc...")
        thinlinc_result = install_thinlinc(detection_result)
        results.append(thinlinc_result)
        if not thinlinc_result.success:
            logger.warning("ThinLinc installation failed (may require manual installation)")

    # Verify remote GUI access capability (AC #4)
    if results:
        _verify_remote_gui_access(detection_result, results)

    logger.info(f"Remote component installation complete: {len(results)} components processed")
    return results
