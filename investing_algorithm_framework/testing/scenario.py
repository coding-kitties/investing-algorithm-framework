"""StrategyScenario: a seeded, isolated portfolio for strategy tests."""
import math
import weakref
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from tempfile import TemporaryDirectory
from typing import Any, Callable, Optional

import pandas as pd
import polars as pl

from investing_algorithm_framework.app import App, TradingStrategy
from investing_algorithm_framework.dependency_container import \
    DependencyContainer
from investing_algorithm_framework.domain import BacktestDateRange, \
    DataType, INDEX_DATETIME, RESOURCE_DIRECTORY, OperationalException, \
    Order, OrderSide, OrderStatus, OrderType, Portfolio, \
    PortfolioConfiguration, Position, PositionMode, ScenarioSetupError, \
    ScenarioStateError, StopLossRule, TakeProfitRule, CooldownRule, \
    TimeFrame, Trade, TradeStatus, TradeStopLoss, TradeTakeProfit
from investing_algorithm_framework.domain.models.signal import (
    Signal, SignalSide,
)
from investing_algorithm_framework.infrastructure.repositories \
    .event_memory import EventMemoryState, activate_event_memory
from investing_algorithm_framework.services.strategy_phases \
    .record_cooldown import record_emission
from investing_algorithm_framework.services.strategy_phases \
    .resolve_conflicts import _TRACKER_SIDE
from investing_algorithm_framework.services.data_providers \
    .data_provider_service import DataProviderService
from investing_algorithm_framework.services.strategy_phases import (
    ApplyRiskBudgetPhase, PhaseState, ResolveConflictsPhase,
    SizedIntent, SizePositionsPhase,
)
from investing_algorithm_framework.services.indicator_engine import (
    _completion, _normalize,
)
from investing_algorithm_framework.services.trade_order_evaluator \
    .backtest_trade_oder_evaluator import BacktestTradeOrderEvaluator

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


@dataclass(frozen=True)
class ScenarioOrderPreview:
    """Non-emitted order intents and production phase diagnostics.

    ``orders`` is empty when blocked. A signal flip can produce both a
    closing and an opening intent. Amounts are pre-executor quantities,
    without fills, exchange rounding, fees or slippage.
    """

    orders: tuple[SizedIntent, ...]
    traces: tuple[tuple[str, object], ...]

    @property
    def approved(self) -> bool:
        return bool(self.orders)


@dataclass(frozen=True)
class ScenarioCooldownPreview:
    """Cooldown state at the next evaluation, without consuming a bar.

    ``rules`` contains active rules blocking the requested signal side.
    ``remaining_bars`` includes the next bar and is the longest wait
    across those rules and the policy-applicable scaling countdown.
    Other eligibility gates are not part of this preview.
    """

    remaining_bars: int
    rules: tuple[CooldownRule, ...]
    scaling_remaining_bars: int

    @property
    def blocked(self) -> bool:
        return self.remaining_bars > 0


@dataclass(frozen=True)
class ScenarioStepResult:
    """Detached snapshots from one scheduled evaluation.

    ``signals`` are raw strategy signals, not necessarily approved.
    ``orders`` were created this step, including protective exits.
    ``filled_orders`` gained a fill this step, including partial fills.
    New orders normally fill on a later step, not retroactively against
    the candles that produced their signals.
    """

    datetime: datetime
    signals: tuple[Signal, ...]
    orders: tuple[Order, ...]
    filled_orders: tuple[Order, ...]
    traces: tuple[tuple[str, object], ...]


class _ScenarioPrices(DataProviderService):
    def __init__(self, prices, trading_symbol, call):
        super().__init__()
        self.prices = prices
        self.trading_symbol = trading_symbol
        self.call = call

    def get_ticker_data(self, symbol, market, date):
        pair = symbol.upper()
        if pair not in self.prices:
            raise ScenarioSetupError(
                f"{self.call}: no price supplied for {pair}. Pass its "
                f"base symbol in prices, e.g. prices={{'ETH': 100}}; "
                f"prices must be in {self.trading_symbol}."
            )
        price = self.prices[pair]
        return {"bid": price, "ask": price}


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

    Register a data generator to drive scheduled :meth:`step` evaluations
    or :meth:`advance_bars`, including production order/fill processing.
    Existing preview methods remain non-mutating and do not advance time.

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
        start (datetime): Timezone-aware initial scenario time, on the hour.
            Required unless start_date is supplied.
        start_date (datetime, optional): Alias for start. If both are given,
            they must identify the same instant.
        end_date (datetime, optional): Inclusive stepping limit, at or after
            the initial time. None (default) leaves stepping unbounded.
        trading_symbol (str): Quote currency, e.g. ``"EUR"``.
        market (str, optional): Market name. Defaults to the single
            market named by the strategy's data sources.
        position_mode (PositionMode, optional): NETTING (default) or
            HEDGE.
        portfolio_configuration (PortfolioConfiguration, optional):
            Use instead of ``trading_symbol``, ``market`` and
            ``position_mode``.
        data_generator (callable, optional): Datetime-based market-data
            callback; alternatively use :meth:`register_data_generator`.

    Raises:
        ScenarioSetupError: If the arguments describe no valid
            portfolio, or the strategy is in use or has already run.
    """

    def __init__(
        self,
        strategy: TradingStrategy,
        *,
        initial_cash: float,
        start: Optional[datetime] = None,
        trading_symbol: Optional[str] = None,
        market: Optional[str] = None,
        position_mode: Optional[PositionMode] = None,
        portfolio_configuration: Optional[PortfolioConfiguration] = None,
        data_generator: Optional[
            Callable[[datetime], Mapping[str, Any]]
        ] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        self._closed = True
        call = "StrategyScenario(...)"
        self._check_strategy(call, strategy)
        if data_generator is not None and not callable(data_generator):
            raise ScenarioSetupError(
                f"{call}: data generator must be callable."
            )

        if not _number(initial_cash) or initial_cash < 0:
            raise ScenarioSetupError(
                f"{call}: initial_cash must be a finite number >= 0 "
                f"(got {initial_cash!r})."
            )

        if start is not None and start_date is not None \
                and start != start_date:
            raise ScenarioSetupError(
                f"{call}: start and start_date must identify the same time."
            )
        if start is None:
            start = start_date
        if not isinstance(start, datetime) or start.tzinfo is None \
                or start.timestamp() % 3600:
            raise ScenarioSetupError(
                f"{call}: start must be a timezone-aware datetime on the "
                f"UTC hour (got {start!r}). Pass e.g. "
                f"datetime(2024, 1, 1, tzinfo=timezone.utc)."
            )
        if end_date is not None:
            if not isinstance(end_date, datetime) or end_date.tzinfo is None \
                    or end_date.utcoffset() is None:
                raise ScenarioSetupError(
                    f"{call}: end_date must be a timezone-aware datetime "
                    f"or None (got {end_date!r})."
                )
            if end_date < start:
                raise ScenarioSetupError(
                    f"{call}: end_date must be at or after start."
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
        self._data_generator = data_generator
        self._source_generators: dict[
            str, Callable[[datetime], Any]
        ] = {}
        self._end_date = end_date
        self._stepping = False
        self._step_failed = False
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
            self._evaluator = BacktestTradeOrderEvaluator(
                trade_service=self._services.trade_service(),
                order_service=self._services.order_service(),
                trade_stop_loss_service=self._services
                .trade_stop_loss_service(),
                trade_take_profit_service=self._services
                .trade_take_profit_service(),
                configuration_service=self._services.configuration_service(),
                context=self._context,
                trading_costs=configuration.trading_costs,
                portfolio_configuration=configuration,
            )

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

    def register_data_generator(
        self,
        generator: Callable[[datetime], Mapping[str, Any]] | str,
        symbol_generator: Optional[Callable[[datetime], Any]] = None,
    ) -> None:
        """Register an offline market-data callback for scheduled steps.

        Called with each evaluation datetime. Return pandas/Polars frames
        keyed by every declared data-source ID. Include sufficient history
        for indicators and fills since the preceding step. OHLCV frames
        need Open/High/Low/Close/Volume and a datetime index or column;
        timestamps are candle opening times. Only completed candles are
        passed to the strategy and fill evaluator.

        The callback generates input data, not a replacement Context.
        It must not mutate the scenario itself.
        Portfolio state remains owned by the scenario. All held/ordered
        assets must have a declared OHLCV source in the quote currency;
        for multiple timeframes, the finest source supplies fill prices.

        Alternatively register_data_generator("BTC", callback) registers
        one OHLCV source. The callback receives the same datetime and returns
        a frame or an iterable of candle records (timestamp and
        open/high/low/close/volume). A base symbol must resolve to one source;
        use its exact data-source ID when ambiguous. Register every declared
        source, and do not mix this mode with a whole-strategy callback.
        """
        self._ensure_open()
        if self._stepping or self._step_failed:
            raise ScenarioSetupError(
                "Cannot replace the data generator during a step or after "
                "a failed evaluation. Create a fresh scenario after failure."
            )
        if isinstance(generator, str):
            if not callable(symbol_generator):
                raise ScenarioSetupError(
                    "A symbol/source generator must be callable."
                )
            if self._data_generator is not None:
                raise ScenarioSetupError(
                    "Cannot mix symbol generators with a whole-strategy "
                    "data generator."
                )
            sources = [
                source for source in self.strategy.data_sources or []
                if source.get_identifier() == generator
            ]
            if not sources:
                symbol = self._check_symbol(
                    _call("register_data_generator", generator), generator,
                )
                sources = [
                    source for source in self.strategy.data_sources or []
                    if source.symbol == f"{symbol}/{self._trading_symbol}"
                    and DataType.OHLCV.equals(source.data_type)
                ]
            if len(sources) != 1 or not DataType.OHLCV.equals(
                sources[0].data_type,
            ):
                raise ScenarioSetupError(
                    f"{generator!r} must resolve to one declared OHLCV "
                    "source. Use an exact data-source ID when ambiguous."
                )
            self._source_generators[sources[0].get_identifier()] = (
                symbol_generator
            )
            return
        if not callable(generator) or symbol_generator is not None:
            raise ScenarioSetupError("data generator must be callable.")
        if self._source_generators:
            raise ScenarioSetupError(
                "Cannot mix a whole-strategy data generator with "
                "symbol generators."
            )
        self._data_generator = generator

    def step(self) -> ScenarioStepResult:
        """Advance to the next scheduled time, evaluate fills, then strategy.

        Reuses the production backtest evaluator and run_strategy pipeline,
        including overridden phases/executors, trading costs, risk rules,
        hooks and cooldown bookkeeping. New orders are pending until a later
        eligible completed candle. No exchange or data-provider fetch runs.

        Generator/data validation errors leave time and trading state
        unchanged. Evaluation failures can leave partial effects: inspect
        them, but use a fresh scenario rather than retrying the failed tick.
        Earlier successful steps in advance_bars are not rolled back.
        """
        self._ensure_open()
        if self._stepping or self._step_failed:
            raise ScenarioSetupError(
                "Cannot step recursively or after a failed evaluation. "
                "Create a fresh scenario after failure."
            )
        if self._data_generator is None and not self._source_generators:
            raise ScenarioSetupError(
                "Register a market-data callback with "
                "register_data_generator before stepping."
            )
        at = self._next_step_time(self.now)
        self._stepping = True
        try:
            generated = (
                self._data_generator(at)
                if self._data_generator is not None else {
                    identifier: self._source_frame(callback(at), identifier)
                    for identifier, callback in self._source_generators.items()
                }
            )
            data, quotes, candles = self._generated_data(generated, at)
            with self._activate(), self._strategy_context():
                services = self._services
                positions = services.position_service().get_all()
                required = {
                    f"{position.symbol}/{self._trading_symbol}"
                    for position in positions
                    if position.symbol != self._trading_symbol
                }
                required.update(
                    order.symbol for order in services.order_service()
                    .get_all({"status": "OPEN"})
                )
                required.update(
                    trade.symbol for trade in services.trade_service()
                    .get_all({"status": "OPEN"})
                )
                missing = required - quotes.keys()
                if missing:
                    raise ScenarioSetupError(
                        f"step({at!r}): no completed OHLCV prices for "
                        f"{sorted(missing)}. Declare and generate their "
                        f"data sources."
                    )
                before = {
                    order.id: order.filled or 0
                    for order in services.order_service().get_all()
                }
                previous_provider = self._context.data_provider_service
                self._context.data_provider_service = _ScenarioPrices(
                    quotes, self._trading_symbol, _call("step", at),
                )
                self._step_failed = True
                services.configuration_service().add_value(INDEX_DATETIME, at)
                try:
                    dispatcher = services.trade_service().trade_hook_dispatcher
                    dispatcher.configure([self.strategy], self._context)
                    self._evaluator.evaluate(
                        open_trades=services.trade_service().get_all(
                            {"status": "OPEN"},
                        ),
                        open_orders=services.order_service().get_all(
                            {"status": "OPEN"},
                        ),
                        ohlcv_data=candles,
                    )
                    self.strategy.run_strategy(self._context, data)
                    emission_errors = [
                        detail for name, detail in self.strategy.traces
                        if name == "emit_orders.error"
                    ]
                    if emission_errors:
                        raise OperationalException(
                            f"step({at!r}): order emission failed: "
                            f"{emission_errors!r}"
                        )
                    self.strategy._last_run = at
                    self._check()
                    orders = services.order_service().get_all()
                    result = ScenarioStepResult(
                        datetime=at,
                        signals=tuple(deepcopy(self.strategy.last_signals)),
                        orders=tuple(deepcopy([
                            order for order in orders if order.id not in before
                        ])),
                        filled_orders=tuple(deepcopy([
                            order for order in orders
                            if (order.filled or 0) > before.get(order.id, 0)
                        ])),
                        traces=tuple(deepcopy(self.strategy.traces)),
                    )
                    self._last_bars_ago.clear()
                    self._step_failed = False
                    return result
                finally:
                    if self._step_failed:
                        self._context.data_provider_service = previous_provider
        finally:
            self._stepping = False

    def advance_bars(self, count: int = 1) -> tuple[ScenarioStepResult, ...]:
        """Run count scheduled evaluations; a bar is one strategy tick.

        Check the whole requested schedule before evaluating any bar.
        Exceeding end_date raises without advancing time or trading state.
        """
        self._ensure_open()
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ScenarioSetupError("advance_bars count must be an int >= 1.")
        at = self.now
        for _ in range(count):
            at = self._next_step_time(at)
        return tuple(self.step() for _ in range(count))

    def _next_step_time(self, after: datetime) -> datetime:
        at = self.strategy.schedule.next_run_after(after)
        if at is None:
            raise ScenarioSetupError("The strategy has no next scheduled run.")
        if self._end_date is not None and at > self._end_date:
            raise ScenarioSetupError(
                f"Scheduled evaluation {at.isoformat()} exceeds end_date "
                f"{self._end_date.isoformat()}."
            )
        return at

    @staticmethod
    def _source_frame(raw, identifier):
        if not isinstance(raw, (pd.DataFrame, pl.DataFrame)):
            if not isinstance(raw, Iterable) \
                    or isinstance(raw, (str, bytes, Mapping)):
                raise ScenarioSetupError(
                    f"Source {identifier}: return a frame or iterable "
                    "of OHLCV records."
                )
            records = list(raw)
            if any(not isinstance(row, Mapping) for row in records):
                raise ScenarioSetupError(
                    f"Source {identifier}: each candle record must be a "
                    "mapping."
                )
            if not records:
                return pd.DataFrame(
                    columns=["Open", "High", "Low", "Close", "Volume"],
                    index=pd.DatetimeIndex([], tz="UTC"),
                )
            raw = pd.DataFrame.from_records(records)
        names = {
            "timestamp": "Datetime", "datetime": "Datetime",
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        }
        renames = {
            column: names[str(column).lower()] for column in raw.columns
            if str(column).lower() in names
        }
        return (
            raw.rename(columns=renames) if isinstance(raw, pd.DataFrame)
            else raw.rename(renames)
        )

    def _generated_data(self, generated, at):
        call = _call("step", at)
        if not isinstance(generated, Mapping):
            raise ScenarioSetupError(
                f"{call}: data generator must return a mapping of "
                "data-source IDs to frames."
            )
        sources = {
            source.get_identifier(): source
            for source in self.strategy.data_sources or []
        }
        if generated.keys() != sources.keys():
            raise ScenarioSetupError(
                f"{call}: generated data-source IDs must match the strategy; "
                f"missing={sorted(sources.keys() - generated.keys())}, "
                f"unexpected={list(generated.keys() - sources.keys())}."
            )
        data, quotes, candles, resolutions = {}, {}, {}, {}
        for identifier, source in sources.items():
            raw = generated[identifier]
            try:
                frame = _normalize(raw, identifier, preserve=True)
            except (TypeError, ValueError) as error:
                raise ScenarioSetupError(f"{call}: {error}") from error
            is_ohlcv = DataType.OHLCV.equals(source.data_type)
            if is_ohlcv and (
                source.time_frame is None
                or source.time_frame == TimeFrame.CURRENT
            ):
                raise ScenarioSetupError(
                    f"{call}: {identifier} needs a candle timeframe."
                )
            available = (
                _completion(frame.index, source.time_frame.value)
                if is_ohlcv else frame.index
            )
            completed = available <= at
            frame = frame.loc[completed]
            if source.pandas:
                data[identifier] = frame
            elif isinstance(raw, pl.DataFrame):
                data[identifier] = raw.filter(pl.Series(completed))
            else:
                normalized = frame.drop(columns=["Datetime"], errors="ignore")
                data[identifier] = pl.from_pandas(
                    normalized.rename_axis("Datetime").reset_index(),
                )
            if not is_ohlcv:
                continue
            columns = ["Open", "High", "Low", "Close", "Volume"]
            if any(column not in frame for column in columns):
                raise ScenarioSetupError(
                    f"{call}: {identifier} requires OHLCV columns {columns}."
                )
            if frame.empty:
                continue
            values = frame[columns]
            if any(
                not pd.api.types.is_numeric_dtype(values[column])
                or pd.api.types.is_bool_dtype(values[column])
                or pd.api.types.is_complex_dtype(values[column])
                for column in columns
            ):
                raise ScenarioSetupError(
                    f"{call}: {identifier} OHLCV values must be numeric."
                )
            if not (
                values.notna().all().all()
                and values.abs().lt(float("inf")).all().all()
                and values[columns[:4]].gt(0).all().all()
                and values["Volume"].ge(0).all()
                and values["Low"].le(values[["Open", "Close"]].min(axis=1))
                .all()
                and values["High"].ge(values[["Open", "Close"]].max(axis=1))
                .all()
            ):
                raise ScenarioSetupError(
                    f"{call}: {identifier} contains invalid OHLCV candles."
                )
            pair = source.symbol
            if pair is None or not pair.endswith(f"/{self._trading_symbol}"):
                raise ScenarioSetupError(
                    f"{call}: {identifier} needs an OHLCV pair in "
                    f"{self._trading_symbol}."
                )
            resolution = source.time_frame.amount_of_minutes
            if pair not in resolutions or resolution < resolutions[pair]:
                resolutions[pair] = resolution
                quotes[pair] = float(frame["Close"].iloc[-1])
                execution = values.copy()
                execution.index.name = "Datetime"
                candles[pair] = pl.from_pandas(execution.reset_index())
        return data, quotes, candles

    def get_position_size(
        self, symbol: str, *, price: float,
        prices: Optional[Mapping[str, float]] = None,
    ) -> float:
        """Return the strategy's raw allocation in quote currency.

        Calls the overridable ``strategy.get_position_size(symbol)`` and
        the returned rule's ``get_size`` with the scenario portfolio.
        No eligibility, scaling, cash or exposure limits are applied.
        ``price`` values the target asset; ``prices`` supplies current
        quote-currency prices for other base symbols in the portfolio,
        including positions created by pending orders.
        """
        call = _call("get_position_size", symbol, price=price)
        with self._sizing_context(call, symbol, price, prices) as symbol:
            rule = self.strategy.get_position_size(symbol)
            if rule is None:
                raise ScenarioSetupError(
                    f"{call}: strategy.get_position_size({symbol!r}) "
                    f"returned None. Return a PositionSize rule."
                )
            size = rule.get_size(self._context.get_portfolio(), price)
            if not _number(size) or size < 0:
                raise ScenarioSetupError(
                    f"{call}: sizing rule must return a finite allocation "
                    f">= 0 in {self._trading_symbol} (got {size!r})."
                )
            return float(size)

    def get_stop_loss_rule(
        self, symbol: str, *, side: str = "long",
    ) -> Optional[StopLossRule]:
        """Inspect the strategy's effective rule through its override.

        ``side`` means position direction (long/short), not order side.
        Side-specific lookup applies only in HEDGE, matching execution.
        None means no configured rule. No trade or rule row is created.
        """
        with self._activate(), self._strategy_context():
            return self._get_risk_rule(
                "get_stop_loss_rule", symbol, side,
            )

    def get_take_profit_rule(
        self, symbol: str, *, side: str = "long",
    ) -> Optional[TakeProfitRule]:
        """Inspect the effective take-profit rule; see get_stop_loss_rule."""
        with self._activate(), self._strategy_context():
            return self._get_risk_rule(
                "get_take_profit_rule", symbol, side,
            )

    def get_cooldown_rules(self, symbol: str) -> tuple[CooldownRule, ...]:
        """Return symbol and portfolio-scoped configuration, active or not."""
        call = _call("get_cooldown_rules", symbol)
        with self._activate():
            symbol = self._check_symbol(call, symbol)
            return tuple(
                rule for rule in self.strategy.cooldowns
                if rule.applies_to_symbol(symbol)
            )

    def preview_stop_loss(
        self, symbol: str, *, price: float, amount: float = 1,
        side: str = "long",
        prices: Optional[Mapping[str, float]] = None,
    ) -> Optional[TradeStopLoss]:
        """Build a detached production risk model for a hypothetical fill.

        The preview has trade_id=0 and is never persisted. Inspect its
        stop_loss_price and sell_amount, or test trailing updates and
        has_triggered on it without changing scenario state. It does not
        check order eligibility. ``side`` is long/short; ``prices`` has
        the same meaning as in get_position_size for contextual overrides.
        None means no effective strategy rule.
        """
        call = _call("preview_stop_loss", symbol, price=price, amount=amount)
        with self._sizing_context(call, symbol, price, prices) as symbol:
            rule = self._get_risk_rule("get_stop_loss_rule", symbol, side)
            return self._preview_risk(
                call, rule, TradeStopLoss, price, amount, side,
            )

    def preview_take_profit(
        self, symbol: str, *, price: float, amount: float = 1,
        side: str = "long",
        prices: Optional[Mapping[str, float]] = None,
    ) -> Optional[TradeTakeProfit]:
        """Build a detached take-profit model; see preview_stop_loss.

        A trailing take-profit's take_profit_price is initially None:
        the production model arms it only after a favorable price move.
        """
        call = _call("preview_take_profit", symbol, price=price, amount=amount)
        with self._sizing_context(call, symbol, price, prices) as symbol:
            rule = self._get_risk_rule("get_take_profit_rule", symbol, side)
            return self._preview_risk(
                call, rule, TradeTakeProfit, price, amount, side,
            )

    def preview_cooldown(
        self, symbol: str, *, side: SignalSide = SignalSide.OPEN_LONG,
    ) -> ScenarioCooldownPreview:
        """Inspect blocking rules and remaining bars without ticking state.

        Uses the production cooldown tracker at the next bar index,
        including portfolio scope, HEDGE legs and scaling countdowns.
        The conflict policy's cooldown_blocks controls scaling countdowns,
        just as in the production eligibility phase.
        """
        call = _call("preview_cooldown", symbol, side=side)
        rules = self.get_cooldown_rules(symbol)
        with self._activate():
            symbol = self._check_symbol(call, symbol)
            if not isinstance(side, SignalSide):
                raise ScenarioSetupError(
                    f"{call}: side must be a SignalSide."
                )
            strategy = self.strategy
            position_side = (
                "long" if side.is_long else "short"
            ) if self._mode == PositionMode.HEDGE else None
            active = []
            remaining = 0
            for rule in rules:
                if not rule.blocks_signal(_TRACKER_SIDE[side]):
                    continue
                bars = strategy._cooldown_tracker.remaining_bars(
                    rule, symbol=symbol,
                    bar_index=strategy._cooldown_bar_index + 1,
                    position_side=position_side,
                )
                if bars > 0:
                    active.append(rule)
                    remaining = max(remaining, bars)
            key = (
                (symbol, position_side)
                if self._mode == PositionMode.HEDGE else symbol
            )
            scaling = (
                max(0, strategy._cooldown_remaining.get(key, 0) - 1)
                if strategy.conflict_policy.is_blocked_by_cooldown(side)
                else 0
            )
            return ScenarioCooldownPreview(
                remaining_bars=max(remaining, scaling),
                rules=tuple(active),
                scaling_remaining_bars=scaling,
            )

    def _get_risk_rule(self, method, symbol, side):
        call = _call(method, symbol, side=side)
        symbol = self._check_symbol(call, symbol)
        if side not in ("long", "short"):
            raise ScenarioSetupError(
                f"{call}: side must be 'long' or 'short'."
            )
        lookup = (
            (symbol, side) if self._mode == PositionMode.HEDGE
            else (symbol,)
        )
        return getattr(self.strategy, method)(*lookup)

    def _preview_risk(self, call, rule, model, price, amount, side):
        self._check_positive(call, amount=amount)
        if rule is None:
            return None
        self._check_positive(call, percentage=rule.percentage_threshold)
        if not _number(rule.sell_percentage) \
                or not 0 < rule.sell_percentage <= 100:
            raise ScenarioSetupError(
                f"{call}: rule sell_percentage must be in (0, 100]."
            )
        return model(
            trade_id=0, percentage=rule.percentage_threshold,
            open_price=price, total_amount_trade=amount,
            sell_percentage=rule.sell_percentage, trailing=rule.trailing,
            is_short=side == "short",
            mirror_on_exchange=rule.mirror_on_exchange,
            created_at=self.now,
        )

    def preview_order(
        self, symbol: str, *, price: float,
        side: SignalSide = SignalSide.OPEN_LONG,
        prices: Optional[Mapping[str, float]] = None,
    ) -> ScenarioOrderPreview:
        """Preview an explicit intent at the next evaluation's bar index.

        Runs production conflict/eligibility, sizing and risk-budget
        phases, honoring strategy sizing overrides. Does not generate
        indicators/signals, submit/fill orders, attach risk rules, scan
        protective exits, or advance the clock/cooldown history.

        Prices have the same meaning as :meth:`get_position_size`.
        Inspect ``orders`` for asset ``amount`` and ``quote_amount``, or
        ``traces`` for gating and budget diagnostics. This is a single
        intent preview, not a simultaneous multi-symbol allocation.
        """
        call = _call("preview_order", symbol, price=price, side=side)
        self._ensure_open()
        if not isinstance(side, SignalSide):
            raise ScenarioSetupError(
                f"{call}: side must be a SignalSide, e.g. "
                f"SignalSide.OPEN_LONG."
            )
        with self._sizing_context(call, symbol, price, prices) as symbol:
            strategy = self.strategy
            remaining = strategy._cooldown_remaining
            strategy._cooldown_remaining = {
                key: bars - 1 for key, bars in remaining.items() if bars > 1
            }
            try:
                state = PhaseState(
                    strategy=strategy, context=self._context, data={},
                    current_datetime=self.now,
                    bar_index=strategy._cooldown_bar_index + 1,
                    raw_signals=[Signal(symbol=symbol, side=side)],
                )
                for phase in (
                    ResolveConflictsPhase(), SizePositionsPhase(),
                    ApplyRiskBudgetPhase(),
                ):
                    phase.run(state)
                orders = []
                for intent in state.sized_intents:
                    if any(
                        not _number(value) or value < 0
                        for value in (intent.amount, intent.quote_amount)
                    ):
                        raise ScenarioSetupError(
                            f"{call}: sizing produced invalid amounts; "
                            f"check the strategy's position/scaling rules."
                        )
                    if intent.amount == 0 or intent.quote_amount == 0:
                        state.trace("preview_order.zero_size", intent)
                        continue
                    orders.append(intent)
                return ScenarioOrderPreview(
                    orders=tuple(orders),
                    traces=tuple(state.traces),
                )
            finally:
                strategy._cooldown_remaining = remaining

    @contextmanager
    def _strategy_context(self):
        previous = self.strategy.context
        self.strategy.context = self._context
        try:
            yield
        finally:
            self.strategy.context = previous

    @contextmanager
    def _sizing_context(self, call, symbol, price, prices):
        with self._activate(), self._strategy_context():
            symbol = self._check_symbol(call, symbol)
            self._check_positive(call, price=price)
            if prices is not None and not isinstance(prices, Mapping):
                raise ScenarioSetupError(
                    f"{call}: prices must map base symbols to prices."
                )
            quotes = {}
            for target, value in (prices or {}).items():
                target = self._check_symbol(call, target)
                self._check_positive(call, **{f"price for {target}": value})
                pair = f"{target}/{self._trading_symbol}"
                if pair in quotes:
                    raise ScenarioSetupError(
                        f"{call}: prices contains duplicate symbol {target}."
                    )
                quotes[pair] = value
            pair = f"{symbol}/{self._trading_symbol}"
            if pair in quotes and quotes[pair] != price:
                raise ScenarioSetupError(
                    f"{call}: price conflicts with prices[{symbol!r}]. "
                    f"Supply one consistent price."
                )
            quotes[pair] = price
            previous_service = self._context.data_provider_service
            self._context.data_provider_service = _ScenarioPrices(
                quotes, self._trading_symbol, call,
            )
            try:
                yield symbol
            finally:
                self._context.data_provider_service = previous_service

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

    def register_position(
        self,
        symbol: str,
        *,
        amount: float,
        price: float,
        direction: str = "long",
        opened_at: Optional[datetime] = None,
        fee: float = 0.0,
        apply_strategy_rules: bool = True,
    ) -> Position:
        """Seed a filled lot through open_trade and return its Position.

        Repeated registrations add lots to the same position. Inspect all
        its lots/orders with get_trades(position=...) and get_orders(
        position=...), including both legs in HEDGE mode. This does not
        replace holdings or link an existing/custom order ID.
        """
        trade = self.open_trade(
            symbol, amount=amount, price=price, direction=direction,
            opened_at=opened_at, fee=fee,
            apply_strategy_rules=apply_strategy_rules,
        )
        with self._activate():
            return self._services.position_service().find({
                "order_id": trade.orders[0].id,
            })

    def get_trades(
        self,
        target_symbol: Optional[str] = None,
        trading_symbol: Optional[str] = None,
        market: Optional[str] = None,
        portfolio: Optional[Portfolio | int] = None,
        status: Optional[TradeStatus | str] = None,
        opened_since: Optional[datetime] = None,
        *,
        position: Optional[Position] = None,
    ) -> list[Trade]:
        """Get trade lots using Context filters and an optional position.

        Filters are combined with AND. Portfolio accepts a Portfolio or ID;
        opened_since is inclusive. With no status, include open/closed lots
        and both HEDGE legs. Omitted filters leave that field unrestricted.
        """
        with self._activate():
            position_id = None if position is None else \
                self._check_position("get_trades", position)
            trades = self._context.get_trades(
                target_symbol=target_symbol, trading_symbol=trading_symbol,
                market=market, portfolio=portfolio, status=status,
                opened_since=opened_since,
            )
            if position is None:
                return trades
            return [
                trade for trade in trades
                if any(order.position_id == position_id
                       for order in trade.orders)
            ]

    def get_orders(
        self,
        target_symbol: Optional[str] = None,
        status: Optional[OrderStatus | str] = None,
        order_type: Optional[OrderType | str] = None,
        order_side: Optional[OrderSide | str] = None,
        market: Optional[str] = None,
        *,
        position: Optional[Position] = None,
    ) -> list[Order]:
        """Get orders using Context filters and an optional position.

        Filters are combined with AND. With no status, include filled
        entries and pending exits. Preserve Context's result ordering.
        """
        with self._activate():
            position_id = None if position is None else \
                self._check_position("get_orders", position)
            orders = self._context.get_orders(
                target_symbol=target_symbol, status=status,
                order_type=order_type, order_side=order_side, market=market,
            )
            if position is None:
                return orders
            return [
                order for order in orders if order.position_id == position_id
            ]

    def _check_position(self, method: str, position: Position) -> int:
        if not isinstance(position, Position):
            raise ScenarioSetupError(
                f"{method}: position must be a Position from this scenario."
            )
        matches = self._services.position_service().get_all({
            "id": position.id,
            "portfolio": position.portfolio_id,
            "symbol": position.symbol,
        })
        if position.id is None or not matches:
            raise ScenarioSetupError(
                f"{method}: position does not exist in this scenario."
            )
        return position.id

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
                               if a.order_id == order.id
                               and a.trade_id is not None)
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
        previous = self.now
        configuration.add_value(INDEX_DATETIME, at)
        try:
            yield
        finally:
            configuration.add_value(INDEX_DATETIME, previous)

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
            at = self.now
        if not isinstance(at, datetime) or at.tzinfo is None:
            raise ScenarioSetupError(
                f"{call}: {name} must be a timezone-aware datetime "
                f"(got {at!r}).")
        if at > self.now:
            boundary = "start" if self.now == self._start else "time"
            raise ScenarioSetupError(
                f"{call}: {name} {at.isoformat()} is after the scenario "
                f"{boundary} {self.now.isoformat()}. Seeded history lies "
                f"at or before the current time.")
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
