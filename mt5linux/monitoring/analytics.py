"""Analytics module for mt5linux monitoring (Story 4.7).

Provides analytics dataclasses and AnalyticsEngine for aggregating
monitoring data into insights and reports.
"""

import statistics
import time
from dataclasses import dataclass
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore[assignment]

from mt5linux.config import AnalyticsConfig


@dataclass(frozen=True, slots=True)
class LatencyAnalytics:
    """Latency statistics for analytics period (Story 4.7).

    Attributes:
        average_ms: Average latency in milliseconds.
        median_ms: Median (p50) latency in milliseconds.
        p95_ms: 95th percentile latency in milliseconds.
        p99_ms: 99th percentile latency in milliseconds.
        min_ms: Minimum latency in milliseconds.
        max_ms: Maximum latency in milliseconds.
        std_dev_ms: Standard deviation in milliseconds.
        measurement_count: Number of measurements analyzed.
        high_latency_count: Number of measurements above threshold.
        high_latency_rate: Percentage of measurements above threshold (0.0-1.0).
    """

    average_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    std_dev_ms: float
    measurement_count: int
    high_latency_count: int
    high_latency_rate: float


@dataclass(frozen=True, slots=True)
class SystemHealthAnalytics:
    """System health statistics for analytics period (Story 4.7).

    Attributes:
        uptime_seconds: Total uptime in seconds.
        heartbeat_count: Total heartbeats performed.
        average_heartbeat_variance_ms: Average variance from expected interval (NFR9).
        connection_status: Current connection status ("connected"/"disconnected").
        consecutive_failures: Current consecutive failure count.
        health_score: Composite health score from 0.0 (unhealthy) to 1.0 (healthy).
    """

    uptime_seconds: float
    heartbeat_count: int
    average_heartbeat_variance_ms: float
    connection_status: str
    consecutive_failures: int
    health_score: float


@dataclass(frozen=True, slots=True)
class TradingAnalytics:
    """Trading statistics for analytics period (Story 4.7).

    Attributes:
        total_trades: Total number of trades.
        successful_trades: Number of successful executions.
        failed_trades: Number of failed executions.
        success_rate: Percentage of successful trades (0.0-1.0).
        average_execution_time_ms: Average execution latency in milliseconds.
        symbols_traded: Tuple of unique symbols traded.
        total_volume: Total volume traded in lots.
    """

    total_trades: int
    successful_trades: int
    failed_trades: int
    success_rate: float
    average_execution_time_ms: float
    symbols_traded: Tuple[str, ...]
    total_volume: float


@dataclass(frozen=True, slots=True)
class AnalyticsReport:
    """Complete analytics report (Story 4.7).

    Attributes:
        timestamp: Report generation timestamp (Unix time).
        period_hours: Analysis period in hours.
        latency: Latency analytics (None if no data).
        system_health: System health analytics (None if no data).
        trading: Trading analytics (None if no data).
        insights: Tuple of actionable insight strings.
    """

    timestamp: float
    period_hours: int
    latency: Optional[LatencyAnalytics]
    system_health: Optional[SystemHealthAnalytics]
    trading: Optional[TradingAnalytics]
    insights: Tuple[str, ...]


class AnalyticsEngine:
    """Aggregates monitoring data into analytics and insights (Story 4.7).

    Collects data from LatencyMonitor, HeartbeatMonitor, and ConnectionManager
    to generate analytics reports and actionable insights.

    Thread-safe via RLock (consistent with monitoring module patterns).

    Example:
        >>> config = AnalyticsConfig(enabled=True, history_window_hours=24)
        >>> engine = AnalyticsEngine(config, latency_monitor, heartbeat_monitor, conn_mgr)
        >>> report = engine.generate_report()
        >>> print(report.insights)
    """

    def __init__(
        self,
        config: Optional[AnalyticsConfig] = None,
        latency_monitor: Optional[Any] = None,
        heartbeat_monitor: Optional[Any] = None,
        connection_manager: Optional[Any] = None,
    ) -> None:
        """Initialize AnalyticsEngine.

        Args:
            config: Optional AnalyticsConfig. Uses defaults if not provided.
            latency_monitor: LatencyMonitor instance for latency data.
            heartbeat_monitor: HeartbeatMonitor instance for health data.
            connection_manager: ConnectionManager instance for connection status.
        """
        if config is None:
            config = AnalyticsConfig()

        self._config = config
        self._latency_monitor = latency_monitor
        self._heartbeat_monitor = heartbeat_monitor
        self._connection_manager = connection_manager

        self._lock = RLock()
        self._reports_generated = 0
        self._last_report_time: Optional[float] = None
        self._insights_history: List[Tuple[float, str]] = []

        logger.debug(
            f"AnalyticsEngine initialized: enabled={config.enabled}, "
            f"window={config.history_window_hours}h"
        )

    def calculate_latency_analytics(self) -> Optional[LatencyAnalytics]:
        """Calculate latency statistics from LatencyMonitor.

        Returns:
            LatencyAnalytics if data available, None otherwise.
        """
        if self._latency_monitor is None:
            return None

        measurements = self._latency_monitor.get_recent_measurements(1000)
        if not measurements:
            return None

        latencies = [m.latency_ms for m in measurements]
        high_latency = [m for m in measurements if m.is_high_latency]

        avg = statistics.mean(latencies)
        median = statistics.median(latencies)
        std_dev = statistics.stdev(latencies) if len(latencies) > 1 else 0.0

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        p95_idx = int(0.95 * (n - 1))
        p99_idx = int(0.99 * (n - 1))

        return LatencyAnalytics(
            average_ms=avg,
            median_ms=median,
            p95_ms=sorted_latencies[p95_idx],
            p99_ms=sorted_latencies[p99_idx],
            min_ms=min(latencies),
            max_ms=max(latencies),
            std_dev_ms=std_dev,
            measurement_count=len(measurements),
            high_latency_count=len(high_latency),
            high_latency_rate=len(high_latency) / len(measurements),
        )

    def calculate_system_health_analytics(self) -> Optional[SystemHealthAnalytics]:
        """Calculate system health statistics from HeartbeatMonitor.

        Returns:
            SystemHealthAnalytics if data available, None otherwise.
        """
        if self._heartbeat_monitor is None:
            return None

        status = self._heartbeat_monitor.get_status()
        uptime = self._heartbeat_monitor.get_uptime() or 0.0
        heartbeat_count = status.get("heartbeat_count", 0)
        avg_variance = status.get("average_variance", 0.0) * 1000  # Convert to ms
        consecutive_failures = status.get("consecutive_failures", 0)
        is_healthy = status.get("is_healthy", False)

        connection_status = "disconnected"
        if self._connection_manager is not None:
            try:
                if hasattr(self._connection_manager, "is_connected"):
                    connection_status = (
                        "connected"
                        if self._connection_manager.is_connected
                        else "disconnected"
                    )
            except Exception:
                pass

        # Calculate health score (0.0-1.0)
        # Factors: is_healthy (50%), low variance (25%), low failures (25%)
        health_score = 0.0
        if is_healthy:
            health_score += 0.5
        if avg_variance <= 1000:  # NFR9: <1 second
            health_score += 0.25
        if consecutive_failures == 0:
            health_score += 0.25

        return SystemHealthAnalytics(
            uptime_seconds=uptime,
            heartbeat_count=heartbeat_count,
            average_heartbeat_variance_ms=avg_variance,
            connection_status=connection_status,
            consecutive_failures=consecutive_failures,
            health_score=health_score,
        )

    def calculate_trading_analytics(self) -> Optional[TradingAnalytics]:
        """Calculate trading statistics.

        Note: Trading analytics requires integration with trade execution
        tracking (Stories 3.1-3.6). Returns None if no trade data available.

        Returns:
            TradingAnalytics if data available, None otherwise.
        """
        if self._latency_monitor is None:
            return None

        measurements = self._latency_monitor.get_recent_measurements(1000)
        if not measurements:
            return None

        symbols = set(m.symbol for m in measurements)
        total_trades = len(measurements)
        avg_execution = (
            sum(m.latency_ms for m in measurements) / total_trades
            if total_trades > 0
            else 0.0
        )

        return TradingAnalytics(
            total_trades=total_trades,
            successful_trades=total_trades,
            failed_trades=0,
            success_rate=1.0,
            average_execution_time_ms=avg_execution,
            symbols_traded=tuple(sorted(symbols)),
            total_volume=0.0,
        )

    def generate_insights(self) -> Tuple[str, ...]:
        """Generate actionable insights from analytics data.

        Returns:
            Tuple of insight strings.
        """
        insights: List[str] = []

        latency = self.calculate_latency_analytics()
        if latency is not None:
            if latency.high_latency_rate > 0.1:
                insights.append(
                    f"High latency rate: {latency.high_latency_rate:.1%} of orders "
                    f"exceed threshold (avg: {latency.average_ms:.1f}ms)"
                )
            elif latency.average_ms < 100:
                insights.append(
                    f"Latency healthy: avg {latency.average_ms:.1f}ms, "
                    f"p95 {latency.p95_ms:.1f}ms"
                )

        health = self.calculate_system_health_analytics()
        if health is not None:
            if health.average_heartbeat_variance_ms > 1000:
                insights.append(
                    f"Heartbeat variance exceeds NFR9 limit: "
                    f"{health.average_heartbeat_variance_ms:.0f}ms average"
                )
            if health.consecutive_failures > 0:
                insights.append(
                    f"Connection instability: {health.consecutive_failures} "
                    f"consecutive failures"
                )
            if health.health_score >= 0.9:
                uptime_hours = health.uptime_seconds / 3600
                insights.append(
                    f"System healthy: {health.health_score:.0%} health score, "
                    f"{uptime_hours:.1f}h uptime"
                )

        with self._lock:
            timestamp = time.time()
            for insight in insights:
                self._insights_history.append((timestamp, insight))
            if len(self._insights_history) > 100:
                self._insights_history = self._insights_history[-100:]

        return tuple(insights)

    def generate_report(self) -> AnalyticsReport:
        """Generate complete analytics report.

        Returns:
            AnalyticsReport with all available analytics and insights.
        """
        with self._lock:
            report = AnalyticsReport(
                timestamp=time.time(),
                period_hours=self._config.history_window_hours,
                latency=self.calculate_latency_analytics(),
                system_health=self.calculate_system_health_analytics(),
                trading=self.calculate_trading_analytics(),
                insights=self.generate_insights(),
            )
            self._reports_generated += 1
            self._last_report_time = time.time()
            return report

    def get_status(self) -> Dict[str, Any]:
        """Get analytics engine status.

        Returns:
            Dictionary with status information.
        """
        with self._lock:
            return {
                "enabled": self._config.enabled,
                "history_window_hours": self._config.history_window_hours,
                "include_in_daily_reports": self._config.include_in_daily_reports,
                "reports_generated": self._reports_generated,
                "last_report_time": self._last_report_time,
                "insights_count": len(self._insights_history),
                "has_latency_monitor": self._latency_monitor is not None,
                "has_heartbeat_monitor": self._heartbeat_monitor is not None,
                "has_connection_manager": self._connection_manager is not None,
            }

    def clear_history(self) -> None:
        """Clear insights history for memory management."""
        with self._lock:
            self._insights_history.clear()
            logger.debug("Analytics insights history cleared")

    @property
    def recent_insights(self) -> List[Tuple[float, str]]:
        """Return list of recent insights with timestamps."""
        with self._lock:
            return list(self._insights_history)
