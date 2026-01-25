"""Tests for mt5linux remote installer module."""

from unittest.mock import MagicMock, patch
import pytest
import subprocess

from mt5linux.setup.remote_installer import (
    install_thinlinc,
    install_x11_server,
    install_window_manager,
    install_remote_components,
    _verify_remote_gui_access,
)
from mt5linux.setup.installer import InstallationResult
from mt5linux.detection import DetectionResult, ComponentInfo


class TestThinLincInstallation:
    """Tests for ThinLinc installation."""

    @patch("mt5linux.setup.remote_installer.detect_thinlinc")
    def test_install_thinlinc_already_installed(self, mock_detect: MagicMock) -> None:
        """Test that ThinLinc installation is skipped if already installed."""
        mock_detect.return_value = ComponentInfo(found=True, path="/opt/thinlinc")
        result = install_thinlinc()
        assert result.success is True
        assert result.installed is False  # Skipped
        assert result.path == "/opt/thinlinc"

    @patch("mt5linux.setup.remote_installer.detect_thinlinc")
    def test_install_thinlinc_not_installed(self, mock_detect: MagicMock) -> None:
        """Test that ThinLinc installation provides manual instructions when not installed."""
        mock_detect.return_value = ComponentInfo(found=False)
        result = install_thinlinc()
        assert result.success is False
        assert result.installed is False
        assert "manual" in result.error.lower() or "manual" in result.recovery_suggestion.lower()


class TestX11ServerInstallation:
    """Tests for X11 server installation."""

    @patch("mt5linux.setup.remote_installer.detect_x11_server")
    def test_install_x11_server_already_installed(self, mock_detect: MagicMock) -> None:
        """Test that X11 server installation is skipped if already installed."""
        mock_detect.return_value = ComponentInfo(found=True, path="/usr/bin/Xvfb", version="Xvfb 1.20.13")
        result = install_x11_server()
        assert result.success is True
        assert result.installed is False  # Skipped
        assert result.path == "/usr/bin/Xvfb"

    @patch("mt5linux.setup.remote_installer._check_sudo_access")
    @patch("mt5linux.setup.remote_installer.detect_x11_server")
    @patch("subprocess.run")
    def test_install_x11_server_success(
        self, mock_run: MagicMock, mock_detect: MagicMock, mock_sudo: MagicMock
    ) -> None:
        """Test successful X11 server installation."""
        mock_sudo.return_value = True
        # First call: X11 server not found
        # Second call: X11 server found after installation
        mock_detect.side_effect = [
            ComponentInfo(found=False),
            ComponentInfo(found=True, path="/usr/bin/Xvfb", version="Xvfb 1.20.13"),
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = install_x11_server()

        assert result.success is True
        assert result.installed is True
        assert result.path == "/usr/bin/Xvfb"
        assert mock_run.call_count >= 2  # apt update and apt install

    @patch("mt5linux.setup.remote_installer._check_sudo_access")
    @patch("mt5linux.setup.remote_installer.detect_x11_server")
    def test_install_x11_server_no_sudo(self, mock_detect: MagicMock, mock_sudo: MagicMock) -> None:
        """Test X11 server installation fails without sudo access."""
        mock_sudo.return_value = False
        mock_detect.return_value = ComponentInfo(found=False)

        result = install_x11_server()

        assert result.success is False
        assert result.installed is False
        assert "sudo" in result.error.lower() or "sudo" in result.recovery_suggestion.lower()

    @patch("mt5linux.setup.remote_installer._check_sudo_access")
    @patch("mt5linux.setup.remote_installer.detect_x11_server")
    @patch("subprocess.run")
    def test_install_x11_server_apt_failure(
        self, mock_run: MagicMock, mock_detect: MagicMock, mock_sudo: MagicMock
    ) -> None:
        """Test X11 server installation handles apt failures."""
        mock_sudo.return_value = True
        mock_detect.return_value = ComponentInfo(found=False)
        mock_run.return_value = MagicMock(returncode=1, stderr="apt error")

        result = install_x11_server()

        assert result.success is False
        assert result.installed is False
        assert result.error is not None


class TestWindowManagerInstallation:
    """Tests for window manager installation."""

    @patch("mt5linux.setup.remote_installer.detect_window_manager")
    def test_install_window_manager_already_installed(self, mock_detect: MagicMock) -> None:
        """Test that window manager installation is skipped if already installed."""
        mock_detect.return_value = ComponentInfo(found=True, path="/usr/bin/openbox", version="Openbox 3.6.1")
        result = install_window_manager()
        assert result.success is True
        assert result.installed is False  # Skipped
        assert result.path == "/usr/bin/openbox"

    @patch("mt5linux.setup.remote_installer._check_sudo_access")
    @patch("mt5linux.setup.remote_installer.detect_window_manager")
    @patch("subprocess.run")
    def test_install_window_manager_success(
        self, mock_run: MagicMock, mock_detect: MagicMock, mock_sudo: MagicMock
    ) -> None:
        """Test successful window manager installation."""
        mock_sudo.return_value = True
        # First call: Window manager not found
        # Second call: Window manager found after installation
        mock_detect.side_effect = [
            ComponentInfo(found=False),
            ComponentInfo(found=True, path="/usr/bin/openbox", version="Openbox 3.6.1"),
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = install_window_manager()

        assert result.success is True
        assert result.installed is True
        assert result.path == "/usr/bin/openbox"
        assert mock_run.call_count >= 2  # apt update and apt install

    @patch("mt5linux.setup.remote_installer._check_sudo_access")
    @patch("mt5linux.setup.remote_installer.detect_window_manager")
    def test_install_window_manager_no_sudo(self, mock_detect: MagicMock, mock_sudo: MagicMock) -> None:
        """Test window manager installation fails without sudo access."""
        mock_sudo.return_value = False
        mock_detect.return_value = ComponentInfo(found=False)

        result = install_window_manager()

        assert result.success is False
        assert result.installed is False
        assert "sudo" in result.error.lower() or "sudo" in result.recovery_suggestion.lower()


class TestRemoteInstallationOrchestration:
    """Tests for remote installation orchestration."""

    def test_install_remote_components_local_environment(self) -> None:
        """Test orchestration skips installation in local environment."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )

        results = install_remote_components(detection_result)

        assert len(results) == 0  # Nothing to install in local environment

    def test_install_remote_components_all_installed(self) -> None:
        """Test orchestration when all remote components are already installed."""
        detection_result = DetectionResult(
            environment_type="remote",
            display_system="none",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            thinlinc=ComponentInfo(found=True),
            x11_server=ComponentInfo(found=True),
            window_manager=ComponentInfo(found=True),
        )

        results = install_remote_components(detection_result)

        assert len(results) == 0  # Nothing to install

    @patch("mt5linux.setup.remote_installer.install_x11_server")
    @patch("mt5linux.setup.remote_installer.install_window_manager")
    @patch("mt5linux.setup.remote_installer.install_thinlinc")
    def test_install_remote_components_ordered(
        self,
        mock_thinlinc: MagicMock,
        mock_wm: MagicMock,
        mock_x11: MagicMock,
    ) -> None:
        """Test that remote components are installed in correct order."""
        detection_result = DetectionResult(
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

        mock_x11.return_value = InstallationResult("x11-server", True, True)
        mock_wm.return_value = InstallationResult("window-manager", True, True)
        mock_thinlinc.return_value = InstallationResult("thinlinc", True, True)

        results = install_remote_components(detection_result)

        # Verify order: x11, window manager, thinlinc
        assert mock_x11.called
        assert mock_wm.called
        assert mock_thinlinc.called
        assert len(results) == 3

    @patch("mt5linux.setup.remote_installer.install_x11_server")
    def test_install_remote_components_continues_on_failure(self, mock_x11: MagicMock) -> None:
        """Test that orchestration continues even if one component fails."""
        detection_result = DetectionResult(
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

        mock_x11.return_value = InstallationResult("x11-server", False, False, error="Installation failed")

        results = install_remote_components(detection_result)

        # Should continue and try other components
        assert len(results) >= 1
        assert results[0].component == "x11-server"
        assert results[0].success is False


class TestRemoteInstallerIntegration:
    """Integration tests for remote installer."""

    @patch("mt5linux.setup.remote_installer.install_x11_server")
    @patch("mt5linux.setup.remote_installer.install_window_manager")
    @patch("mt5linux.setup.remote_installer.install_thinlinc")
    def test_remote_installer_only_runs_in_remote_mode(
        self,
        mock_thinlinc: MagicMock,
        mock_wm: MagicMock,
        mock_x11: MagicMock,
    ) -> None:
        """Test that remote installer only runs in remote mode."""
        # Local environment
        local_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )

        results = install_remote_components(local_result)

        assert len(results) == 0
        assert not mock_x11.called
        assert not mock_wm.called
        assert not mock_thinlinc.called


class TestRemoteGUIAccessVerification:
    """Tests for remote GUI access verification."""

    @patch("subprocess.run")
    def test_verify_remote_gui_access_x11_available(self, mock_run: MagicMock) -> None:
        """Test GUI access verification when X11 server is available."""
        detection_result = DetectionResult(
            environment_type="remote",
            display_system="none",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            x11_server=ComponentInfo(found=True, path="/usr/bin/Xvfb"),
        )
        installation_results = [
            InstallationResult("x11-server", True, True, path="/usr/bin/Xvfb"),
        ]

        mock_run.return_value = MagicMock(returncode=1)  # Help typically exits with 1

        _verify_remote_gui_access(detection_result, installation_results)

        # Verify Xvfb was tested
        assert mock_run.called
        assert "/usr/bin/Xvfb" in str(mock_run.call_args)

    @patch("subprocess.run")
    def test_verify_remote_gui_access_x11_not_available(self, mock_run: MagicMock) -> None:
        """Test GUI access verification when X11 server is not available."""
        detection_result = DetectionResult(
            environment_type="remote",
            display_system="none",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            x11_server=ComponentInfo(found=False),
        )
        installation_results = [
            InstallationResult("x11-server", False, False),
        ]

        _verify_remote_gui_access(detection_result, installation_results)

        # Verify Xvfb was not tested (not available)
        assert not mock_run.called

    @patch("mt5linux.setup.remote_installer._verify_remote_gui_access")
    @patch("mt5linux.setup.remote_installer.install_x11_server")
    @patch("mt5linux.setup.remote_installer.install_window_manager")
    @patch("mt5linux.setup.remote_installer.install_thinlinc")
    def test_install_remote_components_verifies_gui_access(
        self,
        mock_thinlinc: MagicMock,
        mock_wm: MagicMock,
        mock_x11: MagicMock,
        mock_verify: MagicMock,
    ) -> None:
        """Test that remote installer verifies GUI access after installation."""
        detection_result = DetectionResult(
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

        mock_x11.return_value = InstallationResult("x11-server", True, True, path="/usr/bin/Xvfb")
        mock_wm.return_value = InstallationResult("window-manager", True, True)
        mock_thinlinc.return_value = InstallationResult("thinlinc", True, True)

        results = install_remote_components(detection_result)

        # Verify GUI access verification was called
        assert mock_verify.called
        assert len(results) == 3
