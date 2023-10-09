import logging
from math import floor
from typing import List
from decimal import Decimal

from investing_algorithm_framework.domain import OrderStatus, OrderFee, \
    Position, Order, Portfolio, OrderType, OrderSide, ApiException, \
    parse_decimal_to_string

logger = logging.getLogger("investing_algorithm_framework")


class Algorithm:

    def __init__(
        self,
        portfolio_configuration_service,
        portfolio_service,
        position_service,
        order_service,
        market_service,
        market_data_service,
        strategy_orchestrator_service
    ):
        self.portfolio_service = portfolio_service
        self.position_service = position_service
        self.order_service = order_service
        self.market_service = market_service
        self._config = None
        self.portfolio_configuration_service = portfolio_configuration_service
        self.strategy_orchestrator_service = strategy_orchestrator_service
        self.market_data_service = market_data_service

    def start(self, number_of_iterations=None, stateless=False):

        if not stateless:
            self.strategy_orchestrator_service.start(
                algorithm=self,
                number_of_iterations=number_of_iterations
            )

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

    @property
    def running(self) -> bool:
        return self.strategy_orchestrator_service.running

    def run_jobs(self):
        self.strategy_orchestrator_service.run_pending_jobs()

    def create_order(
        self,
        target_symbol,
        price,
        type,
        side,
        amount,
        market=None,
        execute=True,
        validate=True,
        sync=True
    ):
        portfolio = self.portfolio_service.find({"market": market})
        return self.order_service.create(
            {
                "target_symbol": target_symbol,
                "price": price,
                "amount": parse_decimal_to_string(amount),
                "order_type": type,
                "side": side,
                "portfolio_id": portfolio.id,
                "status": OrderStatus.CREATED.value,
                "trading_symbol": portfolio.trading_symbol,
            },
            execute=execute,
            validate=validate,
            sync=sync
        )

    def create_limit_order(
        self,
        target_symbol,
        price,
        side,
        amount=None,
        percentage_of_portfolio=None,
        percentage_of_position=None,
        market=None,
        execute=True,
        validate=True,
        sync=True
    ):
        portfolio = self.portfolio_service.find({"market": market})

        if percentage_of_portfolio is not None and OrderSide.BUY.equals(side):
            size = float(portfolio.net_size) * (percentage_of_portfolio / 100)
            amount = floor(size / price)

        if percentage_of_position is not None and OrderSide.SELL.equals(side):
            position = self.position_service.find(
                {
                    "symbol": target_symbol,
                    "portfolio": portfolio.id
                }
            )
            amount = position.get_amount() * \
                     (Decimal(percentage_of_position) / 100)

        return self.order_service.create(
            {
                "target_symbol": target_symbol,
                "price": price,
                "amount": amount,
                "order_type": OrderType.LIMIT.value,
                "side": OrderSide.from_value(side).value,
                "portfolio_id": portfolio.id,
                "status": OrderStatus.CREATED.value,
                "trading_symbol": portfolio.trading_symbol,
            },
            execute=execute,
            validate=validate,
            sync=sync
        )

    def create_market_order(
        self,
        target_symbol,
        side,
        amount,
        market=None,
        execute=False,
        validate=False,
        sync=True
    ):
        portfolio = self.portfolio_service.find({"market": market})
        return self.order_service.create(
            {
                "target_symbol": target_symbol,
                "amount": amount,
                "order_type": OrderType.MARKET.value,
                "side": OrderSide.from_value(side).value,
                "portfolio_id": portfolio.id,
                "status": OrderStatus.CREATED.value,
                "trading_symbol": portfolio.trading_symbol,
            },
            execute=execute,
            validate=validate,
            sync=sync
        )

    def get_portfolio(self, market=None) -> Portfolio:

        if market is None:
            return self.portfolio_service.find({})

        return self.portfolio_service.find({{"market": market}})

    def get_unallocated(self, market=None) -> Position:

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
        side=None,
        type=None
    ) -> Order:
        query_params = {}

        if reference_id:
            query_params["reference_id"] = reference_id

        if target_symbol:
            query_params["target_symbol"] = target_symbol

        if trading_symbol:
            query_params["trading_symbol"] = trading_symbol

        if side:
            query_params["side"] = side

        if type:
            query_params["type"] = type

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
            type=None,
            side=None,
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
                "type": type,
                "side": side
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

    def get_position_percentage(
            self, symbol, market=None, identifier=None
    ) -> float:
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
        ticker = self.market_service.get_ticker(
            f"{symbol.upper()}/{portfolio.trading_symbol.upper()}"
        )
        return (position.amount * ticker["bid"] /
                self.get_allocated(identifier=portfolio.identifier)) * 100

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

        for order in self.order_service\
                .get_all({
                    "position": position.id, "status": OrderStatus.OPEN.value
                }):
            self.market_service.cancel_order(order.id)

        ticker = self.market_service.get_ticker(
            symbol=f"{symbol.upper()}/{portfolio.trading_symbol.upper()}"
        )
        self.create_limit_order(
            target_symbol=position.symbol,
            amount=position.get_amount(),
            side=OrderSide.SELL.value,
            price=parse_decimal_to_string(ticker["bid"]),
        )

    def add_strategies(self, strategies):
        self.strategy_orchestrator_service.add_strategies(strategies)

    def add_tasks(self, tasks):
        self.strategy_orchestrator_service.add_tasks(tasks)

    def get_allocated(self, market=None, identifier=None) -> float:

        if self.portfolio_configuration_service.count() > 1 \
                and identifier is None and market is None:
            raise ApiException(
                "Multiple portfolios found. Please specify a "
                "portfolio identifier."
            )

        if market is not None and identifier is not None:
            portfolio_configurations = self.portfolio_configuration_service\
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
                self.market_service.initialize(portfolio.configuration)
                price = self.market_service.get_ticker(symbol)
                allocated = allocated + \
                            (position.get_amount() * Decimal(price["bid"]))

        return allocated

    def get_unfilled(self, market=None, identifier=None) -> float:

        if self.portfolio_configuration_service.count() > 1 \
                and identifier is None and market is None:
            raise ApiException(
                "Multiple portfolios found. Please specify a "
                "portfolio identifier."
            )

        if market is not None and identifier is not None:
            portfolio_configurations = self.portfolio_configuration_service\
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
                       + sum([order.get_amount() * order.get_price() for order in orders])

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
        query_params["side"] = OrderSide.BUY.value
        query_params["status"] = OrderStatus.OPEN.value
        return self.order_service.exists(query_params)

    def has_open_sell_orders(self, target_symbol, identifier=None, market=None):
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
        query_params["side"] = OrderSide.SELL.value
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
