"""CLI entry point for mt5linux using Typer framework."""

from typer import Typer, Option, echo
from typing import Literal

app: Typer = Typer(
    name="mt5linux",
    help="MetaTrader5 for Linux users - Automated setup and management",
)


@app.command()
def setup(
    mode: Literal["local", "remote"] = Option(
        "local",
        "--mode",
        "-m",
        help="Setup mode: 'local' for local desktop or 'remote' for remote server",
    ),
) -> None:
    """
    Automated setup command for mt5linux.

    Initiates the automated setup process with environment detection,
    dependency installation, and configuration.

    Args:
        mode: Setup mode - 'local' for local desktop or 'remote' for remote server
    """
    try:
        echo("Starting setup process...")
        echo(f"Setup mode: {mode}")
        # TODO (Story 1.2): Environment detection will be implemented in Story 1.2
        # TODO (Story 1.2): Call environment detection function here
        echo("Setup process initiated. Environment detection will begin next.")
    except Exception as e:
        echo(f"Error during setup: {e}")
        raise


def main() -> None:
    """
    Entry point for CLI application.
    
    This function is called when the CLI is invoked directly via:
    - `python -m mt5linux.cli` 
    - Or when the entry point `mt5linux` is called after package installation.
    
    It delegates to the Typer app instance which handles command parsing and execution.
    """
    app()


if __name__ == "__main__":
    main()
