"""Tests for mt5linux Wayland configuration module."""

import os
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from mt5linux.detection import DetectionResult, ComponentInfo
from mt5linux.setup.wayland_config import (
    configure_xyphir,
    verify_xyphir,
    fallback_to_x11,
    configure_wayland_support,
    WaylandConfigResult,
)


class TestConfigureXyphir:
    """Tests for xyphir configuration."""

    def test_configure_xyphir_already_found(self) -> None:
        """Test xyphir configuration when already detected."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            xyphir=ComponentInfo(found=True, path="/usr/bin/xyphir", version="1.0.0"),
        )
        result = configure_xyphir(detection_result)
        assert result.success is True
        assert result.xyphir_configured is True
        assert result.xyphir_path == "/usr/bin/xyphir"
        assert result.fallback_to_x11 is False

    @patch("mt5linux.setup.wayland_config.detect_xyphir")
    def test_configure_xyphir_detected_on_retry(self, mock_detect: MagicMock) -> None:
        """Test xyphir configuration when detected on retry."""
        mock_detect.return_value = ComponentInfo(found=True, path="/usr/bin/xyphir", version="1.0.0")
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            xyphir=ComponentInfo(found=False),
        )
        result = configure_xyphir(detection_result)
        assert result.success is True
        assert result.xyphir_configured is True
        assert result.xyphir_path == "/usr/bin/xyphir"

    @patch("mt5linux.setup.wayland_config.detect_xyphir")
    @patch("mt5linux.setup.wayland_config._attempt_install_xyphir")
    def test_configure_xyphir_installation_success(self, mock_install: MagicMock, mock_detect: MagicMock) -> None:
        """Test xyphir configuration when installation succeeds."""
        # First call: not found
        # Second call: found after installation
        mock_detect.side_effect = [
            ComponentInfo(found=False),
            ComponentInfo(found=True, path="/usr/bin/xyphir", version="1.0.0"),
        ]
        mock_install.return_value = True
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            xyphir=ComponentInfo(found=False),
        )
        result = configure_xyphir(detection_result)
        assert result.success is True
        assert result.xyphir_configured is True
        assert result.xyphir_path == "/usr/bin/xyphir"
        mock_install.assert_called_once()

    @patch("mt5linux.setup.wayland_config.detect_xyphir")
    @patch("mt5linux.setup.wayland_config._attempt_install_xyphir")
    def test_configure_xyphir_installation_fails(self, mock_install: MagicMock, mock_detect: MagicMock) -> None:
        """Test xyphir configuration when installation fails."""
        mock_detect.return_value = ComponentInfo(found=False)
        mock_install.return_value = False
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            xyphir=ComponentInfo(found=False),
        )
        result = configure_xyphir(detection_result)
        assert result.success is False
        assert result.xyphir_configured is False
        assert result.fallback_to_x11 is True
        mock_install.assert_called_once()

    @patch("mt5linux.setup.wayland_config.detect_xyphir")
    def test_configure_xyphir_not_found(self, mock_detect: MagicMock) -> None:
        """Test xyphir configuration when not found."""
        mock_detect.return_value = ComponentInfo(found=False)
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            xyphir=ComponentInfo(found=False),
        )
        result = configure_xyphir(detection_result)
        assert result.success is False
        assert result.xyphir_configured is False
        assert result.fallback_to_x11 is True
        assert result.error == "xyphir not found"


class TestVerifyXyphir:
    """Tests for xyphir verification."""

    @patch("subprocess.run")
    @patch("os.access")
    @patch("os.path.exists")
    def test_verify_xyphir_success(self, mock_exists: MagicMock, mock_access: MagicMock, mock_run: MagicMock) -> None:
        """Test xyphir verification when successful."""
        mock_exists.return_value = True
        mock_access.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout="xyphir 1.0.0")
        result = verify_xyphir("/usr/bin/xyphir")
        assert result is True

    @patch("subprocess.run")
    @patch("os.access")
    @patch("os.path.exists")
    def test_verify_xyphir_alternative_version_flag(
        self, mock_exists: MagicMock, mock_access: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test xyphir verification with alternative version flag."""
        mock_exists.return_value = True
        mock_access.return_value = True
        # First call fails, second succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=""),
            MagicMock(returncode=0, stdout="xyphir 1.0.0"),
        ]
        result = verify_xyphir("/usr/bin/xyphir")
        assert result is True

    @patch("os.path.exists")
    def test_verify_xyphir_path_not_exists(self, mock_exists: MagicMock) -> None:
        """Test xyphir verification when path doesn't exist."""
        mock_exists.return_value = False
        result = verify_xyphir("/usr/bin/xyphir")
        assert result is False

    @patch("os.access")
    @patch("os.path.exists")
    def test_verify_xyphir_not_executable(self, mock_exists: MagicMock, mock_access: MagicMock) -> None:
        """Test xyphir verification when not executable."""
        mock_exists.return_value = True
        mock_access.return_value = False
        result = verify_xyphir("/usr/bin/xyphir")
        assert result is False


class TestFallbackToX11:
    """Tests for X11 fallback."""

    @patch("mt5linux.setup.wayland_config.detect_x11_server")
    def test_fallback_to_x11_success(self, mock_detect: MagicMock) -> None:
        """Test X11 fallback when X11 server is available."""
        mock_detect.return_value = ComponentInfo(found=True, path="/usr/bin/Xvfb", version="1.20.13")
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )
        result = fallback_to_x11(detection_result)
        assert result.success is True
        assert result.fallback_to_x11 is True
        assert result.x11_server_path == "/usr/bin/Xvfb"

    @patch("shutil.which")
    @patch("mt5linux.setup.wayland_config.detect_x11_server")
    def test_fallback_to_x11_with_xdotool(self, mock_detect: MagicMock, mock_which: MagicMock) -> None:
        """Test X11 fallback when xdotool is available."""
        mock_detect.return_value = ComponentInfo(found=False)
        mock_which.return_value = "/usr/bin/xdotool"
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )
        result = fallback_to_x11(detection_result)
        assert result.success is True
        assert result.fallback_to_x11 is True
        assert result.x11_server_path == "/usr/bin/xdotool"

    @patch("shutil.which")
    @patch("mt5linux.setup.wayland_config.detect_x11_server")
    def test_fallback_to_x11_not_available(self, mock_detect: MagicMock, mock_which: MagicMock) -> None:
        """Test X11 fallback when neither X11 server nor xdotool is available."""
        mock_detect.return_value = ComponentInfo(found=False)
        mock_which.return_value = None
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )
        result = fallback_to_x11(detection_result)
        assert result.success is False
        assert result.fallback_to_x11 is False
        assert result.error == "X11 fallback not available"


class TestConfigureWaylandSupport:
    """Tests for Wayland support configuration."""

    def test_configure_wayland_support_not_local(self) -> None:
        """Test Wayland configuration when not in local environment."""
        detection_result = DetectionResult(
            environment_type="remote",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )
        result = configure_wayland_support(detection_result)
        assert result.success is False
        assert result.error == "Not a local environment"

    def test_configure_wayland_support_not_wayland(self) -> None:
        """Test Wayland configuration when not in Wayland display system."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )
        result = configure_wayland_support(detection_result)
        assert result.success is False
        assert result.error == "Not a Wayland display system"

    @patch("mt5linux.setup.wayland_config.verify_xyphir")
    @patch("mt5linux.setup.wayland_config.configure_xyphir")
    def test_configure_wayland_support_success(
        self, mock_configure: MagicMock, mock_verify: MagicMock
    ) -> None:
        """Test Wayland configuration when xyphir is successfully configured."""
        mock_configure.return_value = WaylandConfigResult(
            success=True,
            xyphir_configured=True,
            fallback_to_x11=False,
            xyphir_path="/usr/bin/xyphir",
        )
        mock_verify.return_value = True
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )
        result = configure_wayland_support(detection_result)
        assert result.success is True
        assert result.xyphir_configured is True

    @patch("mt5linux.setup.wayland_config.fallback_to_x11")
    @patch("mt5linux.setup.wayland_config.verify_xyphir")
    @patch("mt5linux.setup.wayland_config.configure_xyphir")
    def test_configure_wayland_support_fallback_to_x11(
        self, mock_configure: MagicMock, mock_verify: MagicMock, mock_fallback: MagicMock
    ) -> None:
        """Test Wayland configuration when falling back to X11."""
        mock_configure.return_value = WaylandConfigResult(
            success=False,
            xyphir_configured=False,
            fallback_to_x11=True,
            error="xyphir not found",
        )
        mock_verify.return_value = False
        mock_fallback.return_value = WaylandConfigResult(
            success=True,
            xyphir_configured=False,
            fallback_to_x11=True,
            x11_server_path="/usr/bin/Xvfb",
        )
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )
        result = configure_wayland_support(detection_result)
        assert result.success is True
        assert result.fallback_to_x11 is True

    @patch("mt5linux.setup.wayland_config.fallback_to_x11")
    @patch("mt5linux.setup.wayland_config.configure_xyphir")
    def test_configure_wayland_support_both_fail(
        self, mock_configure: MagicMock, mock_fallback: MagicMock
    ) -> None:
        """Test Wayland configuration when both xyphir and X11 fallback fail."""
        mock_configure.return_value = WaylandConfigResult(
            success=False,
            xyphir_configured=False,
            fallback_to_x11=True,
            error="xyphir not found",
        )
        mock_fallback.return_value = WaylandConfigResult(
            success=False,
            xyphir_configured=False,
            fallback_to_x11=False,
            error="X11 fallback not available",
        )
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )
        result = configure_wayland_support(detection_result)
        assert result.success is False
        assert result.error == "Both xyphir and X11 fallback failed"
