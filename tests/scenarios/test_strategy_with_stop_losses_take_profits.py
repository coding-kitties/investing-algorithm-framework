import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from unittest import TestCase

import pandas as pd

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, PositionSize, \
    RESOURCE_DIRECTORY, StopLossRule, TakeProfitRule, CSVOHLCVDataProvider


class FixedStopLossTakeProfitStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    data_sources = [
        DataSource(
            symbol="BTC/EUR",
            data_type=DataType.OHLCV,
            time_frame="2h",
            window_size=200,
            market="BITVAVO",
            identifier="BTC_EUR_OHLCV",
            pandas=True
        ),
    ]
    position_sizes = [
        PositionSize(
            symbol="BTC",
            percentage_of_portfolio=20.0
        ),
    ]
    take_profit_rules = [
        TakeProfitRule(
            symbol="BTC",
            percentage_threshold=10.0,
            trailing=False,
            sell_percentage=100
        ),
    ]
    stop_loss_rules = [
        StopLossRule(
            symbol="BTC",
            percentage_threshold=10.0,
            trailing=False,
            sell_percentage=100
        )
    ]

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        signals = {}

        for symbol in self.symbols:
            df = data["BTC_EUR_OHLCV"]
            signals[symbol] = pd.Series(
                [False] * len(df), index=df.index
            )

        return signals

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        signals = {}

        for symbol in self.symbols:
            df = data["BTC_EUR_OHLCV"]
            buy_signal = df['Close'] == 110
            signals[symbol] = buy_signal

        return signals


class Test(TestCase):

    def test_fixed_take_profit_rule_stop_loss_rule_triggers(self):
        """
        Test that fixed take profit rule is triggered correctly.

        Using synthetic market data from CSV:
        - OHLCV_BTC-EUR_BITVAVO_2h_2020-12-15-07-00_2021-01-31-23-00.csv
        - Entry prices: 110
        - Stop Loss at 99 (10% below entry)
        - Take Profit at 121 (10% above entry)
        - There are exactly two points where price crosses above
            121 or below 99

        Expected Behavior:
        1. Open two trades at entry price 110
        2. Price fall below 99 stop loss triggered
        3. Price rises above 121 take profit triggered
        4. Expected: 4 orders (2 buy, 1 TP sell, 1 SL sell)
        """
        resource_directory = str(Path(__file__).parent.parent / 'resources')
        config = {RESOURCE_DIRECTORY: resource_directory}
        app = create_app(name="FixedTPStrategy", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000
        )
        # Use a date range where we expect TP to trigger
        start_date = datetime(2020, 12, 29, tzinfo=timezone.utc)
        end_date = datetime(2021, 1, 31, 22, 0, 0, tzinfo=timezone.utc)
        strategy = FixedStopLossTakeProfitStrategy()
        csv_data_provider = CSVOHLCVDataProvider(
            storage_path=str(Path(__file__).parent.parent / 'resources' / 'test_data' / 'ohlcv' / 'OHLCV_BTC-EUR_BITVAVO_2h_2020-12-15-07-00_2021-01-31-23-00.csv'),
            symbol="BTC/EUR",
            time_frame="2h",
            market="BITVAVO",
            window_size=200
        )
        app.add_data_provider(
            data_provider=csv_data_provider, priority=1
        )
        backtest_date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        backtest = app.run_backtest(
            strategy=strategy,
            backtest_date_range=backtest_date_range
        )
        # Check that orders are created for buy and take profit sell
        run = backtest.get_backtest_run(backtest_date_range)
        self.assertEqual(4, len(run.get_orders()))
        self.assertEqual(2, len(run.get_trades()))
        # 2021-01-01T16:00:00.000+0000
        self.assertIsNotNone(
            len(
                run.get_orders(
                    created_at=datetime(
                        2021,
                        1,
                        1,
                        16,
                        0,
                        0,
                        tzinfo=timezone.utc
                    )
                )
            )
        )
        # 2021-01-04T14:00:00.000+0000
        self.assertIsNotNone(
            len(
                run.get_orders(
                    created_at=datetime(
                        2021,
                        1,
                        4,
                        14,
                        0,
                        0,
                        tzinfo=timezone.utc
                    )
                )
            )
        )

        # 2021-01-06T22:00:00.000+0000
        self.assertIsNotNone(
            len(
                run.get_orders(
                    created_at=datetime(
                        2021,
                        1,
                        6,
                        22,
                        0,
                        0,
                        tzinfo=timezone.utc
                    )
                )
            )
        )

        # 2021-01-03T20:00:00.000+0000
        self.assertIsNotNone(
            len(
                run.get_orders(
                    created_at=datetime(
                        2021,
                        1,
                        3,
                        20,
                        0,
                        0,
                        tzinfo=timezone.utc
                    )
                )
            )
        )
        # Check that trades are created for buy and take profit sell
        trades = run.get_trades()
        self.assertEqual(2, len(trades))

        # Check stop loss
        stop_losses = run.get_stop_losses()
        self.assertEqual(2, len(stop_losses))
        triggered_stop_losses = run.get_stop_losses(triggered=True)
        self.assertEqual(1, len(triggered_stop_losses))
        stop_loss = triggered_stop_losses[0]

        # Check if the stop loss was triggered at the expected time:
        # 2021-01-06T22:00:00.000+0000
        expected_date = datetime(
            2021,
            1,
            6,
            22,
            0,
            0,
            tzinfo=timezone.utc
        )
        self.assertEqual(expected_date, stop_loss.triggered_at)
        self.assertEqual(expected_date, stop_loss.updated_at)

        # Check take profit
        take_profits = run.get_take_profits()
        self.assertEqual(2, len(take_profits))
        take_profit = take_profits[0]
        triggered_take_profits = run.get_take_profits(triggered=True)
        self.assertEqual(1, len(triggered_take_profits))
        take_profit = triggered_take_profits[0]

        # Check if the take profit was triggered at the expected time
        # 2021-01-03T20:00:00.000+0000
        expected_date = datetime(
            2021,
            1,
            3,
            20,
            0,
            0,
            tzinfo=timezone.utc
        )
        self.assertEqual(expected_date, take_profit.triggered_at)
        self.assertEqual(expected_date, take_profit.updated_at)

    def test_trailing_stop_loss_take_profit_rule_triggers(self):
        """
        Test that fixed stop loss rule is triggered correctly.

        Using real market data from CSV:
        - Peak Price: ~34,300 EUR on 2021-01-07T18:00
        - Then price drops to 25,420 EUR on 2021-01-05T04:00 (price retraces)
        - Further drops to ~25,100 EUR on 2021-01-11T14:00

        Strategy Setup:
        Entry Price: ~31,000 EUR (buy signal triggers when Close > 24000)
        Stop Loss Threshold: 10% below entry = 31,000 * 0.90 = 27,900 EUR (FIXED)
        Take Profit Threshold: 10% above entry = 31,000 * 1.10 = 34,100 EUR (FIXED)

        Expected Behavior:
        1. Position opens at ~31,000
        2. Price hits 34,300 briefly but then retraces significantly to ~25,100
        3. Stop loss rule triggers when price drops to 27,900 or below and sells 50% of position
        4. Expected: 2+ orders (1 buy + 1 SL sell)
        """
        resource_directory = str(Path(__file__).parent.parent / 'resources')
        config = {RESOURCE_DIRECTORY: resource_directory}
        app = create_app(name="FixedSLStrategy", config=config)
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000
        )
        # Use a date range where we expect SL to trigger after peak
        start_date = datetime(2020, 12, 29, tzinfo=timezone.utc)
        end_date = datetime(2021, 1, 31, 22, 0, 0, tzinfo=timezone.utc)
        strategy = FixedStopLossTakeProfitStrategy()
        strategy.take_profit_rules = [
            TakeProfitRule(
                symbol="BTC",
                percentage_threshold=10.0,
                trailing=True,
                sell_percentage=100
            ),
        ]
        strategy.stop_loss_rules = [
            StopLossRule(
                symbol="BTC",
                percentage_threshold=10.0,
                trailing=False,
                sell_percentage=100
            )
        ]
        csv_data_provider = CSVOHLCVDataProvider(
            storage_path=str(Path(__file__).parent.parent / 'resources' / 'test_data' / 'ohlcv' / 'OHLCV_BTC-EUR_BITVAVO_2h_2020-12-14-07-00_2021-01-31-23-00.csv'),
            symbol="BTC/EUR",
            time_frame="2h",
            market="BITVAVO",
            window_size=200
        )
        app.add_data_provider(
            data_provider=csv_data_provider, priority=1
        )
        backtest_date_range = BacktestDateRange(
            start_date=start_date, end_date=end_date
        )
        backtest = app.run_backtest(
            strategy=strategy,
            backtest_date_range=backtest_date_range
        )
        # Check that orders are created for buy and stop loss sell
        run = backtest.get_backtest_run(backtest_date_range)
        self.assertEqual(4, len(run.get_orders()))
        self.assertEqual(2, len(run.get_trades()))
        # 2021-01-01T16:00:00.000+0000
        self.assertIsNotNone(
            len(
                run.get_orders(
                    created_at=datetime(
                        2021,
                        1,
                        1,
                        16,
                        0,
                        0,
                        tzinfo=timezone.utc
                    )
                )
            )
        )
        # 2021-01-04T14:00:00.000+0000
        self.assertIsNotNone(
            len(
                run.get_orders(
                    created_at=datetime(
                        2021,
                        1,
                        4,
                        14,
                        0,
                        0,
                        tzinfo=timezone.utc
                    )
                )
            )
        )

        # 2021-01-06T22:00:00.000+0000
        self.assertIsNotNone(
            len(
                run.get_orders(
                    created_at=datetime(
                        2021,
                        1,
                        6,
                        22,
                        0,
                        0,
                        tzinfo=timezone.utc
                    )
                )
            )
        )

        # 2021-01-03T20:00:00.000+0000
        self.assertIsNotNone(
            len(
                run.get_orders(
                    created_at=datetime(
                        2021,
                        1,
                        3,
                        20,
                        0,
                        0,
                        tzinfo=timezone.utc
                    )
                )
            )
        )
        # Check that trades are created for buy and take profit sell
        trades = run.get_trades()
        self.assertEqual(2, len(trades))

        # Check stop loss
        stop_losses = run.get_stop_losses()
        self.assertEqual(2, len(stop_losses))
        triggered_stop_losses = run.get_stop_losses(triggered=True)
        self.assertEqual(1, len(triggered_stop_losses))
        stop_loss = triggered_stop_losses[0]

        # Check if the stop loss was triggered at the expected time:
        # 2021-01-06T22:00:00.000+0000
        expected_date = datetime(
            2021,
            1,
            5,
            4,
            0,
            0,
            tzinfo=timezone.utc
        )
        self.assertEqual(expected_date, stop_loss.triggered_at)
        self.assertEqual(expected_date, stop_loss.updated_at)

        # Check take profit
        take_profits = run.get_take_profits()
        self.assertEqual(2, len(take_profits))
        take_profit = take_profits[0]
        triggered_take_profits = run.get_take_profits(triggered=True)
        self.assertEqual(1, len(triggered_take_profits))
        take_profit = triggered_take_profits[0]

        # Check if the take profit was triggered at the expected time
        # 2021-01-03T20:00:00.000+0000
        expected_date = datetime(
            2021,
            1,
            2,
            12,
            0,
            0,
            tzinfo=timezone.utc
        )
        self.assertEqual(expected_date, take_profit.triggered_at)
        self.assertEqual(expected_date, take_profit.updated_at)
