"""Daily report generation module (Story 4.2, 4.7).

This module provides the DailyReporter class for generating scheduled daily
reports with account status and system metrics.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore[assignment]

from mt5linux.config import DailyReportsConfig

if TYPE_CHECKING:
    from mt5linux.monitoring.analytics import AnalyticsReport

# MT5 position type constants (ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1)
MT5_POSITION_TYPE_BUY = 0
MT5_POSITION_TYPE_SELL = 1


@dataclass(frozen=True, slots=True)
class PositionInfo:
    """Simplified position information for reports.

    Attributes:
        symbol: Trading symbol (e.g., "EURUSD").
        volume: Position volume in lots.
        profit: Current profit/loss in account currency.
        type: Position type ("buy" or "sell").
    """

    symbol: str
    volume: float
    profit: float
    type: str  # "buy" or "sell"


@dataclass(frozen=True, slots=True)
class DailyReport:
    """Daily report content (Story 4.2, 4.7).

    Contains all metrics for daily report per FR51.

    Attributes:
        timestamp: Report generation timestamp (Unix time).
        account_balance: Current account balance, None if unavailable.
        equity: Current account equity, None if unavailable.
        open_positions: Number of open positions.
        position_details: Tuple of PositionInfo for each position.
        uptime_seconds: Time since system started.
        connection_status: Current connection state ("connected"/"disconnected").
        heartbeat_status: Status dict from HeartbeatMonitor.
        report_time: Human-readable formatted time string.
        analytics: Optional AnalyticsReport (Story 4.7).
    """

    timestamp: float
    account_balance: Optional[float]
    equity: Optional[float]
    open_positions: int
    position_details: Tuple[PositionInfo, ...]
    uptime_seconds: float
    connection_status: str
    heartbeat_status: Dict[str, Any]
    report_time: str
    analytics: Optional["AnalyticsReport"] = None


class DailyReporter:
    """Daily report generator with scheduled reporting (Story 4.2).

    Generates daily reports at configured times containing account status
    and system metrics. Uses APScheduler for timezone-aware scheduling.

    Attributes:
        _connection_manager: Reference to ConnectionManager for MT5 API access.
        _scheduler: APScheduler BackgroundScheduler instance.
        _enabled: Whether reporting is enabled.
        _times: Configured report times as tuple of HH:MM strings.
        _timezone: Configured timezone string.
        _report_callbacks: List of callbacks to invoke on report generation.
        _lock: RLock for thread-safe operations.
        _reports_generated_count: Number of reports generated.
        _last_report_time: Timestamp of last report generation.
        _start_time: Timestamp when reporter was started.
    """

    def __init__(
        self,
        connection_manager: Any,
        config: Optional[DailyReportsConfig] = None,
        heartbeat_monitor: Optional[Any] = None,
    ) -> None:
        """Initialize DailyReporter.

        Args:
            connection_manager: ConnectionManager instance for MT5 API access.
            config: Optional DailyReportsConfig. Uses defaults if not provided.
            heartbeat_monitor: Optional HeartbeatMonitor for status information.
        """
        self._connection_manager = connection_manager
        self._heartbeat_monitor = heartbeat_monitor

        # Load config or use defaults
        if config is None:
            config = DailyReportsConfig()

        self._enabled = config.enabled
        self._times = config.times
        self._timezone = config.timezone

        # Initialize scheduler with timezone
        tz = pytz.timezone(self._timezone)
        self._scheduler = BackgroundScheduler(timezone=tz)

        # Callback system
        self._report_callbacks: List[Callable[[DailyReport], None]] = []

        # Thread safety
        self._lock = RLock()

        # Statistics
        self._reports_generated_count = 0
        self._last_report_time: Optional[float] = None
        self._start_time: Optional[float] = None

        logger.debug(
            f"DailyReporter initialized: enabled={self._enabled}, "
            f"times={self._times}, timezone={self._timezone}"
        )

    def start(self) -> None:
        """Start the reporter and schedule jobs.

        If reporting is disabled, the scheduler is not started.
        """
        with self._lock:
            self._start_time = time.time()

            if not self._enabled:
                logger.info("DailyReporter disabled, not starting scheduler")
                return

            # Add cron job for each configured time
            for time_str in self._times:
                hour, minute = map(int, time_str.split(":"))
                self._scheduler.add_job(
                    self._generate_and_notify,
                    CronTrigger(
                        hour=hour,
                        minute=minute,
                        timezone=pytz.timezone(self._timezone),
                    ),
                    id=f"daily_report_{time_str}",
                    replace_existing=True,
                )
                logger.debug(f"Scheduled daily report at {time_str}")

            self._scheduler.start()
            logger.info(
                f"DailyReporter started with {len(self._times)} scheduled reports"
            )

    def stop(self) -> None:
        """Stop the reporter and shutdown scheduler."""
        with self._lock:
            if self._scheduler.running:
                self._scheduler.shutdown(wait=False)
                logger.info("DailyReporter stopped")

    def on_report_generated(self, callback: Callable[[DailyReport], None]) -> None:
        """Register callback for report generation notifications.

        Args:
            callback: Function to call with DailyReport when generated.
        """
        with self._lock:
            self._report_callbacks.append(callback)
            logger.debug(f"Registered report callback: {callback}")

    def unregister_report_callback(
        self, callback: Callable[[DailyReport], None]
    ) -> None:
        """Unregister a previously registered report callback.

        Args:
            callback: The callback to unregister.
        """
        with self._lock:
            if callback in self._report_callbacks:
                self._report_callbacks.remove(callback)
                logger.debug(f"Unregistered report callback: {callback}")

    def get_status(self) -> Dict[str, Any]:
        """Get current reporter status.

        Returns:
            Dictionary containing reporter status information.
        """
        with self._lock:
            return {
                "enabled": self._enabled,
                "times": self._times,
                "timezone": self._timezone,
                "scheduler_running": self._scheduler.running,
                "reports_generated_count": self._reports_generated_count,
                "last_report_time": self._last_report_time,
                "next_scheduled_time": self._get_next_scheduled_time(),
            }

    @property
    def is_enabled(self) -> bool:
        """Return whether reporting is enabled."""
        return self._enabled

    def get_next_report_time(self) -> Optional[datetime]:
        """Get the next scheduled report time.

        Returns:
            Datetime of next scheduled report, or None if not scheduled.
        """
        return self._get_next_scheduled_time()

    def _get_next_scheduled_time(self) -> Optional[datetime]:
        """Internal helper to get next scheduled time."""
        if not self._scheduler.running:
            return None
        jobs = self._scheduler.get_jobs()
        if not jobs:
            return None
        # Get the earliest next run time
        next_times = [job.next_run_time for job in jobs if job.next_run_time]
        if not next_times:
            return None
        return min(next_times)

    def _generate_and_notify(self) -> None:
        """Generate report and notify all callbacks."""
        report = self._generate_report()
        if report is None:
            return

        with self._lock:
            self._reports_generated_count += 1
            self._last_report_time = time.time()

            # Notify all callbacks
            for callback in self._report_callbacks:
                try:
                    callback(report)
                except Exception as e:
                    logger.error(
                        f"Error in report callback {callback}: {e}",
                        exc_info=True,
                    )

    def _generate_report(self) -> Optional[DailyReport]:
        """Generate daily report with all metrics.

        Returns:
            DailyReport instance, or None if generation fails.
        """
        try:
            # Get account info
            balance: Optional[float] = None
            equity: Optional[float] = None
            try:
                account = self._connection_manager.mt5.account_info()
                if account:
                    balance = account.balance
                    equity = account.equity
            except Exception as e:
                logger.warning(f"Failed to get account info: {e}")

            # Get positions
            positions_count = 0
            position_details: List[PositionInfo] = []
            try:
                positions_count = self._connection_manager.mt5.positions_total() or 0
                positions = self._connection_manager.mt5.positions_get()
                if positions:
                    position_details = [
                        PositionInfo(
                            symbol=p.symbol,
                            volume=p.volume,
                            profit=p.profit,
                            type="buy" if p.type == MT5_POSITION_TYPE_BUY else "sell",
                        )
                        for p in positions
                    ]
            except Exception as e:
                logger.warning(f"Failed to get positions: {e}")

            # Get monitoring status
            heartbeat_status: Dict[str, Any] = {}
            uptime = 0.0
            if self._heartbeat_monitor:
                try:
                    heartbeat_status = self._heartbeat_monitor.get_status()
                    uptime = self._heartbeat_monitor.get_uptime() or 0.0
                except Exception as e:
                    logger.warning(f"Failed to get heartbeat status: {e}")
            elif self._start_time:
                uptime = time.time() - self._start_time

            # Get connection status
            connection_status = "disconnected"
            try:
                if hasattr(self._connection_manager, "is_connected"):
                    connection_status = (
                        "connected"
                        if self._connection_manager.is_connected
                        else "disconnected"
                    )
            except Exception:
                pass

            # Generate timezone-aware report time (AC #3)
            tz = pytz.timezone(self._timezone)
            report_time_dt = datetime.now(tz)

            report = DailyReport(
                timestamp=time.time(),
                account_balance=balance,
                equity=equity,
                open_positions=positions_count,
                position_details=tuple(position_details),
                uptime_seconds=uptime,
                connection_status=connection_status,
                heartbeat_status=heartbeat_status,
                report_time=report_time_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            )

            logger.info(f"Daily report generated: {report.report_time}")
            return report

        except Exception as e:
            logger.error(f"Failed to generate daily report: {e}", exc_info=True)
            return None

    def format_report(self, report: DailyReport) -> str:
        """Format report for Telegram notification.

        Args:
            report: DailyReport instance to format.

        Returns:
            Human-readable formatted string.
        """
        lines = [
            "📊 Daily Trading Report",
            f"🕐 {report.report_time}",
            "",
            "💰 Account Status:",
        ]

        if report.account_balance is not None:
            lines.append(f"  Balance: {report.account_balance:.2f}")
        else:
            lines.append("  Balance: N/A")

        if report.equity is not None:
            lines.append(f"  Equity: {report.equity:.2f}")
        else:
            lines.append("  Equity: N/A")

        lines.extend(["", f"📈 Open Positions: {report.open_positions}"])

        if report.position_details:
            for pos in report.position_details:
                emoji = "🟢" if pos.profit >= 0 else "🔴"
                lines.append(
                    f"  {emoji} {pos.symbol}: {pos.volume} lots, P/L: {pos.profit:.2f}"
                )

        lines.extend(
            [
                "",
                "🔧 System Status:",
                f"  Connection: {report.connection_status}",
                f"  Uptime: {self._format_uptime(report.uptime_seconds)}",
            ]
        )

        if report.heartbeat_status:
            is_healthy = report.heartbeat_status.get("is_healthy", False)
            lines.append(f"  Heartbeat: {'Healthy' if is_healthy else 'Unhealthy'}")

        # Story 4.7: Add analytics section if present
        if report.analytics is not None:
            lines.extend(["", "📊 Analytics:"])

            if report.analytics.latency:
                lat = report.analytics.latency
                lines.append(
                    f"  Latency: avg {lat.average_ms:.1f}ms, "
                    f"p95 {lat.p95_ms:.1f}ms ({lat.measurement_count} samples)"
                )

            if report.analytics.system_health:
                health = report.analytics.system_health
                lines.append(
                    f"  Health: {health.health_score:.0%} score, "
                    f"{health.heartbeat_count} heartbeats"
                )

            if report.analytics.insights:
                lines.extend(["", "💡 Insights:"])
                for insight in report.analytics.insights[:3]:  # Top 3 insights
                    lines.append(f"  • {insight}")

        return "\n".join(lines)

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format uptime seconds to human-readable string."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
