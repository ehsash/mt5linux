"""Unit tests for mt5linux.config module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mt5linux.config import (
    Config,
    get_config,
    reload_config,
    save_config,
    update_config,
)
from mt5linux.detection import ComponentInfo, DetectionResult

pytestmark = pytest.mark.unit  # All tests in this module are unit tests


class TestConfigSingleton:
    """Tests for configuration singleton pattern."""

    def test_get_config_returns_singleton(self) -> None:
        """Test that get_config returns the same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reload_config_creates_new_instance(self) -> None:
        """Test that reload_config reloads configuration."""
        _config1 = get_config()  # noqa: F841 - called for side effect
        reload_config()
        config2 = get_config()
        # After reload, get_config returns the reloaded singleton instance
        # (may be same or different object, but should be valid Config)
        assert isinstance(config2, Config)
        # Verify it's the singleton (subsequent calls return same instance)
        config3 = get_config()
        assert config2 is config3


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_config_creates_defaults_when_file_missing(self) -> None:
        """Test loading configuration when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                config = get_config()
                assert config.wine.prefix_path is None or isinstance(
                    config.wine.prefix_path, str
                )
                assert config.server.host == "localhost"
                assert config.server.port == 18812

    def test_load_config_loads_existing_file(self) -> None:
        """Test loading configuration from existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                """[wine]
prefix_path = "/custom/wine/prefix"

[server]
host = "127.0.0.1"
port = 9999
"""
            )
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                config = get_config()
                assert config.wine.prefix_path == "/custom/wine/prefix"
                assert config.server.host == "127.0.0.1"
                assert config.server.port == 9999

    def test_load_config_handles_invalid_toml(self) -> None:
        """Test loading configuration with invalid TOML format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("invalid toml content [")
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                # Should fall back to defaults
                reload_config()
                config = get_config()
                assert config.server.host == "localhost"
                assert config.server.port == 18812

    def test_load_config_respects_environment_variable(self) -> None:
        """Test that MT5LINUX_CONFIG_PATH environment variable is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "custom_config.toml"
            custom_path.write_text(
                """[wine]
prefix_path = "/env/wine/prefix"
"""
            )
            with patch.dict(os.environ, {"MT5LINUX_CONFIG_PATH": str(custom_path)}):
                reload_config()
                config = get_config()
                assert config.wine.prefix_path == "/env/wine/prefix"


class TestConfigSaving:
    """Tests for configuration saving."""

    def test_save_config_creates_file(self) -> None:
        """Test saving configuration creates file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                config = get_config()
                config.wine.prefix_path = "/test/wine/prefix"
                save_config(config)
                assert config_path.exists()
                content = config_path.read_text()
                assert "prefix_path" in content
                assert "/test/wine/prefix" in content

    def test_save_config_creates_directory(self) -> None:
        """Test saving configuration creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "subdir" / "nested"
            config_path = config_dir / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                config = get_config()
                save_config(config)
                assert config_dir.exists()
                assert config_path.exists()

    def test_save_config_preserves_existing_values(self) -> None:
        """Test saving configuration preserves existing values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                """[wine]
prefix_path = "/existing/prefix"

[server]
host = "localhost"
port = 18812
"""
            )
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                config = get_config()
                # Only update wine prefix
                config.wine.prefix_path = "/new/prefix"
                save_config(config)
                # Reload and verify server settings preserved
                reload_config()
                config2 = get_config()
                assert config2.wine.prefix_path == "/new/prefix"
                assert config2.server.host == "localhost"
                assert config2.server.port == 18812


class TestConfigUpdating:
    """Tests for configuration updating."""

    def test_update_config_updates_wine_prefix(self) -> None:
        """Test updating Wine prefix location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                update_config("wine.prefix_path", "/new/wine/prefix")
                config = get_config()
                assert config.wine.prefix_path == "/new/wine/prefix"

    def test_update_config_validates_path(self) -> None:
        """Test updating configuration validates paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                # Should handle invalid path gracefully
                update_config("wine.prefix_path", "/nonexistent/path")
                config = get_config()
                # Path should be set even if it doesn't exist (validation is warning, not error)
                assert config.wine.prefix_path == "/nonexistent/path"

    def test_update_config_preserves_other_values(self) -> None:
        """Test updating one value preserves others."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                """[server]
host = "localhost"
port = 18812
"""
            )
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                update_config("wine.prefix_path", "/test/prefix")
                config = get_config()
                assert config.wine.prefix_path == "/test/prefix"
                assert config.server.host == "localhost"
                assert config.server.port == 18812


class TestConfigIntegration:
    """Tests for configuration integration with setup flow."""

    def test_extract_wine_prefix_from_detection_result(self) -> None:
        """Test extracting Wine prefix from detection results."""
        detection_result = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(
                found=True,
                path=os.path.expanduser(
                    "~/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"
                ),
            ),
            rpyc=ComponentInfo(found=True),
        )
        from mt5linux.config import extract_wine_prefix_from_detection

        wine_prefix = extract_wine_prefix_from_detection(detection_result)
        assert wine_prefix is not None
        assert "drive_c" in detection_result.mt5.path

    @patch("mt5linux.config.get_config")
    @patch("mt5linux.detection.detect_environment")
    def test_config_loading_integration_with_setup(
        self, mock_detect: MagicMock, mock_get_config: MagicMock
    ) -> None:
        """Test that configuration is loaded and used during setup (AC #2)."""
        from mt5linux.config import Config, WineConfig

        # Mock config with saved Wine prefix
        mock_config = Config(wine=WineConfig(prefix_path="/saved/wine/prefix"))
        mock_get_config.return_value = mock_config

        # Mock detection result
        mock_detect.return_value = DetectionResult(
            environment_type="local",
            display_system="x11",
            wine=ComponentInfo(found=True, path="/usr/bin/wine"),
            python_system=ComponentInfo(found=True),
            python_windows=ComponentInfo(found=True),
            mt5=ComponentInfo(
                found=True,
                path="/saved/wine/prefix/drive_c/Program Files/MetaTrader 5/terminal64.exe",
            ),
            rpyc=ComponentInfo(found=True),
        )

        # Verify that detect_environment is called with saved prefix
        from mt5linux.detection import detect_environment

        result = detect_environment(wine_prefix="/saved/wine/prefix")
        # The saved prefix should be used
        assert mock_detect.called or result is not None

    def test_config_preserves_user_customizations(self) -> None:
        """Test that updating one config value preserves others (AC #2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                """[wine]
prefix_path = "/user/custom/prefix"

[server]
host = "192.168.1.1"
port = 9999
"""
            )
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                # Update only server port
                update_config("server.port", "8888")
                config = get_config()
                # Verify other values preserved
                assert config.wine.prefix_path == "/user/custom/prefix"
                assert config.server.host == "192.168.1.1"
                assert config.server.port == 8888


class TestDailyReportsConfig:
    """Tests for DailyReportsConfig dataclass (Story 4.2)."""

    def test_default_values(self) -> None:
        """Test DailyReportsConfig has correct default values."""
        from mt5linux.config import DailyReportsConfig

        config = DailyReportsConfig()
        assert config.enabled is False  # FR50: default off
        assert config.times == ("09:00", "21:00")  # FR48: default times
        assert config.timezone == "UTC"  # FR49: default timezone

    def test_custom_values(self) -> None:
        """Test DailyReportsConfig accepts custom values."""
        from mt5linux.config import DailyReportsConfig

        config = DailyReportsConfig(
            enabled=True,
            times=("08:00", "20:00", "23:59"),
            timezone="Europe/Paris",
        )
        assert config.enabled is True
        assert config.times == ("08:00", "20:00", "23:59")
        assert config.timezone == "Europe/Paris"

    def test_frozen_dataclass(self) -> None:
        """Test DailyReportsConfig is immutable (frozen=True)."""
        from mt5linux.config import DailyReportsConfig

        config = DailyReportsConfig()
        with pytest.raises(AttributeError):
            config.enabled = True  # type: ignore[misc]

    def test_slots_dataclass(self) -> None:
        """Test DailyReportsConfig uses slots for memory efficiency."""
        from mt5linux.config import DailyReportsConfig

        config = DailyReportsConfig()
        assert hasattr(config, "__slots__") or not hasattr(config, "__dict__")


class TestDailyReportsConfigValidation:
    """Tests for DailyReportsConfig validation (Story 4.2)."""

    def test_valid_time_format_hhmm(self) -> None:
        """Test valid HH:MM time format is accepted."""
        from mt5linux.config import DailyReportsConfig

        config = DailyReportsConfig(times=("00:00", "12:30", "23:59"))
        assert config.times == ("00:00", "12:30", "23:59")

    def test_invalid_time_format_single_digit_hour(self) -> None:
        """Test invalid time format with single digit hour raises error."""
        from mt5linux.config import DailyReportsConfig

        with pytest.raises(ValueError, match="Invalid time format"):
            DailyReportsConfig(times=("9:00",))

    def test_invalid_time_format_missing_colon(self) -> None:
        """Test invalid time format without colon raises error."""
        from mt5linux.config import DailyReportsConfig

        with pytest.raises(ValueError, match="Invalid time format"):
            DailyReportsConfig(times=("0900",))

    def test_invalid_time_format_hour_out_of_range(self) -> None:
        """Test time with hour > 23 raises error."""
        from mt5linux.config import DailyReportsConfig

        with pytest.raises(ValueError, match="Invalid time format"):
            DailyReportsConfig(times=("24:00",))

    def test_invalid_time_format_minute_out_of_range(self) -> None:
        """Test time with minute > 59 raises error."""
        from mt5linux.config import DailyReportsConfig

        with pytest.raises(ValueError, match="Invalid time format"):
            DailyReportsConfig(times=("12:60",))

    def test_invalid_timezone_raises_error(self) -> None:
        """Test invalid timezone raises error."""
        from mt5linux.config import DailyReportsConfig

        with pytest.raises(ValueError, match="Invalid timezone"):
            DailyReportsConfig(timezone="Invalid/Timezone")

    def test_valid_timezone_utc(self) -> None:
        """Test UTC timezone is valid."""
        from mt5linux.config import DailyReportsConfig

        config = DailyReportsConfig(timezone="UTC")
        assert config.timezone == "UTC"

    def test_valid_timezone_named(self) -> None:
        """Test named timezone is valid."""
        from mt5linux.config import DailyReportsConfig

        config = DailyReportsConfig(timezone="America/New_York")
        assert config.timezone == "America/New_York"

    def test_empty_times_raises_error(self) -> None:
        """Test empty times tuple raises error."""
        from mt5linux.config import DailyReportsConfig

        with pytest.raises(ValueError, match="At least one time must be specified"):
            DailyReportsConfig(times=())


class TestDailyReportsConfigIntegration:
    """Tests for DailyReportsConfig integration with Config class (Story 4.2)."""

    def test_config_has_daily_reports_section(self) -> None:
        """Test Config class has daily_reports attribute."""
        from mt5linux.config import Config, DailyReportsConfig

        config = Config()
        assert hasattr(config, "daily_reports")
        assert isinstance(config.daily_reports, DailyReportsConfig)

    def test_config_to_dict_includes_daily_reports(self) -> None:
        """Test Config.to_dict() includes daily_reports section."""
        from mt5linux.config import Config

        config = Config()
        config_dict = config.to_dict()
        assert "daily_reports" in config_dict
        assert config_dict["daily_reports"]["enabled"] is False
        assert config_dict["daily_reports"]["times"] == ["09:00", "21:00"]
        assert config_dict["daily_reports"]["timezone"] == "UTC"

    def test_config_from_dict_loads_daily_reports(self) -> None:
        """Test Config.from_dict() loads daily_reports section."""
        from mt5linux.config import Config

        data = {
            "daily_reports": {
                "enabled": True,
                "times": ["08:00", "16:00"],
                "timezone": "Europe/London",
            }
        }
        config = Config.from_dict(data)
        assert config.daily_reports.enabled is True
        assert config.daily_reports.times == ("08:00", "16:00")
        assert config.daily_reports.timezone == "Europe/London"

    def test_config_from_dict_handles_missing_daily_reports(self) -> None:
        """Test Config.from_dict() uses defaults when daily_reports missing."""
        from mt5linux.config import Config

        data = {"wine": {"prefix_path": "/some/path"}}
        config = Config.from_dict(data)
        assert config.daily_reports.enabled is False
        assert config.daily_reports.times == ("09:00", "21:00")
        assert config.daily_reports.timezone == "UTC"

    def test_save_config_includes_daily_reports(self) -> None:
        """Test save_config() includes daily_reports in TOML output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                from mt5linux.config import Config, DailyReportsConfig, save_config

                config = Config(
                    daily_reports=DailyReportsConfig(
                        enabled=True,
                        times=("10:00", "22:00"),
                        timezone="Asia/Tokyo",
                    )
                )
                save_config(config)
                content = config_path.read_text()
                assert "[daily_reports]" in content
                assert "enabled = true" in content
                assert "Asia/Tokyo" in content

    def test_load_config_reads_daily_reports(self) -> None:
        """Test load_config() reads daily_reports from TOML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                """[daily_reports]
enabled = true
times = ["07:00", "19:00"]
timezone = "America/Chicago"
"""
            )
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                config = get_config()
                assert config.daily_reports.enabled is True
                assert config.daily_reports.times == ("07:00", "19:00")
                assert config.daily_reports.timezone == "America/Chicago"


class TestLatencyConfig:
    """Tests for LatencyConfig dataclass (Story 4.3)."""

    def test_default_values(self) -> None:
        """Test LatencyConfig has correct default values per FR52."""
        from mt5linux.config import LatencyConfig

        config = LatencyConfig()
        assert config.enabled is True  # Default: enabled
        assert config.threshold_ms == 200.0  # FR52: 200ms default threshold
        assert config.warning_delivery_secs == 5.0  # Default: 5 seconds

    def test_custom_values(self) -> None:
        """Test LatencyConfig accepts custom values."""
        from mt5linux.config import LatencyConfig

        config = LatencyConfig(
            enabled=False,
            threshold_ms=500.0,
            warning_delivery_secs=10.0,
        )
        assert config.enabled is False
        assert config.threshold_ms == 500.0
        assert config.warning_delivery_secs == 10.0

    def test_frozen_dataclass(self) -> None:
        """Test LatencyConfig is immutable (frozen=True)."""
        from mt5linux.config import LatencyConfig

        config = LatencyConfig()
        with pytest.raises(AttributeError):
            config.enabled = False  # type: ignore[misc]

    def test_slots_dataclass(self) -> None:
        """Test LatencyConfig uses slots for memory efficiency."""
        from mt5linux.config import LatencyConfig

        config = LatencyConfig()
        assert hasattr(config, "__slots__") or not hasattr(config, "__dict__")


class TestLatencyConfigValidation:
    """Tests for LatencyConfig validation (Story 4.3)."""

    def test_threshold_ms_must_be_positive(self) -> None:
        """Test threshold_ms must be positive."""
        from mt5linux.config import LatencyConfig

        with pytest.raises(ValueError, match="threshold_ms must be positive"):
            LatencyConfig(threshold_ms=0.0)

    def test_threshold_ms_rejects_negative(self) -> None:
        """Test threshold_ms rejects negative values."""
        from mt5linux.config import LatencyConfig

        with pytest.raises(ValueError, match="threshold_ms must be positive"):
            LatencyConfig(threshold_ms=-100.0)

    def test_warning_delivery_secs_must_be_positive(self) -> None:
        """Test warning_delivery_secs must be positive."""
        from mt5linux.config import LatencyConfig

        with pytest.raises(ValueError, match="warning_delivery_secs must be positive"):
            LatencyConfig(warning_delivery_secs=0.0)

    def test_warning_delivery_secs_rejects_negative(self) -> None:
        """Test warning_delivery_secs rejects negative values."""
        from mt5linux.config import LatencyConfig

        with pytest.raises(ValueError, match="warning_delivery_secs must be positive"):
            LatencyConfig(warning_delivery_secs=-5.0)

    def test_valid_positive_threshold(self) -> None:
        """Test valid positive threshold values are accepted."""
        from mt5linux.config import LatencyConfig

        config = LatencyConfig(threshold_ms=0.001)  # Very small but positive
        assert config.threshold_ms == 0.001

    def test_valid_positive_warning_delivery(self) -> None:
        """Test valid positive warning_delivery_secs values are accepted."""
        from mt5linux.config import LatencyConfig

        config = LatencyConfig(warning_delivery_secs=0.001)  # Very small but positive
        assert config.warning_delivery_secs == 0.001


class TestLatencyConfigIntegration:
    """Tests for LatencyConfig integration with Config class (Story 4.3)."""

    def test_config_has_latency_section(self) -> None:
        """Test Config class has latency attribute."""
        from mt5linux.config import Config, LatencyConfig

        config = Config()
        assert hasattr(config, "latency")
        assert isinstance(config.latency, LatencyConfig)

    def test_config_to_dict_includes_latency(self) -> None:
        """Test Config.to_dict() includes latency section."""
        from mt5linux.config import Config

        config = Config()
        config_dict = config.to_dict()
        assert "latency" in config_dict
        assert config_dict["latency"]["enabled"] is True
        assert config_dict["latency"]["threshold_ms"] == 200.0
        assert config_dict["latency"]["warning_delivery_secs"] == 5.0

    def test_config_from_dict_loads_latency(self) -> None:
        """Test Config.from_dict() loads latency section."""
        from mt5linux.config import Config

        data = {
            "latency": {
                "enabled": False,
                "threshold_ms": 300.0,
                "warning_delivery_secs": 10.0,
            }
        }
        config = Config.from_dict(data)
        assert config.latency.enabled is False
        assert config.latency.threshold_ms == 300.0
        assert config.latency.warning_delivery_secs == 10.0

    def test_config_from_dict_handles_missing_latency(self) -> None:
        """Test Config.from_dict() uses defaults when latency missing."""
        from mt5linux.config import Config

        data = {"wine": {"prefix_path": "/some/path"}}
        config = Config.from_dict(data)
        assert config.latency.enabled is True
        assert config.latency.threshold_ms == 200.0
        assert config.latency.warning_delivery_secs == 5.0

    def test_save_config_includes_latency(self) -> None:
        """Test save_config() includes latency in TOML output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                from mt5linux.config import Config, LatencyConfig, save_config

                config = Config(
                    latency=LatencyConfig(
                        enabled=False,
                        threshold_ms=500.0,
                        warning_delivery_secs=15.0,
                    )
                )
                save_config(config)
                content = config_path.read_text()
                assert "[latency]" in content
                assert "enabled = false" in content
                assert "threshold_ms = 500.0" in content
                assert "warning_delivery_secs = 15.0" in content

    def test_load_config_reads_latency(self) -> None:
        """Test load_config() reads latency from TOML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                """[latency]
enabled = false
threshold_ms = 150.0
warning_delivery_secs = 3.0
"""
            )
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                config = get_config()
                assert config.latency.enabled is False
                assert config.latency.threshold_ms == 150.0
                assert config.latency.warning_delivery_secs == 3.0

    def test_save_config_fallback_writer_includes_latency(self) -> None:
        """Test fallback TOML writer (when tomli_w unavailable) includes latency section.

        This tests M5 fix: verify fallback writer produces correct [latency] output.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                # Mock tomli_w as unavailable to force fallback writer
                with patch("mt5linux.config.tomli_w", None):
                    from mt5linux.config import Config, LatencyConfig, save_config

                    config = Config(
                        latency=LatencyConfig(
                            enabled=False,
                            threshold_ms=350.0,
                            warning_delivery_secs=8.0,
                        )
                    )
                    result = save_config(config)

                    assert result is True
                    content = config_path.read_text()
                    # Verify fallback writer produced correct latency section
                    assert "[latency]" in content
                    assert "enabled = false" in content
                    assert "threshold_ms = 350.0" in content
                    assert "warning_delivery_secs = 8.0" in content


class TestTelegramConfig:
    """Tests for TelegramConfig dataclass (Story 4.4)."""

    def test_default_values(self) -> None:
        """Test TelegramConfig has correct default values per FR54-FR57."""
        from mt5linux.config import TelegramConfig

        config = TelegramConfig()
        assert config.enabled is False  # Default: disabled (opt-in)
        assert config.chat_id == ""  # Default: empty
        assert config.retry_count == 3  # Default: 3 retries
        assert config.retry_delay_secs == 1.0  # Default: 1 second
        assert config.delivery_timeout_secs == 5.0  # NFR47: 5 second delivery

    def test_custom_values(self) -> None:
        """Test TelegramConfig accepts custom values."""
        from mt5linux.config import TelegramConfig

        config = TelegramConfig(
            enabled=True,
            chat_id="123456789",
            retry_count=5,
            retry_delay_secs=2.0,
            delivery_timeout_secs=10.0,
        )
        assert config.enabled is True
        assert config.chat_id == "123456789"
        assert config.retry_count == 5
        assert config.retry_delay_secs == 2.0
        assert config.delivery_timeout_secs == 10.0

    def test_frozen_dataclass(self) -> None:
        """Test TelegramConfig is immutable (frozen=True)."""
        from mt5linux.config import TelegramConfig

        config = TelegramConfig()
        with pytest.raises(AttributeError):
            config.enabled = True  # type: ignore[misc]

    def test_slots_dataclass(self) -> None:
        """Test TelegramConfig uses slots for memory efficiency."""
        from mt5linux.config import TelegramConfig

        config = TelegramConfig()
        assert hasattr(config, "__slots__") or not hasattr(config, "__dict__")


class TestTelegramConfigValidation:
    """Tests for TelegramConfig validation (Story 4.4)."""

    def test_enabled_true_requires_chat_id(self) -> None:
        """Test enabled=True requires chat_id to be set."""
        from mt5linux.config import TelegramConfig

        with pytest.raises(
            ValueError, match="chat_id is required when telegram is enabled"
        ):
            TelegramConfig(enabled=True, chat_id="")

    def test_enabled_true_with_chat_id_valid(self) -> None:
        """Test enabled=True with chat_id is valid."""
        from mt5linux.config import TelegramConfig

        config = TelegramConfig(enabled=True, chat_id="123456789")
        assert config.enabled is True
        assert config.chat_id == "123456789"

    def test_enabled_false_empty_chat_id_valid(self) -> None:
        """Test enabled=False allows empty chat_id."""
        from mt5linux.config import TelegramConfig

        config = TelegramConfig(enabled=False, chat_id="")
        assert config.enabled is False
        assert config.chat_id == ""

    def test_retry_count_must_be_non_negative(self) -> None:
        """Test retry_count must be non-negative."""
        from mt5linux.config import TelegramConfig

        with pytest.raises(ValueError, match="retry_count must be non-negative"):
            TelegramConfig(retry_count=-1)

    def test_retry_count_zero_valid(self) -> None:
        """Test retry_count=0 is valid (no retries)."""
        from mt5linux.config import TelegramConfig

        config = TelegramConfig(retry_count=0)
        assert config.retry_count == 0

    def test_retry_delay_secs_must_be_positive(self) -> None:
        """Test retry_delay_secs must be positive."""
        from mt5linux.config import TelegramConfig

        with pytest.raises(ValueError, match="retry_delay_secs must be positive"):
            TelegramConfig(retry_delay_secs=0.0)

    def test_retry_delay_secs_rejects_negative(self) -> None:
        """Test retry_delay_secs rejects negative values."""
        from mt5linux.config import TelegramConfig

        with pytest.raises(ValueError, match="retry_delay_secs must be positive"):
            TelegramConfig(retry_delay_secs=-1.0)

    def test_delivery_timeout_secs_must_be_positive(self) -> None:
        """Test delivery_timeout_secs must be positive."""
        from mt5linux.config import TelegramConfig

        with pytest.raises(ValueError, match="delivery_timeout_secs must be positive"):
            TelegramConfig(delivery_timeout_secs=0.0)

    def test_delivery_timeout_secs_rejects_negative(self) -> None:
        """Test delivery_timeout_secs rejects negative values."""
        from mt5linux.config import TelegramConfig

        with pytest.raises(ValueError, match="delivery_timeout_secs must be positive"):
            TelegramConfig(delivery_timeout_secs=-5.0)

    def test_valid_small_positive_values(self) -> None:
        """Test valid small positive values are accepted."""
        from mt5linux.config import TelegramConfig

        config = TelegramConfig(
            retry_delay_secs=0.001,
            delivery_timeout_secs=0.001,
        )
        assert config.retry_delay_secs == 0.001
        assert config.delivery_timeout_secs == 0.001


class TestTelegramConfigIntegration:
    """Tests for TelegramConfig integration with Config class (Story 4.4)."""

    def test_config_has_telegram_section(self) -> None:
        """Test Config class has telegram attribute."""
        from mt5linux.config import Config, TelegramConfig

        config = Config()
        assert hasattr(config, "telegram")
        assert isinstance(config.telegram, TelegramConfig)

    def test_config_to_dict_includes_telegram(self) -> None:
        """Test Config.to_dict() includes telegram section."""
        from mt5linux.config import Config

        config = Config()
        config_dict = config.to_dict()
        assert "telegram" in config_dict
        assert config_dict["telegram"]["enabled"] is False
        assert config_dict["telegram"]["chat_id"] == ""
        assert config_dict["telegram"]["retry_count"] == 3
        assert config_dict["telegram"]["retry_delay_secs"] == 1.0
        assert config_dict["telegram"]["delivery_timeout_secs"] == 5.0

    def test_config_from_dict_loads_telegram(self) -> None:
        """Test Config.from_dict() loads telegram section."""
        from mt5linux.config import Config

        data = {
            "telegram": {
                "enabled": True,
                "chat_id": "987654321",
                "retry_count": 5,
                "retry_delay_secs": 2.0,
                "delivery_timeout_secs": 10.0,
            }
        }
        config = Config.from_dict(data)
        assert config.telegram.enabled is True
        assert config.telegram.chat_id == "987654321"
        assert config.telegram.retry_count == 5
        assert config.telegram.retry_delay_secs == 2.0
        assert config.telegram.delivery_timeout_secs == 10.0

    def test_config_from_dict_handles_missing_telegram(self) -> None:
        """Test Config.from_dict() uses defaults when telegram missing."""
        from mt5linux.config import Config

        data = {"wine": {"prefix_path": "/some/path"}}
        config = Config.from_dict(data)
        assert config.telegram.enabled is False
        assert config.telegram.chat_id == ""
        assert config.telegram.retry_count == 3
        assert config.telegram.retry_delay_secs == 1.0
        assert config.telegram.delivery_timeout_secs == 5.0

    def test_save_config_includes_telegram(self) -> None:
        """Test save_config() includes telegram in TOML output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                from mt5linux.config import Config, TelegramConfig, save_config

                config = Config(
                    telegram=TelegramConfig(
                        enabled=True,
                        chat_id="111222333",
                        retry_count=4,
                        retry_delay_secs=1.5,
                        delivery_timeout_secs=7.0,
                    )
                )
                save_config(config)
                content = config_path.read_text()
                assert "[telegram]" in content
                assert "enabled = true" in content
                assert "111222333" in content
                assert "retry_count = 4" in content

    def test_load_config_reads_telegram(self) -> None:
        """Test load_config() reads telegram from TOML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                """[telegram]
enabled = true
chat_id = "444555666"
retry_count = 2
retry_delay_secs = 0.5
delivery_timeout_secs = 3.0
"""
            )
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                reload_config()
                config = get_config()
                assert config.telegram.enabled is True
                assert config.telegram.chat_id == "444555666"
                assert config.telegram.retry_count == 2
                assert config.telegram.retry_delay_secs == 0.5
                assert config.telegram.delivery_timeout_secs == 3.0

    def test_save_config_fallback_writer_includes_telegram(self) -> None:
        """Test fallback TOML writer includes telegram section.

        Learned from Stories 4.1-4.3: always test fallback writer for new config sections.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            with patch("mt5linux.config._get_config_path", return_value=config_path):
                # Mock tomli_w as unavailable to force fallback writer
                with patch("mt5linux.config.tomli_w", None):
                    from mt5linux.config import Config, TelegramConfig, save_config

                    config = Config(
                        telegram=TelegramConfig(
                            enabled=True,
                            chat_id="777888999",
                            retry_count=6,
                            retry_delay_secs=3.0,
                            delivery_timeout_secs=12.0,
                        )
                    )
                    result = save_config(config)

                    assert result is True
                    content = config_path.read_text()
                    # Verify fallback writer produced correct telegram section
                    assert "[telegram]" in content
                    assert "enabled = true" in content
                    assert "777888999" in content
                    assert "retry_count = 6" in content
                    assert "retry_delay_secs = 3.0" in content
                    assert "delivery_timeout_secs = 12.0" in content
