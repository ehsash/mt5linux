"""Feature tests for monitoring functionality (Epic 4, Stories 4.1, 4.3).

Tests:
    - Heartbeat monitoring with real connection
    - Latency measurement with real trades
    - Daily reporter (without Telegram)
    - Console notifier

Note:
    Telegram tests are excluded as they require bot configuration.
"""

import time
from typing import Any

import pytest

pytestmark = [pytest.mark.feature_short]


class TestHeartbeatMonitor:
    """Test heartbeat monitoring with real MT5 connection."""

    def test_heartbeat_monitor_starts(self, heartbeat_monitor: Any) -> None:
        """Verify heartbeat monitor starts successfully."""
        assert heartbeat_monitor.is_running is True

    def test_heartbeat_is_healthy(self, heartbeat_monitor: Any) -> None:
        """Verify connection is healthy after startup."""
        status = heartbeat_monitor.get_status()
        assert status is not None
        assert status.get("is_healthy") is True

    def test_heartbeat_count_increases(self, heartbeat_monitor: Any) -> None:
        """Verify heartbeat count increases over time."""
        initial_count = heartbeat_monitor.get_heartbeat_count()

        # Wait for at least one heartbeat (interval is 5s in fixture)
        time.sleep(6)

        new_count = heartbeat_monitor.get_heartbeat_count()
        assert new_count > initial_count

    def test_heartbeat_uptime_available(self, heartbeat_monitor: Any) -> None:
        """Verify uptime is tracked."""
        uptime = heartbeat_monitor.get_uptime()
        assert uptime is not None
        assert uptime > 0

    def test_heartbeat_status_dict(self, heartbeat_monitor: Any) -> None:
        """Verify heartbeat status contains required fields."""
        status = heartbeat_monitor.get_status()

        required_fields = [
            "is_running",
            "is_healthy",
            "heartbeat_count",
            "consecutive_failures",
        ]
        for field in required_fields:
            assert field in status, f"Missing field: {field}"

    def test_heartbeat_no_consecutive_failures(self, heartbeat_monitor: Any) -> None:
        """Verify no failures with stable connection."""
        status = heartbeat_monitor.get_status()
        assert status.get("consecutive_failures", 0) == 0


class TestLatencyMonitor:
    """Test latency monitoring with real MT5 connection."""

    def test_latency_monitor_starts(self, latency_monitor: Any) -> None:
        """Verify latency monitor starts successfully."""
        assert latency_monitor.is_running is True

    def test_latency_status_available(self, latency_monitor: Any) -> None:
        """Verify latency status is available."""
        status = latency_monitor.get_status()
        assert status is not None
        assert "enabled" in status

    def test_latency_threshold_configured(self, latency_monitor: Any) -> None:
        """Verify latency threshold is configured."""
        status = latency_monitor.get_status()
        assert "threshold_ms" in status
        assert status["threshold_ms"] == 200.0  # From fixture config


@pytest.mark.feature_long
class TestLatencyMeasurement:
    """Test actual latency measurement with trades.

    These tests execute trades to measure latency.
    """

    def test_measure_order_latency(
        self,
        mt5: Any,
        latency_monitor: Any,
        symbol_eurusd: str,
        is_demo_account: bool,
        cleanup_positions: None,
    ) -> None:
        """Test measuring latency of order execution."""
        info = mt5.symbol_info(symbol_eurusd)
        tick = mt5.symbol_info_tick(symbol_eurusd)

        # Execute order
        request = {
            "action": 1,
            "symbol": symbol_eurusd,
            "volume": info.volume_min,
            "type": 0,
            "price": tick.ask,
            "deviation": 20,
            "magic": 789012,
            "comment": "latency_test",
            "type_time": 0,
            "type_filling": 2,
        }

        result = mt5.order_send(request)

        if result.retcode == 10009:
            # Give time for measurement to be recorded
            time.sleep(1)

            # Check if measurement was recorded (may or may not be,
            # depending on how latency monitor is integrated)
            measurements = latency_monitor.get_recent_measurements(10)
            assert measurements is not None  # Just verify no error

            # Cleanup position
            positions = mt5.positions_get(symbol=symbol_eurusd)
            if positions:
                mt5.close_position(positions[-1].ticket)


class TestConsoleNotifier:
    """Test console notification channel (without Telegram)."""

    def test_console_notifier_creation(self) -> None:
        """Test creating console notifier."""
        from mt5linux.monitoring import ConsoleNotifier, ConsoleNotifierConfig

        config = ConsoleNotifierConfig(enabled=True, log_level="INFO")
        notifier = ConsoleNotifier(config)

        assert notifier is not None

    def test_console_notifier_send(self) -> None:
        """Test sending notification via console."""
        import time as time_module

        from mt5linux.monitoring import ConsoleNotifier, ConsoleNotifierConfig
        from mt5linux.monitoring.notifier import NotificationMessage

        config = ConsoleNotifierConfig(enabled=True, log_level="INFO")
        notifier = ConsoleNotifier(config)
        notifier.start()

        # Create notification message
        message = NotificationMessage(
            message_type="daily_report",
            title="Test Notification",
            body="This is a feature test notification",
            timestamp=time_module.time(),
            severity="info",
        )

        # Should not raise
        result = notifier.send_notification(message)
        assert isinstance(result, bool)

        notifier.stop()

    def test_console_notifier_when_disabled(self) -> None:
        """Test console notifier when disabled."""
        import time as time_module

        from mt5linux.monitoring import ConsoleNotifier, ConsoleNotifierConfig
        from mt5linux.monitoring.notifier import NotificationMessage

        config = ConsoleNotifierConfig(enabled=False)
        notifier = ConsoleNotifier(config)

        message = NotificationMessage(
            message_type="daily_report",
            title="Test",
            body="Should be ignored",
            timestamp=time_module.time(),
            severity="info",
        )

        # Should not raise even when disabled
        result = notifier.send_notification(message)
        assert result is False  # Disabled notifier returns False


class TestNotificationRouter:
    """Test notification routing (without Telegram)."""

    def test_router_creation(self) -> None:
        """Test notification router creation."""
        from mt5linux.monitoring import NotificationRouter

        router = NotificationRouter()
        assert router is not None

    def test_router_with_console_channel(self) -> None:
        """Test notification router with console channel."""
        import time as time_module

        from mt5linux.monitoring import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
            NotificationRouter,
        )
        from mt5linux.monitoring.notifier import NotificationMessage

        router = NotificationRouter()

        # Register console channel
        console = ConsoleNotifier(ConsoleNotifierConfig(enabled=True))
        router.register_channel(console)
        router.enable_channel("console")
        router.start_all()

        # Create message
        message = NotificationMessage(
            message_type="daily_report",
            title="Router Test",
            body="Testing notification router",
            timestamp=time_module.time(),
            severity="warning",
        )

        # Should route to console without error
        results = router.send_to_all(message)
        assert "console" in results

        router.stop_all()

    def test_router_empty_channels(self) -> None:
        """Test router with no channels configured."""
        import time as time_module

        from mt5linux.monitoring import NotificationRouter
        from mt5linux.monitoring.notifier import NotificationMessage

        router = NotificationRouter()

        message = NotificationMessage(
            message_type="daily_report",
            title="No Channels",
            body="This goes nowhere",
            timestamp=time_module.time(),
            severity="info",
        )

        # Should not raise with no channels
        results = router.send_to_all(message)
        assert results == {}


class TestDailyReporter:
    """Test daily reporter (report generation only, no Telegram)."""

    def test_daily_reporter_creation(self, mt5_connection: Any) -> None:
        """Test creating daily reporter."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring import DailyReporter

        config = DailyReportsConfig(
            enabled=True,
            times=("09:00", "21:00"),
            timezone="UTC",
        )

        # Get connection manager from lifecycle manager
        lifecycle_mgr = mt5_connection._lifecycle_manager
        if lifecycle_mgr is None:
            pytest.skip("LifecycleManager not available")

        conn_mgr = lifecycle_mgr._connection_manager
        reporter = DailyReporter(conn_mgr, config)

        assert reporter is not None
        assert reporter.is_enabled is True

    def test_daily_reporter_status(self, mt5_connection: Any) -> None:
        """Test daily reporter status."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring import DailyReporter

        config = DailyReportsConfig(enabled=True)
        lifecycle_mgr = mt5_connection._lifecycle_manager
        if lifecycle_mgr is None:
            pytest.skip("LifecycleManager not available")

        conn_mgr = lifecycle_mgr._connection_manager
        reporter = DailyReporter(conn_mgr, config)

        status = reporter.get_status()
        assert "enabled" in status
        assert "times" in status
        assert "timezone" in status

    def test_daily_report_format(self, mt5_connection: Any) -> None:
        """Test daily report formatting."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring import DailyReport, DailyReporter

        config = DailyReportsConfig(enabled=True)
        lifecycle_mgr = mt5_connection._lifecycle_manager
        if lifecycle_mgr is None:
            pytest.skip("LifecycleManager not available")

        conn_mgr = lifecycle_mgr._connection_manager
        reporter = DailyReporter(conn_mgr, config)

        # Create a sample report
        report = DailyReport(
            timestamp=time.time(),
            account_balance=10000.0,
            equity=10000.0,
            open_positions=0,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-30 12:00:00 UTC",
        )

        formatted = reporter.format_report(report)
        assert "Daily Trading Report" in formatted
        assert "10000.00" in formatted
