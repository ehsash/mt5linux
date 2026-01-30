"""Tests for analytics module (Story 4.7).

Tests AnalyticsConfig, analytics dataclasses, AnalyticsEngine, and CLI commands.
"""

import pytest

pytestmark = pytest.mark.unit


# =============================================================================
# Task 1: AnalyticsConfig Tests
# =============================================================================


class TestAnalyticsConfig:
    """Test AnalyticsConfig dataclass validation."""

    def test_default_config_values(self) -> None:
        """AnalyticsConfig has correct default values."""
        from mt5linux.config import AnalyticsConfig

        config = AnalyticsConfig()
        assert config.enabled is True
        assert config.history_window_hours == 24
        assert config.include_in_daily_reports is True

    def test_config_custom_values(self) -> None:
        """AnalyticsConfig accepts custom values."""
        from mt5linux.config import AnalyticsConfig

        config = AnalyticsConfig(
            enabled=False,
            history_window_hours=48,
            include_in_daily_reports=False,
        )
        assert config.enabled is False
        assert config.history_window_hours == 48
        assert config.include_in_daily_reports is False

    def test_config_validates_positive_history_window(self) -> None:
        """AnalyticsConfig rejects non-positive history_window_hours."""
        from mt5linux.config import AnalyticsConfig

        with pytest.raises(ValueError, match="history_window_hours must be positive"):
            AnalyticsConfig(history_window_hours=0)

        with pytest.raises(ValueError, match="history_window_hours must be positive"):
            AnalyticsConfig(history_window_hours=-1)

    def test_config_is_frozen(self) -> None:
        """AnalyticsConfig is immutable (frozen=True)."""
        from mt5linux.config import AnalyticsConfig

        config = AnalyticsConfig()
        with pytest.raises(AttributeError):
            config.enabled = False  # type: ignore[misc]

    def test_config_has_slots(self) -> None:
        """AnalyticsConfig uses slots for memory efficiency."""
        from mt5linux.config import AnalyticsConfig

        config = AnalyticsConfig()
        assert hasattr(config, "__slots__") or not hasattr(config, "__dict__")


class TestAnalyticsConfigIntegration:
    """Test AnalyticsConfig integration with Config class."""

    def test_config_to_dict_includes_analytics(self) -> None:
        """Config.to_dict() includes analytics section."""
        from mt5linux.config import Config, AnalyticsConfig

        config = Config()
        config.analytics = AnalyticsConfig(enabled=False, history_window_hours=12)
        config_dict = config.to_dict()

        assert "analytics" in config_dict
        assert config_dict["analytics"]["enabled"] is False
        assert config_dict["analytics"]["history_window_hours"] == 12

    def test_config_from_dict_loads_analytics(self) -> None:
        """Config.from_dict() loads analytics section."""
        from mt5linux.config import Config

        data = {
            "analytics": {
                "enabled": True,
                "history_window_hours": 72,
                "include_in_daily_reports": False,
            }
        }
        config = Config.from_dict(data)

        assert config.analytics is not None
        assert config.analytics.enabled is True
        assert config.analytics.history_window_hours == 72
        assert config.analytics.include_in_daily_reports is False

    def test_config_from_dict_uses_defaults_when_missing(self) -> None:
        """Config.from_dict() uses default AnalyticsConfig when section missing."""
        from mt5linux.config import Config

        config = Config.from_dict({})
        assert config.analytics is not None
        assert config.analytics.enabled is True
        assert config.analytics.history_window_hours == 24


# =============================================================================
# Task 2: Analytics Dataclasses Tests
# =============================================================================


class TestLatencyAnalytics:
    """Test LatencyAnalytics dataclass."""

    def test_latency_analytics_creation(self) -> None:
        """LatencyAnalytics can be created with all fields."""
        from mt5linux.monitoring.analytics import LatencyAnalytics

        analytics = LatencyAnalytics(
            average_ms=50.0,
            median_ms=45.0,
            p95_ms=100.0,
            p99_ms=150.0,
            min_ms=10.0,
            max_ms=200.0,
            std_dev_ms=25.0,
            measurement_count=100,
            high_latency_count=5,
            high_latency_rate=0.05,
        )
        assert analytics.average_ms == 50.0
        assert analytics.median_ms == 45.0
        assert analytics.p95_ms == 100.0
        assert analytics.p99_ms == 150.0
        assert analytics.min_ms == 10.0
        assert analytics.max_ms == 200.0
        assert analytics.std_dev_ms == 25.0
        assert analytics.measurement_count == 100
        assert analytics.high_latency_count == 5
        assert analytics.high_latency_rate == 0.05

    def test_latency_analytics_is_frozen(self) -> None:
        """LatencyAnalytics is immutable (frozen=True)."""
        from mt5linux.monitoring.analytics import LatencyAnalytics

        analytics = LatencyAnalytics(
            average_ms=50.0,
            median_ms=45.0,
            p95_ms=100.0,
            p99_ms=150.0,
            min_ms=10.0,
            max_ms=200.0,
            std_dev_ms=25.0,
            measurement_count=100,
            high_latency_count=5,
            high_latency_rate=0.05,
        )
        with pytest.raises(AttributeError):
            analytics.average_ms = 60.0  # type: ignore[misc]


class TestSystemHealthAnalytics:
    """Test SystemHealthAnalytics dataclass."""

    def test_system_health_analytics_creation(self) -> None:
        """SystemHealthAnalytics can be created with all fields."""
        from mt5linux.monitoring.analytics import SystemHealthAnalytics

        analytics = SystemHealthAnalytics(
            uptime_seconds=3600.0,
            heartbeat_count=120,
            average_heartbeat_variance_ms=500.0,
            connection_status="connected",
            consecutive_failures=0,
            health_score=1.0,
        )
        assert analytics.uptime_seconds == 3600.0
        assert analytics.heartbeat_count == 120
        assert analytics.average_heartbeat_variance_ms == 500.0
        assert analytics.connection_status == "connected"
        assert analytics.consecutive_failures == 0
        assert analytics.health_score == 1.0

    def test_system_health_analytics_is_frozen(self) -> None:
        """SystemHealthAnalytics is immutable (frozen=True)."""
        from mt5linux.monitoring.analytics import SystemHealthAnalytics

        analytics = SystemHealthAnalytics(
            uptime_seconds=3600.0,
            heartbeat_count=120,
            average_heartbeat_variance_ms=500.0,
            connection_status="connected",
            consecutive_failures=0,
            health_score=1.0,
        )
        with pytest.raises(AttributeError):
            analytics.health_score = 0.5  # type: ignore[misc]


class TestTradingAnalytics:
    """Test TradingAnalytics dataclass."""

    def test_trading_analytics_creation(self) -> None:
        """TradingAnalytics can be created with all fields."""
        from mt5linux.monitoring.analytics import TradingAnalytics

        analytics = TradingAnalytics(
            total_trades=50,
            successful_trades=48,
            failed_trades=2,
            success_rate=0.96,
            average_execution_time_ms=75.0,
            symbols_traded=("EURUSD", "GBPUSD"),
            total_volume=5.0,
        )
        assert analytics.total_trades == 50
        assert analytics.successful_trades == 48
        assert analytics.failed_trades == 2
        assert analytics.success_rate == 0.96
        assert analytics.average_execution_time_ms == 75.0
        assert analytics.symbols_traded == ("EURUSD", "GBPUSD")
        assert analytics.total_volume == 5.0

    def test_trading_analytics_is_frozen(self) -> None:
        """TradingAnalytics is immutable (frozen=True)."""
        from mt5linux.monitoring.analytics import TradingAnalytics

        analytics = TradingAnalytics(
            total_trades=50,
            successful_trades=48,
            failed_trades=2,
            success_rate=0.96,
            average_execution_time_ms=75.0,
            symbols_traded=("EURUSD",),
            total_volume=5.0,
        )
        with pytest.raises(AttributeError):
            analytics.total_trades = 100  # type: ignore[misc]


class TestAnalyticsReport:
    """Test AnalyticsReport dataclass."""

    def test_analytics_report_creation_with_all_components(self) -> None:
        """AnalyticsReport can be created with all analytics components."""
        from mt5linux.monitoring.analytics import (
            AnalyticsReport,
            LatencyAnalytics,
            SystemHealthAnalytics,
            TradingAnalytics,
        )

        latency = LatencyAnalytics(
            average_ms=50.0,
            median_ms=45.0,
            p95_ms=100.0,
            p99_ms=150.0,
            min_ms=10.0,
            max_ms=200.0,
            std_dev_ms=25.0,
            measurement_count=100,
            high_latency_count=5,
            high_latency_rate=0.05,
        )
        health = SystemHealthAnalytics(
            uptime_seconds=3600.0,
            heartbeat_count=120,
            average_heartbeat_variance_ms=500.0,
            connection_status="connected",
            consecutive_failures=0,
            health_score=1.0,
        )
        trading = TradingAnalytics(
            total_trades=50,
            successful_trades=48,
            failed_trades=2,
            success_rate=0.96,
            average_execution_time_ms=75.0,
            symbols_traded=("EURUSD",),
            total_volume=5.0,
        )
        report = AnalyticsReport(
            timestamp=1234567890.0,
            period_hours=24,
            latency=latency,
            system_health=health,
            trading=trading,
            insights=("Test insight 1", "Test insight 2"),
        )
        assert report.timestamp == 1234567890.0
        assert report.period_hours == 24
        assert report.latency is latency
        assert report.system_health is health
        assert report.trading is trading
        assert report.insights == ("Test insight 1", "Test insight 2")

    def test_analytics_report_with_none_components(self) -> None:
        """AnalyticsReport can be created with None for optional components."""
        from mt5linux.monitoring.analytics import AnalyticsReport

        report = AnalyticsReport(
            timestamp=1234567890.0,
            period_hours=24,
            latency=None,
            system_health=None,
            trading=None,
            insights=(),
        )
        assert report.latency is None
        assert report.system_health is None
        assert report.trading is None
        assert report.insights == ()

    def test_analytics_report_is_frozen(self) -> None:
        """AnalyticsReport is immutable (frozen=True)."""
        from mt5linux.monitoring.analytics import AnalyticsReport

        report = AnalyticsReport(
            timestamp=1234567890.0,
            period_hours=24,
            latency=None,
            system_health=None,
            trading=None,
            insights=(),
        )
        with pytest.raises(AttributeError):
            report.timestamp = 9999999999.0  # type: ignore[misc]


# =============================================================================
# Task 3: AnalyticsEngine Tests
# =============================================================================


class MockLatencyMonitor:
    """Mock LatencyMonitor for testing AnalyticsEngine."""

    def __init__(self, measurements: list = None) -> None:
        self._measurements = measurements or []

    def get_recent_measurements(self, count: int) -> list:
        """Return mock measurements."""
        return self._measurements[:count]

    def get_status(self) -> dict:
        """Return mock status."""
        return {"measurement_count": len(self._measurements)}


class MockHeartbeatMonitor:
    """Mock HeartbeatMonitor for testing AnalyticsEngine."""

    def __init__(
        self,
        uptime: float = 3600.0,
        heartbeat_count: int = 120,
        average_variance: float = 0.5,
        consecutive_failures: int = 0,
        is_healthy: bool = True,
    ) -> None:
        self._uptime = uptime
        self._heartbeat_count = heartbeat_count
        self._average_variance = average_variance
        self._consecutive_failures = consecutive_failures
        self._is_healthy = is_healthy

    def get_status(self) -> dict:
        """Return mock status."""
        return {
            "heartbeat_count": self._heartbeat_count,
            "average_variance": self._average_variance,
            "consecutive_failures": self._consecutive_failures,
            "is_healthy": self._is_healthy,
        }

    def get_uptime(self) -> float:
        """Return mock uptime."""
        return self._uptime


class MockConnectionManager:
    """Mock ConnectionManager for testing AnalyticsEngine."""

    def __init__(self, is_connected: bool = True) -> None:
        self.is_connected = is_connected


class TestAnalyticsEngine:
    """Test AnalyticsEngine class."""

    def test_engine_initialization_with_defaults(self) -> None:
        """AnalyticsEngine can be initialized with default config."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        engine = AnalyticsEngine()
        status = engine.get_status()
        assert status["enabled"] is True
        assert status["history_window_hours"] == 24
        assert status["reports_generated"] == 0

    def test_engine_initialization_with_custom_config(self) -> None:
        """AnalyticsEngine can be initialized with custom config."""
        from mt5linux.config import AnalyticsConfig
        from mt5linux.monitoring.analytics import AnalyticsEngine

        config = AnalyticsConfig(enabled=False, history_window_hours=48)
        engine = AnalyticsEngine(config=config)
        status = engine.get_status()
        assert status["enabled"] is False
        assert status["history_window_hours"] == 48

    def test_engine_with_monitors(self) -> None:
        """AnalyticsEngine can be initialized with monitor instances."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        latency_monitor = MockLatencyMonitor()
        heartbeat_monitor = MockHeartbeatMonitor()
        conn_manager = MockConnectionManager()

        engine = AnalyticsEngine(
            latency_monitor=latency_monitor,
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_manager,
        )
        status = engine.get_status()
        assert status["has_latency_monitor"] is True
        assert status["has_heartbeat_monitor"] is True
        assert status["has_connection_manager"] is True

    def test_calculate_latency_analytics_no_monitor(self) -> None:
        """calculate_latency_analytics returns None without monitor."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        engine = AnalyticsEngine()
        result = engine.calculate_latency_analytics()
        assert result is None

    def test_calculate_latency_analytics_no_data(self) -> None:
        """calculate_latency_analytics returns None with empty data."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        latency_monitor = MockLatencyMonitor(measurements=[])
        engine = AnalyticsEngine(latency_monitor=latency_monitor)
        result = engine.calculate_latency_analytics()
        assert result is None

    def test_calculate_latency_analytics_with_data(self) -> None:
        """calculate_latency_analytics calculates correct statistics."""
        from mt5linux.monitoring.analytics import AnalyticsEngine
        from mt5linux.monitoring.latency import LatencyMeasurement

        measurements = [
            LatencyMeasurement(
                order_ticket=i,
                symbol="EURUSD",
                order_type="buy",
                send_timestamp=1000.0 + i,
                execution_timestamp=1000.0 + i + 0.05,
                latency_ms=50.0 + (i * 10),
                is_high_latency=(50.0 + (i * 10)) > 150,
            )
            for i in range(10)
        ]
        latency_monitor = MockLatencyMonitor(measurements=measurements)
        engine = AnalyticsEngine(latency_monitor=latency_monitor)

        result = engine.calculate_latency_analytics()
        assert result is not None
        assert result.measurement_count == 10
        assert result.min_ms == 50.0
        assert result.max_ms == 140.0
        # Average of 50, 60, 70, 80, 90, 100, 110, 120, 130, 140 = 95
        assert result.average_ms == 95.0

    def test_calculate_system_health_analytics_no_monitor(self) -> None:
        """calculate_system_health_analytics returns None without monitor."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        engine = AnalyticsEngine()
        result = engine.calculate_system_health_analytics()
        assert result is None

    def test_calculate_system_health_analytics_with_data(self) -> None:
        """calculate_system_health_analytics calculates correct statistics."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        heartbeat_monitor = MockHeartbeatMonitor(
            uptime=7200.0,
            heartbeat_count=240,
            average_variance=0.3,
            consecutive_failures=0,
            is_healthy=True,
        )
        conn_manager = MockConnectionManager(is_connected=True)
        engine = AnalyticsEngine(
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_manager,
        )

        result = engine.calculate_system_health_analytics()
        assert result is not None
        assert result.uptime_seconds == 7200.0
        assert result.heartbeat_count == 240
        assert result.connection_status == "connected"
        assert result.consecutive_failures == 0
        # Healthy (0.5) + low variance (0.25) + no failures (0.25) = 1.0
        assert result.health_score == 1.0

    def test_calculate_system_health_score_unhealthy(self) -> None:
        """Health score reflects unhealthy state."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        heartbeat_monitor = MockHeartbeatMonitor(
            uptime=100.0,
            heartbeat_count=3,
            average_variance=2.0,  # > 1 second = NFR9 violation
            consecutive_failures=5,
            is_healthy=False,
        )
        engine = AnalyticsEngine(heartbeat_monitor=heartbeat_monitor)

        result = engine.calculate_system_health_analytics()
        assert result is not None
        # Not healthy (0) + high variance (0) + failures (0) = 0
        assert result.health_score == 0.0

    def test_generate_report(self) -> None:
        """generate_report creates complete AnalyticsReport."""
        from mt5linux.monitoring.analytics import AnalyticsEngine, AnalyticsReport

        engine = AnalyticsEngine()
        report = engine.generate_report()

        assert isinstance(report, AnalyticsReport)
        assert report.period_hours == 24
        assert report.timestamp > 0
        assert report.latency is None  # No monitor
        assert report.system_health is None  # No monitor
        assert isinstance(report.insights, tuple)

    def test_generate_report_increments_counter(self) -> None:
        """generate_report increments reports_generated counter."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        engine = AnalyticsEngine()
        assert engine.get_status()["reports_generated"] == 0

        engine.generate_report()
        assert engine.get_status()["reports_generated"] == 1

        engine.generate_report()
        assert engine.get_status()["reports_generated"] == 2

    def test_clear_history(self) -> None:
        """clear_history removes insights history."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        engine = AnalyticsEngine()
        # Generate some insights
        engine.generate_report()

        # Check there's something to clear
        engine.clear_history()

        # Verify cleared
        assert engine.recent_insights == []

    def test_recent_insights_property(self) -> None:
        """recent_insights returns list of (timestamp, insight) tuples."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        engine = AnalyticsEngine()
        insights = engine.recent_insights
        assert isinstance(insights, list)


# =============================================================================
# Task 4: Insight Generation Tests
# =============================================================================


class TestAnalyticsEngineInsights:
    """Test insight generation logic."""

    def test_insight_high_latency_rate(self) -> None:
        """Generates insight when high latency rate exceeds 10%."""
        from mt5linux.monitoring.analytics import AnalyticsEngine
        from mt5linux.monitoring.latency import LatencyMeasurement

        # Create measurements where 50% are high latency
        measurements = [
            LatencyMeasurement(
                order_ticket=i,
                symbol="EURUSD",
                order_type="buy",
                send_timestamp=1000.0 + i,
                execution_timestamp=1000.0 + i + 0.2,
                latency_ms=50.0 if i % 2 == 0 else 300.0,
                is_high_latency=i % 2 != 0,  # 50% high latency
            )
            for i in range(10)
        ]
        latency_monitor = MockLatencyMonitor(measurements=measurements)
        engine = AnalyticsEngine(latency_monitor=latency_monitor)

        insights = engine.generate_insights()
        assert any("High latency rate" in insight for insight in insights)

    def test_insight_healthy_latency(self) -> None:
        """Generates 'Latency healthy' insight when avg < 100ms and low high latency rate."""
        from mt5linux.monitoring.analytics import AnalyticsEngine
        from mt5linux.monitoring.latency import LatencyMeasurement

        measurements = [
            LatencyMeasurement(
                order_ticket=i,
                symbol="EURUSD",
                order_type="buy",
                send_timestamp=1000.0 + i,
                execution_timestamp=1000.0 + i + 0.05,
                latency_ms=50.0,
                is_high_latency=False,
            )
            for i in range(10)
        ]
        latency_monitor = MockLatencyMonitor(measurements=measurements)
        engine = AnalyticsEngine(latency_monitor=latency_monitor)

        insights = engine.generate_insights()
        assert any("Latency healthy" in insight for insight in insights)

    def test_insight_nfr9_variance_violation(self) -> None:
        """Generates insight when heartbeat variance exceeds NFR9 limit."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        heartbeat_monitor = MockHeartbeatMonitor(
            uptime=3600.0,
            heartbeat_count=120,
            average_variance=2.0,  # 2000ms > 1000ms NFR9 limit
            consecutive_failures=0,
            is_healthy=True,
        )
        engine = AnalyticsEngine(heartbeat_monitor=heartbeat_monitor)

        insights = engine.generate_insights()
        assert any("NFR9 limit" in insight for insight in insights)

    def test_insight_connection_instability(self) -> None:
        """Generates insight when consecutive failures > 0."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        heartbeat_monitor = MockHeartbeatMonitor(
            uptime=3600.0,
            heartbeat_count=120,
            average_variance=0.5,
            consecutive_failures=3,
            is_healthy=False,
        )
        engine = AnalyticsEngine(heartbeat_monitor=heartbeat_monitor)

        insights = engine.generate_insights()
        assert any("Connection instability" in insight for insight in insights)

    def test_insight_system_healthy(self) -> None:
        """Generates 'System healthy' insight when health score >= 90%."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        heartbeat_monitor = MockHeartbeatMonitor(
            uptime=3600.0,
            heartbeat_count=120,
            average_variance=0.3,
            consecutive_failures=0,
            is_healthy=True,
        )
        conn_manager = MockConnectionManager(is_connected=True)
        engine = AnalyticsEngine(
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_manager,
        )

        insights = engine.generate_insights()
        assert any("System healthy" in insight for insight in insights)

    def test_insights_stored_in_history(self) -> None:
        """Generated insights are stored in history."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        heartbeat_monitor = MockHeartbeatMonitor(
            uptime=3600.0,
            heartbeat_count=120,
            average_variance=0.3,
            consecutive_failures=0,
            is_healthy=True,
        )
        engine = AnalyticsEngine(heartbeat_monitor=heartbeat_monitor)

        # Generate insights
        insights = engine.generate_insights()

        # Check history
        history = engine.recent_insights
        assert len(history) == len(insights)
        for ts, insight_text in history:
            assert ts > 0
            assert insight_text in insights

    def test_insights_history_limited_to_100(self) -> None:
        """Insights history is limited to 100 entries."""
        from mt5linux.monitoring.analytics import AnalyticsEngine

        heartbeat_monitor = MockHeartbeatMonitor(
            uptime=3600.0,
            heartbeat_count=120,
            average_variance=0.3,
            consecutive_failures=0,
            is_healthy=True,
        )
        engine = AnalyticsEngine(heartbeat_monitor=heartbeat_monitor)

        # Generate insights many times
        for _ in range(50):
            engine.generate_insights()

        history = engine.recent_insights
        assert len(history) <= 100


# =============================================================================
# Task 5: DailyReporter Integration Tests
# =============================================================================


class TestDailyReporterAnalyticsIntegration:
    """Test DailyReporter integration with analytics."""

    def test_daily_report_has_analytics_field(self) -> None:
        """DailyReport dataclass has analytics field."""
        from mt5linux.monitoring.reporter import DailyReport

        # Create report with analytics=None (backward compatible)
        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10000.0,
            open_positions=0,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-30 12:00:00 UTC",
            analytics=None,
        )
        assert report.analytics is None

    def test_daily_report_with_analytics(self) -> None:
        """DailyReport can include AnalyticsReport."""
        from mt5linux.monitoring.analytics import AnalyticsReport
        from mt5linux.monitoring.reporter import DailyReport

        analytics = AnalyticsReport(
            timestamp=1234567890.0,
            period_hours=24,
            latency=None,
            system_health=None,
            trading=None,
            insights=("Test insight",),
        )
        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10000.0,
            open_positions=0,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-30 12:00:00 UTC",
            analytics=analytics,
        )
        assert report.analytics is analytics
        assert report.analytics.insights == ("Test insight",)

    def test_format_report_without_analytics(self) -> None:
        """format_report works when analytics is None."""
        from unittest.mock import MagicMock

        from mt5linux.monitoring.reporter import DailyReport, DailyReporter

        conn_mgr = MagicMock()
        reporter = DailyReporter(conn_mgr)

        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10000.0,
            open_positions=0,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-30 12:00:00 UTC",
            analytics=None,
        )

        formatted = reporter.format_report(report)
        assert "Daily Trading Report" in formatted
        assert "Analytics" not in formatted

    def test_format_report_with_analytics(self) -> None:
        """format_report includes analytics section when present."""
        from unittest.mock import MagicMock

        from mt5linux.monitoring.analytics import (
            AnalyticsReport,
            LatencyAnalytics,
            SystemHealthAnalytics,
        )
        from mt5linux.monitoring.reporter import DailyReport, DailyReporter

        conn_mgr = MagicMock()
        reporter = DailyReporter(conn_mgr)

        latency = LatencyAnalytics(
            average_ms=50.0,
            median_ms=45.0,
            p95_ms=100.0,
            p99_ms=150.0,
            min_ms=10.0,
            max_ms=200.0,
            std_dev_ms=25.0,
            measurement_count=100,
            high_latency_count=5,
            high_latency_rate=0.05,
        )
        health = SystemHealthAnalytics(
            uptime_seconds=3600.0,
            heartbeat_count=120,
            average_heartbeat_variance_ms=500.0,
            connection_status="connected",
            consecutive_failures=0,
            health_score=1.0,
        )
        analytics = AnalyticsReport(
            timestamp=1234567890.0,
            period_hours=24,
            latency=latency,
            system_health=health,
            trading=None,
            insights=("System healthy: 100% health score",),
        )
        report = DailyReport(
            timestamp=1234567890.0,
            account_balance=10000.0,
            equity=10000.0,
            open_positions=0,
            position_details=(),
            uptime_seconds=3600.0,
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-30 12:00:00 UTC",
            analytics=analytics,
        )

        formatted = reporter.format_report(report)
        assert "Analytics" in formatted
        assert "50.0ms" in formatted  # Average latency
        assert "100%" in formatted  # Health score
        assert "Insights" in formatted
        assert "System healthy" in formatted


# =============================================================================
# Task 6: CLI Commands Tests
# =============================================================================


class TestAnalyticsCLI:
    """Test CLI commands for analytics (Story 4.7)."""

    def test_analytics_status_command(self) -> None:
        """analytics status shows engine status."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["analytics", "status"])

        assert result.exit_code == 0
        assert "Analytics Status" in result.output
        assert "Enabled" in result.output
        assert "History Window" in result.output

    def test_analytics_report_command(self) -> None:
        """analytics report generates and displays report."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["analytics", "report"])

        assert result.exit_code == 0
        assert "Analytics Report" in result.output
        assert "Generated" in result.output

    def test_analytics_report_when_disabled(self) -> None:
        """analytics report shows warning when disabled."""
        from unittest.mock import patch

        from typer.testing import CliRunner

        from mt5linux.cli import app
        from mt5linux.config import AnalyticsConfig, Config

        # Create config with analytics disabled
        mock_config = Config()
        mock_config.analytics = AnalyticsConfig(enabled=False)

        runner = CliRunner()
        with patch("mt5linux.cli.get_config", return_value=mock_config):
            result = runner.invoke(app, ["analytics", "report"])

        assert result.exit_code == 1
        assert "disabled" in result.output.lower()

    def test_analytics_insights_command(self) -> None:
        """analytics insights shows recent insights."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["analytics", "insights"])

        assert result.exit_code == 0
        # No insights without running monitors
        assert "No recent insights" in result.output or "Recent Insights" in result.output

    def test_analytics_subcommand_help(self) -> None:
        """analytics --help shows available subcommands."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["analytics", "--help"])

        assert result.exit_code == 0
        assert "status" in result.output
        assert "report" in result.output
        assert "insights" in result.output
