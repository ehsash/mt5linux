"""Unit tests for mt5linux.monitoring.notifier module (Story 4.4)."""

import time
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

from mt5linux.config import TelegramConfig

pytestmark = pytest.mark.unit  # All tests in this module are unit tests


class TestTelegramNotifierInit:
    """Tests for TelegramNotifier initialization (Task 2)."""

    def test_init_with_default_config(self) -> None:
        """Test TelegramNotifier initializes with default config."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        assert notifier.is_enabled is False
        assert notifier.is_running is False

    def test_init_with_custom_config(self) -> None:
        """Test TelegramNotifier initializes with custom config."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(
            enabled=True,
            chat_id="123456789",
            retry_count=5,
            retry_delay_secs=2.0,
            delivery_timeout_secs=10.0,
        )
        notifier = TelegramNotifier(config=config)
        assert notifier._enabled is True
        assert notifier._chat_id == "123456789"
        assert notifier._retry_count == 5
        assert notifier._retry_delay_secs == 2.0
        assert notifier._delivery_timeout_secs == 10.0

    def test_init_disabled_by_default(self) -> None:
        """Test TelegramNotifier is disabled by default."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        assert notifier._enabled is False

    def test_init_bot_token_is_none(self) -> None:
        """Test TelegramNotifier bot_token is None initially."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        assert notifier._bot_token is None

    def test_init_bot_is_none(self) -> None:
        """Test TelegramNotifier bot is None initially."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        assert notifier._bot is None

    def test_init_running_is_false(self) -> None:
        """Test TelegramNotifier is not running initially."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        assert notifier._running is False

    def test_init_statistics_are_zero(self) -> None:
        """Test TelegramNotifier statistics are initialized to zero."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        assert notifier._messages_sent == 0
        assert notifier._messages_failed == 0
        assert notifier._retry_count_total == 0
        assert len(notifier._delivery_times) == 0


class TestTelegramNotifierLifecycle:
    """Tests for TelegramNotifier start/stop lifecycle (Task 2)."""

    def test_start_disabled_returns_false(self) -> None:
        """Test start() returns False when disabled."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=False)
        notifier = TelegramNotifier(config=config)
        result = notifier.start()
        assert result is False
        assert notifier.is_running is False

    @patch("mt5linux.monitoring.notifier.keyring")
    def test_start_missing_bot_token_returns_false(
        self, mock_keyring: MagicMock
    ) -> None:
        """Test start() returns False when bot token not in keyring."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = None
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        result = notifier.start()
        assert result is False
        assert notifier.is_running is False
        mock_keyring.get_password.assert_called_once_with(
            "mt5linux", "telegram_bot_token"
        )

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_start_with_valid_token_returns_true(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test start() returns True with valid bot token."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_bot_token_12345"
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        result = notifier.start()
        assert result is True
        assert notifier.is_running is True
        mock_bot_class.assert_called_once_with(token="test_bot_token_12345")

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_stop_sets_running_to_false(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test stop() sets running to False."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_bot_token_12345"
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()
        assert notifier.is_running is True
        notifier.stop()
        assert notifier.is_running is False

    def test_stop_when_not_running_is_safe(self) -> None:
        """Test stop() is safe to call when not running."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        notifier.stop()  # Should not raise
        assert notifier.is_running is False

    def test_is_enabled_property(self) -> None:
        """Test is_enabled property returns correct value."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        config_disabled = TelegramConfig(enabled=False)
        notifier_disabled = TelegramNotifier(config=config_disabled)
        assert notifier_disabled.is_enabled is False

        config_enabled = TelegramConfig(enabled=True, chat_id="123")
        notifier_enabled = TelegramNotifier(config=config_enabled)
        assert notifier_enabled.is_enabled is True

    def test_is_running_property(self) -> None:
        """Test is_running property returns correct value."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        assert notifier.is_running is False


class TestTelegramNotifierCredentials:
    """Tests for credential loading from keyring (Task 3)."""

    @patch("mt5linux.monitoring.notifier.keyring")
    def test_credentials_loaded_from_keyring(self, mock_keyring: MagicMock) -> None:
        """Test bot token is loaded from keyring with correct service/username."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "my_secret_bot_token"
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        with patch("mt5linux.monitoring.notifier.Bot"):
            notifier.start()

        mock_keyring.get_password.assert_called_once_with(
            "mt5linux", "telegram_bot_token"
        )
        assert notifier._bot_token == "my_secret_bot_token"

    @patch("mt5linux.monitoring.notifier.keyring")
    def test_keyring_unavailable_handled_gracefully(
        self, mock_keyring: MagicMock
    ) -> None:
        """Test keyring unavailable is handled gracefully."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.side_effect = Exception("Keyring not available")
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        result = notifier.start()
        assert result is False
        assert notifier.is_running is False

    @patch("mt5linux.monitoring.notifier.keyring")
    def test_empty_bot_token_handled_gracefully(self, mock_keyring: MagicMock) -> None:
        """Test empty bot token is handled gracefully."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = ""
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        result = notifier.start()
        assert result is False
        assert notifier.is_running is False


class TestNotificationMessage:
    """Tests for NotificationMessage dataclass (Task 5)."""

    def test_notification_message_creation(self) -> None:
        """Test NotificationMessage can be created."""
        from mt5linux.monitoring.notifier import NotificationMessage

        msg = NotificationMessage(
            message_type="failure",
            title="Connection Lost",
            body="MT5 connection failed",
            timestamp=1234567890.0,
            severity="critical",
        )
        assert msg.message_type == "failure"
        assert msg.title == "Connection Lost"
        assert msg.body == "MT5 connection failed"
        assert msg.timestamp == 1234567890.0
        assert msg.severity == "critical"

    def test_notification_message_frozen(self) -> None:
        """Test NotificationMessage is immutable (frozen=True)."""
        from mt5linux.monitoring.notifier import NotificationMessage

        msg = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Body",
            timestamp=0.0,
            severity="info",
        )
        with pytest.raises(AttributeError):
            msg.title = "Modified"  # type: ignore[misc]

    def test_notification_message_slots(self) -> None:
        """Test NotificationMessage uses slots for memory efficiency."""
        from mt5linux.monitoring.notifier import NotificationMessage

        msg = NotificationMessage(
            message_type="failure",
            title="Test",
            body="Body",
            timestamp=0.0,
            severity="info",
        )
        assert hasattr(msg, "__slots__") or not hasattr(msg, "__dict__")


class TestNotificationMessageFormatting:
    """Tests for NotificationMessage formatting (Task 5)."""

    def test_format_telegram_critical(self) -> None:
        """Test formatting critical notification."""
        from mt5linux.monitoring.notifier import NotificationMessage

        msg = NotificationMessage(
            message_type="failure",
            title="Connection Lost",
            body="MT5 server unreachable",
            timestamp=1234567890.0,
            severity="critical",
        )
        formatted = msg.format_telegram()
        assert "🔴" in formatted  # Critical emoji
        assert "<b>Connection Lost</b>" in formatted
        assert "MT5 server unreachable" in formatted

    def test_format_telegram_warning(self) -> None:
        """Test formatting warning notification."""
        from mt5linux.monitoring.notifier import NotificationMessage

        msg = NotificationMessage(
            message_type="high_latency",
            title="High Latency Detected",
            body="Latency: 350ms",
            timestamp=1234567890.0,
            severity="warning",
        )
        formatted = msg.format_telegram()
        assert "🟡" in formatted  # Warning emoji
        assert "<b>High Latency Detected</b>" in formatted

    def test_format_telegram_info(self) -> None:
        """Test formatting info notification."""
        from mt5linux.monitoring.notifier import NotificationMessage

        msg = NotificationMessage(
            message_type="daily_report",
            title="Daily Report",
            body="Summary of trading activity",
            timestamp=1234567890.0,
            severity="info",
        )
        formatted = msg.format_telegram()
        assert "🔵" in formatted  # Info emoji
        assert "<b>Daily Report</b>" in formatted

    def test_format_telegram_unknown_severity(self) -> None:
        """Test formatting with unknown severity uses default emoji."""
        from mt5linux.monitoring.notifier import NotificationMessage

        msg = NotificationMessage(
            message_type="test",
            title="Test",
            body="Test body",
            timestamp=1234567890.0,
            severity="unknown",
        )
        formatted = msg.format_telegram()
        assert "⚪" in formatted  # Default emoji


class TestTelegramNotifierSending:
    """Tests for TelegramNotifier message sending (Task 4, 6)."""

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_send_notification_not_running_returns_false(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test send_notification returns False when not running."""
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        # Don't call start()

        msg = NotificationMessage(
            message_type="test",
            title="Test",
            body="Body",
            timestamp=0.0,
            severity="info",
        )
        result = notifier.send_notification(msg)
        assert result is False

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_send_notification_success(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test successful notification sending."""
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        # Mock async send_message
        async def mock_send(*args, **kwargs):
            return MagicMock()

        mock_bot.send_message = mock_send

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        msg = NotificationMessage(
            message_type="test",
            title="Test",
            body="Body",
            timestamp=time.time(),
            severity="info",
        )
        result = notifier.send_notification(msg)
        assert result is True
        assert notifier._messages_sent == 1
        assert notifier._messages_failed == 0

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_send_notification_failure_retries(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notification failure triggers retries."""
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        # Mock async send_message to always fail
        async def mock_send_fail(*args, **kwargs):
            raise Exception("Telegram API error")

        mock_bot.send_message = mock_send_fail

        config = TelegramConfig(
            enabled=True,
            chat_id="123456789",
            retry_count=2,
            retry_delay_secs=0.01,  # Fast retries for test
        )
        notifier = TelegramNotifier(config=config)
        notifier.start()

        msg = NotificationMessage(
            message_type="test",
            title="Test",
            body="Body",
            timestamp=time.time(),
            severity="info",
        )
        result = notifier.send_notification(msg)
        assert result is False
        assert notifier._messages_sent == 0
        assert notifier._messages_failed == 1
        # retry_count=2 means 1 initial + 2 retries = 3 attempts
        assert notifier._retry_count_total == 2  # Only count actual retries

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_send_notification_records_delivery_time(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test successful send records delivery time."""
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        async def mock_send(*args, **kwargs):
            return MagicMock()

        mock_bot.send_message = mock_send

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        msg = NotificationMessage(
            message_type="test",
            title="Test",
            body="Body",
            timestamp=time.time(),
            severity="info",
        )
        notifier.send_notification(msg)
        assert len(notifier._delivery_times) == 1
        assert notifier._delivery_times[0] >= 0


class TestTelegramNotifierRetry:
    """Tests for retry logic with exponential backoff (Task 6)."""

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_exponential_backoff_timing(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test exponential backoff delay calculation."""
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        call_times = []

        async def mock_send_fail(*args, **kwargs):
            call_times.append(time.time())
            raise Exception("Telegram API error")

        mock_bot.send_message = mock_send_fail

        config = TelegramConfig(
            enabled=True,
            chat_id="123456789",
            retry_count=2,
            retry_delay_secs=0.1,  # 100ms base delay
        )
        notifier = TelegramNotifier(config=config)
        notifier.start()

        msg = NotificationMessage(
            message_type="test",
            title="Test",
            body="Body",
            timestamp=time.time(),
            severity="info",
        )
        notifier.send_notification(msg)

        # Should have 3 attempts (1 initial + 2 retries)
        assert len(call_times) == 3

        # Check exponential backoff: first retry ~0.1s, second retry ~0.2s
        if len(call_times) >= 2:
            first_gap = call_times[1] - call_times[0]
            assert first_gap >= 0.08  # Allow some tolerance

        if len(call_times) >= 3:
            second_gap = call_times[2] - call_times[1]
            assert second_gap >= 0.15  # ~0.2s (2^1 * 0.1)


class TestTelegramNotifierCallbacks:
    """Tests for notification type callback methods (Task 7)."""

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_notify_failure_creates_correct_message(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notify_failure creates correct notification message."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        async def mock_send(*args, **kwargs):
            return MagicMock()

        mock_bot.send_message = mock_send

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        # Create a mock failure info
        failure_info = MagicMock()
        failure_info.failure_type = "heartbeat_timeout"
        failure_info.timestamp = time.time()
        failure_info.message = "Connection lost"

        result = notifier.notify_failure(failure_info)
        assert result is True

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_notify_high_latency_creates_correct_message(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notify_high_latency creates correct notification message."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        async def mock_send(*args, **kwargs):
            return MagicMock()

        mock_bot.send_message = mock_send

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        # Create a mock latency alert
        alert = MagicMock()
        alert.latency_ms = 350.0
        alert.threshold_ms = 200.0
        alert.timestamp = time.time()

        result = notifier.notify_high_latency(alert)
        assert result is True

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_notify_trade_failure_creates_correct_message(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notify_trade_failure creates correct notification message."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        async def mock_send(*args, **kwargs):
            return MagicMock()

        mock_bot.send_message = mock_send

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        # Create a mock trade failure info
        failure_info = MagicMock()
        failure_info.symbol = "EURUSD"
        failure_info.order_type = "BUY"
        failure_info.error_code = 10004
        failure_info.timestamp = time.time()

        result = notifier.notify_trade_failure(failure_info)
        assert result is True

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_notify_drawdown_breach_creates_correct_message(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notify_drawdown_breach creates correct notification message."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        async def mock_send(*args, **kwargs):
            return MagicMock()

        mock_bot.send_message = mock_send

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        # Create a mock drawdown breach info
        drawdown_info = MagicMock()
        drawdown_info.current_drawdown = 0.15
        drawdown_info.threshold = 0.10
        drawdown_info.timestamp = time.time()

        result = notifier.notify_drawdown_breach(drawdown_info)
        assert result is True

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_notify_daily_report_creates_correct_message(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notify_daily_report creates correct notification message."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        async def mock_send(*args, **kwargs):
            return MagicMock()

        mock_bot.send_message = mock_send

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        # Create a mock daily report
        report = MagicMock()
        report.report_date = "2026-01-30"
        report.summary = "5 trades, +2.5% P&L"
        report.timestamp = time.time()

        result = notifier.notify_daily_report(report)
        assert result is True


class TestTelegramNotifierStatistics:
    """Tests for statistics API (Task 8)."""

    def test_get_status_disabled(self) -> None:
        """Test get_status returns correct values when disabled."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=False)
        notifier = TelegramNotifier(config=config)
        status = notifier.get_status()

        assert status["enabled"] is False
        assert status["configured"] is False
        assert status["bot_token_available"] is False
        assert status["running"] is False
        assert status["messages_sent"] == 0
        assert status["messages_failed"] == 0

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_get_status_running(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test get_status returns correct values when running."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()
        status = notifier.get_status()

        assert status["enabled"] is True
        assert status["configured"] is True
        assert status["bot_token_available"] is True
        assert status["running"] is True

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_get_status_includes_statistics(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test get_status includes message statistics."""
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        async def mock_send(*args, **kwargs):
            return MagicMock()

        mock_bot.send_message = mock_send

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        # Send a message
        msg = NotificationMessage(
            message_type="test",
            title="Test",
            body="Body",
            timestamp=time.time(),
            severity="info",
        )
        notifier.send_notification(msg)

        status = notifier.get_status()
        assert status["messages_sent"] == 1
        assert status["messages_failed"] == 0
        assert "last_message_time" in status
        assert "average_delivery_time_ms" in status
        assert "max_delivery_time_ms" in status
        assert "retry_count_total" in status


class TestTelegramNotifierDisabled:
    """Tests for disabled state behavior (Task 9)."""

    def test_disabled_notifier_does_not_send(self) -> None:
        """Test disabled notifier does not attempt to send."""
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        config = TelegramConfig(enabled=False)
        notifier = TelegramNotifier(config=config)

        msg = NotificationMessage(
            message_type="test",
            title="Test",
            body="Body",
            timestamp=time.time(),
            severity="info",
        )
        result = notifier.send_notification(msg)
        assert result is False

    def test_disabled_notifier_callbacks_return_false(self) -> None:
        """Test disabled notifier callbacks return False without errors."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=False)
        notifier = TelegramNotifier(config=config)

        # All callbacks should return False safely
        assert notifier.notify_failure(MagicMock()) is False
        assert notifier.notify_high_latency(MagicMock()) is False
        assert notifier.notify_trade_failure(MagicMock()) is False
        assert notifier.notify_drawdown_breach(MagicMock()) is False
        assert notifier.notify_daily_report(MagicMock()) is False


class TestTelegramNotifierThreadSafety:
    """Tests for thread safety (RLock pattern)."""

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_concurrent_sends_are_thread_safe(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test concurrent message sends are thread-safe."""
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        async def mock_send(*args, **kwargs):
            return MagicMock()

        mock_bot.send_message = mock_send

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        results = []

        def send_message():
            msg = NotificationMessage(
                message_type="test",
                title="Test",
                body="Body",
                timestamp=time.time(),
                severity="info",
            )
            result = notifier.send_notification(msg)
            results.append(result)

        # Create multiple threads
        threads = [Thread(target=send_message) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All sends should succeed
        assert all(results)
        assert notifier._messages_sent == 10


class TestTelegramNotifierKeyringUnavailable:
    """Tests for keyring unavailable scenario (M2 fix)."""

    def test_start_when_keyring_module_is_none(self) -> None:
        """Test start() handles keyring module being None (import failed)."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)

        # Patch keyring to None to simulate import failure
        with patch("mt5linux.monitoring.notifier.keyring", None):
            result = notifier.start()
            assert result is False
            assert notifier.is_running is False


class TestTelegramNotifierClearStatistics:
    """Tests for clear_statistics() method (H2 fix)."""

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_clear_statistics_resets_counters(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test clear_statistics() resets all counters."""
        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        async def mock_send(*args, **kwargs):
            return MagicMock()

        mock_bot.send_message = mock_send

        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        # Send some messages to accumulate stats
        msg = NotificationMessage(
            message_type="test",
            title="Test",
            body="Body",
            timestamp=time.time(),
            severity="info",
        )
        notifier.send_notification(msg)
        notifier.send_notification(msg)

        assert notifier._messages_sent == 2
        assert len(notifier._delivery_times) == 2

        # Clear statistics
        notifier.clear_statistics()

        assert notifier._messages_sent == 0
        assert notifier._messages_failed == 0
        assert notifier._retry_count_total == 0
        assert len(notifier._delivery_times) == 0
        assert notifier._last_message_time is None

    def test_clear_statistics_when_not_running(self) -> None:
        """Test clear_statistics() is safe when notifier not running."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        notifier = TelegramNotifier()
        # Should not raise
        notifier.clear_statistics()
        assert notifier._messages_sent == 0


class TestTelegramNotifierInputValidation:
    """Tests for input validation on callback methods (H3 fix)."""

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_notify_failure_with_none_returns_false(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notify_failure returns False when called with None."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        result = notifier.notify_failure(None)
        assert result is False

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_notify_high_latency_with_none_returns_false(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notify_high_latency returns False when called with None."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        result = notifier.notify_high_latency(None)
        assert result is False

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_notify_trade_failure_with_none_returns_false(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notify_trade_failure returns False when called with None."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        result = notifier.notify_trade_failure(None)
        assert result is False

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_notify_drawdown_breach_with_none_returns_false(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notify_drawdown_breach returns False when called with None."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        result = notifier.notify_drawdown_breach(None)
        assert result is False

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_notify_daily_report_with_none_returns_false(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test notify_daily_report returns False when called with None."""
        from mt5linux.monitoring.notifier import TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        config = TelegramConfig(enabled=True, chat_id="123456789")
        notifier = TelegramNotifier(config=config)
        notifier.start()

        result = notifier.notify_daily_report(None)
        assert result is False


class TestTelegramNotifierTimeout:
    """Tests for delivery timeout enforcement (H1 fix)."""

    @patch("mt5linux.monitoring.notifier.Bot")
    @patch("mt5linux.monitoring.notifier.keyring")
    def test_send_message_timeout_returns_false(
        self, mock_keyring: MagicMock, mock_bot_class: MagicMock
    ) -> None:
        """Test send times out and returns False when API is slow."""
        import asyncio

        from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier

        mock_keyring.get_password.return_value = "test_token"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot

        # Mock a slow API call that exceeds timeout
        async def mock_slow_send(*args, **kwargs):
            await asyncio.sleep(10)  # Sleep longer than timeout
            return MagicMock()

        mock_bot.send_message = mock_slow_send

        config = TelegramConfig(
            enabled=True,
            chat_id="123456789",
            delivery_timeout_secs=0.1,  # Very short timeout for test
            retry_count=0,  # No retries to speed up test
        )
        notifier = TelegramNotifier(config=config)
        notifier.start()

        msg = NotificationMessage(
            message_type="test",
            title="Test",
            body="Body",
            timestamp=time.time(),
            severity="info",
        )
        result = notifier.send_notification(msg)
        assert result is False
        assert notifier._messages_failed == 1
