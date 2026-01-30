"""Base notifier abstract interface (Story 4.6).

Provides BaseNotifier abstract class that all notification channels must implement
for consistent behavior and integration with NotificationRouter.

Per FR58, NFR46.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from mt5linux.monitoring.notifier import NotificationMessage


class NotificationType(Enum):
    """Notification type enumeration (Story 4.6).

    Defines the types of notifications that can be sent through
    notification channels.

    Attributes:
        FAILURE: System failure notification.
        HIGH_LATENCY: High latency detected notification.
        TRADE_FAILURE: Trade execution failure notification.
        DRAWDOWN: Drawdown breach notification.
        DAILY_REPORT: Daily report notification.
    """

    FAILURE = "failure"
    HIGH_LATENCY = "high_latency"
    TRADE_FAILURE = "trade_failure"
    DRAWDOWN = "drawdown"
    DAILY_REPORT = "daily_report"


class BaseNotifier(ABC):
    """Abstract base class for notification channels (Story 4.6).

    All notification channels must implement this interface to ensure
    consistent behavior and easy integration with NotificationRouter.

    Thread Safety:
        Implementations MUST be thread-safe (use RLock pattern).

    Delivery Requirements (per NFR45, NFR47):
        - >95% delivery success rate
        - <5 seconds for critical notifications (severity="critical")

    Example:
        >>> class MyNotifier(BaseNotifier):
        ...     @property
        ...     def channel_name(self) -> str:
        ...         return "my_channel"
        ...
        ...     @property
        ...     def is_running(self) -> bool:
        ...         return self._running
        ...
        ...     def start(self) -> bool:
        ...         self._running = True
        ...         return True
        ...
        ...     def stop(self) -> None:
        ...         self._running = False
        ...
        ...     def send_notification(self, message: NotificationMessage) -> bool:
        ...         # Implementation here
        ...         return True
        ...
        ...     def get_status(self) -> Dict[str, Any]:
        ...         return {"running": self._running}
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return unique identifier for this channel.

        Returns:
            Channel name (e.g., "telegram", "console", "slack").
            Must be unique across all registered channels.
        """
        ...

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Return whether the notifier is running.

        Returns:
            True if running and ready to send notifications,
            False otherwise.
        """
        ...

    @abstractmethod
    def start(self) -> bool:
        """Start the notifier, initializing any connections/resources.

        Should load credentials, establish connections, and prepare
        the channel for sending notifications.

        Returns:
            True if started successfully, False otherwise.
            Returns False if channel is disabled by configuration.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the notifier, releasing resources.

        Should close connections, release resources, and set
        is_running to False.
        """
        ...

    @abstractmethod
    def send_notification(self, message: "NotificationMessage") -> bool:
        """Send notification via this channel.

        Args:
            message: NotificationMessage to send.

        Returns:
            True if sent successfully, False otherwise.
            Should return True if message was filtered by preferences
            (this is expected behavior, not a failure).
            Should return False if message is None (H3 fix).
        """
        ...

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get channel status and statistics.

        Returns:
            Dictionary with channel-specific status info.
            Should include at minimum:
            - enabled: bool
            - running: bool
            May include additional statistics like messages_sent,
            messages_failed, delivery times, etc.
        """
        ...
