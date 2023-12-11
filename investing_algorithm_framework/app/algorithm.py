import logging
from typing import List

from investing_algorithm_framework.domain import OrderStatus, OrderFee, \
    Position, Order, Portfolio, OrderType, OrderSide, ApiException, \
    BACKTESTING_FLAG, BACKTESTING_INDEX_DATETIME, Trade, \
    TickerMarketDataSource, OHLCVMarketDataSource, OrderBookMarketDataSource

logger = logging.getLogger("investing_algorithm_framework")


class Algorithm:

    def __init__(
        self,
        configuration_service,
        portfolio_configuration_service,
        portfolio_service,
        position_service,
        order_service,
        market_service,
        strategy_orchestrator_service,
    ):
        self.portfolio_service = portfolio_service
        self.position_service = position_service
        self.order_service = order_service
        self.market_service = market_service
        self.configuration_service = configuration_service
        self.portfolio_configuration_service = portfolio_configuration_service
        self.strategy_orchestrator_service = strategy_orchestrator_service
        self._market_data_sources = []
        self._strategies = []

    def start(self, number_of_iterations=None, stateless=False):

        if not stateless:
            self.strategy_orchestrator_service.start(
                algorithm=self,
                number_of_iterations=number_of_iterations
            )

    @property
    def config(self):
        return self.configuration_service.config

    @property
    def running(self) -> bool:
        return self.strategy_orchestrator_service.running

    def run_jobs(self):
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

    def create_limit_order(
            self,
            target_symbol,
            price,
            order_side,
            amount=None,
            percentage_of_portfolio=None,
            percentage_of_position=None,
            precision=None,
            market=None,
            execute=True,
            validate=True,
            sync=True
    ):
        portfolio = self.portfolio_service.find({"market": market})

        if percentage_of_portfolio is not None:
            if not OrderSide.BUY.equals(order_side):
                raise ApiException(
                    "Percentage of portfolio is only supported for BUY orders."
                )

            percentage_of_portfolio = percentage_of_portfolio
            net_size = portfolio.get_net_size()
            size = net_size * percentage_of_portfolio / 100
            amount = size / price

        elif percentage_of_position is not None:

            if not OrderSide.SELL.equals(order_side):
                raise ApiException(
                    "Percentage of position is only supported for SELL orders."
                )

            position = self.position_service.find(
                {
                    "symbol": target_symbol,
                    "portfolio": portfolio.id
                }
            )
            amount = position.get_amount() * (percentage_of_position / 100)

        if precision is not None:
            amount = self.round_down(amount, precision)

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

        if market is None:
            return self.portfolio_service.find({})

        return self.portfolio_service.find({{"market": market}})

    def get_unallocated(self, market=None) -> float:

        if market:
            portfolio = self.portfolio_service.find({{"market": market}})
        else:
            portfolio = self.portfolio_service.find({})

        trading_symbol = portfolio.trading_symbol
        return self.position_service.find(
            {"portfolio": portfolio.id, "symbol": trading_symbol}
        ).get_amount()

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

    def get_order_fee(self, order_id) -> OrderFee:
        return self.order_service.get_order_fee(order_id)

    def get_positions(
            self,
            market=None,
            identifier=None,
            amount_gt=None,
            amount_gte=None,
            amount_lt=None,
            amount_lte=None
    ) -> List[Position]:
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
            raise ApiException("No portfolio found.")

        portfolio = portfolios[0]
        return self.position_service.get_all(
            {"portfolio": portfolio.id}
        )

    def get_position(self, symbol, market=None, identifier=None) -> Position:
        query_params = {}

        if market is not None:
            query_params["market"] = market

        if identifier is not None:
            query_params["identifier"] = identifier

        portfolios = self.portfolio_service.get_all(query_params)

        if not portfolios:
            raise ApiException("No portfolio found.")

        portfolio = portfolios[0]

        try:
            return self.position_service.find(
                {"portfolio": portfolio.id, "symbol": symbol}
            )
        except ApiException:
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
        return self.position_exists(
            symbol,
            market,
            identifier,
            amount_gt,
            amount_gte,
            amount_lt,
            amount_lte
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
            raise ApiException("No portfolio found.")

        portfolio = portfolios[0]
        position = self.position_service.find(
            {"portfolio": portfolio.id, "symbol": symbol}
        )
        full_symbol = f"{position.symbol.upper()}/" \
                      f"{portfolio.trading_symbol.upper()}"
        ticker = self.get_ticker_market_data_source(portfolio.market, full_symbol)\
            .get_data(
                backtest_index_date=self.config
                .get(BACKTESTING_INDEX_DATETIME)
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
            raise ApiException("No portfolio found.")

        portfolio = portfolios[0]
        position = self.position_service.find(
            {"portfolio": portfolio.id, "symbol": symbol}
        )
        net_size = portfolio.get_net_size()
        return (position.cost / net_size) * 100

    def close_position(self, symbol, market=None, identifier=None):
        portfolio = self.portfolio_service.find(
            {"market": market, "identifier": identifier}
        )
        portfolio_config = self.portfolio_configuration_service.find(
            {"portfolio": portfolio.id}
        )
        self.market_service.initialize(portfolio_config)
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
            self.market_service.cancel_order(order.get_external_id())

        symbol = f"{symbol.upper()}/{portfolio.trading_symbol.upper()}"
        ticker = self.get_ticker_market_data_source(portfolio.market, symbol)\
            .get_data(
                backtest_index_date=self.config.get(BACKTESTING_INDEX_DATETIME)
            )
        self.create_limit_order(
            target_symbol=position.symbol,
            amount=position.get_amount(),
            order_side=OrderSide.SELL.value,
            price=ticker["bid"],
        )

    def add_strategies(self, strategies):
        self.strategy_orchestrator_service.add_strategies(strategies)

    def add_tasks(self, tasks):
        self.strategy_orchestrator_service.add_tasks(tasks)

    @property
    def strategies(self):
        return self.strategy_orchestrator_service.get_strategies()

    def get_strategy(self, strategy_id):
        for strategy in self.strategy_orchestrator_service.get_strategies():
            if strategy.worker_id == strategy_id:
                return strategy

        return None

    def get_allocated(self, market=None, identifier=None) -> float:

        if self.portfolio_configuration_service.count() > 1 \
                and identifier is None and market is None:
            raise ApiException(
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
                ticker = self.get_ticker_market_data_source(
                    portfolio.market, symbol
                ).get_data(
                    backtest_index_date=self.config
                    .get(BACKTESTING_INDEX_DATETIME)
                )
                allocated = allocated + \
                    (position.get_amount() * ticker["bid"])

        return allocated

    def get_unfilled(self, market=None, identifier=None) -> float:

        if self.portfolio_configuration_service.count() > 1 \
                and identifier is None and market is None:
            raise ApiException(
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
            unfilled = unfilled \
                       + sum(
                [order.get_amount() * order.get_price() for order in orders])

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

    def has_open_orders(self, target_symbol, identifier=None, market=None):
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
        query_params["status"] = OrderStatus.OPEN.value
        return self.order_service.exists(query_params)

    def check_pending_orders(self):
        self.order_service.check_pending_orders()

    def get_trades(self):
        portfolios = self.portfolio_service.get_all()
        trades = []

        for portfolio in portfolios:
            buy_orders = self.order_service.get_all({
                "status": OrderStatus.CLOSED.value,
                "order_side": OrderSide.BUY.value,
                "portfolio_id": portfolio.id
            })

            for buy_order in buy_orders:
                symbol = buy_order.get_symbol()
                ticker = self.get_ticker_market_data_source(
                    portfolio.market, symbol
                ).get_data(
                    backtest_index_date=self.config
                    .get(BACKTESTING_INDEX_DATETIME)
                )
                trades.append(
                    Trade(
                        buy_order_id=buy_order.id,
                        target_symbol=buy_order.get_target_symbol(),
                        trading_symbol=buy_order.get_trading_symbol(),
                        amount=buy_order.get_amount(),
                        open_price=buy_order.get_price(),
                        closed_price=buy_order.get_trade_closed_price(),
                        closed_at=buy_order.get_trade_closed_at(),
                        opened_at=buy_order.get_created_at(),
                        current_price=ticker["bid"]
                    )
                )

        return trades

    def get_closed_trades(self):
        buy_orders = self.order_service.get_all({
            "status": OrderStatus.CLOSED.value,
            "order_side": OrderSide.BUY.value
        })
        return [
            Trade(
                buy_order_id=order.id,
                target_symbol=order.get_target_symbol(),
                trading_symbol=order.get_trading_symbol(),
                amount=order.get_amount(),
                open_price=order.get_price(),
                closed_price=order.get_trade_closed_price(),
                closed_at=order.get_trade_closed_at(),
                opened_at=order.get_created_at()
            ) for order in buy_orders
            if order.get_trade_closed_at() is not None
        ]

    def round_down(self, value, decimals):
        factor = 1 / (10 ** decimals)
        return (value // factor) * factor

    def get_open_trades(self, target_symbol=None):
        portfolios = self.portfolio_service.get_all()
        trades = []
        for portfolio in portfolios:

            if target_symbol is not None:
                buy_orders = self.order_service.get_all({
                    "status": OrderStatus.CLOSED.value,
                    "order_side": OrderSide.BUY.value,
                    "portfolio_id": portfolio.id,
                    "target_symbol": target_symbol
                })
            else:
                buy_orders = self.order_service.get_all({
                    "status": OrderStatus.CLOSED.value,
                    "order_side": OrderSide.BUY.value,
                    "portfolio_id": portfolio.id
                })
            buy_orders = [
                buy_order for buy_order in buy_orders
                if buy_order.get_trade_closed_at() is None
            ]
            sell_orders = self.order_service.get_all({
                "status": OrderStatus.OPEN.value,
                "order_side": OrderSide.SELL.value,
                "portfolio_id": portfolio.id
            })
            sell_amount = sum([order.get_amount() for order in sell_orders])

            # Subtract the amount of the open sell orders
            # from the amount of the buy orders
            while sell_amount > 0 and len(buy_orders) > 0:
                first_order = buy_orders[0]

                if first_order.get_available_amount() > sell_amount:
                    first_order.set_available_amount(
                        first_order.get_available_amount() - sell_amount
                    )
                    sell_amount = 0
                else:
                    sell_amount = sell_amount - first_order.get_available_amount()
                    buy_orders.pop(0)

            for buy_order in buy_orders:
                symbol = buy_order.get_symbol()

                try:
                    ticker = self.get_ticker_market_data_source(
                        portfolio.market, symbol
                    ).get_data(
                        backtest_index_date=self.config
                        .get(BACKTESTING_INDEX_DATETIME)
                    )
                except Exception as e:
                    logger.error(e)
                    raise ApiException(
                        f"Error getting ticker data for "
                        f"trade {buy_order.get_target_symbol()}"
                        f"-{buy_order.get_trading_symbol()}. Make sure you "
                        f"have registered a ticker market data source for "
                        f"{buy_order.get_target_symbol()}"
                        f"-{buy_order.get_trading_symbol()} "
                        f"for market {portfolio.market}"
                    )
                trades.append(
                    Trade(
                        buy_order_id=buy_order.id,
                        target_symbol=buy_order.get_target_symbol(),
                        trading_symbol=buy_order.get_trading_symbol(),
                        amount=buy_order.get_amount(),
                        open_price=buy_order.get_price(),
                        opened_at=buy_order.get_created_at(),
                        current_price=ticker["bid"]
                    )
                )

        return trades

    def close_trade(self, trade):

        if trade.closed_at is not None:
            raise ApiException("Trade already closed.")

        order = self.order_service.get(trade.buy_order_id)

        if order.get_filled() <= 0:
            raise ApiException(
                "Buy order belonging to the trade has no amount."
            )

        portfolio = self.portfolio_service\
            .find({"position": order.position_id})
        position = self.get_position(order.get_target_symbol())
        amount = order.get_amount()

        if position.get_amount() < amount:
            logger.warning(
                f"Order amount {amount} is larger then amount "
                f"of available {position.symbol} "
                f"position: {position.get_amount()}, "
                f"changing order amount to size of position"
            )
            amount = position.get_amount()

        symbol = f"{order.get_target_symbol().upper()}" \
                 f"/{order.get_trading_symbol().upper()}"
        ticker = self.get_ticker_market_data_source(portfolio.market, symbol)\
            .get_data(
                backtest_index_date=self.config
                .get(BACKTESTING_INDEX_DATETIME)
            )
        self.create_limit_order(
            target_symbol=order.target_symbol,
            amount=amount,
            order_side=OrderSide.SELL.value,
            price=ticker["bid"],
        )

    def get_market_data_sources(self):
        market_data_sources = []

        for key in self._market_data_sources.keys():
            market_data_sources.append(self._market_data_sources[key])

        return market_data_sources

    def get_market_data_source(self, identifier):

        if identifier in self._market_data_sources:
            return self._market_data_sources[identifier]

        raise ApiException(
            f"No market data source found for with identifier {identifier}."
        )

    def set_market_data_sources(self, market_data_sources):
        self._market_data_sources = {}

        for market_data_source in market_data_sources:
            self._market_data_sources[market_data_source.identifier] = \
                market_data_source

    def get_ticker_market_data_source(self, market, symbol):

        for identifier in self._market_data_sources:
            market_data_source = self._market_data_sources[identifier]

            if isinstance(market_data_source, TickerMarketDataSource):

                if market_data_source.symbol == symbol \
                        and market_data_source.market == market:
                    return market_data_source

        raise ApiException(
            f"No ticker market data source found for with symbol {symbol} "
            f"and market {market}."
        )

    def get_ohlcv_market_data_source(self, market, symbol):

        for market_data_source in self._market_data_sources.values():

            if isinstance(market_data_source, OHLCVMarketDataSource):

                if market_data_source.symbol == symbol \
                        and market_data_source.market == market:
                    return market_data_source

        raise ApiException(
            f"No OHLCV market data source found for with symbol {symbol} "
            f"and market {market}."
        )

    def get_order_book_market_data_source(self, market, symbol):

        for market_data_source in self._market_data_sources.values():

            if isinstance(market_data_source, OrderBookMarketDataSource):

                if market_data_source.symbol == symbol \
                        and market_data_source.market == market:
                    return market_data_source

        raise ApiException(
            f"No OHLCV market data source found for with symbol {symbol} "
            f"and market {market}."
        )
