"""Installation functions for mt5linux dependencies."""

import os
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from mt5linux.detection import DetectionResult, detect_wine, detect_python_windows, detect_mt5, detect_rpyc

try:
    from mt5linux.security import download_file_secure, verify_download
except ImportError:
    download_file_secure = None  # type: ignore
    verify_download = None  # type: ignore

# Constants
WINDOWS_PYTHON_VERSION = "3.11.9"
WINDOWS_PYTHON_URL = f"https://www.python.org/ftp/python/{WINDOWS_PYTHON_VERSION}/python-{WINDOWS_PYTHON_VERSION}-amd64.exe"


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
    Check if the current user has sudo access.

    Returns:
        True if user has sudo access, False otherwise
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


def _get_wine_path(wine_path: Optional[str] = None) -> Tuple[Optional[str], Optional[InstallationResult]]:
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


def install_wine(detection_result: Optional[DetectionResult] = None) -> InstallationResult:
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

    # Install Wine via apt
    try:
        from typer import echo

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
                component="wine",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and apt configuration",
            )

        echo("  Installing Wine (this may take several minutes)...")
        logger.info("Installing Wine...")
        install_result = subprocess.run(
            ["sudo", "apt", "install", "-y", "wine"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes timeout
        )
        if install_result.returncode != 0:
            error_msg = f"Wine installation failed: {install_result.stderr}"
            logger.error(error_msg)
            return InstallationResult(
                component="wine",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check apt logs: /var/log/apt/history.log",
            )

        # Verify installation
        echo("  Verifying Wine installation...")
        wine_info = detect_wine()
        if wine_info.found:
            echo(f"  ✓ Wine installed successfully: {wine_info.version}")
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
    wine_path: Optional[str] = None, detection_result: Optional[DetectionResult] = None
) -> InstallationResult:
    """
    Install Windows Python via Wine.

    Args:
        wine_path: Path to Wine executable (optional, will detect if not provided)
        detection_result: Optional DetectionResult to check if Windows Python is already installed

    Returns:
        InstallationResult with installation status
    """
    logger.info("Starting Windows Python installation")
    
    # Check if Windows Python is already installed
    if detection_result:
        if detection_result.python_windows.found:
            logger.info(f"Windows Python already installed at {detection_result.python_windows.path}")
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
        from typer import echo

        # Use secure download mechanism (Story 1.8)
        if download_file_secure is not None and verify_download is not None:
            echo(f"  Downloading Windows Python {WINDOWS_PYTHON_VERSION} installer securely...")
            logger.info(f"Downloading Windows Python installer securely from {WINDOWS_PYTHON_URL}...")
            
            # Download file with signature and checksum
            download_result = download_file_secure(
                WINDOWS_PYTHON_URL,
                installer_path,
                download_signature=True,
                download_checksum=True,
            )
            
            if not download_result.success:
                return InstallationResult(
                    component="python-windows",
                    success=False,
                    installed=False,
                    error=download_result.error or "Download failed",
                    recovery_suggestion=download_result.recovery_suggestion or "Check internet connection and try again",
                )
            
            # Verify downloaded file
            echo("  Verifying file integrity...")
            verification_result = verify_download(
                download_result.file_path or installer_path,
                signature_path=download_result.signature_path,
                checksum_path=download_result.checksum_path,
                require_gpg=False,  # GPG optional (Python.org may not provide signatures)
                require_sha256=True,  # SHA256 required
            )
            
            if not verification_result.success:
                error_msg = f"File verification failed: {verification_result.error}"
                logger.error(error_msg)
                echo(f"  ✗ Security verification failed: {verification_result.error}")
                if verification_result.recovery_suggestion:
                    echo(f"  Suggestion: {verification_result.recovery_suggestion}")
                return InstallationResult(
                    component="python-windows",
                    success=False,
                    installed=False,
                    error=error_msg,
                    recovery_suggestion=verification_result.recovery_suggestion or "Re-download the file or contact support if issue persists",
                )
            
            echo("  ✓ File verification successful")
            logger.info("Windows Python installer downloaded and verified successfully")
        else:
            # Security requirement: 100% verification rate - cannot proceed without security module
            error_msg = "Secure download module not available - cannot download without verification (security requirement)"
            logger.error(error_msg)
            echo(f"  ✗ Security error: {error_msg}")
            return InstallationResult(
                component="python-windows",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Install python-gnupg: pip install python-gnupg, then retry installation",
            )

        echo(f"  Installing Windows Python via Wine (this may take several minutes)...")

        # Execute installer via Wine
        logger.info("Installing Windows Python via Wine...")
        install_result = subprocess.run(
            [
                wine_path,
                installer_path,
                "/quiet",
                "InstallAllUsers=1",
                "PrependPath=1",
            ],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes timeout
        )

        # Clean up installer
        try:
            os.remove(installer_path)
        except OSError:
            pass

        if install_result.returncode != 0:
            error_msg = f"Windows Python installation failed: {install_result.stderr}"
            logger.error(error_msg)
            return InstallationResult(
                component="python-windows",
                success=False,
                installed=False,
                error=error_msg,
                recovery_suggestion="Check Wine logs and ensure Wine is properly configured",
            )

        # Verify installation
        echo("  Verifying Windows Python installation...")
        python_info = detect_python_windows(wine_path)
        if python_info.found:
            echo(f"  ✓ Windows Python installed successfully: {python_info.version}")
            logger.info(f"Windows Python successfully installed at {python_info.path}")
            return InstallationResult(
                component="python-windows",
                success=True,
                installed=True,
                path=python_info.path,
                version=python_info.version,
            )
        else:
            error_msg = "Windows Python installation completed but verification failed"
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
        from typer import echo

        echo("  Installing MetaTrader5 library via pip...")
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
            [wine_path, python_windows_path, "-c", "import MetaTrader5; print(MetaTrader5.__version__)"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if verify_result.returncode == 0:
            version = verify_result.stdout.strip()
            echo(f"  ✓ MetaTrader5 installed successfully: {version}")
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
            logger.info(f"rpyc already installed, version: {detection_result.rpyc.version}")
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
        from typer import echo

        echo("  Installing rpyc via pip...")
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
            [wine_path, python_windows_path, "-c", "import rpyc; print(rpyc.__version__)"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if verify_result.returncode == 0:
            version = verify_result.stdout.strip()
            echo(f"  ✓ rpyc installed successfully: {version}")
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


def install_missing_components(detection_result: DetectionResult) -> List[InstallationResult]:
    """
    Install all missing components based on detection results.

    Installs components in order: Wine → Windows Python → MT5 → rpyc

    Args:
        detection_result: DetectionResult from environment detection (not mutated)

    Returns:
        List of InstallationResult for each component
    """
    logger.info("Starting installation of missing components")
    results: List[InstallationResult] = []

    # Create a copy of detection result to avoid mutating the input
    # We'll track Wine and Python paths from installation results instead
    wine_path: Optional[str] = detection_result.wine.path if detection_result.wine.found else None
    python_windows_path: Optional[str] = (
        detection_result.python_windows.path if detection_result.python_windows.found else None
    )

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
            detection_result,
        )
        results.append(python_result)
        if not python_result.success:
            logger.error("Windows Python installation failed, stopping installation")
            return results
        # Track Python path from result
        if python_result.path:
            python_windows_path = python_result.path

    # Install MT5 library if missing
    if "mt5" in detection_result.missing_components:
        logger.info("Installing MetaTrader5 library...")
        mt5_result = install_mt5_library(
            wine_path,
            python_windows_path,
            detection_result,
        )
        results.append(mt5_result)
        if not mt5_result.success:
            logger.warning("MT5 library installation failed, continuing with other components")

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
