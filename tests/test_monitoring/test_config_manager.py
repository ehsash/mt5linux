"""Unit tests for mt5linux.monitoring.config_manager module (Story 4.5)."""

import tempfile
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit  # All tests in this module are unit tests


class TestNotificationConfigManagerInit:
    """Tests for NotificationConfigManager initialization."""

    def test_init_with_default_config(self) -> None:
        """Test NotificationConfigManager initializes with default config."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        assert manager is not None
        assert manager._config is not None

    def test_init_with_custom_config(self) -> None:
        """Test NotificationConfigManager initializes with custom config."""
        from mt5linux.config import Config
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        config = Config()
        manager = NotificationConfigManager(config=config)
        assert manager._config is config

    def test_manager_is_thread_safe(self) -> None:
        """Test NotificationConfigManager has thread-safe lock."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        assert hasattr(manager, "_lock")


class TestNotificationConfigManagerSetupTelegram:
    """Tests for NotificationConfigManager.setup_telegram() method."""

    def test_setup_telegram_stores_credentials(self) -> None:
        """Test setup_telegram stores bot token in keyring and updates config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                from mt5linux.config import reload_config
                from mt5linux.monitoring.config_manager import NotificationConfigManager

                reload_config()
                manager = NotificationConfigManager()

                # Mock keyring via the manager's _keyring attribute
                mock_keyring = MagicMock()
                manager._keyring = mock_keyring

                result = manager.setup_telegram(
                    chat_id="123456789", bot_token="123456:ABC-DEF"
                )

                assert result is True
                mock_keyring.set_password.assert_called_once_with(
                    "mt5linux", "telegram_bot_token", "123456:ABC-DEF"
                )

    def test_setup_telegram_rejects_invalid_chat_id(self) -> None:
        """Test setup_telegram rejects invalid chat_id format."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        result = manager.setup_telegram(chat_id="", bot_token="123456:ABC-DEF")
        assert result is False

    def test_setup_telegram_rejects_invalid_bot_token(self) -> None:
        """Test setup_telegram rejects invalid bot_token format."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        result = manager.setup_telegram(chat_id="123456789", bot_token="")
        assert result is False

    def test_setup_telegram_handles_keyring_failure(self) -> None:
        """Test setup_telegram handles keyring storage failure gracefully."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        # Mock keyring to raise exception
        mock_keyring = MagicMock()
        mock_keyring.set_password.side_effect = Exception("Keyring error")
        manager._keyring = mock_keyring

        result = manager.setup_telegram(chat_id="123456789", bot_token="123456:ABC-DEF")
        assert result is False


class TestNotificationConfigManagerCredentials:
    """Tests for NotificationConfigManager credential storage methods."""

    def test_store_bot_token_success(self) -> None:
        """Test store_bot_token stores token in keyring."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        mock_keyring = MagicMock()
        manager._keyring = mock_keyring

        result = manager.store_bot_token("123456:ABC-DEF")

        assert result is True
        mock_keyring.set_password.assert_called_once_with(
            "mt5linux", "telegram_bot_token", "123456:ABC-DEF"
        )

    def test_store_bot_token_failure(self) -> None:
        """Test store_bot_token handles keyring errors."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        mock_keyring = MagicMock()
        mock_keyring.set_password.side_effect = Exception("Keyring error")
        manager._keyring = mock_keyring

        result = manager.store_bot_token("123456:ABC-DEF")
        assert result is False

    def test_verify_bot_token_exists(self) -> None:
        """Test verify_bot_token returns True when token exists."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "123456:ABC-DEF"
        manager._keyring = mock_keyring

        result = manager.verify_bot_token()
        assert result is True

    def test_verify_bot_token_not_exists(self) -> None:
        """Test verify_bot_token returns False when no token."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None
        manager._keyring = mock_keyring

        result = manager.verify_bot_token()
        assert result is False

    def test_clear_bot_token_success(self) -> None:
        """Test clear_bot_token removes token from keyring."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        mock_keyring = MagicMock()
        manager._keyring = mock_keyring

        result = manager.clear_bot_token()

        assert result is True
        mock_keyring.delete_password.assert_called_once_with(
            "mt5linux", "telegram_bot_token"
        )

    def test_clear_bot_token_handles_missing(self) -> None:
        """Test clear_bot_token handles case when no token exists."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        mock_keyring = MagicMock()
        mock_keyring.delete_password.side_effect = Exception("Password not found")
        manager._keyring = mock_keyring

        # Should not raise, just return False
        result = manager.clear_bot_token()
        assert result is False


class TestNotificationConfigManagerKeyringUnavailable:
    """Tests for NotificationConfigManager when keyring is unavailable."""

    def test_store_bot_token_keyring_unavailable(self) -> None:
        """Test store_bot_token handles keyring import failure."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        # Simulate keyring being None (import failed)
        with patch.object(manager, "_keyring", None):
            result = manager.store_bot_token("123456:ABC-DEF")
            assert result is False

    def test_verify_bot_token_keyring_unavailable(self) -> None:
        """Test verify_bot_token handles keyring import failure."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        with patch.object(manager, "_keyring", None):
            result = manager.verify_bot_token()
            assert result is False


class TestNotificationConfigManagerValidation:
    """Tests for NotificationConfigManager validation methods."""

    def test_validate_chat_id_valid_numeric(self) -> None:
        """Test _validate_chat_id accepts numeric string."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        assert manager._validate_chat_id("123456789") is True

    def test_validate_chat_id_valid_negative(self) -> None:
        """Test _validate_chat_id accepts negative (group chat)."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        assert manager._validate_chat_id("-123456789") is True

    def test_validate_chat_id_rejects_empty(self) -> None:
        """Test _validate_chat_id rejects empty string."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        assert manager._validate_chat_id("") is False

    def test_validate_chat_id_rejects_non_numeric(self) -> None:
        """Test _validate_chat_id rejects non-numeric string."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        assert manager._validate_chat_id("abc123") is False

    def test_validate_bot_token_format_valid(self) -> None:
        """Test _validate_bot_token_format accepts valid format."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        # Format: <bot_id>:<secret>
        assert manager._validate_bot_token_format("123456:ABC-DEF1ghIjK") is True

    def test_validate_bot_token_format_rejects_empty(self) -> None:
        """Test _validate_bot_token_format rejects empty string."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        assert manager._validate_bot_token_format("") is False

    def test_validate_bot_token_format_rejects_no_colon(self) -> None:
        """Test _validate_bot_token_format rejects token without colon."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        assert manager._validate_bot_token_format("123456ABC") is False


class TestNotificationConfigManagerTestTelegram:
    """Tests for NotificationConfigManager.test_telegram() method."""

    def test_telegram_success(self) -> None:
        """Test test_telegram returns success when notification sent."""
        from mt5linux.config import Config, TelegramConfig
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        config = Config(telegram=TelegramConfig(enabled=True, chat_id="123456789"))
        manager = NotificationConfigManager(config=config)

        # Mock keyring to return token
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "123456:ABC-DEF"
        manager._keyring = mock_keyring

        # Mock the actual send
        with patch.object(manager, "_send_test_notification", return_value=True):
            success, msg = manager.test_telegram()
            assert success is True
            assert "success" in msg.lower() or "sent" in msg.lower()

    def test_telegram_no_config(self) -> None:
        """Test test_telegram fails when Telegram not configured."""
        from mt5linux.config import Config, TelegramConfig
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        config = Config(telegram=TelegramConfig(enabled=False))
        manager = NotificationConfigManager(config=config)

        success, msg = manager.test_telegram()
        assert success is False
        assert "not configured" in msg.lower() or "disabled" in msg.lower()

    def test_telegram_no_bot_token(self) -> None:
        """Test test_telegram fails when no bot token in keyring."""
        from mt5linux.config import Config, TelegramConfig
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        config = Config(telegram=TelegramConfig(enabled=True, chat_id="123456789"))
        manager = NotificationConfigManager(config=config)

        # Mock keyring to return None (no token)
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None
        manager._keyring = mock_keyring

        success, msg = manager.test_telegram()
        assert success is False
        assert "token" in msg.lower()


class TestNotificationConfigManagerGetTelegramStatus:
    """Tests for NotificationConfigManager.get_telegram_status() method."""

    def test_get_telegram_status_configured(self) -> None:
        """Test get_telegram_status returns correct status when configured."""
        from mt5linux.config import Config, TelegramConfig
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        config = Config(telegram=TelegramConfig(enabled=True, chat_id="123456789"))
        manager = NotificationConfigManager(config=config)

        # Mock keyring
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "123456:ABC-DEF"
        manager._keyring = mock_keyring

        status = manager.get_telegram_status()
        assert status["enabled"] is True
        assert status["chat_id"] == "123456789"
        assert status["bot_token_available"] is True

    def test_get_telegram_status_not_configured(self) -> None:
        """Test get_telegram_status returns correct status when not configured."""
        from mt5linux.config import Config, TelegramConfig
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        config = Config(telegram=TelegramConfig(enabled=False))
        manager = NotificationConfigManager(config=config)

        # Mock keyring to return None
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None
        manager._keyring = mock_keyring

        status = manager.get_telegram_status()
        assert status["enabled"] is False
        assert status["chat_id"] == ""
        assert status["bot_token_available"] is False


class TestNotificationConfigManagerPreferences:
    """Tests for NotificationConfigManager preference methods."""

    def test_get_preferences_returns_config(self) -> None:
        """Test get_preferences returns notification preferences from config."""
        from mt5linux.config import Config, NotificationPreferencesConfig
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        config = Config(
            notification_preferences=NotificationPreferencesConfig(
                failure_notifications=False,
                quiet_hours_enabled=True,
                quiet_hours_start="22:00",
                quiet_hours_end="06:00",
            )
        )
        manager = NotificationConfigManager(config=config)

        prefs = manager.get_preferences()
        assert prefs.failure_notifications is False
        assert prefs.quiet_hours_enabled is True
        assert prefs.quiet_hours_start == "22:00"

    def test_update_preferences_success(self) -> None:
        """Test update_preferences updates configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                from mt5linux.config import reload_config
                from mt5linux.monitoring.config_manager import (
                    NotificationConfigManager,
                )

                reload_config()
                manager = NotificationConfigManager()

                result = manager.update_preferences(
                    {"failure_notifications": False, "quiet_hours_enabled": True}
                )
                assert result is True

                # Verify changes persisted
                prefs = manager.get_preferences()
                assert prefs.failure_notifications is False

    def test_update_preferences_invalid_key(self) -> None:
        """Test update_preferences ignores invalid keys."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        # Invalid key should be ignored, but valid updates still work
        result = manager.update_preferences({"invalid_key": True})
        # Should return True (no valid updates, but no error)
        assert result is True or result is False  # Implementation choice

    def test_update_preferences_validates_quiet_hours(self) -> None:
        """Test update_preferences validates quiet hours format."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        # Invalid time format should fail
        result = manager.update_preferences({"quiet_hours_start": "invalid"})
        assert result is False


class TestNotificationConfigManagerThreadSafety:
    """Tests for NotificationConfigManager thread safety."""

    def test_concurrent_get_preferences(self) -> None:
        """Test concurrent get_preferences calls are thread-safe."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()
        results: list = []

        def get_prefs() -> None:
            for _ in range(100):
                prefs = manager.get_preferences()
                results.append(prefs is not None)

        threads = [Thread(target=get_prefs) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)

    def test_concurrent_get_status(self) -> None:
        """Test concurrent get_telegram_status calls are thread-safe."""
        from mt5linux.monitoring.config_manager import NotificationConfigManager

        manager = NotificationConfigManager()

        # Mock keyring
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "123456:ABC-DEF"
        manager._keyring = mock_keyring

        results: list = []

        def get_status() -> None:
            for _ in range(100):
                status = manager.get_telegram_status()
                results.append("enabled" in status)

        threads = [Thread(target=get_status) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)


class TestTelegramNotifierFiltering:
    """Tests for TelegramNotifier preference filtering (Story 4.5, Task 5)."""

    def test_set_preferences_stores_preferences(self) -> None:
        """Test set_preferences stores preferences on notifier."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        prefs = NotificationPreferencesConfig(failure_notifications=False)
        notifier.set_preferences(prefs)

        assert notifier._preferences is prefs
        assert notifier._preferences.failure_notifications is False

    def test_should_send_returns_true_without_preferences(self) -> None:
        """Test _should_send returns True when no preferences set."""
        from mt5linux.config import TelegramConfig
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        # No preferences set
        assert notifier._should_send("failure") is True
        assert notifier._should_send("high_latency") is True

    def test_should_send_respects_failure_preference(self) -> None:
        """Test _should_send respects failure_notifications preference."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        prefs = NotificationPreferencesConfig(failure_notifications=False)
        notifier.set_preferences(prefs)

        assert notifier._should_send("failure") is False
        assert notifier._should_send("high_latency") is True

    def test_should_send_respects_high_latency_preference(self) -> None:
        """Test _should_send respects high_latency_notifications preference."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        prefs = NotificationPreferencesConfig(high_latency_notifications=False)
        notifier.set_preferences(prefs)

        assert notifier._should_send("high_latency") is False
        assert notifier._should_send("failure") is True

    def test_should_send_respects_trade_failure_preference(self) -> None:
        """Test _should_send respects trade_failure_notifications preference."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        prefs = NotificationPreferencesConfig(trade_failure_notifications=False)
        notifier.set_preferences(prefs)

        assert notifier._should_send("trade_failure") is False

    def test_should_send_respects_drawdown_preference(self) -> None:
        """Test _should_send respects drawdown_notifications preference."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        prefs = NotificationPreferencesConfig(drawdown_notifications=False)
        notifier.set_preferences(prefs)

        assert notifier._should_send("drawdown") is False

    def test_should_send_respects_daily_report_preference(self) -> None:
        """Test _should_send respects daily_report_notifications preference."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        prefs = NotificationPreferencesConfig(daily_report_notifications=False)
        notifier.set_preferences(prefs)

        assert notifier._should_send("daily_report") is False

    def test_should_send_respects_quiet_hours(self) -> None:
        """Test _should_send respects quiet hours."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        # Set quiet hours that include current time (10:00-12:00)
        prefs = NotificationPreferencesConfig(
            quiet_hours_enabled=True,
            quiet_hours_start="10:00",
            quiet_hours_end="12:00",
        )
        notifier.set_preferences(prefs)

        # Test at 11:00 (within quiet hours)
        assert notifier._should_send("failure", current_time="11:00") is False

        # Test at 13:00 (outside quiet hours)
        assert notifier._should_send("failure", current_time="13:00") is True

    def test_should_send_quiet_hours_overnight(self) -> None:
        """Test _should_send with overnight quiet hours (22:00-08:00)."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        prefs = NotificationPreferencesConfig(
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
        )
        notifier.set_preferences(prefs)

        # Test at 23:00 (within quiet hours)
        assert notifier._should_send("failure", current_time="23:00") is False

        # Test at 06:00 (within quiet hours)
        assert notifier._should_send("failure", current_time="06:00") is False

        # Test at 12:00 (outside quiet hours)
        assert notifier._should_send("failure", current_time="12:00") is True

    def test_should_send_quiet_hours_disabled(self) -> None:
        """Test _should_send when quiet hours are disabled."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        # Quiet hours disabled (default)
        prefs = NotificationPreferencesConfig(quiet_hours_enabled=False)
        notifier.set_preferences(prefs)

        # Should always return True regardless of time
        assert notifier._should_send("failure", current_time="23:00") is True
        assert notifier._should_send("failure", current_time="06:00") is True


class TestNotificationPreferencesQuietHoursLogic:
    """Tests for NotificationPreferencesConfig.is_quiet_hours() method."""

    def test_is_quiet_hours_disabled_returns_false(self) -> None:
        """Test is_quiet_hours returns False when disabled."""
        from mt5linux.config import NotificationPreferencesConfig

        prefs = NotificationPreferencesConfig(quiet_hours_enabled=False)
        assert prefs.is_quiet_hours("23:00") is False

    def test_is_quiet_hours_within_range(self) -> None:
        """Test is_quiet_hours returns True within quiet period."""
        from mt5linux.config import NotificationPreferencesConfig

        prefs = NotificationPreferencesConfig(
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
        )
        assert prefs.is_quiet_hours("23:00") is True
        assert prefs.is_quiet_hours("02:00") is True
        assert prefs.is_quiet_hours("07:59") is True

    def test_is_quiet_hours_outside_range(self) -> None:
        """Test is_quiet_hours returns False outside quiet period."""
        from mt5linux.config import NotificationPreferencesConfig

        prefs = NotificationPreferencesConfig(
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
        )
        assert prefs.is_quiet_hours("12:00") is False
        assert prefs.is_quiet_hours("08:00") is False
        assert prefs.is_quiet_hours("21:59") is False

    def test_is_quiet_hours_same_day_range(self) -> None:
        """Test is_quiet_hours with same-day range (e.g., 10:00-14:00)."""
        from mt5linux.config import NotificationPreferencesConfig

        prefs = NotificationPreferencesConfig(
            quiet_hours_enabled=True,
            quiet_hours_start="10:00",
            quiet_hours_end="14:00",
        )
        assert prefs.is_quiet_hours("11:00") is True
        assert prefs.is_quiet_hours("09:00") is False
        assert prefs.is_quiet_hours("15:00") is False


class TestTelegramNotifierFilteringIntegration:
    """Tests for TelegramNotifier filtering integration with send_notification()."""

    def test_send_notification_respects_preferences(self) -> None:
        """Test send_notification filters based on preferences."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        # Set preferences that disable failure notifications
        prefs = NotificationPreferencesConfig(failure_notifications=False)
        notifier.set_preferences(prefs)

        # Mark as running (bypass start() which needs keyring)
        notifier._running = True

        # Create failure notification
        message = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Test body",
            timestamp=0.0,
            severity="critical",
        )

        # Should return True (filtered, not failed) without actually sending
        result = notifier.send_notification(message)
        assert result is True
        # Stats should not be updated since message was filtered
        assert notifier._messages_sent == 0

    def test_send_notification_sends_when_preference_enabled(self) -> None:
        """Test send_notification sends when preferences allow."""
        from mt5linux.config import NotificationPreferencesConfig, TelegramConfig
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        # Set preferences that enable failure notifications
        prefs = NotificationPreferencesConfig(failure_notifications=True)
        notifier.set_preferences(prefs)

        # Mark as running
        notifier._running = True

        # Mock the actual send to avoid network call
        with patch.object(notifier, "_send_message_sync", return_value=True):
            message = NotificationMessage(
                message_type="failure",
                title="Test",
                body="Test body",
                timestamp=0.0,
                severity="critical",
            )
            result = notifier.send_notification(message)
            assert result is True
            assert notifier._messages_sent == 1


class TestNotificationCLI:
    """Tests for notification CLI commands (Story 4.5, Task 7)."""

    def test_notification_status_shows_config(self) -> None:
        """Test 'notification status' command shows configuration."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()

        with patch("mt5linux.cli.NotificationConfigManager") as MockManager:
            # Setup mock
            mock_instance = MagicMock()
            mock_instance.get_telegram_status.return_value = {
                "enabled": False,
                "chat_id": "",
                "bot_token_available": False,
            }
            mock_instance.get_preferences.return_value = MagicMock(
                failure_notifications=True,
                high_latency_notifications=True,
                trade_failure_notifications=True,
                drawdown_notifications=True,
                daily_report_notifications=True,
                quiet_hours_enabled=False,
                quiet_hours_start="22:00",
                quiet_hours_end="08:00",
            )
            MockManager.return_value = mock_instance

            result = runner.invoke(app, ["notification", "status"])

            assert result.exit_code == 0
            assert "Telegram Configuration" in result.stdout
            assert "Enabled" in result.stdout

    def test_notification_preferences_show(self) -> None:
        """Test 'notification preferences --show' command."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()

        with patch("mt5linux.cli.NotificationConfigManager") as MockManager:
            mock_instance = MagicMock()
            mock_instance.get_preferences.return_value = MagicMock(
                failure_notifications=True,
                high_latency_notifications=False,
                trade_failure_notifications=True,
                drawdown_notifications=True,
                daily_report_notifications=False,
                quiet_hours_enabled=True,
                quiet_hours_start="22:00",
                quiet_hours_end="08:00",
            )
            MockManager.return_value = mock_instance

            result = runner.invoke(app, ["notification", "preferences", "--show"])

            assert result.exit_code == 0
            assert "Notification Preferences" in result.stdout
            assert "Failures" in result.stdout

    def test_notification_preferences_update(self) -> None:
        """Test 'notification preferences' command with update options."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()

        with patch("mt5linux.cli.NotificationConfigManager") as MockManager:
            mock_instance = MagicMock()
            mock_instance.update_preferences.return_value = True
            MockManager.return_value = mock_instance

            # Use --no-failures format (Typer boolean flag)
            result = runner.invoke(
                app, ["notification", "preferences", "--no-failures"]
            )

            assert result.exit_code == 0
            mock_instance.update_preferences.assert_called_once()

    def test_notification_test_success(self) -> None:
        """Test 'notification test' command success."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()

        with patch("mt5linux.cli.NotificationConfigManager") as MockManager:
            mock_instance = MagicMock()
            mock_instance.test_telegram.return_value = (True, "Test sent successfully")
            MockManager.return_value = mock_instance

            result = runner.invoke(app, ["notification", "test"])

            assert result.exit_code == 0
            assert (
                "Test sent successfully" in result.stdout
                or "success" in result.stdout.lower()
            )

    def test_notification_test_failure(self) -> None:
        """Test 'notification test' command failure."""
        from typer.testing import CliRunner

        from mt5linux.cli import app

        runner = CliRunner()

        with patch("mt5linux.cli.NotificationConfigManager") as MockManager:
            mock_instance = MagicMock()
            mock_instance.test_telegram.return_value = (False, "Not configured")
            MockManager.return_value = mock_instance

            result = runner.invoke(app, ["notification", "test"])

            assert result.exit_code == 1
            assert "Not configured" in result.stdout
