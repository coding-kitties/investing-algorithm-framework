import os
from datetime import datetime, timedelta

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    TradingStrategy, PortfolioConfiguration, TimeUnit
from investing_algorithm_framework.domain import DATETIME_FORMAT
from tests.resources import TestBase


class TestStrategy(TradingStrategy):
    strategy_id = "test_strategy"
    time_unit = TimeUnit.MINUTE
    interval = 1

    def run_strategy(self, algorithm, market_data):
        pass


class Test(TestBase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.join(
                            os.path.realpath(__file__),
                            os.pardir
                        ),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )

    def test_report_csv_creation(self):
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
        )
        app.add_strategy(TestStrategy())
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        report = app.backtest(
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow(),
        )

        # Check if the backtest report exists
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.resource_dir,
                    "backtest_reports",
                    f"report_{report.identifier}"
                    f"_{report.created_at.strftime(DATETIME_FORMAT)}.csv"
                )
            )
        )

    def test_report_csv_creation_without_strategy_identifier(self):
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
        )
        strategy = TestStrategy()
        strategy.strategy_id = None
        app.add_strategy(strategy)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="bitvavo",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        report = app.backtest(
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow(),
        )

        # Check if the backtest report exists
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.resource_dir,
                    "backtest_reports",
                    f"report"
                    f"_{report.created_at.strftime(DATETIME_FORMAT)}.csv"
                )
            )
        )
