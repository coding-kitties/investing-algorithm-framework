import logging
from typing import List

from investing_algorithm_framework.services import ConfigurationService, \
    MarketCredentialService, MarketDataSourceService, \
    OrderService, PortfolioConfigurationService, PortfolioService, \
    PositionService, TradeService
from investing_algorithm_framework.domain import OrderStatus, OrderType, \
    OrderSide, OperationalException, Portfolio, RoundingService, \
    BACKTESTING_FLAG, BACKTESTING_INDEX_DATETIME, TradeRiskType, Order, \
    Position, Trade, TradeStatus, MarketService, MarketCredential

logger = logging.getLogger("investing_algorithm_framework")


class Context:
    """
    Context class to store the state of the algorithm and
    give access to objects such as orders, positions, trades and
    portfolio.
    """

    def __init__(
        self,
        configuration_service: ConfigurationService,
        portfolio_configuration_service: PortfolioConfigurationService,
        portfolio_service: PortfolioService,
        position_service: PositionService,
        order_service: OrderService,
        market_credential_service: MarketCredentialService,
        market_data_source_service: MarketDataSourceService,
        market_service: MarketService,
        trade_service: TradeService,
    ):
        self.configuration_service: ConfigurationService = \
            configuration_service
        self.portfolio_configuration_service: PortfolioConfigurationService = \
            portfolio_configuration_service
        self.portfolio_service: PortfolioService = portfolio_service
        self.position_service: PositionService = position_service
        self.order_service: OrderService = order_service
        self.market_credential_service: MarketCredentialService = \
            market_credential_service
        self.market_data_source_service: MarketDataSourceService = \
            market_data_source_service
        self.market_service: MarketService = market_service
        self.trade_service: TradeService = trade_service

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
    ) -> Order:
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
    ) -> Order:
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

        logger.info(
            f"Creating limit order: {target_symbol} "
            f"{order_side} {amount} @ {price}"
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

        return self.portfolio_service.find({"market": market})

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
        ticker = self.market_data_source_service.get_ticker(
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
        self, position=None, symbol=None, portfolio=None, precision=None
    ) -> Order:
        """
        Function to close a position. This function will close a position
        by creating a market order to sell the position. If the precision
        parameter is specified, the amount of the order will be rounded
        down to the specified precision.

        Args:
            position (Optional): The position to close
            symbol (Optional): The symbol of the asset
            portfolio (Optional): The portfolio where the position is located
            precision (Optional): The precision of the amount

        Returns:
            Order: The order created to close the position
        """
        query_params = {}

        if position is None and (symbol is None and portfolio is None):
            raise OperationalException(
                "Either position or symbol and portfolio parameters must "
                "be specified to close a position."
            )

        if position is not None:
            query_params["id"] = position.id
            query_params["symbol"] = position.symbol

        if symbol is not None:
            query_params["symbol"] = symbol

        if portfolio is not None:
            query_params["portfolio"] = portfolio.id

        position = self.position_service.find(query_params)
        portfolio = self.portfolio_service.get(position.portfolio_id)

        if position.get_amount() == 0:
            logger.warning("Cannot close position. Amount is 0.")
            return None

        if position.get_symbol() == portfolio.get_trading_symbol():
            raise OperationalException(
                "Cannot close position. The position is the same as the "
                "trading symbol of the portfolio."
            )

        for order in self.order_service \
                .get_all(
                    {
                        "position": position.id,
                        "status": OrderStatus.OPEN.value
                    }
                ):
            self.order_service.cancel_order(order)

        target_symbol = position.get_symbol()
        symbol = f"{target_symbol.upper()}/{portfolio.trading_symbol.upper()}"
        ticker = self.market_data_source_service.get_ticker(
            symbol=symbol, market=portfolio.market
        )
        logger.info(
            f"Closing position {position.symbol} "
            f"with amount {position.get_amount()} "
            f"at price {ticker['bid']}"
        )
        return self.create_limit_order(
            target_symbol=position.symbol,
            amount=position.get_amount(),
            order_side=OrderSide.SELL.value,
            price=ticker["bid"],
            precision=precision,
        )

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
                ticker = self.market_data_source_service.get_ticker(
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

    def get_sell_orders(self, target_symbol, identifier=None, market=None):
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
        return self.order_service.get_all(query_params)

    def get_open_orders(
        self, target_symbol=None, identifier=None, market=None
    ) -> List[Order]:
        """
        Function to get all open orders. This function will return all
        open orders that match the specified query parameters.

        Args:
            target_symbol (str): the symbol of the asset
            identifier (str): the identifier of the portfolio
            market (str): the market of the asset

        Returns:
            List[Order]: A list of open orders that match the query parameters
        """
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
        return self.order_service.get_all(query_params)

    def get_closed_orders(
        self, target_symbol=None, identifier=None, market=None, order_side=None
    ) -> List[Order]:
        """
        Function to get all closed orders. This function will return all
        closed orders that match the specified query parameters.

        Args:
            target_symbol (str): the symbol of the asset
            identifier (str): the identifier of the portfolio
            market (str): the market of the asset
            order_side (str): the side of the order

        Returns:
            List[Order]: A list of closed orders that
                match the query parameters
        """
        query_params = {}

        if identifier is not None:
            portfolio = self.portfolio_service.find(
                {"identifier": identifier}
            )
            query_params["portfolio"] = portfolio.id

        if order_side is not None:
            query_params["order_side"] = order_side

        if market is not None:
            portfolio = self.portfolio_service.find(
                {"market": market}
            )
            query_params["portfolio"] = portfolio.id

        if target_symbol is not None:
            query_params["target_symbol"] = target_symbol

        query_params["status"] = OrderStatus.CLOSED.value
        return self.order_service.get_all(query_params)

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

    def get_pending_trades(
            self, target_symbol=None, market=None
    ) -> List[Trade]:
        """
        Function to get all pending trades. This function will return all
        pending trades that match the specified query parameters. If the
        target_symbol parameter is specified, the pending trades with the
        specified target symbol will be returned. If the market parameter
        is specified, the pending trades with the specified market will be
        returned.

        Args:
            target_symbol: The symbol of the asset
            market: The market of the asset

        Returns:
            List[Trade]: A list of pending trades that match
                the query parameters
        """
        return self.trade_service.get_all(
            {
                "status": TradeStatus.CREATED.value,
                "target_symbol": target_symbol,
                "market": market
            }
        )

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

    def add_stop_loss(
        self,
        trade,
        percentage: float,
        trade_risk_type=TradeRiskType.FIXED,
        sell_percentage: float = 100,
    ):
        """
        Function to add a stop loss to a trade.

        Example of fixed stop loss:
            * You buy BTC at $40,000.
            * You set a SL of 5% → SL level at $38,000 (40,000 - 5%).
            * BTC price increases to $42,000 → SL level remains at $38,000.
            * BTC price drops to $38,000 → SL level reached, trade closes.

        Example of trailing stop loss:
            * You buy BTC at $40,000.
            * You set a TSL of 5%, setting the sell price at $38,000.
            * BTC price increases to $42,000 → New TSL level
                at $39,900 (42,000 - 5%).
            * BTC price drops to $39,900 → SL level reached, trade closes.

        Args:
            trade: Trade object representing the trade
            percentage: float representing the percentage of the open price
                that the stop loss should be set at
            trade_risk_type: The type of the stop loss, fixed
                or trailing
            sell_percentage: float representing the percentage of the trade
                that should be sold if the stop loss is triggered

        Returns:
            None
        """
        self.trade_service.add_stop_loss(
            trade,
            percentage=percentage,
            trade_risk_type=trade_risk_type,
            sell_percentage=sell_percentage,
        )
        return self.trade_service.get(trade.id)

    def add_take_profit(
        self,
        trade,
        percentage: float,
        trade_risk_type=TradeRiskType.FIXED,
        sell_percentage: float = 100,
    ) -> None:
        """
        Function to add a take profit to a trade. This function will add a
        take profit to the specified trade. If the take profit is triggered,
        the trade will be closed.

        Example of take profit:
            * You buy BTC at $40,000.
            * You set a TP of 5% → TP level at $42,000 (40,000 + 5%).
            * BTC rises to $42,000 → TP level reached, trade
                closes, securing profit.

        Example of trailing take profit:
            * You buy BTC at $40,000
            * You set a TTP of 5%, setting the sell price at $42,000.
            * BTC rises to $42,000 → TTP level stays at $42,000.
            * BTC rises to $45,000 → New TTP level at $42,750.
            * BTC drops to $42,750 → Trade closes, securing profit.

        Args:
            trade: Trade object representing the trade
            percentage: float representing the percentage of the open price
                that the stop loss should be set at
            trade_risk_type: The type of the stop loss, fixed
                or trailing
            sell_percentage: float representing the percentage of the trade
                that should be sold if the stop loss is triggered

        Returns:
            None
        """
        self.trade_service.add_take_profit(
            trade,
            percentage=percentage,
            trade_risk_type=trade_risk_type,
            sell_percentage=sell_percentage,
        )
        return self.trade_service.get(trade.id)

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

        if trade.available_amount <= 0:
            raise OperationalException("Trade has no amount to close.")

        position_id = trade.orders[0].position_id
        portfolio = self.portfolio_service.find({"position": position_id})
        position = self.position_service.find(
            {"portfolio": portfolio.id, "symbol": trade.target_symbol}
        )
        amount = trade.available_amount

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

        ticker = self.market_data_source_service.get_ticker(
            symbol=trade.symbol, market=portfolio.market
        )

        logger.info(f"Closing trade {trade.id} {trade.symbol}")
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
            [order.get_remaining() * order.get_price()
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
            [order.get_remaining() * order.get_price()
             for order in pending_orders]
        )

    def get_market_credential(self, market) -> MarketCredential:
        """
        Function to get the market credential for a given market.

        Args:
            market: The market to get the credential for

        Returns:
            MarketCredential: The market credential for the given market
        """
        return self.market_credential_service.get(market)

    def get_market_credentials(self) -> List[MarketCredential]:
        """
        Function to get all market credentials.

        Returns:
            List[MarketCredential]: A list of all market credentials
        """
        return self.market_credential_service.get_all()
