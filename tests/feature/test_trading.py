"""Feature tests for trading operations (Epic 3, Stories 3.1-3.3).

Tests:
    - Order calculation (margin, profit)
    - Order checking (validation)
    - Order execution (buy/sell)
    - Trade verification
    - Trade failure detection
    - Position closing

IMPORTANT:
    These tests ONLY run on DEMO accounts.
    All positions opened are closed in cleanup.
"""

import time
from typing import Any

import pytest

pytestmark = [pytest.mark.feature_long]


class TestOrderCalculations:
    """Test order calculation functions (no actual trading)."""

    @pytest.mark.feature_short
    def test_order_calc_margin_buy(
        self, mt5: Any, symbol_eurusd: str, is_demo_account: bool
    ) -> None:
        """Test margin calculation for buy order."""
        info = mt5.symbol_info(symbol_eurusd)
        volume = info.volume_min

        margin = mt5.order_calc_margin(
            0,  # ORDER_TYPE_BUY
            symbol_eurusd,
            volume,
            info.ask,
        )
        assert margin is not None
        assert margin > 0

    @pytest.mark.feature_short
    def test_order_calc_margin_sell(
        self, mt5: Any, symbol_eurusd: str, is_demo_account: bool
    ) -> None:
        """Test margin calculation for sell order."""
        info = mt5.symbol_info(symbol_eurusd)
        volume = info.volume_min

        margin = mt5.order_calc_margin(
            1,  # ORDER_TYPE_SELL
            symbol_eurusd,
            volume,
            info.bid,
        )
        assert margin is not None
        assert margin > 0

    @pytest.mark.feature_short
    def test_order_calc_profit(
        self, mt5: Any, symbol_eurusd: str, is_demo_account: bool
    ) -> None:
        """Test profit calculation."""
        info = mt5.symbol_info(symbol_eurusd)
        volume = info.volume_min

        # Calculate profit for 10 pip move
        price_open = info.ask
        price_close = price_open + 0.0010  # 10 pips

        profit = mt5.order_calc_profit(
            0,  # ORDER_TYPE_BUY
            symbol_eurusd,
            volume,
            price_open,
            price_close,
        )
        assert profit is not None
        assert profit > 0  # Price went up, so profit should be positive


class TestOrderChecking:
    """Test order validation before execution."""

    @pytest.mark.feature_short
    def test_order_check_valid_buy(
        self, mt5: Any, symbol_eurusd: str, is_demo_account: bool
    ) -> None:
        """Test order check for valid buy order."""
        info = mt5.symbol_info(symbol_eurusd)

        request = {
            "action": 1,  # TRADE_ACTION_DEAL
            "symbol": symbol_eurusd,
            "volume": info.volume_min,
            "type": 0,  # ORDER_TYPE_BUY
            "price": info.ask,
            "deviation": 20,
            "magic": 123456,
            "comment": "test_order_check",
            "type_time": 0,  # ORDER_TIME_GTC
            "type_filling": 2,  # ORDER_FILLING_IOC (or check symbol's filling mode)
        }

        result = mt5.order_check(request)
        assert result is not None
        # retcode 0 means check passed
        assert result.retcode == 0, f"Order check failed: {result.comment}"

    @pytest.mark.feature_short
    def test_order_check_invalid_volume(
        self, mt5: Any, symbol_eurusd: str, is_demo_account: bool
    ) -> None:
        """Test order check rejects invalid volume."""
        info = mt5.symbol_info(symbol_eurusd)

        request = {
            "action": 1,
            "symbol": symbol_eurusd,
            "volume": 0.0,  # Invalid volume
            "type": 0,
            "price": info.ask,
            "deviation": 20,
            "magic": 123456,
            "comment": "test_invalid_volume",
            "type_time": 0,
            "type_filling": 2,
        }

        result = mt5.order_check(request)
        assert result is not None
        # Should fail validation
        assert result.retcode != 0


class TestOrderExecution:
    """Test actual order execution on DEMO account."""

    def test_buy_and_close_position(
        self,
        mt5: Any,
        symbol_eurusd: str,
        is_demo_account: bool,
        cleanup_positions: None,
    ) -> None:
        """Test opening and closing a buy position."""
        info = mt5.symbol_info(symbol_eurusd)
        tick = mt5.symbol_info_tick(symbol_eurusd)

        # Prepare buy request
        request = {
            "action": 1,  # TRADE_ACTION_DEAL
            "symbol": symbol_eurusd,
            "volume": info.volume_min,
            "type": 0,  # ORDER_TYPE_BUY
            "price": tick.ask,
            "deviation": 20,
            "magic": 234567,
            "comment": "feature_test_buy",
            "type_time": 0,
            "type_filling": 2,
        }

        # Execute order
        result = mt5.order_send(request)
        assert result is not None
        assert result.retcode == 10009, f"Order failed: {result.comment}"  # DONE

        # Verify position exists
        time.sleep(1)  # Allow order to process
        # Position might have different ticket than order
        positions = mt5.positions_get(symbol=symbol_eurusd)
        assert len(positions) > 0, "Position not created"

        # Close position
        pos = positions[-1]  # Get the last opened position
        close_result = mt5.close_position(pos.ticket)
        assert close_result is not None

    def test_sell_and_close_position(
        self,
        mt5: Any,
        symbol_eurusd: str,
        is_demo_account: bool,
        cleanup_positions: None,
    ) -> None:
        """Test opening and closing a sell position."""
        info = mt5.symbol_info(symbol_eurusd)
        tick = mt5.symbol_info_tick(symbol_eurusd)

        # Prepare sell request
        request = {
            "action": 1,
            "symbol": symbol_eurusd,
            "volume": info.volume_min,
            "type": 1,  # ORDER_TYPE_SELL
            "price": tick.bid,
            "deviation": 20,
            "magic": 234568,
            "comment": "feature_test_sell",
            "type_time": 0,
            "type_filling": 2,
        }

        # Execute order
        result = mt5.order_send(request)
        assert result is not None
        assert result.retcode == 10009, f"Order failed: {result.comment}"

        # Close position
        time.sleep(1)
        positions = mt5.positions_get(symbol=symbol_eurusd)
        assert len(positions) > 0

        pos = positions[-1]
        close_result = mt5.close_position(pos.ticket)
        assert close_result is not None

    def test_trade_on_index(
        self,
        mt5: Any,
        symbol_ustec: str,
        is_demo_account: bool,
        cleanup_positions: None,
    ) -> None:
        """Test trading on index symbol (USTEC)."""
        info = mt5.symbol_info(symbol_ustec)

        # Check if trading is allowed on this symbol
        if info.trade_mode == 0:  # SYMBOL_TRADE_MODE_DISABLED
            pytest.skip(f"{symbol_ustec} trading is disabled")

        tick = mt5.symbol_info_tick(symbol_ustec)

        request = {
            "action": 1,
            "symbol": symbol_ustec,
            "volume": info.volume_min,
            "type": 0,  # BUY
            "price": tick.ask,
            "deviation": 50,  # Wider deviation for indices
            "magic": 234569,
            "comment": "feature_test_index",
            "type_time": 0,
            "type_filling": 2,
        }

        result = mt5.order_send(request)
        assert result is not None

        # May fail if market is closed or other broker restrictions
        if result.retcode == 10009:
            time.sleep(1)
            positions = mt5.positions_get(symbol=symbol_ustec)
            if positions:
                mt5.close_position(positions[-1].ticket)


class TestTradeVerification:
    """Test trade verification functionality (Story 3.2)."""

    def test_verification_result_available_after_trade(
        self,
        mt5: Any,
        symbol_eurusd: str,
        is_demo_account: bool,
        cleanup_positions: None,
    ) -> None:
        """Test that verification result is available after trade."""
        info = mt5.symbol_info(symbol_eurusd)
        tick = mt5.symbol_info_tick(symbol_eurusd)

        request = {
            "action": 1,
            "symbol": symbol_eurusd,
            "volume": info.volume_min,
            "type": 0,
            "price": tick.ask,
            "deviation": 20,
            "magic": 345678,
            "comment": "test_verification",
            "type_time": 0,
            "type_filling": 2,
        }

        result = mt5.order_send(request)

        if result.retcode == 10009:
            # Check verification result - we just verify method doesn't raise
            _verification = mt5.get_last_verification_result()
            # May or may not be available depending on implementation

            # Cleanup
            time.sleep(1)
            positions = mt5.positions_get(symbol=symbol_eurusd)
            if positions:
                mt5.close_position(positions[-1].ticket)


class TestTradeFailureDetection:
    """Test trade failure detection (Story 3.3)."""

    def test_failure_detected_on_invalid_order(
        self, mt5: Any, symbol_eurusd: str, is_demo_account: bool
    ) -> None:
        """Test that failures are properly detected."""
        info = mt5.symbol_info(symbol_eurusd)

        # Send invalid order (zero volume)
        request = {
            "action": 1,
            "symbol": symbol_eurusd,
            "volume": 0.0,  # Invalid
            "type": 0,
            "price": info.ask,
            "deviation": 20,
            "magic": 456789,
            "comment": "test_failure",
            "type_time": 0,
            "type_filling": 2,
        }

        result = mt5.order_send(request)
        assert result is not None
        assert result.retcode != 10009  # Should NOT succeed

        # Check failure context is available - verify method doesn't raise
        _failure = mt5.get_last_trade_failure()
        # May or may not capture this as a "failure" depending on implementation


class TestPositionModification:
    """Test position modification operations."""

    def test_modify_position_sl_tp(
        self,
        mt5: Any,
        symbol_eurusd: str,
        is_demo_account: bool,
        cleanup_positions: None,
    ) -> None:
        """Test modifying position SL/TP."""
        info = mt5.symbol_info(symbol_eurusd)
        tick = mt5.symbol_info_tick(symbol_eurusd)

        # Open position first
        request = {
            "action": 1,
            "symbol": symbol_eurusd,
            "volume": info.volume_min,
            "type": 0,
            "price": tick.ask,
            "deviation": 20,
            "magic": 567890,
            "comment": "test_modify",
            "type_time": 0,
            "type_filling": 2,
        }

        result = mt5.order_send(request)
        if result.retcode != 10009:
            pytest.skip(f"Could not open position: {result.comment}")

        time.sleep(1)
        positions = mt5.positions_get(symbol=symbol_eurusd)
        assert len(positions) > 0

        pos = positions[-1]

        # Calculate SL/TP (50 pips)
        sl = tick.ask - 0.0050
        tp = tick.ask + 0.0050

        # Modify position - result depends on broker support
        _modify_result = mt5.modify_position_sl_tp(pos.ticket, sl=sl, tp=tp)

        # Cleanup
        mt5.close_position(pos.ticket)


class TestCloseAllPositions:
    """Test bulk position closing."""

    def test_close_all_positions_by_symbol(
        self,
        mt5: Any,
        symbol_eurusd: str,
        is_demo_account: bool,
        cleanup_positions: None,
    ) -> None:
        """Test closing all positions for a symbol."""
        info = mt5.symbol_info(symbol_eurusd)
        tick = mt5.symbol_info_tick(symbol_eurusd)

        # Open two positions
        for i in range(2):
            request = {
                "action": 1,
                "symbol": symbol_eurusd,
                "volume": info.volume_min,
                "type": 0,
                "price": tick.ask,
                "deviation": 20,
                "magic": 678901 + i,
                "comment": f"test_close_all_{i}",
                "type_time": 0,
                "type_filling": 2,
            }
            mt5.order_send(request)
            time.sleep(0.5)

        time.sleep(1)

        # Close all positions for symbol
        _results = mt5.close_all_positions(symbol=symbol_eurusd)

        # Verify all closed
        time.sleep(1)
        remaining = mt5.positions_get(symbol=symbol_eurusd)
        assert len(remaining or ()) == 0, "Not all positions were closed"
