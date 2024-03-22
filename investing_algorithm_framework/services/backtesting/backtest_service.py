from datetime import datetime, timedelta

import pandas as pd
from tqdm import tqdm

from investing_algorithm_framework.domain import BacktestReport, \
    BACKTESTING_INDEX_DATETIME, TimeUnit, BacktestPosition, \
    TradingDataType, OrderStatus, OperationalException, MarketDataSource, \
    OrderSide
from investing_algorithm_framework.services.market_data_source_service import \
    MarketDataSourceService


class BacktestService:
    """
    Service that facilitates backtests for algorithm objects.
    """
    def __init__(
        self,
        market_data_source_service: MarketDataSourceService,
        order_service,
        portfolio_repository,
        position_repository,
        performance_service,
    ):
        self._resource_directory = None
        self._order_service = order_service
        self._portfolio_repository = portfolio_repository
        self._data_index = {
            TradingDataType.OHLCV: {},
            TradingDataType.TICKER: {}
        }
        self._performance_service = performance_service
        self._position_repository = position_repository
        self._market_data_source_service: MarketDataSourceService \
            = market_data_source_service
        self._backtest_market_data_sources = []

    @property
    def resource_directory(self):
        return self._resource_directory

    @resource_directory.setter
    def resource_directory(self, resource_directory):
        self._resource_directory = resource_directory

    def run_backtest(
        self, algorithm, start_date, end_date=None
    ) -> BacktestReport:
        """
        Run a backtest for the given algorithm. This function will run
        a backtest for the given algorithm and return a backtest report.

        A schedule is generated for the given algorithm and the strategies
        are run for each date in the schedule.

        Also, all backtest data is downloaded (if not already downloaded) and
        the backtest is run for each date in the schedule.

        :param algorithm: The algorithm to run the backtest for
        :param start_date: The start date of the backtest
        :param end_date: The end date of the backtest

        :return: The backtest report instance of BacktestReport
        """
        strategy_profiles = []
        portfolios = self._portfolio_repository.get_all()
        initial_unallocated = 0

        for portfolio in portfolios:
            initial_unallocated += portfolio.unallocated

        for strategy in algorithm.strategies:
            strategy_profiles.append(strategy.strategy_profile)

        if end_date is None:
            end_date = datetime.utcnow()

        if start_date > end_date:
            raise OperationalException(
                "Start date cannot be greater than end date for backtest"
            )

        schedule = self.generate_schedule(
            strategies=algorithm.strategies,
            start_date=start_date,
            end_date=end_date
        )

        for index, row in tqdm(
            schedule.iterrows(),
            total=len(schedule),
            desc=f"Running backtests {algorithm.name}",
            colour="GREEN"
        ):
            strategy_profile = self.get_strategy_from_strategy_profiles(
                strategy_profiles, row['id']
            )
            self.run_backtest_for_profile(
                algorithm=algorithm,
                strategy=algorithm.get_strategy(strategy_profile.strategy_id),
                index_date=index,
            )
        return self.create_backtest_report(
            algorithm, len(schedule), start_date, end_date, initial_unallocated
        )

    def run_backtests(self, algorithms, start_date, end_date=None):
        """
        Run backtests for the given algorithms. This function will run
        backtests for the given algorithms and return a list of backtest
        reports.

        :param algorithms: The algorithms to run the backtests for
        :param start_date: The start date of the backtests
        :param end_date: The end date of the backtests
        :return: A list of backtest reports
        """
        backtest_reports = []

        for algorithm in algorithms:
            backtest_reports.append(
                self.run_backtest(
                    algorithm=algorithm,
                    start_date=start_date,
                    end_date=end_date
                )
            )

        return backtest_reports

    def run_backtest_for_profile(self, algorithm, strategy, index_date):
        algorithm.config[BACKTESTING_INDEX_DATETIME] = index_date
        market_data = {}

        if strategy.strategy_profile.market_data_sources is not None:

            for data_id in strategy.strategy_profile.market_data_sources:

                if isinstance(data_id, MarketDataSource):
                    market_data[data_id.get_identifier()] = \
                        self._market_data_source_service.get_data(
                            data_id.get_identifier()
                        )
                else:
                    market_data[data_id] = \
                        self._market_data_source_service.get_data(data_id)

        self._order_service.check_pending_orders()
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

            while current_time <= end_date:
                data.append({
                    "id": id,
                    'run_time': current_time,
                })

                if TimeUnit.SECOND.equals(time_unit):
                    current_time += timedelta(seconds=interval)
                elif TimeUnit.MINUTE.equals(time_unit):
                    current_time += timedelta(minutes=interval)
                elif TimeUnit.HOUR.equals(time_unit):
                    current_time += timedelta(hours=interval)
                elif TimeUnit.DAY.equals(time_unit):
                    current_time += timedelta(days=interval)
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

    def get_strategy_from_strategy_profiles(self, strategy_profiles, id):

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
    ) -> BacktestReport:
        """
        Create a backtest report for the given algorithm. This function
        will create a backtest report for the given algorithm and return
        the backtest report instance.

        It will calculate various performance metrics for the backtest.

        :param algorithm: The algorithm to create the backtest report for
        :param number_of_runs: The number of runs
        :param start_date: The start date of the backtest
        :param end_date: The end date of the backtest
        :param initial_unallocated: The initial unallocated amount
        :return: The backtest report instance of BacktestReport
        """
        for portfolio in self._portfolio_repository.get_all():
            ids = [strategy.strategy_id for strategy in algorithm.strategies]

            # Check if strategy_id is None
            if None in ids:
                # Remove None from ids
                ids = [x for x in ids if x is not None]

            backtest_profile = BacktestReport(
                name=algorithm.name,
                strategy_identifiers=ids,
                backtest_index_date=start_date,
                backtest_start_date=start_date,
                backtest_end_date=end_date,
                initial_unallocated=initial_unallocated,
                trading_symbol=portfolio.trading_symbol,
                created_at=datetime.utcnow(),
            )
            backtest_profile.number_of_runs = number_of_runs
            backtest_profile.number_of_days = (end_date - start_date).days
            backtest_profile.number_of_orders = self._order_service.count({
                "portfolio": portfolio.id
            })
            backtest_profile.number_of_positions = \
                self._position_repository.count({
                    "portfolio": portfolio.id,
                    "amount_gt": 0
                })
            backtest_profile.percentage_negative_trades = \
                self._performance_service\
                    .get_percentage_negative_trades(portfolio.id)
            backtest_profile.percentage_positive_trades = \
                self._performance_service\
                    .get_percentage_positive_trades(portfolio.id)
            backtest_profile.number_of_trades_closed = \
                self._performance_service\
                    .get_number_of_trades_closed(portfolio.id)
            backtest_profile.number_of_trades_open = \
                self._performance_service\
                    .get_number_of_trades_open(portfolio.id)
            backtest_profile.total_cost = portfolio.total_cost
            backtest_profile.total_net_gain = portfolio.total_net_gain
            backtest_profile.total_net_gain_percentage = \
                self._performance_service\
                .get_total_net_gain_percentage_of_backtest(
                    portfolio.id, backtest_profile
                )
            positions = self._position_repository.get_all({
                "portfolio": portfolio.id
            })
            tickers = {}

            for position in positions:

                if position.symbol != portfolio.trading_symbol:
                    ticker_symbol = \
                        f"{position.symbol}/{portfolio.trading_symbol}"
                    tickers[ticker_symbol] = \
                        self._market_data_source_service.get_ticker(
                            f"{position.symbol}/{portfolio.trading_symbol}",
                            market=portfolio.market
                        )

            backtest_profile.growth_rate = self._performance_service \
                .get_growth_rate_of_backtest(
                    portfolio.id, tickers, backtest_profile
                )
            backtest_profile.growth = self._performance_service \
                .get_growth_of_backtest(
                    portfolio.id, tickers, backtest_profile
                )
            backtest_profile.total_value = self._performance_service \
                .get_total_value(portfolio.id, tickers, backtest_profile)
            backtest_profile.average_trade_duration = \
                self._performance_service\
                    .get_average_trade_duration(portfolio.id)
            backtest_profile.average_trade_size = \
                self._performance_service.get_average_trade_size(portfolio.id)
            positions = self._position_repository.get_all({
                "portfolio": portfolio.id
            })
            backtest_positions = []

            for position in positions:

                if position.symbol == portfolio.trading_symbol:
                    backtest_position = BacktestPosition(
                        position,
                        trading_symbol=True,
                        total_value_portfolio=backtest_profile.total_value
                    )
                    backtest_position.price = 1
                else:
                    pending_buy_orders = self._order_service.get_all({
                        "portfolio": portfolio.id,
                        "target_symbol": position.symbol,
                        "status": OrderStatus.OPEN.value,
                        "order_side": OrderSide.BUY.value
                    })
                    amount_in_pending_buy_orders = 0

                    for order in pending_buy_orders:
                        amount_in_pending_buy_orders += order.amount

                    pending_sell_orders = self._order_service.get_all({
                        "portfolio": portfolio.id,
                        "target_symbol": position.symbol,
                        "status": OrderStatus.OPEN.value,
                        "order_side": OrderSide.SELL.value
                    })
                    amount_in_pending_sell_orders = 0

                    for order in pending_sell_orders:
                        amount_in_pending_sell_orders += order.amount

                    backtest_position = BacktestPosition(
                        position,
                        amount_pending_buy=amount_in_pending_buy_orders,
                        amount_pending_sell=amount_in_pending_sell_orders,
                        total_value_portfolio=backtest_profile.total_value
                    )

                    # Probably not needed
                    ticker = self._market_data_source_service \
                        .get_ticker(
                            symbol=f"{position.symbol}"
                                   f"/{portfolio.trading_symbol}",
                            market=portfolio.market
                        )
                    backtest_position.price = ticker["bid"]
                backtest_positions.append(backtest_position)
            backtest_profile.positions = backtest_positions
            backtest_profile.trades = algorithm.get_trades()
            return backtest_profile

    def set_backtest_market_data_sources(self, market_data_sources):
        self._backtest_market_data_sources = market_data_sources

    def get_backtest_market_data_sources(self):
        return self._backtest_market_data_sources

    def get_backtest_market_data_source(self, symbol, market):

        for market_data_source in self._backtest_market_data_sources:
            if market_data_source.symbol == symbol \
                    and market_data_source.market == market:
                return market_data_source
        raise OperationalException(
            f"Market data source for "
            f"symbol {symbol} and market {market} not found"
        )
