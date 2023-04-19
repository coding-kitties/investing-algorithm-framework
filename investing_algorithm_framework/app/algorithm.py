import logging
from typing import List

from investing_algorithm_framework.domain import OrderStatus, \
    Position, Order, Portfolio, OrderType, \
    OrderSide, ApiException

logger = logging.getLogger(__name__)


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

    def run_strategies(self):
        self.strategy_orchestrator_service.run_pending_strategies()

    def create_order(
        self,
        target_symbol,
        price,
        type,
        side,
        amount_target_symbol=None,
        amount_trading_symbol=None,
        market=None,
        execute=False,
        validate=False
    ):
        portfolio = self.portfolio_service.find({"market": market})
        return self.order_service.create(
            {
                "target_symbol": target_symbol,
                "price": price,
                "amount_target_symbol": amount_target_symbol,
                "amount_trading_symbol": amount_trading_symbol,
                "type": type,
                "side": side,
                "portfolio_id": portfolio.id,
                "status": OrderStatus.PENDING.value,
                "trading_symbol": portfolio.trading_symbol,
            },
            execute=execute,
            validate=validate
        )

    def create_limit_order(
            self,
            target_symbol,
            price,
            side,
            amount_target_symbol=None,
            amount_trading_symbol=None,
            market=None,
            execute=True,
            validate=True
    ):
        portfolio = self.portfolio_service.find({"market": market})
        return self.order_service.create(
            {
                "target_symbol": target_symbol,
                "price": price,
                "amount_target_symbol": amount_target_symbol,
                "amount_trading_symbol": amount_trading_symbol,
                "type": OrderType.LIMIT.value,
                "side": OrderSide.from_value(side).value,
                "portfolio_id": portfolio.id,
                "status": OrderStatus.PENDING.value,
                "trading_symbol": portfolio.trading_symbol,
            },
            execute=execute,
            validate=validate
        )

    def create_market_order(
        self,
        target_symbol,
        side,
        amount_target_symbol=None,
        amount_trading_symbol=None,
        market=None,
        execute=False,
        validate=False
    ):
        portfolio = self.portfolio_service.find({"market": market})
        return self.order_service.create(
            {
                "target_symbol": target_symbol,
                "amount_target_symbol": amount_target_symbol,
                "amount_trading_symbol": amount_trading_symbol,
                "type": OrderType.MARKET.value,
                "side": OrderSide.from_value(side).value,
                "portfolio_id": portfolio.id,
                "status": OrderStatus.PENDING.value,
                "trading_symbol": portfolio.trading_symbol,
            },
            execute=execute,
            validate=validate
        )

    def check_order_status(self, market=None, symbol=None, status=None):
        portfolio = self.portfolio_service.get({"market": market})
        orders = self.order_service \
            .get_all({"target_symbol": symbol, "status": status})
        self.order_service.check_order_status(portfolio, orders)

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
            {"portfolio": portfolio.identifier, "symbol": trading_symbol}
        ).amount

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
            positions = self.position_service.get_all({"portfolio": portfolio.id})
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

    def get_positions(self, market=None) -> List[Position]:
        portfolio = self.portfolio_service.find({{"market": market}})
        return self.position_service.get_all({"portfolio": portfolio.id})

    def get_position(self, symbol, market=None) -> Position:
        portfolio = self.portfolio_service.find({"market": market})
        return self.position_service.find(
            {"portfolio": portfolio.id, "symbol": symbol}
        )

    def add_strategies(self, strategies):
        self.strategy_orchestrator_service.add_strategies(strategies)

    def get_allocated(self, portfolio_identifier=None) -> float:

        if self.portfolio_configuration_service.count() > 1 \
                and portfolio_identifier is None:
            raise ApiException(
                "Multiple portfolios found. Please specify a "
                "portfolio identifier."
            )

        if portfolio_identifier is None:
            portfolios = self.portfolio_service.get_all()
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
                    self.market_service.market = portfolio.market
                    price = self.market_service.get_ticker(symbol)
                    allocated = allocated + (position.amount * price["ask"])

            return allocated
        else:
            portfolio = self.portfolio_service.find(
                {"identifier": portfolio_identifier}
            )
            allocated = 0
            positions = self.position_service.get_all(
                {"portfolio": portfolio.id}
            )

            for position in positions:
                if portfolio.trading_symbol == position.symbol:
                    continue

                symbol = f"{position.symbol.upper()}/" \
                         f"{portfolio.trading_symbol.upper()}"
                self.market_service.market = portfolio.market
                price = self.market_service.get_ticker(symbol)
                allocated = allocated + (position.amount * price["ask"])

            return allocated
