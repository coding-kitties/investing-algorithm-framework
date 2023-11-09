import csv
import os
from datetime import datetime, timedelta
from math import floor

from investing_algorithm_framework.domain import OperationalException, \
    BacktestProfile, TradingTimeFrame


class BackTestService:

    def __init__(self, market_data_service):
        self._market_data_service = market_data_service
        self._resource_directory = None

    @property
    def resource_directory(self):
        return self._resource_directory

    @resource_directory.setter
    def resource_directory(self, resource_directory):
        self._resource_directory = resource_directory

    def backtest(self, algorithm, start_date=None, end_date=None):
        backtest_profiles = []

        print(f"Start date: {start_date}")
        print(f"End date: {end_date}")
        for strategy in algorithm.strategies:
            backtest_profile = self.create_backtest_profile(
                strategy=strategy, start_date=start_date, end_date=end_date
            )
            backtest_profile.backtest_start_date_data = \
                self._create_start_date_backtest_data(backtest_profile)

            if start_date is None:
                start_date = datetime.utcnow()

            difference = datetime.utcnow() - backtest_profile\
                .trading_time_frame_start_date

            total_minutes = 0

            if difference.days > 0:
                total_minutes += difference.days * 24 * 60
            if difference.seconds > 0:
                total_minutes += difference.seconds / 60

            backtest_profile.backtest_start_date_data = \
                backtest_profile.backtest_start_date - \
                timedelta(minutes=total_minutes)

            backtest_profiles.append(backtest_profile)
        #
        # for backtest_profile in backtest_profiles:
        #     self._create_test_data(backtest_profile)

        for backtest_profile in backtest_profiles:
            self.run_backtest_for_profile(
                start_date,
                backtest_profile,
                algorithm,
                algorithm.get_strategy(backtest_profile.strategy_id)
            )

        return backtest_profiles

    def run_backtest_for_profile(self, start_date, backtest_profile, algorithm, strategy):
        amount_of_runs_per_day = backtest_profile.get_runs_per_day()
        days_run_without_execution = 0

        print(backtest_profile.backtest_index_date)
        print(backtest_profile.backtest_end_date)

        while backtest_profile.backtest_index_date \
                < backtest_profile.backtest_end_date:

            if amount_of_runs_per_day > 0:
                for _ in range(floor(amount_of_runs_per_day)):
                    data = {}
                    # data = self._get_data(backtest_profile)
                    strategy.run_strategy(data, algorithm)
            else:

                if (days_run_without_execution % amount_of_runs_per_day) \
                        < amount_of_runs_per_day:
                    # data = self._get_data(backtest_profile)
                    data = {}
                    strategy.run_strategy(data, algorithm)
                    days_run_without_execution = 0
                else:
                    days_run_without_execution += 1

            backtest_profile.backtest_index_date = \
                backtest_profile.backtest_index_date + timedelta(days=1)
            backtest_profile.number_of_days += 1
            backtest_profile.number_of_runs += 1

        backtest_profile.number_of_orders += len(algorithm.get_orders())
        backtest_profile.number_of_positions += len(algorithm.get_positions())

    def evaluate(self, backtest_profile, algorithm):
        runs_per_day = backtest_profile.get_runs_per_day()
        amount_of_days = (backtest_profile.backtest_end_date - backtest_profile.backtest_start_date).days
        total_runs = runs_per_day * amount_of_days

        if total_runs == 0:
            return

    def _create_test_data(self, backtest_profile):
        data = self._market_data_service.get_data_for_backtest(backtest_profile)

        for symbol in backtest_profile.symbols:
            symbol_string = symbol.replace("/", "-")
            source_data_path = os.path.join(
                self.resource_directory,
                f"test_data_{symbol_string}_"
                f"{backtest_profile.trading_time_frame.value}_"
                f"{backtest_profile.backtest_start_date_data.strftime('%Y%m%dT%H%M')}_"
                f"{backtest_profile.backtest_end_date.strftime('%Y%m%dT%H%M')}.csv"
            )

            if not os.path.exists(source_data_path):
                # Create the source data file if it does not exist
                with open(source_data_path, "w") as file:
                    column_headers = ["Datetime", "Open", "High", "low", "Close", "Volume"]
                    writer = csv.writer(file)
                    writer.writerow(column_headers)
                    symbol_data = data["ohlcvs"][symbol]
                    rows = symbol_data.to_array()
                    writer.writerows(rows)

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
            symbols=strategy.symbols,
            market=strategy.market,
            backtest_index_date=start_date,
            backtest_start_date=start_date,
            backtest_end_date=end_date,
        )

        if start_date is None:
            backtest_profile.backtest_start_date = \
                self._create_start_date_backtest(strategy)
        else:
            backtest_profile.backtest_start_date = start_date

        backtest_profile.trading_time_frame = strategy.trading_time_frame
        backtest_profile.trading_time_frame_start_date = \
            strategy.trading_time_frame_start_date
        return backtest_profile

    def _create_start_date_backtest_data(self, backtest_profile):
        trading_time_frame = backtest_profile.trading_time_frame

        if TradingTimeFrame.ONE_MINUTE.equals(trading_time_frame):
            data_start_date = backtest_profile.trading_time_frame_start_date \
                              - timedelta(minutes=1)
        elif TradingTimeFrame.FIFTEEN_MINUTE.equals(trading_time_frame):
            data_start_date = backtest_profile.trading_time_frame_start_date \
                              - timedelta(minutes=15)
        elif TradingTimeFrame.ONE_HOUR.equals(trading_time_frame):
            data_start_date = backtest_profile.trading_time_frame_start_date \
                              - timedelta(hours=1)
        elif TradingTimeFrame.ONE_DAY.equals(trading_time_frame):
            data_start_date = backtest_profile.trading_time_frame_start_date \
                              - timedelta(days=1)
        elif TradingTimeFrame.ONE_MONTH.equals(trading_time_frame):
            data_start_date = backtest_profile.trading_time_frame_start_date \
                              - timedelta(weeks=4)
        else:
            data_start_date = backtest_profile.trading_time_frame_start_date \
                              - timedelta(days=365)

        return data_start_date

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
