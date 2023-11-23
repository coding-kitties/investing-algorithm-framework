from typing import List
from datetime import datetime, timedelta
import pandas as pd
from tqdm import tqdm

from investing_algorithm_framework.domain import BacktestProfile, \
    BACKTESTING_INDEX_DATETIME, TimeUnit, StrategyProfile, BacktestPosition, \
    TradingDataType


class BackTestService:

    def __init__(
        self,
        market_data_service,
        market_service,
        order_service,
        portfolio_repository,
        position_repository,
        performance_service,
    ):
        self._market_data_service = market_data_service
        self._resource_directory = None
        self._order_service = order_service
        self._portfolio_repository = portfolio_repository
        self._data_index = {
            TradingDataType.OHLCV: {},
            TradingDataType.TICKER: {}
        }
        self._performance_service = performance_service
        self._position_repository = position_repository
        self._market_service = market_service

    @property
    def resource_directory(self):
        return self._resource_directory

    @resource_directory.setter
    def resource_directory(self, resource_directory):
        self._resource_directory = resource_directory

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

        for strategy_profile in tqdm(strategy_profiles,
                                     total=len(strategy_profiles),
                                     desc="Preparing backtest market data",
                                     colour="GREEN"):
            self._market_service.create_backtest_data(
                backtest_profile, strategy_profile,
            )

        schedule = self.generate_schedule(
            strategy_profiles, start_date, end_date
        )
        backtest_profile.number_of_runs = len(schedule)
        backtest_profile.number_of_days = (end_date - start_date).days

        for index, row in tqdm(schedule.iterrows(), total=len(schedule),
                               desc="Running backtests", colour="GREEN"):
            strategy_profile = self.get_strategy_from_strateg_profiles(
                strategy_profiles, row['id']
            )

            self.run_backtest_for_profile(
                backtest_profile,
                strategy_profile,
                algorithm,
                algorithm.get_strategy(strategy_profile.strategy_id),
                index,
                row['ohlcv_data_index_date']
            )

        portfolio = self._portfolio_repository.find({"identifier": "backtest"})
        backtest_profile.number_of_orders = self._order_service.count({
            "portfolio": portfolio.id
        })
        backtest_profile.number_of_positions = self._position_repository.count({
            "portfolio": portfolio.id,
            "amount_gt": 0
        })
        backtest_profile.percentage_negative_trades = self._performance_service \
            .get_percentage_negative_trades(portfolio.id)
        backtest_profile.percentage_positive_trades = self._performance_service \
            .get_percentage_positive_trades(portfolio.id)
        backtest_profile.number_of_trades_closed = self._performance_service \
            .get_number_of_trades_closed(portfolio.id)
        backtest_profile.number_of_trades_open = self._performance_service \
            .get_number_of_trades_open(portfolio.id)
        backtest_profile.total_cost = portfolio.total_cost
        backtest_profile.total_net_gain = portfolio.total_net_gain
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
                tickers[position.symbol] = self._market_service.get_ticker(
                    f"{position.symbol}/{portfolio.trading_symbol}"
                )

        backtest_profile.growth_rate = self._performance_service\
            .get_growth_rate_of_backtest(
                portfolio.id, tickers, backtest_profile
            )
        backtest_profile.growth = self._performance_service\
            .get_growth_of_backtest(portfolio.id, tickers, backtest_profile)
        backtest_profile.total_value = self._performance_service\
            .get_total_value(portfolio.id, tickers, backtest_profile)
        backtest_profile.average_trade_duration = \
            self._performance_service.get_average_trade_duration(portfolio.id)
        backtest_profile.average_trade_size= \
            self._performance_service.get_average_trade_size(portfolio.id)

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
                ticker = self._market_service.get_ticker(
                    f"{position.symbol}/{portfolio.trading_symbol}"
                )
                backtest_position.price = ticker["bid"]
            backtest_positions.append(backtest_position)
        backtest_profile.positions = backtest_positions
        backtest_profile.trades = algorithm.get_trades()
        return backtest_profile

    def run_backtest_for_profile(
        self,
        backtest_profile: BacktestProfile,
        strategy_profile: StrategyProfile,
        algorithm,
        strategy,
        index_date,
        ohlcv_data_index_date
    ):
        data = {TradingDataType.OHLCV: {}, TradingDataType.TICKER: {}}
        backtest_profile.backtest_index_date = index_date
        algorithm.config[BACKTESTING_INDEX_DATETIME] = index_date

        for symbol in strategy_profile.symbols:

            if TradingDataType.OHLCV in strategy_profile.trading_data_types:
                data[TradingDataType.OHLCV][symbol] = \
                    self._market_service.get_ohclv(
                        symbol,
                        strategy_profile.trading_time_frame,
                        ohlcv_data_index_date,
                        backtest_profile.backtest_index_date
                    )

            if TradingDataType.TICKER in strategy_profile.trading_data_types:
                data[TradingDataType.TICKER][symbol] = \
                    self._market_service.get_ticker(symbol)

        self._order_service.check_pending_orders(data[TradingDataType.OHLCV])
        strategy.run_strategy(data, algorithm)

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
        strategy_profile = strategy.profile

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

    def generate_schedule(
        self,
        strategy_profiles: List[StrategyProfile],
        start_date,
        end_date
    ):
        data = []

        for profile in strategy_profiles:
            id = profile.strategy_id
            time_unit = profile.time_unit
            interval = profile.interval
            current_time = start_date
            ohlcv_data_index_date = profile.backtest_data_index_date

            while current_time <= end_date:
                data.append({
                    "id": id,
                    'run_time': current_time,
                    'ohlcv_data_index_date': ohlcv_data_index_date
                })

                if TimeUnit.SECOND.equals(time_unit):
                    current_time += timedelta(seconds=interval)
                    ohlcv_data_index_date += timedelta(seconds=interval)
                elif TimeUnit.MINUTE.equals(time_unit):
                    current_time += timedelta(minutes=interval)
                    ohlcv_data_index_date += timedelta(minutes=interval)
                elif TimeUnit.HOUR.equals(time_unit):
                    current_time += timedelta(hours=interval)
                    ohlcv_data_index_date += timedelta(hours=interval)
                elif TimeUnit.DAY.equals(time_unit):
                    current_time += timedelta(days=interval)
                    ohlcv_data_index_date += timedelta(days=interval)
                else:
                    raise ValueError(f"Unsupported time unit: {time_unit}")

        schedule_df = pd.DataFrame(data)
        schedule_df.sort_values(by='run_time', inplace=True)
        schedule_df.set_index('run_time', inplace=True)
        return schedule_df

    def get_strategy_from_strateg_profiles(self, strategy_profiles, id):

        for strategy_profile in strategy_profiles:

            if strategy_profile.strategy_id == id:
                return strategy_profile

        raise ValueError(f"Strategy profile with id {id} not found.")
