from typing import List

from investing_algorithm_framework.core.models.order import Order
from investing_algorithm_framework.core.models.order_status import OrderStatus
from investing_algorithm_framework.core.models.position import Position
from investing_algorithm_framework.core.models.snapshots import AssetPrice


class CCXTPortfolioManagerMixin:

    def get_orders(
        self, symbol, since=None, algorithm_context=None, **kwargs
    ) -> List[Order]:
        market_service = algorithm_context.get_market_service(
            market=self.market,
            api_key=self.api_key,
            secret_key=self.secret_key
        )
        ccxt_orders = market_service.get_orders(symbol=symbol, since=since)
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
                    "price": ccxt_order["price"],
                    "initial_price": ccxt_order["price"],
                    "closing_price": ccxt_order["price"],
                    "type": ccxt_order["type"],
                    "side": ccxt_order["side"]
                }
            )
            orders.append(order)
        return orders

    def get_positions(
        self, algorithm_context=None, **kwargs
    ) -> List[Position]:
        market_service = algorithm_context.get_market_service(
            market=self.market,
            api_key=self.api_key,
            secret_key=self.secret_key
        )
        balances = market_service.get_balance()
        positions = []

        for balance in balances["free"]:

            if balances[balance]["free"] > 0:
                position = Position.from_dict(
                    {
                        "target_symbol": balance,
                        "amount": balances[balance]["free"]
                    }
                )
                positions.append(position)
        return positions

    def get_prices(
        self, symbols, algorithm_context, **kwargs
    ) -> List[AssetPrice]:
        market_service = algorithm_context.get_market_service(
            market=self.market,
            api_key=self.api_key,
            secret_key=self.secret_key
        )
        return market_service.get_prices(symbols)
