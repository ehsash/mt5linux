#!/usr/bin/env python
"""
Generate type stubs for mt5linux from running MetaTrader5 instance.

This script connects to the MT5 terminal via rpyc and introspects the actual
types returned by the official MetaTrader5 package, generating accurate .pyi
stub files.

Usage:
    hatch run python scripts/generate_stubs.py          # Generate stubs
    hatch run python scripts/generate_stubs.py --check  # Validate existing stubs

Requirements:
    - MT5 terminal running in Wine
    - rpyc server running (python -m rpyc.classic --host 0.0.0.0)
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

import rpyc  # type: ignore[import-untyped]


class RpycConnection(Protocol):
    """Protocol for rpyc classic connection interface."""

    def eval(self, expr: str) -> Any: ...  # noqa: A003
    def execute(self, code: str) -> None: ...
    def close(self) -> None: ...


STUB_HEADER = '''\
"""
Type stubs for mt5linux - mirrors official MetaTrader5 API.

Auto-generated from MetaTrader5 v{version} runtime introspection.
DO NOT EDIT MANUALLY - regenerate with: hatch run python scripts/generate_stubs.py
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, NamedTuple, TypedDict

from numpy.typing import NDArray

'''

# Map Python type names to stub type annotations
TYPE_MAP = {
    "int": "int",
    "float": "float",
    "str": "str",
    "bool": "bool",
    "NoneType": "None",
}


@dataclass
class NamedTupleInfo:
    """Information about a NamedTuple type extracted from runtime."""

    name: str
    fields: list[tuple[str, str]]


def get_namedtuple_fields(conn: RpycConnection, var_name: str) -> list[tuple[str, str]] | None:
    """Extract field names and types from a NamedTuple instance via rpyc."""
    is_none = conn.eval(f"{var_name} is None")  # noqa: S307 - rpyc remote eval
    if is_none:
        return None

    # Get fields, excluding internal attributes
    conn.execute(
        f"_fields = ["
        f"(n, type(getattr({var_name}, n)).__name__) "
        f"for n in dir({var_name}) "
        f"if not n.startswith('_') and not n.startswith('n_') "
        f"and not callable(getattr({var_name}, n))"
        f"]"
    )
    return conn.eval("_fields")  # noqa: S307 - rpyc remote eval


def extract_namedtuple_type(
    conn: RpycConnection, type_name: str, expression: str
) -> NamedTupleInfo | None:
    """Extract a NamedTuple type definition from a runtime expression."""
    conn.execute(f"_obj = {expression}")
    fields = get_namedtuple_fields(conn, "_obj")
    if fields is None:
        return None
    return NamedTupleInfo(name=type_name, fields=fields)


def generate_namedtuple_stub(info: NamedTupleInfo) -> str:
    """Generate stub code for a NamedTuple class."""
    lines = [f"class {info.name}(NamedTuple):"]
    for field_name, field_type in info.fields:
        py_type = TYPE_MAP.get(field_type, "Any")
        lines.append(f"    {field_name}: {py_type}")
    lines.append("")
    return "\n".join(lines)


def get_function_signatures(conn: RpycConnection) -> list[tuple[str, str]]:
    """Extract function signatures from MetaTrader5 module docstrings."""
    conn.execute(
        "_funcs = ["
        "(n, getattr(mt5, n).__doc__.split('\\n')[0] if getattr(mt5, n).__doc__ else n + '()') "
        "for n in dir(mt5) "
        "if not n.startswith('_') and callable(getattr(mt5, n)) "
        "and type(getattr(mt5, n)).__name__ == 'builtin_function_or_method'"
        "]"
    )
    return conn.eval("_funcs")  # noqa: S307 - rpyc remote eval


def generate_constants_stub(conn: RpycConnection) -> str:
    """Generate stub code for all module constants."""
    conn.execute(
        "_consts = ["
        "(n, getattr(mt5, n)) "
        "for n in dir(mt5) "
        "if not n.startswith('_') and isinstance(getattr(mt5, n), int)"
        "]"
    )
    constants = conn.eval("_consts")  # noqa: S307 - rpyc remote eval

    lines = ["# === CONSTANTS ==="]
    for name, value in sorted(constants):
        lines.append(f"{name}: Literal[{value}] = {value}")
    lines.append("")
    return "\n".join(lines)


def generate_class_stub() -> str:
    """Generate the MetaTrader5 class stub with all methods."""
    # Method signatures with full typing
    method_stubs = {
        "initialize": (
            "def initialize(\n"
            "        self,\n"
            "        path: str | None = None,\n"
            "        *,\n"
            "        login: int | None = None,\n"
            "        password: str | None = None,\n"
            "        server: str | None = None,\n"
            "        timeout: int | None = None,\n"
            "        portable: bool = False,\n"
            "    ) -> bool: ..."
        ),
        "login": (
            "def login(\n"
            "        self,\n"
            "        login: int,\n"
            "        *,\n"
            "        password: str | None = None,\n"
            "        server: str | None = None,\n"
            "        timeout: int | None = None,\n"
            "    ) -> bool: ..."
        ),
        "shutdown": "def shutdown(self) -> None: ...",
        "version": "def version(self) -> tuple[int, int, str] | None: ...",
        "last_error": "def last_error(self) -> tuple[int, str]: ...",
        "account_info": "def account_info(self) -> AccountInfo | None: ...",
        "terminal_info": "def terminal_info(self) -> TerminalInfo | None: ...",
        "symbols_total": "def symbols_total(self) -> int: ...",
        "symbols_get": (
            "def symbols_get(self, *, group: str | None = None) -> tuple[SymbolInfo, ...] | None: ..."
        ),
        "symbol_info": "def symbol_info(self, symbol: str) -> SymbolInfo | None: ...",
        "symbol_info_tick": "def symbol_info_tick(self, symbol: str) -> Tick | None: ...",
        "symbol_select": "def symbol_select(self, symbol: str, enable: bool = True) -> bool: ...",
        "market_book_add": "def market_book_add(self, symbol: str) -> bool: ...",
        "market_book_get": "def market_book_get(self, symbol: str) -> tuple[BookInfo, ...] | None: ...",
        "market_book_release": "def market_book_release(self, symbol: str) -> bool: ...",
        "copy_rates_from": (
            "def copy_rates_from(\n"
            "        self, symbol: str, timeframe: int, date_from: datetime | int, count: int\n"
            "    ) -> NDArray | None: ..."
        ),
        "copy_rates_from_pos": (
            "def copy_rates_from_pos(\n"
            "        self, symbol: str, timeframe: int, start_pos: int, count: int\n"
            "    ) -> NDArray | None: ..."
        ),
        "copy_rates_range": (
            "def copy_rates_range(\n"
            "        self, symbol: str, timeframe: int, date_from: datetime | int, date_to: datetime | int\n"
            "    ) -> NDArray | None: ..."
        ),
        "copy_ticks_from": (
            "def copy_ticks_from(\n"
            "        self, symbol: str, date_from: datetime | int, count: int, flags: int\n"
            "    ) -> NDArray | None: ..."
        ),
        "copy_ticks_range": (
            "def copy_ticks_range(\n"
            "        self, symbol: str, date_from: datetime | int, date_to: datetime | int, flags: int\n"
            "    ) -> NDArray | None: ..."
        ),
        "orders_total": "def orders_total(self) -> int: ...",
        "orders_get": (
            "def orders_get(\n"
            "        self, *, symbol: str | None = None, ticket: int | None = None, group: str | None = None\n"
            "    ) -> tuple[TradeOrder, ...] | None: ..."
        ),
        "order_calc_margin": (
            "def order_calc_margin(\n"
            "        self, action: int, symbol: str, volume: float, price: float\n"
            "    ) -> float | None: ..."
        ),
        "order_calc_profit": (
            "def order_calc_profit(\n"
            "        self, action: int, symbol: str, volume: float, price_open: float, price_close: float\n"
            "    ) -> float | None: ..."
        ),
        "order_check": "def order_check(self, request: TradeRequest) -> TradeCheckResult: ...",
        "order_send": "def order_send(self, request: TradeRequest) -> TradeResult: ...",
        "positions_total": "def positions_total(self) -> int: ...",
        "positions_get": (
            "def positions_get(\n"
            "        self, *, symbol: str | None = None, ticket: int | None = None, group: str | None = None\n"
            "    ) -> tuple[TradePosition, ...] | None: ..."
        ),
        "history_orders_total": (
            "def history_orders_total(self, date_from: datetime | int, date_to: datetime | int) -> int: ..."
        ),
        "history_orders_get": (
            "def history_orders_get(\n"
            "        self,\n"
            "        date_from: datetime | int | None = None,\n"
            "        date_to: datetime | int | None = None,\n"
            "        *,\n"
            "        group: str | None = None,\n"
            "        ticket: int | None = None,\n"
            "        position: int | None = None,\n"
            "    ) -> tuple[TradeOrder, ...] | None: ..."
        ),
        "history_deals_total": (
            "def history_deals_total(self, date_from: datetime | int, date_to: datetime | int) -> int: ..."
        ),
        "history_deals_get": (
            "def history_deals_get(\n"
            "        self,\n"
            "        date_from: datetime | int | None = None,\n"
            "        date_to: datetime | int | None = None,\n"
            "        *,\n"
            "        group: str | None = None,\n"
            "        ticket: int | None = None,\n"
            "        position: int | None = None,\n"
            "    ) -> tuple[TradeDeal, ...] | None: ..."
        ),
    }

    lines = [
        "class MetaTrader5:",
        '    """MetaTrader5 API wrapper for Linux via rpyc."""',
        "",
        "    def __init__(self, host: str = 'localhost', port: int = 18812) -> None: ...",
        "",
    ]

    for stub in method_stubs.values():
        # Indent the stub properly
        indented = "\n".join("    " + line if line else "" for line in stub.split("\n"))
        lines.append(indented)
        lines.append("")

    # Add eval and execute methods
    lines.append("    def eval(self, command: str) -> object: ...")
    lines.append("    def execute(self, command: str) -> None: ...")
    lines.append("")

    return "\n".join(lines)


def generate_trade_request_stub() -> str:
    """Generate the TradeRequest TypedDict stub."""
    return '''
class TradeRequest(TypedDict, total=False):
    """Trade request structure for order_send() and order_check()."""

    action: int
    magic: int
    order: int
    symbol: str
    volume: float
    price: float
    stoplimit: float
    sl: float
    tp: float
    deviation: int
    type: int
    type_filling: int
    type_time: int
    expiration: int
    comment: str
    position: int
    position_by: int

'''


def generate_stubs(conn: RpycConnection) -> str:
    """Generate complete stub file content."""
    conn.execute("import MetaTrader5 as mt5")
    conn.execute("mt5.initialize()")

    version = conn.eval("mt5.__version__")  # noqa: S307 - rpyc remote eval

    # Collect all NamedTuple types
    namedtuple_expressions = [
        ("AccountInfo", "mt5.account_info()"),
        ("TerminalInfo", "mt5.terminal_info()"),
    ]

    # For types that require specific setup, we'll define them manually
    # based on the official documentation since they may not be available
    # without an active trading session

    namedtuples: list[NamedTupleInfo] = []
    for type_name, expr in namedtuple_expressions:
        info = extract_namedtuple_type(conn, type_name, expr)
        if info:
            namedtuples.append(info)

    # Build the stub file
    content = STUB_HEADER.format(version=version)

    # Add NamedTuple definitions
    content += "# === NAMED TUPLE TYPES (auto-generated from runtime) ===\n\n"
    for nt in namedtuples:
        content += generate_namedtuple_stub(nt) + "\n"

    # Add manually defined types that require trading context
    content += generate_manually_defined_types()

    # Add TradeRequest TypedDict
    content += generate_trade_request_stub()

    # Add constants
    content += generate_constants_stub(conn) + "\n"

    # Add class stub
    content += generate_class_stub()

    conn.execute("mt5.shutdown()")

    return content


def generate_manually_defined_types() -> str:
    """Generate stubs for types that require trading context to introspect."""
    return '''
# === NAMED TUPLE TYPES (from official documentation) ===
# These types require active trading/market data to introspect at runtime

class SymbolInfo(NamedTuple):
    """Symbol information returned by symbol_info()."""

    custom: bool
    chart_mode: int
    select: bool
    visible: bool
    session_deals: int
    session_buy_orders: int
    session_sell_orders: int
    volume: int
    volumehigh: int
    volumelow: int
    time: int
    digits: int
    spread: int
    spread_float: bool
    ticks_bookdepth: int
    trade_calc_mode: int
    trade_mode: int
    start_time: int
    expiration_time: int
    trade_stops_level: int
    trade_freeze_level: int
    trade_exemode: int
    swap_mode: int
    swap_rollover3days: int
    margin_hedged_use_leg: bool
    expiration_mode: int
    filling_mode: int
    order_mode: int
    order_gtc_mode: int
    option_mode: int
    option_right: int
    bid: float
    bidhigh: float
    bidlow: float
    ask: float
    askhigh: float
    asklow: float
    last: float
    lasthigh: float
    lastlow: float
    volume_real: float
    volumehigh_real: float
    volumelow_real: float
    option_strike: float
    point: float
    trade_tick_value: float
    trade_tick_value_profit: float
    trade_tick_value_loss: float
    trade_tick_size: float
    trade_contract_size: float
    trade_accrued_interest: float
    trade_face_value: float
    trade_liquidity_rate: float
    volume_min: float
    volume_max: float
    volume_step: float
    volume_limit: float
    swap_long: float
    swap_short: float
    margin_initial: float
    margin_maintenance: float
    session_volume: float
    session_turnover: float
    session_interest: float
    session_buy_orders_volume: float
    session_sell_orders_volume: float
    session_open: float
    session_close: float
    session_aw: float
    session_price_settlement: float
    session_price_limit_min: float
    session_price_limit_max: float
    margin_hedged: float
    price_change: float
    price_volatility: float
    price_theoretical: float
    price_greeks_delta: float
    price_greeks_theta: float
    price_greeks_gamma: float
    price_greeks_vega: float
    price_greeks_rho: float
    price_greeks_omega: float
    price_sensitivity: float
    basis: str
    category: str
    currency_base: str
    currency_profit: str
    currency_margin: str
    bank: str
    description: str
    exchange: str
    formula: str
    isin: str
    name: str
    page: str
    path: str


class Tick(NamedTuple):
    """Tick data returned by symbol_info_tick()."""

    time: int
    bid: float
    ask: float
    last: float
    volume: int
    time_msc: int
    flags: int
    volume_real: float


class TradeOrder(NamedTuple):
    """Order information returned by orders_get() and history_orders_get()."""

    ticket: int
    time_setup: int
    time_setup_msc: int
    time_done: int
    time_done_msc: int
    time_expiration: int
    type: int
    type_time: int
    type_filling: int
    state: int
    magic: int
    position_id: int
    position_by_id: int
    reason: int
    volume_initial: float
    volume_current: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    price_stoplimit: float
    symbol: str
    comment: str
    external_id: str


class TradePosition(NamedTuple):
    """Position information returned by positions_get()."""

    ticket: int
    time: int
    time_msc: int
    time_update: int
    time_update_msc: int
    type: int
    magic: int
    identifier: int
    reason: int
    volume: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    swap: float
    profit: float
    symbol: str
    comment: str
    external_id: str


class TradeDeal(NamedTuple):
    """Deal information returned by history_deals_get()."""

    ticket: int
    order: int
    time: int
    time_msc: int
    type: int
    entry: int
    magic: int
    position_id: int
    reason: int
    volume: float
    price: float
    commission: float
    swap: float
    profit: float
    fee: float
    symbol: str
    comment: str
    external_id: str


class BookInfo(NamedTuple):
    """Market depth entry returned by market_book_get()."""

    type: int
    price: float
    volume: int
    volume_real: float


class TradeCheckResult(NamedTuple):
    """Result of order_check()."""

    retcode: int
    balance: float
    equity: float
    profit: float
    margin: float
    margin_free: float
    margin_level: float
    comment: str
    request: TradeRequest


class TradeResult(NamedTuple):
    """Result of order_send()."""

    retcode: int
    deal: int
    order: int
    volume: float
    price: float
    bid: float
    ask: float
    comment: str
    request_id: int
    request: TradeRequest

'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate mt5linux type stubs")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if existing stubs match generated (for CI)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="rpyc server host (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=18812,
        help="rpyc server port (default: 18812)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("mt5linux/__init__.pyi"),
        help="Output path for stub file",
    )
    args = parser.parse_args()

    try:
        conn = cast(RpycConnection, rpyc.classic.connect(args.host, args.port))  # type: ignore[no-untyped-call]
    except ConnectionRefusedError:
        print(
            "Error: Cannot connect to rpyc server. Ensure MT5 is running with:\n"
            "  wine python -m rpyc.classic --host 0.0.0.0 --port 18812",
            file=sys.stderr,
        )
        return 1

    try:
        stub_content = generate_stubs(conn)
    finally:
        conn.close()

    if args.check:
        if not args.output.exists():
            print(f"Error: {args.output} does not exist", file=sys.stderr)
            return 1

        existing = args.output.read_text()
        if existing != stub_content:
            print(
                f"Error: {args.output} is out of sync with MetaTrader5 runtime.\n"
                f"Run 'hatch run python scripts/generate_stubs.py' to update.",
                file=sys.stderr,
            )
            return 1

        print(f"OK: {args.output} matches runtime")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(stub_content)
    print(f"Generated {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
