import logging
from investing_algorithm_framework.domain import OperationalException, \
    AbstractPortfolioSyncService, RESERVED_BALANCES, APP_MODE, SYMBOLS, \
    OrderSide, AppMode
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
            order_repository,
            position_repository,
            portfolio_repository,
            portfolio_configuration_service,
            market_credential_service,
            market_service
    ):
        self.trade_service = trade_service
        self.configuration_service = configuration_service
        self.order_repository = order_repository
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

        If the algorithm is running stateless it will update the unallocated
        balance of the portfolio to the available balance on the exchange.

        If the algorithm is running stateful, the unallocated balance of the
        portfolio will only check if the amount on the exchange is less
        than the unallocated balance of the portfolio. If the amount on the
        exchange is less than the unallocated balance of the portfolio, the
        unallocated balance of the portfolio will be updated to the amount on
        the exchange or an OperationalException will be raised if the
        throw_exception_on_insufficient_balance is set to True.

        If in the config the RESERVED_BALANCES key is set, the reserved amount
        will be subtracted from the unallocated amount. This is to prevent
        the algorithm from using reserved balances for trading. The reserved
        config is not used for the stateless mode, because this would mean
        that the algorithm should be aware of how much it already used for
        trading. This is not possible in stateless mode.
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

        if portfolio.trading_symbol.upper() not in balances:
            unallocated = 0
        else:
            unallocated = float(balances[portfolio.trading_symbol.upper()])

        reserved_unallocated = 0
        config = self.configuration_service.config
        mode = config.get(APP_MODE)

        if not AppMode.STATELESS.equals(mode):
            if RESERVED_BALANCES in config:
                reserved = config[RESERVED_BALANCES]

                if portfolio.trading_symbol.upper() in reserved:
                    reserved_unallocated \
                        = reserved[portfolio.trading_symbol.upper()]

            unallocated = unallocated - reserved_unallocated

            if portfolio.unallocated is not None and \
                    unallocated != portfolio.unallocated:

                if unallocated < portfolio.unallocated:
                    raise OperationalException(
                        "There seems to be a mismatch between "
                        "the portfolio configuration and the balances on"
                        " the exchange. "
                        f"Please make sure that the available "
                        f"{portfolio.trading_symbol} "
                        f"on your exchange {portfolio.market} "
                        "matches the portfolio configuration amount of: "
                        f"{portfolio.unallocated} "
                        f"{portfolio.trading_symbol}. "
                        f"You have currently {unallocated} "
                        f"{portfolio.trading_symbol} available on the "
                        f"exchange."
                    )

                # If portfolio does not exist and initial balance is set,
                # create the portfolio with the initial balance
                if unallocated > portfolio.unallocated and \
                        not self.portfolio_repository.exists(
                            {"identifier": portfolio.identifier}
                        ):
                    unallocated = portfolio.unallocated

        if not self.portfolio_repository.exists(
                {"identifier": portfolio.identifier}
        ):
            create_data = {
                "identifier": portfolio.get_identifier(),
                "market": portfolio.get_market().upper(),
                "trading_symbol": portfolio.get_trading_symbol(),
                "unallocated": unallocated,
            }
            portfolio = self.portfolio_repository.create(create_data)
        else:
            update_data = {
                "unallocated": unallocated,
            }
            portfolio = self.portfolio_repository.update(
                portfolio.id, update_data
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
        This function will retrieve all orders from the exchange and
        update the portfolio balances and positions accordingly.

        First all orders are retrieved from the exchange and updated in the
        database. If the order does not exist in the database, it will be
        created and treated as a new order.

        When an order is closed on the exchange, the order will be updated
        in the database to closed. We will also then update the portfolio
        and position balances accordingly.

        If the order exists, we will check if the filled amount of the order
        has changed. If the filled amount has changed, we will update the
        order in the database and update the portfolio and position balances

        if the status of an existing order has changed, we will update the
        order in the database and update the portfolio and position balances

        During the syncing of the orders, new orders are not executed. They
        are only created in the database. This is to prevent the algorithm
        from executing orders that are already executed on the exchange.
        """

        portfolio_configuration = self.portfolio_configuration_service \
            .get(portfolio.identifier)
        symbols = self._get_symbols(portfolio)
        positions = self.position_repository.get_all(
            {"portfolio_id": portfolio_configuration.identifier}
        )

        # Remove the portfolio trading symbol from the symbols
        symbols = [
            symbol for symbol in symbols if symbol != portfolio.trading_symbol
        ]

        # Check if there are orders for the available symbols
        for symbol in symbols:
            symbol = f"{symbol.upper()}"
            orders = self.market_service.get_orders(
                symbol=symbol,
                since=portfolio_configuration.track_from,
                market=portfolio.market
            )

            if orders is not None and len(orders) > 0:
                # Order the list of orders by created_at
                ordered_external_order_list = sorted(
                    orders, key=lambda x: x.created_at
                )

                if portfolio_configuration.track_from is not None:
                    ordered_external_order_list = [
                        order for order in ordered_external_order_list
                        if order.created_at >= portfolio_configuration
                        .track_from
                    ]

                for external_order in ordered_external_order_list:

                    if self.order_repository.exists(
                            {"external_id": external_order.external_id}
                    ):
                        logger.info("Updating existing order")
                        order = self.order_repository.find(
                            {"external_id": external_order.external_id}
                        )
                        self.order_repository.update(
                            order.id, external_order.to_dict()
                        )
                    else:
                        logger.info(
                            "Creating new order, based on external order"
                        )
                        data = external_order.to_dict()
                        data.pop("trade_closed_at", None)
                        data.pop("trade_closed_price", None)
                        data.pop("trade_closed_amount", None)
                        position_id = None

                        # Get position id
                        for position in positions:
                            if position.symbol == external_order.target_symbol:
                                position_id = position.id
                                break

                        # Create the new order
                        new_order_data = {
                            "target_symbol": external_order.target_symbol,
                            "trading_symbol": portfolio.trading_symbol,
                            "amount": external_order.amount,
                            "price": external_order.price,
                            "order_side": external_order.order_side,
                            "order_type": external_order.order_type,
                            "external_id": external_order.external_id,
                            "status": "open",
                            "position_id": position_id,
                            "created_at": external_order.created_at,
                        }
                        new_order = self.order_repository.create(
                            new_order_data,
                        )

                        # Update the order to its current status
                        # By default it should not sync the unallocated
                        # balance as this has already by done.
                        # Position amounts should be updated
                        update_data = {
                            "status": external_order.status,
                            "filled": external_order.filled,
                            "remaining": external_order.remaining,
                            "updated_at": external_order.created_at,
                        }
                        self.order_repository.update(
                            new_order.id, update_data
                        )

    def sync_trades(self, portfolio):
        orders = self.order_repository.get_all(
            {
                "portfolio": portfolio.identifier,
                "order_by_created_at_asc": True
            }
        )

        sell_orders = [
            order for order in orders
            if OrderSide.SELL.equals(order.order_side)
        ]

        for sell_order in sell_orders:
            self.trade_service.close_trades(
                sell_order, sell_order.get_filled()
            )

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
