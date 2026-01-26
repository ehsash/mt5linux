"""Setup automation module for mt5linux."""

from mt5linux.setup.installer import (
    InstallationResult,
    install_wine,
    install_windows_python,
    install_mt5_platform,
    install_mt5_library,
    install_rpyc,
    install_missing_components,
)
from mt5linux.setup.remote_installer import (
    install_thinlinc,
    install_x11_server,
    install_window_manager,
    install_remote_components,
)
from mt5linux.setup.wayland_config import (
    WaylandConfigResult,
    configure_xyphir,
    verify_xyphir,
    fallback_to_x11,
    configure_wayland_support,
)
from mt5linux.setup.pause import (
    PauseResult,
    VerificationResult,
    pause_for_mt5_configuration,
    get_mt5_gui_instructions,
    verify_mt5_configuration,
)

__all__ = [
    "InstallationResult",
    "install_wine",
    "install_windows_python",
    "install_mt5_platform",
    "install_mt5_library",
    "install_rpyc",
    "install_missing_components",
    "install_thinlinc",
    "install_x11_server",
    "install_window_manager",
    "install_remote_components",
    "WaylandConfigResult",
    "configure_xyphir",
    "verify_xyphir",
    "fallback_to_x11",
    "configure_wayland_support",
    "PauseResult",
    "VerificationResult",
    "pause_for_mt5_configuration",
    "get_mt5_gui_instructions",
    "verify_mt5_configuration",
]
