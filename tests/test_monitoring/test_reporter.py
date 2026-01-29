"""Unit tests for mt5linux.monitoring.reporter module (Story 4.2)."""

import time
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


class TestDailyReporterInit:
    """Tests for DailyReporter initialization (Task 2)."""

    def test_init_with_connection_manager(self) -> None:
        """Test DailyReporter initializes with connection manager."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)
        assert reporter._connection_manager is mock_cm

    def test_init_with_config(self) -> None:
        """Test DailyReporter accepts optional config."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(enabled=True, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)
        assert reporter._enabled is True
        assert reporter._times == ("10:00",)
        assert reporter._timezone == "UTC"

    def test_init_uses_defaults_when_no_config(self) -> None:
        """Test DailyReporter uses defaults when config not provided."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)
        assert reporter._enabled is False
        assert reporter._times == ("09:00", "21:00")
        assert reporter._timezone == "UTC"

    def test_init_creates_scheduler(self) -> None:
        """Test DailyReporter creates APScheduler instance."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)
        assert reporter._scheduler is not None

    def test_init_creates_empty_callbacks_list(self) -> None:
        """Test DailyReporter initializes with empty callbacks list."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)
        assert reporter._report_callbacks == []

    def test_init_creates_rlock(self) -> None:
        """Test DailyReporter creates RLock for thread safety."""
        from threading import RLock

        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)
        assert isinstance(reporter._lock, type(RLock()))


class TestDailyReporterLifecycle:
    """Tests for DailyReporter start/stop lifecycle (Task 2)."""

    def test_start_starts_scheduler_when_enabled(self) -> None:
        """Test start() starts the scheduler when enabled."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(enabled=True, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)
        reporter.start()
        assert reporter._scheduler.running is True
        reporter.stop()

    def test_start_does_not_start_scheduler_when_disabled(self) -> None:
        """Test start() does not start scheduler when disabled."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(enabled=False, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)
        reporter.start()
        assert reporter._scheduler.running is False

    def test_stop_stops_scheduler(self) -> None:
        """Test stop() stops the scheduler."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(enabled=True, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)
        reporter.start()
        assert reporter._scheduler.running is True
        reporter.stop()
        assert reporter._scheduler.running is False

    def test_stop_when_not_started(self) -> None:
        """Test stop() handles case when not started."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)
        # Should not raise
        reporter.stop()


class TestDailyReportDataclass:
    """Tests for DailyReport dataclass (Task 4)."""

    def test_daily_report_frozen(self) -> None:
        """Test DailyReport is frozen (immutable)."""
        from mt5linux.monitoring.reporter import DailyReport

        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10500.0,
            open_positions=2,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-29 10:00:00",
        )
        with pytest.raises(FrozenInstanceError):
            report.timestamp = 0.0  # type: ignore[misc]

    def test_daily_report_slots(self) -> None:
        """Test DailyReport uses slots."""
        from mt5linux.monitoring.reporter import DailyReport

        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10500.0,
            open_positions=2,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-29 10:00:00",
        )
        assert hasattr(report, "__slots__") or not hasattr(report, "__dict__")

    def test_daily_report_all_fields(self) -> None:
        """Test DailyReport contains all required fields."""
        from mt5linux.monitoring.reporter import DailyReport, PositionInfo

        pos = PositionInfo(symbol="EURUSD", volume=0.1, profit=50.0, type="buy")
        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10500.0,
            open_positions=1,
            position_details=(pos,),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={"is_healthy": True},
            report_time="2026-01-29 10:00:00",
        )
        assert report.timestamp == 1234567890.0
        assert report.account_balance == 10000.0
        assert report.equity == 10500.0
        assert report.open_positions == 1
        assert len(report.position_details) == 1
        assert report.uptime_seconds == 3600.0
        assert report.connection_status == "connected"
        assert report.heartbeat_status == {"is_healthy": True}
        assert report.report_time == "2026-01-29 10:00:00"


class TestPositionInfoDataclass:
    """Tests for PositionInfo dataclass (Task 4)."""

    def test_position_info_frozen(self) -> None:
        """Test PositionInfo is frozen (immutable)."""
        from mt5linux.monitoring.reporter import PositionInfo

        pos = PositionInfo(symbol="EURUSD", volume=0.1, profit=50.0, type="buy")
        with pytest.raises(FrozenInstanceError):
            pos.symbol = "GBPUSD"  # type: ignore[misc]

    def test_position_info_slots(self) -> None:
        """Test PositionInfo uses slots."""
        from mt5linux.monitoring.reporter import PositionInfo

        pos = PositionInfo(symbol="EURUSD", volume=0.1, profit=50.0, type="buy")
        assert hasattr(pos, "__slots__") or not hasattr(pos, "__dict__")

    def test_position_info_fields(self) -> None:
        """Test PositionInfo contains all fields."""
        from mt5linux.monitoring.reporter import PositionInfo

        pos = PositionInfo(symbol="EURUSD", volume=0.1, profit=-25.5, type="sell")
        assert pos.symbol == "EURUSD"
        assert pos.volume == 0.1
        assert pos.profit == -25.5
        assert pos.type == "sell"


class TestDailyReporterCallbacks:
    """Tests for DailyReporter callback system (Task 6)."""

    def test_register_report_callback(self) -> None:
        """Test on_report_generated registers callback."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)

        callback = MagicMock()
        reporter.on_report_generated(callback)
        assert callback in reporter._report_callbacks

    def test_unregister_report_callback(self) -> None:
        """Test unregister_report_callback removes callback."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)

        callback = MagicMock()
        reporter.on_report_generated(callback)
        reporter.unregister_report_callback(callback)
        assert callback not in reporter._report_callbacks

    def test_unregister_nonexistent_callback(self) -> None:
        """Test unregister_report_callback handles nonexistent callback."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)

        callback = MagicMock()
        # Should not raise
        reporter.unregister_report_callback(callback)


class TestDailyReporterScheduling:
    """Tests for DailyReporter scheduling (Task 3)."""

    def test_jobs_added_for_each_time(self) -> None:
        """Test scheduler adds job for each configured time."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(
            enabled=True, times=("09:00", "12:00", "18:00"), timezone="UTC"
        )
        reporter = DailyReporter(mock_cm, config=config)
        reporter.start()
        jobs = reporter._scheduler.get_jobs()
        assert len(jobs) == 3
        reporter.stop()

    def test_job_ids_match_times(self) -> None:
        """Test job IDs are based on configured times."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(
            enabled=True, times=("09:00", "21:00"), timezone="UTC"
        )
        reporter = DailyReporter(mock_cm, config=config)
        reporter.start()
        job_ids = [job.id for job in reporter._scheduler.get_jobs()]
        assert "daily_report_09:00" in job_ids
        assert "daily_report_21:00" in job_ids
        reporter.stop()


class TestDailyReporterStatus:
    """Tests for DailyReporter status API (Task 8)."""

    def test_get_status_returns_dict(self) -> None:
        """Test get_status() returns dictionary with status info."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)
        status = reporter.get_status()
        assert isinstance(status, dict)

    def test_get_status_includes_enabled(self) -> None:
        """Test get_status() includes enabled field."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(enabled=True, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)
        status = reporter.get_status()
        assert status["enabled"] is True

    def test_get_status_includes_times(self) -> None:
        """Test get_status() includes times field."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(
            enabled=True, times=("08:00", "20:00"), timezone="UTC"
        )
        reporter = DailyReporter(mock_cm, config=config)
        status = reporter.get_status()
        assert status["times"] == ("08:00", "20:00")

    def test_get_status_includes_timezone(self) -> None:
        """Test get_status() includes timezone field."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(
            enabled=True, times=("10:00",), timezone="Europe/Paris"
        )
        reporter = DailyReporter(mock_cm, config=config)
        status = reporter.get_status()
        assert status["timezone"] == "Europe/Paris"

    def test_get_status_includes_scheduler_running(self) -> None:
        """Test get_status() includes scheduler_running field."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(enabled=True, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)
        assert reporter.get_status()["scheduler_running"] is False
        reporter.start()
        assert reporter.get_status()["scheduler_running"] is True
        reporter.stop()

    def test_get_status_includes_reports_generated_count(self) -> None:
        """Test get_status() includes reports_generated_count field."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)
        status = reporter.get_status()
        assert "reports_generated_count" in status
        assert status["reports_generated_count"] == 0

    def test_is_enabled_property(self) -> None:
        """Test is_enabled property returns correct value."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(enabled=True, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)
        assert reporter.is_enabled is True

        reporter2 = DailyReporter(mock_cm)
        assert reporter2.is_enabled is False


class TestDailyReporterDisabled:
    """Tests for DailyReporter when disabled (AC: #4)."""

    def test_disabled_reporter_does_not_schedule(self) -> None:
        """Test disabled reporter does not add jobs to scheduler."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(enabled=False, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)
        reporter.start()
        jobs = reporter._scheduler.get_jobs()
        assert len(jobs) == 0


class TestDailyReportGeneration:
    """Tests for DailyReporter report generation (Task 5)."""

    def test_generate_report_returns_daily_report(self) -> None:
        """Test _generate_report returns DailyReport instance."""
        from mt5linux.monitoring.reporter import DailyReport, DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=10000.0, equity=10500.0
        )
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = True

        reporter = DailyReporter(mock_cm)
        report = reporter._generate_report()
        assert isinstance(report, DailyReport)

    def test_generate_report_includes_account_info(self) -> None:
        """Test report includes account balance and equity."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=15000.0, equity=15500.0
        )
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = True

        reporter = DailyReporter(mock_cm)
        report = reporter._generate_report()
        assert report is not None
        assert report.account_balance == 15000.0
        assert report.equity == 15500.0

    def test_generate_report_handles_account_info_error(self) -> None:
        """Test report handles account info retrieval error gracefully."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.side_effect = Exception("Connection error")
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = False

        reporter = DailyReporter(mock_cm)
        report = reporter._generate_report()
        assert report is not None
        assert report.account_balance is None
        assert report.equity is None

    def test_generate_report_includes_positions(self) -> None:
        """Test report includes position details."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=10000.0, equity=10500.0
        )
        mock_cm.mt5.positions_total.return_value = 2
        mock_cm.mt5.positions_get.return_value = [
            MagicMock(symbol="EURUSD", volume=0.1, profit=50.0, type=0),
            MagicMock(symbol="GBPUSD", volume=0.2, profit=-25.0, type=1),
        ]
        mock_cm.is_connected = True

        reporter = DailyReporter(mock_cm)
        report = reporter._generate_report()
        assert report is not None
        assert report.open_positions == 2
        assert len(report.position_details) == 2
        assert report.position_details[0].symbol == "EURUSD"
        assert report.position_details[0].type == "buy"
        assert report.position_details[1].symbol == "GBPUSD"
        assert report.position_details[1].type == "sell"

    def test_generate_report_includes_connection_status(self) -> None:
        """Test report includes connection status."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=10000.0, equity=10000.0
        )
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = True

        reporter = DailyReporter(mock_cm)
        report = reporter._generate_report()
        assert report is not None
        assert report.connection_status == "connected"

        mock_cm.is_connected = False
        report2 = reporter._generate_report()
        assert report2 is not None
        assert report2.connection_status == "disconnected"

    def test_generate_report_includes_heartbeat_status(self) -> None:
        """Test report includes heartbeat monitor status."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=10000.0, equity=10000.0
        )
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = True

        mock_hb = MagicMock()
        mock_hb.get_status.return_value = {"is_healthy": True, "heartbeat_count": 100}
        mock_hb.get_uptime.return_value = 7200.0

        reporter = DailyReporter(mock_cm, heartbeat_monitor=mock_hb)
        report = reporter._generate_report()
        assert report is not None
        assert report.heartbeat_status == {"is_healthy": True, "heartbeat_count": 100}
        assert report.uptime_seconds == 7200.0

    def test_generate_report_includes_timestamp(self) -> None:
        """Test report includes generation timestamp."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=10000.0, equity=10000.0
        )
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = True

        reporter = DailyReporter(mock_cm)
        before = time.time()
        report = reporter._generate_report()
        after = time.time()
        assert report is not None
        assert before <= report.timestamp <= after


class TestDailyReportFormatting:
    """Tests for DailyReporter report formatting (Task 7)."""

    def test_format_report_returns_string(self) -> None:
        """Test format_report returns string."""
        from mt5linux.monitoring.reporter import DailyReport, DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)

        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10500.0,
            open_positions=0,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={"is_healthy": True},
            report_time="2026-01-29 10:00:00",
        )
        formatted = reporter.format_report(report)
        assert isinstance(formatted, str)

    def test_format_report_includes_header(self) -> None:
        """Test formatted report includes header."""
        from mt5linux.monitoring.reporter import DailyReport, DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)

        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10500.0,
            open_positions=0,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-29 10:00:00",
        )
        formatted = reporter.format_report(report)
        assert "Daily Trading Report" in formatted
        assert "2026-01-29 10:00:00" in formatted

    def test_format_report_includes_account_status(self) -> None:
        """Test formatted report includes account status."""
        from mt5linux.monitoring.reporter import DailyReport, DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)

        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=12345.67,
            equity=12400.00,
            open_positions=0,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-29 10:00:00",
        )
        formatted = reporter.format_report(report)
        assert "Balance: 12345.67" in formatted
        assert "Equity: 12400.00" in formatted

    def test_format_report_handles_none_values(self) -> None:
        """Test formatted report handles None values gracefully."""
        from mt5linux.monitoring.reporter import DailyReport, DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)

        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=None,
            equity=None,
            open_positions=0,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="disconnected",
            heartbeat_status={},
            report_time="2026-01-29 10:00:00",
        )
        formatted = reporter.format_report(report)
        assert "Balance: N/A" in formatted
        assert "Equity: N/A" in formatted

    def test_format_report_includes_positions(self) -> None:
        """Test formatted report includes position details."""
        from mt5linux.monitoring.reporter import (
            DailyReport,
            DailyReporter,
            PositionInfo,
        )

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)

        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10500.0,
            open_positions=2,
            position_details=(
                PositionInfo(symbol="EURUSD", volume=0.1, profit=50.0, type="buy"),
                PositionInfo(symbol="GBPUSD", volume=0.2, profit=-25.0, type="sell"),
            ),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-29 10:00:00",
        )
        formatted = reporter.format_report(report)
        assert "Open Positions: 2" in formatted
        assert "EURUSD" in formatted
        assert "GBPUSD" in formatted
        assert "50.00" in formatted
        assert "-25.00" in formatted

    def test_format_report_includes_system_status(self) -> None:
        """Test formatted report includes system status."""
        from mt5linux.monitoring.reporter import DailyReport, DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)

        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10500.0,
            open_positions=0,
            position_details=(),
            uptime_seconds=90000.0,  # 1 day, 1 hour
            connection_status="connected",
            heartbeat_status={"is_healthy": True},
            report_time="2026-01-29 10:00:00",
        )
        formatted = reporter.format_report(report)
        assert "Connection: connected" in formatted
        assert "1d 1h" in formatted
        assert "Heartbeat: Healthy" in formatted


class TestDailyReporterCallbackExecution:
    """Tests for callback execution on report generation."""

    def test_callbacks_invoked_on_report(self) -> None:
        """Test registered callbacks are invoked on report generation."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=10000.0, equity=10000.0
        )
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = True

        reporter = DailyReporter(mock_cm)
        callback = MagicMock()
        reporter.on_report_generated(callback)

        reporter._generate_and_notify()

        callback.assert_called_once()
        assert callback.call_args[0][0].account_balance == 10000.0

    def test_callback_error_does_not_propagate(self) -> None:
        """Test callback errors are caught and don't crash reporter."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=10000.0, equity=10000.0
        )
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = True

        reporter = DailyReporter(mock_cm)
        error_callback = MagicMock(side_effect=Exception("Callback error"))
        success_callback = MagicMock()
        reporter.on_report_generated(error_callback)
        reporter.on_report_generated(success_callback)

        # Should not raise
        reporter._generate_and_notify()

        # Both callbacks should have been called
        error_callback.assert_called_once()
        success_callback.assert_called_once()

    def test_reports_generated_count_increments(self) -> None:
        """Test reports_generated_count increments on each report."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=10000.0, equity=10000.0
        )
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = True

        reporter = DailyReporter(mock_cm)
        assert reporter._reports_generated_count == 0

        reporter._generate_and_notify()
        assert reporter._reports_generated_count == 1

        reporter._generate_and_notify()
        assert reporter._reports_generated_count == 2


class TestDailyReporterUptimeFormatting:
    """Tests for uptime formatting helper."""

    def test_format_uptime_minutes_only(self) -> None:
        """Test uptime formatting for minutes only."""
        from mt5linux.monitoring.reporter import DailyReporter

        assert DailyReporter._format_uptime(300.0) == "5m"
        assert DailyReporter._format_uptime(0.0) == "0m"
        assert DailyReporter._format_uptime(59 * 60) == "59m"

    def test_format_uptime_hours_and_minutes(self) -> None:
        """Test uptime formatting for hours and minutes."""
        from mt5linux.monitoring.reporter import DailyReporter

        assert DailyReporter._format_uptime(3600.0) == "1h 0m"
        assert DailyReporter._format_uptime(3660.0) == "1h 1m"
        assert DailyReporter._format_uptime(7200.0 + 1800.0) == "2h 30m"

    def test_format_uptime_days_hours_minutes(self) -> None:
        """Test uptime formatting for days, hours and minutes."""
        from mt5linux.monitoring.reporter import DailyReporter

        assert DailyReporter._format_uptime(86400.0) == "1d 0h 0m"
        assert DailyReporter._format_uptime(86400.0 + 3600.0 + 60.0) == "1d 1h 1m"
        assert DailyReporter._format_uptime(2 * 86400.0 + 12 * 3600.0) == "2d 12h 0m"


class TestDailyReporterTimezone:
    """Tests for timezone-aware report generation (AC #3, Review Fix M2)."""

    def test_report_time_uses_configured_timezone(self) -> None:
        """Test report_time uses configured timezone (AC #3)."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=10000.0, equity=10000.0
        )
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = True

        # Use a non-UTC timezone
        config = DailyReportsConfig(
            enabled=True, times=("10:00",), timezone="America/New_York"
        )
        reporter = DailyReporter(mock_cm, config=config)
        report = reporter._generate_report()

        assert report is not None
        # Report time should include timezone indicator
        assert "EDT" in report.report_time or "EST" in report.report_time

    def test_report_time_includes_utc_when_configured(self) -> None:
        """Test report_time shows UTC when timezone is UTC."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        mock_cm.mt5.account_info.return_value = MagicMock(
            balance=10000.0, equity=10000.0
        )
        mock_cm.mt5.positions_total.return_value = 0
        mock_cm.mt5.positions_get.return_value = []
        mock_cm.is_connected = True

        config = DailyReportsConfig(enabled=True, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)
        report = reporter._generate_report()

        assert report is not None
        assert "UTC" in report.report_time


class TestDailyReporterNextReportTime:
    """Tests for get_next_report_time() method (Task 8, Review Fix M4)."""

    def test_get_next_report_time_returns_none_when_not_started(self) -> None:
        """Test get_next_report_time returns None when scheduler not started."""
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        reporter = DailyReporter(mock_cm)

        assert reporter.get_next_report_time() is None

    def test_get_next_report_time_returns_datetime_when_running(self) -> None:
        """Test get_next_report_time returns datetime when scheduler running."""
        from datetime import datetime

        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(enabled=True, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)

        reporter.start()
        try:
            next_time = reporter.get_next_report_time()
            assert next_time is not None
            assert isinstance(next_time, datetime)
        finally:
            reporter.stop()

    def test_get_next_report_time_returns_none_after_stop(self) -> None:
        """Test get_next_report_time returns None after scheduler stopped."""
        from mt5linux.config import DailyReportsConfig
        from mt5linux.monitoring.reporter import DailyReporter

        mock_cm = MagicMock()
        config = DailyReportsConfig(enabled=True, times=("10:00",), timezone="UTC")
        reporter = DailyReporter(mock_cm, config=config)

        reporter.start()
        reporter.stop()

        assert reporter.get_next_report_time() is None
