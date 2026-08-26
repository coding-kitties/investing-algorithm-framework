from logging import getLogger

import ccxt

from investing_algorithm_framework.domain import OrderExecutor, \
    OperationalException, Order, OrderStatus, OrderSide, OrderType, \
    MarketCredential, PositionMode

logger = getLogger("investing_algorithm_framework")


class CCXTOrderExecutor(OrderExecutor):
    """
    CCXTOrderExecutor is a class that implements the OrderExecutor
    interface for executing orders using the CCXT library.

    Args:
        priority: See ``OrderExecutor``.
        sandbox: When True, orders are routed to the exchange's own
            sandbox/testnet (CCXT's ``set_sandbox_mode``) instead of
            its live endpoint. Requires the exchange to advertise a
            ``test`` URL (see ``supports_sandbox_mode``) and sandbox
            credentials via the usual ``MarketCredential`` mechanism.
        markets: Optional explicit list of markets this instance
            supports. When omitted (the default, single-instance
            registration case) any CCXT-known market is supported.
            Set this to scope an instance to specific markets only —
            e.g. a sandbox instance for one paper-traded market must
            not also claim every other (live) market in the same app.
    """

    def __init__(self, priority=1, sandbox=False, markets=None):
        super().__init__(priority=priority)
        self.sandbox = sandbox
        self._markets = {m.upper() for m in markets} if markets else None

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
        exchange = self.initialize_exchange(
            market, market_credential, sandbox=self.sandbox
        )
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
            elif OrderType.MARKET.equals(order_type):
                if OrderSide.BUY.equals(order_side):

                    if not hasattr(exchange, "createMarketBuyOrder"):
                        raise OperationalException(
                            f"Exchange {market} does not support "
                            f"functionality createMarketBuyOrder"
                        )

                    external_order = exchange.createMarketBuyOrder(
                        symbol, amount,
                    )
                else:

                    if not hasattr(exchange, "createMarketSellOrder"):
                        raise OperationalException(
                            f"Exchange {market} does not support "
                            f"functionality createMarketSellOrder"
                        )

                    external_order = exchange.createMarketSellOrder(
                        symbol, amount,
                    )
            elif OrderType.STOP.equals(order_type) \
                    or OrderType.STOP_LIMIT.equals(order_type):
                stop_price = order.get_stop_price()

                if stop_price is None:
                    raise OperationalException(
                        f"Order type {order_type} requires a stop_price"
                    )

                if not hasattr(exchange, "createOrder"):
                    raise OperationalException(
                        f"Exchange {market} does not support "
                        f"functionality createOrder needed for "
                        f"{order_type} orders"
                    )

                # CCXT unified API: stop / stop-limit are passed as a
                # generic order with the stopPrice param. STOP maps to
                # the exchange's market-stop type; STOP_LIMIT to the
                # stop-limit type. The exchange-specific mapping is
                # handled by CCXT.
                ccxt_type = (
                    "stop_limit"
                    if OrderType.STOP_LIMIT.equals(order_type)
                    else "stop"
                )
                ccxt_price = price if OrderType.STOP_LIMIT.equals(
                    order_type
                ) else None

                external_order = exchange.createOrder(
                    symbol,
                    ccxt_type,
                    OrderSide.from_value(order_side).value.lower(),
                    amount,
                    ccxt_price,
                    {"stopPrice": stop_price},
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
        exchange = self.initialize_exchange(
            market, market_credential, sandbox=self.sandbox
        )

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
    def initialize_exchange(market, market_credential, sandbox=False):
        """
        Function to initialize the exchange for the market.

        Args:
            market (str): The market to initialize the exchange for
            market_credential (MarketCredential): The market credential to use
                for the exchange
            sandbox (bool): When True, points the exchange client at its
                sandbox/testnet endpoint via CCXT's ``set_sandbox_mode``.
                Raises if the exchange doesn't advertise one.

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

        if sandbox:
            if not exchange.urls.get("test"):
                raise OperationalException(
                    f"Exchange {market} does not advertise a "
                    f"sandbox/testnet endpoint; cannot enable "
                    f"broker-native paper trading for this market. Use "
                    f"PaperTradingMode.LOCAL instead."
                )
            exchange.set_sandbox_mode(True)

        return exchange

    @staticmethod
    def supports_sandbox_mode(market) -> bool:
        """
        Whether this market's exchange advertises a sandbox/testnet
        endpoint (CCXT convention: ``exchange.urls["test"]``). Does not
        require credentials — only public exchange metadata is used.

        Args:
            market (str): The market to check.

        Returns:
            bool: True if a sandbox/testnet is available.
        """
        market = market.lower()

        if not hasattr(ccxt, market):
            return False

        try:
            exchange = getattr(ccxt, market)()
            return bool(exchange.urls.get("test"))
        except Exception:
            return False

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
        if self._markets is not None:
            return market.upper() in self._markets

        return hasattr(ccxt, market.lower())

    def supports_position_mode(self, market, position_mode) -> bool:
        position_mode = PositionMode(position_mode)
        if position_mode == PositionMode.NETTING:
            return self.supports_market(market)

        # CCXT may advertise setPositionMode, but this adapter does not yet
        # pass venue-specific LONG/SHORT leg parameters on createOrder.
        return False
