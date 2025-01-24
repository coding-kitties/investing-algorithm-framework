import logging

from investing_algorithm_framework.domain import OperationalException, \
    AbstractPortfolioSyncService, RESERVED_BALANCES, SYMBOLS, \
    ENVIRONMENT, Environment
from investing_algorithm_framework.services.trade_service import TradeService

logger = logging.getLogger(__name__)


class PortfolioSyncService(AbstractPortfolioSyncService):
    """
    Service to sync the portfolio with the exchange.
    """

    def __init__(
        self,
        trade_service: TradeService,
        configuration_service,
        order_service,
        position_repository,
        portfolio_repository,
        portfolio_configuration_service,
        market_credential_service,
        market_service
    ):
        self.trade_service = trade_service
        self.configuration_service = configuration_service
        self.order_service = order_service
        self.position_repository = position_repository
        self.portfolio_repository = portfolio_repository
        self.market_credential_service = market_credential_service
        self.market_service = market_service
        self.portfolio_configuration_service = portfolio_configuration_service

    def sync_unallocated(self, portfolio):
        """
        Method to sync the unallocated balance of the portfolio with the
        available balance on the exchange. This method will retrieve the
        available balance of the portfolio from the exchange and update the
        unallocated balance of the portfolio accordingly.

        If the portfolio already exists (exists in the database),
        then a check is done if the exchange has the available
        balance of the portfolio unallocated balance. If the exchange
        does not have the available balance of the portfolio,
        an OperationalException will be raised.

        If the portfolio does not exist, the portfolio will be created with
        the unallocated balance of the portfolio set to the available
        balance on the exchange. If also a initial balance is set in
        the portfolio configuration, the unallocated balance will be set
        to the initial balance (given the balance is available on
        the exchange). If the initial balance is not set, the
        unallocated balance will be set to the available balance
        on the exchange.

        Args:
            portfolio: Portfolio object

        Returns:
            Portfolio object
        """
        market_credential = self.market_credential_service.get(
            portfolio.market
        )

        if market_credential is None:
            raise OperationalException(
                f"No market credential found for market "
                f"{portfolio.market}. Cannot sync unallocated amount."
            )

        # Get the unallocated balance of the portfolio from the exchange
        balances = self.market_service.get_balance(market=portfolio.market)

        if not portfolio.initialized:
            # Check if the portfolio has an initial balance set
            if portfolio.initial_balance is not None:
                available = float(balances[portfolio.trading_symbol.upper()])

                if portfolio.initial_balance > available:
                    raise OperationalException(
                        "The initial balance of the " +
                        "portfolio configuration " +
                        f"({portfolio.initial_balance} "
                        f"{portfolio.trading_symbol}) is more " +
                        "than the available balance on the exchange. " +
                        "Please make sure that the initial balance of " +
                        "the portfolio configuration is less " +
                        "than the available balance on the " +
                        f"exchange {available} {portfolio.trading_symbol}."
                    )
                else:
                    unallocated = portfolio.initial_balance
            else:
                # If the portfolio does not have an initial balance
                # set, get the available balance on the exchange
                if portfolio.trading_symbol.upper() not in balances:
                    raise OperationalException(
                        f"There is no available balance on the exchange for "
                        f"{portfolio.trading_symbol.upper()} on market "
                        f"{portfolio.market}. Please make sure that you have "
                        f"an available balance on the exchange for "
                        f"{portfolio.trading_symbol.upper()} on market "
                        f"{portfolio.market}."
                    )
                else:
                    unallocated = float(
                        balances[portfolio.trading_symbol.upper()]
                    )

            update_data = {
                "unallocated": unallocated,
                "net_size": unallocated,
                "initialized": True
            }
            portfolio = self.portfolio_repository.update(
                portfolio.id, update_data
            )

            # Update also a trading symbol position
            trading_symbol_position = self.position_repository.find(
                {
                    "symbol": portfolio.trading_symbol,
                    "portfolio_id": portfolio.id
                }
            )
            self.position_repository.update(
                trading_symbol_position.id, {"amount": unallocated}
            )

        else:
            # Check if the portfolio unallocated balance is
            # available on the exchange
            if portfolio.unallocated > 0:
                if portfolio.trading_symbol.upper() not in balances \
                    or portfolio.unallocated > \
                        float(balances[portfolio.trading_symbol.upper()]):
                    raise OperationalException(
                        f"Out of sync: the unallocated balance"
                        " of the portfolio is more than the available"
                        " balance on the exchange. Please make sure"
                        " that you have at least "
                        f"{portfolio.unallocated}"
                        f" {portfolio.trading_symbol.upper()} available"
                        " on the exchange."
                    )

        return portfolio

    def sync_positions(self, portfolio):
        """
        Method to sync the portfolio balances with the balances
        on the exchange.
        This method will retrieve the balances from the exchange and update
        the portfolio balances accordingly.

        If the unallocated balance of the portfolio is less than the available
        balance on the exchange, the unallocated balance of the portfolio will
        be updated to match the available balance on the exchange.

        If the unallocated balance of the portfolio is more than the available
        balance on the exchange, an OperationalException will be raised.
        """
        portfolio_configuration = self.portfolio_configuration_service \
            .get(portfolio.identifier)
        balances = self.market_service \
            .get_balance(market=portfolio_configuration.market)
        reserved_balances = self.configuration_service.config \
            .get(RESERVED_BALANCES, {})
        symbols = self._get_symbols(portfolio)

        # If config symbols is set, add the symbols to the balances
        if SYMBOLS in self.configuration_service.config \
                and self.configuration_service.config[SYMBOLS] is not None:
            for symbol in symbols:
                target_symbol = symbol.split("/")[0]

                if target_symbol not in balances:
                    balances[target_symbol] = 0

        for key, value in balances.items():
            logger.info(f"Syncing balance for {key}")
            amount = float(value)

            if key in reserved_balances:
                logger.info(
                    f"{key} has reserved balance of {reserved_balances[key]}"
                )
                reserved = float(reserved_balances[key])
                amount = amount - reserved

            if self.position_repository.exists({"symbol": key}):
                position = self.position_repository.find({"symbol": key})
                data = {"amount": amount}
                self.position_repository.update(position.id, data)
            else:
                portfolio = self.portfolio_repository.find(
                    {"identifier": portfolio.identifier}
                )
                self.position_repository.create(
                    {
                        "symbol": key,
                        "amount": amount,
                        "portfolio_id": portfolio.id
                    }
                )

    def sync_orders(self, portfolio):
        """
        Function to sync all local orders with the orders on the exchange.
        This method will go over all local open orders and check if they are
        changed on the exchange. If they are, the local order will be
        updated to match the status on the exchange.

        Args:
            portfolio: Portfolio object

        Returns:
            None
        """

        config = self.configuration_service.get_config()

        if ENVIRONMENT in config \
                and Environment.BACKTEST.equals(config[ENVIRONMENT]):
            return

        self.order_service.check_pending_orders(portfolio=portfolio)

    def _get_symbols(self, portfolio):
        config = self.configuration_service.config
        available_symbols = []

        # Check if there already are positions
        positions = self.position_repository.get_all(
            {"identifier": portfolio.get_identifier()}
        )

        if len(positions) > 0:
            available_symbols = [
                f"{position.get_symbol()}/{portfolio.get_trading_symbol()}"
                for position in positions
                if position.get_symbol() != portfolio.trading_symbol
            ]

        if SYMBOLS in config and config[SYMBOLS] is not None:
            symbols = config[SYMBOLS]

            if not isinstance(symbols, list):
                raise OperationalException(
                    "The symbols configuration should be a list of strings"
                )

            market_symbols = self.market_service.get_symbols(portfolio.market)

            for symbol in symbols:

                if symbol not in market_symbols:
                    raise OperationalException(
                        f"The symbol {symbol} in the configuration is not "
                        "available on the exchange. Please make sure that the "
                        "symbols in the configuration are available on the "
                        "exchange. The available symbols on the exchange are: "
                        f"{market_symbols}"
                    )
                else:

                    if symbol not in available_symbols:
                        available_symbols.append(symbol)
        else:
            market_symbols = self.market_service.get_symbols(portfolio.market)
            available_symbols = market_symbols

        return available_symbols
