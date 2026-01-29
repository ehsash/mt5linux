"""Unit tests for RecoveryManager class.

Tests for automatic recovery from connection failures.
Recovery sequence: retry → relaunch → retry → notify
Target: <30 seconds recovery time (NFR5), >95% success rate (NFR14)
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestRecoveryManagerInit:
    """Test RecoveryManager initialization and configuration."""

    def test_init_with_defaults(self) -> None:
        """RecoveryManager initializes with default values."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        assert manager._lifecycle_manager is lifecycle_manager
        assert manager._max_connection_retries == 3
        assert manager._max_relaunch_retries == 2
        assert manager._recovery_timeout == 30.0  # NFR5
        assert manager._recovery_in_progress is False
        assert manager._last_recovery_attempt is None
        assert manager._recovery_stats == {"success": 0, "failure": 0}
        assert manager._recovery_callbacks == []
        assert isinstance(manager._lock, type(threading.Lock()))

    def test_init_with_custom_values(self) -> None:
        """RecoveryManager accepts custom configuration."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(
            lifecycle_manager,
            max_connection_retries=5,
            max_relaunch_retries=3,
            recovery_timeout=60.0,
        )

        assert manager._max_connection_retries == 5
        assert manager._max_relaunch_retries == 3
        assert manager._recovery_timeout == 60.0

    def test_init_type_hints(self) -> None:
        """RecoveryManager has proper type hints."""
        from mt5linux.recovery import RecoveryManager

        # Check that type hints exist (will fail at runtime if not properly typed)
        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)
        assert hasattr(manager, "_last_recovery_attempt")


@pytest.mark.unit
class TestRecoveryStateTracking:
    """Test recovery state tracking flags."""

    def test_recovery_in_progress_flag(self) -> None:
        """_recovery_in_progress flag tracks active recovery."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        assert manager._recovery_in_progress is False

    def test_last_recovery_attempt_timestamp(self) -> None:
        """_last_recovery_attempt tracks recovery timestamp."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        assert manager._last_recovery_attempt is None

    def test_recovery_stats_dict(self) -> None:
        """_recovery_stats tracks success/failure counts."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        assert manager._recovery_stats["success"] == 0
        assert manager._recovery_stats["failure"] == 0

    def test_thread_safe_lock(self) -> None:
        """RecoveryManager uses threading.Lock for thread-safety."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        # Lock should be acquirable
        acquired = manager._lock.acquire(blocking=False)
        assert acquired is True
        manager._lock.release()


@pytest.mark.unit
class TestRecoveryCallbacks:
    """Test callback registration and management."""

    def test_register_recovery_callback(self) -> None:
        """register_recovery_callback adds callback to list."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        callback = MagicMock()
        manager.register_recovery_callback(callback)

        assert callback in manager._recovery_callbacks

    def test_register_multiple_callbacks(self) -> None:
        """Multiple callbacks can be registered."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        callback1 = MagicMock()
        callback2 = MagicMock()

        manager.register_recovery_callback(callback1)
        manager.register_recovery_callback(callback2)

        assert len(manager._recovery_callbacks) == 2
        assert callback1 in manager._recovery_callbacks
        assert callback2 in manager._recovery_callbacks

    def test_unregister_recovery_callback(self) -> None:
        """unregister_recovery_callback removes callback from list."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        callback = MagicMock()
        manager.register_recovery_callback(callback)
        manager.unregister_recovery_callback(callback)

        assert callback not in manager._recovery_callbacks


@pytest.mark.unit
class TestGetRecoveryStatus:
    """Test get_recovery_status method."""

    def test_get_recovery_status_initial(self) -> None:
        """get_recovery_status returns initial state."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        status = manager.get_recovery_status()

        assert status["last_recovery_time"] is None
        assert status["recovery_in_progress"] is False
        assert status["success_count"] == 0
        assert status["failure_count"] == 0

    def test_get_recovery_status_thread_safe(self) -> None:
        """get_recovery_status is thread-safe."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        results: list = []

        def get_status() -> None:
            for _ in range(100):
                status = manager.get_recovery_status()
                results.append(status)

        threads = [threading.Thread(target=get_status) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should succeed without exception
        assert len(results) == 500


@pytest.mark.unit
class TestAttemptRecovery:
    """Test attempt_recovery main entry point."""

    def test_attempt_recovery_returns_bool(self) -> None:
        """attempt_recovery returns boolean indicating success/failure."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        context = {"last_heartbeat_time": time.time() - 60}

        with patch.object(manager, "_retry_connection", return_value=True):
            result = manager.attempt_recovery(context)

        assert isinstance(result, bool)
        assert result is True

    def test_attempt_recovery_prevents_concurrent(self) -> None:
        """Concurrent recovery attempts are prevented."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        # Simulate recovery in progress
        manager._recovery_in_progress = True

        context = {"last_heartbeat_time": time.time() - 60}
        result = manager.attempt_recovery(context)

        # Should return False, not attempt recovery
        assert result is False

    def test_attempt_recovery_sets_in_progress_flag(self) -> None:
        """attempt_recovery sets _recovery_in_progress flag."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        lifecycle_manager._connection_manager = MagicMock()
        lifecycle_manager._connection_manager.disconnect = MagicMock()
        lifecycle_manager._connection_manager.connect = MagicMock(return_value=True)
        manager = RecoveryManager(lifecycle_manager)

        context = {"last_heartbeat_time": time.time() - 60}

        # Mock _retry_connection to succeed
        with patch.object(manager, "_retry_connection", return_value=True):
            manager.attempt_recovery(context)

        # Flag should be cleared after recovery
        assert manager._recovery_in_progress is False

    def test_attempt_recovery_updates_timestamp(self) -> None:
        """attempt_recovery updates _last_recovery_attempt timestamp."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        context = {"last_heartbeat_time": time.time() - 60}
        before = time.time()

        with patch.object(manager, "_retry_connection", return_value=True):
            manager.attempt_recovery(context)

        assert manager._last_recovery_attempt is not None
        assert manager._last_recovery_attempt >= before


@pytest.mark.unit
class TestRetryConnection:
    """Test _retry_connection method."""

    def test_retry_connection_returns_bool(self) -> None:
        """_retry_connection returns boolean indicating success/failure."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        conn_mgr = MagicMock()
        conn_mgr.disconnect = MagicMock()
        conn_mgr.connect = MagicMock(return_value=True)
        lifecycle_manager._connection_manager = conn_mgr

        manager = RecoveryManager(lifecycle_manager)

        with patch("time.sleep"):
            result = manager._retry_connection()

        assert isinstance(result, bool)

    def test_retry_connection_success_first_attempt(self) -> None:
        """_retry_connection returns True on successful first attempt."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        conn_mgr = MagicMock()
        conn_mgr.disconnect = MagicMock()
        conn_mgr.connect = MagicMock(return_value=True)
        lifecycle_manager._connection_manager = conn_mgr

        manager = RecoveryManager(lifecycle_manager)

        with patch("time.sleep"):  # Speed up test
            result = manager._retry_connection()

        assert result is True
        conn_mgr.disconnect.assert_called_once()
        conn_mgr.connect.assert_called_once()

    def test_retry_connection_uses_exponential_backoff(self) -> None:
        """_retry_connection uses exponential backoff between retries."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        conn_mgr = MagicMock()
        conn_mgr.disconnect = MagicMock()
        # Fail twice, succeed on third
        conn_mgr.connect = MagicMock(
            side_effect=[Exception("fail1"), Exception("fail2"), True]
        )
        lifecycle_manager._connection_manager = conn_mgr

        manager = RecoveryManager(lifecycle_manager, max_connection_retries=3)

        sleep_calls: list = []
        with patch("time.sleep", side_effect=lambda x: sleep_calls.append(x)):
            result = manager._retry_connection()

        assert result is True
        assert len(sleep_calls) == 2  # Two sleeps before third attempt
        # Backoff: 1.0 * 2^0 = 1.0, 1.0 * 2^1 = 2.0 (plus jitter)
        assert sleep_calls[0] >= 1.0
        assert sleep_calls[1] >= 2.0

    def test_retry_connection_respects_max_retries(self) -> None:
        """_retry_connection stops after max_connection_retries."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        conn_mgr = MagicMock()
        conn_mgr.disconnect = MagicMock()
        conn_mgr.connect = MagicMock(side_effect=Exception("connection failed"))
        lifecycle_manager._connection_manager = conn_mgr

        manager = RecoveryManager(lifecycle_manager, max_connection_retries=3)

        with patch("time.sleep"):
            result = manager._retry_connection()

        assert result is False
        # Called once per attempt
        assert conn_mgr.connect.call_count == 3

    def test_retry_connection_returns_false_when_connection_manager_none(self) -> None:
        """_retry_connection returns False when ConnectionManager is None."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        lifecycle_manager._connection_manager = None  # No connection manager

        manager = RecoveryManager(lifecycle_manager)

        result = manager._retry_connection()

        assert result is False


@pytest.mark.unit
class TestRelaunchMT5:
    """Test _relaunch_mt5 method."""

    def test_relaunch_mt5_returns_bool(self) -> None:
        """_relaunch_mt5 returns boolean indicating success/failure."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        lifecycle_manager.ensure_mt5_running = MagicMock(return_value=MagicMock())

        manager = RecoveryManager(lifecycle_manager)

        with patch("time.sleep"):
            result = manager._relaunch_mt5()

        assert isinstance(result, bool)
        assert result is True

    def test_relaunch_mt5_calls_ensure_mt5_running(self) -> None:
        """_relaunch_mt5 uses LifecycleManager.ensure_mt5_running()."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        lifecycle_manager.ensure_mt5_running = MagicMock(return_value=MagicMock())

        manager = RecoveryManager(lifecycle_manager)

        with patch("time.sleep"):
            result = manager._relaunch_mt5()

        assert result is True
        lifecycle_manager.ensure_mt5_running.assert_called()

    def test_relaunch_mt5_handles_failure(self) -> None:
        """_relaunch_mt5 returns False on failure."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        lifecycle_manager.ensure_mt5_running = MagicMock(
            side_effect=Exception("MT5 launch failed")
        )

        manager = RecoveryManager(lifecycle_manager)

        with patch("time.sleep"):
            result = manager._relaunch_mt5()

        assert result is False


@pytest.mark.unit
class TestRetryAfterRelaunch:
    """Test _retry_after_relaunch method."""

    def test_retry_after_relaunch_returns_bool(self) -> None:
        """_retry_after_relaunch returns boolean indicating success/failure."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        conn_mgr = MagicMock()
        conn_mgr.connect = MagicMock(return_value=True)
        lifecycle_manager._connection_manager = conn_mgr

        manager = RecoveryManager(lifecycle_manager)

        with patch("time.sleep"):
            result = manager._retry_after_relaunch()

        assert isinstance(result, bool)

    def test_retry_after_relaunch_success(self) -> None:
        """_retry_after_relaunch returns True on success."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        conn_mgr = MagicMock()
        conn_mgr.connect = MagicMock(return_value=True)
        lifecycle_manager._connection_manager = conn_mgr

        manager = RecoveryManager(lifecycle_manager)

        with patch("time.sleep"):
            result = manager._retry_after_relaunch()

        assert result is True

    def test_retry_after_relaunch_returns_false_when_connection_manager_none(
        self,
    ) -> None:
        """_retry_after_relaunch returns False when ConnectionManager is None."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        lifecycle_manager._connection_manager = None

        manager = RecoveryManager(lifecycle_manager)

        result = manager._retry_after_relaunch()

        assert result is False

    def test_retry_after_relaunch_uses_fewer_retries(self) -> None:
        """_retry_after_relaunch uses half the normal retry count."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        conn_mgr = MagicMock()
        conn_mgr.connect = MagicMock(side_effect=Exception("fail"))
        lifecycle_manager._connection_manager = conn_mgr

        # With max_connection_retries=6, post-relaunch should use 3
        manager = RecoveryManager(lifecycle_manager, max_connection_retries=6)

        with patch("time.sleep"):
            result = manager._retry_after_relaunch()

        assert result is False
        # Should use max(2, 6//2) = 3 retries
        assert conn_mgr.connect.call_count == 3


@pytest.mark.unit
class TestRecoverySequence:
    """Test full recovery sequence flow."""

    def test_recovery_sequence_retry_succeeds(self) -> None:
        """Recovery succeeds on first retry attempt."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        context = {"last_heartbeat_time": time.time() - 60}

        with patch.object(manager, "_retry_connection", return_value=True):
            result = manager.attempt_recovery(context)

        assert result is True
        assert manager._recovery_stats["success"] == 1
        assert manager._recovery_stats["failure"] == 0

    def test_recovery_sequence_retry_fails_relaunch_succeeds(self) -> None:
        """Recovery succeeds after MT5 relaunch."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        context = {"last_heartbeat_time": time.time() - 60}

        with (
            patch.object(manager, "_retry_connection", return_value=False),
            patch.object(manager, "_relaunch_mt5", return_value=True),
            patch.object(manager, "_retry_after_relaunch", return_value=True),
        ):
            result = manager.attempt_recovery(context)

        assert result is True
        assert manager._recovery_stats["success"] == 1

    def test_recovery_sequence_all_fail(self) -> None:
        """Recovery fails when all attempts fail."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        context = {"last_heartbeat_time": time.time() - 60}

        with (
            patch.object(manager, "_retry_connection", return_value=False),
            patch.object(manager, "_relaunch_mt5", return_value=False),
        ):
            result = manager.attempt_recovery(context)

        assert result is False
        assert manager._recovery_stats["failure"] == 1

    def test_recovery_timeout_enforcement(self) -> None:
        """Recovery aborts if timeout exceeded (NFR5)."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager, recovery_timeout=0.05)

        context = {"last_heartbeat_time": time.time() - 60}

        # Track which methods were called
        call_order: list = []

        def slow_retry() -> bool:
            call_order.append("retry_connection")
            time.sleep(0.1)  # Exceeds 0.05s timeout
            return False

        def relaunch() -> bool:
            call_order.append("relaunch_mt5")
            return True

        with (
            patch.object(manager, "_retry_connection", side_effect=slow_retry),
            patch.object(manager, "_relaunch_mt5", side_effect=relaunch),
        ):
            result = manager.attempt_recovery(context)

        # Recovery should fail due to timeout
        assert result is False
        # _retry_connection was called, but relaunch should be skipped due to timeout
        assert "retry_connection" in call_order
        # Relaunch should NOT be called because timeout expired after retry
        assert "relaunch_mt5" not in call_order

    def test_recovery_timeout_check_before_relaunch(self) -> None:
        """Timeout is checked before each recovery step (NFR5)."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        # Very short timeout
        manager = RecoveryManager(lifecycle_manager, recovery_timeout=0.01)

        context = {"last_heartbeat_time": time.time() - 60}

        # First retry fails but takes time
        def slow_first_retry() -> bool:
            time.sleep(0.02)  # Exceed timeout
            return False

        with patch.object(manager, "_retry_connection", side_effect=slow_first_retry):
            with patch.object(manager, "_relaunch_mt5") as mock_relaunch:
                result = manager.attempt_recovery(context)

        # Relaunch should NOT be called because timeout check happens before it
        mock_relaunch.assert_not_called()
        assert result is False


@pytest.mark.unit
class TestRecoveryNotifications:
    """Test recovery notification callbacks."""

    def test_notify_recovery_success(self) -> None:
        """Callbacks are notified on successful recovery."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        callback = MagicMock()
        manager.register_recovery_callback(callback)

        context = {"last_heartbeat_time": time.time() - 60}

        with patch.object(manager, "_retry_connection", return_value=True):
            manager.attempt_recovery(context)

        callback.assert_called_once()
        call_args = callback.call_args
        assert call_args[0][0] is True  # success=True

    def test_notify_recovery_failure(self) -> None:
        """Callbacks are notified on failed recovery."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        callback = MagicMock()
        manager.register_recovery_callback(callback)

        context = {"last_heartbeat_time": time.time() - 60}

        with (
            patch.object(manager, "_retry_connection", return_value=False),
            patch.object(manager, "_relaunch_mt5", return_value=False),
        ):
            manager.attempt_recovery(context)

        callback.assert_called_once()
        call_args = callback.call_args
        assert call_args[0][0] is False  # success=False

    def test_failure_notification_includes_troubleshooting_ac5(self) -> None:
        """Failed recovery includes troubleshooting suggestions (AC#5)."""
        from mt5linux.recovery import TROUBLESHOOTING_STEPS, RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        callback = MagicMock()
        manager.register_recovery_callback(callback)

        context = {"last_heartbeat_time": time.time() - 60}

        with (
            patch.object(manager, "_retry_connection", return_value=False),
            patch.object(manager, "_relaunch_mt5", return_value=False),
        ):
            manager.attempt_recovery(context)

        # Verify callback received troubleshooting info (AC#5)
        callback.assert_called_once()
        call_args = callback.call_args
        success = call_args[0][0]
        notification_context = call_args[0][1]

        assert success is False
        assert "actionable_message" in notification_context
        assert "troubleshooting_steps" in notification_context
        assert "suggested_actions" in notification_context
        assert notification_context["troubleshooting_steps"] == TROUBLESHOOTING_STEPS
        assert len(notification_context["suggested_actions"]) >= 1
        assert "Manual intervention" in notification_context["actionable_message"]

    def test_success_notification_no_troubleshooting(self) -> None:
        """Successful recovery does NOT include troubleshooting suggestions."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        callback = MagicMock()
        manager.register_recovery_callback(callback)

        context = {"last_heartbeat_time": time.time() - 60}

        with patch.object(manager, "_retry_connection", return_value=True):
            manager.attempt_recovery(context)

        callback.assert_called_once()
        call_args = callback.call_args
        success = call_args[0][0]
        notification_context = call_args[0][1]

        assert success is True
        # Success should NOT have troubleshooting keys
        assert "troubleshooting_steps" not in notification_context
        assert "actionable_message" not in notification_context


@pytest.mark.unit
class TestHeartbeatMonitorIntegration:
    """Test integration with HeartbeatMonitor failure callbacks."""

    def test_recovery_callback_signature_matches_heartbeat(self) -> None:
        """attempt_recovery accepts HeartbeatMonitor callback signature."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        # HeartbeatMonitor passes a context dict to failure callbacks
        context = {
            "last_heartbeat_time": time.time() - 60,
            "consecutive_failures": 3,
            "time_since_heartbeat": 60.0,
            "monitoring_start_time": time.time() - 120,
        }

        with patch.object(manager, "_retry_connection", return_value=True):
            # Should not raise
            result = manager.attempt_recovery(context)
            assert result is True

    def test_recovery_triggered_by_heartbeat_failure(self) -> None:
        """RecoveryManager can be triggered by HeartbeatMonitor."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        # Simulate HeartbeatMonitor invoking the callback
        context = {
            "last_heartbeat_time": time.time() - 60,
            "consecutive_failures": 2,
            "time_since_heartbeat": 60.0,
        }

        with patch.object(manager, "_retry_connection", return_value=True):
            result = manager.attempt_recovery(context)

        assert result is True
        assert manager._recovery_stats["success"] == 1

    def test_concurrent_recovery_from_heartbeat(self) -> None:
        """Only one recovery runs even with multiple heartbeat failures."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        context = {"last_heartbeat_time": time.time() - 60}
        results: list = []

        def slow_retry() -> bool:
            time.sleep(0.1)
            return True

        def attempt_in_thread() -> None:
            result = manager.attempt_recovery(context)
            results.append(result)

        with patch.object(manager, "_retry_connection", side_effect=slow_retry):
            threads = [threading.Thread(target=attempt_in_thread) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # Only one recovery should succeed, others should be blocked
        assert results.count(True) == 1
        assert results.count(False) == 2
        assert manager._recovery_stats["success"] == 1


@pytest.mark.unit
class TestLifecycleManagerRecoveryAttribute:
    """Test LifecycleManager has _recovery_manager attribute."""

    def test_lifecycle_manager_has_recovery_manager_attribute(self) -> None:
        """LifecycleManager has _recovery_manager attribute."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        pm = MagicMock(spec=ProcessManager)
        lm = LifecycleManager(pm)

        assert hasattr(lm, "_recovery_manager")
        assert lm._recovery_manager is None  # Initially None


@pytest.mark.unit
class TestMetaTrader5RecoveryIntegration:
    """Test MetaTrader5 integration with RecoveryManager."""

    def test_start_heartbeat_monitoring_creates_recovery_manager(self) -> None:
        """_start_heartbeat_monitoring creates RecoveryManager."""
        # This test verifies the integration in __init__.py
        # We'll use mocks to avoid actual connections
        from mt5linux import MetaTrader5
        from mt5linux.lifecycle import LifecycleManager

        mt5 = MetaTrader5(auto_connect=True)

        # Create a mock lifecycle manager
        mock_lm = MagicMock(spec=LifecycleManager)
        mock_lm._connection_manager = MagicMock()
        mock_lm._heartbeat_monitor = None
        mock_lm._recovery_manager = None
        mt5._lifecycle_manager = mock_lm

        # Call the method
        with (
            patch("mt5linux.monitoring.heartbeat.HeartbeatMonitor"),
            patch("mt5linux.recovery.RecoveryManager") as MockRecovery,
        ):
            mt5._start_heartbeat_monitoring()

            # RecoveryManager should be created
            MockRecovery.assert_called_once_with(mock_lm)

    def test_recovery_callback_registered_with_heartbeat(self) -> None:
        """RecoveryManager.attempt_recovery registered with HeartbeatMonitor."""
        from mt5linux import MetaTrader5
        from mt5linux.lifecycle import LifecycleManager

        mt5 = MetaTrader5(auto_connect=True)

        mock_lm = MagicMock(spec=LifecycleManager)
        mock_lm._connection_manager = MagicMock()
        mock_lm._heartbeat_monitor = None
        mock_lm._recovery_manager = None
        mt5._lifecycle_manager = mock_lm

        mock_heartbeat = MagicMock()
        mock_recovery = MagicMock()

        with (
            patch(
                "mt5linux.monitoring.heartbeat.HeartbeatMonitor",
                return_value=mock_heartbeat,
            ),
            patch("mt5linux.recovery.RecoveryManager", return_value=mock_recovery),
        ):
            mt5._start_heartbeat_monitoring()

            # Callback should be registered
            mock_heartbeat.register_failure_callback.assert_called_once_with(
                mock_recovery.attempt_recovery
            )


@pytest.mark.unit
class TestConnectionStatusWithRecovery:
    """Test connection_status includes recovery information."""

    def test_connection_status_includes_recovery_status(self) -> None:
        """MetaTrader5.connection_status() includes recovery_status."""
        from mt5linux import MetaTrader5
        from mt5linux.lifecycle import LifecycleManager

        mt5 = MetaTrader5(auto_connect=True)

        # Setup mock lifecycle manager with recovery manager
        mock_lm = MagicMock(spec=LifecycleManager)
        mock_lm._connection_manager = MagicMock()
        mock_lm._connection_manager.connection_info = {"connected": True}
        mock_lm._heartbeat_monitor = MagicMock()
        mock_lm._heartbeat_monitor.get_status.return_value = {"is_healthy": True}

        # Add recovery manager
        mock_recovery = MagicMock()
        mock_recovery.get_recovery_status.return_value = {
            "last_recovery_time": None,
            "recovery_in_progress": False,
            "success_count": 0,
            "failure_count": 0,
        }
        mock_lm._recovery_manager = mock_recovery
        mock_lm.get_status.return_value = {
            "monitoring_active": True,
            "current_pid": 1234,
        }

        mt5._lifecycle_manager = mock_lm

        status = mt5.connection_status()

        # Should include recovery_status
        assert "recovery_status" in status
        assert status["recovery_status"]["success_count"] == 0


@pytest.mark.unit
class TestRecoveryStatisticsTracking:
    """Test recovery statistics are properly tracked (NFR14 metrics)."""

    def test_recovery_stats_increment_on_success(self) -> None:
        """success_count increments on successful recovery."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        context = {"last_heartbeat_time": time.time() - 60}

        with patch.object(manager, "_retry_connection", return_value=True):
            manager.attempt_recovery(context)
            manager.attempt_recovery(context)

        assert manager._recovery_stats["success"] == 2
        assert manager._recovery_stats["failure"] == 0

    def test_recovery_stats_increment_on_failure(self) -> None:
        """failure_count increments on failed recovery."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        context = {"last_heartbeat_time": time.time() - 60}

        with (
            patch.object(manager, "_retry_connection", return_value=False),
            patch.object(manager, "_relaunch_mt5", return_value=False),
        ):
            manager.attempt_recovery(context)
            manager.attempt_recovery(context)

        assert manager._recovery_stats["failure"] == 2
        assert manager._recovery_stats["success"] == 0


@pytest.mark.unit
class TestExponentialBackoffTiming:
    """Test exponential backoff timing calculations."""

    def test_backoff_starts_at_base_delay(self) -> None:
        """First attempt uses base delay (1.0s + jitter)."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        # Attempt 0 should give base delay + jitter
        delays = [manager._calculate_backoff(0) for _ in range(100)]

        # All delays should be >= 1.0 and < 1.5 (base + max jitter)
        assert all(d >= 1.0 for d in delays)
        assert all(d < 1.5 for d in delays)

    def test_backoff_doubles_each_attempt(self) -> None:
        """Delay doubles with each attempt (exponential)."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        with patch("random.uniform", return_value=0):  # Remove jitter
            delay0 = manager._calculate_backoff(0)  # 1.0
            delay1 = manager._calculate_backoff(1)  # 2.0
            delay2 = manager._calculate_backoff(2)  # 4.0
            delay3 = manager._calculate_backoff(3)  # 8.0

        assert delay0 == 1.0
        assert delay1 == 2.0
        assert delay2 == 4.0
        assert delay3 == 8.0

    def test_backoff_capped_at_max_delay(self) -> None:
        """Delay is capped at max (10.0s)."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        manager = RecoveryManager(lifecycle_manager)

        with patch("random.uniform", return_value=0):
            delay10 = manager._calculate_backoff(10)  # Would be 1024 without cap

        assert delay10 == 10.0  # RETRY_MAX_DELAY


@pytest.mark.unit
class TestConnectionStateRestoration:
    """Test connection state is properly restored after recovery."""

    def test_disconnect_before_connect(self) -> None:
        """Recovery disconnects before attempting reconnection."""
        from mt5linux.recovery import RecoveryManager

        lifecycle_manager = MagicMock()
        conn_mgr = MagicMock()
        call_order: list = []

        def track_disconnect() -> None:
            call_order.append("disconnect")

        def track_connect() -> bool:
            call_order.append("connect")
            return True

        conn_mgr.disconnect = track_disconnect
        conn_mgr.connect = track_connect
        lifecycle_manager._connection_manager = conn_mgr

        manager = RecoveryManager(lifecycle_manager, max_connection_retries=1)

        with patch("time.sleep"):
            manager._retry_connection()

        assert call_order == ["disconnect", "connect"]
