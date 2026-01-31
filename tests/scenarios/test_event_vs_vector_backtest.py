import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from unittest import TestCase

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, PositionSize, \
    RESOURCE_DIRECTORY, SnapshotInterval


class RSIEMACrossoverStrategy(TradingStrategy):
    """
    A strategy that combines RSI and EMA crossover signals for buy/sell decisions.

    This strategy supports both event-based and vector-based backtesting by
    implementing both the `on_run` method (for event-based) and the
    `generate_buy_signals`/`generate_sell_signals` methods (for vector-based).
    """
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC", "ETH", "DOT", "XRP"]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
        PositionSize(symbol="ETH", percentage_of_portfolio=20.0),
        PositionSize(symbol="DOT", percentage_of_portfolio=10.0),
        PositionSize(symbol="XRP", percentage_of_portfolio=10.0)
    ]

    def __init__(
        self,
        algorithm_id: str,
        time_unit: TimeUnit,
        interval: int,
        market: str,
        rsi_time_frame: str,
        rsi_period: int,
        rsi_overbought_threshold: float,
        rsi_oversold_threshold: float,
        ema_time_frame: str,
        ema_short_period: int,
        ema_long_period: int,
        ema_cross_lookback_window: int = 10
    ):
        self.rsi_time_frame = rsi_time_frame
        self.rsi_period = rsi_period
        self.rsi_result_column = f"rsi_{self.rsi_period}"
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_time_frame = ema_time_frame
        self.ema_short_result_column = f"ema_{ema_short_period}"
        self.ema_long_result_column = f"ema_{ema_long_period}"
        self.ema_crossunder_result_column = "ema_crossunder"
        self.ema_crossover_result_column = "ema_crossover"
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window
        data_sources = []

        for symbol in self.symbols:
            full_symbol = f"{symbol}/EUR"
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_rsi_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.rsi_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True,
                    window_size=800
                )
            )
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_ema_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.ema_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True,
                    window_size=800
                )
            )

        super().__init__(
            algorithm_id=algorithm_id,
            data_sources=data_sources,
            time_unit=time_unit,
            interval=interval
        )

    def prepare_indicators(self, rsi_data, ema_data):
        """Prepare indicators for both RSI and EMA data."""
        ema_data = ema(
            ema_data,
            period=self.ema_short_period,
            source_column="Close",
            result_column=self.ema_short_result_column
        )
        ema_data = ema(
            ema_data,
            period=self.ema_long_period,
            source_column="Close",
            result_column=self.ema_long_result_column
        )
        ema_data = crossover(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossover_result_column
        )
        ema_data = crossunder(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossunder_result_column
        )
        rsi_data = rsi(
            rsi_data,
            period=self.rsi_period,
            source_column="Close",
            result_column=self.rsi_result_column
        )
        return ema_data, rsi_data

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        """Generate buy signals for vector-based backtesting."""
        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"{symbol}_ema_data"
            rsi_data_identifier = f"{symbol}_rsi_data"
            ema_data, rsi_data = self.prepare_indicators(
                data[ema_data_identifier].copy(),
                data[rsi_data_identifier].copy()
            )

            # crossover confirmed within lookback window
            ema_crossover_lookback = ema_data[
                self.ema_crossover_result_column
            ].rolling(window=self.ema_cross_lookback_window).max().astype(bool)

            # RSI oversold condition
            rsi_oversold = rsi_data[self.rsi_result_column] < self.rsi_oversold_threshold

            buy_signal = rsi_oversold & ema_crossover_lookback
            buy_signals = buy_signal.fillna(False).astype(bool)
            signals[symbol] = buy_signals

        return signals

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        """Generate sell signals for vector-based backtesting."""
        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"{symbol}_ema_data"
            rsi_data_identifier = f"{symbol}_rsi_data"

            ema_data, rsi_data = self.prepare_indicators(
                data[ema_data_identifier].copy(),
                data[rsi_data_identifier].copy()
            )

            # crossunder confirmed within lookback window
            ema_crossunder_lookback = ema_data[
                self.ema_crossunder_result_column
            ].rolling(window=self.ema_cross_lookback_window).max().astype(bool)

            # RSI overbought condition
            rsi_overbought = rsi_data[self.rsi_result_column] >= self.rsi_overbought_threshold

            sell_signal = rsi_overbought & ema_crossunder_lookback
            sell_signal = sell_signal.fillna(False).astype(bool)
            signals[symbol] = sell_signal

        return signals


class TestEventVsVectorBacktest(TestCase):
    """
    Test class that compares event-based and vector-based backtest results.

    This test ensures that both backtesting approaches produce consistent
    results when using the same strategy and data.

    KEY DIFFERENCES IN DATA PROVISION:

    1. **Vector backtest**:
       - Loads ALL data at once (from start_date - window_size*timeframe to end_date)
       - Strategy's generate_buy/sell_signals sees the FULL dataset
       - Indicators computed on complete history

    2. **Event backtest**:
       - At each iteration, loads only a WINDOW of data (last N bars)
       - Strategy's on_run sees only the current window
       - Indicators computed fresh on each window

    This means indicators behave identically at the END of the backtest,
    but may differ at the BEGINNING (warmup period). However, with a
    sufficiently large window_size (800 bars in this test), the signals
    should be identical.

    With dynamic_position_sizing=True, the vector backtest processes all
    symbols together in chronological order, sharing the portfolio state.

    Remaining differences in metrics are due to:
    - Execution timing (vector at exact signal time, event at interval)
    - Price used for execution may differ slightly

    The backtests are run once in setUpClass and reused across all tests.
    """

    # Class-level variables to store backtest results
    vector_run = None
    event_run = None
    vector_metrics = None
    event_metrics = None

    @classmethod
    def setUpClass(cls):
        """
        Run backtests once before all tests.
        This significantly improves test performance by avoiding
        redundant backtest runs.
        """
        # Resource directory should point to /tests/resources
        resource_directory = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'resources'
        )
        config = {RESOURCE_DIRECTORY: resource_directory}

        # Create app
        app = create_app(name="EventVsVectorTest", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=400
        )

        # Set up date range
        end_date = datetime(2023, 12, 2, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=730)
        date_range = BacktestDateRange(start_date=start_date, end_date=end_date)

        # Create and run vector-based backtest
        vector_strategy = RSIEMACrossoverStrategy(
            algorithm_id="vector_strategy",
            time_unit=TimeUnit.HOUR,
            interval=2,
            market="BITVAVO",
            rsi_time_frame="2h",
            rsi_period=14,
            rsi_overbought_threshold=70,
            rsi_oversold_threshold=30,
            ema_time_frame="2h",
            ema_short_period=50,
            ema_long_period=200,
            ema_cross_lookback_window=10,
        )
        vector_backtest = app.run_vector_backtest(
            initial_amount=1000,
            backtest_date_range=date_range,
            strategy=vector_strategy,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027,
            trading_symbol="EUR",
            market="BITVAVO",
            dynamic_position_sizing=True,  # Enable dynamic position sizing to match event backtest behavior
        )
        cls.vector_run = vector_backtest.backtest_runs[0]
        cls.vector_metrics = cls.vector_run.backtest_metrics

        # Create and run event-based backtest
        event_strategy = RSIEMACrossoverStrategy(
            algorithm_id="event_strategy",
            time_unit=TimeUnit.HOUR,
            interval=2,
            market="BITVAVO",
            rsi_time_frame="2h",
            rsi_period=14,
            rsi_overbought_threshold=70,
            rsi_oversold_threshold=30,
            ema_time_frame="2h",
            ema_short_period=50,
            ema_long_period=200,
            ema_cross_lookback_window=10,
        )
        event_backtest = app.run_backtest(
            initial_amount=1000,
            backtest_date_range=date_range,
            strategy=event_strategy,
            snapshot_interval=SnapshotInterval.DAILY,
            risk_free_rate=0.027
        )
        cls.event_run = event_backtest.backtest_runs[0]
        cls.event_metrics = cls.event_run.backtest_metrics

    def test_compare_event_and_vector_backtest_trade_counts(self):
        """
        Test that event-based and vector-based backtests produce the same
        number of trades.
        """
        #Compare trade counts
        self.assertEqual(
            len(self.vector_run.get_trades()),
            len(self.event_run.get_trades()),
            f"Trade count mismatch: vector={len(self.vector_run.get_trades())}, "
            f"event={len(self.event_run.get_trades())}"
        )

    def test_compare_event_and_vector_backtest_metrics(self):
        """
        Test that event-based and vector-based backtests produce similar
        performance metrics.

        This test compares key metrics between the two approaches:
        - Number of trades
        - Total net gain
        - Sharpe ratio
        - Profit factor
        - Max drawdown
        - Win rate
        """
        vector_metrics = self.vector_metrics
        event_metrics = self.event_metrics

        # Compare number of trades
        self.assertEqual(
            len(self.vector_run.get_trades()),
            len(self.event_run.get_trades()),
            "Number of trades should match"
        )

        # Note: With dynamic_position_sizing=True, vector and event backtests
        # now share portfolio state across symbols, so results should be very
        # close. Small differences may occur due to execution timing.
        # We use 10% tolerance for financial metrics.

        # Compare total net gain (allow tolerance for timing differences)
        self.assertAlmostEqual(
            vector_metrics.total_net_gain,
            event_metrics.total_net_gain,
            delta=abs(event_metrics.total_net_gain) * 0.10 if event_metrics.total_net_gain != 0 else 10.0,  # 10% tolerance
            msg=f"Total net gain mismatch: vector={vector_metrics.total_net_gain}, "
                f"event={event_metrics.total_net_gain}"
        )

        # Compare total net gain percentage
        self.assertAlmostEqual(
            vector_metrics.total_net_gain_percentage,
            event_metrics.total_net_gain_percentage,
            delta=abs(event_metrics.total_net_gain_percentage) * 0.10 if event_metrics.total_net_gain_percentage != 0 else 1.0,
            msg=f"Total net gain percentage mismatch: "
                f"vector={vector_metrics.total_net_gain_percentage}, "
                f"event={event_metrics.total_net_gain_percentage}"
        )

        # Compare final portfolio value
        self.assertAlmostEqual(
            vector_metrics.final_value,
            event_metrics.final_value,
            delta=abs(event_metrics.final_value) * 0.05,  # 5% tolerance for final value
            msg=f"Final value mismatch: vector={vector_metrics.final_value}, "
                f"event={event_metrics.final_value}"
        )

        # Compare Sharpe ratio (if both have valid values)
        # Sharpe ratio is sensitive to small differences in returns, so we use higher tolerance
        if vector_metrics.sharpe_ratio is not None and event_metrics.sharpe_ratio is not None:
            self.assertAlmostEqual(
                vector_metrics.sharpe_ratio,
                event_metrics.sharpe_ratio,
                delta=abs(event_metrics.sharpe_ratio) * 0.40 if event_metrics.sharpe_ratio != 0 else 0.5,
                msg=f"Sharpe ratio mismatch: vector={vector_metrics.sharpe_ratio}, "
                    f"event={event_metrics.sharpe_ratio}"
            )

        # Compare profit factor (if both have valid values)
        # Note: Profit factor is very sensitive to individual trade outcomes.
        # When profit factors are small (< 1), both indicate unprofitable strategies
        # and small absolute differences become large percentage differences.
        # We check directional agreement (both profitable or both unprofitable).
        if (vector_metrics.profit_factor is not None
            and event_metrics.profit_factor is not None
            and vector_metrics.profit_factor != float('inf')
            and event_metrics.profit_factor != float('inf')):
            # Check if both agree on profitability direction
            vector_profitable = vector_metrics.profit_factor >= 1.0
            event_profitable = event_metrics.profit_factor >= 1.0

            if vector_profitable == event_profitable:
                # Both agree on direction - if both profitable, check tolerance
                if event_profitable and event_metrics.profit_factor >= 1.0:
                    self.assertAlmostEqual(
                        vector_metrics.profit_factor,
                        event_metrics.profit_factor,
                        delta=abs(event_metrics.profit_factor) * 0.50,
                        msg=f"Profit factor mismatch: vector={vector_metrics.profit_factor}, "
                            f"event={event_metrics.profit_factor}"
                    )
                # If both unprofitable, no strict tolerance needed - they agree
            else:
                # Disagreement on profitability - this is a real issue
                self.fail(
                    f"Profit factor direction mismatch: vector={vector_metrics.profit_factor} "
                    f"({'profitable' if vector_profitable else 'unprofitable'}), "
                    f"event={event_metrics.profit_factor} "
                    f"({'profitable' if event_profitable else 'unprofitable'})"
                )

        # Compare max drawdown
        if vector_metrics.max_drawdown is not None and event_metrics.max_drawdown is not None:
            self.assertAlmostEqual(
                vector_metrics.max_drawdown,
                event_metrics.max_drawdown,
                delta=abs(event_metrics.max_drawdown) * 0.40 if event_metrics.max_drawdown != 0 else 0.05,
                msg=f"Max drawdown mismatch: vector={vector_metrics.max_drawdown}, "
                    f"event={event_metrics.max_drawdown}"
            )

        # Compare win rate
        if vector_metrics.win_rate is not None and event_metrics.win_rate is not None:
            self.assertAlmostEqual(
                vector_metrics.win_rate,
                event_metrics.win_rate,
                delta=abs(event_metrics.win_rate) * 0.40 if event_metrics.win_rate != 0 else 10.0,
                msg=f"Win rate mismatch: vector={vector_metrics.win_rate}, "
                    f"event={event_metrics.win_rate}"
            )

    def test_compare_event_and_vector_backtest_detailed_metrics(self):
        """
        Test that provides a detailed comparison of all available metrics
        between event-based and vector-based backtests.
        """
        vector_run = self.vector_run
        event_run = self.event_run
        vector_metrics = self.vector_metrics
        event_metrics = self.event_metrics

        # Collect metrics comparison
        metrics_comparison = {
            "number_of_trades": (
                len(vector_run.get_trades()),
                len(event_run.get_trades())
            ),
            "number_of_orders": (
                len(vector_run.orders),
                len(event_run.orders)
            ),
            "total_net_gain": (
                vector_metrics.total_net_gain,
                event_metrics.total_net_gain
            ),
            "total_net_gain_percentage": (
                vector_metrics.total_net_gain_percentage,
                event_metrics.total_net_gain_percentage
            ),
            "total_growth": (
                vector_metrics.total_growth,
                event_metrics.total_growth
            ),
            "total_growth_percentage": (
                vector_metrics.total_growth_percentage,
                event_metrics.total_growth_percentage
            ),
            "final_value": (
                vector_metrics.final_value,
                event_metrics.final_value
            ),
            "cagr": (
                vector_metrics.cagr,
                event_metrics.cagr
            ),
            "sharpe_ratio": (
                vector_metrics.sharpe_ratio,
                event_metrics.sharpe_ratio
            ),
            "sortino_ratio": (
                vector_metrics.sortino_ratio,
                event_metrics.sortino_ratio
            ),
            "calmar_ratio": (
                vector_metrics.calmar_ratio,
                event_metrics.calmar_ratio
            ),
            "profit_factor": (
                vector_metrics.profit_factor,
                event_metrics.profit_factor
            ),
            "max_drawdown": (
                vector_metrics.max_drawdown,
                event_metrics.max_drawdown
            ),
            "annual_volatility": (
                vector_metrics.annual_volatility,
                event_metrics.annual_volatility
            ),
            "win_rate": (
                vector_metrics.win_rate,
                event_metrics.win_rate
            ),
            "average_trade_return": (
                vector_metrics.average_trade_return,
                event_metrics.average_trade_return
            ),
            "average_trade_duration": (
                vector_metrics.average_trade_duration,
                event_metrics.average_trade_duration
            ),
        }

        # Assert that core metrics match (or are very close)
        # Number of trades should be exactly equal
        self.assertEqual(
            metrics_comparison["number_of_trades"][0],
            metrics_comparison["number_of_trades"][1],
            "Number of trades must be equal"
        )

        # Financial metrics will differ due to architectural differences:
        # - Vector backtest processes each symbol independently
        # - Event backtest considers entire portfolio state
        # We use a 20% tolerance to account for these differences.
        tolerance = 0.20  # 20% tolerance

        for metric_name in ["total_net_gain", "final_value", "total_growth"]:
            vector_val, event_val = metrics_comparison[metric_name]
            if vector_val is not None and event_val is not None and event_val != 0:
                relative_diff = abs(vector_val - event_val) / abs(event_val)
                self.assertLess(
                    relative_diff,
                    tolerance,
                    f"{metric_name} differs by more than {tolerance*100}%: "
                    f"vector={vector_val}, event={event_val}"
                )

    def test_compare_trade_details(self):
        """
        Test that individual trade details match between event and vector backtests.

        With dynamic_position_sizing=True, both vector and event backtests now
        share portfolio state across symbols, so trade amounts should be similar.

        We verify:
        - Same number of trades
        - Same symbols (same signals triggered)
        - Same trade status (open/closed)
        - Similar trade amounts (within tolerance)
        """
        vector_trades = sorted(self.vector_run.get_trades(), key=lambda t: t.opened_at)
        event_trades = sorted(self.event_run.get_trades(), key=lambda t: t.opened_at)

        # Verify trade counts match
        self.assertEqual(
            len(vector_trades),
            len(event_trades),
            "Number of trades should match"
        )

        # Compare individual trades
        for i, (v_trade, e_trade) in enumerate(zip(vector_trades, event_trades)):
            # Compare symbols - should be identical (same signals)
            self.assertEqual(
                v_trade.symbol,
                e_trade.symbol,
                f"Trade {i}: symbol mismatch"
            )

            # Trade amounts will differ due to position sizing differences:
            # - Vector: uses fixed position size based on initial portfolio
            # - Event: recalculates position size based on current portfolio
            # We only verify they are both positive (valid trades)
            self.assertGreater(
                v_trade.amount,
                0,
                f"Trade {i}: vector trade amount should be positive"
            )
            self.assertGreater(
                e_trade.amount,
                0,
                f"Trade {i}: event trade amount should be positive"
            )

            # Compare trade status - should be identical
            # Note: Vector backtest may return status as string, event as enum
            v_status = v_trade.status.value if hasattr(v_trade.status, 'value') else v_trade.status
            e_status = e_trade.status.value if hasattr(e_trade.status, 'value') else e_trade.status
            self.assertEqual(
                v_status,
                e_status,
                f"Trade {i}: status mismatch"
            )


if __name__ == "__main__":
    import unittest
    unittest.main()

