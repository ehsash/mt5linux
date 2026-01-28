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
    detect_thinlinc,
    detect_x11_server,
    detect_window_manager,
    detect_ydotool,
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

    @patch("mt5linux.detection.detect_environment_type")
    @patch("mt5linux.detection.detect_display_system")
    @patch("mt5linux.detection.detect_wine")
    @patch("mt5linux.detection.detect_python_system")
    @patch("mt5linux.detection.detect_python_windows")
    @patch("mt5linux.detection.detect_mt5")
    @patch("mt5linux.detection.detect_rpyc")
    @patch("mt5linux.detection.detect_thinlinc")
    @patch("mt5linux.detection.detect_x11_server")
    @patch("mt5linux.detection.detect_window_manager")
    def test_detect_environment_remote_with_components(
        self,
        mock_wm: MagicMock,
        mock_x11: MagicMock,
        mock_thinlinc: MagicMock,
        mock_rpyc: MagicMock,
        mock_mt5: MagicMock,
        mock_python_windows: MagicMock,
        mock_python_system: MagicMock,
        mock_wine: MagicMock,
        mock_display: MagicMock,
        mock_env_type: MagicMock,
    ) -> None:
        """Test comprehensive environment detection in remote mode with remote components."""
        mock_env_type.return_value = "remote"
        mock_display.return_value = "none"
        mock_wine.return_value = ComponentInfo(found=True, path="/usr/bin/wine")
        mock_python_system.return_value = ComponentInfo(found=True, path="/usr/bin/python3")
        mock_python_windows.return_value = ComponentInfo(found=True)
        mock_mt5.return_value = ComponentInfo(found=True)
        mock_rpyc.return_value = ComponentInfo(found=True)
        mock_thinlinc.return_value = ComponentInfo(found=False)
        mock_x11.return_value = ComponentInfo(found=False)
        mock_wm.return_value = ComponentInfo(found=False)

        result = detect_environment()

        assert isinstance(result, DetectionResult)
        assert result.environment_type == "remote"
        # Verify remote detection functions were called
        assert mock_thinlinc.called
        assert mock_x11.called
        assert mock_wm.called
        assert result.thinlinc.found is False
        assert result.x11_server.found is False
        assert result.window_manager.found is False
        assert "thinlinc" in result.missing_components
        assert "x11-server" in result.missing_components
        assert "window-manager" in result.missing_components

    @patch("mt5linux.detection.detect_environment_type")
    @patch("mt5linux.detection.detect_display_system")
    @patch("mt5linux.detection.detect_wine")
    @patch("mt5linux.detection.detect_python_system")
    @patch("mt5linux.detection.detect_python_windows")
    @patch("mt5linux.detection.detect_mt5")
    @patch("mt5linux.detection.detect_rpyc")
    @patch("mt5linux.detection.detect_thinlinc")
    @patch("mt5linux.detection.detect_x11_server")
    @patch("mt5linux.detection.detect_window_manager")
    def test_detect_environment_local_skips_remote_components(
        self,
        mock_wm: MagicMock,
        mock_x11: MagicMock,
        mock_thinlinc: MagicMock,
        mock_rpyc: MagicMock,
        mock_mt5: MagicMock,
        mock_python_windows: MagicMock,
        mock_python_system: MagicMock,
        mock_wine: MagicMock,
        mock_display: MagicMock,
        mock_env_type: MagicMock,
    ) -> None:
        """Test that remote components are not detected in local environment."""
        mock_env_type.return_value = "local"
        mock_display.return_value = "x11"
        mock_wine.return_value = ComponentInfo(found=True, path="/usr/bin/wine")
        mock_python_system.return_value = ComponentInfo(found=True, path="/usr/bin/python3")
        mock_python_windows.return_value = ComponentInfo(found=True)
        mock_mt5.return_value = ComponentInfo(found=True)
        mock_rpyc.return_value = ComponentInfo(found=True)

        result = detect_environment()

        assert isinstance(result, DetectionResult)
        assert result.environment_type == "local"
        # Verify remote detection functions were NOT called in local mode
        assert not mock_thinlinc.called
        assert not mock_x11.called
        assert not mock_wm.called
        assert "thinlinc" not in result.missing_components
        assert "x11-server" not in result.missing_components
        assert "window-manager" not in result.missing_components


class TestThinLincDetection:
    """Tests for ThinLinc detection."""

    @patch("shutil.which")
    def test_detect_thinlinc_found_server(self, mock_which: MagicMock) -> None:
        """Test ThinLinc detection when thinlinc-server is found."""
        mock_which.side_effect = lambda x: "/usr/bin/thinlinc-server" if x == "thinlinc-server" else None
        result = detect_thinlinc()
        assert result.found is True
        assert result.path == "/usr/bin/thinlinc-server"

    @patch("shutil.which")
    def test_detect_thinlinc_found_client(self, mock_which: MagicMock) -> None:
        """Test ThinLinc detection when tlclient is found."""
        mock_which.side_effect = lambda x: "/usr/bin/tlclient" if x == "tlclient" else None
        result = detect_thinlinc()
        assert result.found is True
        assert result.path == "/usr/bin/tlclient"

    @patch("os.path.isdir")
    @patch("shutil.which")
    def test_detect_thinlinc_found_directory(self, mock_which: MagicMock, mock_isdir: MagicMock) -> None:
        """Test ThinLinc detection when installation directory is found."""
        mock_which.return_value = None
        mock_isdir.side_effect = lambda x: x == "/opt/thinlinc"
        result = detect_thinlinc()
        assert result.found is True
        assert result.path == "/opt/thinlinc"

    @patch("shutil.which")
    def test_detect_thinlinc_not_found(self, mock_which: MagicMock) -> None:
        """Test ThinLinc detection when not found."""
        mock_which.return_value = None
        with patch("os.path.isdir", return_value=False):
            result = detect_thinlinc()
            assert result.found is False


class TestX11ServerDetection:
    """Tests for X11 server detection."""

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_detect_x11_server_found_xvfb(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test X11 server detection when Xvfb is found."""
        mock_which.side_effect = lambda x: "/usr/bin/Xvfb" if x == "Xvfb" else None
        mock_run.return_value = MagicMock(returncode=0, stdout="Xvfb X.Org X Server 1.20.13")
        result = detect_x11_server()
        assert result.found is True
        assert result.path == "/usr/bin/Xvfb"
        assert "1.20.13" in result.version or result.version is not None

    @patch("shutil.which")
    def test_detect_x11_server_found_x_server(self, mock_which: MagicMock) -> None:
        """Test X11 server detection when X server is found."""
        mock_which.side_effect = lambda x: "/usr/bin/X" if x == "X" else None
        result = detect_x11_server()
        assert result.found is True
        assert result.path == "/usr/bin/X"

    @patch("shutil.which")
    def test_detect_x11_server_not_found(self, mock_which: MagicMock) -> None:
        """Test X11 server detection when not found."""
        mock_which.return_value = None
        result = detect_x11_server()
        assert result.found is False


class TestWindowManagerDetection:
    """Tests for window manager detection."""

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_detect_window_manager_found_openbox(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test window manager detection when openbox is found."""
        mock_which.side_effect = lambda x: "/usr/bin/openbox" if x == "openbox" else None
        mock_run.return_value = MagicMock(returncode=0, stdout="Openbox 3.6.1")
        result = detect_window_manager()
        assert result.found is True
        assert result.path == "/usr/bin/openbox"

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_detect_window_manager_found_fluxbox(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test window manager detection when fluxbox is found (openbox not available)."""
        mock_which.side_effect = lambda x: "/usr/bin/fluxbox" if x == "fluxbox" else None
        mock_run.return_value = MagicMock(returncode=0, stdout="Fluxbox 1.3.7")
        result = detect_window_manager()
        assert result.found is True
        assert result.path == "/usr/bin/fluxbox"

    @patch("shutil.which")
    def test_detect_window_manager_not_found(self, mock_which: MagicMock) -> None:
        """Test window manager detection when not found."""
        mock_which.return_value = None
        result = detect_window_manager()
        assert result.found is False


class TestRemoteComponentsInDetectionResult:
    """Tests for remote components in DetectionResult."""

    def test_remote_components_in_remote_environment(self) -> None:
        """Test that remote components are detected and added to missing_components in remote environment."""
        result = DetectionResult(
            environment_type="remote",
            display_system="none",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            thinlinc=ComponentInfo(found=False),
            x11_server=ComponentInfo(found=False),
            window_manager=ComponentInfo(found=False),
        )

        assert "thinlinc" in result.missing_components
        assert "x11-server" in result.missing_components
        assert "window-manager" in result.missing_components

    def test_remote_components_not_checked_in_local_environment(self) -> None:
        """Test that remote components are not checked in local environment."""
        result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )

        assert "thinlinc" not in result.missing_components
        assert "x11-server" not in result.missing_components
        assert "window-manager" not in result.missing_components


class TestYdotoolDetection:
    """Tests for ydotool detection."""

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("os.access")
    def test_detect_ydotool_found(self, mock_access: MagicMock, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test ydotool detection when found."""
        mock_which.return_value = "/usr/bin/ydotool"
        mock_access.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout="ydotool 1.0.0")
        result = detect_ydotool()
        assert result.found is True
        assert result.path == "/usr/bin/ydotool"
        assert result.version == "ydotool 1.0.0"

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("os.access")
    def test_detect_ydotool_found_alternative_version_flag(
        self, mock_access: MagicMock, mock_which: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test ydotool detection when found with alternative version flag."""
        mock_which.return_value = "/usr/bin/ydotool"
        mock_access.return_value = True
        # First call fails, second succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=""),
            MagicMock(returncode=0, stdout="ydotool 1.0.0"),
        ]
        result = detect_ydotool()
        assert result.found is True
        assert result.path == "/usr/bin/ydotool"
        assert result.version == "ydotool 1.0.0"

    @patch("shutil.which")
    def test_detect_ydotool_not_found(self, mock_which: MagicMock) -> None:
        """Test ydotool detection when not found."""
        mock_which.return_value = None
        result = detect_ydotool()
        assert result.found is False

    @patch("shutil.which")
    @patch("os.access")
    def test_detect_ydotool_not_executable(self, mock_access: MagicMock, mock_which: MagicMock) -> None:
        """Test ydotool detection when found but not executable."""
        mock_which.return_value = "/usr/bin/ydotool"
        mock_access.return_value = False
        result = detect_ydotool()
        assert result.found is False


class TestYdotoolInDetectionResult:
    """Tests for ydotool in DetectionResult."""

    @patch("mt5linux.detection.detect_ydotool")
    @patch("mt5linux.detection.detect_window_manager")
    @patch("mt5linux.detection.detect_x11_server")
    @patch("mt5linux.detection.detect_thinlinc")
    @patch("mt5linux.detection.detect_rpyc")
    @patch("mt5linux.detection.detect_mt5")
    @patch("mt5linux.detection.detect_python_windows")
    @patch("mt5linux.detection.detect_python_system")
    @patch("mt5linux.detection.detect_wine")
    def test_ydotool_detected_in_local_wayland_environment(
        self,
        mock_wine: MagicMock,
        mock_python_system: MagicMock,
        mock_python_windows: MagicMock,
        mock_mt5: MagicMock,
        mock_rpyc: MagicMock,
        mock_thinlinc: MagicMock,
        mock_x11_server: MagicMock,
        mock_window_manager: MagicMock,
        mock_ydotool: MagicMock,
    ) -> None:
        """Test that ydotool is detected in local Wayland environment."""
        mock_wine.return_value = ComponentInfo(found=True)
        mock_python_system.return_value = ComponentInfo(found=True)
        mock_python_windows.return_value = ComponentInfo(found=True)
        mock_mt5.return_value = ComponentInfo(found=True)
        mock_rpyc.return_value = ComponentInfo(found=True)
        mock_ydotool.return_value = ComponentInfo(found=True, path="/usr/bin/ydotool", version="1.0.0")
        with patch("mt5linux.detection.detect_environment_type", return_value="local"):
            with patch("mt5linux.detection.detect_display_system", return_value="wayland"):
                result = detect_environment()
                assert result.ydotool.found is True
                assert result.ydotool.path == "/usr/bin/ydotool"
                mock_ydotool.assert_called_once()

    @patch("mt5linux.detection.detect_ydotool")
    @patch("mt5linux.detection.detect_window_manager")
    @patch("mt5linux.detection.detect_x11_server")
    @patch("mt5linux.detection.detect_thinlinc")
    @patch("mt5linux.detection.detect_rpyc")
    @patch("mt5linux.detection.detect_mt5")
    @patch("mt5linux.detection.detect_python_windows")
    @patch("mt5linux.detection.detect_python_system")
    @patch("mt5linux.detection.detect_wine")
    def test_ydotool_not_detected_in_local_x11_environment(
        self,
        mock_wine: MagicMock,
        mock_python_system: MagicMock,
        mock_python_windows: MagicMock,
        mock_mt5: MagicMock,
        mock_rpyc: MagicMock,
        mock_thinlinc: MagicMock,
        mock_x11_server: MagicMock,
        mock_window_manager: MagicMock,
        mock_ydotool: MagicMock,
    ) -> None:
        """Test that ydotool is not detected in local X11 environment."""
        mock_wine.return_value = ComponentInfo(found=True)
        mock_python_system.return_value = ComponentInfo(found=True)
        mock_python_windows.return_value = ComponentInfo(found=True)
        mock_mt5.return_value = ComponentInfo(found=True)
        mock_rpyc.return_value = ComponentInfo(found=True)
        with patch("mt5linux.detection.detect_environment_type", return_value="local"):
            with patch("mt5linux.detection.detect_display_system", return_value="x11"):
                result = detect_environment()
                # ydotool detection should not be called for X11
                mock_ydotool.assert_not_called()
                assert result.ydotool.found is False

    @patch("mt5linux.detection.detect_ydotool")
    @patch("mt5linux.detection.detect_window_manager")
    @patch("mt5linux.detection.detect_x11_server")
    @patch("mt5linux.detection.detect_thinlinc")
    @patch("mt5linux.detection.detect_rpyc")
    @patch("mt5linux.detection.detect_mt5")
    @patch("mt5linux.detection.detect_python_windows")
    @patch("mt5linux.detection.detect_python_system")
    @patch("mt5linux.detection.detect_wine")
    def test_ydotool_not_detected_in_remote_environment(
        self,
        mock_wine: MagicMock,
        mock_python_system: MagicMock,
        mock_python_windows: MagicMock,
        mock_mt5: MagicMock,
        mock_rpyc: MagicMock,
        mock_thinlinc: MagicMock,
        mock_x11_server: MagicMock,
        mock_window_manager: MagicMock,
        mock_ydotool: MagicMock,
    ) -> None:
        """Test that ydotool is not detected in remote environment."""
        mock_wine.return_value = ComponentInfo(found=True)
        mock_python_system.return_value = ComponentInfo(found=True)
        mock_python_windows.return_value = ComponentInfo(found=True)
        mock_mt5.return_value = ComponentInfo(found=True)
        mock_rpyc.return_value = ComponentInfo(found=True)
        mock_thinlinc.return_value = ComponentInfo(found=True)
        mock_x11_server.return_value = ComponentInfo(found=True)
        mock_window_manager.return_value = ComponentInfo(found=True)
        with patch("mt5linux.detection.detect_environment_type", return_value="remote"):
            with patch("mt5linux.detection.detect_display_system", return_value="wayland"):
                result = detect_environment()
                # ydotool detection should not be called for remote
                mock_ydotool.assert_not_called()
                assert result.ydotool.found is False
