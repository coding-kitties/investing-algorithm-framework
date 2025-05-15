from logging import getLogger

import ccxt

from investing_algorithm_framework.domain import OrderExecutor, \
    OperationalException, Order, OrderStatus, OrderSide, OrderType, \
    MarketCredential

logger = getLogger("investing_algorithm_framework")


class CCXTOrderExecutor(OrderExecutor):
    """
    CCXTOrderExecutor is a class that implements the OrderExecutor
    interface for executing orders using the CCXT library.
    """

    def execute_order(self, portfolio, order, market_credential) -> Order:
        """
        Executes an order for a given portfolio on a CCXT exchange.

        Args:
            order: The order to be executed
            portfolio: The portfolio in which the order will be executed
            market_credential: The market credential to use for the order

        Returns:
            Order: Instance of the executed order. The order instance
            should copy the id of the order that has been provided as a
        """
        market = portfolio.market
        exchange = self.initialize_exchange(market, market_credential)
        symbol = order.get_symbol()
        amount = order.get_amount()
        price = order.get_price()
        order_type = order.get_order_type()
        order_side = order.get_order_side()

        try:
            if OrderType.LIMIT.equals(order_type):
                if OrderSide.BUY.equals(order_side):

                    # Check if the exchange supports the
                    # createLimitBuyOrder method
                    if not hasattr(exchange, "createLimitBuyOrder"):
                        raise OperationalException(
                            f"Exchange {market} does not support "
                            f"functionality createLimitBuyOrder"
                        )

                    # Create a limit buy order
                    external_order = exchange.createLimitBuyOrder(
                        symbol, amount, price,
                    )
                else:
                    # Check if the exchange supports
                    # the createLimitSellOrder method
                    if not hasattr(exchange, "createLimitSellOrder"):
                        raise OperationalException(
                            f"Exchange {market} does not support "
                            f"functionality createLimitSellOrder"
                        )

                    # Create a limit sell order
                    external_order = exchange.createLimitSellOrder(
                        symbol, amount, price,
                    )
            else:
                raise OperationalException(
                    f"Order type {order_type} not supported "
                    f"by CCXT OrderExecutor"
                )

            external_order = Order.from_ccxt_order(external_order)
            external_order.id = order.id
            return external_order
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not create limit buy order")

    def cancel_order(self, portfolio, order, market_credential) -> Order:
        """
        Cancels an order for a given portfolio on a CCXT exchange.

        Args:
            order: The order to be canceled
            portfolio: The portfolio in which the order was executed
            market_credential: The market credential to use for the order

        Returns:
            Order: Instance of the canceled order.
        """
        market = portfolio.market
        exchange = self.initialize_exchange(market, market_credential)

        if not exchange.has['cancelOrder']:
            raise OperationalException(
                f"Exchange {market} does not support "
                f"functionality cancelOrder"
            )

        try:
            exchange.cancelOrder(
                order.get_external_id(),
                f"{order.get_target_symbol()}/{order.get_trading_symbol()}"
            )
            order.status = OrderStatus.CANCELED.value
            return order
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not cancel order")

    @staticmethod
    def initialize_exchange(market, market_credential):
        """
        Function to initialize the exchange for the market.

        Args:
            market (str): The market to initialize the exchange for
            market_credential (MarketCredential): The market credential to use
                for the exchange

        Returns:

        """
        market = market.lower()

        if not hasattr(ccxt, market):
            raise OperationalException(
                f"No ccxt exchange for market id {market}"
            )

        exchange_class = getattr(ccxt, market)

        if exchange_class is None:
            raise OperationalException(
                f"No market service found for market id {market}"
            )

        # Check the credentials for the exchange
        CCXTOrderExecutor.check_credentials(exchange_class, market_credential)
        exchange = exchange_class({
            'apiKey': market_credential.api_key,
            'secret': market_credential.secret_key,
        })
        return exchange

    @staticmethod
    def check_credentials(
        exchange_class, market_credential: MarketCredential
    ):
        """
        Function to check if the credentials are valid for the exchange.

        Args:
            exchange_class: The exchange class to check the credentials for
            market_credential: The market credential to use for the exchange

        Raises:
            OperationalException: If the credentials are not valid

        Returns:
            None
        """
        exchange = exchange_class()
        credentials_info = exchange.requiredCredentials
        market = market_credential.get_market()

        if ('apiKey' in credentials_info
                and credentials_info["apiKey"]
                and market_credential.get_api_key() is None):
            raise OperationalException(
                f"Market credential for market {market}"
                " requires an api key, either"
                " as an argument or as an environment variable"
                f" named as {market.upper()}_API_KEY"
            )

        if ('secret' in credentials_info
                and credentials_info["secret"]
                and market_credential.get_secret_key() is None):
            raise OperationalException(
                f"Market credential for market {market}"
                " requires a secret key, either"
                " as an argument or as an environment variable"
                f" named as {market.upper()}_SECRET_KEY"
            )

    def supports_market(self, market):
        """
        Function to check if the market is supported by the portfolio
        provider.

        Args:
            market: Market object

        Returns:
            bool: True if the market is supported, False otherwise
        """
        return hasattr(ccxt, market.lower())
