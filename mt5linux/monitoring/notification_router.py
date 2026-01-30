"""Notification router for multi-channel delivery (Story 4.6).

Provides NotificationRouter class that coordinates notification delivery
across multiple channels, handling errors per-channel without affecting
other channels.

Per FR58, NFR46.
"""

from threading import RLock
from typing import Any, Dict, List

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore

from mt5linux.monitoring.base_notifier import BaseNotifier
from mt5linux.monitoring.notifier import NotificationMessage


class NotificationRouter:
    """Routes notifications to multiple channels (Story 4.6).

    Coordinates notification delivery across multiple channels,
    handling errors per-channel without affecting other channels.

    Thread-safe via RLock (consistent with monitoring module patterns).

    Example:
        >>> from mt5linux.monitoring.notifier import TelegramNotifier
        >>> from mt5linux.monitoring.console_notifier import ConsoleNotifier
        >>>
        >>> router = NotificationRouter()
        >>> router.register_channel(TelegramNotifier(config))
        >>> router.register_channel(ConsoleNotifier(ConsoleNotifierConfig(enabled=True)))
        >>> router.enable_channel("telegram")
        >>> router.enable_channel("console")
        >>> router.start_all()
        >>> results = router.send_to_all(message)
        >>> print(results)  # {"telegram": True, "console": True}
        >>> router.stop_all()
    """

    def __init__(self) -> None:
        """Initialize the notification router."""
        self._channels: Dict[str, BaseNotifier] = {}
        self._lock = RLock()
        self._enabled_channels: List[str] = []  # Order matters for delivery

    def register_channel(self, notifier: BaseNotifier) -> None:
        """Register a notification channel.

        Args:
            notifier: BaseNotifier implementation to register.

        Raises:
            ValueError: If channel with same name already registered.
        """
        with self._lock:
            name = notifier.channel_name
            if name in self._channels:
                raise ValueError(f"Channel '{name}' already registered")
            self._channels[name] = notifier
            logger.info(f"Registered notification channel: {name}")

    def unregister_channel(self, channel_name: str) -> bool:
        """Unregister a notification channel.

        Args:
            channel_name: Name of channel to unregister.

        Returns:
            True if unregistered, False if channel not found.
        """
        with self._lock:
            if channel_name not in self._channels:
                logger.warning(f"Channel '{channel_name}' not found")
                return False
            notifier = self._channels.pop(channel_name)
            if notifier.is_running:
                notifier.stop()
            if channel_name in self._enabled_channels:
                self._enabled_channels.remove(channel_name)
            logger.info(f"Unregistered notification channel: {channel_name}")
            return True

    def enable_channel(self, channel_name: str) -> bool:
        """Enable a registered channel for delivery.

        Args:
            channel_name: Name of channel to enable.

        Returns:
            True if enabled, False if channel not registered.
        """
        with self._lock:
            if channel_name not in self._channels:
                logger.error(f"Cannot enable unregistered channel: {channel_name}")
                return False
            if channel_name not in self._enabled_channels:
                self._enabled_channels.append(channel_name)
                logger.info(f"Enabled channel: {channel_name}")
            return True

    def disable_channel(self, channel_name: str) -> bool:
        """Disable a channel (stop delivery but keep registered).

        Args:
            channel_name: Name of channel to disable.

        Returns:
            True if disabled, False if channel not in enabled list.
        """
        with self._lock:
            if channel_name in self._enabled_channels:
                self._enabled_channels.remove(channel_name)
                logger.info(f"Disabled channel: {channel_name}")
                return True
            return False

    def start_all(self) -> Dict[str, bool]:
        """Start all registered channels.

        Returns:
            Dictionary of channel_name -> success status.
        """
        results: Dict[str, bool] = {}
        with self._lock:
            for name, notifier in self._channels.items():
                try:
                    results[name] = notifier.start()
                except Exception as e:
                    logger.error(f"Failed to start channel {name}: {e}")
                    results[name] = False
        return results

    def stop_all(self) -> None:
        """Stop all registered channels."""
        with self._lock:
            for name, notifier in self._channels.items():
                try:
                    notifier.stop()
                except Exception as e:
                    logger.error(f"Error stopping channel {name}: {e}")

    def send_to_all(self, message: NotificationMessage) -> Dict[str, bool]:
        """Send notification to all enabled channels.

        Errors in one channel do not affect other channels (error isolation).

        Args:
            message: NotificationMessage to send.

        Returns:
            Dictionary of channel_name -> delivery success.
            Only includes enabled channels that were attempted.
        """
        results: Dict[str, bool] = {}
        with self._lock:
            for name in self._enabled_channels:
                if name not in self._channels:
                    continue
                notifier = self._channels[name]
                try:
                    results[name] = notifier.send_notification(message)
                except Exception as e:
                    logger.error(f"Channel {name} delivery failed: {e}")
                    results[name] = False
        return results

    def send_to_channel(self, channel_name: str, message: NotificationMessage) -> bool:
        """Send notification to specific channel.

        Args:
            channel_name: Target channel name.
            message: NotificationMessage to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        with self._lock:
            if channel_name not in self._channels:
                logger.error(f"Channel '{channel_name}' not found")
                return False
            notifier = self._channels[channel_name]
            try:
                return notifier.send_notification(message)
            except Exception as e:
                logger.error(f"Channel {channel_name} delivery failed: {e}")
                return False

    def get_channel_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered channels.

        Returns:
            Dictionary of channel_name -> status dict.
            Status includes 'enabled' and 'running' plus channel-specific info.
        """
        with self._lock:
            return {
                name: {
                    "enabled": name in self._enabled_channels,
                    "running": notifier.is_running,
                    **notifier.get_status(),
                }
                for name, notifier in self._channels.items()
            }

    @property
    def available_channels(self) -> List[str]:
        """Return list of registered channel names.

        Returns:
            List of channel names that are registered.
        """
        with self._lock:
            return list(self._channels.keys())

    @property
    def enabled_channels(self) -> List[str]:
        """Return list of enabled channel names.

        Returns:
            List of channel names that are enabled for delivery.
        """
        with self._lock:
            return list(self._enabled_channels)
