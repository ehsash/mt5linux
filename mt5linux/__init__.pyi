"""
Type stubs for mt5linux - mirrors official MetaTrader5 API.

Auto-generated from MetaTrader5 v5.0.5509 runtime introspection.
DO NOT EDIT MANUALLY - regenerate with: hatch run python scripts/generate_stubs.py
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, NamedTuple, TypedDict

from numpy.typing import NDArray

# === NAMED TUPLE TYPES (auto-generated from runtime) ===

class AccountInfo(NamedTuple):
    assets: float
    balance: float
    commission_blocked: float
    company: str
    credit: float
    currency: str
    currency_digits: int
    equity: float
    fifo_close: bool
    leverage: int
    liabilities: float
    limit_orders: int
    login: int
    margin: float
    margin_free: float
    margin_initial: float
    margin_level: float
    margin_maintenance: float
    margin_mode: int
    margin_so_call: float
    margin_so_mode: int
    margin_so_so: float
    name: str
    profit: float
    server: str
    trade_allowed: bool
    trade_expert: bool
    trade_mode: int

class TerminalInfo(NamedTuple):
    build: int
    codepage: int
    commondata_path: str
    community_account: bool
    community_balance: float
    community_connection: bool
    company: str
    connected: bool
    data_path: str
    dlls_allowed: bool
    email_enabled: bool
    ftp_enabled: bool
    language: str
    maxbars: int
    mqid: bool
    name: str
    notifications_enabled: bool
    path: str
    ping_last: int
    retransmission: float
    trade_allowed: bool
    tradeapi_disabled: bool


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

# === CONSTANTS ===
ACCOUNT_MARGIN_MODE_EXCHANGE: Literal[1] = 1
ACCOUNT_MARGIN_MODE_RETAIL_HEDGING: Literal[2] = 2
ACCOUNT_MARGIN_MODE_RETAIL_NETTING: Literal[0] = 0
ACCOUNT_STOPOUT_MODE_MONEY: Literal[1] = 1
ACCOUNT_STOPOUT_MODE_PERCENT: Literal[0] = 0
ACCOUNT_TRADE_MODE_CONTEST: Literal[1] = 1
ACCOUNT_TRADE_MODE_DEMO: Literal[0] = 0
ACCOUNT_TRADE_MODE_REAL: Literal[2] = 2
BOOK_TYPE_BUY: Literal[2] = 2
BOOK_TYPE_BUY_MARKET: Literal[4] = 4
BOOK_TYPE_SELL: Literal[1] = 1
BOOK_TYPE_SELL_MARKET: Literal[3] = 3
COPY_TICKS_ALL: Literal[-1] = -1
COPY_TICKS_INFO: Literal[1] = 1
COPY_TICKS_TRADE: Literal[2] = 2
DAY_OF_WEEK_FRIDAY: Literal[5] = 5
DAY_OF_WEEK_MONDAY: Literal[1] = 1
DAY_OF_WEEK_SATURDAY: Literal[6] = 6
DAY_OF_WEEK_SUNDAY: Literal[0] = 0
DAY_OF_WEEK_THURSDAY: Literal[4] = 4
DAY_OF_WEEK_TUESDAY: Literal[2] = 2
DAY_OF_WEEK_WEDNESDAY: Literal[3] = 3
DEAL_DIVIDEND: Literal[15] = 15
DEAL_DIVIDEND_FRANKED: Literal[16] = 16
DEAL_ENTRY_IN: Literal[0] = 0
DEAL_ENTRY_INOUT: Literal[2] = 2
DEAL_ENTRY_OUT: Literal[1] = 1
DEAL_ENTRY_OUT_BY: Literal[3] = 3
DEAL_REASON_CLIENT: Literal[0] = 0
DEAL_REASON_EXPERT: Literal[3] = 3
DEAL_REASON_MOBILE: Literal[1] = 1
DEAL_REASON_ROLLOVER: Literal[7] = 7
DEAL_REASON_SL: Literal[4] = 4
DEAL_REASON_SO: Literal[6] = 6
DEAL_REASON_SPLIT: Literal[9] = 9
DEAL_REASON_TP: Literal[5] = 5
DEAL_REASON_VMARGIN: Literal[8] = 8
DEAL_REASON_WEB: Literal[2] = 2
DEAL_TAX: Literal[17] = 17
DEAL_TYPE_BALANCE: Literal[2] = 2
DEAL_TYPE_BONUS: Literal[6] = 6
DEAL_TYPE_BUY: Literal[0] = 0
DEAL_TYPE_BUY_CANCELED: Literal[13] = 13
DEAL_TYPE_CHARGE: Literal[4] = 4
DEAL_TYPE_COMMISSION: Literal[7] = 7
DEAL_TYPE_COMMISSION_AGENT_DAILY: Literal[10] = 10
DEAL_TYPE_COMMISSION_AGENT_MONTHLY: Literal[11] = 11
DEAL_TYPE_COMMISSION_DAILY: Literal[8] = 8
DEAL_TYPE_COMMISSION_MONTHLY: Literal[9] = 9
DEAL_TYPE_CORRECTION: Literal[5] = 5
DEAL_TYPE_CREDIT: Literal[3] = 3
DEAL_TYPE_INTEREST: Literal[12] = 12
DEAL_TYPE_SELL: Literal[1] = 1
DEAL_TYPE_SELL_CANCELED: Literal[14] = 14
ORDER_FILLING_BOC: Literal[3] = 3
ORDER_FILLING_FOK: Literal[0] = 0
ORDER_FILLING_IOC: Literal[1] = 1
ORDER_FILLING_RETURN: Literal[2] = 2
ORDER_REASON_CLIENT: Literal[0] = 0
ORDER_REASON_EXPERT: Literal[3] = 3
ORDER_REASON_MOBILE: Literal[1] = 1
ORDER_REASON_SL: Literal[4] = 4
ORDER_REASON_SO: Literal[6] = 6
ORDER_REASON_TP: Literal[5] = 5
ORDER_REASON_WEB: Literal[2] = 2
ORDER_STATE_CANCELED: Literal[2] = 2
ORDER_STATE_EXPIRED: Literal[6] = 6
ORDER_STATE_FILLED: Literal[4] = 4
ORDER_STATE_PARTIAL: Literal[3] = 3
ORDER_STATE_PLACED: Literal[1] = 1
ORDER_STATE_REJECTED: Literal[5] = 5
ORDER_STATE_REQUEST_ADD: Literal[7] = 7
ORDER_STATE_REQUEST_CANCEL: Literal[9] = 9
ORDER_STATE_REQUEST_MODIFY: Literal[8] = 8
ORDER_STATE_STARTED: Literal[0] = 0
ORDER_TIME_DAY: Literal[1] = 1
ORDER_TIME_GTC: Literal[0] = 0
ORDER_TIME_SPECIFIED: Literal[2] = 2
ORDER_TIME_SPECIFIED_DAY: Literal[3] = 3
ORDER_TYPE_BUY: Literal[0] = 0
ORDER_TYPE_BUY_LIMIT: Literal[2] = 2
ORDER_TYPE_BUY_STOP: Literal[4] = 4
ORDER_TYPE_BUY_STOP_LIMIT: Literal[6] = 6
ORDER_TYPE_CLOSE_BY: Literal[8] = 8
ORDER_TYPE_SELL: Literal[1] = 1
ORDER_TYPE_SELL_LIMIT: Literal[3] = 3
ORDER_TYPE_SELL_STOP: Literal[5] = 5
ORDER_TYPE_SELL_STOP_LIMIT: Literal[7] = 7
POSITION_REASON_CLIENT: Literal[0] = 0
POSITION_REASON_EXPERT: Literal[3] = 3
POSITION_REASON_MOBILE: Literal[1] = 1
POSITION_REASON_WEB: Literal[2] = 2
POSITION_TYPE_BUY: Literal[0] = 0
POSITION_TYPE_SELL: Literal[1] = 1
RES_E_AUTH_FAILED: Literal[-6] = -6
RES_E_AUTO_TRADING_DISABLED: Literal[-8] = -8
RES_E_FAIL: Literal[-1] = -1
RES_E_INTERNAL_FAIL: Literal[-10000] = -10000
RES_E_INTERNAL_FAIL_CONNECT: Literal[-10004] = -10004
RES_E_INTERNAL_FAIL_INIT: Literal[-10003] = -10003
RES_E_INTERNAL_FAIL_RECEIVE: Literal[-10002] = -10002
RES_E_INTERNAL_FAIL_SEND: Literal[-10001] = -10001
RES_E_INTERNAL_FAIL_TIMEOUT: Literal[-10005] = -10005
RES_E_INVALID_PARAMS: Literal[-2] = -2
RES_E_INVALID_VERSION: Literal[-5] = -5
RES_E_NOT_FOUND: Literal[-4] = -4
RES_E_NO_MEMORY: Literal[-3] = -3
RES_E_UNSUPPORTED: Literal[-7] = -7
RES_S_OK: Literal[1] = 1
SYMBOL_CALC_MODE_CFD: Literal[2] = 2
SYMBOL_CALC_MODE_CFDINDEX: Literal[3] = 3
SYMBOL_CALC_MODE_CFDLEVERAGE: Literal[4] = 4
SYMBOL_CALC_MODE_EXCH_BONDS: Literal[37] = 37
SYMBOL_CALC_MODE_EXCH_BONDS_MOEX: Literal[39] = 39
SYMBOL_CALC_MODE_EXCH_FUTURES: Literal[33] = 33
SYMBOL_CALC_MODE_EXCH_OPTIONS: Literal[34] = 34
SYMBOL_CALC_MODE_EXCH_OPTIONS_MARGIN: Literal[36] = 36
SYMBOL_CALC_MODE_EXCH_STOCKS: Literal[32] = 32
SYMBOL_CALC_MODE_EXCH_STOCKS_MOEX: Literal[38] = 38
SYMBOL_CALC_MODE_FOREX: Literal[0] = 0
SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE: Literal[5] = 5
SYMBOL_CALC_MODE_FUTURES: Literal[1] = 1
SYMBOL_CALC_MODE_SERV_COLLATERAL: Literal[64] = 64
SYMBOL_CHART_MODE_BID: Literal[0] = 0
SYMBOL_CHART_MODE_LAST: Literal[1] = 1
SYMBOL_OPTION_MODE_AMERICAN: Literal[1] = 1
SYMBOL_OPTION_MODE_EUROPEAN: Literal[0] = 0
SYMBOL_OPTION_RIGHT_CALL: Literal[0] = 0
SYMBOL_OPTION_RIGHT_PUT: Literal[1] = 1
SYMBOL_ORDERS_DAILY: Literal[1] = 1
SYMBOL_ORDERS_DAILY_NO_STOPS: Literal[2] = 2
SYMBOL_ORDERS_GTC: Literal[0] = 0
SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT: Literal[4] = 4
SYMBOL_SWAP_MODE_CURRENCY_MARGIN: Literal[3] = 3
SYMBOL_SWAP_MODE_CURRENCY_SYMBOL: Literal[2] = 2
SYMBOL_SWAP_MODE_DISABLED: Literal[0] = 0
SYMBOL_SWAP_MODE_INTEREST_CURRENT: Literal[5] = 5
SYMBOL_SWAP_MODE_INTEREST_OPEN: Literal[6] = 6
SYMBOL_SWAP_MODE_POINTS: Literal[1] = 1
SYMBOL_SWAP_MODE_REOPEN_BID: Literal[8] = 8
SYMBOL_SWAP_MODE_REOPEN_CURRENT: Literal[7] = 7
SYMBOL_TRADE_EXECUTION_EXCHANGE: Literal[3] = 3
SYMBOL_TRADE_EXECUTION_INSTANT: Literal[1] = 1
SYMBOL_TRADE_EXECUTION_MARKET: Literal[2] = 2
SYMBOL_TRADE_EXECUTION_REQUEST: Literal[0] = 0
SYMBOL_TRADE_MODE_CLOSEONLY: Literal[3] = 3
SYMBOL_TRADE_MODE_DISABLED: Literal[0] = 0
SYMBOL_TRADE_MODE_FULL: Literal[4] = 4
SYMBOL_TRADE_MODE_LONGONLY: Literal[1] = 1
SYMBOL_TRADE_MODE_SHORTONLY: Literal[2] = 2
TICK_FLAG_ASK: Literal[4] = 4
TICK_FLAG_BID: Literal[2] = 2
TICK_FLAG_BUY: Literal[32] = 32
TICK_FLAG_LAST: Literal[8] = 8
TICK_FLAG_SELL: Literal[64] = 64
TICK_FLAG_VOLUME: Literal[16] = 16
TIMEFRAME_D1: Literal[16408] = 16408
TIMEFRAME_H1: Literal[16385] = 16385
TIMEFRAME_H12: Literal[16396] = 16396
TIMEFRAME_H2: Literal[16386] = 16386
TIMEFRAME_H3: Literal[16387] = 16387
TIMEFRAME_H4: Literal[16388] = 16388
TIMEFRAME_H6: Literal[16390] = 16390
TIMEFRAME_H8: Literal[16392] = 16392
TIMEFRAME_M1: Literal[1] = 1
TIMEFRAME_M10: Literal[10] = 10
TIMEFRAME_M12: Literal[12] = 12
TIMEFRAME_M15: Literal[15] = 15
TIMEFRAME_M2: Literal[2] = 2
TIMEFRAME_M20: Literal[20] = 20
TIMEFRAME_M3: Literal[3] = 3
TIMEFRAME_M30: Literal[30] = 30
TIMEFRAME_M4: Literal[4] = 4
TIMEFRAME_M5: Literal[5] = 5
TIMEFRAME_M6: Literal[6] = 6
TIMEFRAME_MN1: Literal[49153] = 49153
TIMEFRAME_W1: Literal[32769] = 32769
TRADE_ACTION_CLOSE_BY: Literal[10] = 10
TRADE_ACTION_DEAL: Literal[1] = 1
TRADE_ACTION_MODIFY: Literal[7] = 7
TRADE_ACTION_PENDING: Literal[5] = 5
TRADE_ACTION_REMOVE: Literal[8] = 8
TRADE_ACTION_SLTP: Literal[6] = 6
TRADE_RETCODE_CANCEL: Literal[10007] = 10007
TRADE_RETCODE_CLIENT_DISABLES_AT: Literal[10027] = 10027
TRADE_RETCODE_CLOSE_ONLY: Literal[10044] = 10044
TRADE_RETCODE_CLOSE_ORDER_EXIST: Literal[10039] = 10039
TRADE_RETCODE_CONNECTION: Literal[10031] = 10031
TRADE_RETCODE_DONE: Literal[10009] = 10009
TRADE_RETCODE_DONE_PARTIAL: Literal[10010] = 10010
TRADE_RETCODE_ERROR: Literal[10011] = 10011
TRADE_RETCODE_FIFO_CLOSE: Literal[10045] = 10045
TRADE_RETCODE_FROZEN: Literal[10029] = 10029
TRADE_RETCODE_INVALID: Literal[10013] = 10013
TRADE_RETCODE_INVALID_CLOSE_VOLUME: Literal[10038] = 10038
TRADE_RETCODE_INVALID_EXPIRATION: Literal[10022] = 10022
TRADE_RETCODE_INVALID_FILL: Literal[10030] = 10030
TRADE_RETCODE_INVALID_ORDER: Literal[10035] = 10035
TRADE_RETCODE_INVALID_PRICE: Literal[10015] = 10015
TRADE_RETCODE_INVALID_STOPS: Literal[10016] = 10016
TRADE_RETCODE_INVALID_VOLUME: Literal[10014] = 10014
TRADE_RETCODE_LIMIT_ORDERS: Literal[10033] = 10033
TRADE_RETCODE_LIMIT_POSITIONS: Literal[10040] = 10040
TRADE_RETCODE_LIMIT_VOLUME: Literal[10034] = 10034
TRADE_RETCODE_LOCKED: Literal[10028] = 10028
TRADE_RETCODE_LONG_ONLY: Literal[10042] = 10042
TRADE_RETCODE_MARKET_CLOSED: Literal[10018] = 10018
TRADE_RETCODE_NO_CHANGES: Literal[10025] = 10025
TRADE_RETCODE_NO_MONEY: Literal[10019] = 10019
TRADE_RETCODE_ONLY_REAL: Literal[10032] = 10032
TRADE_RETCODE_ORDER_CHANGED: Literal[10023] = 10023
TRADE_RETCODE_PLACED: Literal[10008] = 10008
TRADE_RETCODE_POSITION_CLOSED: Literal[10036] = 10036
TRADE_RETCODE_PRICE_CHANGED: Literal[10020] = 10020
TRADE_RETCODE_PRICE_OFF: Literal[10021] = 10021
TRADE_RETCODE_REJECT: Literal[10006] = 10006
TRADE_RETCODE_REJECT_CANCEL: Literal[10041] = 10041
TRADE_RETCODE_REQUOTE: Literal[10004] = 10004
TRADE_RETCODE_SERVER_DISABLES_AT: Literal[10026] = 10026
TRADE_RETCODE_SHORT_ONLY: Literal[10043] = 10043
TRADE_RETCODE_TIMEOUT: Literal[10012] = 10012
TRADE_RETCODE_TOO_MANY_REQUESTS: Literal[10024] = 10024
TRADE_RETCODE_TRADE_DISABLED: Literal[10017] = 10017

class MetaTrader5:
    """MetaTrader5 API wrapper for Linux via rpyc."""

    def __init__(self, host: str = 'localhost', port: int = 18812) -> None: ...

    def initialize(
            self,
            path: str | None = None,
            *,
            login: int | None = None,
            password: str | None = None,
            server: str | None = None,
            timeout: int | None = None,
            portable: bool = False,
        ) -> bool: ...

    def login(
            self,
            login: int,
            *,
            password: str | None = None,
            server: str | None = None,
            timeout: int | None = None,
        ) -> bool: ...

    def shutdown(self) -> None: ...

    def version(self) -> tuple[int, int, str] | None: ...

    def last_error(self) -> tuple[int, str]: ...

    def account_info(self) -> AccountInfo | None: ...

    def terminal_info(self) -> TerminalInfo | None: ...

    def symbols_total(self) -> int: ...

    def symbols_get(self, *, group: str | None = None) -> tuple[SymbolInfo, ...] | None: ...

    def symbol_info(self, symbol: str) -> SymbolInfo | None: ...

    def symbol_info_tick(self, symbol: str) -> Tick | None: ...

    def symbol_select(self, symbol: str, enable: bool = True) -> bool: ...

    def market_book_add(self, symbol: str) -> bool: ...

    def market_book_get(self, symbol: str) -> tuple[BookInfo, ...] | None: ...

    def market_book_release(self, symbol: str) -> bool: ...

    def copy_rates_from(
            self, symbol: str, timeframe: int, date_from: datetime | int, count: int
        ) -> NDArray | None: ...

    def copy_rates_from_pos(
            self, symbol: str, timeframe: int, start_pos: int, count: int
        ) -> NDArray | None: ...

    def copy_rates_range(
            self, symbol: str, timeframe: int, date_from: datetime | int, date_to: datetime | int
        ) -> NDArray | None: ...

    def copy_ticks_from(
            self, symbol: str, date_from: datetime | int, count: int, flags: int
        ) -> NDArray | None: ...

    def copy_ticks_range(
            self, symbol: str, date_from: datetime | int, date_to: datetime | int, flags: int
        ) -> NDArray | None: ...

    def orders_total(self) -> int: ...

    def orders_get(
            self, *, symbol: str | None = None, ticket: int | None = None, group: str | None = None
        ) -> tuple[TradeOrder, ...] | None: ...

    def order_calc_margin(
            self, action: int, symbol: str, volume: float, price: float
        ) -> float | None: ...

    def order_calc_profit(
            self, action: int, symbol: str, volume: float, price_open: float, price_close: float
        ) -> float | None: ...

    def order_check(self, request: TradeRequest) -> TradeCheckResult: ...

    def order_send(self, request: TradeRequest) -> TradeResult: ...

    def positions_total(self) -> int: ...

    def positions_get(
            self, *, symbol: str | None = None, ticket: int | None = None, group: str | None = None
        ) -> tuple[TradePosition, ...] | None: ...

    def history_orders_total(self, date_from: datetime | int, date_to: datetime | int) -> int: ...

    def history_orders_get(
            self,
            date_from: datetime | int | None = None,
            date_to: datetime | int | None = None,
            *,
            group: str | None = None,
            ticket: int | None = None,
            position: int | None = None,
        ) -> tuple[TradeOrder, ...] | None: ...

    def history_deals_total(self, date_from: datetime | int, date_to: datetime | int) -> int: ...

    def history_deals_get(
            self,
            date_from: datetime | int | None = None,
            date_to: datetime | int | None = None,
            *,
            group: str | None = None,
            ticket: int | None = None,
            position: int | None = None,
        ) -> tuple[TradeDeal, ...] | None: ...

    def eval(self, command: str) -> object: ...
    def execute(self, command: str) -> None: ...
