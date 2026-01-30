"""Shared fixtures for feature tests.

These fixtures manage MT5 connection lifecycle with auto-start capability.
Uses the working MT5 installation in .mt5/ Wine prefix.

PREREQUISITES:
    1. Run 'mt5linux setup' to install MT5 in .mt5/ Wine prefix
    2. Start MT5 terminal: mt5linux start
    3. Log into a DEMO account in MT5 (first time only)
    4. MT5 terminal must be running and connected before running tests

The tests will auto-start rpyc server and connect to running MT5 terminal.
Tests will SKIP (not fail) if MT5 is not properly configured.
"""

import os
import time
from typing import Any, Generator

import pytest

# Test configuration - symbols available in DEMO account
TEST_SYMBOLS = ("EURUSD", "EURCHF", "USTEC")
TEST_SYMBOL_FOREX = "EURUSD"
TEST_SYMBOL_INDEX = "USTEC"

# Wine prefix for MT5 installation
WINE_PREFIX = os.path.join(os.path.dirname(__file__), "..", "..", ".mt5")
MT5_TERMINAL_PATH = os.path.join(
    WINE_PREFIX, "drive_c", "Program Files", "MetaTrader 5", "terminal64.exe"
)


@pytest.fixture(scope="session")
def wine_prefix() -> str:
    """Return the Wine prefix path for MT5 installation."""
    prefix = os.path.abspath(WINE_PREFIX)
    if not os.path.exists(prefix):
        pytest.skip(f"Wine prefix not found at {prefix}. Run 'mt5linux setup' first.")
    return prefix


@pytest.fixture(scope="session")
def mt5_connection(wine_prefix: str) -> Generator[Any, None, None]:
    """Session-scoped MT5 connection with auto-start.

    This fixture:
    1. Creates MetaTrader5 instance with auto_connect=True
    2. Calls initialize() which auto-starts rpyc server and MT5
    3. Yields the connected instance
    4. Cleans up with shutdown() after all tests

    Prerequisites:
        - MT5 terminal must be installed in .mt5/ Wine prefix
        - MT5 terminal should be running and logged into a DEMO account
        - Use 'mt5linux start' to start MT5 before running tests

    Yields:
        Connected MetaTrader5 instance.

    Raises:
        pytest.skip: If connection cannot be established.
    """
    from mt5linux import MetaTrader5

    mt5 = MetaTrader5(host="localhost", port=18812, auto_connect=True)

    # Get MT5 terminal path for initialization
    terminal_path = f"{wine_prefix}/drive_c/Program Files/MetaTrader 5/terminal64.exe"

    try:
        # Initialize with path to terminal (helps MetaTrader5 library find it)
        # Timeout of 60s allows slow Wine startup
        result = mt5.initialize(path=terminal_path, timeout=60000)
        if not result:
            error = mt5.last_error()
            error_code = error[0] if error else "unknown"

            skip_msg = f"MT5 initialization failed: {error}\n\n"
            if error_code == -10003:
                skip_msg += (
                    "MT5 terminal not found or not ready.\n"
                    "To run feature tests:\n"
                    "  1. Re-run 'mt5linux setup' to configure MT5 in portable mode\n"
                    "  2. Log into a DEMO account during setup\n"
                    "  3. Re-run tests once connected\n"
                )
            elif error_code == -10005:
                skip_msg += (
                    "MT5 terminal found but IPC timed out.\n"
                    "This usually means MT5 is not logged into an account.\n\n"
                    "If credentials weren't saved (first time):\n"
                    "  1. Re-run 'mt5linux setup' to configure MT5 in portable mode\n"
                    "  2. Log into a DEMO account during setup\n"
                    "  3. Complete setup and re-run tests\n\n"
                    "If MT5 is configured but not running:\n"
                    "  1. Start MT5 manually with /portable flag\n"
                    "  2. Wait for 'Connected' status\n"
                    "  3. Re-run tests\n"
                )
            pytest.skip(skip_msg)

        # Allow MT5 to fully initialize
        time.sleep(2)

        # Verify connection
        if not mt5.is_connected:
            pytest.skip("MT5 connection not established - is MT5 logged in?")

        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            pytest.skip("Cannot get terminal info - MT5 not ready or not logged in")

        yield mt5

    finally:
        # Clean shutdown
        try:
            mt5.shutdown()
        except Exception:
            pass  # Ignore shutdown errors


@pytest.fixture(scope="function")
def mt5(mt5_connection: Any) -> Any:
    """Function-scoped alias for mt5_connection.

    Use this fixture when tests don't need to share state.
    The underlying connection is still session-scoped.
    """
    return mt5_connection


@pytest.fixture(scope="session")
def account_info(mt5_connection: Any) -> Any:
    """Session-scoped account info for assertions.

    Returns:
        Account info namedtuple from MT5.
    """
    info = mt5_connection.account_info()
    if info is None:
        pytest.skip("Cannot retrieve account info")
    return info


@pytest.fixture(scope="session")
def is_demo_account(account_info: Any) -> bool:
    """Check if connected to a DEMO account.

    Returns:
        True if DEMO account, raises skip otherwise.

    Note:
        Trading tests MUST only run on DEMO accounts.
    """
    # trade_mode: 0=demo, 1=contest, 2=real
    if hasattr(account_info, "trade_mode"):
        if account_info.trade_mode != 0:
            pytest.skip("Trading tests require a DEMO account (trade_mode=0)")
    return True


@pytest.fixture
def symbol_eurusd(mt5: Any) -> str:
    """Ensure EURUSD is selected and return symbol name."""
    symbol = TEST_SYMBOL_FOREX
    if not mt5.symbol_select(symbol, True):
        pytest.skip(f"Symbol {symbol} not available")
    return symbol


@pytest.fixture
def symbol_eurchf(mt5: Any) -> str:
    """Ensure EURCHF is selected and return symbol name."""
    symbol = "EURCHF"
    if not mt5.symbol_select(symbol, True):
        pytest.skip(f"Symbol {symbol} not available")
    return symbol


@pytest.fixture
def symbol_ustec(mt5: Any) -> str:
    """Ensure USTEC is selected and return symbol name."""
    symbol = TEST_SYMBOL_INDEX
    if not mt5.symbol_select(symbol, True):
        pytest.skip(f"Symbol {symbol} not available")
    return symbol


@pytest.fixture
def cleanup_positions(mt5: Any, is_demo_account: bool) -> Generator[None, None, None]:
    """Fixture that closes any test positions after the test.

    Use this fixture for tests that open positions.
    """
    initial_positions = mt5.positions_total() or 0

    yield

    # Cleanup: close any positions opened during test
    try:
        current_positions = mt5.positions_total() or 0
        if current_positions > initial_positions:
            # Close positions opened during test
            positions = mt5.positions_get()
            if positions:
                for pos in positions:
                    try:
                        mt5.close_position(pos.ticket)
                        time.sleep(0.5)  # Allow order to process
                    except Exception:
                        pass  # Best effort cleanup
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture(scope="session")
def heartbeat_monitor(mt5_connection: Any) -> Generator[Any, None, None]:
    """Create a HeartbeatMonitor connected to the MT5 session.

    Yields:
        Started HeartbeatMonitor instance.
    """
    from mt5linux.monitoring import HeartbeatMonitor

    # Get the connection manager from lifecycle manager
    lifecycle_mgr = mt5_connection._lifecycle_manager
    if lifecycle_mgr is None:
        pytest.skip("LifecycleManager not available")

    conn_mgr = lifecycle_mgr._connection_manager
    if conn_mgr is None:
        pytest.skip("ConnectionManager not available")

    # HeartbeatMonitor takes connection_manager and individual params
    monitor = HeartbeatMonitor(
        connection_manager=conn_mgr,
        heartbeat_interval=5.0,  # Faster for testing
        failure_threshold=10.0,
    )
    monitor.start()

    yield monitor

    monitor.stop()


@pytest.fixture(scope="session")
def latency_monitor() -> Generator[Any, None, None]:
    """Create a LatencyMonitor for testing.

    Yields:
        Started LatencyMonitor instance.

    Note:
        LatencyMonitor doesn't require connection_manager - it tracks
        latency measurements independently.
    """
    from mt5linux.config import LatencyConfig
    from mt5linux.monitoring import LatencyMonitor

    config = LatencyConfig(
        enabled=True,
        threshold_ms=200.0,
    )
    monitor = LatencyMonitor(config=config)
    monitor.start()

    yield monitor

    monitor.stop()
