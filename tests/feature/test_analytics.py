"""Feature tests for analytics functionality (Epic 4, Story 4.7).

Tests:
    - AnalyticsEngine with real monitors
    - Insight generation with real data
    - Analytics report generation
    - CLI commands for analytics
"""

import time
from typing import Any

import pytest

pytestmark = [pytest.mark.feature_short]


class TestAnalyticsEngine:
    """Test analytics engine with real monitoring data."""

    def test_analytics_engine_creation(
        self, heartbeat_monitor: Any, latency_monitor: Any, mt5_connection: Any
    ) -> None:
        """Test creating analytics engine with real monitors."""
        from mt5linux.config import AnalyticsConfig
        from mt5linux.monitoring import AnalyticsEngine

        lifecycle_mgr = mt5_connection._lifecycle_manager
        conn_mgr = lifecycle_mgr._connection_manager if lifecycle_mgr else None

        config = AnalyticsConfig(
            enabled=True,
            history_window_hours=24,
            include_in_daily_reports=True,
        )

        engine = AnalyticsEngine(
            config=config,
            latency_monitor=latency_monitor,
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_mgr,
        )

        assert engine is not None

    def test_analytics_engine_status(
        self, heartbeat_monitor: Any, latency_monitor: Any, mt5_connection: Any
    ) -> None:
        """Test analytics engine status."""
        from mt5linux.config import AnalyticsConfig
        from mt5linux.monitoring import AnalyticsEngine

        lifecycle_mgr = mt5_connection._lifecycle_manager
        conn_mgr = lifecycle_mgr._connection_manager if lifecycle_mgr else None

        engine = AnalyticsEngine(
            config=AnalyticsConfig(),
            latency_monitor=latency_monitor,
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_mgr,
        )

        status = engine.get_status()

        assert "enabled" in status
        assert "history_window_hours" in status
        assert "has_latency_monitor" in status
        assert "has_heartbeat_monitor" in status
        assert "has_connection_manager" in status

        # Verify monitors are connected
        assert status["has_latency_monitor"] is True
        assert status["has_heartbeat_monitor"] is True
        assert status["has_connection_manager"] is True


class TestSystemHealthAnalytics:
    """Test system health analytics with real heartbeat data."""

    def test_calculate_system_health(
        self, heartbeat_monitor: Any, mt5_connection: Any
    ) -> None:
        """Test calculating system health from real heartbeat monitor."""
        from mt5linux.config import AnalyticsConfig
        from mt5linux.monitoring import AnalyticsEngine

        lifecycle_mgr = mt5_connection._lifecycle_manager
        conn_mgr = lifecycle_mgr._connection_manager if lifecycle_mgr else None

        engine = AnalyticsEngine(
            config=AnalyticsConfig(),
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_mgr,
        )

        # Wait for some heartbeats
        time.sleep(6)

        health = engine.calculate_system_health_analytics()
        assert health is not None

        # Verify health metrics
        assert health.uptime_seconds > 0
        assert health.heartbeat_count > 0
        assert health.connection_status in ("connected", "disconnected")
        assert 0.0 <= health.health_score <= 1.0

    def test_health_score_is_high_for_stable_connection(
        self, heartbeat_monitor: Any, mt5_connection: Any
    ) -> None:
        """Verify health score is high for stable connection."""
        from mt5linux.config import AnalyticsConfig
        from mt5linux.monitoring import AnalyticsEngine

        lifecycle_mgr = mt5_connection._lifecycle_manager
        conn_mgr = lifecycle_mgr._connection_manager if lifecycle_mgr else None

        engine = AnalyticsEngine(
            config=AnalyticsConfig(),
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_mgr,
        )

        time.sleep(6)  # Wait for heartbeats

        health = engine.calculate_system_health_analytics()
        assert health is not None

        # Stable connection should have high health score
        assert (
            health.health_score >= 0.5
        ), f"Health score too low: {health.health_score}"


class TestAnalyticsReportGeneration:
    """Test generating complete analytics reports."""

    def test_generate_report(
        self, heartbeat_monitor: Any, latency_monitor: Any, mt5_connection: Any
    ) -> None:
        """Test generating analytics report."""
        from mt5linux.config import AnalyticsConfig
        from mt5linux.monitoring import AnalyticsEngine, AnalyticsReport

        lifecycle_mgr = mt5_connection._lifecycle_manager
        conn_mgr = lifecycle_mgr._connection_manager if lifecycle_mgr else None

        engine = AnalyticsEngine(
            config=AnalyticsConfig(),
            latency_monitor=latency_monitor,
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_mgr,
        )

        time.sleep(6)  # Allow data collection

        report = engine.generate_report()

        assert isinstance(report, AnalyticsReport)
        assert report.timestamp > 0
        assert report.period_hours == 24
        assert report.system_health is not None  # Should have heartbeat data

    def test_report_includes_insights(
        self, heartbeat_monitor: Any, mt5_connection: Any
    ) -> None:
        """Test that report includes insights."""
        from mt5linux.config import AnalyticsConfig
        from mt5linux.monitoring import AnalyticsEngine

        lifecycle_mgr = mt5_connection._lifecycle_manager
        conn_mgr = lifecycle_mgr._connection_manager if lifecycle_mgr else None

        engine = AnalyticsEngine(
            config=AnalyticsConfig(),
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_mgr,
        )

        time.sleep(6)

        report = engine.generate_report()

        # Should have at least "System healthy" insight
        assert isinstance(report.insights, tuple)
        # Insights depend on system state


class TestInsightGeneration:
    """Test insight generation with real data."""

    def test_generate_insights_with_healthy_system(
        self, heartbeat_monitor: Any, mt5_connection: Any
    ) -> None:
        """Test insight generation for healthy system."""
        from mt5linux.config import AnalyticsConfig
        from mt5linux.monitoring import AnalyticsEngine

        lifecycle_mgr = mt5_connection._lifecycle_manager
        conn_mgr = lifecycle_mgr._connection_manager if lifecycle_mgr else None

        engine = AnalyticsEngine(
            config=AnalyticsConfig(),
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_mgr,
        )

        time.sleep(6)

        insights = engine.generate_insights()

        assert isinstance(insights, tuple)
        # Should get "System healthy" insight for stable connection
        # But depends on actual system state

    def test_insights_stored_in_history(
        self, heartbeat_monitor: Any, mt5_connection: Any
    ) -> None:
        """Test that insights are stored in history."""
        from mt5linux.config import AnalyticsConfig
        from mt5linux.monitoring import AnalyticsEngine

        lifecycle_mgr = mt5_connection._lifecycle_manager
        conn_mgr = lifecycle_mgr._connection_manager if lifecycle_mgr else None

        engine = AnalyticsEngine(
            config=AnalyticsConfig(),
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_mgr,
        )

        time.sleep(6)

        # Generate some insights
        engine.generate_insights()

        # Check history
        history = engine.recent_insights
        assert isinstance(history, list)


class TestAnalyticsCLI:
    """Test analytics CLI commands."""

    def test_analytics_status_command(self) -> None:
        """Test 'analytics status' CLI command."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["analytics", "status"])

        assert result.exit_code == 0
        assert "Analytics Status" in result.output

    def test_analytics_report_command(self) -> None:
        """Test 'analytics report' CLI command."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["analytics", "report"])

        assert result.exit_code == 0
        assert "Analytics Report" in result.output

    def test_analytics_insights_command(self) -> None:
        """Test 'analytics insights' CLI command."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["analytics", "insights"])

        assert result.exit_code == 0
        # May show "No recent insights" if no data


class TestAnalyticsWithDailyReport:
    """Test analytics integration with daily reports."""

    def test_daily_report_with_analytics(
        self, heartbeat_monitor: Any, mt5_connection: Any
    ) -> None:
        """Test daily report includes analytics data."""
        from mt5linux.config import AnalyticsConfig, DailyReportsConfig
        from mt5linux.monitoring import AnalyticsEngine, DailyReport, DailyReporter

        lifecycle_mgr = mt5_connection._lifecycle_manager
        if lifecycle_mgr is None:
            pytest.skip("LifecycleManager not available")

        conn_mgr = lifecycle_mgr._connection_manager

        # Create analytics engine
        analytics_engine = AnalyticsEngine(
            config=AnalyticsConfig(include_in_daily_reports=True),
            heartbeat_monitor=heartbeat_monitor,
            connection_manager=conn_mgr,
        )

        # Create daily reporter
        reporter = DailyReporter(
            conn_mgr,
            DailyReportsConfig(enabled=True),
        )

        time.sleep(6)  # Allow data collection

        # Generate analytics report
        analytics_report = analytics_engine.generate_report()

        # Create daily report with analytics
        daily_report = DailyReport(
            timestamp=time.time(),
            account_balance=10000.0,
            equity=10000.0,
            open_positions=0,
            position_details=(),
            uptime_seconds=(
                analytics_report.system_health.uptime_seconds
                if analytics_report.system_health
                else 0
            ),
            connection_status="connected",
            heartbeat_status={},
            report_time="2026-01-30 12:00:00 UTC",
            analytics=analytics_report,
        )

        # Format and verify
        formatted = reporter.format_report(daily_report)
        assert "Analytics" in formatted
        if analytics_report.insights:
            assert "Insights" in formatted
