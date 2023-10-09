import os
from datetime import datetime

from investing_algorithm_framework.domain import OperationalException, \
    BacktestProfile, TradingTimeFrame


class BackTestService:

    def __init__(self, market_data_service, resource_directory):
        self._market_data_service = market_data_service
        self._resource_directory = None

    @property
    def resource_directory(self):
        return self._resource_directory

    @resource_directory.setter
    def resource_directory(self, resource_directory):
        self._resource_directory = resource_directory

    def backtest(self, algorithm, start_date = None, end_date = None):
        backtest_profiles = []

        for strategy in algorithm.strategies:
            backtest_profile = BacktestProfile(
                strategy_id=strategy.worker_id,
                time_unit=strategy.time_unit,
                interval=strategy.interval
            )

            if start_date is None:
                backtest_profile.backtest_start_date = \
                    self._create_start_date_backtest(strategy)
            else:
                backtest_profile.backtest_start_date = start_date

            if end_date is None:
                backtest_profile.backtest_end_date = datetime.utcnow()
            else:
                backtest_profile.backtest_end_date = end_date

            backtest_profile.backtest_start_date_data = \
                self._create_start_date_backtest_data(backtest_profile)

            backtest_profiles.append(backtest_profile)
            self.run_backtest(backtest_profile, strategy, algorithm)
            self.evaluate(backtest_profile, algorithm)

    def run_backtest(self, backtest_profile, strategy, algorithm):
        backtest_profile.backtest_index_date = \
            backtest_profile.backtest_start_date

        # Create (if not exists) the dataset for the backtest
        self._create_test_data(backtest_profile)

        # Keep running the backtest while the index date has not surpassed the
        # backtest end date
        while backtest_profile.backtest_index_date <= \
                backtest_profile.backtest_end_date:

            # Retrieve the data slice for the index date
            data = self._get_data(backtest_profile)
            strategy.run_strategy(data, algorithm)

            # Generate next index date
            backtest_profile.backtest_index_date = \
                self._create_index_date_backtest(backtest_profile)

    def evaluate(self, backtest_profile, algorithm):
        pass

    def _create_test_data(self, backtest_profile):

        for trade_profile in trade_profiles:
            time_frame = trade_profile.time_frame
            in_between_date, end_date = time_frame.create_time_frame(datetime.utcnow())
            start_date, in_between_date = time_frame.create_time_frame(in_between_date)

            for target_symbol in trade_profile.target_symbols:

                if not self._test_data_csv_file_exists(start_date, end_date, target_symbol):
                    file_path = self._create_test_data_csv_files(
                        start_date, end_date, target_symbol
                    )
                    data = self._market_data_service.get_market_data(
                        trade_profile.market,
                        trade_profile.trading_symbol,
                        start_date,
                        end_date
                    )
                    self._write_test_data_to_csv(file_path, data)

    def _test_data_csv_file_exists(self, start_date, end_date, target_symbol):
        if self.resource_directory is None:
            raise OperationalException(
                "The resource directory is not configured. Please configure "
                "the resource directory before backtesting."
            )

        trading_test_data_path = os.path.join(
            self.resource_directory,
            f"test_data_{target_symbol}_{start_date}_{end_date}.csv"
        )

        return os.path.exists(trading_test_data_path)

    def _create_test_data_csv_files(self, start_date, end_date, target_symbol):

        if self.resource_directory is None:
            raise OperationalException(
                "The resource directory is not configured. Please configure "
                "the resource directory before backtesting."
            )

        trading_test_data_path = os.path.join(
            self.resource_directory,
            f"test_data_{target_symbol}_{start_date}_{end_date}.csv"
        )

        if not os.path.exists(trading_test_data_path):
            with open(trading_test_data_path, 'w') as _:
                pass

    def _write_test_data_to_csv(self, file_path, data):
        pass

    def create_backtest_profile(self, strategy, start_date, end_date):
        backtest_profile = BacktestProfile(
            strategy_id=strategy.worker_id,
            interval=strategy.interval,
            time_unit=strategy.time_unit,
        )
        backtest_profile.

    def _create_start_date_backtest(self, strategy):
        pass

    def _create_start_date_backtest_data(self, backtest_profile):
        trading_time_frame = backtest_profile.trading_time_frame

        if TradingTimeFrame.create_start_date(backtest_profile.backtest_start_date, )


    def _create_index_date_backtest(self, backtest_profile):
        time_unit = backtest_profile.time_unit
        interval = backtest_profile.interval

        if backtest_profile.backtest_index_date:
           return time_unit.create_date(
                backtest_profile.backtest_index_date, interval
            )

        return time_unit.create_date(
            backtest_profile.backtest_start_date, interval
        )

    def _get_data(self, backtest_profile):
        pass
