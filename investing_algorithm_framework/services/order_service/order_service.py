import logging
from datetime import datetime

from investing_algorithm_framework.domain import OrderType, OrderSide, \
    OperationalException, OrderStatus, Order, random_number, INDEX_DATETIME
from investing_algorithm_framework.services.repository_service \
    import RepositoryService

logger = logging.getLogger("investing_algorithm_framework")

# Cash/collateral checks compare a recomputed ``amount * price`` against
# the portfolio's unallocated balance. Upstream risk-budget scaling
# (``ApplyRiskBudgetPhase``) derives ``amount`` from ``quote_amount /
# price`` and then this check recomputes ``amount * price`` — the
# divide/multiply round-trip can leave the result a few ULPs above the
# actual unallocated cash even when the intent was scaled to fit
# exactly. A tiny relative tolerance absorbs that float noise without
# masking genuine overspend.
_CASH_TOLERANCE_REL = 1e-9
_CASH_TOLERANCE_ABS = 1e-8


def _cash_tolerance(*values):
    return max(
        _CASH_TOLERANCE_ABS,
        _CASH_TOLERANCE_REL * max(abs(v) for v in values),
    )


class OrderService(RepositoryService):
    """
    Service to manage orders. This service will use the provided
    order executors to execute the orders. The order service is
    responsible for creating, updating, canceling and deleting orders.

    Attributes:
        configuration_service (ConfigurationService): The service
            responsible for managing configurations.
        order_repository (OrderRepository): The repository
            responsible for managing orders.
        position_service (PositionService): The service
            responsible for managing positions.
        portfolio_repository (PortfolioRepository): The repository
            responsible for managing portfolios.
        portfolio_configuration_service (PortfolioConfigurationService):
            service responsible for managing portfolio configurations.
        portfolio_snapshot_service (PortfolioSnapshotService):
            service responsible for managing portfolio snapshots.
        market_credential_service (MarketCredentialService):
            service responsible for managing market credentials.
        trade_service (TradeService): The service responsible for
            managing trades.
    """

    def __init__(
        self,
        configuration_service,
        order_repository,
        position_service,
        portfolio_repository,
        portfolio_configuration_service,
        portfolio_snapshot_service,
        trade_service,
        portfolio_provider_lookup=None,
        order_executor_lookup=None,
        market_credential_service=None
    ):
        super(OrderService, self).__init__(order_repository)
        self.configuration_service = configuration_service
        self.order_repository = order_repository
        self.position_service = position_service
        self.portfolio_repository = portfolio_repository
        self.portfolio_configuration_service = portfolio_configuration_service
        self.portfolio_snapshot_service = portfolio_snapshot_service
        self.market_credential_service = market_credential_service
        self.trade_service = trade_service
        self._order_executor_lookup = order_executor_lookup
        self._portfolio_provider_lookup = portfolio_provider_lookup

    def create(self, data, execute=True, validate=True, sync=True) -> Order:
        """
        Function to create an order. The function will create the order and
        execute it if execute is set to True. The function will also validate
        the order if validate is set to True. The function will also sync the
        portfolio with the order if sync is set to True.

        The following only applies if the order is a sell order:

        If stop_losses, or take_profits are in the data, we assume that the
        order has been created by a stop loss or take profit. We will then
        create for the order one or more metadata objects with the
        amount and stop loss id or take profit id. These objects can later
        be used to restore the stop loss or take profit to its original state
        if the order is cancelled or rejected.

        If trades are in the data, we assume that the order has
        been created by a closing a specific trade. We will then create for
        the order one metadata object with the amount and trade id. This
        objects can later be used to restore the trade to its original
        state if the order is cancelled or rejected.

        If there are no trades in the data, we rely on the trade service to
        create the metadata objects for the order.

        The metadata objects are needed because for trades, stop losses and
        take profits we need to know how much of the order has been
        filled at any given time. If the order is cancelled or rejected we
        need to add the pending amount back to the trade, stop loss or take
        profit.

        Args:
            data: dict - the data to create the order with. Data should have
                the following format:
                {
                    "target_symbol": str,
                    "trading_symbol": str,
                    "order_side": str,
                    "order_type": str,
                    "amount": float,
                    "filled" (optional): float, // If set, trades
                        and positions are synced
                    "remaining" (optional): float, // Same as filled
                    "price": float,
                    "portfolio_id": int
                    "stop_losses" (optional): list[dict] - list of stop
                      losses with the following format:
                        {
                            "stop_loss_id": float,
                            "amount": float
                        }
                    "take_profits" (optional): list[dict] - list of
                        take profits with the following format:
                        {
                            "take_profit_id": float,
                            "amount": float
                        }
                    "trades" (optional): list[dict] - list of trades
                        with the following format:
                        {
                            "trade_id": int,
                            "amount": float
                        }
                }

            execute: bool - if True the order will be executed
            validate: bool - if True the order will be validated
            sync: bool - if True the portfolio will be synced with the order

        Returns:
            Order: Order object
        """
        portfolio_id = data["portfolio_id"]
        portfolio = self.portfolio_repository.get(portfolio_id)
        trades = data.get("trades", [])
        stop_losses = data.get("stop_losses", [])
        take_profits = data.get("take_profits", [])
        # v9.0 (#431) — BUY-side: user-supplied rules that should be
        # attached to each trade materialized at fill time.
        pending_stop_losses = data.get("pending_stop_losses", [])
        pending_take_profits = data.get("pending_take_profits", [])

        # v9.0 (#431) — capture any user-supplied filled/remaining/status
        # so we can re-apply them after the executor runs. This supports
        # call sites that pre-simulate a filled order (commonly tests, but
        # also live setups where the executor returns synchronously
        # filled and the caller passes the resulting state in). The
        # default ``CREATED`` status is filtered out because it is always
        # injected by ``context.create_limit_order`` even when the caller
        # has no opinion on the final status — preserving it would
        # silently overwrite whatever the executor returns.
        explicit_filled = data.get("filled")
        explicit_remaining = data.get("remaining")
        explicit_status = data.get("status") if "status" in data else None
        if explicit_status == OrderStatus.CREATED.value:
            explicit_status = None

        if "filled" in data:
            del data["filled"]

        if "remaining" in data:
            del data["remaining"]

        if "trades" in data:
            del data["trades"]

        if "stop_losses" in data:
            del data["stop_losses"]

        if "take_profits" in data:
            del data["take_profits"]

        if "pending_stop_losses" in data:
            del data["pending_stop_losses"]

        if "pending_take_profits" in data:
            del data["pending_take_profits"]

        if pending_stop_losses or pending_take_profits:
            order_metadata = data.setdefault("metadata", {}) or {}
            data["metadata"] = order_metadata
            if pending_stop_losses:
                order_metadata.setdefault(
                    "pending_stop_losses", []
                ).extend(pending_stop_losses)
            if pending_take_profits:
                order_metadata.setdefault(
                    "pending_take_profits", []
                ).extend(pending_take_profits)

        if validate:
            self.validate_order(data, portfolio)

        del data["portfolio_id"]
        data["target_symbol"] = data["target_symbol"].upper()
        symbol = data["target_symbol"]
        data["id"] = self._create_order_id()

        order = self.repository.create(data, save=False)

        # v9.0 (#431) — snapshot the price used to reserve cash so that
        # slippage between reservation and fill can be settled later
        # even after order.price is overwritten by the executor.
        if OrderSide.BUY.equals(order.order_side):
            reservation_price = order.reservation_price
            if reservation_price is not None:
                order.metadata["_reservation_price"] = reservation_price
                # Keep the persisted JSON column in sync with the
                # in-memory metadata dict so the reservation price
                # survives the eventual ``order_repository.save``.
                if hasattr(order, "metadata_json"):
                    import json as _json
                    order.metadata_json = _json.dumps(order.metadata)

        if validate:
            self.validate_order(data, portfolio)

        if execute:
            order = self.execute_order(order, portfolio)

        # v9.0 (#431) — if the caller supplied filled / remaining / status
        # explicitly, prefer them over whatever the executor returned. This
        # supports callers that pre-simulate fills (tests and live setups
        # where the executor responds synchronously). When execute is False
        # we still need to honour the explicit values since execute_order
        # never ran.
        if explicit_filled is not None:
            order.set_filled(explicit_filled)
            if explicit_remaining is not None:
                order.set_remaining(explicit_remaining)
            else:
                order.set_remaining(
                    max(order.get_amount() - explicit_filled, 0)
                )
        if explicit_status is not None:
            order.set_status(explicit_status)

        position = self._create_position_if_not_exists(symbol, portfolio)
        order.position_id = position.id
        order = self.order_repository.save(order)
        order_id = order.id
        order_side = order.order_side

        if OrderSide.SELL.equals(order_side):
            # Create order metadata if there is a key in the data
            # for trades, stop_losses or take_profits
            self.trade_service.create_trade_allocations(
                sell_order=order,
                trades=trades,
                stop_losses=stop_losses,
                take_profits=take_profits
            )
        elif OrderSide.COVER.equals(order_side) and trades:
            # #434 phase 3 — stash the SL/TP-triggered trade
            # allocation hint on the COVER order so the fill handler
            # can close the right SHORT trade(s) instead of falling
            # back to pure FIFO.
            order.metadata["_cover_trade_allocations"] = trades
            if hasattr(order, "metadata_json"):
                import json as _json
                order.metadata_json = _json.dumps(order.metadata)
            # v9.0 — re-assert ``updated_at`` so the SQL model's
            # ``onupdate=utcnow`` hook does not silently overwrite the
            # executor-supplied timestamp on this second UPDATE.
            # Without this, backtest sim-time gets clobbered by wall
            # clock, which breaks the per-bar fill scan that uses
            # ``Datetime >= updated_at`` to skip past candles.
            preserved_updated_at = order.updated_at
            order = self.order_repository.save(order)
            if preserved_updated_at is not None \
                    and order.updated_at != preserved_updated_at:
                order = self.order_repository.update(
                    order.id,
                    {"updated_at": preserved_updated_at},
                )
        # v9.0 (#431) — BUY orders no longer eagerly create a trade.
        # The trade is created from the actual fill event in
        # ``_sync_with_buy_order_filled``.
        # #434 phase 2 — SHORT trades are created from the fill event
        # in ``_sync_with_short_order_filled``; COVER closes the open
        # SHORT trade(s) in ``_sync_with_cover_order_filled``.

        if sync:
            order = self.get(order_id)
            if OrderSide.BUY.equals(order_side):
                self._sync_portfolio_with_created_buy_order(order)
                # v9.0 (#431) — if the executor reported the order
                # already filled at create time, route the filled
                # portion through the regular fill-handling path so a
                # Trade is created and any slippage settled.
                if order.get_filled() and order.get_filled() > 0:
                    synthetic_previous = Order.from_dict(order.to_dict())
                    synthetic_previous.set_filled(0)
                    self._sync_with_buy_order_filled(
                        synthetic_previous, order
                    )
            elif OrderSide.SHORT.equals(order_side):
                self._sync_portfolio_with_created_short_order(order)
                if order.get_filled() and order.get_filled() > 0:
                    synthetic_previous = Order.from_dict(order.to_dict())
                    synthetic_previous.set_filled(0)
                    self._sync_with_short_order_filled(
                        synthetic_previous, order
                    )
            elif OrderSide.COVER.equals(order_side):
                self._sync_portfolio_with_created_cover_order(order)
                if order.get_filled() and order.get_filled() > 0:
                    synthetic_previous = Order.from_dict(order.to_dict())
                    synthetic_previous.set_filled(0)
                    self._sync_with_cover_order_filled(
                        synthetic_previous, order
                    )
            else:
                self._sync_portfolio_with_created_sell_order(order)

        order = self.get(order_id)
        return order

    def update(self, object_id, data):
        """
        Function to update an order. The function will update the order and
        sync the portfolio, position and trades if the order has been filled.

        If the order has been cancelled, expired or rejected the function will
        sync the portfolio, position, trades, stop losses, and
        take profits with the order.

        Args:
            object_id: int - the id of the order to update
            data: dict - the data to update the order with
              the following format:
                {
                    "amount": float,
                    "filled" (optional): float,
                    "remaining" (optional): float,
                    "status" (optional): str,
                }

        Returns:
            Order: Order object that has been updated
        """
        previous_order = self.order_repository.get(object_id)
        new_order = self.order_repository.update(object_id, data)
        filled_difference = new_order.get_filled() \
            - previous_order.get_filled()

        new_side = new_order.get_order_side()

        if filled_difference > 0:
            if OrderSide.BUY.equals(new_side):
                self._sync_with_buy_order_filled(previous_order, new_order)
            elif OrderSide.SHORT.equals(new_side):
                self._sync_with_short_order_filled(
                    previous_order, new_order
                )
            elif OrderSide.COVER.equals(new_side):
                self._sync_with_cover_order_filled(
                    previous_order, new_order
                )
            else:
                self._sync_with_sell_order_filled(previous_order, new_order)

        if "status" in data:

            if OrderStatus.CANCELED.equals(new_order.get_status()):
                if OrderSide.BUY.equals(new_side):
                    self._sync_with_buy_order_cancelled(new_order)
                elif OrderSide.SHORT.equals(new_side):
                    self._sync_with_short_order_cancelled(new_order)
                elif OrderSide.COVER.equals(new_side):
                    self._sync_with_cover_order_cancelled(new_order)
                else:
                    self._sync_with_sell_order_cancelled(new_order)

            if OrderStatus.EXPIRED.equals(new_order.get_status()):

                if OrderSide.BUY.equals(new_side):
                    self._sync_with_buy_order_expired(new_order)
                elif OrderSide.SHORT.equals(new_side):
                    self._sync_with_short_order_expired(new_order)
                elif OrderSide.COVER.equals(new_side):
                    self._sync_with_cover_order_expired(new_order)
                else:
                    self._sync_with_sell_order_expired(new_order)

            if OrderStatus.REJECTED.equals(new_order.get_status()):

                if OrderSide.BUY.equals(new_side):
                    self._sync_with_buy_order_rejected(new_order)
                elif OrderSide.SHORT.equals(new_side):
                    self._sync_with_short_order_rejected(new_order)
                elif OrderSide.COVER.equals(new_side):
                    self._sync_with_cover_order_rejected(new_order)
                else:
                    self._sync_with_sell_order_expired(new_order)

        return new_order

    def execute_order(self, order, portfolio) -> Order:
        """
        Function to execute an order. The function will execute the order
        with a matching order executor. The function will also update
        the order attributes with the external order attributes.

        Args:
            order: Order object representing the order to be executed
            portfolio: Portfolio object representing the portfolio in which

        Returns:
            order: Order object representing the executed order
        """
        logger.info(
            f"Executing order {order.get_symbol()} with "
            f"amount {order.get_amount()} "
            f"and price {order.get_price()}"
        )

        order_executor = self._order_executor_lookup\
            .get_order_executor(portfolio.market)
        market_credential = self.market_credential_service.get(
            portfolio.market
        )
        external_order = order_executor.execute_order(
            portfolio, order, market_credential
        )
        logger.info(f"Executed order: {external_order.to_dict()}")
        order.set_external_id(external_order.get_external_id())
        order.set_status(external_order.get_status())
        order.set_filled(external_order.get_filled())
        order.set_remaining(external_order.get_remaining())

        # Copy the actual execution price back from the exchange
        # response so that slippage is captured correctly.
        if external_order.get_price() is not None:
            order.set_price(external_order.get_price())

        config = self.configuration_service.config
        order.updated_at = config[INDEX_DATETIME]
        return order

    def validate_order(self, order_data, portfolio):

        order_side = order_data["order_side"]
        if OrderSide.BUY.equals(order_side):
            self.validate_buy_order(order_data, portfolio)
        elif OrderSide.SELL.equals(order_side):
            self.validate_sell_order(order_data, portfolio)
        elif OrderSide.SHORT.equals(order_side):
            # #434 phase 1 — plumbing only. The validator runs but the
            # event-engine sync that actually opens the short position
            # arrives in phase 2.
            self.validate_short_order(order_data, portfolio)
        elif OrderSide.COVER.equals(order_side):
            self.validate_cover_order(order_data, portfolio)
        else:
            raise OperationalException(
                f"Order side {order_side} is not supported"
            )

        if OrderType.LIMIT.equals(order_data["order_type"]):
            self.validate_limit_order(order_data, portfolio)
        elif OrderType.MARKET.equals(order_data["order_type"]):
            self.validate_market_order(order_data, portfolio)
        elif OrderType.STOP.equals(order_data["order_type"]):
            self.validate_stop_order(order_data, portfolio)
        elif OrderType.STOP_LIMIT.equals(order_data["order_type"]):
            self.validate_stop_limit_order(order_data, portfolio)
        else:
            raise OperationalException(
                f"Order type {order_data['order_type']} is not supported"
            )

    def validate_sell_order(self, order_data, portfolio):

        if not self.position_service.exists(
            {
                "symbol": order_data["target_symbol"],
                "portfolio": portfolio.id
            }
        ):
            raise OperationalException(
                "Can't add sell order to non existing position"
            )

        position = self.position_service\
            .find(
                {
                    "symbol": order_data["target_symbol"],
                    "portfolio": portfolio.id
                }
            )

        if position.get_amount() < order_data["amount"]:
            raise OperationalException(
                f"Order amount {order_data['amount']} is larger " +
                f"then amount of open position {position.get_amount()}"
            )

        if not order_data["trading_symbol"] == portfolio.trading_symbol:
            raise OperationalException(
                f"Can't add sell order with target "
                f"symbol {order_data['target_symbol']} to "
                f"portfolio with trading symbol {portfolio.trading_symbol}"
            )

    @staticmethod
    def validate_buy_order(order_data, portfolio):

        if not order_data["trading_symbol"] == portfolio.trading_symbol:
            raise OperationalException(
                f"Can't add buy order with trading "
                f"symbol {order_data['trading_symbol']} to "
                f"portfolio with trading symbol {portfolio.trading_symbol}"
            )

    def validate_short_order(self, order_data, portfolio):
        """
        Validate a SHORT (short-entry) order.

        Phase 1 of #434 — high-level invariants only. Cash-collateral
        reservation is enforced by the type-level validator
        (``_validate_short_collateral`` via the LIMIT/MARKET/STOP
        validators).

        Invariants:
          * trading_symbol matches portfolio.trading_symbol
          * amount > 0
          * no existing **long** position (positive amount) in the
            same symbol — you must close the long before opening a
            short (per #434: one direction per symbol).
        """
        if not order_data["trading_symbol"] == portfolio.trading_symbol:
            raise OperationalException(
                f"Can't add short order with trading "
                f"symbol {order_data['trading_symbol']} to "
                f"portfolio with trading symbol {portfolio.trading_symbol}"
            )

        if order_data.get("amount", 0) <= 0:
            raise OperationalException(
                "Short order amount must be greater than zero"
            )

        if self.position_service.exists(
            {
                "symbol": order_data["target_symbol"],
                "portfolio": portfolio.id,
            }
        ):
            position = self.position_service.find(
                {
                    "symbol": order_data["target_symbol"],
                    "portfolio": portfolio.id,
                }
            )
            if position.get_amount() and position.get_amount() > 0:
                raise OperationalException(
                    f"Can't open short on {order_data['target_symbol']}: "
                    f"existing long position of "
                    f"{position.get_amount()} must be closed first"
                )

    def validate_cover_order(self, order_data, portfolio):
        """
        Validate a COVER (short-close) order.

        Invariants:
          * trading_symbol matches portfolio.trading_symbol
          * amount > 0
          * an open short position must exist in the same symbol
            (phase-2 sync model: short positions carry a negative
            ``amount``; until phase 2 lands no short positions exist
            in event mode and this check always fails — by design).
          * cover amount must not exceed the absolute size of the
            open short.
        """
        if not order_data["trading_symbol"] == portfolio.trading_symbol:
            raise OperationalException(
                f"Can't add cover order with trading "
                f"symbol {order_data['trading_symbol']} to "
                f"portfolio with trading symbol {portfolio.trading_symbol}"
            )

        if order_data.get("amount", 0) <= 0:
            raise OperationalException(
                "Cover order amount must be greater than zero"
            )

        if not self.position_service.exists(
            {
                "symbol": order_data["target_symbol"],
                "portfolio": portfolio.id,
            }
        ):
            raise OperationalException(
                f"Can't cover {order_data['target_symbol']}: no "
                f"open short position exists"
            )

        position = self.position_service.find(
            {
                "symbol": order_data["target_symbol"],
                "portfolio": portfolio.id,
            }
        )
        position_amount = position.get_amount() or 0

        if position_amount >= 0:
            raise OperationalException(
                f"Can't cover {order_data['target_symbol']}: "
                f"position is not short (amount={position_amount})"
            )

        if order_data["amount"] > abs(position_amount):
            raise OperationalException(
                f"Cover amount {order_data['amount']} exceeds open "
                f"short size {abs(position_amount)} on "
                f"{order_data['target_symbol']}"
            )

    # ------------------------------------------------------------------
    # Shared validation primitives — every order-type validator
    # composes these two helpers rather than calling each other. The
    # only thing that varies per type is which field holds the
    # reservation reference price.
    # ------------------------------------------------------------------

    def _validate_sell_amount(self, order_data, portfolio):
        """SELL: amount > 0 and amount <= current position size."""
        amount = order_data["amount"]
        position = self.position_service.find(
            {
                "portfolio": portfolio.id,
                "symbol": order_data["target_symbol"],
            }
        )

        if amount <= 0:
            raise OperationalException(
                f"Order amount: {amount} {position.symbol}, is "
                f"less or equal to 0"
            )

        if amount > position.get_amount():
            raise OperationalException(
                f"Order amount: {amount} {position.symbol}, is "
                f"larger then position size: {position.get_amount()} "
                f"{position.symbol} of the portfolio"
            )

    def _validate_buy_cash(self, order_data, portfolio, reference_price):
        """BUY: amount * reference_price <= portfolio unallocated cash.

        The reference price is supplied by the caller and represents
        the worst-case cash to reserve for the order:

        - LIMIT      → ``order_data["price"]``
        - MARKET     → ``order_data["price"]`` (caller-supplied estimate)
        - STOP       → ``stop_price`` (no limit price exists)
        - STOP_LIMIT → ``price`` (limit price; trigger is not a fill)
        """
        if reference_price is None or reference_price <= 0:
            raise OperationalException(
                "Cannot validate buy order: reference price is "
                "missing or non-positive"
            )

        total_price = order_data["amount"] * reference_price
        unallocated_position = self.position_service.find(
            {
                "portfolio": portfolio.id,
                "symbol": portfolio.trading_symbol,
            }
        )
        unallocated_amount = unallocated_position.get_amount()

        if unallocated_amount is None:
            raise OperationalException(
                "Unallocated amount of the portfolio is None. "
                "Please check if the portfolio configuration is correct."
            )

        tolerance = _cash_tolerance(unallocated_amount, total_price)
        if unallocated_amount < total_price - tolerance:
            raise OperationalException(
                f"Order total: {total_price} "
                f"{portfolio.trading_symbol}, is "
                f"larger then unallocated size: {portfolio.unallocated} "
                f"{portfolio.trading_symbol} of the portfolio"
            )

    def _validate_short_collateral(
        self, order_data, portfolio, reference_price
    ):
        """SHORT: amount * reference_price <= unallocated cash (full
        collateral, no leverage). Mirrors ``_validate_buy_cash``
        for the short side; kept separate so the error message and
        future leverage hook stay distinct.
        """
        if reference_price is None or reference_price <= 0:
            raise OperationalException(
                "Cannot validate short order: reference price is "
                "missing or non-positive"
            )

        required_collateral = order_data["amount"] * reference_price
        unallocated_position = self.position_service.find(
            {
                "portfolio": portfolio.id,
                "symbol": portfolio.trading_symbol,
            }
        )
        unallocated_amount = unallocated_position.get_amount()

        if unallocated_amount is None:
            raise OperationalException(
                "Unallocated amount of the portfolio is None. "
                "Please check if the portfolio configuration is correct."
            )

        tolerance = _cash_tolerance(unallocated_amount, required_collateral)
        if unallocated_amount < required_collateral - tolerance:
            raise OperationalException(
                f"Short collateral required: {required_collateral} "
                f"{portfolio.trading_symbol}, exceeds unallocated "
                f"balance: {portfolio.unallocated} "
                f"{portfolio.trading_symbol}"
            )

    def _validate_cover_amount(self, order_data, portfolio):
        """COVER: amount > 0 and amount <= abs(open short size)."""
        amount = order_data["amount"]
        position = self.position_service.find(
            {
                "portfolio": portfolio.id,
                "symbol": order_data["target_symbol"],
            }
        )
        position_amount = position.get_amount() or 0

        if amount <= 0:
            raise OperationalException(
                f"Cover amount: {amount} {position.symbol}, is "
                f"less or equal to 0"
            )

        if position_amount >= 0:
            raise OperationalException(
                f"Position {position.symbol} is not short "
                f"(amount={position_amount}); cannot cover"
            )

        if amount > abs(position_amount):
            raise OperationalException(
                f"Cover amount: {amount} {position.symbol}, exceeds "
                f"open short size: {abs(position_amount)} "
                f"{position.symbol}"
            )

    def validate_limit_order(self, order_data, portfolio):
        side = order_data["order_side"]
        if OrderSide.SELL.equals(side):
            self._validate_sell_amount(order_data, portfolio)
        elif OrderSide.COVER.equals(side):
            self._validate_cover_amount(order_data, portfolio)
        elif OrderSide.SHORT.equals(side):
            self._validate_short_collateral(
                order_data, portfolio, order_data.get("price")
            )
        else:
            self._validate_buy_cash(
                order_data, portfolio, order_data.get("price")
            )

    def validate_market_order(self, order_data, portfolio):
        """
        Validate a market order. For sell orders, validates position
        size. For buy orders, validates using the estimated price
        supplied at creation time against the portfolio's unallocated
        balance. SHORT mirrors BUY (collateral); COVER mirrors SELL
        (amount vs open short).
        """
        side = order_data["order_side"]
        if OrderSide.SELL.equals(side):
            self._validate_sell_amount(order_data, portfolio)
        elif OrderSide.COVER.equals(side):
            self._validate_cover_amount(order_data, portfolio)
        elif OrderSide.SHORT.equals(side):
            self._validate_short_collateral(
                order_data, portfolio, order_data.get("price", 0)
            )
        else:
            self._validate_buy_cash(
                order_data, portfolio, order_data.get("price", 0)
            )

    def validate_stop_order(self, order_data, portfolio):
        """
        Validate a STOP order. Requires a positive ``stop_price`` and,
        for BUY/SHORT, reserves cash against ``stop_price`` (no limit
        price exists). The actual fill price is discovered at trigger
        time.
        """
        stop_price = order_data.get("stop_price")

        if stop_price is None or stop_price <= 0:
            raise OperationalException(
                "Stop orders require a positive stop_price"
            )

        side = order_data["order_side"]
        if OrderSide.SELL.equals(side):
            self._validate_sell_amount(order_data, portfolio)
        elif OrderSide.COVER.equals(side):
            self._validate_cover_amount(order_data, portfolio)
        elif OrderSide.SHORT.equals(side):
            self._validate_short_collateral(
                order_data, portfolio, stop_price
            )
        else:
            self._validate_buy_cash(order_data, portfolio, stop_price)

    def validate_stop_limit_order(self, order_data, portfolio):
        """
        Validate a STOP_LIMIT order. Requires both ``stop_price``
        (trigger) and ``price`` (limit). For BUY, reserves cash
        against the limit price — once triggered, the order behaves
        like a LIMIT.
        """
        stop_price = order_data.get("stop_price")
        limit_price = order_data.get("price")

        if stop_price is None or stop_price <= 0:
            raise OperationalException(
                "Stop-limit orders require a positive stop_price"
            )

        if limit_price is None or limit_price <= 0:
            raise OperationalException(
                "Stop-limit orders require a positive limit price"
            )

        if OrderSide.BUY.equals(order_data["order_side"]):
            if limit_price < stop_price:
                raise OperationalException(
                    "For BUY stop-limit orders, the limit price must be "
                    "greater than or equal to the stop price"
                )
            self._validate_buy_cash(order_data, portfolio, limit_price)
        elif OrderSide.SHORT.equals(order_data["order_side"]):
            # SHORT stop-limit: stop above limit (sells into a drop).
            if limit_price > stop_price:
                raise OperationalException(
                    "For SHORT stop-limit orders, the limit price must "
                    "be less than or equal to the stop price"
                )
            self._validate_short_collateral(
                order_data, portfolio, limit_price
            )
        elif OrderSide.COVER.equals(order_data["order_side"]):
            # COVER stop-limit: behaves like BUY stop-limit (limit
            # >= stop) because it buys to close a short.
            if limit_price < stop_price:
                raise OperationalException(
                    "For COVER stop-limit orders, the limit price must "
                    "be greater than or equal to the stop price"
                )
            self._validate_cover_amount(order_data, portfolio)
        else:
            if limit_price > stop_price:
                raise OperationalException(
                    "For SELL stop-limit orders, the limit price must be "
                    "less than or equal to the stop price"
                )
            self._validate_sell_amount(order_data, portfolio)

    def check_pending_orders(self, portfolio=None):
        """
        Function to check if
        """
        if portfolio is not None:
            pending_orders = self.get_all(
                {
                    "status": OrderStatus.OPEN.value,
                    "portfolio_id": portfolio.id
                }
            )
        else:
            pending_orders = self.get_all({"status": OrderStatus.OPEN.value})

        # v9.0 (#431) — process pending orders in creation order so
        # that the trades materialized at fill time preserve the
        # original BUY placement order. Downstream FIFO sell-allocation
        # depends on this ordering.
        pending_orders = sorted(
            pending_orders,
            key=lambda o: (
                o.get_created_at() or datetime.min,
                o.get_id() or 0,
            ),
        )

        for order in pending_orders:
            position = self.position_service.get(order.position_id)
            portfolio = self.portfolio_repository.get(position.portfolio_id)
            portfolio_provider = self._portfolio_provider_lookup\
                .get_portfolio_provider(portfolio.market)
            market_credential = self.market_credential_service.get(
                portfolio.market
            )
            logger.info(
                f"Checking {order.get_order_side()} order {order.get_id()} "
                f"with external id: {order.get_external_id()} "
                f"at market {portfolio.market}"
            )
            external_order = portfolio_provider.get_order(
                portfolio, order, market_credential
            )

            if external_order is None:
                logger.warning(
                    f"External order not found for order "
                    f"{order.get_id()} with external id "
                    f"{order.get_external_id()} at market "
                    f"{portfolio.market}. Skipping sync."
                )
                continue

            self.update(order.id, external_order.to_dict())

    def _create_position_if_not_exists(self, symbol, portfolio):
        if not self.position_service.exists(
            {"portfolio": portfolio.id, "symbol": symbol}
        ):
            self.position_service \
                .create({"portfolio_id": portfolio.id, "symbol": symbol})
            position = self.position_service \
                .find({"portfolio": portfolio.id, "symbol": symbol})
        else:
            position = self.position_service \
                .find({"portfolio": portfolio.id, "symbol": symbol})

        return position

    def _sync_portfolio_with_created_buy_order(self, order):
        """
        Function to sync the portfolio and positions with a created buy order.

        Args:
            order: the order object representing the buy order

        Returns:
            None
        """
        self.position_service.update_positions_with_created_buy_order(
            order
        )
        position = self.position_service.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        size = order.get_size()
        self.portfolio_repository.update(
            portfolio.id, {"unallocated": portfolio.get_unallocated() - size}
        )

    def _sync_portfolio_with_created_sell_order(self, order):
        """
        Function to sync the portfolio with a created sell order. The
        function will subtract the amount of the order from the position and
        the trade amount. If the sell order is already filled, then
        the function will also update the portfolio and the
        trading symbol position.

        The portfolio will not be updated because the sell order has not been
        filled.

        Args:
            order: Order object representing the sell order

        Returns:
            None
        """
        self.position_service.update_positions_with_created_sell_order(
            order
        )

        filled = order.get_filled()

        if filled > 0:
            position = self.position_service.get(order.position_id)
            portfolio = self.portfolio_repository.get(position.portfolio_id)
            size = filled * order.get_price()
            self.portfolio_repository.update(
                portfolio.id,
                {
                    "unallocated": portfolio.get_unallocated() + size
                }
            )

    # ------------------------------------------------------------------
    # #434 phase 2 — SHORT / COVER portfolio sync.
    #
    # Cash model (mirrors the vector engine, #433):
    #
    #   SHORT
    #     create  -> reserve collateral (amount * reservation_price)
    #                from unallocated and trading-symbol position.
    #     fill    -> release reservation, credit proceeds, decrement
    #                target position (going negative). Net cash
    #                change from create->fill is +proceeds.
    #     cancel/ -> refund unfilled reservation.
    #     expire/
    #     reject
    #
    #   COVER
    #     create  -> reserve cover cash (amount * reservation_price)
    #                — same cash-side semantics as a BUY reservation.
    #     fill    -> release reservation, debit actual cover cost,
    #                move target position toward zero, realize P&L
    #                on the open short trade.
    #     cancel/ -> refund unfilled reservation.
    #     expire/
    #     reject
    # ------------------------------------------------------------------

    def _sync_portfolio_with_created_short_order(self, order):
        """Reserve cash collateral for a freshly-created SHORT order.
        Cash-side semantics are identical to a BUY reservation; the
        target position is left untouched until the fill arrives.
        """
        self.position_service.update_positions_with_created_short_order(
            order
        )
        position = self.position_service.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        size = order.get_size()
        self.portfolio_repository.update(
            portfolio.id,
            {"unallocated": portfolio.get_unallocated() - size}
        )

    def _sync_portfolio_with_created_cover_order(self, order):
        """Reserve cash to buy back the short for a freshly-created
        COVER order. Cash-side semantics are identical to a BUY
        reservation.
        """
        self.position_service.update_positions_with_created_cover_order(
            order
        )
        position = self.position_service.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        size = order.get_size()
        self.portfolio_repository.update(
            portfolio.id,
            {"unallocated": portfolio.get_unallocated() - size}
        )

    def _sync_with_short_order_filled(self, previous_order, current_order):
        """SHORT fill: release the per-fill reservation, credit
        proceeds, drive the target position further negative, create
        a SHORT trade row.
        """
        filled_difference = current_order.get_filled() - \
            previous_order.get_filled()

        if filled_difference <= 0:
            return

        logger.info(
            f"Syncing portfolio with filled short "
            f"order {current_order.get_id()} with filled amount "
            f"{filled_difference}"
        )

        fill_price = current_order.get_price()
        if fill_price is None or fill_price == 0:
            fill_price = current_order.reservation_price or 0

        reservation_price = current_order.metadata.get(
            "_reservation_price"
        )
        if reservation_price is None:
            reservation_price = (
                current_order.reservation_price or fill_price
            )

        filled_size = filled_difference * fill_price
        reserved_for_fill = filled_difference * reservation_price

        # Drive the target position further negative; accrue proceeds
        # as the position's ``cost`` so net_gain math stays symmetric
        # with the long path.
        self.position_service.update_positions_with_short_order_filled(
            current_order, filled_difference
        )

        position = self.position_service.get(current_order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)

        # Cash flow at fill: refund the per-fill reservation and
        # credit the realized proceeds.
        cash_credit = reserved_for_fill + filled_size
        self.portfolio_repository.update(
            portfolio.id,
            {
                "unallocated": portfolio.get_unallocated() + cash_credit,
                "total_trade_volume": portfolio.get_total_trade_volume()
                + filled_size,
            }
        )
        trading_symbol_position = self.position_service.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_service.update(
            trading_symbol_position.id,
            {
                "amount":
                    trading_symbol_position.get_amount() + cash_credit
            }
        )

        # If the exchange modified the order amount (partial-fill
        # rounding), reconcile the still-reserved balance for the
        # outstanding remainder.
        if current_order.amount != previous_order.amount:
            portfolio = self.portfolio_repository.get(position.portfolio_id)
            difference = current_order.amount - previous_order.amount
            cost_adjustment = difference * reservation_price
            self.portfolio_repository.update(
                portfolio.id,
                {
                    "unallocated":
                        portfolio.get_unallocated() - cost_adjustment
                }
            )
            trading_symbol_position = self.position_service.find(
                {
                    "symbol": portfolio.trading_symbol,
                    "portfolio": portfolio.id
                }
            )
            self.position_service.update(
                trading_symbol_position.id,
                {
                    "amount":
                        trading_symbol_position.get_amount()
                        - cost_adjustment
                }
            )

        # Record the SHORT trade for this fill event.
        self.trade_service.create_short_trade_at_fill(
            current_order,
            filled_difference,
            fill_price,
            current_order.updated_at or current_order.created_at,
        )

    def _sync_with_cover_order_filled(self, previous_order, current_order):
        """COVER fill: release the per-fill reservation, debit the
        actual cover cost, move the target position toward zero, and
        realize P&L on the matched open SHORT trade(s).
        """
        filled_difference = current_order.get_filled() - \
            previous_order.get_filled()

        if filled_difference <= 0:
            return

        logger.info(
            f"Syncing portfolio with filled cover "
            f"order {current_order.get_id()} with filled amount "
            f"{filled_difference}"
        )

        fill_price = current_order.get_price()
        if fill_price is None or fill_price == 0:
            fill_price = current_order.reservation_price or 0

        reservation_price = current_order.metadata.get(
            "_reservation_price"
        )
        if reservation_price is None:
            reservation_price = (
                current_order.reservation_price or fill_price
            )

        filled_size = filled_difference * fill_price
        reserved_for_fill = filled_difference * reservation_price

        # Move target position toward zero; reduce the position's
        # short-side ``cost`` proportionally.
        self.position_service.update_positions_with_cover_order_filled(
            current_order, filled_difference
        )

        position = self.position_service.get(current_order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)

        # Cash flow at fill: refund the per-fill reservation, debit
        # the actual cover cost.
        cash_delta = reserved_for_fill - filled_size
        self.portfolio_repository.update(
            portfolio.id,
            {
                "unallocated": portfolio.get_unallocated() + cash_delta,
                "total_trade_volume": portfolio.get_total_trade_volume()
                + filled_size,
            }
        )
        trading_symbol_position = self.position_service.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_service.update(
            trading_symbol_position.id,
            {
                "amount":
                    trading_symbol_position.get_amount() + cash_delta
            }
        )

        # Reconcile if the exchange modified the order amount.
        if current_order.amount != previous_order.amount:
            portfolio = self.portfolio_repository.get(position.portfolio_id)
            difference = current_order.amount - previous_order.amount
            cost_adjustment = difference * reservation_price
            self.portfolio_repository.update(
                portfolio.id,
                {
                    "unallocated":
                        portfolio.get_unallocated() - cost_adjustment
                }
            )
            trading_symbol_position = self.position_service.find(
                {
                    "symbol": portfolio.trading_symbol,
                    "portfolio": portfolio.id
                }
            )
            self.position_service.update(
                trading_symbol_position.id,
                {
                    "amount":
                        trading_symbol_position.get_amount()
                        - cost_adjustment
                }
            )

        # Realize P&L on the matched open SHORT trade(s) (FIFO).
        self.trade_service.close_short_trade_with_filled_cover_order(
            filled_difference, current_order
        )

    def _sync_with_short_order_cancelled(self, order):
        """Cancellation reversal for a SHORT order. Cash-side
        semantics are identical to BUY (refund unfilled reservation).
        """
        self._restore_buy_order_balance(order)

    def _sync_with_short_order_expired(self, order):
        self._restore_buy_order_balance(order)

    def _sync_with_short_order_rejected(self, order):
        self._restore_buy_order_balance(order)

    def _sync_with_short_order_failed(self, order):
        self._restore_buy_order_balance(order)

    def _sync_with_cover_order_cancelled(self, order):
        """Cancellation reversal for a COVER order. Cash-side
        semantics are identical to BUY (refund unfilled reservation).
        """
        self._restore_buy_order_balance(order)

    def _sync_with_cover_order_expired(self, order):
        self._restore_buy_order_balance(order)

    def _sync_with_cover_order_rejected(self, order):
        self._restore_buy_order_balance(order)

    def _sync_with_cover_order_failed(self, order):
        self._restore_buy_order_balance(order)

    def cancel_order(self, order):
        self.check_pending_orders()
        order = self.order_repository.get(order.id)

        if order is not None:

            if OrderStatus.OPEN.equals(order.status):
                portfolio = self.portfolio_repository\
                    .find({"position": order.position_id})
                market_credential = self.market_credential_service.get(
                    portfolio.market
                )
                order_executor = self._order_executor_lookup\
                    .get_order_executor(portfolio.market)
                order = order_executor\
                    .cancel_order(portfolio, order, market_credential)
                self.update(order.id, order.to_dict())

    def _sync_with_buy_order_filled(self, previous_order, current_order):
        """
        Function to sync the portfolio, position and trades with the
        filled buy order.

        v9.0 (#431) — a fresh Trade is created for every fill event
        (one trade per fill), and the slippage between the price used
        to reserve cash at order-creation time and the actual fill
        price is settled here in a unified way for LIMIT, MARKET and
        STOP / STOP_LIMIT orders.

        Args:
            previous_order: the previous order object
            current_order:  the current order object

        Returns:
            None
        """
        logger.info("Syncing portfolio with filled buy order")
        filled_difference = current_order.get_filled() - \
            previous_order.get_filled()

        if filled_difference <= 0:
            return

        fill_price = current_order.get_price()
        # Fall back through the reservation chain if the executor has
        # not yet written a price (defensive — shouldn't happen for a
        # fill event).
        if fill_price is None or fill_price == 0:
            fill_price = current_order.reservation_price or 0

        # Snapshot of the reservation price stashed by ``create``.
        reservation_price = current_order.metadata.get(
            "_reservation_price"
        )
        if reservation_price is None:
            reservation_price = (
                current_order.reservation_price or fill_price
            )

        filled_size = filled_difference * fill_price
        reserved_for_fill = filled_difference * reservation_price
        slippage_delta = reserved_for_fill - filled_size

        self.position_service.update_positions_with_buy_order_filled(
            current_order, filled_difference
        )
        position = self.position_service.get(current_order.position_id)

        # Update portfolio: book the actual cost / volume, and refund
        # (or charge) the slippage delta against the original
        # reservation so unallocated stays consistent.
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        portfolio_updates = {
            "total_cost": portfolio.get_total_cost() + filled_size,
            "total_trade_volume": portfolio.get_total_trade_volume()
            + filled_size,
        }
        if slippage_delta != 0:
            portfolio_updates["unallocated"] = (
                portfolio.get_unallocated() + slippage_delta
            )
        self.portfolio_repository.update(portfolio.id, portfolio_updates)

        if slippage_delta != 0:
            trading_symbol_position = self.position_service.find(
                {
                    "symbol": portfolio.trading_symbol,
                    "portfolio": portfolio.id
                }
            )
            self.position_service.update(
                trading_symbol_position.id,
                {
                    "amount":
                        trading_symbol_position.get_amount()
                        + slippage_delta
                }
            )
            # Refresh portfolio reference for the amount-change branch
            portfolio = self.portfolio_repository.get(position.portfolio_id)

        # If the exchange modified the order amount (e.g. partial
        # fill rounding), reconcile the reserved balance using the
        # original reservation price.
        if current_order.amount != previous_order.amount:
            difference = current_order.amount - previous_order.amount
            cost_adjustment = difference * reservation_price
            self.portfolio_repository.update(
                portfolio.id,
                {
                    "unallocated":
                        portfolio.get_unallocated() - cost_adjustment
                }
            )
            trading_symbol_position = self.position_service.find(
                {
                    "symbol": portfolio.trading_symbol,
                    "portfolio": portfolio.id
                }
            )
            self.position_service.update(
                trading_symbol_position.id,
                {
                    "amount":
                        trading_symbol_position.get_amount()
                        - cost_adjustment
                }
            )

        # v9.0 (#431) — create the Trade row for this fill event.
        self.trade_service.create_trade_at_fill(
            current_order,
            filled_difference,
            fill_price,
            current_order.updated_at or current_order.created_at,
        )

    def _sync_with_sell_order_filled(self, previous_order, current_order):
        """
        Function to sync the portfolio, position and trades with the
        filled sell order. The function will update the portfolio and
        position with the filled amount of the order. The function will
        also update the trades with the filled amount of the order.

        Args:
            previous_order: Order object representing the previous order
            current_order: Order object representing the current order

        Returns:
            None
        """
        filled_difference = current_order.get_filled() - \
            previous_order.get_filled()
        filled_size = filled_difference * current_order.get_price()

        if filled_difference <= 0:
            return

        logger.info(
            f"Syncing portfolio with filled sell "
            f"order {current_order.get_id()} with filled amount "
            f"{filled_difference}"
        )

        # Get position
        position = self.position_service.get(current_order.position_id)

        # Update the portfolio
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        self.portfolio_repository.update(
            portfolio.id,
            {
                "unallocated": portfolio.get_unallocated() + filled_size,
                "total_trade_volume": portfolio.get_total_trade_volume()
                + filled_size,
            }
        )

        # Update the trading symbol position
        trading_symbol_position = self.position_service.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_service.update(
            trading_symbol_position.id,
            {
                "amount":
                    trading_symbol_position.get_amount() + filled_size
            }
        )

        # Update the position if the amount has changed
        if current_order.amount != previous_order.amount:
            difference = current_order.amount - previous_order.amount
            cost = difference * current_order.get_price()
            self.position_service.update(
                position.id,
                {
                    "amount": position.get_amount() - difference,
                    "cost": position.get_cost() - cost
                }
            )

        self.trade_service.update_trade_with_filled_sell_order(
            filled_difference, current_order
        )

    def _restore_buy_order_balance(self, order):
        """Shared logic: restore reserved balance when a BUY order is
        cancelled, expired, rejected, or failed.

        v9.0 (#431) — uses the reservation-price snapshot stashed on
        ``order.metadata['_reservation_price']`` so that STOP orders
        (whose ``price`` is None until trigger) and MARKET orders
        (whose ``price`` may have been overwritten by an early fill)
        still refund the originally-reserved amount.
        """
        remaining = order.get_amount() - order.get_filled()
        reservation_price = order.metadata.get("_reservation_price")
        if reservation_price is None:
            reservation_price = order.reservation_price or order.get_price()
        size = remaining * reservation_price

        portfolio = self.portfolio_repository.find(
            {"position": order.position_id}
        )
        self.portfolio_repository.update(
            portfolio.id,
            {"unallocated": portfolio.get_unallocated() + size}
        )

        trading_symbol_position = self.position_service.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_service.update(
            trading_symbol_position.id,
            {"amount": trading_symbol_position.get_amount() + size}
        )

    def _restore_sell_order_position(self, order):
        """Shared logic: restore locked position when a SELL order is
        cancelled, expired, rejected, or failed."""
        remaining = order.get_amount() - order.get_filled()

        position = self.position_service.get(order.position_id)
        self.position_service.update(
            position.id,
            {"amount": position.get_amount() + remaining}
        )
        self.trade_service.update_trade_with_removed_sell_order(order)

    def _sync_with_buy_order_cancelled(self, order):
        self._restore_buy_order_balance(order)

    def _sync_with_sell_order_cancelled(self, order):
        self._restore_sell_order_position(order)

    def _sync_with_buy_order_failed(self, order):
        self._restore_buy_order_balance(order)

    def _sync_with_sell_order_failed(self, order):
        self._restore_sell_order_position(order)

    def _sync_with_buy_order_expired(self, order):
        self._restore_buy_order_balance(order)

    def _sync_with_sell_order_expired(self, order):
        self._restore_sell_order_position(order)

    def _sync_with_buy_order_rejected(self, order):
        self._restore_buy_order_balance(order)

    def _sync_with_sell_order_rejected(self, order):
        self._restore_sell_order_position(order)

    def _create_order_id(self):
        """
        Function to create a new order id. The function will
        create a new order id and return it.

        Returns:
            int: The new order id
        """

        unique = False
        order_id = None

        while not unique:
            order_id = random_number(12)

            if not self.repository.exists({"id": order_id}):
                unique = True

        return order_id
