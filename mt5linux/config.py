"""Configuration management module for mt5linux."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from mt5linux.detection import DetectionResult

try:
    import tomli
except ImportError:
    tomli = None  # type: ignore

try:
    import tomli_w
except ImportError:
    tomli_w = None  # type: ignore

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

try:
    from typer import echo
except ImportError:
    echo = print  # type: ignore


@dataclass
class WineConfig:
    """Wine configuration section."""

    prefix_path: Optional[str] = None


@dataclass
class ServerConfig:
    """Server configuration section."""

    host: str = "localhost"
    port: int = 18812


@dataclass(frozen=True, slots=True)
class NotificationPreferencesConfig:
    """Configuration for notification preferences (Story 4.5).

    Configures which notification types are enabled and quiet hours per FR58.

    Attributes:
        failure_notifications: Enable system failure notifications (default: True).
        high_latency_notifications: Enable high latency notifications (default: True).
        trade_failure_notifications: Enable trade failure notifications (default: True).
        drawdown_notifications: Enable drawdown breach notifications (default: True).
        daily_report_notifications: Enable daily report notifications (default: True).
        quiet_hours_enabled: Enable quiet hours filtering (default: False).
        quiet_hours_start: Quiet hours start time HH:MM (default: 22:00).
        quiet_hours_end: Quiet hours end time HH:MM (default: 08:00).

    Raises:
        ValueError: If quiet_hours_start or quiet_hours_end has invalid HH:MM format.
    """

    failure_notifications: bool = True
    high_latency_notifications: bool = True
    trade_failure_notifications: bool = True
    drawdown_notifications: bool = True
    daily_report_notifications: bool = True
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self._is_valid_time(self.quiet_hours_start):
            raise ValueError(
                f"Invalid time format for quiet_hours_start: {self.quiet_hours_start}, "
                "expected HH:MM (00:00-23:59)"
            )
        if not self._is_valid_time(self.quiet_hours_end):
            raise ValueError(
                f"Invalid time format for quiet_hours_end: {self.quiet_hours_end}, "
                "expected HH:MM (00:00-23:59)"
            )

    @staticmethod
    def _is_valid_time(time_str: str) -> bool:
        """Check if time string is valid HH:MM format."""
        import re

        if not re.match(r"^\d{2}:\d{2}$", time_str):
            return False
        hour, minute = map(int, time_str.split(":"))
        return 0 <= hour <= 23 and 0 <= minute <= 59

    def is_quiet_hours(self, current_time: Optional[str] = None) -> bool:
        """Check if current time is within quiet hours.

        Args:
            current_time: Time to check in HH:MM format. If None, uses current time.

        Returns:
            True if within quiet hours (notifications should be suppressed),
            False otherwise.
        """
        if not self.quiet_hours_enabled:
            return False

        if current_time is None:
            from datetime import datetime

            current_time = datetime.now().strftime("%H:%M")

        # Handle overnight quiet hours (e.g., 22:00 to 08:00)
        if self.quiet_hours_start > self.quiet_hours_end:
            # Overnight: quiet if time >= start OR time < end
            return (
                current_time >= self.quiet_hours_start
                or current_time < self.quiet_hours_end
            )
        else:
            # Same day: quiet if start <= time < end
            return self.quiet_hours_start <= current_time < self.quiet_hours_end


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    """Configuration for Telegram notifications (Story 4.4).

    Configures Telegram notification delivery per FR54-FR57, NFR44-NFR47.

    Attributes:
        enabled: Whether Telegram notifications are enabled (default: False).
        chat_id: Telegram chat ID to send notifications to (required when enabled).
        retry_count: Number of retry attempts on failure (default: 3).
        retry_delay_secs: Base delay between retries in seconds (default: 1.0).
        delivery_timeout_secs: Max seconds to deliver notification (default: 5.0, NFR47).

    Raises:
        ValueError: If enabled=True but chat_id is empty.
        ValueError: If retry_count is negative.
        ValueError: If retry_delay_secs or delivery_timeout_secs is non-positive.
    """

    enabled: bool = False  # Default: disabled (opt-in)
    chat_id: str = ""  # Required when enabled
    retry_count: int = 3  # Default: 3 retries
    retry_delay_secs: float = 1.0  # Default: 1 second base delay
    delivery_timeout_secs: float = 5.0  # NFR47: 5 second delivery

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.enabled and not self.chat_id:
            raise ValueError("chat_id is required when telegram is enabled")
        if self.retry_count < 0:
            raise ValueError(
                f"retry_count must be non-negative, got {self.retry_count}"
            )
        if self.retry_delay_secs <= 0:
            raise ValueError(
                f"retry_delay_secs must be positive, got {self.retry_delay_secs}"
            )
        if self.delivery_timeout_secs <= 0:
            raise ValueError(
                f"delivery_timeout_secs must be positive, got {self.delivery_timeout_secs}"
            )


@dataclass(frozen=True, slots=True)
class LatencyConfig:
    """Configuration for latency monitoring (Story 4.3).

    Configures latency measurement and alerting per FR52.

    Attributes:
        enabled: Whether latency monitoring is enabled (default: True).
        threshold_ms: Latency threshold in milliseconds (FR52, default: 200ms).
        warning_delivery_secs: Warning delivery timeout in seconds (default: 5.0).

    Raises:
        ValueError: If threshold_ms or warning_delivery_secs is non-positive.
    """

    enabled: bool = True  # Default: enabled
    threshold_ms: float = 200.0  # FR52: 200ms default threshold
    warning_delivery_secs: float = 5.0  # Default: 5 second delivery warning

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.threshold_ms <= 0:
            raise ValueError(f"threshold_ms must be positive, got {self.threshold_ms}")
        if self.warning_delivery_secs <= 0:
            raise ValueError(
                f"warning_delivery_secs must be positive, got {self.warning_delivery_secs}"
            )


@dataclass(frozen=True, slots=True)
class DailyReportsConfig:
    """Configuration for daily reports (Story 4.2).

    Configures report scheduling per FR48, FR49, FR50.

    Attributes:
        enabled: Whether daily reports are enabled (FR50, default: off).
        times: Tuple of times in HH:MM format (FR48, default: 09:00, 21:00).
        timezone: Timezone for report scheduling (FR49, default: UTC).

    Raises:
        ValueError: If time format is invalid, timezone is invalid, or times is empty.
    """

    enabled: bool = False  # FR50: default off
    times: Tuple[str, ...] = ("09:00", "21:00")  # FR48: default times
    timezone: str = "UTC"  # FR49: default timezone

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate times is not empty
        if not self.times:
            raise ValueError(
                "At least one time must be specified for daily_reports.times"
            )

        # Validate time format for each time
        for time_str in self.times:
            if not self._is_valid_time(time_str):
                raise ValueError(
                    f"Invalid time format: {time_str}, expected HH:MM (00:00-23:59)"
                )

        # Validate timezone
        try:
            import pytz

            pytz.timezone(self.timezone)
        except Exception:
            raise ValueError(f"Invalid timezone: {self.timezone}")

    @staticmethod
    def _is_valid_time(time_str: str) -> bool:
        """Check if time string is valid HH:MM format."""
        import re

        if not re.match(r"^\d{2}:\d{2}$", time_str):
            return False
        hour, minute = map(int, time_str.split(":"))
        return 0 <= hour <= 23 and 0 <= minute <= 59


@dataclass(frozen=True, slots=True)
class NotificationChannelsConfig:
    """Configuration for notification channels (Story 4.6).

    Configures which notification channels are enabled and their settings.

    Attributes:
        enabled_channels: Tuple of enabled channel names (default: ("telegram",)).
        console_enabled: Whether console channel is enabled (default: False).
        console_log_level: Log level for console notifications (default: "INFO").

    Raises:
        ValueError: If console_log_level is not a valid log level.
    """

    enabled_channels: Tuple[str, ...] = ("telegram",)  # Use tuple for frozen dataclass
    console_enabled: bool = False
    console_log_level: str = "INFO"

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate log level
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if self.console_log_level.upper() not in valid_levels:
            raise ValueError(
                f"Invalid console_log_level: {self.console_log_level}, "
                f"expected one of {valid_levels}"
            )


@dataclass(frozen=True, slots=True)
class AnalyticsConfig:
    """Configuration for analytics engine (Story 4.7).

    Attributes:
        enabled: Whether analytics are enabled (default: True).
        history_window_hours: Hours of data to analyze (default: 24).
        include_in_daily_reports: Include analytics in daily reports (default: True).

    Raises:
        ValueError: If history_window_hours is not positive.
    """

    enabled: bool = True
    history_window_hours: int = 24
    include_in_daily_reports: bool = True

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.history_window_hours <= 0:
            raise ValueError(
                f"history_window_hours must be positive, got {self.history_window_hours}"
            )


@dataclass
class MonitoringConfig:
    """Monitoring configuration section (Story 4.1).

    Configures heartbeat system parameters per FR46, FR47, NFR9, NFR12.

    Raises:
        ValueError: If interval or threshold is non-positive, or interval >= threshold.
    """

    heartbeat_interval: float = 30.0  # FR46, NFR9: 30 second heartbeat
    heartbeat_failure_threshold: float = (
        45.0  # FR47, NFR12: 45 second failure threshold
    )

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.heartbeat_interval <= 0:
            raise ValueError(
                f"heartbeat_interval must be positive, got {self.heartbeat_interval}"
            )
        if self.heartbeat_failure_threshold <= 0:
            raise ValueError(
                f"heartbeat_failure_threshold must be positive, got {self.heartbeat_failure_threshold}"
            )
        if self.heartbeat_interval >= self.heartbeat_failure_threshold:
            raise ValueError(
                f"heartbeat_interval ({self.heartbeat_interval}) must be less than "
                f"heartbeat_failure_threshold ({self.heartbeat_failure_threshold})"
            )


@dataclass
class Config:
    """Main configuration structure."""

    wine: WineConfig = field(default_factory=WineConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    daily_reports: DailyReportsConfig = field(default_factory=DailyReportsConfig)
    latency: LatencyConfig = field(default_factory=LatencyConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    notification_preferences: NotificationPreferencesConfig = field(
        default_factory=NotificationPreferencesConfig
    )
    notification_channels: NotificationChannelsConfig = field(
        default_factory=NotificationChannelsConfig
    )
    analytics: AnalyticsConfig = field(default_factory=AnalyticsConfig)

    def to_dict(self) -> dict:
        """Convert configuration to dictionary for TOML serialization."""
        return {
            "wine": {
                "prefix_path": self.wine.prefix_path,
            },
            "server": {
                "host": self.server.host,
                "port": self.server.port,
            },
            "monitoring": {
                "heartbeat_interval": self.monitoring.heartbeat_interval,
                "heartbeat_failure_threshold": self.monitoring.heartbeat_failure_threshold,
            },
            "daily_reports": {
                "enabled": self.daily_reports.enabled,
                "times": list(
                    self.daily_reports.times
                ),  # Convert tuple to list for TOML
                "timezone": self.daily_reports.timezone,
            },
            "latency": {
                "enabled": self.latency.enabled,
                "threshold_ms": self.latency.threshold_ms,
                "warning_delivery_secs": self.latency.warning_delivery_secs,
            },
            "telegram": {
                "enabled": self.telegram.enabled,
                "chat_id": self.telegram.chat_id,
                "retry_count": self.telegram.retry_count,
                "retry_delay_secs": self.telegram.retry_delay_secs,
                "delivery_timeout_secs": self.telegram.delivery_timeout_secs,
            },
            "notification_preferences": {
                "failure_notifications": self.notification_preferences.failure_notifications,
                "high_latency_notifications": self.notification_preferences.high_latency_notifications,
                "trade_failure_notifications": self.notification_preferences.trade_failure_notifications,
                "drawdown_notifications": self.notification_preferences.drawdown_notifications,
                "daily_report_notifications": self.notification_preferences.daily_report_notifications,
                "quiet_hours_enabled": self.notification_preferences.quiet_hours_enabled,
                "quiet_hours_start": self.notification_preferences.quiet_hours_start,
                "quiet_hours_end": self.notification_preferences.quiet_hours_end,
            },
            "notification_channels": {
                "enabled_channels": list(
                    self.notification_channels.enabled_channels
                ),  # Convert tuple to list for TOML
                "console_enabled": self.notification_channels.console_enabled,
                "console_log_level": self.notification_channels.console_log_level,
            },
            "analytics": {
                "enabled": self.analytics.enabled,
                "history_window_hours": self.analytics.history_window_hours,
                "include_in_daily_reports": self.analytics.include_in_daily_reports,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create configuration from dictionary."""
        wine_data = data.get("wine", {})
        server_data = data.get("server", {})
        monitoring_data = data.get("monitoring", {})
        daily_reports_data = data.get("daily_reports", {})
        latency_data = data.get("latency", {})
        telegram_data = data.get("telegram", {})
        notification_preferences_data = data.get("notification_preferences", {})
        notification_channels_data = data.get("notification_channels", {})
        analytics_data = data.get("analytics", {})

        # Convert times list to tuple if present
        times_list = daily_reports_data.get("times", ["09:00", "21:00"])
        times_tuple = tuple(times_list) if isinstance(times_list, list) else times_list

        return cls(
            wine=WineConfig(
                prefix_path=wine_data.get("prefix_path"),
            ),
            server=ServerConfig(
                host=server_data.get("host", "localhost"),
                port=server_data.get("port", 18812),
            ),
            monitoring=MonitoringConfig(
                heartbeat_interval=monitoring_data.get("heartbeat_interval", 30.0),
                heartbeat_failure_threshold=monitoring_data.get(
                    "heartbeat_failure_threshold", 45.0
                ),
            ),
            daily_reports=DailyReportsConfig(
                enabled=daily_reports_data.get("enabled", False),
                times=times_tuple,
                timezone=daily_reports_data.get("timezone", "UTC"),
            ),
            latency=LatencyConfig(
                enabled=latency_data.get("enabled", True),
                threshold_ms=latency_data.get("threshold_ms", 200.0),
                warning_delivery_secs=latency_data.get("warning_delivery_secs", 5.0),
            ),
            telegram=TelegramConfig(
                enabled=telegram_data.get("enabled", False),
                chat_id=telegram_data.get("chat_id", ""),
                retry_count=telegram_data.get("retry_count", 3),
                retry_delay_secs=telegram_data.get("retry_delay_secs", 1.0),
                delivery_timeout_secs=telegram_data.get("delivery_timeout_secs", 5.0),
            ),
            notification_preferences=NotificationPreferencesConfig(
                failure_notifications=notification_preferences_data.get(
                    "failure_notifications", True
                ),
                high_latency_notifications=notification_preferences_data.get(
                    "high_latency_notifications", True
                ),
                trade_failure_notifications=notification_preferences_data.get(
                    "trade_failure_notifications", True
                ),
                drawdown_notifications=notification_preferences_data.get(
                    "drawdown_notifications", True
                ),
                daily_report_notifications=notification_preferences_data.get(
                    "daily_report_notifications", True
                ),
                quiet_hours_enabled=notification_preferences_data.get(
                    "quiet_hours_enabled", False
                ),
                quiet_hours_start=notification_preferences_data.get(
                    "quiet_hours_start", "22:00"
                ),
                quiet_hours_end=notification_preferences_data.get(
                    "quiet_hours_end", "08:00"
                ),
            ),
            notification_channels=NotificationChannelsConfig(
                enabled_channels=tuple(
                    notification_channels_data.get("enabled_channels", ["telegram"])
                ),
                console_enabled=notification_channels_data.get(
                    "console_enabled", False
                ),
                console_log_level=notification_channels_data.get(
                    "console_log_level", "INFO"
                ),
            ),
            analytics=AnalyticsConfig(
                enabled=analytics_data.get("enabled", True),
                history_window_hours=analytics_data.get("history_window_hours", 24),
                include_in_daily_reports=analytics_data.get(
                    "include_in_daily_reports", True
                ),
            ),
        )


# Singleton instance
_config_instance: Optional[Config] = None


def _get_config_path() -> Path:
    """
    Get the configuration file path.

    Checks MT5LINUX_CONFIG_PATH environment variable first,
    then falls back to default: .mt5/config.toml in current working directory.

    This keeps config local to the project, allowing multiple MT5 instances
    without conflicts.

    Returns:
        Path to configuration file
    """
    env_path = os.environ.get("MT5LINUX_CONFIG_PATH")
    if env_path:
        return Path(env_path)

    # Default location: local to project (same directory as wine prefix)
    # This allows multiple MT5 instances without conflicts
    config_dir = Path.cwd() / ".mt5"
    return config_dir / "config.toml"


def _ensure_config_directory(config_path: Path) -> None:
    """Ensure configuration directory exists."""
    config_dir = config_path.parent
    if not config_dir.exists():
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created configuration directory: {config_dir}")
        except OSError as e:
            logger.error(f"Failed to create configuration directory {config_dir}: {e}")
            raise


def load_config() -> Config:
    """
    Load configuration from file.

    Returns:
        Config instance with loaded or default values
    """
    global _config_instance

    if tomli is None:
        logger.warning("tomli library not available, using default configuration")
        _config_instance = Config()
        return _config_instance

    config_path = _get_config_path()

    # If file doesn't exist, return defaults
    if not config_path.exists():
        logger.debug(f"Configuration file not found: {config_path}, using defaults")
        _config_instance = Config()
        return _config_instance

    # Load from file
    try:
        with open(config_path, "rb") as f:
            data = tomli.load(f)
        logger.debug(f"Loaded configuration from: {config_path}")
        _config_instance = Config.from_dict(data)
        return _config_instance
    except Exception as e:
        logger.warning(
            f"Failed to load configuration from {config_path}: {e}, using defaults"
        )
        _config_instance = Config()
        return _config_instance


def save_config(config: Optional[Config] = None) -> bool:
    """
    Save configuration to file.

    Args:
        config: Configuration to save. If None, uses current singleton instance.

    Returns:
        True if saved successfully, False otherwise
    """
    if tomli_w is None and tomli is None:
        logger.error("tomli/tomli_w library not available, cannot save configuration")
        return False

    if config is None:
        config = get_config()

    config_path = _get_config_path()

    try:
        _ensure_config_directory(config_path)

        # Convert to dict and save
        config_dict = config.to_dict()

        # Use tomli_w if available (supports writing), otherwise fallback
        if tomli_w is not None:
            with open(config_path, "wb") as f:
                tomli_w.dump(config_dict, f)
        else:
            # Fallback: write manually formatted TOML
            # Escape special characters for TOML string values
            def escape_toml_string(value: str) -> str:
                """Escape special characters in TOML string values."""
                # Replace backslashes first
                value = value.replace("\\", "\\\\")
                # Replace quotes
                value = value.replace('"', '\\"')
                # Replace newlines
                value = value.replace("\n", "\\n")
                # Replace carriage returns
                value = value.replace("\r", "\\r")
                # Replace tabs
                value = value.replace("\t", "\\t")
                return value

            with open(config_path, "w") as f:
                f.write("# mt5linux configuration file\n")
                f.write("# Generated automatically by mt5linux setup\n\n")
                f.write("[wine]\n")
                if config.wine.prefix_path:
                    escaped_path = escape_toml_string(config.wine.prefix_path)
                    f.write(f'prefix_path = "{escaped_path}"\n')
                f.write("\n[server]\n")
                escaped_host = escape_toml_string(config.server.host)
                f.write(f'host = "{escaped_host}"\n')
                f.write(f"port = {config.server.port}\n")
                f.write("\n[monitoring]\n")
                f.write(
                    f"heartbeat_interval = {config.monitoring.heartbeat_interval}\n"
                )
                f.write(
                    f"heartbeat_failure_threshold = {config.monitoring.heartbeat_failure_threshold}\n"
                )
                f.write("\n[daily_reports]\n")
                f.write(
                    f"enabled = {'true' if config.daily_reports.enabled else 'false'}\n"
                )
                # Format times as TOML array
                times_str = ", ".join(f'"{t}"' for t in config.daily_reports.times)
                f.write(f"times = [{times_str}]\n")
                f.write(f'timezone = "{config.daily_reports.timezone}"\n')
                f.write("\n[latency]\n")
                f.write(f"enabled = {'true' if config.latency.enabled else 'false'}\n")
                f.write(f"threshold_ms = {config.latency.threshold_ms}\n")
                f.write(
                    f"warning_delivery_secs = {config.latency.warning_delivery_secs}\n"
                )
                f.write("\n[telegram]\n")
                f.write(f"enabled = {'true' if config.telegram.enabled else 'false'}\n")
                escaped_chat_id = escape_toml_string(config.telegram.chat_id)
                f.write(f'chat_id = "{escaped_chat_id}"\n')
                f.write(f"retry_count = {config.telegram.retry_count}\n")
                f.write(f"retry_delay_secs = {config.telegram.retry_delay_secs}\n")
                f.write(
                    f"delivery_timeout_secs = {config.telegram.delivery_timeout_secs}\n"
                )
                f.write("\n[notification_preferences]\n")
                np = config.notification_preferences
                f.write(
                    f"failure_notifications = {'true' if np.failure_notifications else 'false'}\n"
                )
                f.write(
                    f"high_latency_notifications = {'true' if np.high_latency_notifications else 'false'}\n"
                )
                f.write(
                    f"trade_failure_notifications = {'true' if np.trade_failure_notifications else 'false'}\n"
                )
                f.write(
                    f"drawdown_notifications = {'true' if np.drawdown_notifications else 'false'}\n"
                )
                f.write(
                    f"daily_report_notifications = {'true' if np.daily_report_notifications else 'false'}\n"
                )
                f.write(
                    f"quiet_hours_enabled = {'true' if np.quiet_hours_enabled else 'false'}\n"
                )
                f.write(f'quiet_hours_start = "{np.quiet_hours_start}"\n')
                f.write(f'quiet_hours_end = "{np.quiet_hours_end}"\n')
                f.write("\n[notification_channels]\n")
                nc = config.notification_channels
                # Format enabled_channels as TOML array
                channels_str = ", ".join(f'"{c}"' for c in nc.enabled_channels)
                f.write(f"enabled_channels = [{channels_str}]\n")
                f.write(
                    f"console_enabled = {'true' if nc.console_enabled else 'false'}\n"
                )
                f.write(f'console_log_level = "{nc.console_log_level}"\n')
                f.write("\n[analytics]\n")
                an = config.analytics
                f.write(f"enabled = {'true' if an.enabled else 'false'}\n")
                f.write(f"history_window_hours = {an.history_window_hours}\n")
                f.write(
                    f"include_in_daily_reports = {'true' if an.include_in_daily_reports else 'false'}\n"
                )

        logger.info(f"Saved configuration to: {config_path}")
        return True
    except OSError as e:
        logger.error(f"Failed to save configuration to {config_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving configuration: {e}", exc_info=True)
        return False


def get_config() -> Config:
    """
    Get current configuration instance (singleton).

    Returns:
        Current Config instance (loads if not already loaded)
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = load_config()

    return _config_instance


def reload_config() -> Config:
    """
    Reload configuration from file (clears cache).

    Returns:
        Reloaded Config instance
    """
    global _config_instance
    _config_instance = None
    return load_config()


def update_config(key: str, value: str) -> bool:
    """
    Update a configuration value.

    Args:
        key: Configuration key in format "section.key" (e.g., "wine.prefix_path")
        value: New value (will be converted to appropriate type)

    Returns:
        True if update successful, False otherwise
    """
    config = get_config()

    try:
        # Parse key (e.g., "wine.prefix_path" -> ["wine", "prefix_path"])
        parts = key.split(".")
        if len(parts) != 2:
            logger.error(
                f"Invalid configuration key format: {key} (expected 'section.key')"
            )
            return False

        section, field_name = parts

        # Update wine section
        if section == "wine":
            if field_name == "prefix_path":
                # Validate path if provided
                if value:
                    path = Path(value)
                    if not path.exists():
                        logger.warning(f"Wine prefix path does not exist: {value}")
                        # Still allow setting it (user might create it later)
                    else:
                        # Validate Wine prefix structure (should have drive_c subdirectory)
                        drive_c_path = path / "drive_c"
                        if not drive_c_path.is_dir():
                            logger.warning(
                                f"Path does not appear to be a valid Wine prefix (missing drive_c subdirectory): {value}"
                            )
                    config.wine.prefix_path = value
                else:
                    config.wine.prefix_path = None
            else:
                logger.error(f"Unknown wine configuration field: {field_name}")
                return False

        # Update server section
        elif section == "server":
            if field_name == "host":
                config.server.host = value
            elif field_name == "port":
                try:
                    port = int(value)
                    if not (1 <= port <= 65535):
                        logger.error(
                            f"Invalid port value: {port} (must be between 1 and 65535)"
                        )
                        return False
                    config.server.port = port
                except ValueError:
                    logger.error(f"Invalid port value: {value} (must be integer)")
                    return False
            else:
                logger.error(f"Unknown server configuration field: {field_name}")
                return False

        else:
            logger.error(f"Unknown configuration section: {section}")
            return False

        # Save updated configuration
        return save_config(config)

    except Exception as e:
        logger.error(f"Error updating configuration: {e}", exc_info=True)
        return False


def extract_wine_prefix_from_detection(
    detection_result: "DetectionResult",
) -> Optional[str]:
    """
    Extract Wine prefix location from detection results.

    Args:
        detection_result: DetectionResult from environment detection.
            Must have mt5.path set to extract prefix from MT5 installation path.

    Returns:
        Wine prefix path if found, None otherwise.
        Returns the Wine prefix directory (e.g., ~/.wine) containing drive_c subdirectory.
    """
    # Try to extract from MT5 path
    if detection_result.mt5.found and detection_result.mt5.path:
        mt5_path = detection_result.mt5.path
        # Wine prefix is the directory CONTAINING drive_c
        # e.g., /home/user/.mt5/drive_c/Program Files/MetaTrader 5/terminal64.exe
        #       → Wine prefix is /home/user/.mt5
        if "drive_c" in mt5_path:
            # Find the position of drive_c and get the parent
            drive_c_idx = mt5_path.find("/drive_c/")
            if drive_c_idx != -1:
                prefix_candidate = mt5_path[:drive_c_idx]
                if os.path.isdir(prefix_candidate):
                    return prefix_candidate

    # Fallback to common prefixes
    common_prefixes = [
        os.path.join(os.getcwd(), ".mt5"),  # Default mt5linux prefix
        os.path.expanduser("~/.wine"),
        os.path.join(os.getcwd(), ".wine"),
    ]
    for prefix in common_prefixes:
        if os.path.isdir(prefix):
            return prefix

    return None
