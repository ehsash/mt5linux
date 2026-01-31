"""Process cleanup utilities for MT5 setup."""

import os
import signal
import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


def _get_process_wineprefix(pid: int) -> Optional[Path]:
    """Read WINEPREFIX from a process's environment.

    Returns the WINEPREFIX path if set, None otherwise.
    """
    try:
        environ_path = Path(f"/proc/{pid}/environ")
        if not environ_path.exists():
            return None

        # Read null-separated environment variables
        env_data = environ_path.read_bytes()
        for entry in env_data.split(b"\x00"):
            if entry.startswith(b"WINEPREFIX="):
                prefix_path = entry.split(b"=", 1)[1].decode("utf-8", errors="replace")
                return Path(prefix_path)
    except (OSError, PermissionError):
        # Process may have exited or we lack permission
        pass

    return None


def kill_mt5_processes(wine_prefix: Optional[Path] = None) -> int:
    """Kill MT5 terminal processes for a specific Wine prefix.

    Args:
        wine_prefix: If specified, only kills processes using this exact prefix.
                     If None, kills ALL MT5 processes (use with caution).

    Returns:
        Number of processes killed.
    """
    killed = 0

    try:
        # Find all terminal64.exe processes (PIDs only)
        result = subprocess.run(
            ["pgrep", "-f", "terminal64.exe"],
            capture_output=True,
            text=True,
        )

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            try:
                pid = int(line.strip())
            except ValueError:
                continue

            # If wine_prefix specified, check process's actual WINEPREFIX env var
            if wine_prefix:
                process_prefix = _get_process_wineprefix(pid)
                if process_prefix is None:
                    # Can't determine prefix, skip to be safe
                    continue

                # Resolve both paths to handle symlinks and normalize
                try:
                    target_resolved = wine_prefix.resolve()
                    process_resolved = process_prefix.resolve()
                    if process_resolved != target_resolved:
                        # Different prefix, leave it alone
                        continue
                except OSError:
                    # Path resolution failed, skip to be safe
                    continue

            try:
                os.kill(pid, signal.SIGTERM)
                killed += 1
            except ProcessLookupError:
                pass
            except PermissionError:
                console.print(
                    f"[yellow]Cannot kill PID {pid} - permission denied[/yellow]"
                )

    except Exception as e:
        console.print(f"[yellow]Error finding MT5 processes: {e}[/yellow]")

    return killed


def _get_process_cmdline(pid: int) -> Optional[str]:
    """Read full command line from a process."""
    try:
        cmdline_path = Path(f"/proc/{pid}/cmdline")
        if not cmdline_path.exists():
            return None

        # Command line is null-separated
        cmdline_data = cmdline_path.read_bytes()
        return (
            cmdline_data.replace(b"\x00", b" ")
            .decode("utf-8", errors="replace")
            .strip()
        )
    except (OSError, PermissionError):
        pass

    return None


def kill_rpyc_processes(
    port: Optional[int] = None,
    wine_prefix: Optional[Path] = None,
) -> int:
    """Kill RPyC server processes for a specific port and/or Wine prefix.

    Args:
        port: If specified, only kills RPyC servers on this exact port.
        wine_prefix: If specified, only kills RPyC servers using this Wine prefix.

    Returns:
        Number of processes killed.
    """
    killed = 0

    try:
        # Find all rpyc processes (PIDs only)
        result = subprocess.run(
            ["pgrep", "-f", "rpyc"],
            capture_output=True,
            text=True,
        )

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            try:
                pid = int(line.strip())
            except ValueError:
                continue

            cmdline = _get_process_cmdline(pid)
            if not cmdline:
                continue

            # Skip if it's not a server process
            if "rpyc_classic" not in cmdline and "rpyc.bin" not in cmdline:
                continue

            # If port specified, only kill processes for that port
            if port:
                port_str = str(port)
                if (
                    f"--port {port_str}" not in cmdline
                    and f"-p {port_str}" not in cmdline
                ):
                    continue

            # If wine_prefix specified, check process's WINEPREFIX env var
            if wine_prefix:
                process_prefix = _get_process_wineprefix(pid)
                if process_prefix is None:
                    # Can't determine prefix, skip to be safe
                    continue

                try:
                    target_resolved = wine_prefix.resolve()
                    process_resolved = process_prefix.resolve()
                    if process_resolved != target_resolved:
                        continue
                except OSError:
                    continue

            try:
                os.kill(pid, signal.SIGTERM)
                killed += 1
            except ProcessLookupError:
                pass
            except PermissionError:
                console.print(
                    f"[yellow]Cannot kill PID {pid} - permission denied[/yellow]"
                )

    except Exception as e:
        console.print(f"[yellow]Error finding RPyC processes: {e}[/yellow]")

    return killed


def kill_wine_server(wine_prefix: Optional[Path] = None) -> bool:
    """Kill the Wine server for a prefix."""
    env = os.environ.copy()
    if wine_prefix:
        env["WINEPREFIX"] = str(wine_prefix)

    try:
        subprocess.run(
            ["wineserver", "-k"],
            env=env,
            capture_output=True,
            timeout=10,
        )
        return True
    except Exception:
        return False


def cleanup_all(wine_prefix: Optional[Path] = None, port: Optional[int] = None) -> dict:
    """Kill MT5 and RPyC processes for a specific prefix/port.

    Only kills processes that match the specified prefix and/or port.
    Processes from other projects are left untouched.

    Returns dict with counts of killed processes.
    """
    console.print("[bold]Cleaning up stale processes...[/bold]")

    mt5_killed = kill_mt5_processes(wine_prefix)
    if mt5_killed:
        console.print(f"  Killed {mt5_killed} MT5 process(es)")

    # Pass both port and wine_prefix for precise targeting
    rpyc_killed = kill_rpyc_processes(port=port, wine_prefix=wine_prefix)
    if rpyc_killed:
        console.print(f"  Killed {rpyc_killed} RPyC process(es)")

    if wine_prefix:
        kill_wine_server(wine_prefix)
        console.print("  Stopped Wine server")

    if mt5_killed == 0 and rpyc_killed == 0:
        console.print("  No stale processes found")

    return {
        "mt5_killed": mt5_killed,
        "rpyc_killed": rpyc_killed,
    }
