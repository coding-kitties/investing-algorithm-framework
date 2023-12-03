from typing import List
from datetime import datetime, timedelta
import pandas as pd
from tqdm import tqdm

from investing_algorithm_framework.domain import BacktestProfile, \
    BACKTESTING_INDEX_DATETIME, TimeUnit, StrategyProfile, BacktestPosition, \
    TradingDataType, OrderStatus, OperationalException
from investing_algorithm_framework.infrastructure import \
    CCXTOHLCVBacktestMarketDataSource


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

    def backtest(self, algorithm, start_date, end_date=None):
        strategy_profiles = []
        portfolio = self._portfolio_repository.find({"identifier": "backtest"})
        initial_unallocated = portfolio.get_unallocated()

        if end_date is None:
            end_date = datetime.utcnow()

        if start_date > end_date:
            raise OperationalException(
                "Start date cannot be greater than end date for backtest"
            )

        market_data_sources = []
        backtest_market_data_sources = []

        for strategy in algorithm.strategies:
            strategy_profiles.append(strategy.strategy_profile)
            if strategy.strategy_profile.market_data_sources is not None:
                for market_data_source in \
                        strategy.strategy_profile.market_data_sources:

                    if market_data_source not in market_data_sources:
                        market_data_sources.append(market_data_source)

        for market_data_source in tqdm(
                market_data_sources,
                total=len(market_data_sources),
                desc="Preparing backtest market data",
                colour="GREEN"
        ):
            backtest_market_data_source = market_data_source \
                .to_backtest_market_data_source()
            backtest_market_data_source.prepare_data(
                config=algorithm.config,
                backtest_start_date=start_date,
                backtest_end_date=end_date
            )
            backtest_market_data_sources.append(backtest_market_data_source)

        algorithm.market_service.backtest_market_data_sources = \
            backtest_market_data_sources
        schedule = self.generate_schedule(
            strategies=algorithm.strategies,
            start_date=start_date,
            end_date=end_date
        )

        for index, row in tqdm(schedule.iterrows(), total=len(schedule),
                               desc="Running backtests", colour="GREEN"):
            strategy_profile = self.get_strategy_from_strateg_profiles(
                strategy_profiles, row['id']
            )
            self.run_backtest_for_profile(
                algorithm=algorithm,
                strategy=algorithm.get_strategy(strategy_profile.strategy_id),
                index_date=index,
                backtest_market_data_sources=backtest_market_data_sources
            )

        return self.create_backtest_report(
            algorithm, len(schedule), start_date, end_date, initial_unallocated
        )

    def run_backtest_for_profile(
        self,
        algorithm,
        strategy,
        index_date,
        backtest_market_data_sources=None
    ):
        algorithm.config[BACKTESTING_INDEX_DATETIME] = index_date
        market_data = {}

        if strategy.strategy_profile.market_data_sources is None or \
                len(strategy.strategy_profile.market_data_sources) == 0:
            raise OperationalException(
                f"No market data sources found for strategy "
                f"with id {strategy.strategy_profile.strategy_id}."
            )

        for market_data_source in strategy.strategy_profile.market_data_sources:
            backtest_market_data_source = [
                backtest_market_data_source for backtest_market_data_source
                in backtest_market_data_sources
                if backtest_market_data_source.get_identifier()
                == market_data_source.get_identifier()
            ]

            if len(backtest_market_data_source) == 0:
                raise OperationalException(
                    f"Backtest market data source with identifier "
                    f"{market_data_source.get_identifier()} not found."
                )

            backtest_market_data_source = backtest_market_data_source[0]
            market_data[market_data_source.get_identifier()] = \
                backtest_market_data_source.get_data(
                    backtest_index_date=index_date
                )

        pending_orders_ohlcv_data = {}

        for market_data_source in backtest_market_data_sources:

            if isinstance(market_data_source, CCXTOHLCVBacktestMarketDataSource):

                if market_data_source.symbol not in pending_orders_ohlcv_data:
                    pending_orders_ohlcv_data[market_data_source.symbol] = \
                        market_data_source.get_data(
                            backtest_index_date=index_date
                        )

        self._order_service.check_pending_orders(pending_orders_ohlcv_data)
        strategy.run_strategy(algorithm=algorithm, market_data=market_data)

    def generate_schedule(
        self,
        strategies,
        start_date,
        end_date
    ):
        data = []

        for strategy in strategies:
            id = strategy.strategy_profile.strategy_id
            time_unit = strategy.strategy_profile.time_unit
            interval = strategy.strategy_profile.interval
            current_time = start_date
            # ohlcv_data_index_date = strategy.strategy_profile.backtest_data_index_date

            while current_time <= end_date:
                data.append({
                    "id": id,
                    'run_time': current_time,
                    # 'ohlcv_data_index_date': ohlcv_data_index_date
                })

                if TimeUnit.SECOND.equals(time_unit):
                    current_time += timedelta(seconds=interval)
                    # ohlcv_data_index_date += timedelta(seconds=interval)
                elif TimeUnit.MINUTE.equals(time_unit):
                    current_time += timedelta(minutes=interval)
                    # ohlcv_data_index_date += timedelta(minutes=interval)
                elif TimeUnit.HOUR.equals(time_unit):
                    current_time += timedelta(hours=interval)
                    # ohlcv_data_index_date += timedelta(hours=interval)
                elif TimeUnit.DAY.equals(time_unit):
                    current_time += timedelta(days=interval)
                    # ohlcv_data_index_date += timedelta(days=interval)
                else:
                    raise ValueError(f"Unsupported time unit: {time_unit}")

        schedule_df = pd.DataFrame(data)
        if schedule_df.empty:
            raise OperationalException(
                "Could not generate schedule "
                "for backtest, do you have a strategy "
                "registered for your algorithm?"
            )

        schedule_df.sort_values(by='run_time', inplace=True)
        schedule_df.set_index('run_time', inplace=True)
        return schedule_df

    def get_strategy_from_strateg_profiles(self, strategy_profiles, id):

        for strategy_profile in strategy_profiles:

            if strategy_profile.strategy_id == id:
                return strategy_profile

        raise ValueError(f"Strategy profile with id {id} not found.")

    def create_backtest_report(
        self,
        algorithm,
        number_of_runs,
        start_date,
        end_date,
        initial_unallocated=0
    ):
        portfolio = self._portfolio_repository.find({"identifier": "backtest"})
        backtest_profile = BacktestProfile(
            backtest_index_date=start_date,
            backtest_start_date=start_date,
            backtest_end_date=end_date,
            initial_unallocated=initial_unallocated,
            trading_symbol=portfolio.trading_symbol,
        )
        backtest_profile.number_of_runs = number_of_runs
        backtest_profile.number_of_days = (end_date - start_date).days
        backtest_profile.number_of_orders = self._order_service.count({
            "portfolio": portfolio.id
        })
        backtest_profile.number_of_positions = self._position_repository.count(
            {
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

        backtest_profile.growth_rate = self._performance_service \
            .get_growth_rate_of_backtest(
            portfolio.id, tickers, backtest_profile
        )
        backtest_profile.growth = self._performance_service \
            .get_growth_of_backtest(portfolio.id, tickers, backtest_profile)
        backtest_profile.total_value = self._performance_service \
            .get_total_value(portfolio.id, tickers, backtest_profile)
        backtest_profile.average_trade_duration = \
            self._performance_service.get_average_trade_duration(portfolio.id)
        backtest_profile.average_trade_size = \
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
                pending_orders = self._order_service.get_all({
                    "portfolio": portfolio.id,
                    "target_symbol": position.symbol,
                    "status": OrderStatus.OPEN.value
                })

                amount_in_pending_orders = 0

                for order in pending_orders:
                    amount_in_pending_orders += order.amount

                backtest_position = BacktestPosition(
                    position, amount_pending=amount_in_pending_orders
                )
                ticker = self._market_service.get_ticker(
                    f"{position.symbol}/{portfolio.trading_symbol}"
                )
                backtest_position.price = ticker["bid"]
            backtest_positions.append(backtest_position)
        backtest_profile.positions = backtest_positions
        backtest_profile.trades = algorithm.get_trades()
        return backtest_profile
