"""MT5 Linux setup module."""

from .checks import SetupState, check_all
from .cleanup import cleanup_all, kill_mt5_processes, kill_rpyc_processes
from .config import MT5Config, detect_project_root, get_config
from .orchestrator import SetupResult, setup
from .registry import (
    find_available_port,
    get_instance,
    load_registry,
    register_instance,
    unregister_instance,
)

__all__ = [
    # Config
    "MT5Config",
    "detect_project_root",
    "get_config",
    # Checks
    "SetupState",
    "check_all",
    # Cleanup
    "cleanup_all",
    "kill_mt5_processes",
    "kill_rpyc_processes",
    # Registry
    "load_registry",
    "find_available_port",
    "register_instance",
    "unregister_instance",
    "get_instance",
    # Main API
    "setup",
    "SetupResult",
]
