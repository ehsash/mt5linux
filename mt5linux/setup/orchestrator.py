"""Main setup orchestrator."""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from rich.console import Console

from .checks import SetupState, check_all, find_python_in_wine
from .config import MT5Config, detect_project_root
from .registry import find_available_port, register_instance
from .rpyc_service import (create_systemd_service, restart_service,
                           start_service)
from .server import (install_thinlinc_server, install_xserver_and_desktop,
                     is_server_environment, is_thinlinc_installed,
                     is_xserver_installed, show_thinlinc_instructions)
from .wine import (create_wine_prefix, install_mt5_terminal,
                   install_packages_in_wine, install_python_in_wine,
                   install_wine_staging)

console = Console()


class Action(Enum):
    """Actions that can be performed during setup."""

    INSTALL_WINE = auto()
    CREATE_PREFIX = auto()
    INSTALL_PYTHON_WINE = auto()
    INSTALL_MT5 = auto()
    CREATE_SERVICE = auto()
    START_SERVICE = auto()
    RESTART_SERVICE = auto()


@dataclass
class SetupResult:
    """Result of setup operation."""

    success: bool
    state: SetupState
    error: Optional[str] = None
    warning: Optional[str] = None


def get_required_actions(state: SetupState, force: bool = False) -> list[Action]:
    """Determine what actions need to be performed."""
    actions = []

    if not state.wine_installed:
        actions.append(Action.INSTALL_WINE)

    if not state.wine_prefix_exists or force:
        actions.append(Action.CREATE_PREFIX)

    if not state.python_in_wine or force:
        actions.append(Action.INSTALL_PYTHON_WINE)

    if not state.mt5_installed:
        actions.append(Action.INSTALL_MT5)

    if not state.rpyc_service_exists:
        actions.append(Action.CREATE_SERVICE)
    elif not state.rpyc_service_running:
        actions.append(Action.START_SERVICE)
    elif not state.rpyc_port_responding:
        actions.append(Action.RESTART_SERVICE)

    return actions


def setup(
    project_path: Optional[Path] = None,
    port: Optional[int] = None,
    force_reinstall: bool = False,
) -> SetupResult:
    """
    Idempotent MT5 setup. Installs/fixes only what's needed.

    Args:
        project_path: Project root (default: detect from cwd)
        port: Override port (default: auto-assign)
        force_reinstall: Reinstall even if configured

    Returns:
        SetupResult with status and any errors
    """
    project_path = project_path or detect_project_root()

    console.print("[bold]MT5 Linux Setup[/bold]")
    console.print(f"Project: {project_path}\n")

    # Step 0: Handle server environment (ThinLinc installation if needed)
    if is_server_environment():
        console.print("[yellow]Server environment detected (no display)[/yellow]")

        if not is_xserver_installed():
            console.print(
                "[bold]Installing X server and desktop environment...[/bold]\n"
            )
            if not install_xserver_and_desktop():
                return SetupResult(
                    success=False,
                    error="Failed to install X server",
                    state=check_all(project_path),
                )

        if not is_thinlinc_installed():
            console.print("[bold]Installing ThinLinc server...[/bold]\n")
            if not install_thinlinc_server():
                return SetupResult(
                    success=False,
                    error="Failed to install ThinLinc",
                    state=check_all(project_path),
                )

        # X server and ThinLinc installed, but no display yet
        # User needs to connect via ThinLinc
        show_thinlinc_instructions()
        raise SetupInterrupt(
            "Please connect via ThinLinc and run setup() again to continue"
        )

    # Step 1: Check current state
    console.print("[bold]Checking installation state...[/bold]")
    state = check_all(project_path)

    _print_state(state)

    # Step 2: Determine required actions
    actions = get_required_actions(state, force_reinstall)

    if not actions:
        console.print("\n[green]✓ Everything is configured correctly[/green]")
        return SetupResult(success=True, state=state)

    console.print(
        f"\n[bold]Actions needed:[/bold] {', '.join(a.name for a in actions)}\n"
    )

    # Step 3: Warn about sudo if needed
    if Action.INSTALL_WINE in actions:
        console.print("[yellow]⚠ Wine installation requires sudo[/yellow]\n")

    # Step 4: Execute actions
    for action in actions:
        try:
            _execute_action(action, state, project_path, port)
        except SetupInterrupt as e:
            # MT5 needs manual installation - not a failure
            console.print(f"\n[yellow]{e}[/yellow]")
            return SetupResult(
                success=True, warning=str(e), state=check_all(project_path)
            )
        except Exception as e:
            console.print(f"[red]✗ {action.name} failed: {e}[/red]")
            return SetupResult(success=False, error=str(e), state=state)

    # Step 5: Verify
    console.print("\n[bold]Verifying setup...[/bold]")
    final_state = check_all(project_path)

    if final_state.rpyc_port_responding:
        console.print(
            "[green]✓ Setup complete! You can now use mt5linux.MetaTrader5()[/green]"
        )
        return SetupResult(success=True, state=final_state)
    else:
        console.print(
            "[yellow]⚠ Setup complete but RPyC not responding. "
            "Check mt5linux.doctor()[/yellow]"
        )
        return SetupResult(
            success=True, warning="RPyC not responding", state=final_state
        )


class SetupInterrupt(Exception):
    """Raised when setup needs user intervention (e.g., MT5 install)."""

    pass


def _print_state(state: SetupState) -> None:
    """Print current state."""
    checks = [
        ("Wine", state.wine_installed, state.wine_version),
        ("Wine prefix", state.wine_prefix_exists, state.wine_prefix_path),
        ("Python (Wine)", state.python_in_wine, state.python_wine_path),
        ("MT5 terminal", state.mt5_installed, state.mt5_exe_path),
        ("RPyC service", state.rpyc_service_exists, state.rpyc_service_name),
        ("RPyC running", state.rpyc_service_running, None),
        ("RPyC responding", state.rpyc_port_responding, f"port {state.rpyc_port}"),
    ]

    for name, ok, detail in checks:
        icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
        detail_str = f" ({detail})" if detail else ""
        console.print(f"  {icon} {name}{detail_str}")


def _execute_action(
    action: Action,
    state: SetupState,
    project_path: Path,
    port: Optional[int],
) -> None:
    """Execute a single setup action."""
    wine_prefix = project_path / ".mt5"

    if action == Action.INSTALL_WINE:
        console.print("[bold]Installing Wine Staging...[/bold]")
        if not install_wine_staging():
            raise RuntimeError("Wine installation failed")
        console.print("[green]✓ Wine installed[/green]")

    elif action == Action.CREATE_PREFIX:
        console.print(f"[bold]Creating Wine prefix at {wine_prefix}...[/bold]")
        if not create_wine_prefix(wine_prefix):
            raise RuntimeError("Wine prefix creation failed")
        console.print("[green]✓ Wine prefix created[/green]")

    elif action == Action.INSTALL_PYTHON_WINE:
        console.print("[bold]Installing Python in Wine...[/bold]")
        if not install_python_in_wine(wine_prefix):
            raise RuntimeError("Python installation failed")

        # Find the installed Python
        python_exe = find_python_in_wine(wine_prefix)
        if python_exe:
            install_packages_in_wine(wine_prefix, python_exe)
        console.print("[green]✓ Python + rpyc installed[/green]")

    elif action == Action.INSTALL_MT5:
        console.print("[bold]Installing MetaTrader 5...[/bold]")
        if not install_mt5_terminal(wine_prefix):
            raise SetupInterrupt(
                "MT5 installation incomplete - run setup() again after installing"
            )

    elif action == Action.CREATE_SERVICE:
        assigned_port = port or find_available_port()

        python_exe = find_python_in_wine(wine_prefix)
        if not python_exe:
            raise RuntimeError("Python not found in Wine prefix")

        console.print(f"[bold]Creating RPyC service on port {assigned_port}...[/bold]")

        # Save config
        config = MT5Config(
            wine_prefix=wine_prefix,
            rpyc_port=assigned_port,
            rpyc_host="localhost",
            venv_path=project_path / ".venv",
            project_path=project_path,
        )
        config.save(project_path / ".mt5env")

        # Create service
        if not create_systemd_service(
            project_path, assigned_port, python_exe, wine_prefix
        ):
            raise RuntimeError("Service creation failed")

        # Register
        register_instance(project_path, assigned_port)

        # Start
        if not start_service(project_path):
            raise RuntimeError("Service start failed")

        console.print(f"[green]✓ RPyC service created on port {assigned_port}[/green]")

    elif action == Action.START_SERVICE:
        console.print("[bold]Starting RPyC service...[/bold]")
        if not start_service(project_path):
            raise RuntimeError("Service start failed")
        console.print("[green]✓ RPyC service started[/green]")

    elif action == Action.RESTART_SERVICE:
        console.print("[bold]Restarting RPyC service...[/bold]")
        if not restart_service(project_path):
            raise RuntimeError("Service restart failed")
        console.print("[green]✓ RPyC service restarted[/green]")
