import ccxt
from logging import getLogger
from typing import Union

from investing_algorithm_framework.domain import PortfolioProvider, \
    OperationalException, Order, Position, MarketCredential


logger = getLogger("investing_algorithm_framework")


class CCXTPortfolioProvider(PortfolioProvider):
    """
    Implementation of Portfolio Provider for CCXT.
    """

    def get_order(
        self, portfolio, order, market_credential
    ) -> Union[Order, None]:
        """
        Method to check if there are any pending orders for the portfolio.
        This method will retrieve the open orders from the exchange and
        check if there are any pending orders for the portfolio.

        !IMPORTANT: This function should return None if the order is
        not found or if the order is not available on the
        exchange or broker. Please do not throw an exception if the
        order is not found.

        Args:
            portfolio: Portfolio object
            order: Order object from the database
            market_credential: Market credential object

        Returns:
            None
        """
        exchange = self.initialize_exchange(
            portfolio.market, market_credential
        )

        if not exchange.has['fetchOrder']:
            raise OperationalException(
                f"Market service {portfolio.market} does not support "
                f"functionality get_order"
            )

        symbol = order.get_symbol()

        try:
            external_order = exchange.fetchOrder(order.external_id, symbol)
            external_order = Order.from_ccxt_order(external_order)
            external_order.id = order.id
            return external_order
        except Exception as e:
            logger.exception(e)
            raise OperationalException("Could not retrieve order")

    def get_position(
        self, portfolio, symbol, market_credential
    ) -> Union[Position, None]:
        """
        Function to get the position for a given symbol in the portfolio.
        The returned position should be an object that reflects the current
        state of the position on the exchange or broker.

        !IMPORTANT: This function should return None if the position is
        not found or if the position is not available on the
        exchange or broker. Please do not throw an exception if the
        position is not found.

        Args:
            portfolio (Portfolio): Portfolio object
            symbol (str): Symbol object
            market_credential (MarketCredential): MarketCredential object

        Returns:
            Position: Position for the given symbol in the portfolio
        """

        exchange = self.initialize_exchange(
            portfolio.market, market_credential
        )

        if not exchange.has['fetchBalance']:
            raise OperationalException(
                f"Market service {portfolio.market} does not support "
                f"functionality get_balance"
            )

        try:
            amount = exchange.fetchBalance()["free"]

            if symbol not in amount:
                return None

            return Position(
                symbol=symbol,
                amount=amount[symbol],
                cost=0,
                portfolio_id=portfolio.id
            )
        except Exception as e:
            logger.exception(e)
            raise OperationalException(
                f"Please make sure you have "
                f"registered a valid market credential "
                f"object to the app: {str(e)}"
            )

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
        (CCXTPortfolioProvider
         .check_credentials(exchange_class, market_credential))
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
