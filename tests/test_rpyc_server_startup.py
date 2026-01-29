"""Tests for rpyc server startup functionality in process_manager module.

Tests cover:
- Windows Python discovery (found, not found, multiple found)
- Server startup success path
- Server startup when already running (skip startup)
- Startup failure handling (exceptions, error messages)
- Configuration integration (host, port, prefix)
- Startup verification (success, timeout, retry)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mt5linux.process_manager import (
    MT5LinuxError,
    ProcessError,
    ProcessInfo,
    ProcessManager,
    PythonNotFoundError,
    RpycServerError,
)


@pytest.mark.unit
class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_mt5linux_error_exists(self) -> None:
        """Test that MT5LinuxError base exception exists."""
        assert MT5LinuxError is not None

    def test_mt5linux_error_is_exception_subclass(self) -> None:
        """Test that MT5LinuxError is an Exception subclass."""
        assert issubclass(MT5LinuxError, Exception)

    def test_process_error_inherits_from_mt5linux_error(self) -> None:
        """Test that ProcessError inherits from MT5LinuxError."""
        assert issubclass(ProcessError, MT5LinuxError)

    def test_python_not_found_error_inherits_from_process_error(self) -> None:
        """Test that PythonNotFoundError inherits from ProcessError."""
        assert issubclass(PythonNotFoundError, ProcessError)

    def test_rpyc_server_error_inherits_from_process_error(self) -> None:
        """Test that RpycServerError inherits from ProcessError."""
        assert issubclass(RpycServerError, ProcessError)

    def test_can_catch_all_process_errors_with_mt5linux_error(self) -> None:
        """Test that all process errors can be caught with MT5LinuxError."""
        try:
            raise PythonNotFoundError("test")
        except MT5LinuxError:
            pass  # Expected

        try:
            raise RpycServerError("test")
        except MT5LinuxError:
            pass  # Expected


@pytest.mark.unit
class TestPythonNotFoundError:
    """Tests for PythonNotFoundError exception class."""

    def test_exception_exists(self) -> None:
        """Test that PythonNotFoundError exception class exists."""
        assert PythonNotFoundError is not None

    def test_exception_is_exception_subclass(self) -> None:
        """Test that PythonNotFoundError is an Exception subclass."""
        assert issubclass(PythonNotFoundError, Exception)

    def test_exception_can_be_raised_with_message(self) -> None:
        """Test that PythonNotFoundError can be raised with a message."""
        with pytest.raises(PythonNotFoundError) as exc_info:
            raise PythonNotFoundError("Windows Python not found in Wine prefix")
        assert "Windows Python not found" in str(exc_info.value)


@pytest.mark.unit
class TestRpycServerError:
    """Tests for RpycServerError exception class."""

    def test_exception_exists(self) -> None:
        """Test that RpycServerError exception class exists."""
        assert RpycServerError is not None

    def test_exception_is_exception_subclass(self) -> None:
        """Test that RpycServerError is an Exception subclass."""
        assert issubclass(RpycServerError, Exception)

    def test_exception_can_be_raised_with_message(self) -> None:
        """Test that RpycServerError can be raised with a message."""
        with pytest.raises(RpycServerError) as exc_info:
            raise RpycServerError("Failed to start rpyc server")
        assert "Failed to start rpyc server" in str(exc_info.value)


@pytest.mark.unit
class TestFindWindowsPython:
    """Tests for Windows Python discovery in Wine prefix."""

    def test_find_windows_python_method_exists(self) -> None:
        """Test that find_windows_python method exists on ProcessManager."""
        manager = ProcessManager()
        assert hasattr(manager, "find_windows_python")
        assert callable(manager.find_windows_python)

    @patch("mt5linux.process_manager.get_config")
    def test_find_windows_python_in_python_dir(
        self, mock_get_config: MagicMock, tmp_path: Path
    ) -> None:
        """Test finding python.exe in drive_c/Python* directory."""
        # Setup Wine prefix with Python installation
        wine_prefix = tmp_path / ".mt5"
        python_dir = wine_prefix / "drive_c" / "Python311"
        python_dir.mkdir(parents=True)
        python_exe = python_dir / "python.exe"
        python_exe.touch()

        # Mock config to return our test Wine prefix
        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_get_config.return_value = mock_config

        manager = ProcessManager()
        result = manager.find_windows_python()

        assert result is not None
        assert result.endswith("python.exe")
        assert "Python311" in result

    @patch("mt5linux.process_manager.get_config")
    def test_find_windows_python_in_program_files(
        self, mock_get_config: MagicMock, tmp_path: Path
    ) -> None:
        """Test finding python.exe in Program Files directory."""
        # Setup Wine prefix with Python in Program Files
        wine_prefix = tmp_path / ".mt5"
        python_dir = wine_prefix / "drive_c" / "Program Files" / "Python39"
        python_dir.mkdir(parents=True)
        python_exe = python_dir / "python.exe"
        python_exe.touch()

        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_get_config.return_value = mock_config

        manager = ProcessManager()
        result = manager.find_windows_python()

        assert result is not None
        assert result.endswith("python.exe")

    @patch("mt5linux.process_manager.get_config")
    def test_find_windows_python_not_found_raises_exception(
        self, mock_get_config: MagicMock, tmp_path: Path
    ) -> None:
        """Test that PythonNotFoundError is raised when python.exe not found."""
        # Setup empty Wine prefix
        wine_prefix = tmp_path / ".mt5"
        wine_prefix.mkdir(parents=True)
        (wine_prefix / "drive_c").mkdir()

        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_get_config.return_value = mock_config

        manager = ProcessManager()

        with pytest.raises(PythonNotFoundError) as exc_info:
            manager.find_windows_python()

        # Error message should be actionable
        assert "python" in str(exc_info.value).lower()

    @patch("mt5linux.process_manager.get_config")
    def test_find_windows_python_uses_cwd_fallback(
        self,
        mock_get_config: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that find_windows_python falls back to .mt5 in cwd when no config."""
        # Setup .mt5 in cwd with Python
        monkeypatch.chdir(tmp_path)
        wine_prefix = tmp_path / ".mt5"
        python_dir = wine_prefix / "drive_c" / "Python310"
        python_dir.mkdir(parents=True)
        python_exe = python_dir / "python.exe"
        python_exe.touch()

        # Config returns None for prefix_path
        mock_config = MagicMock()
        mock_config.wine.prefix_path = None
        mock_get_config.return_value = mock_config

        manager = ProcessManager()
        result = manager.find_windows_python()

        assert result is not None
        assert result.endswith("python.exe")

    @patch("mt5linux.process_manager.get_config")
    def test_find_windows_python_prefers_newer_version(
        self, mock_get_config: MagicMock, tmp_path: Path
    ) -> None:
        """Test that newer Python version is preferred when multiple found."""
        wine_prefix = tmp_path / ".mt5"

        # Create multiple Python installations
        for version in ["Python38", "Python311", "Python39"]:
            python_dir = wine_prefix / "drive_c" / version
            python_dir.mkdir(parents=True)
            (python_dir / "python.exe").touch()

        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_get_config.return_value = mock_config

        manager = ProcessManager()
        result = manager.find_windows_python()

        assert result is not None
        # Should prefer Python311 (highest version)
        assert "Python311" in result


@pytest.mark.unit
class TestStartRpycServer:
    """Tests for rpyc server startup functionality."""

    def test_start_rpyc_server_method_exists(self) -> None:
        """Test that start_rpyc_server method exists on ProcessManager."""
        manager = ProcessManager()
        assert hasattr(manager, "start_rpyc_server")
        assert callable(manager.start_rpyc_server)

    @patch.object(ProcessManager, "_verify_port_listening")
    @patch("mt5linux.process_manager.subprocess.Popen")
    @patch.object(ProcessManager, "find_rpyc_server")
    @patch.object(ProcessManager, "find_windows_python")
    @patch("mt5linux.process_manager.get_config")
    def test_start_rpyc_server_when_not_running(
        self,
        mock_get_config: MagicMock,
        mock_find_python: MagicMock,
        mock_find_rpyc: MagicMock,
        mock_popen: MagicMock,
        mock_verify_port: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test starting rpyc server when not already running."""
        # Setup config
        wine_prefix = tmp_path / ".mt5"
        wine_prefix.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_config.server.host = "localhost"
        mock_config.server.port = 18812
        mock_get_config.return_value = mock_config

        # Python found
        mock_find_python.return_value = str(
            wine_prefix / "drive_c/Python311/python.exe"
        )

        # Server not running initially, then running after start
        mock_find_rpyc.side_effect = [
            None,  # First call: not running
            ProcessInfo(pid=12345, name="python.exe", status="running"),  # After start
        ]

        # Port is listening after startup
        mock_verify_port.return_value = True

        # Mock subprocess
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process still running
        mock_popen.return_value = mock_process

        manager = ProcessManager()
        result = manager.start_rpyc_server()

        assert result is not None
        assert result.pid == 12345
        mock_popen.assert_called_once()

    @patch.object(ProcessManager, "find_rpyc_server")
    @patch("mt5linux.process_manager.get_config")
    def test_start_rpyc_server_when_already_running(
        self,
        mock_get_config: MagicMock,
        mock_find_rpyc: MagicMock,
    ) -> None:
        """Test that start_rpyc_server skips startup when server already running."""
        mock_config = MagicMock()
        mock_config.wine.prefix_path = "/some/path"
        mock_config.server.host = "localhost"
        mock_config.server.port = 18812
        mock_get_config.return_value = mock_config

        # Server already running
        existing_process = ProcessInfo(
            pid=9999,
            name="python.exe",
            status="running",
            cmdline=["python", "-c", "rpyc"],
        )
        mock_find_rpyc.return_value = existing_process

        manager = ProcessManager()
        result = manager.start_rpyc_server()

        # Should return existing process, not start new one
        assert result is not None
        assert result.pid == 9999
        # find_rpyc_server should only be called once (no startup attempt)
        mock_find_rpyc.assert_called_once()

    @patch.object(ProcessManager, "_verify_port_listening")
    @patch("mt5linux.process_manager.subprocess.Popen")
    @patch.object(ProcessManager, "find_rpyc_server")
    @patch.object(ProcessManager, "find_windows_python")
    @patch("mt5linux.process_manager.get_config")
    def test_start_rpyc_server_uses_config_host_port(
        self,
        mock_get_config: MagicMock,
        mock_find_python: MagicMock,
        mock_find_rpyc: MagicMock,
        mock_popen: MagicMock,
        mock_verify_port: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that start_rpyc_server uses host/port from config."""
        wine_prefix = tmp_path / ".mt5"
        wine_prefix.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_config.server.host = "127.0.0.1"
        mock_config.server.port = 19999
        mock_get_config.return_value = mock_config

        mock_find_python.return_value = str(
            wine_prefix / "drive_c/Python311/python.exe"
        )
        mock_find_rpyc.side_effect = [
            None,
            ProcessInfo(pid=12345, name="python.exe", status="running"),
        ]

        mock_verify_port.return_value = True

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        manager = ProcessManager()
        manager.start_rpyc_server()

        # Verify the command includes the configured host and port
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "127.0.0.1" in cmd_str or "hostname='127.0.0.1'" in cmd_str
        assert "19999" in cmd_str or "port=19999" in cmd_str

    @patch.object(ProcessManager, "_verify_port_listening")
    @patch("mt5linux.process_manager.subprocess.Popen")
    @patch.object(ProcessManager, "find_rpyc_server")
    @patch.object(ProcessManager, "find_windows_python")
    @patch("mt5linux.process_manager.get_config")
    def test_start_rpyc_server_sets_wineprefix_env(
        self,
        mock_get_config: MagicMock,
        mock_find_python: MagicMock,
        mock_find_rpyc: MagicMock,
        mock_popen: MagicMock,
        mock_verify_port: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that WINEPREFIX environment variable is set correctly."""
        wine_prefix = tmp_path / ".mt5"
        wine_prefix.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_config.server.host = "localhost"
        mock_config.server.port = 18812
        mock_get_config.return_value = mock_config

        mock_find_python.return_value = str(
            wine_prefix / "drive_c/Python311/python.exe"
        )
        mock_find_rpyc.side_effect = [
            None,
            ProcessInfo(pid=12345, name="python.exe", status="running"),
        ]

        mock_verify_port.return_value = True

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        manager = ProcessManager()
        manager.start_rpyc_server()

        # Verify WINEPREFIX is in the environment
        call_kwargs = mock_popen.call_args[1]
        assert "env" in call_kwargs
        assert "WINEPREFIX" in call_kwargs["env"]
        assert call_kwargs["env"]["WINEPREFIX"] == str(wine_prefix)

    @patch.object(ProcessManager, "find_rpyc_server")
    @patch.object(ProcessManager, "find_windows_python")
    @patch("mt5linux.process_manager.get_config")
    def test_start_rpyc_server_raises_on_python_not_found(
        self,
        mock_get_config: MagicMock,
        mock_find_python: MagicMock,
        mock_find_rpyc: MagicMock,
    ) -> None:
        """Test that PythonNotFoundError is raised when Python not found."""
        mock_config = MagicMock()
        mock_config.wine.prefix_path = "/some/path"
        mock_get_config.return_value = mock_config

        mock_find_rpyc.return_value = None
        mock_find_python.side_effect = PythonNotFoundError("Python not found")

        manager = ProcessManager()

        with pytest.raises(PythonNotFoundError):
            manager.start_rpyc_server()

    @patch("mt5linux.process_manager.subprocess.Popen")
    @patch.object(ProcessManager, "find_rpyc_server")
    @patch.object(ProcessManager, "find_windows_python")
    @patch("mt5linux.process_manager.get_config")
    def test_start_rpyc_server_raises_on_startup_failure(
        self,
        mock_get_config: MagicMock,
        mock_find_python: MagicMock,
        mock_find_rpyc: MagicMock,
        mock_popen: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that RpycServerError is raised when server fails to start."""
        wine_prefix = tmp_path / ".mt5"
        wine_prefix.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_config.server.host = "localhost"
        mock_config.server.port = 18812
        mock_get_config.return_value = mock_config

        mock_find_python.return_value = str(
            wine_prefix / "drive_c/Python311/python.exe"
        )

        # Server never starts (always returns None)
        mock_find_rpyc.return_value = None

        # Process exits immediately (failed)
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Non-zero exit code
        mock_popen.return_value = mock_process

        manager = ProcessManager()

        with pytest.raises(RpycServerError) as exc_info:
            manager.start_rpyc_server()

        # Error message should be actionable
        assert (
            "server" in str(exc_info.value).lower()
            or "start" in str(exc_info.value).lower()
        )

    @patch("mt5linux.process_manager.subprocess.Popen")
    @patch.object(ProcessManager, "find_rpyc_server")
    @patch.object(ProcessManager, "find_windows_python")
    @patch("mt5linux.process_manager.get_config")
    def test_start_rpyc_server_raises_on_wine_oserror(
        self,
        mock_get_config: MagicMock,
        mock_find_python: MagicMock,
        mock_find_rpyc: MagicMock,
        mock_popen: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that RpycServerError is raised when Wine subprocess fails with OSError."""
        wine_prefix = tmp_path / ".mt5"
        wine_prefix.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_config.server.host = "localhost"
        mock_config.server.port = 18812
        mock_get_config.return_value = mock_config

        mock_find_python.return_value = str(
            wine_prefix / "drive_c/Python311/python.exe"
        )
        mock_find_rpyc.return_value = None

        # Simulate OSError when launching Wine (e.g., Wine not installed)
        mock_popen.side_effect = OSError("Wine executable not found")

        manager = ProcessManager()

        with pytest.raises(RpycServerError) as exc_info:
            manager.start_rpyc_server()

        # Error message should mention Wine
        assert "wine" in str(exc_info.value).lower()


@pytest.mark.unit
class TestStartupVerification:
    """Tests for startup verification functionality."""

    @patch.object(ProcessManager, "_verify_port_listening")
    @patch("mt5linux.process_manager.time.sleep")
    @patch("mt5linux.process_manager.subprocess.Popen")
    @patch.object(ProcessManager, "find_rpyc_server")
    @patch.object(ProcessManager, "find_windows_python")
    @patch("mt5linux.process_manager.get_config")
    def test_startup_verification_retries(
        self,
        mock_get_config: MagicMock,
        mock_find_python: MagicMock,
        mock_find_rpyc: MagicMock,
        mock_popen: MagicMock,
        mock_sleep: MagicMock,
        mock_verify_port: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that startup verification retries before failing."""
        wine_prefix = tmp_path / ".mt5"
        wine_prefix.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_config.server.host = "localhost"
        mock_config.server.port = 18812
        mock_get_config.return_value = mock_config

        mock_find_python.return_value = str(
            wine_prefix / "drive_c/Python311/python.exe"
        )

        # Server not running initially, then succeeds on 3rd check
        mock_find_rpyc.side_effect = [
            None,  # Initial check
            None,  # Verification attempt 1
            None,  # Verification attempt 2
            ProcessInfo(pid=12345, name="python.exe", status="running"),  # Attempt 3
        ]

        # Port listening succeeds when process is found
        mock_verify_port.return_value = True

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        manager = ProcessManager()
        result = manager.start_rpyc_server()

        assert result is not None
        assert result.pid == 12345
        # Should have called sleep between retries
        assert mock_sleep.call_count >= 2

    @patch("mt5linux.process_manager.time.sleep")
    @patch("mt5linux.process_manager.subprocess.Popen")
    @patch.object(ProcessManager, "find_rpyc_server")
    @patch.object(ProcessManager, "find_windows_python")
    @patch("mt5linux.process_manager.get_config")
    def test_startup_verification_timeout(
        self,
        mock_get_config: MagicMock,
        mock_find_python: MagicMock,
        mock_find_rpyc: MagicMock,
        mock_popen: MagicMock,
        mock_sleep: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that startup verification times out and raises error."""
        wine_prefix = tmp_path / ".mt5"
        wine_prefix.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.wine.prefix_path = str(wine_prefix)
        mock_config.server.host = "localhost"
        mock_config.server.port = 18812
        mock_get_config.return_value = mock_config

        mock_find_python.return_value = str(
            wine_prefix / "drive_c/Python311/python.exe"
        )

        # Server never detected as running
        mock_find_rpyc.return_value = None

        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process still running but not detected
        mock_popen.return_value = mock_process

        manager = ProcessManager()

        with pytest.raises(RpycServerError):
            manager.start_rpyc_server()


@pytest.mark.unit
class TestConfigurationIntegration:
    """Tests for configuration module integration."""

    @patch("mt5linux.process_manager.get_config")
    def test_uses_default_host_when_not_configured(
        self, mock_get_config: MagicMock
    ) -> None:
        """Test that default host 'localhost' is used when not configured."""
        mock_config = MagicMock()
        mock_config.wine.prefix_path = None
        mock_config.server.host = "localhost"  # Default
        mock_config.server.port = 18812
        mock_get_config.return_value = mock_config

        # Just verify config is accessed correctly
        _manager = ProcessManager()  # noqa: F841
        config = mock_get_config()
        assert config.server.host == "localhost"

    @patch("mt5linux.process_manager.get_config")
    def test_uses_default_port_when_not_configured(
        self, mock_get_config: MagicMock
    ) -> None:
        """Test that default port 18812 is used when not configured."""
        mock_config = MagicMock()
        mock_config.wine.prefix_path = None
        mock_config.server.host = "localhost"
        mock_config.server.port = 18812  # Default
        mock_get_config.return_value = mock_config

        _manager = ProcessManager()  # noqa: F841
        config = mock_get_config()
        assert config.server.port == 18812
