"""
Tests for TradingCost — verifies fees and slippage are correctly
applied in the vector backtest engine.

Uses the same compact CSV as the scaling rule tests
(OHLCV_BTC-EUR_BITVAVO_2h_SCALING_FAST.csv).

Price pattern:
  Rows 1-5: warmup (Close=100)
  Row 6: Close=110 → BUY
  Row 16: Close=90 → SELL

Without costs:  net_gain = (90 - 110) * amount = -20 * amount
With slippage:  buy fills higher, sell fills lower → worse P&L
With fees:      fee deducted from capital and proceeds → worse P&L
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

import pandas as pd

from investing_algorithm_framework import (
    TradingStrategy, DataSource, TimeUnit, DataType,
    create_app, BacktestDateRange, PositionSize,
    RESOURCE_DIRECTORY, CSVOHLCVDataProvider, TradingCost,
)


CSV_FILENAME = "OHLCV_BTC-EUR_BITVAVO_2h_SCALING_FAST.csv"
WARMUP = 5
START_DATE = datetime(2020, 12, 20, 10, 0, 0, tzinfo=timezone.utc)
END_DATE = datetime(2020, 12, 21, 8, 0, 0, tzinfo=timezone.utc)
INITIAL_BALANCE = 10000.0


def _make_data_source():
    return DataSource(
        symbol="BTC/EUR",
        data_type=DataType.OHLCV,
        time_frame="2h",
        warmup_window=WARMUP,
        market="BITVAVO",
        identifier="BTC_EUR_OHLCV",
        pandas=True,
    )


# ── Strategy with NO costs (baseline) ──────────────────────────────
class NoCostStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]

    def generate_buy_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 110}

    def generate_sell_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 90}


# ── Strategy with symbol-level TradingCost ─────────────────────────
class SymbolCostStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]
    trading_costs = [
        TradingCost(
            symbol="BTC",
            fee_percentage=0.1,        # 0.1 %
            slippage_percentage=0.5,   # 0.5 %
        ),
    ]

    def generate_buy_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 110}

    def generate_sell_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 90}


# ── Strategy with fee only (no slippage) ───────────────────────────
class FeeOnlyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]
    trading_costs = [
        TradingCost(
            symbol="BTC",
            fee_percentage=1.0,  # 1 % fee (big for clear effect)
        ),
    ]

    def generate_buy_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 110}

    def generate_sell_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 90}


# ── Strategy with slippage only (no fee) ───────────────────────────
class SlippageOnlyStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]
    trading_costs = [
        TradingCost(
            symbol="BTC",
            slippage_percentage=1.0,  # 1 % slippage (big for clear effect)
        ),
    ]

    def generate_buy_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 110}

    def generate_sell_signals(self, data):
        df = data["BTC_EUR_OHLCV"]
        return {"BTC": df['Close'] == 90}


def _run_backtest(strategy_class, fee_pct=0.0, slippage_pct=0.0):
    """Run a vector backtest and return the single closed trade."""
    app = create_app()
    app.add_market(
        market="BITVAVO",
        trading_symbol="EUR",
        initial_balance=INITIAL_BALANCE,
        fee_percentage=fee_pct,
        slippage_percentage=slippage_pct,
    )
    csv_path = str(
        Path(__file__).parent.parent / 'resources' / 'test_data'
        / 'ohlcv' / CSV_FILENAME
    )
    app.add_data_provider(
        data_provider=CSVOHLCVDataProvider(
            storage_path=csv_path,
            symbol="BTC/EUR",
            time_frame="2h",
            market="BITVAVO",
            warmup_window=WARMUP,
        ),
        priority=1,
    )
    strategy = strategy_class()
    app.add_strategy(strategy)
    backtest = app.run_vector_backtest(
        backtest_date_range=BacktestDateRange(
            start_date=START_DATE, end_date=END_DATE
        ),
    )
    runs = backtest.backtest_runs
    assert len(runs) == 1, f"Expected 1 run, got {len(runs)}"
    trades = runs[0].trades
    closed = [t for t in trades if t.status == "CLOSED"]
    assert len(closed) == 1, f"Expected 1 closed trade, got {len(closed)}"
    return closed[0]


class TestTradingCostVectorBacktest(TestCase):

    # ------------------------------------------------------------------
    # Baseline: no costs
    # ------------------------------------------------------------------
    def test_baseline_no_costs(self):
        """With zero costs, net_gain = (90 - 110) * amount."""
        trade = _run_backtest(NoCostStrategy)
        # Capital = 20% of 10000 = 2000, buy at 110 → amount = 2000/110
        expected_amount = 2000.0 / 110.0
        expected_gain = (90 - 110) * expected_amount
        self.assertAlmostEqual(trade.net_gain, expected_gain, places=4)
        self.assertAlmostEqual(trade.open_price, 110.0, places=4)
        self.assertEqual(trade.total_fees, 0)

    # ------------------------------------------------------------------
    # Symbol-level: fee + slippage
    # ------------------------------------------------------------------
    def test_symbol_level_fee_and_slippage(self):
        """Symbol-level TradingCost applies slippage and fee."""
        trade = _run_backtest(SymbolCostStrategy)
        # Slippage 0.5%: buy fills at 110*1.005=110.55
        buy_fill = 110.0 * 1.005
        # Fee 0.1% on capital: buy_fee = 2000 * 0.001 = 2
        capital = 2000.0
        buy_fee = capital * 0.001
        net_capital = capital - buy_fee
        amount = net_capital / buy_fill
        # Sell fills at 90*0.995=89.55
        sell_fill = 90.0 * 0.995
        sell_gross = amount * sell_fill
        sell_fee = sell_gross * 0.001
        expected_gain = sell_gross - sell_fee - net_capital
        self.assertAlmostEqual(trade.open_price, buy_fill, places=2)
        self.assertAlmostEqual(trade.net_gain, expected_gain, places=2)
        self.assertGreater(trade.total_fees, 0)
        # Net gain should be worse than baseline
        baseline = _run_backtest(NoCostStrategy)
        self.assertLess(trade.net_gain, baseline.net_gain)

    # ------------------------------------------------------------------
    # Fee only
    # ------------------------------------------------------------------
    def test_fee_only(self):
        """Fee reduces capital and proceeds, slippage=0 → price unchanged."""
        trade = _run_backtest(FeeOnlyStrategy)
        # buy at exactly 110 (no slippage)
        self.assertAlmostEqual(trade.open_price, 110.0, places=4)
        # Fee 1%: buy_fee = 2000*0.01 = 20
        capital = 2000.0
        buy_fee = capital * 0.01
        amount = (capital - buy_fee) / 110.0
        sell_gross = amount * 90.0
        sell_fee = sell_gross * 0.01
        expected_gain = sell_gross - sell_fee - (capital - buy_fee)
        self.assertAlmostEqual(trade.net_gain, expected_gain, places=2)
        self.assertAlmostEqual(trade.total_fees, buy_fee + sell_fee, places=2)

    # ------------------------------------------------------------------
    # Slippage only
    # ------------------------------------------------------------------
    def test_slippage_only(self):
        """Slippage moves fill prices; no fee deducted."""
        trade = _run_backtest(SlippageOnlyStrategy)
        buy_fill = 110.0 * 1.01  # +1 % slippage
        sell_fill = 90.0 * 0.99  # -1 % slippage
        amount = 2000.0 / buy_fill
        expected_gain = (sell_fill - buy_fill) * amount
        self.assertAlmostEqual(trade.open_price, buy_fill, places=4)
        self.assertAlmostEqual(trade.net_gain, expected_gain, places=2)
        self.assertEqual(trade.total_fees, 0)

    # ------------------------------------------------------------------
    # Market-level defaults (no TradingCost on strategy)
    # ------------------------------------------------------------------
    def test_market_level_defaults(self):
        """Fee/slippage set on add_market applies to all symbols."""
        trade = _run_backtest(
            NoCostStrategy, fee_pct=0.5, slippage_pct=0.2
        )
        # Values should differ from the zero-cost baseline
        baseline = _run_backtest(NoCostStrategy)
        self.assertLess(trade.net_gain, baseline.net_gain)
        self.assertGreater(trade.total_fees, 0)
        # open_price should include slippage
        buy_fill = 110.0 * 1.002  # 0.2 %
        self.assertAlmostEqual(trade.open_price, buy_fill, places=2)

    # ------------------------------------------------------------------
    # Symbol-level overrides market-level
    # ------------------------------------------------------------------
    def test_symbol_overrides_market(self):
        """Per-symbol TradingCost should override market defaults."""
        # SymbolCostStrategy has fee=0.1%, slip=0.5% on BTC
        # Market defaults: fee=5%, slip=5% (intentionally large)
        trade_symbol = _run_backtest(
            SymbolCostStrategy, fee_pct=5.0, slippage_pct=5.0
        )
        # The symbol-level values should be used, not market-level
        buy_fill = 110.0 * 1.005  # 0.5%, not 5%
        self.assertAlmostEqual(
            trade_symbol.open_price, buy_fill, places=2
        )

    # ------------------------------------------------------------------
    # Orders have fee fields set
    # ------------------------------------------------------------------
    def test_orders_have_fee_fields(self):
        """Buy and sell orders should have order_fee set."""
        trade = _run_backtest(SymbolCostStrategy)
        buy_orders = [
            o for o in trade.orders if o.order_side == "BUY"
        ]
        sell_orders = [
            o for o in trade.orders if o.order_side == "SELL"
        ]
        self.assertEqual(len(buy_orders), 1)
        self.assertEqual(len(sell_orders), 1)
        self.assertIsNotNone(buy_orders[0].order_fee)
        self.assertGreater(buy_orders[0].order_fee, 0)
        self.assertIsNotNone(sell_orders[0].order_fee)
        self.assertGreater(sell_orders[0].order_fee, 0)

    # ------------------------------------------------------------------
    # TradingCost model unit tests
    # ------------------------------------------------------------------
    def test_trading_cost_resolve_symbol_level(self):
        """resolve() returns symbol-level cost when available."""
        costs = [TradingCost(symbol="BTC", fee_percentage=0.5)]
        tc = TradingCost.resolve("BTC", costs)
        self.assertEqual(tc.fee_percentage, 0.5)

    def test_trading_cost_resolve_market_level(self):
        """resolve() falls back to market-level defaults."""
        from investing_algorithm_framework import PortfolioConfiguration
        pc = PortfolioConfiguration(
            market="TEST", trading_symbol="EUR",
            fee_percentage=0.3, slippage_percentage=0.1
        )
        tc = TradingCost.resolve("ETH", [], pc)
        self.assertEqual(tc.fee_percentage, 0.3)
        self.assertEqual(tc.slippage_percentage, 0.1)

    def test_trading_cost_resolve_zero_fallback(self):
        """resolve() returns zero-cost when nothing configured."""
        tc = TradingCost.resolve("ETH", [])
        self.assertEqual(tc.fee_percentage, 0.0)
        self.assertEqual(tc.slippage_percentage, 0.0)

    def test_buy_fill_price(self):
        tc = TradingCost(slippage_percentage=1.0)
        self.assertAlmostEqual(tc.get_buy_fill_price(100), 101.0)

    def test_sell_fill_price(self):
        tc = TradingCost(slippage_percentage=1.0)
        self.assertAlmostEqual(tc.get_sell_fill_price(100), 99.0)

    def test_get_fee(self):
        tc = TradingCost(fee_percentage=0.5, fee_fixed=1.0)
        # 0.5% of 1000 + 1.0 = 6.0
        self.assertAlmostEqual(tc.get_fee(1000), 6.0)
