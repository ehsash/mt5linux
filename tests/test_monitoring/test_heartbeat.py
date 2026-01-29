"""Unit tests for HeartbeatMonitor class.

Tests the heartbeat monitoring functionality including:
- Initialization with configuration
- Heartbeat success/failure detection
- Failure threshold timing (NFR12: 45 seconds)
- Callback system for failure notifications
- Status reporting
- Thread lifecycle (start/stop)
- LifecycleManager integration
"""

import threading
import time
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Task 2: HeartbeatMonitor Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestHeartbeatMonitorInit:
    """Test HeartbeatMonitor initialization."""

    def test_init_with_defaults(self) -> None:
        """HeartbeatMonitor should initialize with default values."""
        from mt5linux.monitoring.heartbeat import (
            DEFAULT_FAILURE_THRESHOLD,
            DEFAULT_HEARTBEAT_INTERVAL,
            HeartbeatMonitor,
        )

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        assert monitor._connection_manager is mock_conn_mgr
        assert monitor._heartbeat_interval == DEFAULT_HEARTBEAT_INTERVAL
        assert monitor._failure_threshold == DEFAULT_FAILURE_THRESHOLD
        assert monitor._last_heartbeat_time is None
        assert monitor._consecutive_failures == 0
        assert monitor._failure_callbacks == []
        assert monitor._monitor_thread is None
        assert isinstance(monitor._stop_event, threading.Event)
        # Accept Lock or RLock (RLock needed to avoid deadlock in get_status)
        assert isinstance(
            monitor._lock, (type(threading.Lock()), type(threading.RLock()))
        )

    def test_init_with_custom_interval(self) -> None:
        """HeartbeatMonitor should accept custom heartbeat interval."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=15.0)

        assert monitor._heartbeat_interval == 15.0

    def test_init_with_custom_threshold(self) -> None:
        """HeartbeatMonitor should accept custom failure threshold."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=60.0)

        assert monitor._failure_threshold == 60.0

    def test_init_creates_lock(self) -> None:
        """HeartbeatMonitor should create a threading lock."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        assert hasattr(monitor, "_lock")
        # Accept Lock or RLock (RLock needed to avoid deadlock in get_status)
        assert isinstance(
            monitor._lock, (type(threading.Lock()), type(threading.RLock()))
        )


# =============================================================================
# Task 3: Heartbeat Check Tests
# =============================================================================


@pytest.mark.unit
class TestHeartbeatCheck:
    """Test HeartbeatMonitor._perform_heartbeat() method."""

    def test_heartbeat_success_updates_last_time(self) -> None:
        """Successful heartbeat should update last_heartbeat_time."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True

        monitor = HeartbeatMonitor(mock_conn_mgr)
        before = time.time()
        result = monitor._perform_heartbeat()
        after = time.time()

        assert result is True
        assert monitor._last_heartbeat_time is not None
        assert before <= monitor._last_heartbeat_time <= after

    def test_heartbeat_success_resets_failures(self) -> None:
        """Successful heartbeat should reset consecutive failures."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True

        monitor = HeartbeatMonitor(mock_conn_mgr)
        monitor._consecutive_failures = 3  # Simulate previous failures

        result = monitor._perform_heartbeat()

        assert result is True
        assert monitor._consecutive_failures == 0

    def test_heartbeat_failure_increments_counter(self) -> None:
        """Failed heartbeat should increment consecutive failures."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = False

        monitor = HeartbeatMonitor(mock_conn_mgr)

        result = monitor._perform_heartbeat()

        assert result is False
        assert monitor._consecutive_failures == 1

    def test_heartbeat_exception_increments_counter(self) -> None:
        """Heartbeat exception should increment consecutive failures."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.side_effect = Exception("Connection error")

        monitor = HeartbeatMonitor(mock_conn_mgr)

        result = monitor._perform_heartbeat()

        assert result is False
        assert monitor._consecutive_failures == 1

    def test_multiple_failures_accumulate(self) -> None:
        """Multiple consecutive failures should accumulate."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = False

        monitor = HeartbeatMonitor(mock_conn_mgr)

        monitor._perform_heartbeat()
        monitor._perform_heartbeat()
        monitor._perform_heartbeat()

        assert monitor._consecutive_failures == 3


# =============================================================================
# Task 4: Start/Stop Tests
# =============================================================================


@pytest.mark.unit
class TestStartStop:
    """Test HeartbeatMonitor start/stop methods."""

    def test_start_creates_daemon_thread(self) -> None:
        """start() should create a daemon monitoring thread."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True

        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=0.1)

        try:
            monitor.start()

            assert monitor._monitor_thread is not None
            assert monitor._monitor_thread.daemon is True
            assert monitor._monitor_thread.is_alive()
        finally:
            monitor.stop()

    def test_start_clears_stop_event(self) -> None:
        """start() should clear stop event before starting."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=0.1)

        monitor._stop_event.set()  # Simulate previous stop

        try:
            monitor.start()
            assert not monitor._stop_event.is_set()
        finally:
            monitor.stop()

    def test_start_does_nothing_if_already_running(self) -> None:
        """start() should do nothing if monitoring already active."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=0.1)

        try:
            monitor.start()
            first_thread = monitor._monitor_thread

            monitor.start()  # Second start

            assert monitor._monitor_thread is first_thread
        finally:
            monitor.stop()

    def test_stop_sets_stop_event(self) -> None:
        """stop() should set stop event."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=0.1)

        monitor.start()
        monitor.stop()

        assert monitor._stop_event.is_set()

    def test_stop_waits_for_thread(self) -> None:
        """stop() should wait for thread to terminate."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=0.1)

        monitor.start()
        monitor.stop()

        # Thread should be terminated after stop
        assert monitor._monitor_thread is None or not monitor._monitor_thread.is_alive()

    def test_stop_does_nothing_if_not_running(self) -> None:
        """stop() should do nothing if not monitoring."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        # Should not raise
        monitor.stop()


# =============================================================================
# Task 5: Failure Detection Tests
# =============================================================================


@pytest.mark.unit
class TestFailureDetection:
    """Test failure detection and threshold timing."""

    def test_failure_detected_when_threshold_exceeded(self) -> None:
        """Failure should be detected when threshold exceeded."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(
            mock_conn_mgr,
            heartbeat_interval=10.0,
            failure_threshold=25.0,
        )

        # Simulate: heartbeat at time 0, now check at time 30 (exceeds 25s)
        monitor._last_heartbeat_time = time.time() - 30.0
        callback_called = []

        def on_failure(ctx: dict) -> None:
            callback_called.append(ctx)

        monitor.register_failure_callback(on_failure)
        monitor._check_failure_threshold()

        assert len(callback_called) == 1

    def test_no_failure_when_within_threshold(self) -> None:
        """No failure should be detected when within threshold."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(
            mock_conn_mgr,
            heartbeat_interval=10.0,
            failure_threshold=45.0,
        )

        # Heartbeat 10 seconds ago - within threshold
        monitor._last_heartbeat_time = time.time() - 10.0
        callback_called = []

        def on_failure(ctx: dict) -> None:
            callback_called.append(ctx)

        monitor.register_failure_callback(on_failure)
        monitor._check_failure_threshold()

        assert len(callback_called) == 0

    def test_nfr12_45_second_threshold(self) -> None:
        """NFR12: Failure must be detected within 45 seconds."""
        from mt5linux.monitoring.heartbeat import DEFAULT_FAILURE_THRESHOLD

        # Verify default threshold is 45 seconds per NFR12
        assert DEFAULT_FAILURE_THRESHOLD == 45.0

    def test_failure_context_includes_details(self) -> None:
        """Failure callback context should include details."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=10.0)

        monitor._last_heartbeat_time = time.time() - 20.0
        monitor._consecutive_failures = 3
        received_context = {}

        def on_failure(ctx: dict) -> None:
            received_context.update(ctx)

        monitor.register_failure_callback(on_failure)
        monitor._check_failure_threshold()

        assert "last_heartbeat_time" in received_context
        assert "consecutive_failures" in received_context
        assert "time_since_heartbeat" in received_context

    def test_is_healthy_true_when_within_threshold(self) -> None:
        """is_healthy should be True when within threshold."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=45.0)
        monitor._last_heartbeat_time = time.time() - 10.0

        assert monitor.is_healthy is True

    def test_is_healthy_false_when_threshold_exceeded(self) -> None:
        """is_healthy should be False when threshold exceeded."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=45.0)
        monitor._last_heartbeat_time = time.time() - 60.0

        assert monitor.is_healthy is False

    def test_is_healthy_false_when_no_heartbeat_yet(self) -> None:
        """is_healthy should be False when no heartbeat recorded yet."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        assert monitor.is_healthy is False


# =============================================================================
# Task 6: Callback System Tests
# =============================================================================


@pytest.mark.unit
class TestCallbackSystem:
    """Test callback registration and invocation."""

    def test_register_callback(self) -> None:
        """register_failure_callback should add callback to list."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        def callback(ctx: dict) -> None:
            pass

        monitor.register_failure_callback(callback)

        assert callback in monitor._failure_callbacks

    def test_unregister_callback(self) -> None:
        """unregister_failure_callback should remove callback from list."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        def callback(ctx: dict) -> None:
            pass

        monitor.register_failure_callback(callback)
        monitor.unregister_failure_callback(callback)

        assert callback not in monitor._failure_callbacks

    def test_callback_invoked_on_failure(self) -> None:
        """Callbacks should be invoked on failure detection."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=10.0)
        monitor._last_heartbeat_time = time.time() - 20.0

        call_count = [0]

        def callback(ctx: dict) -> None:
            call_count[0] += 1

        monitor.register_failure_callback(callback)
        monitor._check_failure_threshold()

        assert call_count[0] == 1

    def test_multiple_callbacks_invoked(self) -> None:
        """All registered callbacks should be invoked."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=10.0)
        monitor._last_heartbeat_time = time.time() - 20.0

        calls = []

        def callback1(ctx: dict) -> None:
            calls.append("cb1")

        def callback2(ctx: dict) -> None:
            calls.append("cb2")

        monitor.register_failure_callback(callback1)
        monitor.register_failure_callback(callback2)
        monitor._check_failure_threshold()

        assert "cb1" in calls
        assert "cb2" in calls

    def test_callback_error_does_not_propagate(self) -> None:
        """Callback errors should be caught and logged, not propagated."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=10.0)
        monitor._last_heartbeat_time = time.time() - 20.0

        def bad_callback(ctx: dict) -> None:
            raise Exception("Callback error")

        good_called = [False]

        def good_callback(ctx: dict) -> None:
            good_called[0] = True

        monitor.register_failure_callback(bad_callback)
        monitor.register_failure_callback(good_callback)

        # Should not raise
        monitor._check_failure_threshold()

        # Good callback should still be called
        assert good_called[0] is True


# =============================================================================
# Task 7: Status Reporting Tests
# =============================================================================


@pytest.mark.unit
class TestStatusReporting:
    """Test get_status() method."""

    def test_get_status_includes_monitoring_active(self) -> None:
        """get_status should include monitoring_active field."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=0.1)

        # Not started
        status = monitor.get_status()
        assert status["monitoring_active"] is False

        # Started
        try:
            monitor.start()
            status = monitor.get_status()
            assert status["monitoring_active"] is True
        finally:
            monitor.stop()

    def test_get_status_includes_last_heartbeat(self) -> None:
        """get_status should include last_heartbeat timestamp."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        # No heartbeat yet
        status = monitor.get_status()
        assert status["last_heartbeat"] is None

        # After heartbeat
        monitor._last_heartbeat_time = time.time()
        status = monitor.get_status()
        assert status["last_heartbeat"] is not None

    def test_get_status_includes_consecutive_failures(self) -> None:
        """get_status should include consecutive_failures count."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        monitor._consecutive_failures = 5
        status = monitor.get_status()

        assert status["consecutive_failures"] == 5

    def test_get_status_includes_is_healthy(self) -> None:
        """get_status should include is_healthy flag."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=45.0)

        # Healthy
        monitor._last_heartbeat_time = time.time()
        status = monitor.get_status()
        assert status["is_healthy"] is True

        # Unhealthy
        monitor._last_heartbeat_time = time.time() - 60.0
        status = monitor.get_status()
        assert status["is_healthy"] is False

    def test_get_status_thread_safe(self) -> None:
        """get_status should be thread-safe."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        # Should not deadlock when called from multiple threads
        results = []

        def get_status_task() -> None:
            for _ in range(10):
                status = monitor.get_status()
                results.append(status)

        threads = [threading.Thread(target=get_status_task) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50


# =============================================================================
# Task 8: LifecycleManager Integration Tests
# =============================================================================


@pytest.mark.unit
class TestLifecycleIntegration:
    """Test LifecycleManager integration with HeartbeatMonitor."""

    def test_lifecycle_manager_has_heartbeat_monitor_attribute(self) -> None:
        """LifecycleManager should have _heartbeat_monitor attribute."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        mock_pm = MagicMock(spec=ProcessManager)
        lm = LifecycleManager(mock_pm)

        assert hasattr(lm, "_heartbeat_monitor")
        assert lm._heartbeat_monitor is None  # Initially None

    def test_lifecycle_get_status_includes_heartbeat_status(self) -> None:
        """LifecycleManager.get_status() should include heartbeat_status."""
        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor
        from mt5linux.process_manager import ProcessManager

        mock_pm = MagicMock(spec=ProcessManager)
        lm = LifecycleManager(mock_pm)

        # No heartbeat monitor
        status = lm.get_status()
        assert "heartbeat_status" in status or status.get("heartbeat_status") is None

        # With heartbeat monitor
        mock_conn_mgr = MagicMock()
        lm._heartbeat_monitor = HeartbeatMonitor(mock_conn_mgr)
        lm._heartbeat_monitor._last_heartbeat_time = time.time()

        status = lm.get_status()
        assert "heartbeat_status" in status


# =============================================================================
# Review Fix: Debouncing Tests (H1)
# =============================================================================


@pytest.mark.unit
class TestFailureDebouncing:
    """Test that failure callbacks are only invoked once per failure episode."""

    def test_callbacks_invoked_only_once_per_failure_episode(self) -> None:
        """Callbacks should only be invoked once until recovery."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=10.0)

        # Simulate monitoring started 20 seconds ago
        monitor._monitoring_start_time = time.time() - 20.0
        monitor._last_heartbeat_time = time.time() - 20.0  # Last heartbeat 20s ago

        call_count = [0]

        def on_failure(ctx: dict) -> None:
            call_count[0] += 1

        monitor.register_failure_callback(on_failure)

        # First check should trigger callback
        monitor._check_failure_threshold()
        assert call_count[0] == 1

        # Subsequent checks should NOT trigger callback (debounced)
        monitor._check_failure_threshold()
        monitor._check_failure_threshold()
        monitor._check_failure_threshold()
        assert call_count[0] == 1  # Still just 1

    def test_callback_reinvoked_after_recovery(self) -> None:
        """Callbacks should be invoked again after recovery and new failure."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True

        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=10.0)
        monitor._monitoring_start_time = time.time() - 20.0
        monitor._last_heartbeat_time = time.time() - 20.0

        call_count = [0]

        def on_failure(ctx: dict) -> None:
            call_count[0] += 1

        monitor.register_failure_callback(on_failure)

        # First failure
        monitor._check_failure_threshold()
        assert call_count[0] == 1

        # Recovery (successful heartbeat resets _failure_notified)
        monitor._perform_heartbeat()
        assert monitor._failure_notified is False

        # New failure (simulate time passing)
        monitor._last_heartbeat_time = time.time() - 20.0
        monitor._check_failure_threshold()
        assert call_count[0] == 2  # Callback invoked again

    def test_failure_notified_flag_in_status(self) -> None:
        """get_status() should include failure_notified flag."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        status = monitor.get_status()
        assert "failure_notified" in status
        assert status["failure_notified"] is False


# =============================================================================
# Review Fix: Initial Timing Edge Case Tests (M2)
# =============================================================================


@pytest.mark.unit
class TestInitialTimingEdgeCase:
    """Test failure detection when first heartbeat fails."""

    def test_failure_detected_when_no_successful_heartbeat(self) -> None:
        """Failure should be detected even if no heartbeat ever succeeded."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = False

        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=10.0)

        # Simulate: monitoring started 20 seconds ago, no successful heartbeat
        monitor._monitoring_start_time = time.time() - 20.0
        monitor._last_heartbeat_time = None  # No successful heartbeat yet

        callback_called = []

        def on_failure(ctx: dict) -> None:
            callback_called.append(ctx)

        monitor.register_failure_callback(on_failure)
        monitor._check_failure_threshold()

        assert len(callback_called) == 1
        assert callback_called[0]["last_heartbeat_time"] is None
        assert "monitoring_start_time" in callback_called[0]

    def test_monitoring_start_time_set_on_start(self) -> None:
        """start() should set _monitoring_start_time."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True

        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=0.1)

        assert monitor._monitoring_start_time is None

        try:
            before = time.time()
            monitor.start()
            after = time.time()

            assert monitor._monitoring_start_time is not None
            assert before <= monitor._monitoring_start_time <= after
        finally:
            monitor.stop()

    def test_monitoring_start_time_in_status(self) -> None:
        """get_status() should include monitoring_start_time."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        status = monitor.get_status()
        assert "monitoring_start_time" in status


# =============================================================================
# Review Fix: Duplicate Callback Prevention Tests (M4)
# =============================================================================


@pytest.mark.unit
class TestDuplicateCallbackPrevention:
    """Test that duplicate callback registrations are prevented."""

    def test_duplicate_registration_ignored(self) -> None:
        """Registering same callback twice should only add it once."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        def callback(ctx: dict) -> None:
            pass

        monitor.register_failure_callback(callback)
        monitor.register_failure_callback(callback)  # Duplicate

        assert len(monitor._failure_callbacks) == 1

    def test_duplicate_callback_invoked_once(self) -> None:
        """Even if registered twice, callback should only be called once."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, failure_threshold=10.0)
        monitor._monitoring_start_time = time.time() - 20.0
        monitor._last_heartbeat_time = time.time() - 20.0

        call_count = [0]

        def callback(ctx: dict) -> None:
            call_count[0] += 1

        monitor.register_failure_callback(callback)
        monitor.register_failure_callback(callback)  # Attempt duplicate

        monitor._check_failure_threshold()

        assert call_count[0] == 1


# =============================================================================
# Review Fix: Start After Stop Race Condition Test (L1)
# =============================================================================


@pytest.mark.unit
class TestStartStopRaceCondition:
    """Test start/stop race conditions."""

    def test_start_after_stop_creates_new_thread(self) -> None:
        """start() after stop() should create a new monitoring thread."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True

        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=0.1)

        try:
            # First start/stop cycle
            monitor.start()
            first_thread = monitor._monitor_thread
            assert first_thread is not None
            assert first_thread.is_alive()

            monitor.stop()

            # Second start should create new thread
            monitor.start()
            second_thread = monitor._monitor_thread
            assert second_thread is not None
            assert second_thread.is_alive()
            assert second_thread is not first_thread

        finally:
            monitor.stop()

    def test_failure_notified_reset_on_start(self) -> None:
        """start() should reset _failure_notified flag."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=0.1)
        monitor._failure_notified = True  # Simulate previous failure

        try:
            monitor.start()
            assert monitor._failure_notified is False
        finally:
            monitor.stop()


# =============================================================================
# Story 4.1: Heartbeat System - Configuration Integration
# =============================================================================


@pytest.mark.unit
class TestHeartbeatConfig:
    """Test HeartbeatConfig dataclass (Task 2)."""

    def test_heartbeat_config_defaults(self) -> None:
        """HeartbeatConfig should have correct defaults."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig

        config = HeartbeatConfig()
        assert config.interval == 30.0
        assert config.failure_threshold == 45.0

    def test_heartbeat_config_custom_values(self) -> None:
        """HeartbeatConfig should accept custom values."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig

        config = HeartbeatConfig(interval=15.0, failure_threshold=30.0)
        assert config.interval == 15.0
        assert config.failure_threshold == 30.0

    def test_heartbeat_config_is_frozen(self) -> None:
        """HeartbeatConfig should be immutable (frozen=True)."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig

        config = HeartbeatConfig()
        with pytest.raises(AttributeError):
            config.interval = 10.0  # type: ignore

    def test_heartbeat_config_validation_interval_less_than_threshold(self) -> None:
        """HeartbeatConfig should validate interval < threshold."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig

        # This should raise ValueError
        with pytest.raises(ValueError, match="must be less than"):
            HeartbeatConfig(interval=50.0, failure_threshold=30.0)

    def test_heartbeat_config_validation_equal_values(self) -> None:
        """HeartbeatConfig should reject equal interval and threshold."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig

        with pytest.raises(ValueError, match="must be less than"):
            HeartbeatConfig(interval=30.0, failure_threshold=30.0)


@pytest.mark.unit
class TestMonitoringConfig:
    """Test MonitoringConfig in config.py (Task 1)."""

    def test_monitoring_config_defaults(self) -> None:
        """MonitoringConfig should have correct defaults."""
        from mt5linux.config import MonitoringConfig

        config = MonitoringConfig()
        assert config.heartbeat_interval == 30.0
        assert config.heartbeat_failure_threshold == 45.0

    def test_monitoring_config_custom_values(self) -> None:
        """MonitoringConfig should accept custom values."""
        from mt5linux.config import MonitoringConfig

        config = MonitoringConfig(
            heartbeat_interval=20.0, heartbeat_failure_threshold=40.0
        )
        assert config.heartbeat_interval == 20.0
        assert config.heartbeat_failure_threshold == 40.0

    def test_config_includes_monitoring_section(self) -> None:
        """Config should include monitoring section."""
        from mt5linux.config import Config

        config = Config()
        assert hasattr(config, "monitoring")

    def test_config_to_dict_includes_monitoring(self) -> None:
        """Config.to_dict() should include monitoring section."""
        from mt5linux.config import Config

        config = Config()
        config_dict = config.to_dict()
        assert "monitoring" in config_dict
        assert "heartbeat_interval" in config_dict["monitoring"]
        assert "heartbeat_failure_threshold" in config_dict["monitoring"]

    def test_config_from_dict_loads_monitoring(self) -> None:
        """Config.from_dict() should load monitoring section."""
        from mt5linux.config import Config

        data = {
            "monitoring": {
                "heartbeat_interval": 20.0,
                "heartbeat_failure_threshold": 35.0,
            }
        }
        config = Config.from_dict(data)
        assert config.monitoring.heartbeat_interval == 20.0
        assert config.monitoring.heartbeat_failure_threshold == 35.0


@pytest.mark.unit
class TestHeartbeatConfigIntegration:
    """Test HeartbeatMonitor config integration (Task 3)."""

    def test_init_with_heartbeat_config(self) -> None:
        """HeartbeatMonitor should accept HeartbeatConfig."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig, HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        config = HeartbeatConfig(interval=20.0, failure_threshold=35.0)
        monitor = HeartbeatMonitor(mock_conn_mgr, config=config)

        assert monitor._heartbeat_interval == 20.0
        assert monitor._failure_threshold == 35.0

    def test_init_explicit_params_override_config(self) -> None:
        """Explicit params should override HeartbeatConfig."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig, HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        config = HeartbeatConfig(interval=20.0, failure_threshold=35.0)
        monitor = HeartbeatMonitor(
            mock_conn_mgr,
            heartbeat_interval=15.0,
            failure_threshold=25.0,
            config=config,
        )

        # Explicit params take precedence
        assert monitor._heartbeat_interval == 15.0
        assert monitor._failure_threshold == 25.0

    def test_backward_compatibility_without_config(self) -> None:
        """HeartbeatMonitor should work without HeartbeatConfig (backward compat)."""
        from mt5linux.monitoring.heartbeat import (
            DEFAULT_FAILURE_THRESHOLD,
            DEFAULT_HEARTBEAT_INTERVAL,
            HeartbeatMonitor,
        )

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        assert monitor._heartbeat_interval == DEFAULT_HEARTBEAT_INTERVAL
        assert monitor._failure_threshold == DEFAULT_FAILURE_THRESHOLD


# =============================================================================
# Story 4.1: NFR9 Variance Tracking (Task 4)
# =============================================================================


@pytest.mark.unit
class TestNFR9VarianceTracking:
    """Test NFR9 variance tracking (<1 second variance requirement)."""

    def test_heartbeat_count_tracking(self) -> None:
        """HeartbeatMonitor should track heartbeat count."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True
        monitor = HeartbeatMonitor(mock_conn_mgr)

        # Perform heartbeats
        monitor._perform_heartbeat()
        monitor._perform_heartbeat()
        monitor._perform_heartbeat()

        assert monitor._heartbeat_count == 3

    def test_variance_tracking_attributes_exist(self) -> None:
        """HeartbeatMonitor should have variance tracking attributes."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        assert hasattr(monitor, "_heartbeat_count")
        assert hasattr(monitor, "_total_variance")
        assert hasattr(monitor, "_previous_heartbeat_time")

    def test_get_status_includes_variance_metrics(self) -> None:
        """get_status() should include variance metrics."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True
        monitor = HeartbeatMonitor(mock_conn_mgr)

        # Perform heartbeats to generate metrics
        monitor._perform_heartbeat()
        time.sleep(0.05)
        monitor._perform_heartbeat()

        status = monitor.get_status()
        assert "heartbeat_count" in status
        assert "average_variance" in status

    def test_get_heartbeat_count_method(self) -> None:
        """get_heartbeat_count() should return total heartbeats."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True
        monitor = HeartbeatMonitor(mock_conn_mgr)

        assert monitor.get_heartbeat_count() == 0

        monitor._perform_heartbeat()
        monitor._perform_heartbeat()

        assert monitor.get_heartbeat_count() == 2

    def test_get_average_interval_method(self) -> None:
        """get_average_interval() should return average actual interval."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True
        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=0.1)

        # First heartbeat doesn't have a previous time
        monitor._perform_heartbeat()
        time.sleep(0.05)
        monitor._perform_heartbeat()
        time.sleep(0.05)
        monitor._perform_heartbeat()

        avg_interval = monitor.get_average_interval()
        # Should be around 0.05 seconds
        assert avg_interval is not None
        assert 0.03 < avg_interval < 0.1


# =============================================================================
# Story 4.1: Callback Hooks (Task 5)
# =============================================================================


@pytest.mark.unit
class TestHeartbeatFailureInfo:
    """Test HeartbeatFailureInfo dataclass (Task 5)."""

    def test_heartbeat_failure_info_creation(self) -> None:
        """HeartbeatFailureInfo should be creatable with all fields."""
        from mt5linux.monitoring.heartbeat import HeartbeatFailureInfo

        info = HeartbeatFailureInfo(
            last_heartbeat_time=1000.0,
            consecutive_failures=3,
            time_since_heartbeat=50.0,
            monitoring_start_time=900.0,
            failure_timestamp=1050.0,
        )

        assert info.last_heartbeat_time == 1000.0
        assert info.consecutive_failures == 3
        assert info.time_since_heartbeat == 50.0
        assert info.monitoring_start_time == 900.0
        assert info.failure_timestamp == 1050.0

    def test_heartbeat_failure_info_is_frozen(self) -> None:
        """HeartbeatFailureInfo should be immutable."""
        from mt5linux.monitoring.heartbeat import HeartbeatFailureInfo

        info = HeartbeatFailureInfo(
            last_heartbeat_time=1000.0,
            consecutive_failures=3,
            time_since_heartbeat=50.0,
            monitoring_start_time=900.0,
            failure_timestamp=1050.0,
        )

        with pytest.raises(AttributeError):
            info.consecutive_failures = 5  # type: ignore


@pytest.mark.unit
class TestHeartbeatCallbackHooks:
    """Test callback hook methods (Task 5)."""

    def test_on_heartbeat_failure_registers_callback(self) -> None:
        """on_heartbeat_failure() should register typed callback."""
        from mt5linux.monitoring.heartbeat import (
            HeartbeatFailureInfo,
            HeartbeatMonitor,
        )

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        received_info: list = []

        def callback(info: HeartbeatFailureInfo) -> None:
            received_info.append(info)

        monitor.on_heartbeat_failure(callback)

        # Should have registered a callback
        assert len(monitor._failure_callbacks) == 1

    def test_on_heartbeat_failure_provides_typed_info(self) -> None:
        """on_heartbeat_failure() callback should receive HeartbeatFailureInfo."""
        from mt5linux.monitoring.heartbeat import (
            HeartbeatFailureInfo,
            HeartbeatMonitor,
        )

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = False
        monitor = HeartbeatMonitor(
            mock_conn_mgr, heartbeat_interval=0.01, failure_threshold=0.02
        )

        received_info: list = []

        def callback(info: HeartbeatFailureInfo) -> None:
            received_info.append(info)

        monitor.on_heartbeat_failure(callback)

        try:
            monitor.start()
            # Wait for failure detection
            time.sleep(0.1)
        finally:
            monitor.stop()

        assert len(received_info) > 0
        assert isinstance(received_info[0], HeartbeatFailureInfo)
        assert received_info[0].consecutive_failures > 0

    def test_on_heartbeat_success_registers_callback(self) -> None:
        """on_heartbeat_success() should register success callback."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        callback_count = [0]

        def callback() -> None:
            callback_count[0] += 1

        monitor.on_heartbeat_success(callback)

        # Should have registered
        assert len(monitor._success_callbacks) == 1


# =============================================================================
# Story 4.1: Status API Methods (Task 7)
# =============================================================================


@pytest.mark.unit
class TestHeartbeatStatusAPI:
    """Test new status API methods (Task 7)."""

    def test_get_uptime_before_start(self) -> None:
        """get_uptime() should return None before monitoring starts."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        assert monitor.get_uptime() is None

    def test_get_uptime_after_start(self) -> None:
        """get_uptime() should return time since monitoring started."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True
        monitor = HeartbeatMonitor(mock_conn_mgr, heartbeat_interval=1.0)

        try:
            monitor.start()
            time.sleep(0.1)
            uptime = monitor.get_uptime()
            assert uptime is not None
            assert uptime >= 0.1
        finally:
            monitor.stop()

    def test_get_status_extended_metrics(self) -> None:
        """get_status() should include extended metrics from Story 4.1."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True
        monitor = HeartbeatMonitor(mock_conn_mgr)

        monitor._perform_heartbeat()
        status = monitor.get_status()

        # New metrics from Story 4.1
        assert "heartbeat_count" in status
        assert "average_variance" in status
        assert "uptime" in status


# =============================================================================
# Code Review Fixes: Validation and Edge Cases
# =============================================================================


@pytest.mark.unit
class TestHeartbeatConfigValidation:
    """Test HeartbeatConfig validation for invalid values (Review Fix M1)."""

    def test_negative_interval_raises_value_error(self) -> None:
        """HeartbeatConfig should reject negative interval."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig

        with pytest.raises(ValueError, match="must be positive"):
            HeartbeatConfig(interval=-1.0, failure_threshold=45.0)

    def test_zero_interval_raises_value_error(self) -> None:
        """HeartbeatConfig should reject zero interval."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig

        with pytest.raises(ValueError, match="must be positive"):
            HeartbeatConfig(interval=0.0, failure_threshold=45.0)

    def test_negative_threshold_raises_value_error(self) -> None:
        """HeartbeatConfig should reject negative failure_threshold."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig

        with pytest.raises(ValueError, match="must be positive"):
            HeartbeatConfig(interval=30.0, failure_threshold=-1.0)

    def test_zero_threshold_raises_value_error(self) -> None:
        """HeartbeatConfig should reject zero failure_threshold."""
        from mt5linux.monitoring.heartbeat import HeartbeatConfig

        with pytest.raises(ValueError, match="must be positive"):
            HeartbeatConfig(interval=30.0, failure_threshold=0.0)


@pytest.mark.unit
class TestMonitoringConfigValidation:
    """Test MonitoringConfig validation for invalid values (Review Fix M1)."""

    def test_negative_interval_raises_value_error(self) -> None:
        """MonitoringConfig should reject negative heartbeat_interval."""
        from mt5linux.config import MonitoringConfig

        with pytest.raises(ValueError, match="must be positive"):
            MonitoringConfig(heartbeat_interval=-1.0, heartbeat_failure_threshold=45.0)

    def test_zero_interval_raises_value_error(self) -> None:
        """MonitoringConfig should reject zero heartbeat_interval."""
        from mt5linux.config import MonitoringConfig

        with pytest.raises(ValueError, match="must be positive"):
            MonitoringConfig(heartbeat_interval=0.0, heartbeat_failure_threshold=45.0)

    def test_negative_threshold_raises_value_error(self) -> None:
        """MonitoringConfig should reject negative heartbeat_failure_threshold."""
        from mt5linux.config import MonitoringConfig

        with pytest.raises(ValueError, match="must be positive"):
            MonitoringConfig(heartbeat_interval=30.0, heartbeat_failure_threshold=-1.0)

    def test_zero_threshold_raises_value_error(self) -> None:
        """MonitoringConfig should reject zero heartbeat_failure_threshold."""
        from mt5linux.config import MonitoringConfig

        with pytest.raises(ValueError, match="must be positive"):
            MonitoringConfig(heartbeat_interval=30.0, heartbeat_failure_threshold=0.0)

    def test_interval_gte_threshold_raises_value_error(self) -> None:
        """MonitoringConfig should reject interval >= threshold."""
        from mt5linux.config import MonitoringConfig

        with pytest.raises(ValueError, match="must be less than"):
            MonitoringConfig(heartbeat_interval=50.0, heartbeat_failure_threshold=30.0)


@pytest.mark.unit
class TestUnregisterSuccessCallback:
    """Test unregister_success_callback method (Review Fix M2)."""

    def test_unregister_success_callback_removes_callback(self) -> None:
        """unregister_success_callback should remove callback from list."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        def callback() -> None:
            pass

        monitor.on_heartbeat_success(callback)
        assert callback in monitor._success_callbacks

        monitor.unregister_success_callback(callback)
        assert callback not in monitor._success_callbacks

    def test_unregister_nonexistent_callback_no_error(self) -> None:
        """unregister_success_callback should not error for unknown callback."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        monitor = HeartbeatMonitor(mock_conn_mgr)

        def callback() -> None:
            pass

        # Should not raise
        monitor.unregister_success_callback(callback)


@pytest.mark.unit
class TestSuccessCallbackErrorHandling:
    """Test success callback error handling (Review Fix L1)."""

    def test_success_callback_error_does_not_propagate(self) -> None:
        """Success callback errors should be caught and logged, not propagated."""
        from mt5linux.monitoring.heartbeat import HeartbeatMonitor

        mock_conn_mgr = MagicMock()
        mock_conn_mgr.verify_connection.return_value = True
        monitor = HeartbeatMonitor(mock_conn_mgr)

        def bad_callback() -> None:
            raise Exception("Callback error")

        good_called = [False]

        def good_callback() -> None:
            good_called[0] = True

        monitor.on_heartbeat_success(bad_callback)
        monitor.on_heartbeat_success(good_callback)

        # Should not raise
        monitor._perform_heartbeat()

        # Good callback should still be called
        assert good_called[0] is True
