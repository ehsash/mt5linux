"""Tests for mt5linux GUI automation module."""

import subprocess
from unittest.mock import patch, MagicMock
import pytest

from mt5linux.detection import DetectionResult, ComponentInfo
from mt5linux.gui.automation import (
    get_gui_automation_tool,
    click,
    type_text,
    press_key,
    window_focus,
)


class TestGetGUIAutomationTool:
    """Tests for GUI automation tool selection."""

    def test_get_tool_wayland_with_xyphir(self) -> None:
        """Test tool selection for Wayland with xyphir."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            xyphir=ComponentInfo(found=True, path="/usr/bin/xyphir"),
        )
        tool, path = get_gui_automation_tool(detection_result)
        assert tool == "xyphir"
        assert path == "/usr/bin/xyphir"

    @patch("shutil.which")
    def test_get_tool_wayland_without_xyphir_fallback_to_xdotool(self, mock_which: MagicMock) -> None:
        """Test tool selection for Wayland without xyphir, falling back to xdotool."""
        mock_which.return_value = "/usr/bin/xdotool"
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
        tool, path = get_gui_automation_tool(detection_result)
        assert tool == "xdotool"
        assert path == "/usr/bin/xdotool"

    @patch("shutil.which")
    def test_get_tool_wayland_no_tools(self, mock_which: MagicMock) -> None:
        """Test tool selection for Wayland when neither xyphir nor xdotool is available."""
        mock_which.return_value = None
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
        tool, path = get_gui_automation_tool(detection_result)
        assert tool == "none"
        assert path is None

    @patch("shutil.which")
    def test_get_tool_x11_with_xdotool(self, mock_which: MagicMock) -> None:
        """Test tool selection for X11 with xdotool."""
        mock_which.return_value = "/usr/bin/xdotool"
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )
        tool, path = get_gui_automation_tool(detection_result)
        assert tool == "xdotool"
        assert path == "/usr/bin/xdotool"

    @patch("shutil.which")
    def test_get_tool_x11_no_xdotool(self, mock_which: MagicMock) -> None:
        """Test tool selection for X11 when xdotool is not available."""
        mock_which.return_value = None
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
        )
        tool, path = get_gui_automation_tool(detection_result)
        assert tool == "none"
        assert path is None


class TestClick:
    """Tests for click function."""

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_click_with_xyphir(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test click with xyphir."""
        mock_which.return_value = "/usr/bin/xyphir"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = click(100, 200, tool="xyphir")
        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_click_with_xdotool(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test click with xdotool."""
        mock_which.return_value = "/usr/bin/xdotool"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = click(100, 200, tool="xdotool")
        assert result is True
        mock_run.assert_called_once()

    @patch("shutil.which")
    def test_click_tool_not_found(self, mock_which: MagicMock) -> None:
        """Test click when tool is not found."""
        mock_which.return_value = None
        result = click(100, 200, tool="xyphir")
        assert result is False

    def test_click_with_detection_result(self) -> None:
        """Test click with detection result for auto-detection."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True),
            rpyc=ComponentInfo(found=True),
            xyphir=ComponentInfo(found=True, path="/usr/bin/xyphir"),
        )
        with patch("mt5linux.gui.automation.shutil.which", return_value="/usr/bin/xyphir"):
            with patch("mt5linux.gui.automation.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                result = click(100, 200, detection_result=detection_result)
                assert result is True


class TestTypeText:
    """Tests for type_text function."""

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_type_text_with_xyphir(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test type_text with xyphir."""
        mock_which.return_value = "/usr/bin/xyphir"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = type_text("Hello World", tool="xyphir")
        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_type_text_with_xdotool(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test type_text with xdotool."""
        mock_which.return_value = "/usr/bin/xdotool"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = type_text("Hello World", tool="xdotool")
        assert result is True
        mock_run.assert_called_once()


class TestPressKey:
    """Tests for press_key function."""

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_press_key_with_xyphir(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test press_key with xyphir."""
        mock_which.return_value = "/usr/bin/xyphir"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = press_key("Return", tool="xyphir")
        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_press_key_with_xdotool(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test press_key with xdotool."""
        mock_which.return_value = "/usr/bin/xdotool"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = press_key("Return", tool="xdotool")
        assert result is True
        mock_run.assert_called_once()


class TestWindowFocus:
    """Tests for window_focus function."""

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_window_focus_with_xyphir(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test window_focus with xyphir."""
        mock_which.return_value = "/usr/bin/xyphir"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = window_focus("MT5", tool="xyphir")
        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_window_focus_with_xdotool(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test window_focus with xdotool."""
        mock_which.return_value = "/usr/bin/xdotool"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = window_focus("MT5", tool="xdotool")
        assert result is True
        mock_run.assert_called_once()
