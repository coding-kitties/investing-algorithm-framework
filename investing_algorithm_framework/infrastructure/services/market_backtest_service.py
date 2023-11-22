import csv
import logging
import os
from datetime import datetime

from investing_algorithm_framework.domain import \
    DATETIME_FORMAT_BACKTESTING, DATETIME_FORMAT, BacktestProfile, \
    StrategyProfile, TradingDataType, BACKTESTING_INDEX_DATETIME
from investing_algorithm_framework.domain import OperationalException
from .market_service import MarketService

logger = logging.getLogger("investing_algorithm_framework")


class MarketBacktestService(MarketService):
    _data_index = None

    def __init__(self, backtest_data_directory, configuration_service):
        self._backtest_data_directory = backtest_data_directory
        self._configuration_service = configuration_service

    def initialize(self, portfolio_configuration):
        self._market = portfolio_configuration.market

    def write_ohlcv_to_file(self, data_file, data):

        if not os.path.isdir(self._backtest_data_directory):
            os.mkdir(self._backtest_data_directory)

        # Create the source data file if it does not exist
        with open(data_file, "w") as file:
            column_headers = [
                "Datetime", "Open", "High", "Low", "Close", "Volume"
            ]
            writer = csv.writer(file)
            writer.writerow(column_headers)
            rows = data
            writer.writerows(rows)

    def write_tickers_to_file(self, data_file, data):

        # Create the source data file if it does not exist
        with open(data_file, "w") as file:
            column_headers = [
                "Datetime", "Ask", "High", "Low", "previousClose",
            ]
            writer = csv.writer(file)
            writer.writerow(column_headers)
            rows = []

            for row in data:
                rows.append([
                    row[0],
                    row[4],
                    row[2],
                    row[3],
                    row[4],
                ])
            writer.writerows(rows)

    def _backtest_data_exists(
        self,
        backtest_profile: BacktestProfile,
        strategy_profile: StrategyProfile,
        trading_data_type: TradingDataType,
        symbol
    ):
        return os.path.exists(self.create_backtest_data_file_path(
            backtest_profile, strategy_profile, symbol, trading_data_type
        ))

    def create_backtest_data(
        self,
        backtest_profile: BacktestProfile,
        strategy_profile: StrategyProfile,
    ):

        for symbol in strategy_profile.symbols:

            if strategy_profile.trading_data_types is not None:

                if TradingDataType.OHLCV in strategy_profile\
                        .trading_data_types:

                    if not self._backtest_data_exists(
                        backtest_profile,
                        strategy_profile,
                        TradingDataType.OHLCV,
                        symbol
                    ):
                        self.market = strategy_profile.market
                        data = super().get_ohclv(
                            symbol,
                            time_frame=strategy_profile.trading_time_frame,
                            from_timestamp=strategy_profile
                            .backtest_start_date_data,
                            to_timestamp=backtest_profile.backtest_end_date
                        )
                        file = self.create_backtest_data_file_path(
                            backtest_profile,
                            strategy_profile,
                            symbol,
                            TradingDataType.OHLCV
                        )
                        self.write_ohlcv_to_file(file, data)

                if TradingDataType.TICKER in strategy_profile\
                        .trading_data_types:

                    if not self._backtest_data_exists(
                            backtest_profile,
                            strategy_profile,
                            TradingDataType.TICKER,
                            symbol
                    ):
                        self.market = strategy_profile.market
                        data = super().get_ohclv(
                            symbol,
                            time_frame=strategy_profile.trading_time_frame,
                            from_timestamp=strategy_profile
                            .backtest_start_date_data,
                            to_timestamp=backtest_profile.backtest_end_date
                        )
                        file = self.create_backtest_data_file_path(
                            backtest_profile,
                            strategy_profile,
                            symbol,
                            TradingDataType.TICKER
                        )
                        self.write_tickers_to_file(file, data)

    def create_backtest_data_file_path(
        self,
        backtest_profile: BacktestProfile,
        strategy_profile: StrategyProfile,
        symbol,
        trading_data_type: TradingDataType
    ):
        symbol_string = symbol.replace("/", "-")
        time_frame_string = strategy_profile.trading_time_frame \
            .value.replace("_", "")
        return os.path.join(
            self._backtest_data_directory,
            os.path.join(
                f"{trading_data_type.value}_"
                f"{symbol_string}_"
                f"{time_frame_string}_"
                f"{strategy_profile.backtest_start_date_data.strftime(DATETIME_FORMAT_BACKTESTING)}_"
                f"{backtest_profile.backtest_end_date.strftime(DATETIME_FORMAT_BACKTESTING)}.csv"
            )
        )

    def create_backtest_data_file(
        self,
        backtest_profile: BacktestProfile,
        strategy_profile: StrategyProfile,
        symbol
    ):

        if not os.path.isdir(self._backtest_data_directory):
            os.mkdir(self._backtest_data_directory)

        file_path = self.create_backtest_data_file_path(
            backtest_profile, strategy_profile, symbol, TradingDataType.OHLCV
        )

        if os.path.isfile(file_path):
            os.mknod(file_path)

        return file_path

    def index_data(self):
        data_dir = os.path.join(self._backtest_data_directory)
        self._data_index = {
            TradingDataType.OHLCV.value: {}, TradingDataType.TICKER.value: {}
        }

        for file in os.listdir(data_dir):
            data_type = file.split("_")[0]
            symbol = file.split("_")[1]
            self._data_index[data_type][symbol] = {}

            if "files" in self._data_index[data_type]:
                self._data_index[data_type][symbol]["files"].append(file)
            else:
                self._data_index[data_type][symbol]["files"] = [file]

    def get_order(self, order):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality get_order"
        )

    def get_orders(self, symbol, since: datetime = None):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality get_orders"
        )

    def create_limit_buy_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float
    ):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality create_limit_buy_order"
        )

    def create_limit_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float
    ):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality create_limit_sell_order"
        )

    def create_market_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
    ):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality create_market_sell_order"
        )

    def cancel_order(self, order):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality cancel_order"
        )

    def get_open_orders(
        self, target_symbol: str = None, trading_symbol: str = None
    ):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality get_open_orders"
        )

    def get_closed_orders(
        self, target_symbol: str = None, trading_symbol: str = None
    ):
        raise OperationalException(
            f"Backtest market service {self.market} does not support "
            f"functionality get_closed_orders"
        )

    def get_ohclv(self, symbol, time_frame, from_timestamp, to_timestamp=None):
        self.index_data()
        matching_rows = []
        matching_file = None
        symbol_string = symbol.replace("/", "-")
        self._data_index[TradingDataType.OHLCV.value][symbol_string]["files"].sort()

        if to_timestamp is None:
            to_timestamp = datetime.utcnow()

        for file in self._data_index[TradingDataType.OHLCV.value][symbol_string]["files"]:
            start_date_file = datetime.strptime(
                file.split("_")[3], DATETIME_FORMAT_BACKTESTING
            )
            end_date_file = datetime.strptime(
                file.split("_")[4].split(".")[0], DATETIME_FORMAT_BACKTESTING
            )

            if start_date_file <= from_timestamp and to_timestamp <= end_date_file:
                matching_file = file
                break

        if matching_file is None:
            raise OperationalException(
                f"No ohlvc backtest data found for symbol "
                f"{symbol} between {from_timestamp} and {to_timestamp}"
            )

        path = os.path.join(self._backtest_data_directory, matching_file)
        with open(path, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header row

            for row in reader:
                row_date = datetime.strptime(row[0], DATETIME_FORMAT)

                if from_timestamp <= row_date <= to_timestamp:
                    data = [
                        row_date,
                        float(row[1]),
                        float(row[2]),
                        float(row[3]),
                        float(row[4]),
                        float(row[5]),
                    ]
                    matching_rows.append(data)

        return matching_rows

    def get_ticker(self, symbol):
        self.index_data()
        matching_file = None
        match = None
        symbol_string = symbol.replace("/", "-")
        self._data_index[TradingDataType.TICKER.value][symbol_string]["files"].sort()
        date_time = self._configuration_service.config[BACKTESTING_INDEX_DATETIME]

        for file in self._data_index[TradingDataType.TICKER.value][symbol_string]["files"]:
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

        path = os.path.join(self._backtest_data_directory, matching_file)
        with open(path, 'r') as file:
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

        return {
            "symbol": symbol,
            "ask": float(match[1]),
            "high": float(match[2]),
            "low": float(match[3]),
            "previousClose": float(match[4]),
            "bid": float(match[1]),
        }
