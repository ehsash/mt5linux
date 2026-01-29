"""Tests for rpyc server lifecycle management.

This module tests the LifecycleManager class which provides:
- Background health monitoring of the rpyc server
- Automatic restart with exponential backoff on crash detection
- Callback notifications for monitoring integration
- Thread-safe lifecycle operations
"""

import threading

import pytest


@pytest.mark.unit
class TestLifecycleManagerInit:
    """Test LifecycleManager initialization and configuration."""

    def test_init_with_default_check_interval(self) -> None:
        """LifecycleManager should use 5.0 second default check interval."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        assert lm._check_interval == 5.0

    def test_init_with_custom_check_interval(self) -> None:
        """LifecycleManager should accept custom check interval."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=10.0)

        assert lm._check_interval == 10.0

    def test_init_stores_process_manager_reference(self) -> None:
        """LifecycleManager should store reference to ProcessManager."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        assert lm._process_manager is pm

    def test_init_creates_stop_event(self) -> None:
        """LifecycleManager should create threading.Event for shutdown."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        assert isinstance(lm._stop_event, threading.Event)
        assert not lm._stop_event.is_set()

    def test_init_creates_lock(self) -> None:
        """LifecycleManager should create threading.Lock for thread safety."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        assert isinstance(lm._lock, type(threading.Lock()))

    def test_init_with_empty_callbacks_list(self) -> None:
        """LifecycleManager should initialize with empty callbacks list."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        assert lm._callbacks == []

    def test_init_monitor_thread_is_none(self) -> None:
        """LifecycleManager should start with no monitoring thread."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        assert lm._monitor_thread is None

    def test_init_current_pid_is_none(self) -> None:
        """LifecycleManager should start with no tracked PID."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        assert lm._current_pid is None


@pytest.mark.unit
class TestLifecycleManagerStartMonitoring:
    """Test start_monitoring method."""

    def test_start_monitoring_creates_daemon_thread(self) -> None:
        """start_monitoring should create daemon thread."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=2.0)

        try:
            lm.start_monitoring()

            assert lm._monitor_thread is not None
            assert lm._monitor_thread.daemon is True
        finally:
            lm.stop_monitoring()

    def test_start_monitoring_sets_thread_name(self) -> None:
        """start_monitoring should set descriptive thread name."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=2.0)

        try:
            lm.start_monitoring()

            assert lm._monitor_thread is not None
            assert "lifecycle" in lm._monitor_thread.name.lower()
        finally:
            lm.stop_monitoring()

    def test_start_monitoring_thread_is_alive(self) -> None:
        """start_monitoring should start the thread."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=2.0)

        try:
            lm.start_monitoring()

            assert lm._monitor_thread is not None
            assert lm._monitor_thread.is_alive()
        finally:
            lm.stop_monitoring()

    def test_start_monitoring_clears_stop_event(self) -> None:
        """start_monitoring should clear stop event."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=2.0)
        lm._stop_event.set()  # Pre-set it

        try:
            lm.start_monitoring()

            assert not lm._stop_event.is_set()
        finally:
            lm.stop_monitoring()

    def test_start_monitoring_does_not_create_duplicate_threads(self) -> None:
        """start_monitoring should not create duplicate threads."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=2.0)

        try:
            lm.start_monitoring()
            first_thread = lm._monitor_thread

            lm.start_monitoring()  # Call again
            second_thread = lm._monitor_thread

            assert first_thread is second_thread
        finally:
            lm.stop_monitoring()


@pytest.mark.unit
class TestLifecycleManagerStopMonitoring:
    """Test stop_monitoring method."""

    def test_stop_monitoring_sets_stop_event(self) -> None:
        """stop_monitoring should set stop event."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=2.0)

        lm.start_monitoring()
        lm.stop_monitoring()

        assert lm._stop_event.is_set()

    def test_stop_monitoring_waits_for_thread_termination(self) -> None:
        """stop_monitoring should wait for thread to terminate."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=2.0)

        lm.start_monitoring()
        lm.stop_monitoring()

        assert lm._monitor_thread is None or not lm._monitor_thread.is_alive()

    def test_stop_monitoring_handles_no_active_thread(self) -> None:
        """stop_monitoring should handle case when no thread is running."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        # Should not raise
        lm.stop_monitoring()

        assert lm._monitor_thread is None


@pytest.mark.unit
class TestLifecycleManagerGetStatus:
    """Test get_status method."""

    def test_get_status_returns_dict(self) -> None:
        """get_status should return dictionary."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        status = lm.get_status()

        assert isinstance(status, dict)

    def test_get_status_contains_monitoring_active_key(self) -> None:
        """get_status should contain monitoring_active key."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        status = lm.get_status()

        assert "monitoring_active" in status
        assert status["monitoring_active"] is False

    def test_get_status_monitoring_active_when_running(self) -> None:
        """get_status should show monitoring_active=True when thread running."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=2.0)

        try:
            lm.start_monitoring()

            status = lm.get_status()

            assert status["monitoring_active"] is True
        finally:
            lm.stop_monitoring()

    def test_get_status_contains_current_pid(self) -> None:
        """get_status should contain current_pid key."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        status = lm.get_status()

        assert "current_pid" in status

    def test_get_status_contains_consecutive_failures(self) -> None:
        """get_status should contain consecutive_failures key."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        status = lm.get_status()

        assert "consecutive_failures" in status
        assert status["consecutive_failures"] == 0

    def test_get_status_contains_total_restarts(self) -> None:
        """get_status should contain total_restarts key."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        status = lm.get_status()

        assert "total_restarts" in status
        assert status["total_restarts"] == 0


@pytest.mark.unit
class TestLifecycleExceptions:
    """Test lifecycle exception hierarchy."""

    def test_lifecycle_error_inherits_from_process_error(self) -> None:
        """LifecycleError should inherit from ProcessError."""
        from mt5linux.lifecycle import LifecycleError
        from mt5linux.process_manager import ProcessError

        assert issubclass(LifecycleError, ProcessError)

    def test_server_restart_error_inherits_from_lifecycle_error(self) -> None:
        """ServerRestartError should inherit from LifecycleError."""
        from mt5linux.lifecycle import LifecycleError, ServerRestartError

        assert issubclass(ServerRestartError, LifecycleError)

    def test_monitoring_error_inherits_from_lifecycle_error(self) -> None:
        """MonitoringError should inherit from LifecycleError."""
        from mt5linux.lifecycle import LifecycleError, MonitoringError

        assert issubclass(MonitoringError, LifecycleError)

    def test_lifecycle_error_can_be_raised_with_message(self) -> None:
        """LifecycleError should accept message."""
        from mt5linux.lifecycle import LifecycleError

        error = LifecycleError("Test error message")
        assert str(error) == "Test error message"

    def test_server_restart_error_can_be_raised_with_message(self) -> None:
        """ServerRestartError should accept message."""
        from mt5linux.lifecycle import ServerRestartError

        error = ServerRestartError("Failed after 5 attempts")
        assert str(error) == "Failed after 5 attempts"

    def test_monitoring_error_can_be_raised_with_message(self) -> None:
        """MonitoringError should accept message."""
        from mt5linux.lifecycle import MonitoringError

        error = MonitoringError("Thread failed unexpectedly")
        assert str(error) == "Thread failed unexpectedly"


@pytest.mark.unit
class TestHealthMonitoring:
    """Test health monitoring functionality."""

    def test_perform_health_check_updates_last_check_time(self) -> None:
        """_perform_health_check should update last_check_time."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        assert lm._last_check_time is None

        lm._perform_health_check()

        assert lm._last_check_time is not None

    def test_perform_health_check_tracks_pid_when_server_found(self) -> None:
        """_perform_health_check should track PID when server found."""
        from unittest.mock import patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        mock_info = ProcessInfo(pid=12345, name="python.exe", status="running")

        with patch.object(pm, "find_rpyc_server", return_value=mock_info):
            lm._perform_health_check()

        assert lm._current_pid == 12345
        assert lm._failure_count == 0

    def test_perform_health_check_increments_failures_when_not_found(self) -> None:
        """_perform_health_check should increment failures when server not found."""
        from unittest.mock import patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)
        lm._current_pid = 12345  # Simulate previously running

        with patch.object(pm, "find_rpyc_server", return_value=None):
            with patch.object(lm, "_handle_crash"):  # Prevent actual restart
                lm._perform_health_check()

        assert lm._failure_count == 1
        assert lm._current_pid is None

    def test_perform_health_check_resets_failures_after_success(self) -> None:
        """_perform_health_check should reset failures after success."""
        from unittest.mock import patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)
        lm._failure_count = 3  # Simulate previous failures

        mock_info = ProcessInfo(pid=12345, name="python.exe", status="running")

        with patch.object(pm, "find_rpyc_server", return_value=mock_info):
            lm._perform_health_check()

        assert lm._failure_count == 0


@pytest.mark.unit
class TestAutomaticRestart:
    """Test automatic restart with exponential backoff."""

    def test_restart_with_backoff_calls_start_rpyc_server(self) -> None:
        """_restart_with_backoff should call start_rpyc_server."""
        from unittest.mock import patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        mock_info = ProcessInfo(pid=99999, name="python.exe", status="running")

        with patch.object(
            pm, "start_rpyc_server", return_value=mock_info
        ) as mock_start:
            result = lm._restart_with_backoff()

        mock_start.assert_called_once()
        assert result.pid == 99999

    def test_restart_with_backoff_increments_restart_count(self) -> None:
        """_restart_with_backoff should increment restart count."""
        from unittest.mock import patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        assert lm._restart_count == 0

        mock_info = ProcessInfo(pid=99999, name="python.exe", status="running")

        with patch.object(pm, "start_rpyc_server", return_value=mock_info):
            lm._restart_with_backoff()

        assert lm._restart_count == 1

    def test_restart_with_backoff_retries_on_failure(self) -> None:
        """_restart_with_backoff should retry on failure with backoff."""
        from unittest.mock import patch

        from mt5linux.lifecycle import LifecycleManager, ServerRestartError
        from mt5linux.process_manager import ProcessManager, RpycServerError

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        with patch.object(
            pm, "start_rpyc_server", side_effect=RpycServerError("failed")
        ):
            with patch("mt5linux.lifecycle.time.sleep") as mock_sleep:
                with pytest.raises(ServerRestartError):
                    lm._restart_with_backoff()

        # Should have attempted 5 times with 4 sleeps between
        assert mock_sleep.call_count == 4
        assert lm._restart_count == 5

    def test_restart_with_backoff_exponential_delays(self) -> None:
        """_restart_with_backoff should use exponential delays."""
        from typing import List
        from unittest.mock import patch

        from mt5linux.lifecycle import LifecycleManager, ServerRestartError
        from mt5linux.process_manager import ProcessManager, RpycServerError

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        sleep_calls: List[float] = []

        def capture_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch.object(
            pm, "start_rpyc_server", side_effect=RpycServerError("failed")
        ):
            with patch("mt5linux.lifecycle.time.sleep", side_effect=capture_sleep):
                with pytest.raises(ServerRestartError):
                    lm._restart_with_backoff()

        # Verify delays are approximately 1, 2, 4, 8 (with jitter 0-0.1)
        assert len(sleep_calls) == 4
        assert 1.0 <= sleep_calls[0] <= 1.1
        assert 2.0 <= sleep_calls[1] <= 2.1
        assert 4.0 <= sleep_calls[2] <= 4.1
        assert 8.0 <= sleep_calls[3] <= 8.1


@pytest.mark.unit
class TestCallbackNotifications:
    """Test callback registration and notification."""

    def test_register_callback_adds_to_list(self) -> None:
        """register_callback should add callback to list."""
        from unittest.mock import MagicMock

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        callback = MagicMock()
        lm.register_callback(callback)

        assert callback in lm._callbacks

    def test_unregister_callback_removes_from_list(self) -> None:
        """unregister_callback should remove callback from list."""
        from unittest.mock import MagicMock

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        callback = MagicMock()
        lm.register_callback(callback)
        lm.unregister_callback(callback)

        assert callback not in lm._callbacks

    def test_notify_callbacks_calls_all_registered(self) -> None:
        """_notify_callbacks should call all registered callbacks."""
        from unittest.mock import MagicMock

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        callback1 = MagicMock()
        callback2 = MagicMock()

        lm.register_callback(callback1)
        lm.register_callback(callback2)

        lm._notify_callbacks("test_event", 12345, {"key": "value"})

        callback1.assert_called_once_with("test_event", 12345, {"key": "value"})
        callback2.assert_called_once_with("test_event", 12345, {"key": "value"})

    def test_notify_callbacks_handles_exceptions_gracefully(self) -> None:
        """_notify_callbacks should handle callback exceptions."""
        from unittest.mock import MagicMock

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        failing_callback = MagicMock(side_effect=ValueError("callback error"))
        success_callback = MagicMock()

        lm.register_callback(failing_callback)
        lm.register_callback(success_callback)

        # Should not raise, and should still call second callback
        lm._notify_callbacks("test_event", 12345, {})

        failing_callback.assert_called_once()
        success_callback.assert_called_once()

    def test_restart_notifies_on_success(self) -> None:
        """_restart_with_backoff should notify on success."""
        from unittest.mock import MagicMock, patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        callback = MagicMock()
        lm.register_callback(callback)

        mock_info = ProcessInfo(pid=99999, name="python.exe", status="running")

        with patch.object(pm, "start_rpyc_server", return_value=mock_info):
            lm._restart_with_backoff()

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == "restart"
        assert args[1] == 99999

    def test_restart_notifies_on_final_failure(self) -> None:
        """_restart_with_backoff should notify on final failure."""
        from unittest.mock import MagicMock, patch

        from mt5linux.lifecycle import LifecycleManager, ServerRestartError
        from mt5linux.process_manager import ProcessManager, RpycServerError

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        callback = MagicMock()
        lm.register_callback(callback)

        with patch.object(
            pm, "start_rpyc_server", side_effect=RpycServerError("failed")
        ):
            with patch("mt5linux.lifecycle.time.sleep"):
                with pytest.raises(ServerRestartError):
                    lm._restart_with_backoff()

        # Should be called once with "failure" event
        callback.assert_called()
        last_call = callback.call_args_list[-1]
        assert last_call[0][0] == "failure"


@pytest.mark.unit
class TestProcessManagerIntegration:
    """Test ProcessManager lifecycle integration methods."""

    def test_start_lifecycle_management_creates_manager(self) -> None:
        """start_lifecycle_management should create LifecycleManager."""
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()

        try:
            pm.start_lifecycle_management(check_interval=2.0)

            assert pm._lifecycle_manager is not None
        finally:
            pm.stop_lifecycle_management()

    def test_start_lifecycle_management_starts_monitoring(self) -> None:
        """start_lifecycle_management should start monitoring."""
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()

        try:
            pm.start_lifecycle_management(check_interval=2.0)

            status = pm.get_lifecycle_status()
            assert status is not None
            assert status["monitoring_active"] is True
        finally:
            pm.stop_lifecycle_management()

    def test_stop_lifecycle_management_stops_monitoring(self) -> None:
        """stop_lifecycle_management should stop monitoring."""
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()

        pm.start_lifecycle_management(check_interval=2.0)
        pm.stop_lifecycle_management()

        status = pm.get_lifecycle_status()
        assert status is not None
        assert status["monitoring_active"] is False

    def test_get_lifecycle_status_returns_none_when_not_active(self) -> None:
        """get_lifecycle_status should return None when not active."""
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()

        status = pm.get_lifecycle_status()

        assert status is None

    def test_get_lifecycle_status_returns_dict_when_active(self) -> None:
        """get_lifecycle_status should return dict when active."""
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()

        try:
            pm.start_lifecycle_management(check_interval=2.0)

            status = pm.get_lifecycle_status()

            assert isinstance(status, dict)
            assert "monitoring_active" in status
            assert "current_pid" in status
        finally:
            pm.stop_lifecycle_management()

    def test_stop_lifecycle_management_handles_no_manager(self) -> None:
        """stop_lifecycle_management should handle no active manager."""
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()

        # Should not raise
        pm.stop_lifecycle_management()


@pytest.mark.unit
class TestEnsureServerRunning:
    """Test ensure_server_running method."""

    def test_ensure_server_running_returns_existing(self) -> None:
        """ensure_server_running should return existing server."""
        from unittest.mock import patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        mock_info = ProcessInfo(pid=12345, name="python.exe", status="running")

        with patch.object(pm, "find_rpyc_server", return_value=mock_info):
            result = lm.ensure_server_running()

        assert result.pid == 12345
        assert lm._current_pid == 12345

    def test_ensure_server_running_starts_when_not_running(self) -> None:
        """ensure_server_running should start server when not running."""
        from unittest.mock import patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        mock_info = ProcessInfo(pid=99999, name="python.exe", status="running")

        with patch.object(pm, "find_rpyc_server", return_value=None):
            with patch.object(
                pm, "start_rpyc_server", return_value=mock_info
            ) as mock_start:
                result = lm.ensure_server_running()

        mock_start.assert_called_once()
        assert result.pid == 99999
        assert lm._current_pid == 99999


@pytest.mark.unit
class TestCheckIntervalValidation:
    """Test check_interval bounds validation."""

    def test_init_accepts_min_interval(self) -> None:
        """LifecycleManager should accept minimum check interval."""
        from mt5linux.lifecycle import MIN_CHECK_INTERVAL, LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=MIN_CHECK_INTERVAL)

        assert lm._check_interval == MIN_CHECK_INTERVAL

    def test_init_accepts_max_interval(self) -> None:
        """LifecycleManager should accept maximum check interval."""
        from mt5linux.lifecycle import MAX_CHECK_INTERVAL, LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=MAX_CHECK_INTERVAL)

        assert lm._check_interval == MAX_CHECK_INTERVAL

    def test_init_rejects_below_min_interval(self) -> None:
        """LifecycleManager should reject interval below minimum."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()

        with pytest.raises(ValueError) as exc_info:
            LifecycleManager(pm, check_interval=0.5)

        assert "check_interval must be between" in str(exc_info.value)

    def test_init_rejects_above_max_interval(self) -> None:
        """LifecycleManager should reject interval above maximum."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()

        with pytest.raises(ValueError) as exc_info:
            LifecycleManager(pm, check_interval=60.0)

        assert "check_interval must be between" in str(exc_info.value)


@pytest.mark.unit
class TestCrashCallbackNotification:
    """Test crash event callback notifications."""

    def test_health_check_notifies_crash_callback(self) -> None:
        """_perform_health_check should notify crash callback when server not found."""
        from unittest.mock import MagicMock, patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)
        lm._current_pid = 12345  # Simulate previously running server

        callback = MagicMock()
        lm.register_callback(callback)

        with patch.object(pm, "find_rpyc_server", return_value=None):
            with patch.object(lm, "_handle_crash"):  # Prevent restart attempt
                lm._perform_health_check()

        # Verify callback was called with "crash" event
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == "crash"
        assert args[1] == 12345  # Old PID
        assert "consecutive_failures" in args[2]

    def test_crash_callback_receives_consecutive_failures_count(self) -> None:
        """Crash callback should receive consecutive_failures in context."""
        from unittest.mock import MagicMock, patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)
        lm._current_pid = 12345
        lm._failure_count = 2  # Simulate previous failures

        callback = MagicMock()
        lm.register_callback(callback)

        with patch.object(pm, "find_rpyc_server", return_value=None):
            with patch.object(lm, "_handle_crash"):
                lm._perform_health_check()

        args = callback.call_args[0]
        # Failure count should be 3 (2 previous + 1 current)
        assert args[2]["consecutive_failures"] == 3


@pytest.mark.unit
class TestConcurrentOperations:
    """Test thread safety of concurrent lifecycle operations."""

    def test_concurrent_start_monitoring_creates_single_thread(self) -> None:
        """Concurrent start_monitoring calls should create only one thread."""
        from concurrent.futures import ThreadPoolExecutor

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=2.0)

        threads_created = []

        def start_and_capture():
            lm.start_monitoring()
            threads_created.append(lm._monitor_thread)

        try:
            # Launch multiple concurrent start_monitoring calls
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(start_and_capture) for _ in range(5)]
                for f in futures:
                    f.result()

            # All captures should reference the same thread
            unique_threads = set(id(t) for t in threads_created if t is not None)
            assert len(unique_threads) == 1
        finally:
            lm.stop_monitoring()

    def test_concurrent_get_status_is_thread_safe(self) -> None:
        """Concurrent get_status calls should not raise exceptions."""
        from concurrent.futures import ThreadPoolExecutor

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm, check_interval=2.0)

        results = []

        def get_status_repeatedly():
            for _ in range(10):
                status = lm.get_status()
                results.append(status)

        try:
            lm.start_monitoring()

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(get_status_repeatedly) for _ in range(5)]
                for f in futures:
                    f.result()

            # All results should be valid dicts
            assert len(results) == 50
            assert all(isinstance(r, dict) for r in results)
            assert all("monitoring_active" in r for r in results)
        finally:
            lm.stop_monitoring()

    def test_concurrent_callback_registration_is_thread_safe(self) -> None:
        """Concurrent callback registration should not lose callbacks."""
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import MagicMock

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = ProcessManager()
        lm = LifecycleManager(pm)

        callbacks = [MagicMock() for _ in range(20)]

        def register_callback(cb):
            lm.register_callback(cb)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(register_callback, cb) for cb in callbacks]
            for f in futures:
                f.result()

        # All callbacks should be registered
        assert len(lm._callbacks) == 20
        for cb in callbacks:
            assert cb in lm._callbacks
