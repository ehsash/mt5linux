"""Unit tests for mt5linux.monitoring.latency module (Story 4.3)."""

import time
from threading import Thread
from typing import List
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit  # All tests in this module are unit tests


class TestLatencyMeasurement:
    """Tests for LatencyMeasurement dataclass."""

    def test_create_measurement(self) -> None:
        """Test creating a LatencyMeasurement."""
        from mt5linux.monitoring.latency import LatencyMeasurement

        measurement = LatencyMeasurement(
            order_ticket=12345,
            symbol="EURUSD",
            order_type="buy",
            send_timestamp=1000.0,
            execution_timestamp=1000.15,
            latency_ms=150.0,
            is_high_latency=False,
        )
        assert measurement.order_ticket == 12345
        assert measurement.symbol == "EURUSD"
        assert measurement.order_type == "buy"
        assert measurement.send_timestamp == 1000.0
        assert measurement.execution_timestamp == 1000.15
        assert measurement.latency_ms == 150.0
        assert measurement.is_high_latency is False

    def test_frozen_dataclass(self) -> None:
        """Test LatencyMeasurement is immutable."""
        from mt5linux.monitoring.latency import LatencyMeasurement

        measurement = LatencyMeasurement(
            order_ticket=12345,
            symbol="EURUSD",
            order_type="buy",
            send_timestamp=1000.0,
            execution_timestamp=1000.15,
            latency_ms=150.0,
            is_high_latency=False,
        )
        with pytest.raises(AttributeError):
            measurement.latency_ms = 200.0  # type: ignore[misc]

    def test_slots_dataclass(self) -> None:
        """Test LatencyMeasurement uses slots."""
        from mt5linux.monitoring.latency import LatencyMeasurement

        measurement = LatencyMeasurement(
            order_ticket=12345,
            symbol="EURUSD",
            order_type="buy",
            send_timestamp=1000.0,
            execution_timestamp=1000.15,
            latency_ms=150.0,
            is_high_latency=False,
        )
        assert hasattr(measurement, "__slots__") or not hasattr(measurement, "__dict__")


class TestLatencyAlert:
    """Tests for LatencyAlert dataclass."""

    def test_create_alert(self) -> None:
        """Test creating a LatencyAlert."""
        from mt5linux.monitoring.latency import LatencyAlert, LatencyMeasurement

        measurement = LatencyMeasurement(
            order_ticket=12345,
            symbol="EURUSD",
            order_type="buy",
            send_timestamp=1000.0,
            execution_timestamp=1000.25,
            latency_ms=250.0,
            is_high_latency=True,
        )
        alert = LatencyAlert(
            measurement=measurement,
            threshold_ms=200.0,
            alert_timestamp=1000.3,
            message="High latency detected",
        )
        assert alert.measurement is measurement
        assert alert.threshold_ms == 200.0
        assert alert.alert_timestamp == 1000.3
        assert alert.message == "High latency detected"

    def test_frozen_dataclass(self) -> None:
        """Test LatencyAlert is immutable."""
        from mt5linux.monitoring.latency import LatencyAlert, LatencyMeasurement

        measurement = LatencyMeasurement(
            order_ticket=12345,
            symbol="EURUSD",
            order_type="buy",
            send_timestamp=1000.0,
            execution_timestamp=1000.25,
            latency_ms=250.0,
            is_high_latency=True,
        )
        alert = LatencyAlert(
            measurement=measurement,
            threshold_ms=200.0,
            alert_timestamp=1000.3,
            message="High latency detected",
        )
        with pytest.raises(AttributeError):
            alert.threshold_ms = 300.0  # type: ignore[misc]

    def test_slots_dataclass(self) -> None:
        """Test LatencyAlert uses slots."""
        from mt5linux.monitoring.latency import LatencyAlert, LatencyMeasurement

        measurement = LatencyMeasurement(
            order_ticket=12345,
            symbol="EURUSD",
            order_type="buy",
            send_timestamp=1000.0,
            execution_timestamp=1000.25,
            latency_ms=250.0,
            is_high_latency=True,
        )
        alert = LatencyAlert(
            measurement=measurement,
            threshold_ms=200.0,
            alert_timestamp=1000.3,
            message="High latency detected",
        )
        assert hasattr(alert, "__slots__") or not hasattr(alert, "__dict__")


class TestLatencyMonitorInit:
    """Tests for LatencyMonitor initialization."""

    def test_default_initialization(self) -> None:
        """Test LatencyMonitor with default config."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        assert monitor._enabled is True
        assert monitor._threshold_ms == 200.0
        assert monitor._warning_delivery_secs == 5.0

    def test_custom_config(self) -> None:
        """Test LatencyMonitor with custom config."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(
            enabled=False, threshold_ms=500.0, warning_delivery_secs=10.0
        )
        monitor = LatencyMonitor(config=config)
        assert monitor._enabled is False
        assert monitor._threshold_ms == 500.0
        assert monitor._warning_delivery_secs == 10.0

    def test_empty_pending_orders(self) -> None:
        """Test LatencyMonitor starts with empty pending orders."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        assert len(monitor._pending_orders) == 0

    def test_empty_measurements(self) -> None:
        """Test LatencyMonitor starts with empty measurements."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        assert len(monitor._measurements) == 0

    def test_empty_callbacks(self) -> None:
        """Test LatencyMonitor starts with empty callbacks."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        assert len(monitor._high_latency_callbacks) == 0


class TestLatencyMonitorLifecycle:
    """Tests for LatencyMonitor start/stop."""

    def test_start_sets_start_time(self) -> None:
        """Test start() sets start time."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        assert monitor._start_time is None
        monitor.start()
        assert monitor._start_time is not None
        assert monitor._start_time > 0

    def test_stop_resets_state(self) -> None:
        """Test stop() resets start time."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        monitor.start()
        monitor.stop()
        assert monitor._start_time is None

    def test_multiple_start_stop(self) -> None:
        """Test multiple start/stop cycles."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        for _ in range(3):
            monitor.start()
            assert monitor._start_time is not None
            monitor.stop()
            assert monitor._start_time is None

    def test_is_running_property(self) -> None:
        """Test is_running property reflects state."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        assert monitor.is_running is False
        monitor.start()
        assert monitor.is_running is True
        monitor.stop()
        assert monitor.is_running is False


class TestLatencyRecording:
    """Tests for order sent/executed recording."""

    def test_record_order_sent(self) -> None:
        """Test recording an order sent."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        monitor.start()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        assert 12345 in monitor._pending_orders
        symbol, order_type, timestamp = monitor._pending_orders[12345]
        assert symbol == "EURUSD"
        assert order_type == "buy"
        assert timestamp > 0

    def test_record_order_executed_returns_measurement(self) -> None:
        """Test recording order execution returns measurement."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        monitor.start()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        measurement = monitor.record_order_executed(12345)
        assert measurement is not None
        assert measurement.order_ticket == 12345
        assert measurement.symbol == "EURUSD"
        assert measurement.order_type == "buy"
        assert measurement.latency_ms >= 0

    def test_record_order_executed_removes_from_pending(self) -> None:
        """Test order is removed from pending after execution."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        monitor.start()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        assert 12345 in monitor._pending_orders
        monitor.record_order_executed(12345)
        assert 12345 not in monitor._pending_orders

    def test_record_order_executed_adds_to_measurements(self) -> None:
        """Test measurement is added to history."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        monitor.start()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        monitor.record_order_executed(12345)
        assert len(monitor._measurements) == 1

    def test_record_order_executed_unknown_order(self) -> None:
        """Test recording execution for unknown order returns None."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        monitor.start()
        measurement = monitor.record_order_executed(99999)
        assert measurement is None

    def test_multiple_orders(self) -> None:
        """Test recording multiple orders."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        monitor.start()
        monitor.record_order_sent(111, "EURUSD", "buy")
        monitor.record_order_sent(222, "GBPUSD", "sell")
        monitor.record_order_sent(333, "USDJPY", "buy")

        assert len(monitor._pending_orders) == 3

        monitor.record_order_executed(222)
        assert len(monitor._pending_orders) == 2
        assert len(monitor._measurements) == 1

        monitor.record_order_executed(111)
        monitor.record_order_executed(333)
        assert len(monitor._pending_orders) == 0
        assert len(monitor._measurements) == 3


class TestLatencyCalculation:
    """Tests for latency calculation accuracy."""

    def test_latency_calculation_positive(self) -> None:
        """Test latency is calculated correctly."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        monitor.start()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        # Small sleep to ensure measurable latency
        time.sleep(0.01)  # 10ms
        measurement = monitor.record_order_executed(12345)
        assert measurement is not None
        assert measurement.latency_ms >= 10  # At least 10ms
        assert measurement.latency_ms < 100  # But not too long

    def test_latency_timestamps_correct(self) -> None:
        """Test timestamps are recorded correctly."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        monitor.start()

        before_send = time.time()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        after_send = time.time()

        time.sleep(0.01)

        before_exec = time.time()
        measurement = monitor.record_order_executed(12345)
        after_exec = time.time()

        assert measurement is not None
        assert before_send <= measurement.send_timestamp <= after_send
        assert before_exec <= measurement.execution_timestamp <= after_exec


class TestHighLatencyDetection:
    """Tests for high latency detection."""

    def test_normal_latency_not_flagged(self) -> None:
        """Test normal latency is not flagged as high."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)  # 1 second threshold
        monitor = LatencyMonitor(config=config)
        monitor.start()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        time.sleep(0.01)  # 10ms - well under threshold
        measurement = monitor.record_order_executed(12345)
        assert measurement is not None
        assert measurement.is_high_latency is False

    def test_high_latency_flagged(self) -> None:
        """Test high latency is flagged."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=5.0)  # 5ms threshold
        monitor = LatencyMonitor(config=config)
        monitor.start()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        time.sleep(0.02)  # 20ms - over threshold
        measurement = monitor.record_order_executed(12345)
        assert measurement is not None
        assert measurement.is_high_latency is True

    def test_high_latency_increments_count(self) -> None:
        """Test high latency increments counter."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=5.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()
        assert monitor._high_latency_count == 0

        monitor.record_order_sent(12345, "EURUSD", "buy")
        time.sleep(0.02)
        monitor.record_order_executed(12345)
        assert monitor._high_latency_count == 1


class TestLatencyCallbacks:
    """Tests for notification callback system."""

    def test_register_callback(self) -> None:
        """Test registering a callback."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()

        def callback(alert):
            pass

        monitor.on_high_latency(callback)
        assert callback in monitor._high_latency_callbacks

    def test_unregister_callback(self) -> None:
        """Test unregistering a callback."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()

        def callback(alert):
            pass

        monitor.on_high_latency(callback)
        monitor.unregister_high_latency_callback(callback)
        assert callback not in monitor._high_latency_callbacks

    def test_callback_invoked_on_high_latency(self) -> None:
        """Test callback is invoked on high latency."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=5.0)
        monitor = LatencyMonitor(config=config)

        alerts: List = []

        def callback(alert):
            alerts.append(alert)

        monitor.on_high_latency(callback)
        monitor.start()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        time.sleep(0.02)
        monitor.record_order_executed(12345)

        assert len(alerts) == 1
        assert alerts[0].measurement.order_ticket == 12345
        assert alerts[0].threshold_ms == 5.0

    def test_callback_not_invoked_on_normal_latency(self) -> None:
        """Test callback is not invoked on normal latency."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)  # 1 second threshold
        monitor = LatencyMonitor(config=config)

        alerts: List = []

        def callback(alert):
            alerts.append(alert)

        monitor.on_high_latency(callback)
        monitor.start()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        time.sleep(0.01)
        monitor.record_order_executed(12345)

        assert len(alerts) == 0

    def test_callback_error_handled(self) -> None:
        """Test callback errors are handled gracefully."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=5.0)
        monitor = LatencyMonitor(config=config)

        def bad_callback(alert):
            raise ValueError("Test error")

        good_callback = MagicMock()

        monitor.on_high_latency(bad_callback)
        monitor.on_high_latency(good_callback)
        monitor.start()
        monitor.record_order_sent(12345, "EURUSD", "buy")
        time.sleep(0.02)
        # Should not raise, should continue to good_callback
        monitor.record_order_executed(12345)

        # Good callback should still be called
        good_callback.assert_called_once()

    def test_unregister_nonexistent_callback(self) -> None:
        """Test unregistering a callback that wasn't registered."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()

        def callback(alert):
            pass

        # Should not raise
        monitor.unregister_high_latency_callback(callback)


class TestLatencyStatistics:
    """Tests for statistics API methods."""

    def test_get_status_empty(self) -> None:
        """Test get_status with no measurements."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        status = monitor.get_status()

        assert status["enabled"] is True
        assert status["threshold_ms"] == 200.0
        assert status["measurement_count"] == 0
        assert status["average_latency_ms"] is None
        assert status["max_latency_ms"] is None
        assert status["min_latency_ms"] is None
        assert status["high_latency_count"] == 0

    def test_get_status_with_measurements(self) -> None:
        """Test get_status with measurements."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        # Create several measurements
        for i in range(3):
            monitor.record_order_sent(i, "EURUSD", "buy")
            time.sleep(0.01)
            monitor.record_order_executed(i)

        status = monitor.get_status()
        assert status["measurement_count"] == 3
        assert status["average_latency_ms"] is not None
        assert status["average_latency_ms"] > 0
        assert status["max_latency_ms"] is not None
        assert status["min_latency_ms"] is not None

    def test_get_average_latency_empty(self) -> None:
        """Test get_average_latency with no measurements."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        assert monitor.get_average_latency() is None

    def test_get_average_latency_with_data(self) -> None:
        """Test get_average_latency with measurements."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        monitor.record_order_sent(1, "EURUSD", "buy")
        time.sleep(0.01)
        monitor.record_order_executed(1)

        avg = monitor.get_average_latency()
        assert avg is not None
        assert avg > 0

    def test_get_latency_percentile_empty(self) -> None:
        """Test get_latency_percentile with no measurements."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        assert monitor.get_latency_percentile(50.0) is None

    def test_get_latency_percentile_50th(self) -> None:
        """Test get_latency_percentile for 50th percentile (median)."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        for i in range(5):
            monitor.record_order_sent(i, "EURUSD", "buy")
            time.sleep(0.01)
            monitor.record_order_executed(i)

        p50 = monitor.get_latency_percentile(50.0)
        assert p50 is not None
        assert p50 > 0

    def test_get_latency_percentile_99th(self) -> None:
        """Test get_latency_percentile for 99th percentile."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        for i in range(10):
            monitor.record_order_sent(i, "EURUSD", "buy")
            time.sleep(0.01)
            monitor.record_order_executed(i)

        p99 = monitor.get_latency_percentile(99.0)
        p50 = monitor.get_latency_percentile(50.0)
        assert p99 is not None
        assert p50 is not None
        assert p99 >= p50  # 99th should be >= 50th

    def test_get_recent_measurements_empty(self) -> None:
        """Test get_recent_measurements with no data."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        recent = monitor.get_recent_measurements(10)
        assert recent == []

    def test_get_recent_measurements_limited(self) -> None:
        """Test get_recent_measurements returns limited count."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        for i in range(10):
            monitor.record_order_sent(i, "EURUSD", "buy")
            monitor.record_order_executed(i)

        recent = monitor.get_recent_measurements(3)
        assert len(recent) == 3

    def test_get_recent_measurements_all(self) -> None:
        """Test get_recent_measurements returns all when count > total."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        for i in range(5):
            monitor.record_order_sent(i, "EURUSD", "buy")
            monitor.record_order_executed(i)

        recent = monitor.get_recent_measurements(100)
        assert len(recent) == 5


class TestLatencyMonitorDisabled:
    """Tests for disabled state."""

    def test_disabled_does_not_record(self) -> None:
        """Test disabled monitor does not record measurements."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(enabled=False)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        monitor.record_order_sent(12345, "EURUSD", "buy")
        # Disabled should skip recording
        assert len(monitor._pending_orders) == 0

    def test_disabled_returns_none_on_execute(self) -> None:
        """Test disabled monitor returns None on execute."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(enabled=False)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        measurement = monitor.record_order_executed(12345)
        assert measurement is None

    def test_disabled_status_shows_enabled_false(self) -> None:
        """Test get_status shows enabled=False when disabled."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(enabled=False)
        monitor = LatencyMonitor(config=config)
        status = monitor.get_status()
        assert status["enabled"] is False

    def test_is_enabled_property(self) -> None:
        """Test is_enabled property."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        enabled_monitor = LatencyMonitor(config=LatencyConfig(enabled=True))
        disabled_monitor = LatencyMonitor(config=LatencyConfig(enabled=False))

        assert enabled_monitor.is_enabled is True
        assert disabled_monitor.is_enabled is False


class TestLatencyMonitorThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_record_orders(self) -> None:
        """Test concurrent order recording is thread-safe."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        def record_orders(start_id: int):
            for i in range(10):
                order_id = start_id + i
                monitor.record_order_sent(order_id, "EURUSD", "buy")
                monitor.record_order_executed(order_id)

        threads = [Thread(target=record_orders, args=(i * 100,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(monitor._measurements) == 50
        assert len(monitor._pending_orders) == 0


class TestLatencyMonitorMemoryManagement:
    """Tests for memory management methods (H1, H2 fixes)."""

    def test_clear_measurements_empties_list(self) -> None:
        """Test clear_measurements removes all measurements."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        # Create some measurements
        for i in range(5):
            monitor.record_order_sent(i, "EURUSD", "buy")
            monitor.record_order_executed(i)

        assert monitor.get_status()["measurement_count"] == 5

        cleared = monitor.clear_measurements()

        assert cleared == 5
        assert monitor.get_status()["measurement_count"] == 0

    def test_clear_measurements_resets_high_latency_count(self) -> None:
        """Test clear_measurements resets high latency counter."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=5.0)  # Very low threshold
        monitor = LatencyMonitor(config=config)
        monitor.start()

        # Create high latency measurement
        monitor.record_order_sent(1, "EURUSD", "buy")
        time.sleep(0.02)  # 20ms > 5ms threshold
        monitor.record_order_executed(1)

        assert monitor.get_status()["high_latency_count"] == 1

        monitor.clear_measurements()

        assert monitor.get_status()["high_latency_count"] == 0

    def test_clear_measurements_empty_returns_zero(self) -> None:
        """Test clear_measurements on empty monitor returns 0."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        cleared = monitor.clear_measurements()
        assert cleared == 0

    def test_clear_pending_orders_empties_dict(self) -> None:
        """Test clear_pending_orders removes all pending orders."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        monitor.start()

        # Create pending orders that won't be executed
        monitor.record_order_sent(111, "EURUSD", "buy")
        monitor.record_order_sent(222, "GBPUSD", "sell")
        monitor.record_order_sent(333, "USDJPY", "buy")

        assert monitor.get_status()["pending_orders_count"] == 3

        cleared = monitor.clear_pending_orders()

        assert cleared == 3
        assert monitor.get_status()["pending_orders_count"] == 0

    def test_clear_pending_orders_empty_returns_zero(self) -> None:
        """Test clear_pending_orders on empty monitor returns 0."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        cleared = monitor.clear_pending_orders()
        assert cleared == 0


class TestLatencyMonitorInputValidation:
    """Tests for input validation (M1, M2 fixes)."""

    def test_get_latency_percentile_rejects_negative(self) -> None:
        """Test get_latency_percentile rejects negative percentile."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        with pytest.raises(ValueError, match="percentile must be between 0 and 100"):
            monitor.get_latency_percentile(-10.0)

    def test_get_latency_percentile_rejects_over_100(self) -> None:
        """Test get_latency_percentile rejects percentile > 100."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        with pytest.raises(ValueError, match="percentile must be between 0 and 100"):
            monitor.get_latency_percentile(150.0)

    def test_get_latency_percentile_accepts_boundary_values(self) -> None:
        """Test get_latency_percentile accepts 0 and 100."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        monitor.record_order_sent(1, "EURUSD", "buy")
        monitor.record_order_executed(1)

        # Should not raise
        p0 = monitor.get_latency_percentile(0.0)
        p100 = monitor.get_latency_percentile(100.0)

        assert p0 is not None
        assert p100 is not None
        assert p0 <= p100

    def test_get_recent_measurements_rejects_negative(self) -> None:
        """Test get_recent_measurements rejects negative count."""
        from mt5linux.monitoring.latency import LatencyMonitor

        monitor = LatencyMonitor()
        with pytest.raises(ValueError, match="count must be non-negative"):
            monitor.get_recent_measurements(-5)

    def test_get_recent_measurements_accepts_zero(self) -> None:
        """Test get_recent_measurements with count=0 returns empty list."""
        from mt5linux.config import LatencyConfig
        from mt5linux.monitoring.latency import LatencyMonitor

        config = LatencyConfig(threshold_ms=1000.0)
        monitor = LatencyMonitor(config=config)
        monitor.start()

        monitor.record_order_sent(1, "EURUSD", "buy")
        monitor.record_order_executed(1)

        recent = monitor.get_recent_measurements(0)
        assert recent == []
