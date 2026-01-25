"""Setup automation module for mt5linux."""

from mt5linux.setup.installer import (
    InstallationResult,
    install_wine,
    install_windows_python,
    install_mt5_library,
    install_rpyc,
    install_missing_components,
)

__all__ = [
    "InstallationResult",
    "install_wine",
    "install_windows_python",
    "install_mt5_library",
    "install_rpyc",
    "install_missing_components",
]
