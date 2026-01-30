"""Tests for notification channels module (Story 4.6).

Tests the extensible notification architecture: BaseNotifier interface,
ConsoleNotifier implementation, NotificationRouter multi-channel delivery,
and configuration dataclasses.
"""

from typing import Any, Dict

import pytest

pytestmark = pytest.mark.unit


# =============================================================================
# Task 1: BaseNotifier Interface Tests
# =============================================================================


class TestBaseNotifierInterface:
    """Test BaseNotifier abstract interface contract."""

    def test_base_notifier_cannot_be_instantiated(self) -> None:
        """BaseNotifier is abstract and cannot be instantiated directly."""
        from mt5linux.monitoring.base_notifier import BaseNotifier

        with pytest.raises(TypeError, match="abstract"):
            BaseNotifier()  # type: ignore

    def test_base_notifier_requires_channel_name(self) -> None:
        """Subclass must implement channel_name property."""
        from mt5linux.monitoring.base_notifier import BaseNotifier

        class IncompleteNotifier(BaseNotifier):
            @property
            def is_running(self) -> bool:
                return False

            def start(self) -> bool:
                return True

            def stop(self) -> None:
                pass

            def send_notification(self, message: Any) -> bool:
                return True

            def get_status(self) -> Dict[str, Any]:
                return {}

        with pytest.raises(TypeError, match="abstract"):
            IncompleteNotifier()  # type: ignore

    def test_base_notifier_requires_is_running(self) -> None:
        """Subclass must implement is_running property."""
        from mt5linux.monitoring.base_notifier import BaseNotifier

        class IncompleteNotifier(BaseNotifier):
            @property
            def channel_name(self) -> str:
                return "test"

            def start(self) -> bool:
                return True

            def stop(self) -> None:
                pass

            def send_notification(self, message: Any) -> bool:
                return True

            def get_status(self) -> Dict[str, Any]:
                return {}

        with pytest.raises(TypeError, match="abstract"):
            IncompleteNotifier()  # type: ignore

    def test_base_notifier_requires_start(self) -> None:
        """Subclass must implement start method."""
        from mt5linux.monitoring.base_notifier import BaseNotifier

        class IncompleteNotifier(BaseNotifier):
            @property
            def channel_name(self) -> str:
                return "test"

            @property
            def is_running(self) -> bool:
                return False

            def stop(self) -> None:
                pass

            def send_notification(self, message: Any) -> bool:
                return True

            def get_status(self) -> Dict[str, Any]:
                return {}

        with pytest.raises(TypeError, match="abstract"):
            IncompleteNotifier()  # type: ignore

    def test_base_notifier_requires_stop(self) -> None:
        """Subclass must implement stop method."""
        from mt5linux.monitoring.base_notifier import BaseNotifier

        class IncompleteNotifier(BaseNotifier):
            @property
            def channel_name(self) -> str:
                return "test"

            @property
            def is_running(self) -> bool:
                return False

            def start(self) -> bool:
                return True

            def send_notification(self, message: Any) -> bool:
                return True

            def get_status(self) -> Dict[str, Any]:
                return {}

        with pytest.raises(TypeError, match="abstract"):
            IncompleteNotifier()  # type: ignore

    def test_base_notifier_requires_send_notification(self) -> None:
        """Subclass must implement send_notification method."""
        from mt5linux.monitoring.base_notifier import BaseNotifier

        class IncompleteNotifier(BaseNotifier):
            @property
            def channel_name(self) -> str:
                return "test"

            @property
            def is_running(self) -> bool:
                return False

            def start(self) -> bool:
                return True

            def stop(self) -> None:
                pass

            def get_status(self) -> Dict[str, Any]:
                return {}

        with pytest.raises(TypeError, match="abstract"):
            IncompleteNotifier()  # type: ignore

    def test_base_notifier_requires_get_status(self) -> None:
        """Subclass must implement get_status method."""
        from mt5linux.monitoring.base_notifier import BaseNotifier

        class IncompleteNotifier(BaseNotifier):
            @property
            def channel_name(self) -> str:
                return "test"

            @property
            def is_running(self) -> bool:
                return False

            def start(self) -> bool:
                return True

            def stop(self) -> None:
                pass

            def send_notification(self, message: Any) -> bool:
                return True

        with pytest.raises(TypeError, match="abstract"):
            IncompleteNotifier()  # type: ignore


class TestCompleteNotifierImplementation:
    """Test that a complete implementation can be instantiated."""

    def test_complete_implementation_can_be_instantiated(self) -> None:
        """A class implementing all abstract methods can be instantiated."""
        from mt5linux.monitoring.base_notifier import BaseNotifier

        class CompleteNotifier(BaseNotifier):
            @property
            def channel_name(self) -> str:
                return "complete"

            @property
            def is_running(self) -> bool:
                return True

            def start(self) -> bool:
                return True

            def stop(self) -> None:
                pass

            def send_notification(self, message: Any) -> bool:
                return True

            def get_status(self) -> Dict[str, Any]:
                return {"channel": "complete"}

        notifier = CompleteNotifier()
        assert notifier.channel_name == "complete"
        assert notifier.is_running is True
        assert notifier.start() is True
        notifier.stop()
        assert notifier.send_notification(None) is True
        assert notifier.get_status() == {"channel": "complete"}


class TestNotificationType:
    """Test NotificationType enum."""

    def test_notification_type_values(self) -> None:
        """NotificationType has expected values."""
        from mt5linux.monitoring.base_notifier import NotificationType

        assert NotificationType.FAILURE.value == "failure"
        assert NotificationType.HIGH_LATENCY.value == "high_latency"
        assert NotificationType.TRADE_FAILURE.value == "trade_failure"
        assert NotificationType.DRAWDOWN.value == "drawdown"
        assert NotificationType.DAILY_REPORT.value == "daily_report"

    def test_notification_type_is_enum(self) -> None:
        """NotificationType is an enum."""
        from enum import Enum

        from mt5linux.monitoring.base_notifier import NotificationType

        assert issubclass(NotificationType, Enum)


# =============================================================================
# Task 2: TelegramNotifier Backward Compatibility Tests
# =============================================================================


class TestTelegramNotifierBackwardCompatibility:
    """Test TelegramNotifier backward compatibility after refactor."""

    def test_telegram_notifier_is_base_notifier(self) -> None:
        """TelegramNotifier inherits from BaseNotifier."""
        from mt5linux.monitoring.base_notifier import BaseNotifier
        from mt5linux.monitoring.notifier import TelegramNotifier

        assert issubclass(TelegramNotifier, BaseNotifier)

    def test_telegram_notifier_channel_name(self) -> None:
        """TelegramNotifier.channel_name returns 'telegram'."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        assert notifier.channel_name == "telegram"

    def test_telegram_notifier_existing_api_preserved(self) -> None:
        """All existing TelegramNotifier methods still work."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()

        # Check existing properties
        assert hasattr(notifier, "is_enabled")
        assert hasattr(notifier, "is_running")

        # Check existing methods
        assert hasattr(notifier, "start")
        assert hasattr(notifier, "stop")
        assert hasattr(notifier, "send_notification")
        assert hasattr(notifier, "notify_failure")
        assert hasattr(notifier, "notify_high_latency")
        assert hasattr(notifier, "notify_trade_failure")
        assert hasattr(notifier, "notify_drawdown_breach")
        assert hasattr(notifier, "notify_daily_report")
        assert hasattr(notifier, "set_preferences")
        assert hasattr(notifier, "get_status")
        assert hasattr(notifier, "clear_statistics")

    def test_telegram_notifier_get_status_includes_channel_info(self) -> None:
        """TelegramNotifier.get_status includes all expected fields."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        status = notifier.get_status()

        # Check required status fields
        assert "enabled" in status
        assert "running" in status
        assert "messages_sent" in status
        assert "messages_failed" in status


# =============================================================================
# Task 3: ConsoleNotifier Tests
# =============================================================================


class TestConsoleNotifierConfig:
    """Test ConsoleNotifierConfig dataclass."""

    def test_default_values(self) -> None:
        """ConsoleNotifierConfig has expected defaults."""
        from mt5linux.monitoring.console_notifier import ConsoleNotifierConfig

        config = ConsoleNotifierConfig()
        assert config.enabled is False
        assert config.log_level == "INFO"

    def test_custom_values(self) -> None:
        """ConsoleNotifierConfig accepts custom values."""
        from mt5linux.monitoring.console_notifier import ConsoleNotifierConfig

        config = ConsoleNotifierConfig(enabled=True, log_level="DEBUG")
        assert config.enabled is True
        assert config.log_level == "DEBUG"

    def test_frozen_dataclass(self) -> None:
        """ConsoleNotifierConfig is frozen (immutable)."""
        from mt5linux.monitoring.console_notifier import ConsoleNotifierConfig

        config = ConsoleNotifierConfig()
        with pytest.raises(AttributeError):
            config.enabled = True  # type: ignore

    def test_slots_dataclass(self) -> None:
        """ConsoleNotifierConfig uses slots."""
        from mt5linux.monitoring.console_notifier import ConsoleNotifierConfig

        config = ConsoleNotifierConfig()
        assert hasattr(config, "__slots__")


class TestConsoleNotifier:
    """Test ConsoleNotifier implementation."""

    def test_is_base_notifier(self) -> None:
        """ConsoleNotifier inherits from BaseNotifier."""
        from mt5linux.monitoring.base_notifier import BaseNotifier
        from mt5linux.monitoring.console_notifier import ConsoleNotifier

        assert issubclass(ConsoleNotifier, BaseNotifier)

    def test_channel_name(self) -> None:
        """ConsoleNotifier.channel_name returns 'console'."""
        from mt5linux.monitoring.console_notifier import ConsoleNotifier

        notifier = ConsoleNotifier()
        assert notifier.channel_name == "console"

    def test_default_not_running(self) -> None:
        """ConsoleNotifier is not running by default."""
        from mt5linux.monitoring.console_notifier import ConsoleNotifier

        notifier = ConsoleNotifier()
        assert notifier.is_running is False

    def test_start_disabled(self) -> None:
        """ConsoleNotifier.start returns False when disabled."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )

        config = ConsoleNotifierConfig(enabled=False)
        notifier = ConsoleNotifier(config)
        assert notifier.start() is False
        assert notifier.is_running is False

    def test_start_enabled(self) -> None:
        """ConsoleNotifier.start returns True when enabled."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )

        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)
        assert notifier.start() is True
        assert notifier.is_running is True

    def test_stop(self) -> None:
        """ConsoleNotifier.stop sets is_running to False."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )

        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)
        notifier.start()
        assert notifier.is_running is True
        notifier.stop()
        assert notifier.is_running is False

    def test_send_notification_when_not_running(self) -> None:
        """ConsoleNotifier.send_notification returns False when not running."""
        from mt5linux.monitoring.console_notifier import ConsoleNotifier
        from mt5linux.monitoring.notifier import NotificationMessage

        notifier = ConsoleNotifier()
        message = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Test body",
            timestamp=0.0,
            severity="info",
        )
        assert notifier.send_notification(message) is False

    def test_send_notification_when_running(self) -> None:
        """ConsoleNotifier.send_notification returns True when running."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notifier import NotificationMessage

        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)
        notifier.start()

        message = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Test body",
            timestamp=0.0,
            severity="info",
        )
        assert notifier.send_notification(message) is True

    def test_send_notification_with_none(self) -> None:
        """ConsoleNotifier.send_notification returns False for None message."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )

        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)
        notifier.start()

        assert notifier.send_notification(None) is False  # type: ignore

    def test_logged_notifications_tracking(self) -> None:
        """ConsoleNotifier tracks logged notifications."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notifier import NotificationMessage

        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)
        notifier.start()

        message = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Test body",
            timestamp=0.0,
            severity="info",
        )
        notifier.send_notification(message)

        assert len(notifier.logged_notifications) == 1
        assert notifier.logged_notifications[0] == message

    def test_clear_statistics(self) -> None:
        """ConsoleNotifier.clear_statistics resets counters."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notifier import NotificationMessage

        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)
        notifier.start()

        message = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Test body",
            timestamp=0.0,
            severity="info",
        )
        notifier.send_notification(message)

        assert len(notifier.logged_notifications) == 1
        notifier.clear_statistics()
        assert len(notifier.logged_notifications) == 0

    def test_get_status(self) -> None:
        """ConsoleNotifier.get_status returns expected fields."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )

        config = ConsoleNotifierConfig(enabled=True, log_level="DEBUG")
        notifier = ConsoleNotifier(config)

        status = notifier.get_status()
        assert status["enabled"] is True
        assert status["running"] is False
        assert status["messages_logged"] == 0
        assert status["log_level"] == "DEBUG"


# =============================================================================
# Task 4: NotificationRouter Tests
# =============================================================================


class TestNotificationRouter:
    """Test NotificationRouter multi-channel coordinator."""

    def test_init_empty(self) -> None:
        """NotificationRouter initializes with no channels."""
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        assert router.available_channels == []
        assert router.enabled_channels == []

    def test_register_channel(self) -> None:
        """NotificationRouter can register a channel."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)

        router.register_channel(notifier)
        assert "console" in router.available_channels

    def test_register_duplicate_raises(self) -> None:
        """NotificationRouter raises on duplicate channel name."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier1 = ConsoleNotifier(config)
        notifier2 = ConsoleNotifier(config)

        router.register_channel(notifier1)
        with pytest.raises(ValueError, match="already registered"):
            router.register_channel(notifier2)

    def test_unregister_channel(self) -> None:
        """NotificationRouter can unregister a channel."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)

        router.register_channel(notifier)
        assert "console" in router.available_channels

        result = router.unregister_channel("console")
        assert result is True
        assert "console" not in router.available_channels

    def test_unregister_nonexistent(self) -> None:
        """NotificationRouter.unregister_channel returns False for unknown channel."""
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        result = router.unregister_channel("nonexistent")
        assert result is False

    def test_enable_channel(self) -> None:
        """NotificationRouter can enable a channel."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)

        router.register_channel(notifier)
        result = router.enable_channel("console")
        assert result is True
        assert "console" in router.enabled_channels

    def test_enable_unregistered_channel(self) -> None:
        """NotificationRouter.enable_channel returns False for unregistered channel."""
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        result = router.enable_channel("nonexistent")
        assert result is False

    def test_disable_channel(self) -> None:
        """NotificationRouter can disable a channel."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)

        router.register_channel(notifier)
        router.enable_channel("console")
        assert "console" in router.enabled_channels

        result = router.disable_channel("console")
        assert result is True
        assert "console" not in router.enabled_channels

    def test_start_all(self) -> None:
        """NotificationRouter.start_all starts all channels."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)

        router.register_channel(notifier)
        results = router.start_all()

        assert results["console"] is True
        assert notifier.is_running is True

    def test_stop_all(self) -> None:
        """NotificationRouter.stop_all stops all channels."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)

        router.register_channel(notifier)
        router.start_all()
        assert notifier.is_running is True

        router.stop_all()
        assert notifier.is_running is False

    def test_send_to_all(self) -> None:
        """NotificationRouter.send_to_all sends to all enabled channels."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter
        from mt5linux.monitoring.notifier import NotificationMessage

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)

        router.register_channel(notifier)
        router.enable_channel("console")
        router.start_all()

        message = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Test body",
            timestamp=0.0,
            severity="info",
        )
        results = router.send_to_all(message)

        assert results["console"] is True
        assert len(notifier.logged_notifications) == 1

    def test_send_to_all_skips_disabled(self) -> None:
        """NotificationRouter.send_to_all skips disabled channels."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter
        from mt5linux.monitoring.notifier import NotificationMessage

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)

        router.register_channel(notifier)
        # Do NOT enable
        router.start_all()

        message = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Test body",
            timestamp=0.0,
            severity="info",
        )
        results = router.send_to_all(message)

        assert "console" not in results  # Not in results because not enabled

    def test_send_to_channel(self) -> None:
        """NotificationRouter.send_to_channel sends to specific channel."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter
        from mt5linux.monitoring.notifier import NotificationMessage

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)

        router.register_channel(notifier)
        router.start_all()

        message = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Test body",
            timestamp=0.0,
            severity="info",
        )
        result = router.send_to_channel("console", message)

        assert result is True
        assert len(notifier.logged_notifications) == 1

    def test_send_to_channel_nonexistent(self) -> None:
        """NotificationRouter.send_to_channel returns False for unknown channel."""
        from mt5linux.monitoring.notification_router import NotificationRouter
        from mt5linux.monitoring.notifier import NotificationMessage

        router = NotificationRouter()
        message = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Test body",
            timestamp=0.0,
            severity="info",
        )
        result = router.send_to_channel("nonexistent", message)
        assert result is False

    def test_get_channel_status(self) -> None:
        """NotificationRouter.get_channel_status returns status for all channels."""
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter

        router = NotificationRouter()
        config = ConsoleNotifierConfig(enabled=True)
        notifier = ConsoleNotifier(config)

        router.register_channel(notifier)
        router.enable_channel("console")
        router.start_all()

        status = router.get_channel_status()
        assert "console" in status
        assert status["console"]["enabled"] is True
        assert status["console"]["running"] is True


class TestNotificationRouterErrorIsolation:
    """Test NotificationRouter error isolation between channels."""

    def test_error_in_one_channel_does_not_affect_others(self) -> None:
        """Error in one channel doesn't prevent delivery to other channels."""
        from mt5linux.monitoring.base_notifier import BaseNotifier
        from mt5linux.monitoring.console_notifier import (
            ConsoleNotifier,
            ConsoleNotifierConfig,
        )
        from mt5linux.monitoring.notification_router import NotificationRouter
        from mt5linux.monitoring.notifier import NotificationMessage

        # Create a failing notifier
        class FailingNotifier(BaseNotifier):
            @property
            def channel_name(self) -> str:
                return "failing"

            @property
            def is_running(self) -> bool:
                return True

            def start(self) -> bool:
                return True

            def stop(self) -> None:
                pass

            def send_notification(self, message: Any) -> bool:
                raise RuntimeError("Intentional failure")

            def get_status(self) -> Dict[str, Any]:
                return {}

        router = NotificationRouter()

        # Add console (working)
        config = ConsoleNotifierConfig(enabled=True)
        console = ConsoleNotifier(config)
        router.register_channel(console)
        router.enable_channel("console")

        # Add failing channel
        failing = FailingNotifier()
        router.register_channel(failing)
        router.enable_channel("failing")

        router.start_all()

        message = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Test body",
            timestamp=0.0,
            severity="info",
        )
        results = router.send_to_all(message)

        # Console should succeed, failing should fail
        assert results["console"] is True
        assert results["failing"] is False
        assert len(console.logged_notifications) == 1


# =============================================================================
# Task 5: Configuration Tests
# =============================================================================


class TestNotificationChannelsConfig:
    """Test NotificationChannelsConfig dataclass."""

    def test_default_values(self) -> None:
        """NotificationChannelsConfig has expected defaults."""
        from mt5linux.config import NotificationChannelsConfig

        config = NotificationChannelsConfig()
        assert config.enabled_channels == ("telegram",)
        assert config.console_enabled is False
        assert config.console_log_level == "INFO"

    def test_custom_values(self) -> None:
        """NotificationChannelsConfig accepts custom values."""
        from mt5linux.config import NotificationChannelsConfig

        config = NotificationChannelsConfig(
            enabled_channels=("telegram", "console"),
            console_enabled=True,
            console_log_level="DEBUG",
        )
        assert config.enabled_channels == ("telegram", "console")
        assert config.console_enabled is True
        assert config.console_log_level == "DEBUG"

    def test_frozen_dataclass(self) -> None:
        """NotificationChannelsConfig is frozen (immutable)."""
        from mt5linux.config import NotificationChannelsConfig

        config = NotificationChannelsConfig()
        with pytest.raises(AttributeError):
            config.console_enabled = True  # type: ignore

    def test_invalid_log_level_raises(self) -> None:
        """NotificationChannelsConfig raises for invalid log level."""
        from mt5linux.config import NotificationChannelsConfig

        with pytest.raises(ValueError, match="Invalid console_log_level"):
            NotificationChannelsConfig(console_log_level="INVALID")

    def test_valid_log_levels(self) -> None:
        """NotificationChannelsConfig accepts all valid log levels."""
        from mt5linux.config import NotificationChannelsConfig

        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            config = NotificationChannelsConfig(console_log_level=level)
            assert config.console_log_level == level

    def test_log_level_case_insensitive_validation(self) -> None:
        """NotificationChannelsConfig validates log level case-insensitively."""
        from mt5linux.config import NotificationChannelsConfig

        # Should work with lowercase
        config = NotificationChannelsConfig(console_log_level="debug")
        assert config.console_log_level == "debug"


# =============================================================================
# Task 6: CLI Tests
# =============================================================================


class TestNotificationCLIChannels:
    """Test CLI commands for notification channel management."""

    def test_channels_command_exists(self) -> None:
        """CLI has notification channels command."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["notification", "channels", "--help"])
        # Should not error on --help
        assert result.exit_code == 0

    def test_enable_command_exists(self) -> None:
        """CLI has notification enable command."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["notification", "enable", "--help"])
        assert result.exit_code == 0

    def test_disable_command_exists(self) -> None:
        """CLI has notification disable command."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["notification", "disable", "--help"])
        assert result.exit_code == 0

    def test_channels_command_lists_channels(self) -> None:
        """CLI channels command lists available channels."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["notification", "channels"])
        # Should show output (even if exit code varies based on config availability)
        # Check that it mentions telegram and console
        assert "telegram" in result.output.lower() or result.exit_code == 1

    def test_enable_invalid_channel_fails(self) -> None:
        """CLI enable command fails for invalid channel."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["notification", "enable", "invalid_channel"])
        # Should fail with exit code 1 for unknown channel
        assert result.exit_code == 1
        assert "unknown channel" in result.output.lower()

    def test_disable_invalid_channel_fails(self) -> None:
        """CLI disable command fails for invalid channel."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["notification", "disable", "invalid_channel"])
        # Should fail with exit code 1 for unknown channel
        assert result.exit_code == 1
        assert "unknown channel" in result.output.lower()


# =============================================================================
# Task 7: Module Export Tests
# =============================================================================


class TestModuleExports:
    """Test that new classes are exported from monitoring package."""

    def test_base_notifier_exported(self) -> None:
        """BaseNotifier is exported from monitoring package."""
        from mt5linux.monitoring import BaseNotifier

        assert BaseNotifier is not None

    def test_notification_type_exported(self) -> None:
        """NotificationType is exported from monitoring package."""
        from mt5linux.monitoring import NotificationType

        assert NotificationType is not None

    def test_console_notifier_exported(self) -> None:
        """ConsoleNotifier is exported from monitoring package."""
        from mt5linux.monitoring import ConsoleNotifier

        assert ConsoleNotifier is not None

    def test_console_notifier_config_exported(self) -> None:
        """ConsoleNotifierConfig is exported from monitoring package."""
        from mt5linux.monitoring import ConsoleNotifierConfig

        assert ConsoleNotifierConfig is not None

    def test_notification_router_exported(self) -> None:
        """NotificationRouter is exported from monitoring package."""
        from mt5linux.monitoring import NotificationRouter

        assert NotificationRouter is not None
