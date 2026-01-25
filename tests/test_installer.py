"""Tests for mt5linux installer module."""

from unittest.mock import MagicMock, patch
import pytest
import subprocess

from mt5linux.setup.installer import (
    InstallationResult,
    install_wine,
    install_windows_python,
    install_mt5_library,
    install_rpyc,
    install_missing_components,
    _check_sudo_access,
)
from mt5linux.detection import DetectionResult, ComponentInfo


class TestSudoAccess:
    """Tests for sudo access checking."""

    @patch("subprocess.run")
    def test_sudo_access_available(self, mock_run: MagicMock) -> None:
        """Test that sudo access is detected when available."""
        mock_run.return_value = MagicMock(returncode=0)
        result = _check_sudo_access()
        assert result is True

    @patch("subprocess.run")
    def test_sudo_access_unavailable(self, mock_run: MagicMock) -> None:
        """Test that sudo access is detected as unavailable."""
        mock_run.return_value = MagicMock(returncode=1)
        result = _check_sudo_access()
        assert result is False


class TestWineInstallation:
    """Tests for Wine installation."""

    @patch("mt5linux.setup.installer.detect_wine")
    def test_install_wine_already_installed(self, mock_detect: MagicMock) -> None:
        """Test that Wine installation is skipped if already installed."""
        mock_detect.return_value = ComponentInfo(found=True, path="/usr/bin/wine", version="wine-11.0")
        result = install_wine()
        assert result.success is True
        assert result.installed is False  # Skipped
        assert result.path == "/usr/bin/wine"

    @patch("mt5linux.setup.installer._check_sudo_access")
    @patch("mt5linux.setup.installer.detect_wine")
    @patch("subprocess.run")
    def test_install_wine_success(
        self, mock_run: MagicMock, mock_detect: MagicMock, mock_sudo: MagicMock
    ) -> None:
        """Test successful Wine installation."""
        mock_sudo.return_value = True
        # First call: Wine not found
        # Second call: Wine found after installation
        mock_detect.side_effect = [
            ComponentInfo(found=False),
            ComponentInfo(found=True, path="/usr/bin/wine", version="wine-11.0"),
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = install_wine()

        assert result.success is True
        assert result.installed is True
        assert result.path == "/usr/bin/wine"
        assert mock_run.call_count >= 2  # apt update and apt install

    @patch("mt5linux.setup.installer._check_sudo_access")
    @patch("mt5linux.setup.installer.detect_wine")
    def test_install_wine_no_sudo(self, mock_detect: MagicMock, mock_sudo: MagicMock) -> None:
        """Test Wine installation fails without sudo access."""
        mock_sudo.return_value = False
        mock_detect.return_value = ComponentInfo(found=False)

        result = install_wine()

        assert result.success is False
        assert result.installed is False
        assert "sudo" in result.error.lower() or "sudo" in result.recovery_suggestion.lower()

    @patch("mt5linux.setup.installer._check_sudo_access")
    @patch("mt5linux.setup.installer.detect_wine")
    @patch("subprocess.run")
    def test_install_wine_apt_failure(
        self, mock_run: MagicMock, mock_detect: MagicMock, mock_sudo: MagicMock
    ) -> None:
        """Test Wine installation handles apt failures."""
        mock_sudo.return_value = True
        mock_detect.return_value = ComponentInfo(found=False)
        mock_run.return_value = MagicMock(returncode=1, stderr="apt error")

        result = install_wine()

        assert result.success is False
        assert result.installed is False
        assert result.error is not None


class TestWindowsPythonInstallation:
    """Tests for Windows Python installation."""

    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    def test_install_windows_python_already_installed(
        self, mock_detect_wine: MagicMock, mock_detect_python: MagicMock
    ) -> None:
        """Test that Windows Python installation is skipped if already installed."""
        mock_detect_wine.return_value = ComponentInfo(found=True, path="/usr/bin/wine")
        mock_detect_python.return_value = ComponentInfo(
            found=True, path="/path/to/python.exe", version="Python 3.11.0"
        )

        result = install_windows_python()

        assert result.success is True
        assert result.installed is False  # Skipped
        assert result.path == "/path/to/python.exe"

    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    def test_install_windows_python_no_wine(
        self, mock_detect_wine: MagicMock, mock_detect_python: MagicMock
    ) -> None:
        """Test that Windows Python installation fails if Wine is not installed."""
        mock_detect_wine.return_value = ComponentInfo(found=False)

        result = install_windows_python()

        assert result.success is False
        assert "Wine" in result.error or "wine" in result.error.lower()

    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    @patch("urllib.request.urlretrieve")
    @patch("subprocess.run")
    @patch("os.remove")
    @patch("os.path.exists")
    def test_install_windows_python_success(
        self,
        mock_exists: MagicMock,
        mock_remove: MagicMock,
        mock_run: MagicMock,
        mock_urlretrieve: MagicMock,
        mock_detect_wine: MagicMock,
        mock_detect_python: MagicMock,
    ) -> None:
        """Test successful Windows Python installation."""
        mock_detect_wine.return_value = ComponentInfo(found=True, path="/usr/bin/wine")
        mock_detect_python.side_effect = [
            ComponentInfo(found=False),  # Before installation
            ComponentInfo(found=True, path="/path/to/python.exe", version="Python 3.11.0"),  # After
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_urlretrieve.return_value = None
        mock_exists.return_value = True

        result = install_windows_python()

        assert result.success is True
        assert result.installed is True
        assert result.path == "/path/to/python.exe"

    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    @patch("urllib.request.urlretrieve")
    @patch("os.path.exists")
    def test_install_windows_python_download_failure(
        self,
        mock_exists: MagicMock,
        mock_urlretrieve: MagicMock,
        mock_detect_wine: MagicMock,
        mock_detect_python: MagicMock,
    ) -> None:
        """Test Windows Python installation handles download failures."""
        mock_detect_wine.return_value = ComponentInfo(found=True, path="/usr/bin/wine")
        mock_detect_python.return_value = ComponentInfo(found=False)
        import urllib.error

        mock_urlretrieve.side_effect = urllib.error.URLError("Network error")
        mock_exists.return_value = False

        result = install_windows_python()

        assert result.success is False
        assert result.installed is False
        assert "download" in result.error.lower() or "network" in result.error.lower()

    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    @patch("urllib.request.urlretrieve")
    @patch("os.path.exists")
    def test_install_windows_python_disk_error(
        self,
        mock_exists: MagicMock,
        mock_urlretrieve: MagicMock,
        mock_detect_wine: MagicMock,
        mock_detect_python: MagicMock,
    ) -> None:
        """Test Windows Python installation handles disk errors."""
        mock_detect_wine.return_value = ComponentInfo(found=True, path="/usr/bin/wine")
        mock_detect_python.return_value = ComponentInfo(found=False)
        mock_urlretrieve.side_effect = OSError("No space left on device")
        mock_exists.return_value = False

        result = install_windows_python()

        assert result.success is False
        assert result.installed is False
        assert "save" in result.error.lower() or "disk" in result.error.lower()

    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    @patch("urllib.request.urlretrieve")
    @patch("subprocess.run")
    @patch("os.remove")
    @patch("os.path.exists")
    def test_install_windows_python_cleanup_failure(
        self,
        mock_exists: MagicMock,
        mock_remove: MagicMock,
        mock_run: MagicMock,
        mock_urlretrieve: MagicMock,
        mock_detect_wine: MagicMock,
        mock_detect_python: MagicMock,
    ) -> None:
        """Test Windows Python installation handles cleanup failures gracefully."""
        mock_detect_wine.return_value = ComponentInfo(found=True, path="/usr/bin/wine")
        mock_detect_python.side_effect = [
            ComponentInfo(found=False),  # Before installation
            ComponentInfo(found=True, path="/path/to/python.exe", version="Python 3.11.0"),  # After
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_urlretrieve.return_value = None
        mock_exists.return_value = True
        mock_remove.side_effect = OSError("Permission denied")

        result = install_windows_python()

        # Installation should still succeed even if cleanup fails
        assert result.success is True
        assert result.installed is True
        assert result.path == "/path/to/python.exe"


class TestMT5LibraryInstallation:
    """Tests for MetaTrader5 library installation."""

    @patch("mt5linux.setup.installer.detect_mt5")
    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    def test_install_mt5_already_installed(
        self, mock_detect_wine: MagicMock, mock_detect_python: MagicMock, mock_detect_mt5: MagicMock
    ) -> None:
        """Test that MT5 installation is skipped if already installed."""
        # Create DetectionResult with MT5 already installed
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True, path="/path/to/python.exe"),
            mt5=ComponentInfo(found=True, path="/path/to/mt5"),
            rpyc=ComponentInfo(found=False),
        )

        result = install_mt5_library(detection_result=detection_result)

        assert result.success is True
        assert result.installed is False  # Skipped

    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    def test_install_mt5_no_wine(self, mock_detect_wine: MagicMock, mock_detect_python: MagicMock) -> None:
        """Test that MT5 installation fails if Wine is not installed."""
        mock_detect_wine.return_value = ComponentInfo(found=False)

        result = install_mt5_library()

        assert result.success is False
        assert "Wine" in result.error or "wine" in result.error.lower()

    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    @patch("subprocess.run")
    def test_install_mt5_success(
        self, mock_run: MagicMock, mock_detect_wine: MagicMock, mock_detect_python: MagicMock
    ) -> None:
        """Test successful MT5 library installation."""
        mock_detect_wine.return_value = ComponentInfo(found=True, path="/usr/bin/wine")
        mock_detect_python.return_value = ComponentInfo(found=True, path="/path/to/python.exe")
        # First call: pip install, Second call: verification
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="5.0.45", stderr=""),
        ]

        result = install_mt5_library()

        assert result.success is True
        assert result.installed is True
        assert result.version == "5.0.45"


class TestRpycInstallation:
    """Tests for rpyc installation."""

    @patch("mt5linux.setup.installer.detect_rpyc")
    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    def test_install_rpyc_already_installed(
        self, mock_detect_wine: MagicMock, mock_detect_python: MagicMock, mock_detect_rpyc: MagicMock
    ) -> None:
        """Test that rpyc installation is skipped if already installed."""
        # Create DetectionResult with rpyc already installed
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True, path="/path/to/python.exe"),
            mt5=ComponentInfo(found=False),
            rpyc=ComponentInfo(found=True, version="5.2.3"),
        )

        result = install_rpyc(detection_result=detection_result)

        assert result.success is True
        assert result.installed is False  # Skipped

    @patch("mt5linux.setup.installer.detect_python_windows")
    @patch("mt5linux.setup.installer.detect_wine")
    @patch("subprocess.run")
    def test_install_rpyc_success(
        self, mock_run: MagicMock, mock_detect_wine: MagicMock, mock_detect_python: MagicMock
    ) -> None:
        """Test successful rpyc installation."""
        mock_detect_wine.return_value = ComponentInfo(found=True, path="/usr/bin/wine")
        mock_detect_python.return_value = ComponentInfo(found=True, path="/path/to/python.exe")
        # First call: pip install, Second call: verification
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="5.2.3", stderr=""),
        ]

        result = install_rpyc()

        assert result.success is True
        assert result.installed is True
        assert result.version == "5.2.3"


class TestInstallationOrchestration:
    """Tests for installation orchestration."""

    def test_install_missing_components_all_installed(self) -> None:
        """Test orchestration when all components are already installed."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )

        results = install_missing_components(detection_result)

        assert len(results) == 0  # Nothing to install

    @patch("mt5linux.setup.installer.install_wine")
    @patch("mt5linux.setup.installer.install_windows_python")
    @patch("mt5linux.setup.installer.install_mt5_library")
    @patch("mt5linux.setup.installer.install_rpyc")
    def test_install_missing_components_ordered(
        self,
        mock_rpyc: MagicMock,
        mock_mt5: MagicMock,
        mock_python: MagicMock,
        mock_wine: MagicMock,
    ) -> None:
        """Test that components are installed in correct order."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=False),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=False),
            mt5=ComponentInfo(found=False),
            rpyc=ComponentInfo(found=False),
        )

        mock_wine.return_value = InstallationResult("wine", True, True)
        mock_python.return_value = InstallationResult("python-windows", True, True)
        mock_mt5.return_value = InstallationResult("mt5", True, True)
        mock_rpyc.return_value = InstallationResult("rpyc", True, True)

        results = install_missing_components(detection_result)

        # Verify order: wine, python, mt5, rpyc
        assert mock_wine.called
        assert mock_python.called
        assert mock_mt5.called
        assert mock_rpyc.called
        assert len(results) == 4

    @patch("mt5linux.setup.installer.install_wine")
    def test_install_missing_components_stops_on_failure(self, mock_wine: MagicMock) -> None:
        """Test that installation stops if Wine installation fails."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=False),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=False),
            mt5=ComponentInfo(found=False),
            rpyc=ComponentInfo(found=False),
        )

        mock_wine.return_value = InstallationResult("wine", False, False, error="Installation failed")

        results = install_missing_components(detection_result)

        assert len(results) == 1
        assert results[0].component == "wine"
        assert results[0].success is False
