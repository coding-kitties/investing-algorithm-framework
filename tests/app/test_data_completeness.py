import os
from datetime import datetime, timezone
from unittest.mock import patch

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, TradingStrategy, DataSource, BacktestDateRange, \
    Schedule, TimeUnit
from investing_algorithm_framework.domain.exceptions import DataError
from tests.resources import TestBase

class TestStrategy(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.DAY)
    data_sources = [
        DataSource(
            data_type="OHLCV",
            identifier="sol_1d_ohlcv_data",
            time_frame="1d",
            warmup_window=200,
            symbol="SOL/EUR",
            market="BITVAVO",
        )
    ]


class TestStrategyIncompleteData(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.DAY)
    data_sources = [
        DataSource(
            data_type="OHLCV",
            identifier="sol_1d_incomplete_ohlcv_data",
            time_frame="1d",
            warmup_window=200,
            symbol="SOL/EUR",
            market="BITVAVO",
            data_provider_identifier="BITVAVO"
        )
    ]


class TestConfig(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    external_balances = {
        "EUR": 1000,
    }

    def test_data_completeness(self):
        """Test that check_data_completeness passes when data is complete."""
        strategy = TestStrategy()

        self.app.check_data_completeness(
            strategies=[strategy],
            backtest_date_range=BacktestDateRange(
                start_date=datetime(
                    2021, 8, 3, tzinfo=timezone.utc
                ),
                end_date=datetime(
                    2021, 8, 20, tzinfo=timezone.utc
                )
            )
        )

    def test_data_completeness_incomplete_data(self):
        """
        Test that check_data_completeness raises DataError when data is
        incomplete. This test mocks the data provider to return incomplete
        data with gaps.
        """
        strategy = TestStrategyIncompleteData()

        data_complete, completeness_info = self.app.check_data_completeness(
                strategies=[strategy],
                backtest_date_range=BacktestDateRange(
                    start_date=datetime(
                        2021, 6, 15, tzinfo=timezone.utc
                    ),
                    end_date=datetime(
                        2024, 1, 1, tzinfo=timezone.utc
                    )
                )
            )

        self.assertFalse(data_complete)
        self.assertIn(
            "sol_1d_incomplete_ohlcv_data", completeness_info
        )
