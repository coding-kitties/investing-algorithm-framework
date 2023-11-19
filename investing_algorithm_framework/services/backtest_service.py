import csv
import os
from datetime import datetime, timedelta
from math import floor

from investing_algorithm_framework.domain import BacktestProfile, \
    DATETIME_FORMAT_BACKTESTING, DATETIME_FORMAT, BACKTESTING_INDEX_DATETIME, \
    StrategyProfile, OperationalException, Ticker, BacktestPosition, \
    parse_string_to_decimal


class BackTestService:

    def __init__(
        self,
        market_data_service,
        order_service,
        portfolio_repository,
        position_repository,
        performance_service,
    ):
        self._market_data_service = market_data_service
        self._resource_directory = None
        self._order_service = order_service
        self._portfolio_repository = portfolio_repository
        self._data_index = {"OHCLV": {}, "TICKER": {}}
        self._performance_service = performance_service
        self._position_repository = position_repository

    @property
    def resource_directory(self):
        return self._resource_directory

    @resource_directory.setter
    def resource_directory(self, resource_directory):
        self._resource_directory = resource_directory

    def create_backtest_data_file(
        self,
        backtest_profile: BacktestProfile,
        strategy_profile: StrategyProfile,
        symbol
    ):
        data_dir = os.path.join(self.resource_directory, "backtest_data")

        if not os.path.isdir(data_dir):
            os.mkdir(data_dir)

        symbol_string = symbol.replace("/", "-")
        time_frame_string = strategy_profile.trading_time_frame\
            .value.replace("_", "")

        return os.path.join(
            self.resource_directory,
            os.path.join(
                "backtest_data",
                f"OHCLV_"
                f"{symbol_string}_"
                f"{time_frame_string}_"
                f"{strategy_profile.backtest_start_date_data.strftime(DATETIME_FORMAT_BACKTESTING)}_"
                f"{backtest_profile.backtest_end_date.strftime(DATETIME_FORMAT_BACKTESTING)}.csv"
            )
        )

    def backtest(self, algorithm, start_date=None, end_date=None):
        strategy_profiles = []

        if start_date is None:
            start_date = datetime.utcnow()

        for strategy in algorithm.strategies:
            strategy_profiles.append(
                self.create_strategy_profile(strategy, start_date)
            )

        backtest_profile = self.create_backtest_profile(
            start_date=start_date, end_date=end_date
        )

        for strategy_profile in strategy_profiles:
            self._create_test_data(backtest_profile, strategy_profile)
            self.run_backtest_for_profile(
                backtest_profile,
                strategy_profile,
                algorithm,
                algorithm.get_strategy(strategy_profile.strategy_id)
            )

        portfolio = self._portfolio_repository.find({"identifier": "backtest"})
        backtest_profile.percentage_negative_trades = self._performance_service \
            .get_percentage_negative_trades(portfolio.id)
        backtest_profile.percentage_positive_trades = self._performance_service \
            .get_percentage_positive_trades(portfolio.id)
        backtest_profile.number_of_trades_closed = self._performance_service \
            .get_number_of_trades_closed(portfolio.id)
        backtest_profile.number_of_trades_open = self._performance_service \
            .get_number_of_trades_open(portfolio.id)
        backtest_profile.total_cost = \
            parse_string_to_decimal(portfolio.total_cost)
        backtest_profile.total_net_gain = \
            parse_string_to_decimal(portfolio.total_net_gain)
        backtest_profile.total_net_gain_percentage = self._performance_service \
            .get_total_net_gain_percentage_of_backtest(
                portfolio.id, backtest_profile
            )
        positions = self._position_repository.get_all({
            "portfolio": portfolio.id
        })
        tickers = {}

        for position in positions:

            if position.symbol != portfolio.trading_symbol:
                tickers[position.symbol] = self.get_ticker(
                    f"{position.symbol}/{portfolio.trading_symbol}",
                    backtest_profile.backtest_end_date
                )

        backtest_profile.growth_rate = self._performance_service\
            .get_growth_rate_of_backtest(
                portfolio.id, tickers, backtest_profile
            )
        backtest_profile.growth = self._performance_service\
            .get_growth_of_backtest(portfolio.id, tickers, backtest_profile)
        backtest_profile.total_value = self._performance_service\
            .get_total_value(portfolio.id, tickers, backtest_profile)

        positions = self._position_repository.get_all({
            "portfolio": portfolio.id
        })
        backtest_positions = []

        for position in positions:

            if position.symbol == portfolio.trading_symbol:
                backtest_position = BacktestPosition(
                    position, trading_symbol=True
                )
                backtest_position.price = 1
            else:
                backtest_position = BacktestPosition(position)
                ticker = self.get_ticker(
                    f"{position.symbol}/{portfolio.trading_symbol}",
                    backtest_profile.backtest_end_date
                )
                backtest_position.price = ticker.price
            backtest_positions.append(backtest_position)
        backtest_profile.positions = backtest_positions
        return backtest_profile

    def run_backtest_for_profile(
        self,
        backtest_profile: BacktestProfile,
        strategy_profile: StrategyProfile,
        algorithm,
        strategy
    ):
        amount_of_runs_per_day = strategy_profile.get_runs_per_day()
        days_run_without_execution = 0

        while backtest_profile.backtest_index_date \
                < backtest_profile.backtest_end_date:
            algorithm.config[BACKTESTING_INDEX_DATETIME] \
                = backtest_profile.backtest_index_date

            if amount_of_runs_per_day > 0:
                for _ in range(floor(amount_of_runs_per_day)):
                    data = {"ohlcvs": {}}

                    for symbol in strategy_profile.symbols:
                        data["ohlcvs"][symbol] = \
                            self.get_ohclv(
                                symbol,
                                strategy_profile.backtest_data_index_date,
                                backtest_profile.backtest_index_date
                            )

                    self._order_service.check_pending_orders(data["ohlcvs"])
                    strategy.run_strategy(data, algorithm)
            else:

                if (days_run_without_execution % amount_of_runs_per_day) \
                        < amount_of_runs_per_day:
                    data = {"ohlcvs": {}}

                    for symbol in backtest_profile.symbols:
                        data["ohlcvs"][symbol] = \
                            self.get_ohclv(
                                symbol,
                                strategy_profile.backtest_data_index_date,
                                backtest_profile.backtest_index_date
                            )

                    self._order_service.check_pending_orders()
                    strategy.run_strategy(data, algorithm)
                    days_run_without_execution = 0
                else:
                    days_run_without_execution += 1

            backtest_profile.backtest_index_date = \
                backtest_profile.backtest_index_date + timedelta(days=1)
            strategy_profile.backtest_data_index_date = \
                strategy_profile.backtest_data_index_date + timedelta(days=1)
            backtest_profile.number_of_days += 1
            backtest_profile.number_of_runs += 1

        backtest_profile.number_of_orders += len(algorithm.get_orders())
        backtest_profile.number_of_positions += len(algorithm.get_positions())

    def _create_test_data(
        self,
        backtest_profile: BacktestProfile,
        strategy_profile: StrategyProfile
    ):
        data = self._market_data_service\
            .get_data_for_backtest(
                backtest_profile.backtest_end_date, strategy_profile
            )

        for symbol in strategy_profile.symbols:
            data_file = self.create_backtest_data_file(
                backtest_profile, strategy_profile, symbol
            )

            if not os.path.exists(data_file):
                # Create the source data file if it does not exist
                with open(data_file, "w") as file:
                    column_headers = [
                        "Datetime", "Open", "High", "low", "Close", "Volume"
                    ]
                    writer = csv.writer(file)
                    writer.writerow(column_headers)
                    symbol_data = data["ohlcvs"][symbol]
                    rows = symbol_data.to_array()
                    writer.writerows(rows)

            self.index_data()

    def create_backtest_profile(self, start_date, end_date):
        portfolio = self._portfolio_repository.find(
            {"identifier": "backtest"}
        )
        return BacktestProfile(
            backtest_index_date=start_date,
            backtest_start_date=start_date,
            backtest_end_date=end_date,
            initial_unallocated=portfolio.get_unallocated(),
            trading_symbol=portfolio.trading_symbol,
        )

    def create_strategy_profile(self, strategy, backtest_start_date):
        strategy_profile = StrategyProfile(
            strategy_id=strategy.worker_id,
            interval=strategy.interval,
            time_unit=strategy.time_unit,
            symbols=strategy.symbols,
            market=strategy.market,
            trading_time_frame=strategy.trading_time_frame,
            trading_time_frame_start_date=strategy
            .trading_time_frame_start_date,
        )

        # Calculating the backtest data start date
        difference = datetime.utcnow() - strategy_profile \
            .trading_time_frame_start_date

        total_minutes = 0

        if difference.days > 0:
            total_minutes += difference.days * 24 * 60
        if difference.seconds > 0:
            total_minutes += difference.seconds / 60

        strategy_profile.backtest_start_date_data = \
            backtest_start_date - timedelta(minutes=total_minutes)
        strategy_profile.backtest_data_index_date = \
            strategy_profile.backtest_start_date_data
        return strategy_profile

    def _get_data(
        self,
        symbol,
        backtest_profile: BacktestProfile,
        strategy_profile: StrategyProfile
    ):
        matching_rows = []
        data_file = self.create_backtest_data_file(
            backtest_profile, strategy_profile, symbol
        )

        with open(data_file, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header row

            for row in reader:
                row_date = datetime.strptime(row[0], DATETIME_FORMAT)

                if strategy_profile.backtest_data_index_date \
                        <= row_date <= backtest_profile.backtest_index_date:
                    matching_rows.append(row)

        return matching_rows

    def get_ohclv(self, symbol, start_date, end_date):
        matching_rows = []
        matching_file = None
        symbol_string = symbol.replace("/", "-")
        self._data_index["OHCLV"][symbol_string]["files"].sort()

        for file in self._data_index["OHCLV"][symbol_string]["files"]:
            start_date_file = datetime.strptime(
                file.split("_")[3], DATETIME_FORMAT_BACKTESTING
            )
            end_date_file = datetime.strptime(
                file.split("_")[4].split(".")[0], DATETIME_FORMAT_BACKTESTING
            )

            if start_date_file <= start_date and end_date <= end_date_file:
                matching_file = file

        if matching_file is None:
            raise OperationalException(
                f"No backtest data found for symbol "
                f"{symbol} between {start_date} and {end_date}"
            )

        with open(os.path.join(self.resource_directory, "backtest_data", matching_file), 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header row

            for row in reader:
                row_date = datetime.strptime(row[0], DATETIME_FORMAT)

                if start_date <= row_date <= end_date:
                    matching_rows.append(row)

        return matching_rows

    def get_ticker(self, symbol, date_time):
        matching_file = None
        match = None
        symbol_string = symbol.replace("/", "-")
        self._data_index["OHCLV"][symbol_string]["files"].sort()

        for file in self._data_index["OHCLV"][symbol_string]["files"]:
            start_date_file = datetime.strptime(
                file.split("_")[3], DATETIME_FORMAT_BACKTESTING
            )
            end_date_file = datetime.strptime(
                file.split("_")[4].split(".")[0], DATETIME_FORMAT_BACKTESTING
            )

            if start_date_file <= date_time <= end_date_file:
                matching_file = file

        if matching_file is None:
            raise OperationalException(
                f"No backtest data found for symbol {symbol} on {date_time}"
            )

        with open(os.path.join(self.resource_directory, "backtest_data", matching_file), 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header row
            last_row = None

            for row in reader:
                row_date = datetime.strptime(row[0], DATETIME_FORMAT)

                if row_date > date_time:
                    match = last_row
                    break

                last_row = row

        if last_row is not None and match is None:
            match = last_row

        if match is None:
            raise OperationalException(
                f"No backtest data found for symbol {symbol} on {date_time}"
            )

        return Ticker.from_dict({
            "symbol": symbol,
            "price": match[4],
            "ask_price": match[4],
            "ask_volume": match[4],
            "bid_price": match[4],
            "bid_volume": match[5],
            "high_price": match[2],
            "low_price": match[3]
        })

    def index_data(self):
        data_dir = os.path.join(self.resource_directory, "backtest_data")

        for file in os.listdir(data_dir):
            data_type = file.split("_")[0]
            symbol = file.split("_")[1]
            self._data_index[data_type][symbol] = {}

            if "files" in self._data_index[data_type]:
                self._data_index[data_type][symbol]["files"].append(file)
            else:
                self._data_index[data_type][symbol]["files"] = [file]

    def _get_last_row(self, file):
        with open(file, 'r') as csv_file:
            # Create a CSV reader object
            csv_reader = csv.reader(csv_file)

            # Convert the CSV reader object to a list and get the last row
            rows = list(csv_reader)
            last_row = rows[-1]
            return last_row
