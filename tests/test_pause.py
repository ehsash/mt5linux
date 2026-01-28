"""Tests for mt5linux pause/resume mechanism."""

import os
import time
from unittest.mock import patch, MagicMock
import pytest

from mt5linux.detection import DetectionResult, ComponentInfo
from mt5linux.setup.pause import (
    pause_for_mt5_configuration,
    get_mt5_gui_instructions,
    verify_mt5_configuration,
    PauseResult,
    VerificationResult,
)


class TestGetMT5GUIInstructions:
    """Tests for MT5 GUI instruction generation."""

    @patch("os.path.isdir")
    @patch("os.path.dirname")
    def test_instructions_local_environment(self, mock_dirname: MagicMock, mock_isdir: MagicMock) -> None:
        """Test instruction generation for local environment."""
        mock_dirname.return_value = "/home/user/.wine/drive_c/Program Files/MetaTrader 5"
        mock_isdir.return_value = True
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
        )
        instructions = get_mt5_gui_instructions(detection_result)
        assert "Local Environment" in instructions
        assert "wine" in instructions.lower()
        assert "terminal64.exe" in instructions or "MT5" in instructions
        # Check for Wine prefix information (Task 2 requirement)
        assert ".wine" in instructions or "Wine prefix" in instructions

    def test_instructions_local_wayland(self) -> None:
        """Test instruction generation for local Wayland environment."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="wayland",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
        )
        instructions = get_mt5_gui_instructions(detection_result)
        assert "Local Environment" in instructions
        # Wayland environment mentions XWayland
        assert "xwayland" in instructions.lower()

    @patch("socket.getfqdn")
    @patch("socket.gethostname")
    @patch("socket.socket")
    def test_instructions_remote_environment(self, mock_socket_class: MagicMock, mock_hostname: MagicMock, mock_fqdn: MagicMock) -> None:
        """Test instruction generation for remote environment."""
        mock_hostname.return_value = "server1"
        mock_fqdn.return_value = "server1.example.com"
        # Mock socket connection for IP address
        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("192.168.1.100", 12345)
        mock_sock.connect.return_value = None
        mock_sock.close.return_value = None
        mock_socket_class.return_value = mock_sock
        
        detection_result = DetectionResult(
            environment_type="remote",
            display_system="none",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
            thinlinc=ComponentInfo(found=True, path="/opt/thinlinc"),
        )
        instructions = get_mt5_gui_instructions(detection_result)
        assert "Remote Environment" in instructions
        assert "ThinLinc" in instructions
        assert "terminal64.exe" in instructions or "MT5" in instructions
        # Check for connection details (AC #3 requirement)
        assert "server1" in instructions or "192.168.1.100" in instructions

    def test_instructions_remote_with_x11_server(self) -> None:
        """Test instruction generation for remote environment with X11 server."""
        detection_result = DetectionResult(
            environment_type="remote",
            display_system="none",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
            thinlinc=ComponentInfo(found=True, path="/opt/thinlinc"),
            x11_server=ComponentInfo(found=True, path="/usr/bin/Xvfb"),
        )
        instructions = get_mt5_gui_instructions(detection_result)
        assert "Remote Environment" in instructions
        assert "X11 server" in instructions or "Xvfb" in instructions


class TestVerifyMT5Configuration:
    """Tests for MT5 configuration verification."""

    @patch("os.path.exists")
    def test_verify_mt5_success(self, mock_exists: MagicMock) -> None:
        """Test MT5 verification when successful."""
        mock_exists.return_value = True
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
        )
        result = verify_mt5_configuration(detection_result)
        assert result.success is True
        assert result.mt5_accessible is True

    def test_verify_mt5_not_found(self) -> None:
        """Test MT5 verification when MT5 not found."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=False),
            rpyc=ComponentInfo(found=True),
        )
        result = verify_mt5_configuration(detection_result)
        assert result.success is False
        assert result.mt5_accessible is False
        assert result.error == "MT5 not found"

    def test_verify_mt5_no_path(self) -> None:
        """Test MT5 verification when MT5 path not available."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path=None),
            rpyc=ComponentInfo(found=True),
        )
        result = verify_mt5_configuration(detection_result)
        assert result.success is False
        assert result.mt5_accessible is False
        assert result.error == "MT5 path not available"

    @patch("os.path.exists")
    def test_verify_mt5_path_not_exists(self, mock_exists: MagicMock) -> None:
        """Test MT5 verification when path doesn't exist."""
        mock_exists.return_value = False
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/nonexistent/path/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
        )
        result = verify_mt5_configuration(detection_result)
        assert result.success is False
        assert result.mt5_accessible is False
        assert "not found" in result.error.lower()

    def test_verify_mt5_no_wine(self) -> None:
        """Test MT5 verification when Wine not found."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=False),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
        )
        result = verify_mt5_configuration(detection_result)
        assert result.success is False
        assert result.mt5_accessible is False
        assert result.error == "Wine not found"


class TestPauseForMT5Configuration:
    """Tests for pause/resume mechanism."""

    @patch("mt5linux.setup.pause.prompt")
    def test_pause_success(self, mock_prompt: MagicMock) -> None:
        """Test pause when user presses Enter."""
        mock_prompt.return_value = ""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
        )
        result = pause_for_mt5_configuration(detection_result)
        assert result.success is True
        assert result.resumed is True
        assert result.duration_seconds is not None
        assert result.duration_seconds >= 0

    @patch("mt5linux.setup.pause.prompt")
    def test_pause_keyboard_interrupt(self, mock_prompt: MagicMock) -> None:
        """Test pause when user presses Ctrl+C."""
        mock_prompt.side_effect = KeyboardInterrupt()
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
        )
        result = pause_for_mt5_configuration(detection_result)
        assert result.success is False
        assert result.resumed is False
        assert result.error == "User cancelled pause"

    @patch("mt5linux.setup.pause.prompt")
    def test_pause_eof_error(self, mock_prompt: MagicMock) -> None:
        """Test pause when input stream is closed (non-interactive)."""
        mock_prompt.side_effect = EOFError()
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
        )
        result = pause_for_mt5_configuration(detection_result)
        assert result.success is False
        assert result.resumed is False
        assert "Input stream closed" in result.error

    @patch("mt5linux.setup.pause.prompt")
    def test_pause_unexpected_error(self, mock_prompt: MagicMock) -> None:
        """Test pause when unexpected error occurs."""
        mock_prompt.side_effect = Exception("Unexpected error")
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
        )
        result = pause_for_mt5_configuration(detection_result)
        assert result.success is False
        assert result.resumed is False
        assert result.error is not None

    @patch("mt5linux.setup.pause.echo")
    @patch("mt5linux.setup.pause.prompt")
    def test_pause_exact_ac_message_format(self, mock_prompt: MagicMock, mock_echo: MagicMock) -> None:
        """Test that pause displays exact AC #1 message format."""
        mock_prompt.return_value = ""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(found=True, path="/home/user/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"),
            rpyc=ComponentInfo(found=True),
        )
        pause_for_mt5_configuration(detection_result)
        # Check that exact AC message is displayed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        echo_output = " ".join([str(call[0][0]) for call in mock_echo.call_args_list if call[0]])
        assert "Please configure MT5 (credentials, autotrading, DLLs, webrequests)" in echo_output
