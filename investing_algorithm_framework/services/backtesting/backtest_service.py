from datetime import datetime, timedelta

import pandas as pd
from dateutil import parser
from tqdm import tqdm

from investing_algorithm_framework.domain import BacktestReport, \
    BACKTESTING_INDEX_DATETIME, TimeUnit, BacktestPosition, \
    TradingDataType, OrderStatus, OperationalException, MarketDataSource, \
    OrderSide, SYMBOLS, BacktestDateRange
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
            configuration_service
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
        self._configuration_service = configuration_service

    @property
    def resource_directory(self):
        return self._resource_directory

    @resource_directory.setter
    def resource_directory(self, resource_directory):
        self._resource_directory = resource_directory

    def run_backtest(
        self, algorithm, backtest_date_range: BacktestDateRange
    ) -> BacktestReport:
        """
        Run a backtest for the given algorithm. This function will run
        a backtest for the given algorithm and return a backtest report.

        A schedule is generated for the given algorithm and the strategies
        are run for each date in the schedule.

        Also, all backtest data is downloaded (if not already downloaded) and
        the backtest is run for each date in the schedule.

        At the end of the run all traces

        Args:
            algorithm: The algorithm to run the backtest for
            backtest_date_range: The backtest date range

        return:
            BacktestReport: The backtest report
        """
        strategy_profiles = []
        portfolios = self._portfolio_repository.get_all()
        initial_unallocated = 0

        for portfolio in portfolios:
            initial_unallocated += portfolio.unallocated

        for strategy in algorithm.strategies:
            strategy_profiles.append(strategy.strategy_profile)

        # Check if required market data sources are registered
        self._check_if_required_market_data_sources_are_registered()

        schedule = self.generate_schedule(
            strategies=algorithm.strategies,
            start_date=backtest_date_range.start_date,
            end_date=backtest_date_range.end_date
        )

        for index, row in tqdm(
            schedule.iterrows(),
            total=len(schedule),
            desc=f"Running backtest for algorithm with name {algorithm.name}",
            colour="GREEN"
        ):
            strategy_profile = self.get_strategy_from_strategy_profiles(
                strategy_profiles, row['id']
            )
            index_date = parser.parse(str(index))
            self.run_backtest_for_profile(
                algorithm=algorithm,
                strategy=algorithm.get_strategy(strategy_profile.strategy_id),
                index_date=index_date,
            )
        return self.create_backtest_report(
            algorithm, len(schedule), backtest_date_range, initial_unallocated
        )

    def run_backtests(
        self, algorithms, backtest_date_range: BacktestDateRange
    ):
        """
        Run backtests for the given algorithms. This function will run
        backtests for the given algorithms and return a list of backtest
        reports.

        :param algorithms: The algorithms to run the backtests for
        :param backtest_date_range: The backtest date range of the backtests
        :return: A list of backtest reports
        """
        backtest_reports = []

        for algorithm in algorithms:
            backtest_reports.append(
                self.run_backtest(
                    algorithm=algorithm,
                    backtest_date_range=backtest_date_range
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

        strategy.context = algorithm.context
        strategy.run_strategy(algorithm=algorithm, market_data=market_data)

    def generate_schedule(
        self, strategies, start_date, end_date
    ) -> pd.DataFrame:
        """
        Generate a schedule for the given strategies. This function will
        calculate when the strategies should run based on the given start
        and end date. The schedule will be stored in a pandas DataFrame.

        Args:
            strategies: The strategies to generate the schedule for
            start_date: The start date of the schedule
            end_date: The end date of the schedule

        Returns:
            pd.DataFrame: The schedule DataFrame
        """
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
        backtest_date_range: BacktestDateRange,
        initial_unallocated=0
    ) -> BacktestReport:
        """
        Create a backtest report for the given algorithm. This function
        will create a backtest report for the given algorithm and return
        the backtest report instance.

        It will calculate various performance metrics for the backtest.
        Also, it will add all traces to the backtest report. The traces
        are collected from each strategy that was run during the backtest.

        Args:
            algorithm: The algorithm to create the backtest report for
            number_of_runs: The number of runs
            backtest_date_range: The backtest date range of the backtest
            initial_unallocated: The initial unallocated amount

        Returns:
            BacktestReport: The backtest report instance of BacktestReport
        """

        for portfolio in self._portfolio_repository.get_all():
            ids = [strategy.strategy_id for strategy in algorithm.strategies]

            # Check if strategy_id is None
            if None in ids:
                # Remove None from ids
                ids = [x for x in ids if x is not None]

            backtest_report = BacktestReport(
                name=algorithm.name,
                strategy_identifiers=ids,
                backtest_date_range=backtest_date_range,
                initial_unallocated=initial_unallocated,
                trading_symbol=portfolio.trading_symbol,
                created_at=datetime.utcnow(),
            )
            backtest_report.number_of_runs = number_of_runs
            backtest_report.number_of_orders = self._order_service.count({
                "portfolio": portfolio.id
            })
            backtest_report.number_of_positions = \
                self._position_repository.count({
                    "portfolio": portfolio.id,
                    "amount_gt": 0
                })
            backtest_report.percentage_negative_trades = \
                self._performance_service \
                    .get_percentage_negative_trades(portfolio.id)
            backtest_report.percentage_positive_trades = \
                self._performance_service \
                    .get_percentage_positive_trades(portfolio.id)
            backtest_report.number_of_trades_closed = \
                self._performance_service \
                    .get_number_of_trades_closed(portfolio.id)
            backtest_report.number_of_trades_open = \
                self._performance_service \
                    .get_number_of_trades_open(portfolio.id)
            backtest_report.total_cost = portfolio.total_cost
            backtest_report.total_net_gain = portfolio.total_net_gain
            backtest_report.total_net_gain_percentage = \
                self._performance_service \
                    .get_total_net_gain_percentage_of_backtest(
                    portfolio.id, backtest_report
                )
            positions = self._position_repository.get_all({
                "portfolio": portfolio.id
            })
            orders = self._order_service.get_all({
                "portfolio": portfolio.id
            })
            tickers = {}

            for position in positions:

                if position.symbol != portfolio.trading_symbol:
                    ticker_symbol = \
                        f"{position.symbol}/{portfolio.trading_symbol}"

                    if not self._market_data_source_service \
                        .has_ticker_market_data_source(
                            symbol=ticker_symbol, market=portfolio.market
                        ):
                        raise OperationalException(
                            f"Ticker market data source for "
                            f"symbol {ticker_symbol} "
                            f"and market {portfolio.market} not found, please "
                            f"make sure you register a ticker market "
                            f"data source for this symbol and market "
                            f"in backtest mode. Otherwise, the backtest report" 
                            " cannot be generated."
                        )
                    tickers[ticker_symbol] = \
                        self._market_data_source_service.get_ticker(
                            f"{position.symbol}/{portfolio.trading_symbol}",
                            market=portfolio.market
                        )

            backtest_report.growth_rate = self._performance_service \
                .get_growth_rate_of_backtest(
                portfolio.id, tickers, backtest_report
            )
            backtest_report.growth = self._performance_service \
                .get_growth_of_backtest(
                portfolio.id, tickers, backtest_report
            )
            backtest_report.total_value = self._performance_service \
                .get_total_value(portfolio.id, tickers, backtest_report)
            backtest_report.average_trade_duration = \
                self._performance_service \
                    .get_average_trade_duration(portfolio.id)
            backtest_report.average_trade_size = \
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
                        total_value_portfolio=backtest_report.total_value
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
                        total_value_portfolio=backtest_report.total_value
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
            backtest_report.positions = backtest_positions
            backtest_report.trades = algorithm.get_trades()
            backtest_report.orders = orders
            backtest_report.context = algorithm.context
            traces = {}

            # Add traces to the backtest report
            for strategy in algorithm.strategies:
                strategy_traces = strategy.get_traces()
                traces[strategy.strategy_id] = strategy_traces

            backtest_report.traces = traces

            # Calculate metrics for the backtest report
            backtest_report.calculate_metrics()
            return backtest_report

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

    def _check_if_required_market_data_sources_are_registered(self):
        """
        Check if the required market data sources are registered.

        It will iterate over all registered symbols and markets and check
        if a ticker market data source is registered for the symbol and market.
        """
        symbols = self._configuration_service.config[SYMBOLS]

        if symbols is not None:

            for symbol in symbols:
                if not self._market_data_source_service\
                        .has_ticker_market_data_source(
                            symbol=symbol
                        ):
                    raise OperationalException(
                            f"Ticker market data source for "
                            f"symbol {symbol} not found, please "
                            f"make sure you register a ticker market "
                            f"data source for this symbol "
                            f"in backtest mode. Otherwise, the backtest report" 
                            " cannot be generated."
                        )
