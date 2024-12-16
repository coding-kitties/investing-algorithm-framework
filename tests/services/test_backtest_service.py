import os

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY, BacktestDateRange
from investing_algorithm_framework.services import BacktestService
from tests.resources import TestBase, MarketServiceStub


class TestMarketDataSourceService(TestBase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.realpath(__file__),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )
        self.backtest_report_dir = os.path.join(
            self.resource_dir,
            "backtest_reports_for_testing"
        )
        self.app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(
            MarketServiceStub(self.app.container.market_credential_service())
        )

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
            os.path.join(self.resource_dir, "config.json")
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

    def test_get_report(self):
        backtest_service = self.app.container.backtest_service()
        date_range = BacktestDateRange(
            start_date="2021-12-21 00:00",
            end_date="2022-06-20 00:00"
        )
        report = backtest_service.get_report(
            algorithm_name="test", 
            backtest_date_range=date_range, directory=self.backtest_report_dir
        )
        self.assertIsNotNone(report)
