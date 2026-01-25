"""Tests for mt5linux environment detection module."""

import os
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from mt5linux.detection import (
    detect_environment_type,
    detect_display_system,
    detect_wine,
    detect_python_system,
    detect_python_windows,
    detect_mt5,
    detect_rpyc,
    detect_environment,
    ComponentInfo,
    DetectionResult,
)


class TestEnvironmentTypeDetection:
    """Tests for remote/local environment detection."""

    def test_detect_local_environment(self) -> None:
        """Test detection of local environment."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove SSH-related variables
            os.environ.pop("SSH_CONNECTION", None)
            os.environ.pop("SSH_CLIENT", None)
            os.environ.pop("DISPLAY", None)
            result = detect_environment_type()
            assert result == "local"

    def test_detect_remote_via_ssh_connection(self) -> None:
        """Test detection of remote environment via SSH_CONNECTION."""
        with patch.dict(os.environ, {"SSH_CONNECTION": "192.168.1.1 12345 192.168.1.2 22"}):
            result = detect_environment_type()
            assert result == "remote"

    def test_detect_remote_via_ssh_client(self) -> None:
        """Test detection of remote environment via SSH_CLIENT."""
        with patch.dict(os.environ, {"SSH_CLIENT": "192.168.1.1 12345 22"}):
            result = detect_environment_type()
            assert result == "remote"

    def test_detect_remote_via_x11_forwarding(self) -> None:
        """Test detection of remote environment via X11 forwarding."""
        with patch.dict(os.environ, {"DISPLAY": "localhost:10.0"}):
            result = detect_environment_type()
            assert result == "remote"

    def test_detect_local_with_local_display(self) -> None:
        """Test that local display (e.g., :0.0) is detected as local."""
        with patch.dict(os.environ, {"DISPLAY": ":0.0"}):
            result = detect_environment_type()
            assert result == "local"


class TestDisplaySystemDetection:
    """Tests for display system detection."""

    def test_detect_wayland(self) -> None:
        """Test detection of Wayland display system."""
        with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}):
            result = detect_display_system()
            assert result == "wayland"

    def test_detect_x11(self) -> None:
        """Test detection of X11 display system."""
        with patch.dict(os.environ, {"DISPLAY": ":0.0"}):
            # Remove Wayland to ensure X11 is detected
            os.environ.pop("WAYLAND_DISPLAY", None)
            result = detect_display_system()
            assert result == "x11"

    def test_detect_none(self) -> None:
        """Test detection when no display system is present."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISPLAY", None)
            os.environ.pop("WAYLAND_DISPLAY", None)
            result = detect_display_system()
            assert result == "none"

    def test_wayland_takes_precedence(self) -> None:
        """Test that Wayland takes precedence over X11 when both are present."""
        with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0.0"}):
            result = detect_display_system()
            assert result == "wayland"


class TestWineDetection:
    """Tests for Wine detection."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_wine_found(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        """Test detection when Wine is found."""
        mock_which.return_value = "/usr/bin/wine"
        mock_run.return_value = MagicMock(returncode=0, stdout="wine-11.0 (Staging)\n")

        result = detect_wine()

        assert result.found is True
        assert result.path == "/usr/bin/wine"
        mock_which.assert_called_once_with("wine")

    @patch("shutil.which")
    def test_detect_wine_not_found(self, mock_which: MagicMock) -> None:
        """Test detection when Wine is not found."""
        mock_which.return_value = None

        result = detect_wine()

        assert result.found is False
        assert result.path is None
        assert result.version is None

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_wine_version_failure(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        """Test detection when Wine is found but version check fails."""
        mock_which.return_value = "/usr/bin/wine"
        mock_run.side_effect = subprocess.TimeoutExpired("wine", 5)

        result = detect_wine()

        assert result.found is True
        assert result.path == "/usr/bin/wine"
        assert result.version is None


class TestPythonSystemDetection:
    """Tests for system Python detection."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_python3_found(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        """Test detection when Python 3 is found."""
        mock_which.side_effect = lambda cmd: "/usr/bin/python3" if cmd == "python3" else None
        mock_run.return_value = MagicMock(returncode=0, stdout="Python 3.10.16\n")

        result = detect_python_system()

        assert result.found is True
        assert result.path == "/usr/bin/python3"

    @patch("shutil.which")
    def test_detect_python_not_found(self, mock_which: MagicMock) -> None:
        """Test detection when Python is not found."""
        mock_which.return_value = None

        result = detect_python_system()

        assert result.found is False
        assert result.path is None


class TestPythonWindowsDetection:
    """Tests for Windows Python detection via Wine."""

    @patch("shutil.which")
    def test_detect_python_windows_no_wine(self, mock_which: MagicMock) -> None:
        """Test detection when Wine is not available."""
        mock_which.return_value = None

        result = detect_python_windows()

        assert result.found is False

    @patch("shutil.which")
    @patch("os.path.isdir")
    @patch("glob.glob")
    def test_detect_python_windows_found(
        self, mock_glob: MagicMock, mock_isdir: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test detection when Windows Python is found."""
        mock_which.return_value = "/usr/bin/wine"
        mock_isdir.return_value = True
        mock_glob.return_value = ["/home/user/.wine/drive_c/Python311/python.exe"]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Python 3.11.0\n")
            result = detect_python_windows()

        assert result.found is True
        assert result.path == "/home/user/.wine/drive_c/Python311/python.exe"


class TestMT5Detection:
    """Tests for MetaTrader5 detection."""

    @patch("shutil.which")
    def test_detect_mt5_no_wine(self, mock_which: MagicMock) -> None:
        """Test detection when Wine is not available."""
        mock_which.return_value = None

        result = detect_mt5()

        assert result.found is False

    @patch("shutil.which")
    @patch("os.path.isdir")
    @patch("os.path.isfile")
    def test_detect_mt5_found(
        self, mock_isfile: MagicMock, mock_isdir: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test detection when MT5 is found."""
        mock_which.return_value = "/usr/bin/wine"
        mock_isdir.return_value = True
        mock_isfile.return_value = True

        result = detect_mt5()

        assert result.found is True


class TestRpycDetection:
    """Tests for rpyc detection."""

    @patch("shutil.which")
    def test_detect_rpyc_no_wine(self, mock_which: MagicMock) -> None:
        """Test detection when Wine is not available."""
        mock_which.return_value = None

        result = detect_rpyc()

        assert result.found is False

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_rpyc_found(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        """Test detection when rpyc is found."""
        mock_which.return_value = "/usr/bin/wine"
        mock_run.return_value = MagicMock(returncode=0, stdout="5.2.3\n")

        result = detect_rpyc(wine_path="/usr/bin/wine", python_windows_path="/path/to/python.exe")

        assert result.found is True
        assert result.version == "5.2.3"


class TestDetectionResult:
    """Tests for DetectionResult data structure."""

    def test_detection_result_missing_components(self) -> None:
        """Test that missing components are correctly identified."""
        result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=False),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=False),
            mt5=ComponentInfo(found=False),
            rpyc=ComponentInfo(found=False),
        )

        assert "wine" in result.missing_components
        assert "python-windows" in result.missing_components
        assert "mt5" in result.missing_components
        assert "rpyc" in result.missing_components
        assert "python-system" not in result.missing_components

    def test_detection_result_installation_plan(self) -> None:
        """Test that installation plan is generated correctly."""
        result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=False),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=False),
            mt5=ComponentInfo(found=False),
            rpyc=ComponentInfo(found=False),
        )

        assert len(result.installation_plan) > 0
        assert any("Wine" in step for step in result.installation_plan)
        assert any("Windows Python" in step for step in result.installation_plan)
        assert any("MetaTrader5" in step for step in result.installation_plan)
        assert any("rpyc" in step for step in result.installation_plan)


class TestDetectEnvironment:
    """Tests for comprehensive environment detection."""

    @patch("mt5linux.detection.detect_environment_type")
    @patch("mt5linux.detection.detect_display_system")
    @patch("mt5linux.detection.detect_wine")
    @patch("mt5linux.detection.detect_python_system")
    @patch("mt5linux.detection.detect_python_windows")
    @patch("mt5linux.detection.detect_mt5")
    @patch("mt5linux.detection.detect_rpyc")
    def test_detect_environment_comprehensive(
        self,
        mock_rpyc: MagicMock,
        mock_mt5: MagicMock,
        mock_python_windows: MagicMock,
        mock_python_system: MagicMock,
        mock_wine: MagicMock,
        mock_display: MagicMock,
        mock_env_type: MagicMock,
    ) -> None:
        """Test comprehensive environment detection."""
        mock_env_type.return_value = "local"
        mock_display.return_value = "x11"
        mock_wine.return_value = ComponentInfo(found=True, path="/usr/bin/wine")
        mock_python_system.return_value = ComponentInfo(found=True, path="/usr/bin/python3")
        mock_python_windows.return_value = ComponentInfo(found=False)
        mock_mt5.return_value = ComponentInfo(found=False)
        mock_rpyc.return_value = ComponentInfo(found=False)

        result = detect_environment()

        assert isinstance(result, DetectionResult)
        assert result.environment_type == "local"
        assert result.display_system == "x11"
        assert result.wine.found is True
        assert result.python_system.found is True
        assert result.python_windows.found is False
        assert len(result.missing_components) > 0
