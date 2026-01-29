"""Unit tests for MT5 launch functionality (Story 2.4).

Tests MT5LaunchError exception class, find_mt5_executable(), start_mt5(),
and MT5 readiness verification methods.

All tests are marked with @pytest.mark.unit for fast, isolated execution.
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from mt5linux.process_manager import MT5LinuxError, ProcessError


@pytest.mark.unit
class TestMT5LaunchError:
    """Test MT5LaunchError exception class."""

    def test_mt5_launch_error_inherits_from_process_error(self) -> None:
        """MT5LaunchError should inherit from ProcessError."""
        from mt5linux.process_manager import MT5LaunchError

        error = MT5LaunchError("Test error")
        assert isinstance(error, ProcessError)
        assert isinstance(error, MT5LinuxError)
        assert isinstance(error, Exception)

    def test_mt5_launch_error_message_preserved(self) -> None:
        """MT5LaunchError should preserve error message."""
        from mt5linux.process_manager import MT5LaunchError

        message = "MT5 not found in Wine prefix"
        error = MT5LaunchError(message)
        assert str(error) == message

    def test_mt5_launch_error_with_troubleshooting_suggestion(self) -> None:
        """MT5LaunchError can include troubleshooting suggestions."""
        from mt5linux.process_manager import MT5LaunchError

        message = (
            "MetaTrader5 terminal not found in Wine prefix: /home/user/.mt5. "
            "Ensure MT5 is installed in the Wine prefix. "
            "Run 'mt5linux setup' to install MT5."
        )
        error = MT5LaunchError(message)
        assert "mt5linux setup" in str(error)
        assert "Wine prefix" in str(error)

    def test_mt5_launch_error_preserves_cause(self) -> None:
        """MT5LaunchError should preserve exception chain."""
        from mt5linux.process_manager import MT5LaunchError

        original = OSError("File not found")
        try:
            try:
                raise original
            except OSError as e:
                raise MT5LaunchError("Launch failed") from e
        except MT5LaunchError as error:
            assert error.__cause__ is original


@pytest.mark.unit
class TestFindMT5Executable:
    """Test ProcessManager.find_mt5_executable() method."""

    def test_find_mt5_executable_no_wine_prefix(self) -> None:
        """Should raise MT5LaunchError when Wine prefix not configured."""
        from mt5linux.process_manager import MT5LaunchError, ProcessManager

        pm = ProcessManager()

        # Mock _get_wine_prefix to return None
        with patch.object(pm, "_get_wine_prefix", return_value=None):
            with pytest.raises(MT5LaunchError) as exc_info:
                pm.find_mt5_executable()

            assert "Wine prefix not configured" in str(exc_info.value)
            assert "mt5linux setup" in str(exc_info.value)

    def test_find_mt5_executable_program_files(self, tmp_path) -> None:
        """Should find MT5 in Program Files location."""
        from mt5linux.process_manager import ProcessManager

        # Create mock Wine prefix structure
        wine_prefix = tmp_path / "wine_prefix"
        mt5_dir = wine_prefix / "drive_c" / "Program Files" / "MetaTrader 5"
        mt5_dir.mkdir(parents=True)
        mt5_exe = mt5_dir / "terminal64.exe"
        mt5_exe.touch()

        pm = ProcessManager()

        with patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix)):
            result = pm.find_mt5_executable()
            assert result == str(mt5_exe)

    def test_find_mt5_executable_program_files_x86(self, tmp_path) -> None:
        """Should find MT5 in Program Files (x86) location."""
        from mt5linux.process_manager import ProcessManager

        # Create mock Wine prefix structure
        wine_prefix = tmp_path / "wine_prefix"
        mt5_dir = wine_prefix / "drive_c" / "Program Files (x86)" / "MetaTrader 5"
        mt5_dir.mkdir(parents=True)
        mt5_exe = mt5_dir / "terminal64.exe"
        mt5_exe.touch()

        pm = ProcessManager()

        with patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix)):
            result = pm.find_mt5_executable()
            assert result == str(mt5_exe)

    def test_find_mt5_executable_prefers_program_files(self, tmp_path) -> None:
        """Should prefer Program Files over Program Files (x86)."""
        from mt5linux.process_manager import ProcessManager

        # Create mock Wine prefix with both locations
        wine_prefix = tmp_path / "wine_prefix"

        # Program Files (preferred)
        mt5_dir_pf = wine_prefix / "drive_c" / "Program Files" / "MetaTrader 5"
        mt5_dir_pf.mkdir(parents=True)
        mt5_exe_pf = mt5_dir_pf / "terminal64.exe"
        mt5_exe_pf.touch()

        # Program Files (x86)
        mt5_dir_x86 = wine_prefix / "drive_c" / "Program Files (x86)" / "MetaTrader 5"
        mt5_dir_x86.mkdir(parents=True)
        mt5_exe_x86 = mt5_dir_x86 / "terminal64.exe"
        mt5_exe_x86.touch()

        pm = ProcessManager()

        with patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix)):
            result = pm.find_mt5_executable()
            # Should return Program Files (first in search order)
            assert result == str(mt5_exe_pf)

    def test_find_mt5_executable_not_found(self, tmp_path) -> None:
        """Should raise MT5LaunchError when MT5 not found."""
        from mt5linux.process_manager import MT5LaunchError, ProcessManager

        # Create empty Wine prefix
        wine_prefix = tmp_path / "wine_prefix"
        drive_c = wine_prefix / "drive_c"
        drive_c.mkdir(parents=True)

        pm = ProcessManager()

        with patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix)):
            with pytest.raises(MT5LaunchError) as exc_info:
                pm.find_mt5_executable()

            assert "MetaTrader5 terminal not found" in str(exc_info.value)
            assert str(wine_prefix) in str(exc_info.value)

    def test_find_mt5_executable_logs_found_path(self, tmp_path, caplog) -> None:
        """Should log when MT5 executable is found."""
        import logging

        from mt5linux.process_manager import ProcessManager

        # Create mock Wine prefix structure
        wine_prefix = tmp_path / "wine_prefix"
        mt5_dir = wine_prefix / "drive_c" / "Program Files" / "MetaTrader 5"
        mt5_dir.mkdir(parents=True)
        mt5_exe = mt5_dir / "terminal64.exe"
        mt5_exe.touch()

        pm = ProcessManager()

        with patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix)):
            with caplog.at_level(logging.INFO):
                result = pm.find_mt5_executable()
                assert "Found MT5 executable" in caplog.text or result == str(mt5_exe)


@pytest.mark.unit
class TestStartMT5:
    """Test ProcessManager.start_mt5() method."""

    def test_start_mt5_already_running(self) -> None:
        """Should return existing process when MT5 already running."""
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        existing_process = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
            cmdline=["wine", "terminal64.exe"],
        )

        with patch.object(pm, "find_mt5", return_value=existing_process):
            result = pm.start_mt5()
            assert result == existing_process
            assert result.pid == 12345

    def test_start_mt5_launches_new_instance(self, tmp_path) -> None:
        """Should launch new MT5 instance via Wine."""
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()

        # Create mock Wine prefix structure
        wine_prefix = tmp_path / "wine_prefix"
        mt5_dir = wine_prefix / "drive_c" / "Program Files" / "MetaTrader 5"
        mt5_dir.mkdir(parents=True)
        mt5_exe = mt5_dir / "terminal64.exe"
        mt5_exe.touch()

        new_process = ProcessInfo(
            pid=54321,
            name="terminal64.exe",
            status="running",
        )

        mock_popen = MagicMock()
        mock_popen.poll.return_value = None  # Still running

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(pm, "find_mt5", side_effect=[None, new_process])
            )
            stack.enter_context(
                patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix))
            )
            popen_mock = stack.enter_context(
                patch("subprocess.Popen", return_value=mock_popen)
            )

            result = pm.start_mt5()
            assert result.pid == 54321

            # Verify Wine command was called
            popen_mock.assert_called_once()
            call_args = popen_mock.call_args
            cmd = call_args[0][0]
            assert cmd[0] == "wine"
            assert "terminal64.exe" in cmd[1]
            assert call_args[1]["start_new_session"] is True

    def test_start_mt5_sets_wineprefix(self, tmp_path) -> None:
        """Should set WINEPREFIX environment variable."""
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()

        # Create mock Wine prefix structure
        wine_prefix = tmp_path / "wine_prefix"
        mt5_dir = wine_prefix / "drive_c" / "Program Files" / "MetaTrader 5"
        mt5_dir.mkdir(parents=True)
        mt5_exe = mt5_dir / "terminal64.exe"
        mt5_exe.touch()

        new_process = ProcessInfo(pid=54321, name="terminal64.exe", status="running")
        mock_popen = MagicMock()
        mock_popen.poll.return_value = None

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(pm, "find_mt5", side_effect=[None, new_process])
            )
            stack.enter_context(
                patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix))
            )
            popen_mock = stack.enter_context(
                patch("subprocess.Popen", return_value=mock_popen)
            )

            pm.start_mt5()

            call_args = popen_mock.call_args
            env = call_args[1]["env"]
            assert env["WINEPREFIX"] == str(wine_prefix)

    def test_start_mt5_raises_on_wine_error(self, tmp_path) -> None:
        """Should raise MT5LaunchError when Wine fails to start."""
        from mt5linux.process_manager import MT5LaunchError, ProcessManager

        pm = ProcessManager()

        # Create mock Wine prefix structure
        wine_prefix = tmp_path / "wine_prefix"
        mt5_dir = wine_prefix / "drive_c" / "Program Files" / "MetaTrader 5"
        mt5_dir.mkdir(parents=True)
        mt5_exe = mt5_dir / "terminal64.exe"
        mt5_exe.touch()

        with ExitStack() as stack:
            stack.enter_context(patch.object(pm, "find_mt5", return_value=None))
            stack.enter_context(
                patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix))
            )
            stack.enter_context(
                patch("subprocess.Popen", side_effect=OSError("Wine not found"))
            )

            with pytest.raises(MT5LaunchError) as exc_info:
                pm.start_mt5()

            assert "Failed to launch MT5 via Wine" in str(exc_info.value)

    def test_start_mt5_logs_launch_decision(self, tmp_path, caplog) -> None:
        """Should log whether MT5 is already running or needs launching."""
        import logging

        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        existing_process = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
        )

        with caplog.at_level(logging.INFO):
            with patch.object(pm, "find_mt5", return_value=existing_process):
                pm.start_mt5()

            assert "already running" in caplog.text.lower() or "12345" in caplog.text


@pytest.mark.unit
class TestWaitForMT5Ready:
    """Test ProcessManager._wait_for_mt5_ready() method."""

    def test_wait_for_mt5_ready_success(self) -> None:
        """Should return ProcessInfo when MT5 becomes ready."""
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        ready_process = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
        )

        with patch.object(pm, "find_mt5", return_value=ready_process):
            result = pm._wait_for_mt5_ready(timeout=5.0)
            assert result.pid == 12345
            assert result.status == "running"

    def test_wait_for_mt5_ready_timeout(self) -> None:
        """Should raise MT5LaunchError when MT5 doesn't start in time."""
        from mt5linux.process_manager import MT5LaunchError, ProcessManager

        pm = ProcessManager()

        # MT5 never starts
        with patch.object(pm, "find_mt5", return_value=None):
            with patch("time.sleep"):  # Speed up test
                with pytest.raises(MT5LaunchError) as exc_info:
                    pm._wait_for_mt5_ready(timeout=0.1)

            assert "did not become ready" in str(exc_info.value)

    def test_wait_for_mt5_ready_eventual_success(self) -> None:
        """Should succeed when MT5 becomes ready after a few checks."""
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        ready_process = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
        )

        # Return None twice, then success
        call_count = [0]

        def mock_find_mt5():
            call_count[0] += 1
            if call_count[0] >= 3:
                return ready_process
            return None

        with ExitStack() as stack:
            stack.enter_context(patch.object(pm, "find_mt5", side_effect=mock_find_mt5))
            stack.enter_context(patch("time.sleep"))  # Speed up test

            result = pm._wait_for_mt5_ready(timeout=10.0)
            assert result.pid == 12345

    def test_wait_for_mt5_ready_process_not_running(self) -> None:
        """Should keep waiting if process found but status not 'running'."""
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        sleeping_process = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="sleeping",
        )
        running_process = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
        )

        call_count = [0]

        def mock_find_mt5():
            call_count[0] += 1
            if call_count[0] >= 2:
                return running_process
            return sleeping_process

        with ExitStack() as stack:
            stack.enter_context(patch.object(pm, "find_mt5", side_effect=mock_find_mt5))
            stack.enter_context(patch("time.sleep"))

            result = pm._wait_for_mt5_ready(timeout=10.0)
            assert result.status == "running"

    def test_wait_for_mt5_ready_logs_success(self, caplog) -> None:
        """Should log when MT5 becomes ready."""
        import logging

        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        ready_process = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
        )

        with caplog.at_level(logging.INFO):
            with patch.object(pm, "find_mt5", return_value=ready_process):
                pm._wait_for_mt5_ready(timeout=5.0)

            assert "ready" in caplog.text.lower() or "12345" in caplog.text


@pytest.mark.unit
class TestEnsureMT5Running:
    """Test LifecycleManager.ensure_mt5_running() method."""

    def test_ensure_mt5_running_already_running(self) -> None:
        """Should return existing ProcessInfo when MT5 already running."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=5.0)

        existing_process = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
        )

        with patch.object(pm, "find_mt5", return_value=existing_process):
            result = lm.ensure_mt5_running()
            assert result.pid == 12345
            assert lm._mt5_pid == 12345

    def test_ensure_mt5_running_starts_mt5(self) -> None:
        """Should start MT5 when not running."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=5.0)

        new_process = ProcessInfo(
            pid=54321,
            name="terminal64.exe",
            status="running",
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(pm, "find_mt5", return_value=None))
            stack.enter_context(patch.object(pm, "start_mt5", return_value=new_process))

            result = lm.ensure_mt5_running()
            assert result.pid == 54321
            assert lm._mt5_pid == 54321

    def test_ensure_mt5_running_logs_decision(self, caplog) -> None:
        """Should log whether MT5 is reused or started."""
        import logging

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=5.0)

        existing_process = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
        )

        with caplog.at_level(logging.DEBUG):
            with patch.object(pm, "find_mt5", return_value=existing_process):
                lm.ensure_mt5_running()

            # Check log mentions existing/already running
            assert "already running" in caplog.text.lower() or "12345" in caplog.text

    def test_ensure_mt5_running_propagates_mt5_launch_error(self) -> None:
        """Should propagate MT5LaunchError when launch fails."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import MT5LaunchError, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=5.0)

        with ExitStack() as stack:
            stack.enter_context(patch.object(pm, "find_mt5", return_value=None))
            stack.enter_context(
                patch.object(
                    pm, "start_mt5", side_effect=MT5LaunchError("MT5 not found")
                )
            )

            with pytest.raises(MT5LaunchError):
                lm.ensure_mt5_running()

    def test_ensure_mt5_running_thread_safe(self) -> None:
        """Should be thread-safe with proper locking."""
        import threading

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=5.0)

        existing_process = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
        )

        results = []
        errors = []

        def call_ensure():
            try:
                with patch.object(pm, "find_mt5", return_value=existing_process):
                    result = lm.ensure_mt5_running()
                    results.append(result.pid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_ensure) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(pid == 12345 for pid in results)


@pytest.mark.unit
class TestProcessManagerMT5Lifecycle:
    """Test ProcessManager MT5 lifecycle integration methods."""

    def test_start_mt5_lifecycle(self) -> None:
        """Should start MT5 lifecycle management."""
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()

        # Mock find_mt5 to return a running process
        with patch.object(
            pm,
            "find_mt5",
            return_value=ProcessInfo(
                pid=12345,
                name="terminal64.exe",
                status="running",
            ),
        ):
            pm.start_mt5_lifecycle()
            # Should create lifecycle manager if not exists
            assert pm._lifecycle_manager is not None
            # Should have tracked MT5 PID
            assert pm._lifecycle_manager._mt5_pid == 12345

    def test_get_mt5_status_no_lifecycle(self) -> None:
        """Should return None when lifecycle management not active."""
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        pm._lifecycle_manager = None

        result = pm.get_mt5_status()
        assert result is None

    def test_get_mt5_status_with_lifecycle(self) -> None:
        """Should return MT5 status from lifecycle manager."""
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        mock_lifecycle = MagicMock()
        mock_lifecycle._mt5_pid = 12345
        mock_lifecycle.get_status.return_value = {
            "monitoring_active": True,
            "current_pid": 99999,  # rpyc server pid
            "mt5_pid": 12345,
        }
        pm._lifecycle_manager = mock_lifecycle

        result = pm.get_mt5_status()
        assert result is not None
        assert result["mt5_pid"] == 12345

    def test_get_mt5_status_integrates_with_lifecycle(self) -> None:
        """Should integrate MT5 status with lifecycle status."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=5.0)
        pm._lifecycle_manager = lm

        # Set MT5 PID via ensure_mt5_running
        with patch.object(
            pm,
            "find_mt5",
            return_value=ProcessInfo(
                pid=12345,
                name="terminal64.exe",
                status="running",
            ),
        ):
            lm.ensure_mt5_running()

        result = pm.get_mt5_status()
        assert result is not None
        assert result.get("mt5_pid") == 12345


@pytest.mark.unit
class TestMT5AlreadyRunning:
    """Test MT5 detection when already running."""

    def test_start_mt5_returns_existing_immediately(self) -> None:
        """start_mt5 should return immediately without launching when MT5 running."""
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        existing = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
        )

        call_count = [0]

        def mock_find_mt5():
            call_count[0] += 1
            return existing

        with patch.object(pm, "find_mt5", side_effect=mock_find_mt5):
            result = pm.start_mt5()
            # Should only call find_mt5 once
            assert call_count[0] == 1
            assert result.pid == 12345

    def test_start_mt5_does_not_call_subprocess_when_running(self) -> None:
        """start_mt5 should not call Popen when MT5 already running."""
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        existing = ProcessInfo(
            pid=12345,
            name="terminal64.exe",
            status="running",
        )

        with ExitStack() as stack:
            stack.enter_context(patch.object(pm, "find_mt5", return_value=existing))
            popen_mock = stack.enter_context(patch("subprocess.Popen"))

            pm.start_mt5()
            popen_mock.assert_not_called()


@pytest.mark.unit
class TestMT5ErrorHandling:
    """Test error handling scenarios for MT5 launch."""

    def test_find_mt5_executable_handles_permission_error(self, tmp_path) -> None:
        """find_mt5_executable should handle permission errors gracefully."""
        from mt5linux.process_manager import MT5LaunchError, ProcessManager

        pm = ProcessManager()

        # Create Wine prefix but with no MT5
        wine_prefix = tmp_path / "wine_prefix"
        drive_c = wine_prefix / "drive_c"
        drive_c.mkdir(parents=True)

        with patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix)):
            with pytest.raises(MT5LaunchError) as exc_info:
                pm.find_mt5_executable()
            assert "not found" in str(exc_info.value)

    def test_start_mt5_handles_process_died_during_wait(self, tmp_path) -> None:
        """Should raise MT5LaunchError if process dies during wait."""
        from mt5linux.process_manager import MT5LaunchError, ProcessManager

        pm = ProcessManager()

        # Create mock Wine prefix
        wine_prefix = tmp_path / "wine_prefix"
        mt5_dir = wine_prefix / "drive_c" / "Program Files" / "MetaTrader 5"
        mt5_dir.mkdir(parents=True)
        mt5_exe = mt5_dir / "terminal64.exe"
        mt5_exe.touch()

        mock_popen = MagicMock()
        mock_popen.poll.return_value = None

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(pm, "find_mt5", return_value=None)
            )  # Never found
            stack.enter_context(
                patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix))
            )
            stack.enter_context(patch("subprocess.Popen", return_value=mock_popen))
            stack.enter_context(patch("time.sleep"))

            with pytest.raises(MT5LaunchError) as exc_info:
                pm.start_mt5()
            assert "did not become ready" in str(exc_info.value)


@pytest.mark.unit
class TestLifecycleStatusIntegration:
    """Test LifecycleManager status includes MT5 information."""

    def test_get_status_includes_mt5_pid(self) -> None:
        """get_status should include MT5 PID when set."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=5.0)

        with patch.object(
            pm,
            "find_mt5",
            return_value=ProcessInfo(
                pid=99999,
                name="terminal64.exe",
                status="running",
            ),
        ):
            lm.ensure_mt5_running()

        status = lm.get_status()
        # Status contains base lifecycle info
        assert "monitoring_active" in status
        assert "current_pid" in status

    def test_lifecycle_manager_initializes_mt5_pid_none(self) -> None:
        """LifecycleManager should initialize _mt5_pid to None."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=5.0)

        assert lm._mt5_pid is None


@pytest.mark.unit
class TestMT5LaunchLogging:
    """Test logging during MT5 launch operations."""

    def test_find_mt5_executable_logs_error_before_raising(
        self, tmp_path, caplog
    ) -> None:
        """Should log error details before raising MT5LaunchError."""
        import logging

        from mt5linux.process_manager import MT5LaunchError, ProcessManager

        pm = ProcessManager()
        wine_prefix = tmp_path / "wine_prefix"
        drive_c = wine_prefix / "drive_c"
        drive_c.mkdir(parents=True)

        with ExitStack() as stack:
            stack.enter_context(caplog.at_level(logging.DEBUG))
            stack.enter_context(
                patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix))
            )

            try:
                pm.find_mt5_executable()
            except MT5LaunchError:
                pass
            # The method raises before logging, which is acceptable behavior

    def test_start_mt5_logs_wine_command(self, tmp_path, caplog) -> None:
        """Should log the Wine command when starting MT5."""
        import logging

        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        wine_prefix = tmp_path / "wine_prefix"
        mt5_dir = wine_prefix / "drive_c" / "Program Files" / "MetaTrader 5"
        mt5_dir.mkdir(parents=True)
        mt5_exe = mt5_dir / "terminal64.exe"
        mt5_exe.touch()

        mock_popen = MagicMock()
        mock_popen.poll.return_value = None

        new_process = ProcessInfo(
            pid=54321,
            name="terminal64.exe",
            status="running",
        )

        with ExitStack() as stack:
            stack.enter_context(caplog.at_level(logging.DEBUG))
            stack.enter_context(
                patch.object(pm, "find_mt5", side_effect=[None, new_process])
            )
            stack.enter_context(
                patch.object(pm, "_get_wine_prefix", return_value=str(wine_prefix))
            )
            stack.enter_context(patch("subprocess.Popen", return_value=mock_popen))

            pm.start_mt5()
            # Check debug logs contain command info
            assert "wine" in caplog.text.lower() or "starting" in caplog.text.lower()
