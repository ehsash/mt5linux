"""Console notification channel for development/testing (Story 4.6).

Provides ConsoleNotifier class that logs notifications via loguru.
Useful for debugging and testing multi-channel setup without external services.

Per FR58, NFR46.
"""

from dataclasses import dataclass
from threading import RLock
from typing import Any, Dict, List, Optional

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore

from mt5linux.monitoring.base_notifier import BaseNotifier
from mt5linux.monitoring.notifier import NotificationMessage


@dataclass(frozen=True, slots=True)
class ConsoleNotifierConfig:
    """Configuration for console notifier (Story 4.6).

    Attributes:
        enabled: Whether console notifications are enabled (default: False).
        log_level: Log level for notifications (default: "INFO").
    """

    enabled: bool = False
    log_level: str = "INFO"


class ConsoleNotifier(BaseNotifier):
    """Console notification channel for development/testing (Story 4.6).

    Logs notifications via loguru. Useful for debugging and testing
    multi-channel setup without external service dependencies.

    Thread-safe via RLock (consistent with monitoring module patterns).

    Example:
        >>> config = ConsoleNotifierConfig(enabled=True)
        >>> notifier = ConsoleNotifier(config)
        >>> notifier.start()
        >>> notifier.send_notification(message)  # Logs to loguru
        >>> notifier.stop()
    """

    def __init__(self, config: Optional[ConsoleNotifierConfig] = None) -> None:
        """Initialize the console notifier.

        Args:
            config: Optional configuration. Defaults to disabled.
        """
        if config is None:
            config = ConsoleNotifierConfig()

        self._enabled = config.enabled
        self._log_level = config.log_level
        self._lock = RLock()
        self._running = False

        # Statistics
        self._messages_logged = 0
        self._notifications: List[NotificationMessage] = []

    @property
    def channel_name(self) -> str:
        """Return channel identifier.

        Returns:
            'console' as the channel name.
        """
        return "console"

    @property
    def is_running(self) -> bool:
        """Return whether the notifier is running.

        Returns:
            True if running and ready to log notifications.
        """
        with self._lock:
            return self._running

    def start(self) -> bool:
        """Start the console notifier.

        Returns:
            True if started successfully, False if disabled.
        """
        with self._lock:
            if not self._enabled:
                logger.info("ConsoleNotifier disabled by configuration")
                return False
            self._running = True
            logger.info("ConsoleNotifier started")
            return True

    def stop(self) -> None:
        """Stop the console notifier."""
        with self._lock:
            self._running = False
            logger.info("ConsoleNotifier stopped")

    def send_notification(self, message: NotificationMessage) -> bool:
        """Log notification to console via loguru.

        Args:
            message: NotificationMessage to log.

        Returns:
            True if logged successfully, False if not running or message is None.
        """
        # H3 fix: validate input (before lock to fail fast)
        if message is None:
            logger.warning("send_notification called with None, skipping")
            return False

        # Acquire lock for thread-safe _running check and statistics update
        with self._lock:
            if not self._running:
                logger.warning("ConsoleNotifier not running, skipping notification")
                return False

            # Reuse existing formatting from NotificationMessage
            formatted = message.format_telegram()

            # Log at configured level
            log_fn = getattr(logger, self._log_level.lower(), logger.info)
            log_fn(f"[{self.channel_name}] {formatted}")

            self._messages_logged += 1
            # Keep last 100 for testing
            self._notifications.append(message)
            if len(self._notifications) > 100:
                self._notifications.pop(0)

        return True

    def clear_statistics(self) -> None:
        """Clear accumulated statistics (H2 fix - memory management).

        Resets message count and notification list.
        Call periodically in long-running sessions to prevent memory growth.
        """
        with self._lock:
            self._messages_logged = 0
            self._notifications.clear()
            logger.debug("ConsoleNotifier statistics cleared")

    def get_status(self) -> Dict[str, Any]:
        """Get notifier status and statistics.

        Returns:
            Dictionary with status and statistics.
        """
        with self._lock:
            return {
                "enabled": self._enabled,
                "running": self._running,
                "messages_logged": self._messages_logged,
                "log_level": self._log_level,
            }

    @property
    def logged_notifications(self) -> List[NotificationMessage]:
        """Return list of logged notifications (for testing).

        Returns:
            Copy of the list of logged notifications.
        """
        with self._lock:
            return list(self._notifications)
