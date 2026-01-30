"""Notification configuration manager module (Story 4.5).

Provides NotificationConfigManager class for managing notification channels
and preferences. Handles Telegram setup, credential storage, and preference
configuration.

Per FR58.
"""

import re
from threading import RLock
from typing import Any, Dict, Optional, Tuple

try:
    import keyring
except ImportError:
    keyring = None  # type: ignore

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore

from mt5linux.config import (
    Config,
    NotificationPreferencesConfig,
    TelegramConfig,
    get_config,
    save_config,
)


class NotificationConfigManager:
    """Manages notification configuration (Story 4.5).

    Provides setup, validation, and management for notification channels
    and preferences. Thread-safe via RLock.

    Example:
        >>> manager = NotificationConfigManager()
        >>> success = manager.setup_telegram(chat_id="123456789", bot_token="token")
        >>> success, msg = manager.test_telegram()
        >>> print(f"Test result: {msg}")
    """

    def __init__(self, config: Optional[Config] = None) -> None:
        """Initialize the configuration manager.

        Args:
            config: Configuration object. If None, loads from get_config().
        """
        if config is None:
            config = get_config()

        self._config = config
        self._lock = RLock()
        self._keyring = keyring

    def setup_telegram(self, chat_id: str, bot_token: str) -> bool:
        """Set up Telegram notification channel.

        Args:
            chat_id: Telegram chat ID to send notifications to.
            bot_token: Telegram bot token (will be stored in keyring).

        Returns:
            True if setup successful, False otherwise.
        """
        with self._lock:
            # Validate inputs
            if not self._validate_chat_id(chat_id):
                logger.error("Invalid chat_id format")
                return False

            if not self._validate_bot_token_format(bot_token):
                logger.error("Invalid bot_token format")
                return False

            # Store bot token in keyring
            if not self.store_bot_token(bot_token):
                return False

            # Update config with chat_id and enable Telegram
            try:
                new_telegram = TelegramConfig(
                    enabled=True,
                    chat_id=chat_id,
                    retry_count=self._config.telegram.retry_count,
                    retry_delay_secs=self._config.telegram.retry_delay_secs,
                    delivery_timeout_secs=self._config.telegram.delivery_timeout_secs,
                )
                # Since Config is mutable, create new Config with updated telegram
                self._config = Config(
                    wine=self._config.wine,
                    server=self._config.server,
                    monitoring=self._config.monitoring,
                    daily_reports=self._config.daily_reports,
                    latency=self._config.latency,
                    telegram=new_telegram,
                    notification_preferences=self._config.notification_preferences,
                )
                save_config(self._config)
                logger.info("Telegram setup completed")
                return True
            except Exception as e:
                logger.error(f"Failed to update config: {e}")
                return False

    def store_bot_token(self, token: str) -> bool:
        """Store bot token in system keyring.

        Args:
            token: Bot token to store.

        Returns:
            True if stored successfully, False otherwise.
        """
        if self._keyring is None:
            logger.warning("keyring library not available, cannot store bot token")
            return False

        try:
            self._keyring.set_password("mt5linux", "telegram_bot_token", token)
            logger.info("Bot token stored in keyring")
            return True
        except Exception as e:
            logger.error(f"Failed to store bot token: {e}")
            return False

    def verify_bot_token(self) -> bool:
        """Verify bot token exists in keyring.

        Returns:
            True if token exists, False otherwise.
        """
        if self._keyring is None:
            logger.warning("keyring library not available")
            return False

        try:
            token = self._keyring.get_password("mt5linux", "telegram_bot_token")
            return token is not None
        except Exception as e:
            logger.error(f"Failed to verify bot token: {e}")
            return False

    def clear_bot_token(self) -> bool:
        """Remove bot token from keyring.

        Returns:
            True if removed successfully, False otherwise.
        """
        if self._keyring is None:
            logger.warning("keyring library not available")
            return False

        try:
            self._keyring.delete_password("mt5linux", "telegram_bot_token")
            logger.info("Bot token removed from keyring")
            return True
        except Exception as e:
            logger.error(f"Failed to remove bot token: {e}")
            return False

    def test_telegram(self) -> Tuple[bool, str]:
        """Test Telegram notification delivery.

        Returns:
            Tuple of (success, message).
        """
        with self._lock:
            # Check if Telegram is enabled
            if not self._config.telegram.enabled:
                return False, "Telegram notifications are disabled"

            # Check if chat_id is configured
            if not self._config.telegram.chat_id:
                return False, "Telegram chat_id is not configured"

            # Check if bot token exists
            if not self.verify_bot_token():
                return False, "Telegram bot token not found in keyring"

            # Send test notification
            if self._send_test_notification():
                return True, "Test notification sent successfully"
            else:
                return False, "Failed to send test notification"

    def _send_test_notification(self) -> bool:
        """Send a test notification via Telegram.

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            from mt5linux.monitoring.notifier import (
                NotificationMessage,
                TelegramNotifier,
            )

            notifier = TelegramNotifier(config=self._config.telegram)
            if not notifier.start():
                logger.error("Failed to start notifier for test")
                return False

            try:
                message = NotificationMessage(
                    message_type="test",
                    title="Test Notification",
                    body="This is a test notification from mt5linux.",
                    timestamp=0.0,
                    severity="info",
                )
                return notifier.send_notification(message)
            finally:
                notifier.stop()
        except Exception as e:
            logger.error(f"Failed to send test notification: {e}")
            return False

    def get_telegram_status(self) -> Dict[str, Any]:
        """Get Telegram configuration status.

        Returns:
            Dictionary with Telegram status information.
        """
        with self._lock:
            return {
                "enabled": self._config.telegram.enabled,
                "chat_id": self._config.telegram.chat_id,
                "bot_token_available": self.verify_bot_token(),
                "retry_count": self._config.telegram.retry_count,
                "retry_delay_secs": self._config.telegram.retry_delay_secs,
                "delivery_timeout_secs": self._config.telegram.delivery_timeout_secs,
            }

    def get_preferences(self) -> NotificationPreferencesConfig:
        """Get notification preferences configuration.

        Returns:
            NotificationPreferencesConfig object.
        """
        with self._lock:
            return self._config.notification_preferences

    def update_preferences(self, preferences: Dict[str, Any]) -> bool:
        """Update notification preferences.

        Args:
            preferences: Dictionary of preference updates.
                Valid keys: failure_notifications, high_latency_notifications,
                trade_failure_notifications, drawdown_notifications,
                daily_report_notifications, quiet_hours_enabled,
                quiet_hours_start, quiet_hours_end.

        Returns:
            True if updated successfully, False otherwise.
        """
        with self._lock:
            current = self._config.notification_preferences

            # Build new preferences with updates
            new_values = {
                "failure_notifications": preferences.get(
                    "failure_notifications", current.failure_notifications
                ),
                "high_latency_notifications": preferences.get(
                    "high_latency_notifications", current.high_latency_notifications
                ),
                "trade_failure_notifications": preferences.get(
                    "trade_failure_notifications", current.trade_failure_notifications
                ),
                "drawdown_notifications": preferences.get(
                    "drawdown_notifications", current.drawdown_notifications
                ),
                "daily_report_notifications": preferences.get(
                    "daily_report_notifications", current.daily_report_notifications
                ),
                "quiet_hours_enabled": preferences.get(
                    "quiet_hours_enabled", current.quiet_hours_enabled
                ),
                "quiet_hours_start": preferences.get(
                    "quiet_hours_start", current.quiet_hours_start
                ),
                "quiet_hours_end": preferences.get(
                    "quiet_hours_end", current.quiet_hours_end
                ),
            }

            # Validate quiet hours format if provided
            for key in ["quiet_hours_start", "quiet_hours_end"]:
                if key in preferences and preferences[key] is not None:
                    if not self._is_valid_time(preferences[key]):
                        logger.error(
                            f"Invalid time format for {key}: {preferences[key]}"
                        )
                        return False

            try:
                new_prefs = NotificationPreferencesConfig(**new_values)
            except ValueError as e:
                logger.error(f"Invalid preferences: {e}")
                return False

            # Update config
            try:
                self._config = Config(
                    wine=self._config.wine,
                    server=self._config.server,
                    monitoring=self._config.monitoring,
                    daily_reports=self._config.daily_reports,
                    latency=self._config.latency,
                    telegram=self._config.telegram,
                    notification_preferences=new_prefs,
                )
                save_config(self._config)
                logger.info("Notification preferences updated")
                return True
            except Exception as e:
                logger.error(f"Failed to save preferences: {e}")
                return False

    def _validate_chat_id(self, chat_id: str) -> bool:
        """Validate Telegram chat ID format.

        Args:
            chat_id: Chat ID to validate.

        Returns:
            True if valid, False otherwise.
        """
        if not chat_id:
            return False
        # Chat ID should be numeric (can be negative for groups)
        return bool(re.match(r"^-?\d+$", chat_id))

    def _validate_bot_token_format(self, token: str) -> bool:
        """Validate Telegram bot token format.

        Args:
            token: Bot token to validate.

        Returns:
            True if valid format, False otherwise.
        """
        if not token:
            return False
        # Basic format: <bot_id>:<secret>
        # Bot ID is numeric, secret is alphanumeric with special chars
        return ":" in token and len(token) > 10

    @staticmethod
    def _is_valid_time(time_str: str) -> bool:
        """Check if time string is valid HH:MM format.

        Args:
            time_str: Time string to validate.

        Returns:
            True if valid HH:MM format, False otherwise.
        """
        if not re.match(r"^\d{2}:\d{2}$", time_str):
            return False
        hour, minute = map(int, time_str.split(":"))
        return 0 <= hour <= 23 and 0 <= minute <= 59
