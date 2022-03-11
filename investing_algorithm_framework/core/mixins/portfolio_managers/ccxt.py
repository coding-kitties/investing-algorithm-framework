from datetime import datetime
from typing import List
from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.models.position import Position
from investing_algorithm_framework.core.models.order import Order
from investing_algorithm_framework.core.models.order_status import OrderStatus
from investing_algorithm_framework.core.models.snapshots import AssetPrice


class CCXTPortfolioManagerMixin:

    def get_orders(
            self, symbol, since: datetime = None, algorithm_context=None
    ) -> List[Order]:
        market_service = algorithm_context.get_market_service(self.identifier)
        ccxt_orders = market_service.get_orders(symbol, since)
        orders = []

        for ccxt_order in ccxt_orders:
            status = OrderStatus.PENDING.value

            if ccxt_order["status"] == "open":
                status = OrderStatus.PENDING.value
            if ccxt_order["status"] == "closed":
                status = OrderStatus.CLOSED.value
            if ccxt_order["status"] == "canceled":
                status = OrderStatus.CANCELED.value
            if ccxt_order["status"] == "expired":
                status = OrderStatus.FAILED.value
            if ccxt_order["status"] == "rejected":
                status = OrderStatus.FAILED.value

            order = Order.from_dict(
                {
                    "reference_id": ccxt_order["id"],
                    "target_symbol": ccxt_order["symbol"].split("/")[0],
                    "trading_symbol": ccxt_order["symbol"].split("/")[1],
                    "amount_target_symbol": ccxt_order["amount"],
                    "status": status,
                    "price":  ccxt_order["price"],
                    "initial_price": ccxt_order["price"],
                    "closing_price": ccxt_order["price"],
                    "type": ccxt_order["type"],
                    "side": ccxt_order["side"]
                }
            )
            orders.append(order)
        return orders

    def get_positions(self, algorithm_context) -> List[Position]:
        market_service = algorithm_context.get_market_service(self.identifier)
        binance_balances = market_service.get_balances()
        positions = []

        for binance_balance in binance_balances["free"]:

            if binance_balances[binance_balance]["free"] > 0:
                position = Position.from_dict(
                    {
                        "target_symbol": binance_balance,
                        "amount": binance_balances[binance_balance]["free"]
                    }
                )
                positions.append(position)
        return positions

    def get_prices(
        self, symbols, algorithm_context, **kwargs
    ) -> List[AssetPrice]:
        market_service = algorithm_context.get_market_service(BINANCE)
        return market_service.get_prices(symbols)
