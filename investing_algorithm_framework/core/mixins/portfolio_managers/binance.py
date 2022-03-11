from typing import List
from investing_algorithm_framework.configuration.constants import BINANCE
from investing_algorithm_framework.core.models.position import Position
from investing_algorithm_framework.core.models.order import Order
from investing_algorithm_framework.core.models.order_status import OrderStatus
from investing_algorithm_framework.core.models.snapshots import AssetPrice


class BinancePortfolioManagerMixin:

    def get_orders(
            self, symbol, algorithm_context
    ) -> List[Order]:
        market_service = algorithm_context.get_market_service(BINANCE)
        binance_orders = market_service.get_orders(symbol)
        orders = []

        for binance_order in binance_orders:
            status = OrderStatus.PENDING.value

            if binance_order["status"] == "open":
                status = OrderStatus.PENDING.value
            if binance_order["status"] == "closed":
                status = OrderStatus.CLOSED.value
            if binance_order["status"] == "canceled":
                status = OrderStatus.CANCELED.value
            if binance_order["status"] == "expired":
                status = OrderStatus.FAILED.value
            if binance_order["status"] == "rejected":
                status = OrderStatus.FAILED.value

            order = Order.from_dict(
                {
                    "reference_id": binance_order["id"],
                    "target_symbol": binance_order["symbol"].split("/")[0],
                    "trading_symbol": binance_order["symbol"].split("/")[1],
                    "amount_target_symbol": binance_order["amount"],
                    "status": status,
                    "price":  binance_order["price"],
                    "initial_price": binance_order["price"],
                    "closing_price": binance_order["price"],
                    "type": binance_order["type"],
                    "side": binance_order["side"]
                }
            )
            orders.append(order)
        return orders

    def get_positions(self, algorithm_context) -> List[Position]:
        market_service = algorithm_context.get_market_service(BINANCE)
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
