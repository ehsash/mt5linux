"""Configuration management module for mt5linux."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

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


@dataclass
class Config:
    """Main configuration structure."""

    wine: WineConfig = field(default_factory=WineConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create configuration from dictionary."""
        wine_data = data.get("wine", {})
        server_data = data.get("server", {})

        return cls(
            wine=WineConfig(
                prefix_path=wine_data.get("prefix_path"),
            ),
            server=ServerConfig(
                host=server_data.get("host", "localhost"),
                port=server_data.get("port", 18812),
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
        logger.warning(f"Failed to load configuration from {config_path}: {e}, using defaults")
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
            logger.error(f"Invalid configuration key format: {key} (expected 'section.key')")
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
                        logger.error(f"Invalid port value: {port} (must be between 1 and 65535)")
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


def extract_wine_prefix_from_detection(detection_result: "DetectionResult") -> Optional[str]:
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
