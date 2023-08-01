import os
from investing_algorithm_framework.domain import RESOURCE_DIRECTORY, \
    OperationalException


class BackTestService:

    def __init__(self, market_data_service):
        self._market_data_service = market_data_service

    def backtest(self, start_date, end_date, strategies, config):
        self._create_test_data_csv(
            start_date,
            end_date,
            [strategy.trade_profile for strategy in strategies],
            config
        )
        self._create_test_data(
            start_date,
            end_date,
            [strategy.trade_profile for strategy in strategies]
        )

    def _create_test_data(self, start_date, end_date, trade_profiles):

        for trade_profile in trade_profiles:
            data = self._market_data_service.get_market_data(
                trade_profile.market,
                trade_profile.trading_symbol,
                start_date,
                end_date
            )

    def _create_test_data_csv(self, start_date, end_date, trade_profiles, config):
        print(config)

        if RESOURCE_DIRECTORY not in config \
                or config.get(RESOURCE_DIRECTORY) is None:
            raise OperationalException(
                "The resource directory is not configured. Please configure "
                "the resource directory before backtesting."
            )
        trading_test_data_path = os.path.join(
            config[RESOURCE_DIRECTORY],
            "ohclv_trading_test_data.csv"
        )

        if not os.path.exists(trading_test_data_path):
            with open(trading_test_data_path, 'w') as file:
                pass
