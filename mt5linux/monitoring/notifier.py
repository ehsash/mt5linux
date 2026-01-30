"""Telegram notification sender module (Story 4.4, 4.6).

Provides TelegramNotifier class for sending Telegram notifications for system
failures, high latency, trade failures, drawdown breaches, and daily reports.

Per FR54-FR57, NFR44-NFR47.

Story 4.6: TelegramNotifier now implements BaseNotifier interface for
multi-channel notification support.
"""

import asyncio
import time
from dataclasses import dataclass
from threading import RLock
from typing import Any, Dict, List, Optional

try:
    import keyring
except ImportError:
    keyring = None  # type: ignore

try:
    from telegram import Bot
except ImportError:
    Bot = None  # type: ignore

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore

from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
from mt5linux.monitoring.base_notifier import BaseNotifier


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    """A notification message to be sent (Story 4.4).

    Attributes:
        message_type: Type of notification (failure, high_latency, trade_failure,
            drawdown, daily_report).
        title: Notification title.
        body: Notification body text.
        timestamp: Unix timestamp when event occurred.
        severity: Severity level (critical, warning, info).
    """

    message_type: str
    title: str
    body: str
    timestamp: float
    severity: str  # "critical", "warning", "info"

    def format_telegram(self) -> str:
        """Format as Telegram HTML message."""
        severity_emoji = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "🔵",
        }
        emoji = severity_emoji.get(self.severity, "⚪")
        return f"{emoji} <b>{self.title}</b>\n\n{self.body}"


class TelegramNotifier(BaseNotifier):
    """Telegram notification sender (Story 4.4, 4.6).

    Sends notifications to Telegram for system events including failures,
    high latency, trade failures, drawdown breaches, and daily reports.

    Implements BaseNotifier interface for multi-channel support (Story 4.6).

    Thread-safe via RLock pattern (consistent with other monitoring modules).

    Example:
        >>> config = TelegramConfig(enabled=True, chat_id="123456789")
        >>> notifier = TelegramNotifier(config=config)
        >>> notifier.start()  # Loads bot token from keyring
        >>> notifier.notify_failure(failure_info)
        >>> notifier.stop()
    """

    @property
    def channel_name(self) -> str:
        """Return channel identifier (Story 4.6).

        Returns:
            'telegram' as the channel name.
        """
        return "telegram"

    def __init__(self, config: Optional[TelegramConfig] = None) -> None:
        """Initialize the Telegram notifier.

        Args:
            config: Telegram configuration. If None, uses default (disabled).
        """
        if config is None:
            config = TelegramConfig()

        self._enabled = config.enabled
        self._chat_id = config.chat_id
        self._retry_count = config.retry_count
        self._retry_delay_secs = config.retry_delay_secs
        self._delivery_timeout_secs = config.delivery_timeout_secs

        self._bot_token: Optional[str] = None
        self._bot: Optional[Any] = None  # telegram.Bot
        self._lock = RLock()
        self._running = False

        # Statistics
        self._messages_sent = 0
        self._messages_failed = 0
        self._retry_count_total = 0
        self._delivery_times: List[float] = []
        self._last_message_time: Optional[float] = None

        # Notification preferences (Story 4.5)
        self._preferences: Optional[NotificationPreferencesConfig] = None

    @property
    def is_enabled(self) -> bool:
        """Return whether Telegram notifications are enabled."""
        return self._enabled

    @property
    def is_running(self) -> bool:
        """Return whether the notifier is running."""
        with self._lock:
            return self._running

    def set_preferences(self, preferences: NotificationPreferencesConfig) -> None:
        """Set notification preferences for filtering (Story 4.5).

        Args:
            preferences: Notification preferences configuration.
        """
        with self._lock:
            self._preferences = preferences
            logger.debug("Notification preferences updated")

    def _should_send(
        self, message_type: str, current_time: Optional[str] = None
    ) -> bool:
        """Check if notification should be sent based on preferences (Story 4.5).

        Args:
            message_type: Type of notification (failure, high_latency, trade_failure,
                drawdown, daily_report).
            current_time: Current time in HH:MM format (for testing). If None,
                uses actual current time.

        Returns:
            True if notification should be sent, False if filtered out.
        """
        if self._preferences is None:
            return True  # No preferences = send all

        # Check quiet hours first
        if self._preferences.is_quiet_hours(current_time):
            logger.debug(f"Notification {message_type} suppressed: quiet hours")
            return False

        # Check type-specific enable flags
        type_checks = {
            "failure": self._preferences.failure_notifications,
            "high_latency": self._preferences.high_latency_notifications,
            "trade_failure": self._preferences.trade_failure_notifications,
            "drawdown": self._preferences.drawdown_notifications,
            "daily_report": self._preferences.daily_report_notifications,
        }

        if message_type in type_checks and not type_checks[message_type]:
            logger.debug(
                f"Notification {message_type} suppressed: disabled by preference"
            )
            return False

        return True

    def start(self) -> bool:
        """Start the notifier, loading credentials from keyring.

        Returns:
            True if started successfully, False otherwise.
        """
        with self._lock:
            if not self._enabled:
                logger.info("TelegramNotifier disabled by configuration")
                return False

            if keyring is None:
                logger.warning("keyring library not available, cannot load bot token")
                return False

            # Load bot token from keyring
            try:
                self._bot_token = keyring.get_password("mt5linux", "telegram_bot_token")
            except Exception as e:
                logger.warning(f"Failed to load bot token from keyring: {e}")
                return False

            if not self._bot_token:
                logger.warning("Telegram bot token not found in keyring")
                return False

            if Bot is None:
                logger.warning("python-telegram-bot library not available")
                return False

            # Create Bot instance
            try:
                self._bot = Bot(token=self._bot_token)
                self._running = True
                logger.info("TelegramNotifier started")
                return True
            except Exception as e:
                logger.error(f"Failed to create Telegram Bot: {e}")
                return False

    def stop(self) -> None:
        """Stop the notifier."""
        with self._lock:
            self._running = False
            self._bot = None
            logger.info("TelegramNotifier stopped")

    async def _send_message_async(self, text: str) -> bool:
        """Send message via Telegram API (async).

        Args:
            text: Message text to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._bot:
            return False

        try:
            # Enforce delivery timeout per NFR47 (H1 fix)
            await asyncio.wait_for(
                self._bot.send_message(
                    chat_id=self._chat_id,
                    text=text,
                    parse_mode="HTML",
                ),
                timeout=self._delivery_timeout_secs,
            )
            return True
        except asyncio.TimeoutError:
            logger.error(
                f"Telegram send_message timed out after {self._delivery_timeout_secs}s"
            )
            return False
        except Exception as e:
            logger.error(f"Telegram send_message failed: {e}")
            return False

    def _send_message_sync(self, text: str) -> bool:
        """Send message synchronously (thread-safe).

        Creates a new event loop per call to avoid conflicts with existing loops.
        This pattern is safe for notification volumes (few messages/day).
        For high-throughput scenarios, consider a persistent background loop.

        Args:
            text: Message text to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            # M1: Create fresh loop per call - safe for low-volume notifications
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._send_message_async(text))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Telegram sync send failed: {e}")
            return False

    def send_notification(self, message: NotificationMessage) -> bool:
        """Send notification with retry logic.

        Args:
            message: Notification message to send.

        Returns:
            True if sent successfully, False if failed or filtered out.
        """
        if not self._running:
            logger.warning("TelegramNotifier not running, skipping notification")
            return False

        # Check if notification should be sent based on preferences (Story 4.5)
        if not self._should_send(message.message_type):
            logger.info(f"Notification {message.message_type} filtered by preferences")
            return True  # Return True as this is expected behavior, not a failure

        start_time = time.time()
        text = message.format_telegram()

        for attempt in range(self._retry_count + 1):
            if attempt > 0:
                # Exponential backoff: delay * 2^(attempt-1)
                delay = self._retry_delay_secs * (2 ** (attempt - 1))
                logger.debug(
                    f"Retry attempt {attempt}/{self._retry_count}, waiting {delay}s"
                )
                time.sleep(delay)
                with self._lock:
                    self._retry_count_total += 1

            if self._send_message_sync(text):
                delivery_time = (time.time() - start_time) * 1000
                with self._lock:
                    self._messages_sent += 1
                    self._delivery_times.append(delivery_time)
                    self._last_message_time = time.time()
                logger.info(f"Notification sent in {delivery_time:.2f}ms")
                return True

        with self._lock:
            self._messages_failed += 1
        logger.error(f"Notification failed after {self._retry_count + 1} attempts")
        return False

    def notify_failure(self, failure_info: Any) -> bool:
        """Send notification for system failure.

        Args:
            failure_info: HeartbeatFailureInfo or similar with failure details.

        Returns:
            True if notification sent, False otherwise.
        """
        if not self._running:
            return False

        # H3 fix: validate input
        if failure_info is None:
            logger.warning("notify_failure called with None, skipping")
            return False

        title = "⚠️ System Failure"
        body_parts = []

        if hasattr(failure_info, "failure_type"):
            body_parts.append(f"Type: {failure_info.failure_type}")
        if hasattr(failure_info, "message"):
            body_parts.append(f"Message: {failure_info.message}")

        body = "\n".join(body_parts) if body_parts else "System failure detected"
        timestamp = getattr(failure_info, "timestamp", time.time())

        message = NotificationMessage(
            message_type="failure",
            title=title,
            body=body,
            timestamp=timestamp,
            severity="critical",
        )
        return self.send_notification(message)

    def notify_high_latency(self, alert: Any) -> bool:
        """Send notification for high latency.

        Args:
            alert: LatencyAlert or similar with latency details.

        Returns:
            True if notification sent, False otherwise.
        """
        if not self._running:
            return False

        # H3 fix: validate input
        if alert is None:
            logger.warning("notify_high_latency called with None, skipping")
            return False

        title = "⏱️ High Latency Detected"
        body_parts = []

        if hasattr(alert, "latency_ms"):
            body_parts.append(f"Latency: {alert.latency_ms:.1f}ms")
        if hasattr(alert, "threshold_ms"):
            body_parts.append(f"Threshold: {alert.threshold_ms:.1f}ms")

        body = "\n".join(body_parts) if body_parts else "High latency detected"
        timestamp = getattr(alert, "timestamp", time.time())

        message = NotificationMessage(
            message_type="high_latency",
            title=title,
            body=body,
            timestamp=timestamp,
            severity="warning",
        )
        return self.send_notification(message)

    def notify_trade_failure(self, failure_info: Any) -> bool:
        """Send notification for trade execution failure.

        Args:
            failure_info: TradeFailureInfo or similar with trade failure details.
                Per FR68, sensitive data is excluded.

        Returns:
            True if notification sent, False otherwise.
        """
        if not self._running:
            return False

        # H3 fix: validate input
        if failure_info is None:
            logger.warning("notify_trade_failure called with None, skipping")
            return False

        title = "❌ Trade Execution Failed"
        body_parts = []

        if hasattr(failure_info, "symbol"):
            body_parts.append(f"Symbol: {failure_info.symbol}")
        if hasattr(failure_info, "order_type"):
            body_parts.append(f"Type: {failure_info.order_type}")
        if hasattr(failure_info, "error_code"):
            body_parts.append(f"Error: {failure_info.error_code}")
        # Per FR68: Don't include sensitive data like lot size, price, etc.

        body = "\n".join(body_parts) if body_parts else "Trade execution failed"
        timestamp = getattr(failure_info, "timestamp", time.time())

        message = NotificationMessage(
            message_type="trade_failure",
            title=title,
            body=body,
            timestamp=timestamp,
            severity="critical",
        )
        return self.send_notification(message)

    def notify_drawdown_breach(self, drawdown_info: Any) -> bool:
        """Send notification for drawdown breach.

        Args:
            drawdown_info: DrawdownBreachInfo or similar with drawdown details.

        Returns:
            True if notification sent, False otherwise.
        """
        if not self._running:
            return False

        # H3 fix: validate input
        if drawdown_info is None:
            logger.warning("notify_drawdown_breach called with None, skipping")
            return False

        title = "📉 Drawdown Breach"
        body_parts = []

        if hasattr(drawdown_info, "current_drawdown"):
            pct = drawdown_info.current_drawdown * 100
            body_parts.append(f"Current: {pct:.1f}%")
        if hasattr(drawdown_info, "threshold"):
            pct = drawdown_info.threshold * 100
            body_parts.append(f"Threshold: {pct:.1f}%")

        body = "\n".join(body_parts) if body_parts else "Drawdown threshold breached"
        timestamp = getattr(drawdown_info, "timestamp", time.time())

        message = NotificationMessage(
            message_type="drawdown",
            title=title,
            body=body,
            timestamp=timestamp,
            severity="critical",
        )
        return self.send_notification(message)

    def notify_daily_report(self, report: Any) -> bool:
        """Send daily report notification.

        Args:
            report: DailyReport or similar with report details.

        Returns:
            True if notification sent, False otherwise.
        """
        if not self._running:
            return False

        # H3 fix: validate input
        if report is None:
            logger.warning("notify_daily_report called with None, skipping")
            return False

        title = "📊 Daily Report"
        body_parts = []

        if hasattr(report, "report_date"):
            body_parts.append(f"Date: {report.report_date}")
        if hasattr(report, "summary"):
            body_parts.append(f"\n{report.summary}")

        body = "\n".join(body_parts) if body_parts else "Daily report generated"
        timestamp = getattr(report, "timestamp", time.time())

        message = NotificationMessage(
            message_type="daily_report",
            title=title,
            body=body,
            timestamp=timestamp,
            severity="info",
        )
        return self.send_notification(message)

    def clear_statistics(self) -> None:
        """Clear accumulated statistics (H2 fix - memory management).

        Resets message counts, delivery times, and retry counts.
        Call periodically in long-running sessions to prevent memory growth.
        """
        with self._lock:
            self._messages_sent = 0
            self._messages_failed = 0
            self._retry_count_total = 0
            self._delivery_times.clear()
            self._last_message_time = None
            logger.debug("TelegramNotifier statistics cleared")

    def get_status(self) -> Dict[str, Any]:
        """Get notifier status and statistics.

        Returns:
            Dictionary with status and statistics.
        """
        with self._lock:
            configured = bool(self._chat_id)
            avg_delivery = (
                sum(self._delivery_times) / len(self._delivery_times)
                if self._delivery_times
                else 0.0
            )
            max_delivery = max(self._delivery_times) if self._delivery_times else 0.0

            return {
                "enabled": self._enabled,
                "configured": configured,
                "bot_token_available": bool(self._bot_token),
                "running": self._running,
                "messages_sent": self._messages_sent,
                "messages_failed": self._messages_failed,
                "last_message_time": self._last_message_time,
                "average_delivery_time_ms": avg_delivery,
                "max_delivery_time_ms": max_delivery,
                "retry_count_total": self._retry_count_total,
            }
