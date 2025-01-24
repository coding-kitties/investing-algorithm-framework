import inspect
import logging
from typing import List, Dict
import re

from investing_algorithm_framework.domain import OrderStatus, \
    Position, Order, Portfolio, OrderType, OrderSide, TradeStatus, \
    BACKTESTING_FLAG, BACKTESTING_INDEX_DATETIME, MarketService, TimeUnit, \
    OperationalException, random_string, RoundingService, Trade
from investing_algorithm_framework.services import MarketCredentialService, \
    MarketDataSourceService, PortfolioService, PositionService, TradeService, \
    OrderService, ConfigurationService, StrategyOrchestratorService, \
    PortfolioConfigurationService
from .task import Task

logger = logging.getLogger("investing_algorithm_framework")


class Algorithm:
    """
    Class to represent an algorithm. An algorithm is a collection of
    strategies that are executed in a specific order. The algorithm
    class is responsible for managing the strategies and executing
    them in the correct order.

    Args:
        name (str): The name of the algorithm
        description (str): The description of the algorithm
        context (dict): The context of the algorithm, for backtest
          references
        strategy: A single strategy to add to the algorithm
        data_sources: The list of data sources to add to the algorithm
    """
    def __init__(
        self,
        name: str = None,
        description: str = None,
        context: Dict = None,
        strategy=None,
        data_sources=None
    ):
        self._name = name
        self._context = {}

        if name is None:
            self._name = f"algorithm_{random_string(10)}"

        self._description = None

        if description is not None:
            self._description = description

        if context is not None:
            self.add_context(context)

        self._strategies = []
        self._tasks = []
        self.portfolio_service: PortfolioService
        self.position_service: PositionService
        self.order_service: OrderService
        self.market_service: MarketService
        self.configuration_service: ConfigurationService
        self.portfolio_configuration_service: PortfolioConfigurationService
        self.strategy_orchestrator_service: StrategyOrchestratorService = None
        self._data_sources = {}
        self._strategies = []
        self._market_credential_service: MarketCredentialService
        self._market_data_source_service: MarketDataSourceService
        self.trade_service: TradeService

        if strategy is not None:
            self.add_strategy(strategy)

        if data_sources is not None:
            self.add_data_sources(data_sources)

    def _validate_name(self, name):
        """
        Function to validate the name of the algorithm. This function
        will check if the name of the algorithm is a string and raise
        an exception if it is not.

        Name can only contain letters, numbers

        Parameters:
            name: The name of the algorithm

        Returns:
            None
        """
        if not isinstance(name, str):
            raise OperationalException(
                "The name of the algorithm must be a string"
            )

        pattern = re.compile(r"^[a-zA-Z0-9]*$")

        if not pattern.match(name):
            raise OperationalException(
                "The name of the algorithm can only contain" +
                " letters and numbers"
            )

        illegal_chars = r"[\/:*?\"<>|]"

        if re.search(illegal_chars, name):
            raise OperationalException(
                f"Illegal characters detected in algorithm: {name}. "
                f"Illegal characters: / \\ : * ? \" < > |"
            )

    def initialize_services(
        self,
        configuration_service,
        portfolio_configuration_service,
        portfolio_service,
        position_service,
        order_service,
        market_service,
        strategy_orchestrator_service,
        market_credential_service,
        market_data_source_service,
        trade_service
    ):
        self.portfolio_service: PortfolioService = portfolio_service
        self.position_service: PositionService = position_service
        self.order_service: OrderService = order_service
        self.market_service: MarketService = market_service
        self.configuration_service: ConfigurationService \
            = configuration_service
        self.portfolio_configuration_service: PortfolioConfigurationService \
            = portfolio_configuration_service
        self.strategy_orchestrator_service: StrategyOrchestratorService \
            = strategy_orchestrator_service
        self._data_sources = {}
        self._market_credential_service: MarketCredentialService \
            = market_credential_service
        self._market_data_source_service: MarketDataSourceService \
            = market_data_source_service
        self.trade_service: TradeService = trade_service

        # Add all registered strategies to the orchestrator
        self.strategy_orchestrator_service.add_strategies(
            self._strategies
        )

    def start(self, number_of_iterations: int = None):
        """
        Function to start the algorithm.
        This function will start the algorithm by scheduling all
        jobs in the strategy orchestrator service. The jobs are not
        run immediately, but are scheduled to run in the future by the
        app.

        Args:
            number_of_iterations (int): (Optional) The number of
              iterations to run the algorithm

        Returns:
            None
        """
        self.strategy_orchestrator_service.start(
            algorithm=self,
            number_of_iterations=number_of_iterations
        )

    def stop(self) -> None:
        """
        Function to stop the algorithm. This function will stop the
        algorithm by stopping all jobs in the strategy orchestrator
        service.

        Returns:
            None
        """

        if self.strategy_orchestrator_service is not None:
            self.strategy_orchestrator_service.stop()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._validate_name(name)
        self._name = name

    @property
    def data_sources(self):
        return self._data_sources

    @property
    def config(self):
        """
        Function to get a config instance. This allows users when
        having access to the algorithm instance also to read the
        configs of the app.
        """
        return self.configuration_service.get_config()

    def get_config(self):
        """
        Function to get a config instance. This allows users when
        having access to the algorithm instance also to read the
        configs of the app.
        """
        return self.configuration_service.get_config()

    @property
    def description(self):
        """
        Function to get the description of the algorithm
        """
        return self._description

    @property
    def context(self):
        """
        Function to get the context of the algorithm
        """
        return self._context

    def add_context(self, context: Dict):
        # Check if the context is a dictionary with only string,
        # float or int values
        for key, value in self.context.items():
            if not isinstance(key, str) or \
                    not isinstance(value, (str, float, int)):
                raise OperationalException(
                    "The context for an algorithm must be a dictionary with "
                    "only string, float or int values."
                )

        self._context = context

    @property
    def running(self) -> bool:
        """
        Returns True if the algorithm is running, False otherwise.

        The algorithm is considered to be running if has strategies
        scheduled to run in the strategy orchestrator service.
        """
        return self.strategy_orchestrator_service.running

    def run_jobs(self):
        """
        Function run all pending jobs in the strategy orchestrator
        """
        self.strategy_orchestrator_service.run_pending_jobs()

    def create_order(
        self,
        target_symbol,
        price,
        order_type,
        order_side,
        amount,
        market=None,
        execute=True,
        validate=True,
        sync=True
    ):
        """
        Function to create an order. This function will create an order
        and execute it if the execute parameter is set to True. If the
        validate parameter is set to True, the order will be validated

        Args:
            target_symbol: The symbol of the asset to trade
            price: The price of the asset
            order_type: The type of the order
            order_side: The side of the order
            amount: The amount of the asset to trade
            market: The market to trade the asset
            execute: If set to True, the order will be executed
            validate: If set to True, the order will be validated
            sync: If set to True, the created order will be synced
            with the portfolio of the algorithm.

        Returns:
            The order created
        """
        portfolio = self.portfolio_service.find({"market": market})
        order_data = {
            "target_symbol": target_symbol,
            "price": price,
            "amount": amount,
            "order_type": order_type,
            "order_side": order_side,
            "portfolio_id": portfolio.id,
            "status": OrderStatus.CREATED.value,
            "trading_symbol": portfolio.trading_symbol,
        }

        if BACKTESTING_FLAG in self.configuration_service.config \
                and self.configuration_service.config[BACKTESTING_FLAG]:
            order_data["created_at"] = \
                self.configuration_service.config[BACKTESTING_INDEX_DATETIME]

        return self.order_service.create(
            order_data, execute=execute, validate=validate, sync=sync
        )

    def has_balance(self, symbol, amount, market=None):
        """
        Function to check if the portfolio has enough balance to
        create an order. This function will return True if the
        portfolio has enough balance to create an order, False
        otherwise.

        Parameters:
            symbol: The symbol of the asset
            amount: The amount of the asset
            market: The market of the asset

        Returns:
            Boolean: True if the portfolio has enough balance
        """

        portfolio = self.portfolio_service.find({"market": market})
        position = self.position_service.find(
            {"portfolio": portfolio.id, "symbol": symbol}
        )

        if position is None:
            return False

        return position.get_amount() >= amount

    def create_limit_order(
        self,
        target_symbol,
        price,
        order_side,
        amount=None,
        amount_trading_symbol=None,
        percentage=None,
        percentage_of_portfolio=None,
        percentage_of_position=None,
        precision=None,
        market=None,
        execute=True,
        validate=True,
        sync=True
    ):
        """
        Function to create a limit order. This function will create a limit
        order and execute it if the execute parameter is set to True. If the
        validate parameter is set to True, the order will be validated

        Args:
            target_symbol: The symbol of the asset to trade
            price: The price of the asset
            order_side: The side of the order
            amount (optional): The amount of the asset to trade
            amount_trading_symbol (optional): The amount of the
              trading symbol to trade
            percentage (optional): The percentage of the portfolio
              to allocate to the
                order
            percentage_of_portfolio (optional): The percentage
              of the portfolio to allocate to the order
            percentage_of_position (optional): The percentage
              of the position to allocate to
                the order. (Only supported for SELL orders)
            precision (optional): The precision of the amount
            market (optional): The market to trade the asset
            execute (optional): Default True. If set to True,
              the order will be executed
            validate (optional): Default True. If set to
              True, the order will be validated
            sync (optional): Default True. If set to True,
              the created order will be synced with the
                portfolio of the algorithm

        Returns:
            Order: Instance of the order created
        """
        portfolio = self.portfolio_service.find({"market": market})

        if percentage_of_portfolio is not None:
            if not OrderSide.BUY.equals(order_side):
                raise OperationalException(
                    "Percentage of portfolio is only supported for BUY orders."
                )

            net_size = portfolio.get_net_size()
            size = net_size * (percentage_of_portfolio / 100)
            amount = size / price

        elif percentage_of_position is not None:

            if not OrderSide.SELL.equals(order_side):
                raise OperationalException(
                    "Percentage of position is only supported for SELL orders."
                )

            position = self.position_service.find(
                {
                    "symbol": target_symbol,
                    "portfolio": portfolio.id
                }
            )
            amount = position.get_amount() * (percentage_of_position / 100)

        elif percentage is not None:
            net_size = portfolio.get_net_size()
            size = net_size * (percentage / 100)
            amount = size / price

        if precision is not None:
            amount = RoundingService.round_down(amount, precision)

        if amount_trading_symbol is not None:
            amount = amount_trading_symbol / price

        if amount is None:
            raise OperationalException(
                "The amount parameter is required to create a limit order." +
                "Either the amount, amount_trading_symbol, percentage, " +
                "percentage_of_portfolio or percentage_of_position "
                "parameter must be specified."
            )

        order_data = {
            "target_symbol": target_symbol,
            "price": price,
            "amount": amount,
            "order_type": OrderType.LIMIT.value,
            "order_side": OrderSide.from_value(order_side).value,
            "portfolio_id": portfolio.id,
            "status": OrderStatus.CREATED.value,
            "trading_symbol": portfolio.trading_symbol,
        }

        if BACKTESTING_FLAG in self.configuration_service.config \
                and self.configuration_service.config[BACKTESTING_FLAG]:
            order_data["created_at"] = \
                self.configuration_service.config[BACKTESTING_INDEX_DATETIME]

        return self.order_service.create(
            order_data, execute=execute, validate=validate, sync=sync
        )

    def create_market_order(
        self,
        target_symbol,
        order_side,
        amount,
        market=None,
        execute=False,
        validate=False,
        sync=True
    ):
        """
        Function to create a market order. This function will create a market
        order and execute it if the execute parameter is set to True. If the
        validate parameter is set to True, the order will be validated

        Parameters:
            target_symbol: The symbol of the asset to trade
            order_side: The side of the order
            amount: The amount of the asset to trade
            market: The market to trade the asset
            execute: If set to True, the order will be executed
            validate: If set to True, the order will be validated
            sync: If set to True, the created order will be synced with the
                portfolio of the algorithm

        Returns:
            Order: Instance of the order created
        """

        if market is None:
            portfolio = self.portfolio_service.get_all()[0]
        else:
            portfolio = self.portfolio_service.find({"market": market})
        order_data = {
            "target_symbol": target_symbol,
            "amount": amount,
            "order_type": OrderType.MARKET.value,
            "order_side": OrderSide.from_value(order_side).value,
            "portfolio_id": portfolio.id,
            "status": OrderStatus.CREATED.value,
            "trading_symbol": portfolio.trading_symbol,
        }

        if BACKTESTING_FLAG in self.configuration_service.config \
                and self.configuration_service.config[BACKTESTING_FLAG]:
            order_data["created_at"] = \
                self.configuration_service.config[BACKTESTING_INDEX_DATETIME]

        return self.order_service.create(
            order_data, execute=execute, validate=validate, sync=sync
        )

    def get_portfolio(self, market=None) -> Portfolio:
        """
        Function to get the portfolio of the algorithm. This function
        will return the portfolio of the algorithm. If the market
        parameter is specified, the portfolio of the specified market
        will be returned.

        Parameters:
            market: The market of the portfolio

        Returns:
            Portfolio: The portfolio of the algorithm
        """

        if market is None:
            return self.portfolio_service.get_all()[0]

        return self.portfolio_service.find({{"market": market}})

    def get_portfolios(self):
        """
        Function to get all portfolios of the algorithm. This function
        will return all portfolios of the algorithm.

        Returns:
            List[Portfolio]: A list of all portfolios of the algorithm
        """
        return self.portfolio_service.get_all()

    def get_unallocated(self, market=None) -> float:
        """
        Function to get the unallocated balance of the portfolio. This
        function will return the unallocated balance of the portfolio.
        If the market parameter is specified, the unallocated balance
        of the specified market will be returned.

        Args:
            market: The market of the portfolio

        Returns:
            float: The unallocated balance of the portfolio
        """

        if market:
            portfolio = self.portfolio_service.find({{"market": market}})
        else:
            portfolio = self.portfolio_service.get_all()[0]

        trading_symbol = portfolio.trading_symbol
        return self.position_service.find(
            {"portfolio": portfolio.id, "symbol": trading_symbol}
        ).get_amount()

    def get_total_size(self):
        """
        Returns the total size of the portfolio.

        The total size of the portfolio is the unallocated balance and the
        allocated balance of the portfolio.

        Returns:
            float: The total size of the portfolio
        """
        return self.get_unallocated() + self.get_allocated()

    def reset(self):
        self._workers = []
        self._running_workers = []

    def get_order(
        self,
        reference_id=None,
        market=None,
        target_symbol=None,
        trading_symbol=None,
        order_side=None,
        order_type=None
    ) -> Order:
        """
        Function to retrieve an order.

        Exception is thrown when no param has been provided.

        Args:
            reference_id [optional] (int): id given by the external
                market or exchange.
            market [optional] (str): the market that the order was
                executed on.
            target_symbol [optional] (str): the symbol of the asset
                that the order was executed
        """
        query_params = {}

        if reference_id:
            query_params["reference_id"] = reference_id

        if target_symbol:
            query_params["target_symbol"] = target_symbol

        if trading_symbol:
            query_params["trading_symbol"] = trading_symbol

        if order_side:
            query_params["order_side"] = order_side

        if order_type:
            query_params["order_type"] = order_type

        if market:
            portfolio = self.portfolio_service.find({"market": market})
            positions = self.position_service.get_all(
                {"portfolio": portfolio.id}
            )
            query_params["position"] = [position.id for position in positions]

        if not query_params:
            raise OperationalException(
                "No parameters provided to get order."
            )

        return self.order_service.find(query_params)

    def get_orders(
        self,
        target_symbol=None,
        status=None,
        order_type=None,
        order_side=None,
        market=None
    ) -> List[Order]:

        if market is None:
            portfolio = self.portfolio_service.get_all()[0]
        else:
            portfolio = self.portfolio_service.find({"market": market})

        positions = self.position_service.get_all({"portfolio": portfolio.id})
        return self.order_service.get_all(
            {
                "position": [position.id for position in positions],
                "target_symbol": target_symbol,
                "status": status,
                "order_type": order_type,
                "order_side": order_side
            }
        )

    def get_positions(
        self,
        market=None,
        identifier=None,
        amount_gt=None,
        amount_gte=None,
        amount_lt=None,
        amount_lte=None
    ) -> List[Position]:
        """
        Function to get all positions. This function will return all
        positions that match the specified query parameters. If the
        market parameter is specified, the positions of the specified
        market will be returned. If the identifier parameter is
        specified, the positions of the specified portfolio will be
        returned. If the amount_gt parameter is specified, the positions
        with an amount greater than the specified amount will be returned.
        If the amount_gte parameter is specified, the positions with an
        amount greater than or equal to the specified amount will be
        returned. If the amount_lt parameter is specified, the positions
        with an amount less than the specified amount will be returned.
        If the amount_lte parameter is specified, the positions with an
        amount less than or equal to the specified amount will be returned.

        Parameters:
            market: The market of the portfolio where the positions are
            identifier: The identifier of the portfolio
            amount_gt: The amount of the asset must be greater than this
            amount_gte: The amount of the asset must be greater than or
                equal to this
            amount_lt: The amount of the asset must be less than this
            amount_lte: The amount of the asset must be less than or equal
                to this

        Returns:
            List[Position]: A list of positions that match the query parameters
        """
        query_params = {}

        if market is not None:
            query_params["market"] = market

        if identifier is not None:
            query_params["identifier"] = identifier

        if amount_gt is not None:
            query_params["amount_gt"] = amount_gt

        if amount_gte is not None:
            query_params["amount_gte"] = amount_gte

        if amount_lt is not None:
            query_params["amount_lt"] = amount_lt

        if amount_lte is not None:
            query_params["amount_lte"] = amount_lte

        portfolios = self.portfolio_service.get_all(query_params)

        if not portfolios:
            raise OperationalException("No portfolio found.")

        portfolio = portfolios[0]
        return self.position_service.get_all(
            {"portfolio": portfolio.id}
        )

    def get_position(self, symbol, market=None, identifier=None) -> Position:
        """
        Function to get a position. This function will return the
        position that matches the specified query parameters. If the
        market parameter is specified, the position of the specified
        market will be returned. If the identifier parameter is
        specified, the position of the specified portfolio will be
        returned.

        Parameters:
            symbol: The symbol of the asset that represents the position
            market: The market of the portfolio where the position is located
            identifier: The identifier of the portfolio

        Returns:
            Position: The position that matches the query parameters
        """

        query_params = {}

        if market is not None:
            query_params["market"] = market

        if identifier is not None:
            query_params["identifier"] = identifier

        portfolios = self.portfolio_service.get_all(query_params)

        if not portfolios:
            raise OperationalException("No portfolio found.")

        portfolio = portfolios[0]

        try:
            return self.position_service.find(
                {"portfolio": portfolio.id, "symbol": symbol}
            )
        except OperationalException:
            return None

    def has_position(
        self,
        symbol,
        market=None,
        identifier=None,
        amount_gt=0,
        amount_gte=None,
        amount_lt=None,
        amount_lte=None
    ):
        """
        Function to check if a position exists. This function will return
        True if a position exists, False otherwise. This function will check
        if the amount > 0 condition by default.

        Parameters:
            param symbol: The symbol of the asset
            param market: The market of the asset
            param identifier: The identifier of the portfolio
            param amount_gt: The amount of the asset must be greater than this
            param amount_gte: The amount of the asset must be greater than
            or equal to this
            param amount_lt: The amount of the asset must be less than this
            param amount_lte: The amount of the asset must be less than
            or equal to this

        Returns:
            Boolean: True if a position exists, False otherwise
        """

        return self.position_exists(
            symbol=symbol,
            market=market,
            identifier=identifier,
            amount_gt=amount_gt,
            amount_gte=amount_gte,
            amount_lt=amount_lt,
            amount_lte=amount_lte
        )

    def position_exists(
            self,
            symbol,
            market=None,
            identifier=None,
            amount_gt=None,
            amount_gte=None,
            amount_lt=None,
            amount_lte=None
    ) -> bool:
        """
        Function to check if a position exists. This function will return
        True if a position exists, False otherwise. This function will
        not check the amount > 0 condition by default. If you want to
        check if a position exists with an amount greater than 0, you
        can use the amount_gt parameter. If you want to check if a
        position exists with an amount greater than or equal to a
        certain amount, you can use the amount_gte parameter. If you
        want to check if a position exists with an amount less than a
        certain amount, you can use the amount_lt parameter. If you want
        to check if a position exists with an amount less than or equal
        to a certain amount, you can use the amount_lte parameter.

        It is not recommended to use this method directly because it can
        have adverse effects on the algorithm. It is recommended to use
        the has_position method instead.

        param symbol: The symbol of the asset
        param market: The market of the asset
        param identifier: The identifier of the portfolio
        param amount_gt: The amount of the asset must be greater than this
        param amount_gte: The amount of the asset must be greater than
        or equal to this
        param amount_lt: The amount of the asset must be less than this
        param amount_lte: The amount of the asset must be less than
        or equal to this

        return: True if a position exists, False otherwise
        """
        query_params = {}

        if market is not None:
            query_params["market"] = market

        if identifier is not None:
            query_params["identifier"] = identifier

        if amount_gt is not None:
            query_params["amount_gt"] = amount_gt

        if amount_gte is not None:
            query_params["amount_gte"] = amount_gte

        if amount_lt is not None:
            query_params["amount_lt"] = amount_lt

        if amount_lte is not None:
            query_params["amount_lte"] = amount_lte

        query_params["symbol"] = symbol
        return self.position_service.exists(query_params)

    def get_position_percentage_of_portfolio(
        self, symbol, market=None, identifier=None
    ) -> float:
        """
        Returns the percentage of the current total value of the portfolio
        that is allocated to a position. This is calculated by dividing
        the current value of the position by the total current value
        of the portfolio.
        """

        query_params = {}

        if market is not None:
            query_params["market"] = market

        if identifier is not None:
            query_params["identifier"] = identifier

        portfolios = self.portfolio_service.get_all(query_params)

        if not portfolios:
            raise OperationalException("No portfolio found.")

        portfolio = portfolios[0]
        position = self.position_service.find(
            {"portfolio": portfolio.id, "symbol": symbol}
        )
        full_symbol = f"{position.symbol.upper()}/" \
                      f"{portfolio.trading_symbol.upper()}"
        ticker = self._market_data_source_service.get_ticker(
            symbol=full_symbol, market=market
        )
        total = self.get_unallocated() + self.get_allocated()
        return (position.amount * ticker["bid"] / total) * 100

    def get_position_percentage_of_portfolio_by_net_size(
        self, symbol, market=None, identifier=None
    ) -> float:
        """
        Returns the percentage of the portfolio that is allocated to a
        position. This is calculated by dividing the cost of the position
        by the total net size of the portfolio.

        The total net size of the portfolio is the initial balance of the
        portfolio plus the all the net gains of your trades.
        """
        query_params = {}

        if market is not None:
            query_params["market"] = market

        if identifier is not None:
            query_params["identifier"] = identifier

        portfolios = self.portfolio_service.get_all(query_params)

        if not portfolios:
            raise OperationalException("No portfolio found.")

        portfolio = portfolios[0]
        position = self.position_service.find(
            {"portfolio": portfolio.id, "symbol": symbol}
        )
        net_size = portfolio.get_net_size()
        return (position.cost / net_size) * 100

    def close_position(
        self, symbol, market=None, identifier=None, precision=None
    ):
        """
        Function to close a position. This function will close a position
        by creating a market order to sell the position. If the precision
        parameter is specified, the amount of the order will be rounded
        down to the specified precision.

        Parameters:
            symbol: The symbol of the asset
            market: The market of the asset
            identifier: The identifier of the portfolio
            precision: The precision of the amount

        Returns:
            None
        """
        portfolio = self.portfolio_service.find(
            {"market": market, "identifier": identifier}
        )
        position = self.position_service.find(
            {"portfolio": portfolio.id, "symbol": symbol}
        )

        if position.get_amount() == 0:
            return

        for order in self.order_service \
                .get_all(
                    {
                        "position": position.id,
                        "status": OrderStatus.OPEN.value
                    }
                ):
            self.order_service.cancel_order(order)

        symbol = f"{symbol.upper()}/{portfolio.trading_symbol.upper()}"
        ticker = self._market_data_source_service.get_ticker(
            symbol=symbol, market=market
        )
        self.create_limit_order(
            target_symbol=position.symbol,
            amount=position.get_amount(),
            order_side=OrderSide.SELL.value,
            price=ticker["bid"],
            precision=precision,
        )

    def add_strategies(self, strategies):
        """
        Function to add multiple strategies to the algorithm.
        This function will check if there are any duplicate strategies
        with the same name and raise an exception if there are.
        """
        has_duplicates = False

        for strategy in strategies:
            from .strategy import TradingStrategy
            if not issubclass(strategy, TradingStrategy):
                raise OperationalException(
                    "The strategy must be a subclass of TradingStrategy"
                )

            if inspect.isclass(strategy):
                strategy = strategy()

            assert isinstance(strategy, TradingStrategy), \
                OperationalException(
                    "Strategy object is not an instance of a TradingStrategy"
                )

        # Check if there are any duplicate strategies
        for i in range(len(strategies)):
            for j in range(i + 1, len(strategies)):
                if strategies[i].worker_id == strategies[j].worker_id:
                    has_duplicates = True
                    break

        if has_duplicates:
            raise OperationalException(
                "There are duplicate strategies with the same name"
            )

        self._strategies = strategies

    def add_strategy(self, strategy):
        """
        Function to add multiple strategies to the algorithm.
        This function will check if there are any duplicate strategies
        with the same name and raise an exception if there are.
        """
        has_duplicates = False
        from .strategy import TradingStrategy

        if inspect.isclass(strategy):

            if not issubclass(strategy, TradingStrategy):
                raise OperationalException(
                    "The strategy must be a subclass of TradingStrategy"
                )

            strategy = strategy()

        assert isinstance(strategy, TradingStrategy), \
            OperationalException(
                "Strategy object is not an instance of a TradingStrategy"
            )

        for i in range(len(self._strategies)):
            for j in range(i + 1, len(self._strategies)):
                if self._strategies[i].worker_id == strategy.worker_id:
                    has_duplicates = True
                    break

        if has_duplicates:
            raise OperationalException(
                "Can't add strategy, there already exists a strategy "
                "with the same id in the algorithm"
            )

        if strategy.market_data_sources is not None:
            self.add_data_sources(strategy.market_data_sources)

        self._strategies.append(strategy)

    @property
    def strategies(self):
        return self._strategies

    def get_strategy(self, strategy_id):
        for strategy in self.strategy_orchestrator_service.get_strategies():
            if strategy.worker_id == strategy_id:
                return strategy

        return None

    def add_tasks(self, tasks):
        self.strategy_orchestrator_service.add_tasks(tasks)

    def get_allocated(self, market=None, identifier=None) -> float:

        if self.portfolio_configuration_service.count() > 1 \
                and identifier is None and market is None:
            raise OperationalException(
                "Multiple portfolios found. Please specify a "
                "portfolio identifier."
            )

        if market is not None and identifier is not None:
            portfolio_configurations = self.portfolio_configuration_service \
                .get_all()

        else:
            query_params = {"market": market, "identifier": identifier}
            portfolio_configuration = self.portfolio_configuration_service \
                .find(query_params)

            if not portfolio_configuration:
                raise OperationalException("No portfolio found.")

            portfolio_configurations = [portfolio_configuration]

        if len(portfolio_configurations) == 0:
            raise OperationalException("No portfolio found.")

        portfolios = []

        for portfolio_configuration in portfolio_configurations:
            portfolio = self.portfolio_service.find(
                {"identifier": portfolio_configuration.identifier}
            )
            portfolio.configuration = portfolio_configuration
            portfolios.append(portfolio)

        allocated = 0

        for portfolio in portfolios:
            positions = self.position_service.get_all(
                {"portfolio": portfolio.id}
            )

            for position in positions:
                if portfolio.trading_symbol == position.symbol:
                    continue

                symbol = f"{position.symbol.upper()}/" \
                         f"{portfolio.trading_symbol.upper()}"
                ticker = self._market_data_source_service.get_ticker(
                    symbol=symbol, market=market,
                )
                allocated = allocated + \
                    (position.get_amount() * ticker["bid"])

        return allocated

    def get_unfilled(self, market=None, identifier=None) -> float:

        if self.portfolio_configuration_service.count() > 1 \
                and identifier is None and market is None:
            raise OperationalException(
                "Multiple portfolios found. Please specify a "
                "portfolio identifier."
            )

        if market is not None and identifier is not None:
            portfolio_configurations = self.portfolio_configuration_service \
                .get_all()

        else:
            query_params = {
                "market": market,
                "identifier": identifier
            }
            portfolio_configurations = [self.portfolio_configuration_service
                                        .find(query_params)]

        portfolios = []

        for portfolio_configuration in portfolio_configurations:
            portfolio = self.portfolio_service.find(
                {"identifier": portfolio_configuration.identifier}
            )
            portfolios.append(portfolio)

        unfilled = 0

        for portfolio in portfolios:
            orders = self.order_service.get_all(
                {"status": OrderStatus.OPEN.value, "portfolio": portfolio.id}
            )
            unfilled = unfilled + sum(
                [order.get_amount() * order.get_price() for order in orders]
            )

        return unfilled

    def get_portfolio_configurations(self):
        return self.portfolio_configuration_service.get_all()

    def has_open_buy_orders(self, target_symbol, identifier=None, market=None):
        query_params = {}

        if identifier is not None:
            portfolio = self.portfolio_service.find(
                {"identifier": identifier}
            )
            query_params["portfolio"] = portfolio.id

        if market is not None:
            portfolio = self.portfolio_service.find(
                {"market": market}
            )
            query_params["portfolio"] = portfolio.id

        query_params["target_symbol"] = target_symbol
        query_params["order_side"] = OrderSide.BUY.value
        query_params["status"] = OrderStatus.OPEN.value
        return self.order_service.exists(query_params)

    def has_open_sell_orders(self, target_symbol, identifier=None,
                             market=None):
        query_params = {}

        if identifier is not None:
            portfolio = self.portfolio_service.find(
                {"identifier": identifier}
            )
            query_params["portfolio"] = portfolio.id

        if market is not None:
            portfolio = self.portfolio_service.find(
                {"market": market}
            )
            query_params["portfolio"] = portfolio.id

        query_params["target_symbol"] = target_symbol
        query_params["order_side"] = OrderSide.SELL.value
        query_params["status"] = OrderStatus.OPEN.value
        return self.order_service.exists(query_params)

    def has_open_orders(
        self, target_symbol=None, identifier=None, market=None
    ):
        query_params = {}

        if identifier is not None:
            portfolio = self.portfolio_service.find(
                {"identifier": identifier}
            )
            query_params["portfolio"] = portfolio.id

        if market is not None:
            portfolio = self.portfolio_service.find(
                {"market": market}
            )
            query_params["portfolio"] = portfolio.id

        if target_symbol is not None:
            query_params["target_symbol"] = target_symbol

        query_params["status"] = OrderStatus.OPEN.value
        return self.order_service.exists(query_params)

    def get_trade(
        self,
        target_symbol=None,
        trading_symbol=None,
        market=None,
        portfolio=None,
        status=None,
        order_id=None
    ) -> List[Trade]:
        """
        Function to get all trades. This function will return all trades
        that match the specified query parameters. If the market parameter
        is specified, the trades with the specified market will be returned.

        Args:
            market: The market of the asset
            portfolio: The portfolio of the asset
            status: The status of the trade
            order_id: The order id of the trade
            target_symbol: The symbol of the asset
            trading_symbol: The trading symbol of the asset

        Returns:
            List[Trade]: A list of trades that match the query parameters
        """
        query_params = {}

        if market is not None:
            query_params["market"] = market

        if portfolio is not None:
            query_params["portfolio"] = portfolio

        if status is not None:
            query_params["status"] = status

        if order_id is not None:
            query_params["order_id"] = order_id

        if target_symbol is not None:
            query_params["target_symbol"] = target_symbol

        if trading_symbol is not None:
            query_params["trading_symbol"] = trading_symbol

        return self.trade_service.find(query_params)

    def get_trades(
        self,
        target_symbol=None,
        trading_symbol=None,
        market=None,
        portfolio=None,
        status=None,
    ) -> List[Trade]:
        """
        Function to get all trades. This function will return all trades
        that match the specified query parameters. If the market parameter
        is specified, the trades with the specified market will be returned.

        Args:
            market: The market of the asset
            portfolio: The portfolio of the asset
            status: The status of the trade
            target_symbol: The symbol of the asset
            trading_symbol: The trading symbol of the asset

        Returns:
            List[Trade]: A list of trades that match the query parameters
        """

        query_params = {}

        if market is not None:
            query_params["market"] = market

        if portfolio is not None:
            query_params["portfolio"] = portfolio

        if status is not None:
            query_params["status"] = status

        if target_symbol is not None:
            query_params["target_symbol"] = target_symbol

        if trading_symbol is not None:
            query_params["trading_symbol"] = trading_symbol

        return self.trade_service.get_all({"market": market})

    def get_closed_trades(self) -> List[Trade]:
        """
        Function to get all closed trades. This function will return all
        closed trades of the algorithm.

        Returns:
            List[Trade]: A list of closed trades
        """
        return self.trade_service.get_all({"status": TradeStatus.CLOSED.value})

    def count_trades(
        self,
        target_symbol=None,
        trading_symbol=None,
        market=None,
        portfolio=None
    ) -> int:
        """
        Function to count trades. This function will return the number of
        trades that match the specified query parameters.

        Args:
            target_symbol: The symbol of the asset
            trading_symbol: The trading symbol of the asset
            market: The market of the asset
            portfolio: The portfolio of the asset

        Returns:
            int: The number of trades that match the query parameters
        """

        query_params = {}

        if market is not None:
            query_params["market"] = market

        if portfolio is not None:
            query_params["portfolio"] = portfolio

        if target_symbol is not None:
            query_params["target_symbol"] = target_symbol

        if trading_symbol is not None:
            query_params["trading_symbol"] = trading_symbol

        return self.trade_service.count(query_params)

    def get_open_trades(self, target_symbol=None, market=None) -> List[Trade]:
        """
        Function to get all open trades. This function will return all
        open trades that match the specified query parameters. If the
        target_symbol parameter is specified, the open trades with the
        specified target symbol will be returned. If the market parameter
        is specified, the open trades with the specified market will be
        returned.

        Args:
            target_symbol: The symbol of the asset
            market: The market of the asset

        Returns:
            List[Trade]: A list of open trades that match the query parameters
        """
        return self.trade_service.get_all(
            {
                "status": TradeStatus.OPEN.value,
                "target_symbol": target_symbol,
                "market": market
            }
        )

    def add_stop_loss(self, trade, percentage: int) -> None:
        """
        Function to add a stop loss to a trade. This function will add a
        stop loss to the specified trade. If the stop loss is triggered,
        the trade will be closed.

        Args:
            trade: Trade - The trade to add the stop loss to
            percentage: int - The stop loss of the trade

        Returns:
            None
        """
        self.trade_service.add_stop_loss(trade, percentage=percentage)

    def add_trailing_stop_loss(self, trade, percentage: int) -> None:
        """
        Function to add a trailing stop loss to a trade. This function will
        add a trailing stop loss to the specified trade. If the trailing
        stop loss is triggered, the trade will be closed.

        Args:
            trade: Trade - The trade to add the trailing stop loss to
            trailing_stop_loss: float - The trailing stop loss of the trade

        Returns:
            None
        """
        self.trade_service.add_trailing_stop_loss(trade, percentage=percentage)

    def close_trade(self, trade, precision=None) -> None:
        """
        Function to close a trade. This function will close a trade by
        creating a market order to sell the position. If the precision
        parameter is specified, the amount of the order will be rounded
        down to the specified precision.

        Args:
            trade: Trade - The trade to close
            precision: int - The precision of the amount

        Returns:
            None
        """

        trade = self.trade_service.get(trade.id)

        if TradeStatus.CLOSED.equals(trade.status):
            raise OperationalException("Trade already closed.")

        if trade.remaining <= 0:
            raise OperationalException("Trade has no amount to close.")

        position_id = trade.orders[0].position_id
        portfolio = self.portfolio_service.find({"position": position_id})
        position = self.position_service.find(
            {"portfolio": portfolio.id, "symbol": trade.target_symbol}
        )
        amount = trade.remaining

        if precision is not None:
            amount = RoundingService.round_down(amount, precision)

        if position.get_amount() < amount:
            logger.warning(
                f"Order amount {amount} is larger then amount "
                f"of available {position.symbol} "
                f"position: {position.get_amount()}, "
                f"changing order amount to size of position"
            )
            amount = position.get_amount()

        ticker = self._market_data_source_service.get_ticker(
            symbol=trade.symbol, market=portfolio.market
        )

        self.order_service.create(
            {
                "portfolio_id": portfolio.id,
                "trading_symbol": trade.trading_symbol,
                "target_symbol": trade.target_symbol,
                "amount": amount,
                "order_side": OrderSide.SELL.value,
                "order_type": OrderType.LIMIT.value,
                "price": ticker["bid"],
            }
        )

    def get_number_of_positions(self):
        """
        Returns the number of positions that have a positive amount.

        Returns:
            int: The number of positions
        """
        return self.position_service.count({"amount_gt": 0})

    def has_trading_symbol_position_available(
        self,
        amount_gt=None,
        amount_gte=None,
        percentage_of_portfolio=None,
        market=None
    ):
        """
        Checks if there is a position available for the trading symbol of the
        portfolio. If the amount_gt or amount_gte parameters are specified,
        the amount of the position must be greater than the specified amount.
        If the percentage_of_portfolio parameter is specified, the amount of
        the position must be greater than the net_size of the
        portfolio.

        Parameters:
            amount_gt: The amount of the position must be greater than this
              amount.
        :param amount_gte: The amount of the position must be greater than
        or equal to this amount.
        :param percentage_of_portfolio: The amount of the position must be
        greater than the net_size of the portfolio.
        :param market: The market of the portfolio.
        :return: True if there is a trading symbol position available with the
        specified parameters, False otherwise.
        """
        portfolio = self.portfolio_service.find({"market": market})
        position = self.position_service.find(
            {"portfolio": portfolio.id, "symbol": portfolio.trading_symbol}
        )

        if amount_gt is not None:
            return position.get_amount() > amount_gt

        if amount_gte is not None:
            return position.get_amount() >= amount_gte

        if percentage_of_portfolio is not None:
            net_size = portfolio.get_net_size()
            return position.get_amount() >= net_size \
                * percentage_of_portfolio / 100

        return position.get_amount() > 0

    def strategy(
        self,
        function=None,
        time_unit: TimeUnit = TimeUnit.MINUTE,
        interval=10,
        market_data_sources=None,
    ):
        from .strategy import TradingStrategy

        if function:
            strategy_object = TradingStrategy(
                decorated=function,
                time_unit=time_unit,
                interval=interval,
                market_data_sources=market_data_sources
            )
            self.add_strategy(strategy_object)
        else:

            def wrapper(f):
                self.add_strategy(
                    TradingStrategy(
                        decorated=f,
                        time_unit=time_unit,
                        interval=interval,
                        market_data_sources=market_data_sources,
                        worker_id=f.__name__
                    )
                )
                return f

            return wrapper

    def add_task(self, task):
        if inspect.isclass(task):
            task = task()

        assert isinstance(task, Task), \
            OperationalException(
                "Task object is not an instance of a Task"
            )

        self._tasks.append(task)

    def add_data_sources(self, data_sources):
        self._data_sources = data_sources

    @property
    def tasks(self):
        return self._tasks

    def get_pending_orders(
        self, order_side=None, target_symbol=None, portfolio_id=None
    ):
        """
        Function to get all pending orders of the algorithm. If the
        portfolio_id parameter is specified, the function will return
        all pending orders of the portfolio with the specified id.
        """
        query_params = {}

        if portfolio_id:
            query_params["portfolio"] = portfolio_id

        if target_symbol:
            query_params["target_symbol"] = target_symbol

        if order_side:
            query_params["order_side"] = order_side

        return self.order_service.get_all({"status": OrderStatus.OPEN.value})

    def get_unfilled_buy_value(self):
        """
        Returns the total value of all unfilled buy orders.
        """
        pending_orders = self.get_pending_orders(
            order_side=OrderSide.BUY.value
        )

        return sum(
            [order.get_amount() * order.get_price()
             for order in pending_orders]
        )

    def get_unfilled_sell_value(self):
        """
        Returns the total value of all unfilled buy orders.
        """
        pending_orders = self.get_pending_orders(
            order_side=OrderSide.SELL.value
        )

        return sum(
            [order.get_amount() * order.get_price()
             for order in pending_orders]
        )

    def get_trade_service(self):
        return self.trade_service

    def get_market_data_source_service(self):
        return self._market_data_source_service
