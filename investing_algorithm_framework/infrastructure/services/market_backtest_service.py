import logging
from datetime import datetime

import ccxt

from investing_algorithm_framework.domain import OperationalException
from .market_service import MarketService

logger = logging.getLogger("investing_algorithm_framework")


class MarketBacktestService(MarketService):

    def initialize(self, portfolio_configuration):
        self._market = portfolio_configuration.market

        if not hasattr(ccxt, self.market):
            raise OperationalException(
                f"No market service found for market id {self.market}"
            )

        self.exchange_class = getattr(ccxt, self.market)

        if self.exchange_class is None:
            raise OperationalException(
                f"No market service found for market id {self.market}"
            )

        self.exchange = self.exchange_class({})

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
