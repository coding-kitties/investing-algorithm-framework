"""StrategyScenario: a seeded, isolated portfolio for strategy tests."""
import math
import weakref
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from tempfile import TemporaryDirectory
from typing import Optional

from investing_algorithm_framework.app import App, TradingStrategy
from investing_algorithm_framework.dependency_container import \
    DependencyContainer
from investing_algorithm_framework.domain import BacktestDateRange, \
    INDEX_DATETIME, RESOURCE_DIRECTORY, Order, OrderSide, \
    PortfolioConfiguration, PositionMode, ScenarioSetupError, \
    ScenarioStateError, Trade, TradeStopLoss, TradeTakeProfit
from investing_algorithm_framework.domain.models.signal import SignalSide
from investing_algorithm_framework.infrastructure.repositories \
    .event_memory import EventMemoryState, activate_event_memory
from investing_algorithm_framework.services.strategy_phases \
    .record_cooldown import record_emission

# ids of strategy instances bound to an open scenario
_bound_strategies = set()


def _call(name, *args, **kwargs):
    shown = [repr(a) for a in args]
    shown += [f"{k}={v!r}" for k, v in kwargs.items() if v is not None]
    return f"{name}({', '.join(shown)})"


def _number(value):
    return isinstance(value, (int, float)) \
        and not isinstance(value, bool) and math.isfinite(value)


def _close(a, b):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def _exceeds(a, b):
    return a > b and not _close(a, b)


class StrategyScenario:
    """A portfolio seeded with cash, trade lots, pending orders, risk
    rules and cooldown history for testing one strategy instance.

    Every seed goes through the production services (order creation
    and fill, stop-loss and take-profit attachment), so cash,
    positions, cost basis, trade lots and reservations agree; each
    seeding call validates its inputs before changing anything and
    runs :meth:`check_consistency` afterwards.

    State lives in an in-memory store owned by the scenario. Nothing
    touches the SQL database, the network, credentials, environment
    variables or files outside a temporary directory, so independent
    scenarios never share state. Process-wide caches that hold no
    portfolio state (timeframe parsing, blotter registry) are shared.

    Example::

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with StrategyScenario(MyStrategy(), initial_cash=1_000,
                              trading_symbol="EUR", market="BITVAVO",
                              start=start) as scenario:
            trade = scenario.open_trade(
                "BTC", amount=2, price=100,
                opened_at=start - timedelta(hours=4))
            assert scenario.context.get_unallocated() == 800
            assert scenario.context.get_position("BTC").cost == 200

    Args:
        strategy (TradingStrategy): A fresh strategy instance; it is
            bound to this scenario until :meth:`close`.
        initial_cash (float): Quote-currency cash at the start.
        start (datetime): Timezone-aware scenario time, on the hour.
            Seeded history lies at or before it.
        trading_symbol (str): Quote currency, e.g. ``"EUR"``.
        market (str, optional): Market name. Defaults to the single
            market named by the strategy's data sources.
        position_mode (PositionMode, optional): NETTING (default) or
            HEDGE.
        portfolio_configuration (PortfolioConfiguration, optional):
            Use instead of ``trading_symbol``, ``market`` and
            ``position_mode``.

    Raises:
        ScenarioSetupError: If the arguments describe no valid
            portfolio, or the strategy is in use or has already run.
    """

    def __init__(
        self,
        strategy: TradingStrategy,
        *,
        initial_cash: float,
        start: datetime,
        trading_symbol: Optional[str] = None,
        market: Optional[str] = None,
        position_mode: Optional[PositionMode] = None,
        portfolio_configuration: Optional[PortfolioConfiguration] = None,
    ):
        self._closed = True
        call = "StrategyScenario(...)"
        self._check_strategy(call, strategy)

        if not _number(initial_cash) or initial_cash < 0:
            raise ScenarioSetupError(
                f"{call}: initial_cash must be a finite number >= 0 "
                f"(got {initial_cash!r})."
            )

        if not isinstance(start, datetime) or start.tzinfo is None \
                or start.timestamp() % 3600:
            raise ScenarioSetupError(
                f"{call}: start must be a timezone-aware datetime on the "
                f"UTC hour (got {start!r}). Pass e.g. "
                f"datetime(2024, 1, 1, tzinfo=timezone.utc)."
            )

        configuration = self._portfolio_configuration(
            call, strategy, initial_cash, trading_symbol, market,
            position_mode, portfolio_configuration,
        )
        self.strategy = strategy
        self.initial_cash = float(initial_cash)
        self._mode = configuration.position_mode
        self._trading_symbol = configuration.trading_symbol
        self._last_bars_ago = {}
        self._tmp = TemporaryDirectory(prefix="iaf-scenario-")
        _bound_strategies.add(id(strategy))
        # Also releases the strategy if the scenario is never closed.
        self._release = weakref.finalize(
            self, _bound_strategies.discard, id(strategy))
        self._closed = False

        try:
            app = App(name="strategy-scenario")
            app.container = DependencyContainer()
            app.set_config(RESOURCE_DIRECTORY, self._tmp.name)
            app.add_portfolio_configuration(configuration)
            date_range = BacktestDateRange(start_date=start, end_date=start)
            app.initialize_backtest_config(
                backtest_date_range=date_range,
                initial_amount=self.initial_cash,
            )
            app.initialize_backtest_services()
            self._services = app.container
            self._context = app.context
            self._context._current_strategy_id = strategy.strategy_id
            self._start = date_range.start_date
            self._state = EventMemoryState()

            with self._activate():
                self._services.portfolio_service() \
                    .create_portfolio_from_configuration(
                        configuration,
                        initial_amount=self.initial_cash,
                        created_at=self._start,
                    )
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> "StrategyScenario":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        """Release the store, the strategy and the temporary directory.

        Safe to call more than once; later method calls raise
        :class:`ScenarioSetupError`.
        """
        if self._closed:
            return
        self._closed = True
        if hasattr(self, "_state"):
            self._state.close()
        self._release()
        self._tmp.cleanup()

    @property
    def context(self):
        """The production :class:`Context`; each method call runs
        against this scenario's state."""
        return _ScopedContext(self)

    @property
    def now(self) -> datetime:
        """The scenario clock (``INDEX_DATETIME``)."""
        self._ensure_open()
        return self._services.configuration_service() \
            .config[INDEX_DATETIME]

    # ----------------------------------------------------------------
    # Seeding
    # ----------------------------------------------------------------

    def open_trade(
        self,
        symbol: str,
        *,
        amount: float,
        price: float,
        direction: str = "long",
        opened_at: Optional[datetime] = None,
        fee: float = 0.0,
        apply_strategy_rules: bool = True,
    ) -> Trade:
        """Open a filled trade lot as the strategy would have.

        Places a limit BUY (``direction="long"``) or SHORT order and
        fills it at ``price``, so cash, the position leg and its cost
        basis move exactly as in a backtest.

        Args:
            symbol (str): Target symbol, e.g. ``"BTC"``.
            amount (float): Lot size, > 0.
            price (float): Entry price, > 0.
            direction (str): ``"long"`` or ``"short"``.
            opened_at (datetime, optional): Fill time; defaults to the
                scenario start.
            fee (float): Quote-currency fee paid on the fill.
            apply_strategy_rules (bool): Attach the strategy's
                stop-loss and take-profit rules for this symbol and
                side, as ``AttachRiskRulesPhase`` would.

        Returns:
            Trade: The opened lot.
        """
        call = _call("open_trade", symbol, amount=amount, price=price,
                     direction=direction, opened_at=opened_at, fee=fee)

        with self._activate():
            symbol = self._check_symbol(call, symbol)
            self._check_positive(call, amount=amount, price=price)
            if not _number(fee) or fee < 0:
                raise ScenarioSetupError(
                    f"{call}: fee must be a finite number >= 0.")
            if direction not in ("long", "short"):
                raise ScenarioSetupError(
                    f"{call}: direction must be 'long' or 'short'.")
            short = direction == "short"
            at = self._check_time(call, "opened_at", opened_at)
            self._check_entry(call, symbol, short, amount, price, fee)

            with self._clock(at):
                order = self._create_entry(
                    symbol, short, amount, price, apply_strategy_rules)
                fill = {"filled": amount, "remaining": 0,
                        "status": "CLOSED"}
                if fee:
                    fill["order_fee"] = fee
                self._services.order_service().update(order.id, fill)

            self._check()
            return self._services.trade_service() \
                .get_all({"order_id": order.id})[0]

    def place_order(
        self,
        symbol: str,
        *,
        side,
        amount: float,
        price: float,
        created_at: Optional[datetime] = None,
        apply_strategy_rules: bool = True,
    ) -> Order:
        """Place a limit order that stays pending (OPEN).

        BUY, SHORT and COVER orders reserve ``amount * price`` of
        cash; a SELL reserves ``amount`` of the long leg from the
        oldest lots first.

        Args:
            symbol (str): Target symbol.
            side (OrderSide | str): BUY, SELL, SHORT or COVER.
            amount (float): Order size, > 0.
            price (float): Limit price, > 0.
            created_at (datetime, optional): Placement time; defaults
                to the scenario start.
            apply_strategy_rules (bool): For BUY and SHORT orders,
                queue the strategy's stop-loss and take-profit rules
                so they attach to the trade when the order fills.

        Returns:
            Order: The pending order.
        """
        call = _call("place_order", symbol, side=side, amount=amount,
                     price=price, created_at=created_at)

        with self._activate():
            symbol = self._check_symbol(call, symbol)
            self._check_positive(call, amount=amount, price=price)
            try:
                side = OrderSide.from_value(side)
            except Exception:
                raise ScenarioSetupError(
                    f"{call}: side must be BUY, SELL, SHORT or COVER.")
            at = self._check_time(call, "created_at", created_at)
            position = self._position(symbol)

            if side in (OrderSide.BUY, OrderSide.SHORT):
                short = side is OrderSide.SHORT
                self._check_entry(call, symbol, short, amount, price)
            elif side is OrderSide.SELL:
                available = position.long_amount if position else 0
                if _exceeds(amount, available):
                    raise ScenarioSetupError(
                        f"{call}: sells {amount} {symbol} but the long "
                        f"leg has {available} {symbol} not yet reserved "
                        f"by pending SELL orders. Open a larger lot or "
                        f"reduce the order."
                    )
            else:
                pending = sum(
                    o.amount - (o.filled or 0)
                    for o in self._open_orders(OrderSide.COVER, symbol)
                )
                available = (position.short_amount if position else 0) \
                    - pending
                if _exceeds(amount, available):
                    raise ScenarioSetupError(
                        f"{call}: covers {amount} {symbol} but the "
                        f"short leg has {available} {symbol} not yet "
                        f"covered by pending COVER orders. Open a larger "
                        f"short or reduce the order."
                    )
                self._check_cash(call, amount * price)

            with self._clock(at):
                if side in (OrderSide.BUY, OrderSide.SHORT):
                    order = self._create_entry(
                        symbol, side is OrderSide.SHORT, amount, price,
                        apply_strategy_rules,
                    )
                elif side is OrderSide.SELL:
                    order = self._context.create_limit_order(
                        target_symbol=symbol, order_side="SELL",
                        price=price, amount=amount,
                    )
                else:
                    order = self._context.create_cover_order(
                        target_symbol=symbol, price=price, amount=amount,
                    )

            self._check()
            return self._services.order_service().get(order.id)

    def add_stop_loss(
        self,
        trade: Trade,
        *,
        percentage: float,
        trailing: bool = False,
        sell_percentage: float = 100,
        created_at: Optional[datetime] = None,
    ) -> TradeStopLoss:
        """Attach a stop-loss to an open seeded trade.

        Args:
            trade (Trade): An open trade of this scenario.
            percentage (float): Distance from the entry price, > 0.
            trailing (bool): Trail the high-water mark.
            sell_percentage (float): Share of the trade to sell, in
                (0, 100].
            created_at (datetime, optional): Defaults to the start.

        Returns:
            TradeStopLoss: The attached rule.
        """
        return self._add_rule(
            "add_stop_loss", trade, percentage, trailing,
            sell_percentage, created_at,
        )

    def add_take_profit(
        self,
        trade: Trade,
        *,
        percentage: float,
        trailing: bool = False,
        sell_percentage: float = 100,
        created_at: Optional[datetime] = None,
    ) -> TradeTakeProfit:
        """Attach a take-profit to an open seeded trade.

        Args:
            trade (Trade): An open trade of this scenario.
            percentage (float): Distance from the entry price, > 0.
            trailing (bool): Trail the high-water mark.
            sell_percentage (float): Share of the trade to sell, in
                (0, 100].
            created_at (datetime, optional): Defaults to the start.

        Returns:
            TradeTakeProfit: The attached rule.
        """
        return self._add_rule(
            "add_take_profit", trade, percentage, trailing,
            sell_percentage, created_at,
        )

    def mark_price(self, symbol: str, price: float, *,
                   at: datetime) -> None:
        """Report a historical price for every open trade of
        ``symbol``, moving trailing stop-loss and take-profit state
        the way the backtest's per-bar mark does.

        Args:
            symbol (str): Target symbol with open trades.
            price (float): Price, > 0. It must not trigger an active
                rule: a triggered rule would have closed the trade.
            at (datetime): Time of the price, at or before the start.
        """
        call = _call("mark_price", symbol, price, at=at)

        with self._activate():
            symbol = self._check_symbol(call, symbol)
            self._check_positive(call, price=price)
            trades = self._services.trade_service().get_all(
                {"target_symbol": symbol, "status": "OPEN"})
            if not trades:
                raise ScenarioSetupError(
                    f"{call}: no open trade for {symbol}. Call "
                    f"open_trade first.")
            history = []
            for trade in trades:
                history += [
                    (f"trade {trade.id} opened", trade.opened_at),
                    (f"the last mark of trade {trade.id}",
                     trade.last_reported_price_datetime),
                ] + [
                    (f"a rule of trade {trade.id} was created",
                     rule.created_at)
                    for rule in trade.stop_losses + trade.take_profits
                ]
            at = self._check_time(call, "at", at, history)

            for trade in trades:
                for kind, rules in (("stop-loss", trade.stop_losses),
                                    ("take-profit", trade.take_profits)):
                    # The rows are detached copies, so this check
                    # leaves the stored rules untouched.
                    if any(r.active and r.has_triggered(price)
                           for r in rules):
                        raise ScenarioSetupError(
                            f"{call}: price {price} triggers the active "
                            f"{kind} of trade {trade.id}, which would "
                            f"have closed it. Use a price inside the "
                            f"rule's range."
                        )

            with self._clock(at):
                for trade in trades:
                    # Same update the backtest evaluator makes per bar.
                    self._services.trade_service().update(trade.id, {
                        "last_reported_price": price,
                        "last_reported_price_datetime": at,
                        "updated_at": at,
                    })
            self._check()

    def record_cooldown(self, symbol: str, *, side: SignalSide,
                        bars_ago: int) -> None:
        """Record that the strategy emitted a ``side`` order on
        ``symbol`` ``bars_ago`` bars before the next evaluation.

        Updates the cooldown tracker, scale-out counter and
        ``ScalingRule.cooldown_in_bars`` countdown exactly as the
        ``RecordCooldownPhase`` would have. Seed in chronological
        order (``bars_ago`` not increasing).

        Args:
            symbol (str): Target symbol.
            side (SignalSide): Side of the emitted signal.
            bars_ago (int): 1 for the previous bar, 2 for the one
                before, and so on.
        """
        call = _call("record_cooldown", symbol, side=side,
                     bars_ago=bars_ago)
        self._ensure_open()
        symbol = self._check_symbol(call, symbol)
        strategy = self.strategy

        if not isinstance(side, SignalSide):
            raise ScenarioSetupError(
                f"{call}: side must be a SignalSide, e.g. "
                f"SignalSide.OPEN_LONG.")
        if isinstance(bars_ago, bool) or not isinstance(bars_ago, int) \
                or bars_ago < 1:
            raise ScenarioSetupError(
                f"{call}: bars_ago must be an int >= 1 (1 is the bar "
                f"before the next evaluation).")
        last = self._last_bars_ago.get(symbol)
        if last is not None and bars_ago > last:
            raise ScenarioSetupError(
                f"{call}: an event {last} bars ago is already recorded "
                f"for {symbol}. Record events oldest first.")
        if strategy.get_scaling_rule(symbol) is None and not any(
            rule.applies_to_symbol(symbol) for rule in strategy.cooldowns
        ):
            raise ScenarioSetupError(
                f"{call}: {strategy.strategy_id} declares no "
                f"CooldownRule or ScalingRule for {symbol}, so this "
                f"history would change nothing. Add the rule to the "
                f"strategy or drop the seed."
            )

        # The next evaluation runs at bar index _cooldown_bar_index + 1.
        bar_index = strategy._cooldown_bar_index + 1 - bars_ago
        record_emission(strategy, symbol, side, bar_index, self._mode)

        # Age the scaling countdown by the bars that have passed since,
        # as CollectSignalsPhase does once per bar.
        key = (symbol, "long" if side.is_long else "short") \
            if self._mode == PositionMode.HEDGE else symbol
        if key in strategy._cooldown_remaining:
            strategy._cooldown_remaining[key] -= bars_ago - 1
            if strategy._cooldown_remaining[key] <= 0:
                del strategy._cooldown_remaining[key]
        self._last_bars_ago[symbol] = bars_ago

    # ----------------------------------------------------------------
    # Consistency
    # ----------------------------------------------------------------

    def check_consistency(self) -> None:
        """Check that cash, positions, trade lots and reservations
        agree.

        Raises:
            ScenarioStateError: Listing every violated invariant.
        """
        with self._activate():
            self._check()

    def _check(self):
        services = self._services
        violations = []
        portfolio = services.portfolio_service().get_all()[0]
        positions = services.position_service().get_all()
        trades = services.trade_service().get_all()
        orders = services.order_service().get_all()
        allocations = services.trade_allocation_repository().get_all()
        quote = next(p for p in positions
                     if p.symbol == self._trading_symbol)

        if not _close(portfolio.unallocated, quote.amount):
            violations.append(
                f"unallocated {portfolio.unallocated} != "
                f"{self._trading_symbol} position {quote.amount}")

        # Cash follows from the order ledger: fills move it by
        # price * filled, fees reduce it, and pending BUY, SHORT and
        # COVER orders reserve their reservation price * remaining.
        # An order filled in chunks at different prices is booked at
        # its last price, so such states are outside this check.
        sign = {"BUY": -1, "SELL": 1, "SHORT": 1, "COVER": -1}
        cash = self.initial_cash
        for order in orders:
            filled = order.filled or 0
            if filled:
                cash += sign[order.order_side] * order.price * filled
            cash -= order.order_fee or 0
            if order.status == "OPEN" and order.order_side != "SELL":
                reservation = order.metadata.get("_reservation_price") \
                    or order.reservation_price
                cash -= reservation * (order.amount - filled)
            elif order.status == "OPEN":
                reserved = sum(a.amount_pending for a in allocations
                               if a.order_id == order.id)
                if not _close(reserved, order.amount - filled):
                    violations.append(
                        f"pending SELL {order.id} reserves {reserved} "
                        f"of {order.amount - filled} from trade lots")
        if not _close(portfolio.unallocated, cash):
            violations.append(
                f"unallocated {portfolio.unallocated} != {cash} implied "
                f"by initial cash, fills, fees and reservations")

        pending = {}
        for allocation in allocations:
            pending[allocation.trade_id] = \
                pending.get(allocation.trade_id, 0) \
                + allocation.amount_pending

        for position in positions:
            if position is quote:
                continue
            for leg, is_short in (("long", False), ("short", True)):
                amount = getattr(position, f"{leg}_amount")
                cost = getattr(position, f"{leg}_cost")
                lots = [t for t in trades
                        if t.target_symbol == position.symbol
                        and bool(t.is_short) == is_short]
                lot_amount = sum(t.available_amount for t in lots)
                lot_cost = sum(
                    t.open_price
                    * (t.available_amount + pending.get(t.id, 0))
                    for t in lots
                )
                name = f"{position.symbol} {leg} leg"
                if amount < 0 or cost < 0:
                    violations.append(
                        f"{name} is negative ({amount}, cost {cost})")
                if not _close(amount, lot_amount):
                    violations.append(
                        f"{name} {amount} != open lots {lot_amount}")
                if not _close(cost, lot_cost):
                    violations.append(
                        f"{name} cost {cost} != lot cost {lot_cost}")
            if self._mode == PositionMode.NETTING \
                    and position.long_amount and position.short_amount:
                violations.append(
                    f"{position.symbol} holds a long and a short leg in "
                    f"NETTING mode")

        if violations:
            raise ScenarioStateError(violations)

    # ----------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------

    def _ensure_open(self):
        if self._closed:
            raise ScenarioSetupError("The scenario is closed.")

    @contextmanager
    def _activate(self):
        self._ensure_open()
        with activate_event_memory(self._state):
            yield

    @contextmanager
    def _clock(self, at):
        configuration = self._services.configuration_service()
        configuration.add_value(INDEX_DATETIME, at)
        try:
            yield
        finally:
            configuration.add_value(INDEX_DATETIME, self._start)

    @staticmethod
    def _check_strategy(call, strategy):
        if not isinstance(strategy, TradingStrategy):
            raise ScenarioSetupError(
                f"{call}: strategy must be a TradingStrategy instance.")
        if id(strategy) in _bound_strategies:
            raise ScenarioSetupError(
                f"{call}: this {type(strategy).__name__} instance belongs "
                f"to an open scenario. Create a new instance per "
                f"scenario.")
        if strategy._last_run is not None \
                or strategy._cooldown_bar_index \
                or strategy._cooldown_tracker._last_event \
                or strategy._cooldown_remaining \
                or strategy._scale_out_counts \
                or strategy._last_system_exit_scan_at is not None:
            raise ScenarioSetupError(
                f"{call}: this {type(strategy).__name__} instance has "
                f"already run or holds cooldown state. Create a new "
                f"instance per scenario.")

    @staticmethod
    def _portfolio_configuration(
        call, strategy, initial_cash, trading_symbol, market,
        position_mode, configuration,
    ):
        if configuration is not None:
            if not isinstance(configuration, PortfolioConfiguration):
                raise ScenarioSetupError(
                    f"{call}: portfolio_configuration must be a "
                    f"PortfolioConfiguration.")
            if (trading_symbol, market, position_mode) != (None,) * 3:
                raise ScenarioSetupError(
                    f"{call}: pass trading_symbol, market and "
                    f"position_mode inside portfolio_configuration, "
                    f"not next to it.")
            balance = configuration.initial_balance
            if balance is not None and not _close(balance, initial_cash):
                raise ScenarioSetupError(
                    f"{call}: initial_cash {initial_cash} conflicts with "
                    f"portfolio_configuration.initial_balance {balance}. "
                    f"Make them equal or leave initial_balance unset.")
            return configuration

        if not trading_symbol or not isinstance(trading_symbol, str):
            raise ScenarioSetupError(
                f"{call}: trading_symbol is required, e.g. 'EUR'.")
        try:
            position_mode = PositionMode(
                position_mode or PositionMode.NETTING)
        except ValueError:
            raise ScenarioSetupError(
                f"{call}: position_mode must be a PositionMode (got "
                f"{position_mode!r}).")
        if market is None:
            markets = {
                ds.market for ds in strategy.data_sources
                if getattr(ds, "market", None)
            }
            if len(markets) != 1:
                raise ScenarioSetupError(
                    f"{call}: pass market=...; the strategy's data "
                    f"sources name {sorted(markets) or 'no market'}.")
            market = markets.pop()
        return PortfolioConfiguration(
            market=market,
            trading_symbol=trading_symbol,
            initial_balance=initial_cash,
            position_mode=position_mode,
        )

    def _check_symbol(self, call, symbol):
        if not isinstance(symbol, str) or not symbol or "/" in symbol:
            raise ScenarioSetupError(
                f"{call}: symbol must be a base symbol such as 'BTC'.")
        if symbol.upper() == self._trading_symbol:
            raise ScenarioSetupError(
                f"{call}: {symbol} is the trading symbol; seed cash "
                f"through initial_cash.")
        return symbol.upper()

    @staticmethod
    def _check_positive(call, **values):
        for name, value in values.items():
            if not _number(value) or value <= 0:
                raise ScenarioSetupError(
                    f"{call}: {name} must be a finite number > 0 "
                    f"(got {value!r}).")

    def _check_time(self, call, name, at, after=()):
        if at is None:
            at = self._start
        if not isinstance(at, datetime) or at.tzinfo is None:
            raise ScenarioSetupError(
                f"{call}: {name} must be a timezone-aware datetime "
                f"(got {at!r}).")
        if at > self._start:
            raise ScenarioSetupError(
                f"{call}: {name} {at.isoformat()} is after the scenario "
                f"start {self._start.isoformat()}. Seeded history lies "
                f"at or before the start.")
        for event, when in after:
            if when is not None and at < when:
                raise ScenarioSetupError(
                    f"{call}: {name} {at.isoformat()} is before {event} "
                    f"at {when.isoformat()}. Use a later time.")
        return at

    def _position(self, symbol):
        positions = self._services.position_service().get_all(
            {"symbol": symbol})
        return positions[0] if positions else None

    def _open_orders(self, side, symbol=None):
        return [
            o for o in self._services.order_service().get_all(
                {"status": "OPEN"})
            if o.order_side == side.value
            and symbol in (None, o.target_symbol)
        ]

    def _check_cash(self, call, needed):
        cash = self._services.portfolio_service().get_all()[0].unallocated
        if _exceeds(needed, cash):
            reserved = sum(
                o.price * (o.amount - (o.filled or 0))
                for side in (OrderSide.BUY, OrderSide.SHORT,
                             OrderSide.COVER)
                for o in self._open_orders(side)
            )
            raise ScenarioSetupError(
                f"{call}: needs {needed} {self._trading_symbol} but "
                f"{cash} {self._trading_symbol} is unallocated "
                f"(initial_cash {self.initial_cash}, pending order "
                f"reservations {reserved}). Raise initial_cash or "
                f"reduce the order."
            )

    def _check_entry(self, call, symbol, short, amount, price, fee=0.0):
        position = self._position(symbol)
        if self._mode == PositionMode.NETTING and position is not None:
            opposite = position.long_amount if short \
                else position.short_amount
            if opposite:
                held = "long" if short else "short"
                raise ScenarioSetupError(
                    f"{call}: {symbol} already holds a {held} leg of "
                    f"{opposite} and NETTING allows one direction per "
                    f"symbol. Use position_mode=PositionMode.HEDGE to "
                    f"hold both."
                )
        self._check_cash(call, amount * price + fee)

    def _create_entry(self, symbol, short, amount, price, apply_rules):
        if short:
            order = self._context.create_short_order(
                target_symbol=symbol, price=price, amount=amount)
        else:
            order = self._context.create_limit_order(
                target_symbol=symbol, order_side="BUY", price=price,
                amount=amount)

        if not apply_rules:
            return order

        # Same lookup and attachment as AttachRiskRulesPhase.
        strategy = self.strategy
        lookup = (symbol, "short" if short else "long") \
            if self._mode == PositionMode.HEDGE else (symbol,)
        for rule, attach in (
            (strategy.get_stop_loss_rule(*lookup),
             self._context.add_stop_loss),
            (strategy.get_take_profit_rule(*lookup),
             self._context.add_take_profit),
        ):
            if rule is not None:
                attach(
                    order=order,
                    percentage=rule.percentage_threshold,
                    trailing=rule.trailing,
                    sell_percentage=rule.sell_percentage,
                    mirror_on_exchange=rule.mirror_on_exchange,
                )
        return order

    def _add_rule(self, name, trade, percentage, trailing,
                  sell_percentage, created_at):
        call = _call(name, getattr(trade, "id", trade),
                     percentage=percentage, trailing=trailing or None,
                     sell_percentage=sell_percentage,
                     created_at=created_at)

        with self._activate():
            self._check_positive(call, percentage=percentage)
            if not _number(sell_percentage) \
                    or not 0 < sell_percentage <= 100:
                raise ScenarioSetupError(
                    f"{call}: sell_percentage must be in (0, 100] "
                    f"(got {sell_percentage!r}).")
            trades = self._services.trade_service().get_all(
                {"status": "OPEN"})
            stored = next(
                (t for t in trades if t.id == getattr(trade, "id", None)),
                None)
            if stored is None:
                raise ScenarioSetupError(
                    f"{call}: the trade is not an open trade of this "
                    f"scenario. Pass a trade returned by open_trade.")
            kind, existing = ("stop-losses", stored.stop_losses) \
                if name == "add_stop_loss" \
                else ("take-profits", stored.take_profits)
            used = sum(rule.sell_percentage for rule in existing)
            if _exceeds(used + sell_percentage, 100):
                raise ScenarioSetupError(
                    f"{call}: the trade's {kind} already sell {used}%, "
                    f"so another {sell_percentage}% exceeds 100%. Lower "
                    f"sell_percentage.")
            at = self._check_time(
                call, "created_at", created_at,
                [(f"trade {stored.id} opened", stored.opened_at)])
            with self._clock(at):
                created = getattr(self._context, name)(
                    trade=stored, percentage=percentage,
                    trailing=trailing, sell_percentage=sell_percentage,
                    created_at=at,
                )
            self._check()
            return created


class _ScopedContext:
    """Proxy that runs each method call of the wrapped framework
    object (the :class:`Context`, or a service reached through it)
    against its scenario's state."""

    def __init__(self, scenario, target=None):
        self._scenario = scenario
        self._target = target

    def __getattr__(self, name):
        scenario = self._scenario
        scenario._ensure_open()
        target = scenario._context if self._target is None \
            else self._target
        value = getattr(target, name)
        if not callable(value):
            if type(value).__module__.startswith(
                    "investing_algorithm_framework"):
                return _ScopedContext(scenario, value)
            return value

        @wraps(value)
        def call(*args, **kwargs):
            with scenario._activate():
                return value(*args, **kwargs)
        return call
