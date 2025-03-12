import os

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, BacktestDateRange
from tests.resources import TestBase


class TestBacktestService(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="USDT"
        )
    ]
    backtest_report_dir = os.path.join(
        TestBase.resource_directory,
        "backtest_reports_for_testing"
    )
    resource_directory = os.path.join(
        os.path.join(
            os.path.join(
                os.path.realpath(__file__),
                os.pardir
            ),
            os.pardir
        ),
        "resources"
    )
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="test",
            secret_key="test"
        )
    ]
    initialize = False

    def test_is_backtest_report(self):
        backtest_service = self.app.container.backtest_service()
        path = os.path.join(
            self.backtest_report_dir,
            "report_test_backtest-start-date_" +
            "2021-12-21:00:00_backtest-end-date_" +
            "2022-06-20:00:00_created-at_2024-04-25:13:52.json"
        )
        self.assertTrue(backtest_service._is_backtest_report(path))
        self.assertFalse(backtest_service._is_backtest_report(
            os.path.join(self.resource_directory, "config.json")
        ))
        path = os.path.join(
            self.backtest_report_dir,
            "report_test_backtest-start-date_2024-07-03:08:45_backtest-end-date_" +
            "2024-07-04:08:45_created-at_2024-07-04:08:45.json"
        )
        self.assertTrue(backtest_service._is_backtest_report(path))
        path = os.path.join(
            self.backtest_report_dir,
            "report_backtest-start-date_2024-07-03:08:45_backtest-end-date_" +
            "2024-07-04:08:45_created-at_2024-07-04:08:45.json"
        )
        self.assertFalse(backtest_service._is_backtest_report(path))

    # def test_get_report(self):
    #     backtest_service = self.app.container.backtest_service()
    #     date_range = BacktestDateRange(
    #         start_date="2021-12-21 00:00",
    #         end_date="2022-06-20 00:00"
    #     )
    #     report = backtest_service.get_report(
    #         algorithm_name="test",
    #         backtest_date_range=date_range, directory=self.backtest_report_dir
    #     )
    #     self.assertIsNotNone(report)
