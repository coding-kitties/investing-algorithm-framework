import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Union

import pandas as pd

from investing_algorithm_framework.domain import (
    INDEX_DATETIME, ConflictPolicy, CooldownRule, CooldownTracker,
    DataSource, DataType, ExposureRule, OperationalException, Order,
    Position, PositionSize, ScalingRule, Schedule, ScheduledFunction,
    ScoreCard, Signal, SignalSeries, StopLossRule, StrategyProfile,
    TakeProfitRule, TradingCost, Trade,
)
from ..services.executors import Executor, LimitOrderExecutor
from ..services.strategy_phases import (
    PhaseState, StrategyPhase, build_default_phases,
)
from .context import Context

logger = logging.getLogger(__name__)


class TradingStrategy:
    """
    TradingStrategy is the base class for all trading strategies. A trading
    strategy is a set of rules that defines when to buy or sell an asset.

    Signal surface:
        Strategies override a single :py:meth:`generate_signals` method
        which yields :class:`Signal` instances. Each signal carries a
        :class:`SignalSide` (``OPEN_LONG``, ``CLOSE_LONG``, ``SCALE_IN``,
        ``SCALE_OUT``, ``OPEN_SHORT``, ``CLOSE_SHORT``), an optional
        :pyattr:`Signal.strength` in ``[0.0, 1.0]`` used for top-N
        ranking when capital binds, and a free-form ``source`` /
        ``metadata`` payload that flows through to the order.

    Per symbol the engine keeps at most one open position direction
    (long *or* short, never both). When a short position is open,
    long ``OPEN_LONG``/``SCALE_IN`` signals are dropped until the
    short is covered, and vice versa.

    Pipeline composition:
        ``run_strategy`` is a thin loop over :pyattr:`phases` — by
        default the seven canonical phases (collect → resolve → size
        → risk-budget → emit → attach-rules → record-cooldown).
        Override :pyattr:`phases` to insert/replace/reorder; override
        :pyattr:`conflict_policy` to change how same-symbol signal
        clashes are resolved; override :pyattr:`executor` to swap
        order routing (LIMIT vs MARKET vs bracket vs OCO).

    Attributes:
        algorithm_id (string): the unique id for your
            combined strategy instances. An algorithm consists out of one or
            more strategy instances that run together. The algorithm_id
            is used to uniquely indentify the combined strategy instances.
            This is id is used in various places in the framework, e.g. for
            backtesting results, logging, monitoring etc.
        schedule (Schedule): when this strategy fires. Build with
            ``Schedule.every(interval, time_unit)`` for periodic strategies
            or ``Schedule.on(date_rule, time_rule)`` for calendar-anchored
            strategies (e.g. month-end at 16:00).
        scheduled_functions (List[ScheduledFunction]): additional methods on
            this strategy that should run on independent schedules
            (e.g. a rebalance hook on the last trading day of the month).
        worker_id ((optional) str): the id of the worker
        strategy_id ((optional) str): the id of the strategy
        decorated ((optional) bool): the decorated function
        data_sources (List[DataSource] optional): the list of data
            sources to use for the strategy. The data sources will be used
            to indentify data providers that will be called to gather data
            and pass to the strategy before its run.
        phases (List[StrategyPhase] optional): the ordered list of
            phases run by :py:meth:`run_strategy`. Defaults to
            :func:`build_default_phases`.
        conflict_policy (ConflictPolicy optional): how same-symbol
            signal clashes are resolved. Defaults to
            :py:meth:`ConflictPolicy.default` (RAISE on direction
            conflict).
        executor (Executor optional): order-routing strategy. Defaults
            to :class:`LimitOrderExecutor`.
        flip_on_opposite_signal (bool optional): when true, an
            ``OPEN_SHORT`` signal closes an existing long before opening
            short, and an ``OPEN_LONG`` signal covers an existing short
            before opening long, on the same strategy tick. Defaults to
            false.
        exposure_rule (ExposureRule optional): caps the total
            percentage of portfolio value that may be invested across
            all positions combined (e.g. "never more than 80%
            invested"). Portfolio-wide, so unlike
            ``scaling_rules``/``position_sizes`` there is only ever
            one, not a per-symbol list. Defaults to None (no cap).
        metadata (optional): Dict[str, Any] - a dictionary
            containing metadata about the strategy. This can be used to
            store additional information about the strategy, such as its
            author, version, description, params etc.
    """
    algorithm_id: str
    schedule: Schedule = None
    scheduled_functions: List[ScheduledFunction] = []
    strategy_id: str = None
    decorated = None
    data_sources: List[DataSource] = []
    pipelines: List[type] = []
    traces = None
    last_signals: List[Signal] = []
    last_score_cards: List[Dict[str, Any]] = []
    context: Context = None
    metadata: Dict[str, Any] = None
    position_sizes: List[PositionSize] = []
    stop_losses: List[StopLossRule] = []
    take_profits: List[TakeProfitRule] = []
    scaling_rules: List[ScalingRule] = []
    trading_costs: List[TradingCost] = []
    cooldowns: List[CooldownRule] = []
    symbols: List[str] = []
    trading_symbol: str = None
    phases: List[StrategyPhase] = None
    conflict_policy: ConflictPolicy = None
    executor: Executor = None
    flip_on_opposite_signal: bool = False
    exposure_rule: ExposureRule = None

    def __init__(
        self,
        algorithm_id=None,
        strategy_id=None,
        schedule: Schedule = None,
        scheduled_functions: List[ScheduledFunction] = None,
        data_sources=None,
        metadata=None,
        position_sizes=None,
        stop_losses=None,
        take_profits=None,
        scaling_rules=None,
        trading_costs=None,
        cooldowns=None,
        symbols=None,
        trading_symbol=None,
        phases: List[StrategyPhase] = None,
        conflict_policy: ConflictPolicy = None,
        executor: Executor = None,
        flip_on_opposite_signal: bool = None,
        exposure_rule: ExposureRule = None,
        decorated=None
    ):
        if metadata is None:
            metadata = {}

        self.metadata = metadata

        if strategy_id is not None:
            self.strategy_id = strategy_id
        else:
            # Check if class has strategy_id defined as an actual value
            # (not just a type hint, e.g. ``strategy_id: str``).
            class_strategy_id = getattr(self.__class__, 'strategy_id', None)

            if (class_strategy_id is None
                    or isinstance(class_strategy_id, type)):
                self.strategy_id = self.__class__.__name__
            else:
                self.strategy_id = class_strategy_id

        # Initialize algorithm_id: use provided value, fall back to class
        # attribute if set, otherwise None
        if algorithm_id is not None:
            self.algorithm_id = algorithm_id
        elif "algorithm_id" in self.metadata:
            self.algorithm_id = self.metadata["algorithm_id"]
        else:
            # Check if class has algorithm_id defined as an actual value
            # (not just a type hint). Type hints result in the type being
            # returned (e.g., str, int), so we check for that.
            class_algorithm_id = getattr(self.__class__, 'algorithm_id', None)

            # If it's a type (like str, int) or None, it's just a type hint
            # In that case, use the class name as the algorithm_id
            if (class_algorithm_id is None
                    or isinstance(class_algorithm_id, type)):
                self.algorithm_id = None
            else:
                self.algorithm_id = class_algorithm_id

        # Resolve schedule: instance arg > class attribute > error.
        if schedule is not None:
            self.schedule = schedule
        else:
            class_schedule = getattr(self.__class__, 'schedule', None)
            if isinstance(class_schedule, Schedule):
                self.schedule = class_schedule
            else:
                raise OperationalException(
                    f"Schedule not set for strategy instance "
                    f"{self.strategy_id}. Set ``schedule = "
                    f"Schedule.every(...)`` or ``schedule = "
                    f"Schedule.on(...)`` on the class, or pass "
                    f"``schedule=`` to the constructor."
                )

        # Resolve scheduled_functions: instance arg > class attribute > [].
        if scheduled_functions is not None:
            self.scheduled_functions = list(scheduled_functions)
        else:
            class_sfs = getattr(self.__class__, 'scheduled_functions', [])
            self.scheduled_functions = list(class_sfs) if class_sfs else []

        # Initialize data_sources as a new list per instance
        # to avoid sharing the class-level mutable default
        if data_sources is not None:
            self.data_sources = list(data_sources)
        else:
            # Check if class has data_sources defined, copy them
            class_data_sources = getattr(self.__class__, 'data_sources', [])
            self.data_sources = list(class_data_sources) \
                if class_data_sources else []

        # Initialize pipelines as a new list per instance. Pipelines
        # are class-attribute opt-in (see
        # docs/architecture/strategy/pipeline-api.md). When empty, the
        # engine is never invoked and there is zero behavioural change.
        class_pipelines = getattr(self.__class__, 'pipelines', [])
        self.pipelines = list(class_pipelines) if class_pipelines else []

        if decorated is not None:
            self.decorated = decorated

        # Initialize position_sizes as a new list per instance
        if position_sizes is not None:
            self.position_sizes = list(position_sizes)
        else:
            class_position_sizes = getattr(
                self.__class__, 'position_sizes', []
            )
            self.position_sizes = list(class_position_sizes) \
                if class_position_sizes else []

        # Initialize symbols as a new list per instance
        if symbols is not None:
            self.symbols = list(symbols)
        else:
            class_symbols = getattr(self.__class__, 'symbols', [])
            self.symbols = list(class_symbols) if class_symbols else []

        if trading_symbol is not None:
            self.trading_symbol = trading_symbol

        # Check if scheduling interval is faster than the smallest
        # OHLCV data source timeframe. Only meaningful for interval-mode
        # schedules — rule-based schedules (e.g. month-end) cannot be
        # checked here without expanding against a calendar.
        ohlcv_timeframes = [
            ds.time_frame.amount_of_minutes
            for ds in self.data_sources
            if ds.time_frame is not None
            and DataType.OHLCV.equals(ds.data_type)
        ]

        if ohlcv_timeframes and self.schedule.is_interval:
            step = self.schedule.step()
            scheduling_interval = int(step.total_seconds() // 60)
            smallest_timeframe = min(ohlcv_timeframes)

            if scheduling_interval < smallest_timeframe:
                tu = self.schedule.time_unit
                iv = self.schedule.interval
                raise OperationalException(
                    f"Strategy '{self.strategy_id}' scheduling interval "
                    f"({iv} {tu.value.lower()}"
                    f"{'s' if iv > 1 else ''}"
                    f" = {scheduling_interval} min) is faster than "
                    f"the smallest OHLCV data source timeframe "
                    f"({smallest_timeframe} min). The strategy would "
                    f"run without new data. Increase the scheduling "
                    f"interval or use a smaller data timeframe."
                )

        # Validate that every declared pipeline has enough warmup on
        # the strategy's OHLCV data sources to compute its longest
        # factor window. Without this check a live strategy starts
        # silently emitting NaN columns until enough bars accrue.
        if self.pipelines:
            ohlcv_sources = [
                ds for ds in self.data_sources
                if DataType.OHLCV.equals(ds.data_type)
            ]
            if not ohlcv_sources:
                raise OperationalException(
                    f"Strategy '{self.strategy_id}' declares "
                    f"{len(self.pipelines)} pipeline(s) but has no "
                    f"OHLCV data sources. Pipelines build their panel "
                    f"from the strategy's OHLCV data sources — add at "
                    f"least one DataSource(data_type=DataType.OHLCV, "
                    f"...) to data_sources."
                )
            for pipeline_cls in self.pipelines:
                required = pipeline_cls.required_window()
                # We compare against each OHLCV source's warmup_window
                # (canonical) / window_size (legacy alias) — the
                # framework keeps them in sync, but a source may
                # legitimately leave both unset, which we treat as
                # "insufficient" because the pipeline cannot guarantee
                # a full window of data.
                short_sources = [
                    ds for ds in ohlcv_sources
                    if ds.warmup_window is None
                    or ds.warmup_window < required
                ]
                if short_sources:
                    short_desc = ", ".join(
                        f"{ds.symbol}@{ds.time_frame.value if ds.time_frame else '?'}"  # noqa: E501
                        f" (warmup_window="
                        f"{ds.warmup_window if ds.warmup_window is not None else 'unset'})"  # noqa: E501
                        for ds in short_sources
                    )
                    raise OperationalException(
                        f"Strategy '{self.strategy_id}' pipeline "
                        f"'{pipeline_cls.__name__}' requires a "
                        f"warmup window of {required} bars but the "
                        f"following OHLCV data source(s) have an "
                        f"insufficient warmup_window: {short_desc}. "
                        f"Set warmup_window>={required} on each OHLCV "
                        f"DataSource the pipeline relies on, otherwise "
                        f"the pipeline will emit NaN columns until "
                        f"enough bars accrue."
                    )

        # Initialize stop_losses as a new list per instance
        if stop_losses is not None:
            self.stop_losses = list(stop_losses)
        else:
            class_stop_losses = getattr(self.__class__, 'stop_losses', [])
            self.stop_losses = list(class_stop_losses) \
                if class_stop_losses else []

        # Initialize take_profits as a new list per instance
        if take_profits is not None:
            self.take_profits = list(take_profits)
        else:
            class_take_profits = getattr(self.__class__, 'take_profits', [])
            self.take_profits = list(class_take_profits) \
                if class_take_profits else []

        # Initialize scaling_rules as a new list per instance
        if scaling_rules is not None:
            self.scaling_rules = list(scaling_rules)
        else:
            class_scaling_rules = getattr(
                self.__class__, 'scaling_rules', []
            )
            self.scaling_rules = list(class_scaling_rules) \
                if class_scaling_rules else []

        # Initialize trading_costs as a new list per instance
        if trading_costs is not None:
            self.trading_costs = list(trading_costs)
        else:
            class_trading_costs = getattr(
                self.__class__, 'trading_costs', []
            )
            self.trading_costs = list(class_trading_costs) \
                if class_trading_costs else []

        # Initialize cooldowns as a new list per instance
        if cooldowns is not None:
            self.cooldowns = list(cooldowns)
        else:
            class_cooldowns = getattr(self.__class__, 'cooldowns', [])
            self.cooldowns = list(class_cooldowns) \
                if class_cooldowns else []

        # Resolve pipeline composition. Each is instance arg >
        # class attribute > sensible default. Phases and executor are
        # stateless by contract so reusing class-level instances is
        # safe, but we copy phases into a new list so per-instance
        # mutation (e.g. inserting a custom phase) doesn't leak across
        # strategies.
        if phases is not None:
            self.phases = list(phases)
        else:
            class_phases = getattr(self.__class__, 'phases', None)
            if class_phases:
                self.phases = list(class_phases)
            else:
                self.phases = build_default_phases()

        if conflict_policy is not None:
            self.conflict_policy = conflict_policy
        else:
            class_cp = getattr(self.__class__, 'conflict_policy', None)
            if isinstance(class_cp, ConflictPolicy):
                self.conflict_policy = class_cp
            else:
                self.conflict_policy = ConflictPolicy.default()

        if executor is not None:
            self.executor = executor
        else:
            class_ex = getattr(self.__class__, 'executor', None)
            if isinstance(class_ex, Executor):
                self.executor = class_ex
            else:
                self.executor = LimitOrderExecutor()

        if flip_on_opposite_signal is not None:
            self.flip_on_opposite_signal = bool(flip_on_opposite_signal)
        else:
            self.flip_on_opposite_signal = bool(getattr(
                self.__class__, 'flip_on_opposite_signal', False
            ))

        if exposure_rule is not None:
            self.exposure_rule = exposure_rule
        else:
            class_exposure_rule = getattr(
                self.__class__, 'exposure_rule', None
            )
            self.exposure_rule = class_exposure_rule \
                if isinstance(class_exposure_rule, ExposureRule) else None

        # context initialization
        self._context = None
        self._last_run = None
        self.stop_loss_rules_lookup = {}
        self.take_profit_rules_lookup = {}
        self.scaling_rules_lookup = {}
        self.position_sizes_lookup = {}
        self._parameters = {}

        # Scaling state: tracks cooldown and scale-out count per symbol.
        # Persists across run_strategy() calls in event-based backtests.
        self._cooldown_remaining = {}   # {symbol: bars remaining}
        self._scale_out_counts = {}     # {symbol: number of scale-outs}
        # CooldownRule support — bar index is incremented every
        # ``run_strategy`` call so the tracker can compare events across
        # bars even when the engine doesn't expose a global bar counter.
        self._cooldown_tracker = CooldownTracker()
        self._cooldown_bar_index = 0
        # Tracks the most recent ``created_at`` for which the
        # CooldownTracker has been updated with system-emitted exits
        # (TP / SL fills from the TradeOrderEvaluator). The
        # RecordCooldownPhase advances this watermark every tick so
        # exits trip cooldowns just like signal-driven sells.
        self._last_system_exit_scan_at = None

    def set_parameters(self, params: dict) -> None:
        """
        Store strategy parameters for saving alongside backtest results.
        Only JSON-serializable values (str, int, float, bool, None, list,
        dict) are kept; non-serializable values are silently dropped.

        Side effect: if the strategy was constructed without an
        explicit ``algorithm_id`` (i.e. ``self.algorithm_id is None``)
        the id is auto-derived here from the canonical parameter set
        via :func:`generate_algorithm_id`. This guarantees that any
        downstream caller hashing ``Backtest.parameters`` reproduces the
        same id — which is what notebook 04 (out-of-sample) relies on
        when re-instantiating the in-sample winners. Pass an explicit
        ``algorithm_id`` to opt out.

        Args:
            params (dict): A dictionary of parameter names to values.
        """
        _JSON_TYPES = (str, int, float, bool, type(None))

        def _is_serializable(v):
            if isinstance(v, _JSON_TYPES):
                return True
            if isinstance(v, (list, tuple)):
                return all(_is_serializable(x) for x in v)
            if isinstance(v, dict):
                return all(
                    isinstance(k, str) and _is_serializable(val)
                    for k, val in v.items()
                )
            return False

        self._parameters = {
            k: v for k, v in params.items() if _is_serializable(v)
        }

        # Auto-derive algorithm_id from the canonical parameter set so
        # the id is reproducible from ``Backtest.parameters`` alone.
        # Only fires when no explicit id was supplied to ``__init__``.
        if getattr(self, "algorithm_id", None) is None and self._parameters:
            from investing_algorithm_framework.domain import (
                generate_algorithm_id,
            )
            self.algorithm_id = generate_algorithm_id(
                params=self._parameters
            )

    def get_parameters(self) -> dict:
        """
        Return the stored strategy parameters.

        Returns:
            dict: The strategy parameters dictionary.
        """
        return dict(self._parameters)

    def generate_signals(
        self, context: Context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        """
        Emit :class:`Signal` instances describing what the strategy
        wants to do on this bar.

        This is the **only** signal-producing method on
        :class:`TradingStrategy`. Each
        ``Signal`` carries a :class:`SignalSide`, an optional
        :pyattr:`Signal.strength` (used for top-N ranking when
        capital binds), and an optional ``source`` /
        ``metadata`` payload that flows through to the order.

        The method is expected to return an *iterable* — yielding
        signals lazily is recommended for cross-sectional strategies
        with hundreds of symbols. Return value is materialized once
        per call by :class:`CollectSignalsPhase`.

        Example (boolean Series, single symbol)::

            from investing_algorithm_framework import (
                Signal, SignalSide, signals_from_column,
            )

            def generate_signals(self, context, data):
                btc = data["BTC/EUR_1h"]
                yield from signals_from_column(
                    btc, "buy_signal",
                    side=SignalSide.OPEN_LONG, symbol="BTC",
                )
                yield from signals_from_column(
                    btc, "sell_signal",
                    side=SignalSide.CLOSE_LONG, symbol="BTC",
                )

        Example (cross-sectional panel)::

            from investing_algorithm_framework import signals_from_panel

            def generate_signals(self, context, data):
                panel = data["sp500_daily"]
                yield from signals_from_panel(
                    panel, "rank_top_decile",
                    side=SignalSide.OPEN_LONG,
                    strength_column="zscore",
                )

        Args:
            context (Context): The strategy context. Provides access
                to portfolio, positions, trades, and order helpers.
            data (Dict[str, Any]): Market data keyed by data-source
                identifier. Pipelines (when configured) have already
                materialized their factor columns into the relevant
                frames.

        Yields:
            Signal: Zero or more signals.

        Notes:
            The default implementation yields nothing. This is the
            correct behaviour for strategies that drive trading
            through other mechanisms (overriding :py:meth:`run_strategy`,
            using ``@app.strategy`` decorators with ``apply_strategy``,
            or test fixtures that exercise scheduling alone). Override
            to emit signals from indicator columns; the helpers in
            :mod:`investing_algorithm_framework.domain.models.signal_helpers`
            (``signals_from_column``, ``signals_from_panel``) are the
            canonical bridge from a pandas/polars frame.
        """
        return iter(())

    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
        """
        Emit :class:`SignalSeries` for the *vector* backtest engine.

        This is the batched, whole-window counterpart to
        :py:meth:`generate_signals`. Where ``generate_signals`` is
        called once per bar by the event-driven loop,
        ``generate_signal_series`` is called *once* by
        :class:`VectorBacktestService` with the full backtest window
        materialised. Each yielded :class:`SignalSeries` carries a
        boolean pandas/polars Series of bar-indexed flags for a
        single ``(symbol, side)`` pair; the vector engine walks the
        master timeline and fires the corresponding side wherever the
        series is truthy.

        Implementing this method is **only required if the strategy
        will be run through the vector backtest engine**. Live
        trading, paper trading, and event-driven backtests all use
        :py:meth:`generate_signals` exclusively and will never call
        this method. Strategies that never see the vector engine can
        leave the default ``NotImplementedError`` in place.

        Example (single-symbol, pandas)::

            from investing_algorithm_framework import (
                SignalSide, signal_series_from_column,
            )

            def generate_signal_series(self, data):
                df = data["BTC/EUR_1d"]
                df["entry"] = df["ema_fast"] > df["ema_slow"]
                df["exit"]  = df["ema_fast"] < df["ema_slow"]
                yield signal_series_from_column(
                    df, "entry",
                    side=SignalSide.OPEN_LONG, symbol="BTC",
                    source="ema_cross",
                )
                yield signal_series_from_column(
                    df, "exit",
                    side=SignalSide.CLOSE_LONG, symbol="BTC",
                    source="ema_cross",
                )

        Args:
            data (Dict[str, Any]): Market data keyed by data-source
                identifier. Unlike the event-driven case, every
                frame carries the full backtest window (with any
                configured warm-up) so that vectorised indicators
                can be computed in a single pass.

        Yields:
            SignalSeries: Zero or more series, one per
            ``(symbol, side)`` pair the strategy wants to express.

        Notes:
            The default implementation yields nothing. Vector-mode
            strategies must override; :func:`VectorBacktestService`
            verifies that the method has been overridden before
            running and raises a clear ``OperationalException`` if
            not.
        """
        return iter(())

    def run_strategy(self, context: Context, data: Dict[str, Any]):
        """
        Run one tick of the strategy by walking the configured
        :pyattr:`phases` in order.

        The body is intentionally tiny: ``run_strategy`` constructs a
        :class:`PhaseState`, hands it to each phase in turn, and
        returns. All trading behaviour lives in the phases — see
        :class:`CollectSignalsPhase`, :class:`ResolveConflictsPhase`,
        :class:`SizePositionsPhase`, :class:`ApplyRiskBudgetPhase`,
        :class:`EmitOrdersPhase`, :class:`AttachRiskRulesPhase`,
        :class:`RecordCooldownPhase`.

        Strategies that want to customise behaviour should:

        * Override :py:meth:`generate_signals` to emit different
          :class:`Signal`\\ s (the most common case).
        * Override :pyattr:`conflict_policy` to change how same-symbol
          signal clashes are resolved (default: RAISE).
        * Override :pyattr:`executor` to swap order routing (default:
          :class:`LimitOrderExecutor`; ship a
          :class:`MarketOrderExecutor` for market orders).
        * Override :pyattr:`phases` to add / remove / reorder phases.

        Args:
            context (Context): The strategy context.
            data (Dict[str, Any]): The market data keyed by data-source
                identifier.

        Returns:
            None
        """
        self.context = context
        self._pending_score_cards = []
        state = PhaseState(
            strategy=self,
            context=context,
            data=data,
            current_datetime=context.config[INDEX_DATETIME],
        )
        for phase in self.phases:
            phase.run(state)
        # Capture traces and raw signals so users (and RunReport) can
        # introspect a tick post-mortem, including signals that never
        # turned into an order.
        self.traces = state.traces
        self.last_signals = list(state.raw_signals)
        self.last_score_cards = list(self._pending_score_cards)

    def record_score_card(
        self, score_card: ScoreCard, symbol: str = None
    ) -> None:
        """Record a :class:`ScoreCard` for this tick, independent of
        whether :py:meth:`generate_signals` yields a ``Signal``.

        Use this to explain a *non-decision* — e.g. "RSI is neutral,
        no crossover" — so ``RunReport`` shows why nothing happened,
        not just why something did. A score card attached to an
        actual ``Signal`` (via :py:meth:`Signal.with_score_card`)
        does not need this; call it only for symbols/ticks that
        produced no signal.

        Args:
            score_card (ScoreCard): The explanation to record.
            symbol (str, optional): The symbol this explains, if any.

        Returns:
            None
        """
        self._pending_score_cards.append({
            "symbol": symbol,
            "score_card": score_card.to_dict(),
        })

    def apply_strategy(self, context, data):
        if self.decorated:
            self.decorated(context=context, data=data)
        else:
            raise NotImplementedError("Apply strategy is not implemented")

    @property
    def strategy_profile(self):
        return StrategyProfile(
            strategy_id=self.strategy_id,
            schedule=self.schedule,
            scheduled_functions=list(self.scheduled_functions),
            data_sources=self.data_sources
        )

    def get_take_profit_rule(
        self, symbol: str, side: str = None
    ) -> Union[TakeProfitRule, None]:
        """
        Get the take profit definition for a given symbol.

        Args:
            symbol (str): The symbol of the asset.

        Returns:
            Union[TakeProfitRule, None]: The take profit rule if found,
              None otherwise.
        """

        if self.take_profits is None or len(self.take_profits) == 0:
            return None

        if self.take_profit_rules_lookup == {}:
            for tp in self.take_profits:
                self.take_profit_rules_lookup[(tp.symbol, tp.side)] = tp

        return self.take_profit_rules_lookup.get(
            (symbol, side),
            self.take_profit_rules_lookup.get((symbol, None)),
        )

    def get_stop_loss_rule(
        self, symbol: str, side: str = None
    ) -> Union[StopLossRule, None]:
        """
        Get the stop loss definition for a given symbol.

        Args:
            symbol (str): The symbol of the asset.

        Returns:
            Union[StopLossRule, None]: The stop loss rule if found,
              None otherwise.
        """

        if self.stop_losses is None or len(self.stop_losses) == 0:
            return None

        if self.stop_loss_rules_lookup == {}:
            for sl in self.stop_losses:
                self.stop_loss_rules_lookup[(sl.symbol, sl.side)] = sl

        return self.stop_loss_rules_lookup.get(
            (symbol, side),
            self.stop_loss_rules_lookup.get((symbol, None)),
        )

    def get_position_size(self, symbol: str) -> Union[PositionSize, None]:
        """
        Get the position size definition for a given symbol.

        A symbol-specific ``PositionSize`` always takes precedence; a
        ``PositionSize(symbol=None, ...)`` entry (if any) is used as
        the default for any symbol without one of its own.

        Args:
            symbol (str): The symbol of the asset.

        Returns:
            Union[PositionSize, None]: The position size if found,
              None otherwise.
        """

        if self.position_sizes is not None and len(self.position_sizes) == 0:
            raise OperationalException(
                f"No position size defined for symbol "
                f"{symbol} in strategy "
                f"{self.strategy_id}"
            )

        if self.position_sizes_lookup == {}:
            for ps in self.position_sizes:
                self.position_sizes_lookup[ps.symbol] = ps

        position_size = self.position_sizes_lookup.get(
            symbol, self.position_sizes_lookup.get(None)
        )

        if position_size is None:
            raise OperationalException(
                f"No position size defined for symbol "
                f"{symbol} in strategy "
                f"{self.strategy_id}"
            )

        return position_size

    def get_scaling_rule(self, symbol: str) -> Union[ScalingRule, None]:
        """
        Get the scaling rule for a given symbol.

        A symbol-specific ``ScalingRule`` always takes precedence; a
        ``ScalingRule(symbol=None, ...)`` entry (if any) is used as
        the default for any symbol without one of its own.

        Args:
            symbol (str): The symbol of the asset.

        Returns:
            Union[ScalingRule, None]: The scaling rule if found,
              None otherwise.
        """

        if self.scaling_rules is None or len(self.scaling_rules) == 0:
            return None

        if self.scaling_rules_lookup == {}:
            for sr in self.scaling_rules:
                self.scaling_rules_lookup[sr.symbol] = sr

        return self.scaling_rules_lookup.get(
            symbol, self.scaling_rules_lookup.get(None)
        )

    def generate_recorded_values(
        self, data: Dict[str, Any]
    ) -> Union[Dict[str, pd.Series], None]:
        """
        Optional method to generate recorded values for vectorized
        backtesting. Override this to record arbitrary indicators,
        metrics, or variables as time series during a vectorized
        backtest.

        Each key in the returned dict becomes a recorded variable
        with the Series index as timestamps and the Series values
        as the recorded data.

        This is the vectorized equivalent of calling
        ``context.record()`` in event-driven backtests.

        Args:
            data (Dict[str, Any]): The market data for the strategy.

        Returns:
            Dict[str, Series] | None: A dictionary where keys are
                variable names and values are pandas Series with the
                recorded values. Return None to not record anything.
        """
        return None

    def on_trade_closed(self, context: Context, trade: Trade):
        pass

    def on_trade_updated(self, context: Context, trade: Trade):
        pass

    def on_trade_created(self, context: Context, trade: Trade):
        pass

    def on_trade_opened(self, context: Context, trade: Trade):
        pass

    def on_trade_stop_loss_triggered(self, context: Context, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_triggered(
        self, context: Context, trade: Trade
    ):
        pass

    def on_trade_take_profit_triggered(
        self, context: Context, trade: Trade
    ):
        pass

    def on_trade_stop_loss_updated(self, context: Context, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_updated(
        self, context: Context, trade: Trade
    ):
        pass

    def on_trade_take_profit_updated(self, context: Context, trade: Trade):
        pass

    def on_trade_stop_loss_created(self, context: Context, trade: Trade):
        pass

    def on_trade_trailing_stop_loss_created(
        self, context: Context, trade: Trade
    ):
        pass

    def on_trade_take_profit_created(self, context: Context, trade: Trade):
        pass

    @property
    def strategy_identifier(self):

        if self.strategy_id is not None:
            return self.strategy_id

        return getattr(self, "worker_id", None) or self.__class__.__name__

    def has_open_orders(
        self, target_symbol=None, identifier=None, market=None
    ) -> bool:
        """
        Check if there are open orders for a given symbol

        Args:
            target_symbol (str): The symbol of the asset e.g BTC if the
              asset is BTC/USDT
            identifier (str): The identifier of the portfolio
            market (str): The market of the asset

        Returns:
            bool: True if there are open orders, False otherwise
        """
        return self.context.has_open_orders(
            target_symbol=target_symbol, identifier=identifier, market=market
        )

    def create_limit_order(
        self,
        target_symbol,
        price,
        order_side,
        amount=None,
        amount_trading_symbol=None,
        percentage=None,
        percentage_of_portfolio=None,
        percentage_of_position=None,
        precision=None,
        market=None,
        execute=True,
        validate=True,
        sync=True,
        metadata=None,
        validate_symbol=False
    ) -> Order:
        """
        Function to create a limit order. This function will create
        a limit order and execute it if the execute parameter is set to True.
        If the validate parameter is set to True, the order will be validated

        Args:
            target_symbol: The symbol of the asset to trade
            price: The price of the asset
            order_side: The side of the order
            amount (optional): The amount of the asset to trade
            amount_trading_symbol (optional): The amount of the trading
              symbol to trade
            percentage (optional): The percentage of the portfolio to
                allocate to the order
            percentage_of_portfolio (optional): The percentage of
              the portfolio to allocate to the order
            percentage_of_position (optional): The percentage of
              the position to allocate to the order.
              (Only supported for SELL orders)
            precision (optional): The precision of the amount
            market (optional): The market to trade the asset
            execute (optional): Default True. If set to True, the order
              will be executed
            validate (optional): Default True. If set to True, the order
              will be validated
            sync (optional): Default True. If set to True, the created
              order will be synced with the portfolio of the context

        Returns:
            Order: Instance of the order created
        """
        return self.context.create_limit_order(
            target_symbol=target_symbol,
            price=price,
            order_side=order_side,
            amount=amount,
            amount_trading_symbol=amount_trading_symbol,
            percentage=percentage,
            percentage_of_portfolio=percentage_of_portfolio,
            percentage_of_position=percentage_of_position,
            precision=precision,
            market=market,
            execute=execute,
            validate=validate,
            sync=sync,
            metadata=metadata,
            validate_symbol=validate_symbol
        )

    def create_market_order(
        self,
        target_symbol,
        order_side,
        amount=None,
        amount_trading_symbol=None,
        percentage=None,
        percentage_of_portfolio=None,
        percentage_of_position=None,
        precision=None,
        market=None,
        execute=True,
        validate=True,
        sync=True,
        metadata=None
    ) -> Order:
        """
        Function to create a market order. Market orders execute at
        the best available price. In backtesting, this means the
        open price of the next candle (+ slippage).

        Args:
            target_symbol: The symbol of the asset to trade
            order_side: The side of the order (BUY or SELL)
            amount (optional): The amount of the asset to trade
            amount_trading_symbol (optional): The amount of the trading
              symbol to trade
            percentage (optional): The percentage of the portfolio to
                allocate to the order
            percentage_of_portfolio (optional): The percentage of
              the portfolio to allocate to the order
            percentage_of_position (optional): The percentage of
              the position to allocate to the order.
              (Only supported for SELL orders)
            precision (optional): The precision of the amount
            market (optional): The market to trade the asset
            execute (optional): Default True. If set to True, the order
              will be executed
            validate (optional): Default True. If set to True, the order
              will be validated
            sync (optional): Default True. If set to True, the created
              order will be synced with the portfolio of the context
            metadata (optional): Additional metadata for the order

        Returns:
            Order: Instance of the order created
        """
        return self.context.create_market_order(
            target_symbol=target_symbol,
            order_side=order_side,
            amount=amount,
            amount_trading_symbol=amount_trading_symbol,
            percentage=percentage,
            percentage_of_portfolio=percentage_of_portfolio,
            percentage_of_position=percentage_of_position,
            precision=precision,
            market=market,
            execute=execute,
            validate=validate,
            sync=sync,
            metadata=metadata
        )

    def create_short_order(
        self,
        target_symbol,
        price,
        amount=None,
        percentage_of_portfolio=None,
        order_type=None,
        market=None,
        execute=False,
        validate=True,
        sync=False,
        metadata=None,
    ) -> Order:
        """
        Thin wrapper around :py:meth:`Context.create_short_order`.

        ``execute``/``sync`` default to ``False`` because short orders
        are not yet wired into the live/event-driven sync path — the
        order is validated and persisted only. Vector backtests route
        shorts independently via :py:meth:`generate_signal_series` with
        :pyattr:`SignalSide.OPEN_SHORT`.
        """
        from investing_algorithm_framework.domain import OrderType
        kwargs = {
            "target_symbol": target_symbol,
            "price": price,
            "amount": amount,
            "percentage_of_portfolio": percentage_of_portfolio,
            "market": market,
            "execute": execute,
            "validate": validate,
            "sync": sync,
            "metadata": metadata,
        }
        if order_type is not None:
            kwargs["order_type"] = order_type
        else:
            kwargs["order_type"] = OrderType.LIMIT
        return self.context.create_short_order(**kwargs)

    def create_cover_order(
        self,
        target_symbol,
        price,
        amount=None,
        percentage_of_position=None,
        order_type=None,
        market=None,
        execute=False,
        validate=True,
        sync=False,
        metadata=None,
    ) -> Order:
        """
        Thin wrapper around :py:meth:`Context.create_cover_order`.

        See :py:meth:`create_short_order` for the execute/sync caveat.
        """
        from investing_algorithm_framework.domain import OrderType
        kwargs = {
            "target_symbol": target_symbol,
            "price": price,
            "amount": amount,
            "percentage_of_position": percentage_of_position,
            "market": market,
            "execute": execute,
            "validate": validate,
            "sync": sync,
            "metadata": metadata,
        }
        if order_type is not None:
            kwargs["order_type"] = order_type
        else:
            kwargs["order_type"] = OrderType.LIMIT
        return self.context.create_cover_order(**kwargs)

    def close_position(
        self, symbol, market=None, identifier=None, precision=None
    ) -> Order:
        """
        Function to close a position. This function will close a position
        by creating a market order to sell the position. If the precision
        parameter is specified, the amount of the order will be rounded
        down to the specified precision.

        Args:
            symbol: The symbol of the asset
            market: The market of the asset
            identifier: The identifier of the portfolio
            precision: The precision of the amount

        Returns:
            None
        """
        return self.context.close_position(
            symbol=symbol,
            market=market,
            identifier=identifier,
            precision=precision
        )

    def get_positions(
        self,
        market=None,
        identifier=None,
        amount_gt=None,
        amount_gte=None,
        amount_lt=None,
        amount_lte=None
    ) -> List[Position]:
        """
        Function to get all positions. This function will return all
        positions that match the specified query parameters. If the
        market parameter is specified, the positions of the specified
        market will be returned. If the identifier parameter is
        specified, the positions of the specified portfolio will be
        returned. If the amount_gt parameter is specified, the positions
        with an amount greater than the specified amount will be returned.
        If the amount_gte parameter is specified, the positions with an
        amount greater than or equal to the specified amount will be
        returned. If the amount_lt parameter is specified, the positions
        with an amount less than the specified amount will be returned.
        If the amount_lte parameter is specified, the positions with an
        amount less than or equal to the specified amount will be returned.

        Args:
            market: The market of the portfolio where the positions are
            identifier: The identifier of the portfolio
            amount_gt: The amount of the asset must be greater than this
            amount_gte: The amount of the asset must be greater than or
                equal to this
            amount_lt: The amount of the asset must be less than this
            amount_lte: The amount of the asset must be less than or equal
                to this

        Returns:
            List[Position]: A list of positions that match the query parameters
        """
        return self.context.get_positions(
            market=market,
            identifier=identifier,
            amount_gt=amount_gt,
            amount_gte=amount_gte,
            amount_lt=amount_lt,
            amount_lte=amount_lte
        )

    def get_trades(self, market=None) -> List[Trade]:
        """
        Function to get all trades. This function will return all trades
        that match the specified query parameters. If the market parameter
        is specified, the trades with the specified market will be returned.

        Args:
            market: The market of the asset

        Returns:
            List[Trade]: A list of trades that match the query parameters
        """
        return self.context.get_trades(market)

    def get_closed_trades(self) -> List[Trade]:
        """
        Function to get all closed trades. This function will return all
        closed trades of the context.

        Returns:
            List[Trade]: A list of closed trades
        """
        return self.context.get_closed_trades()

    def get_open_trades(self, target_symbol=None, market=None) -> List[Trade]:
        """
        Function to get all open trades. This function will return all
        open trades that match the specified query parameters. If the
        target_symbol parameter is specified, the open trades with the
        specified target symbol will be returned. If the market parameter
        is specified, the open trades with the specified market will be
        returned.

        Args:
            target_symbol: The symbol of the asset
            market: The market of the asset

        Returns:
            List[Trade]: A list of open trades that match the query parameters
        """
        return self.context.get_open_trades(target_symbol, market)

    def close_trade(self, trade, market=None, precision=None) -> None:
        """
        Function to close a trade. This function will close a trade by
        creating a market order to sell the position. If the precision
        parameter is specified, the amount of the order will be rounded
        down to the specified precision.

        Args:
            trade: Trade - The trade to close
            market: str - The market of the trade
            precision: float - The precision of the amount

        Returns:
            None
        """
        self.context.close_trade(
            trade=trade, market=market, precision=precision
        )

    def get_number_of_positions(self):
        """
        Returns the number of positions that have a positive amount.

        Returns:
            int: The number of positions
        """
        return self.context.get_number_of_positions()

    def get_position(
        self, symbol, market=None, identifier=None
    ) -> Position:
        """
        Function to get a position. This function will return the
        position that matches the specified query parameters. If the
        market parameter is specified, the position of the specified
        market will be returned. If the identifier parameter is
        specified, the position of the specified portfolio will be
        returned.

        Args:
            symbol: The symbol of the asset that represents the position
            market: The market of the portfolio where the position is located
            identifier: The identifier of the portfolio

        Returns:
            Position: The position that matches the query parameters
        """
        return self.context.get_position(
            symbol=symbol,
            market=market,
            identifier=identifier
        )

    def has_position(
        self,
        symbol,
        market=None,
        identifier=None,
        amount_gt=0,
        amount_gte=None,
        amount_lt=None,
        amount_lte=None
    ):
        """
        Function to check if a position exists. This function will return
        True if a position exists, False otherwise. This function will check
        if the amount > 0 condition by default.

        Args:
            param symbol: The symbol of the asset
            param market: The market of the asset
            param identifier: The identifier of the portfolio
            param amount_gt: The amount of the asset must be greater than this
            param amount_gte: The amount of the asset must be greater than
            or equal to this
            param amount_lt: The amount of the asset must be less than this
            param amount_lte: The amount of the asset must be less than
            or equal to this

        Returns:
            Boolean: True if a position exists, False otherwise
        """
        return self.context.has_position(
            symbol=symbol,
            market=market,
            identifier=identifier,
            amount_gt=amount_gt,
            amount_gte=amount_gte,
            amount_lt=amount_lt,
            amount_lte=amount_lte
        )

    def has_balance(self, symbol, amount, market=None):
        """
        Function to check if the portfolio has enough balance to
        create an order. This function will return True if the
        portfolio has enough balance to create an order, False
        otherwise.

        Args:
            symbol: The symbol of the asset
            amount: The amount of the asset
            market: The market of the asset

        Returns:
            Boolean: True if the portfolio has enough balance
        """
        return self.context.has_balance(symbol, amount, market)

    def last_run(self) -> datetime:
        """
        Function to get the last run of the strategy

        Returns:
            DateTime: The last run of the strategy
        """
        return self.context.last_run()

    def get_data_sources(self):
        """
        Function to get the data sources of the strategy

        Returns:
            List[DataSource]: The data sources of the strategy
        """
        return self.data_sources

    def __repr__(self):
        return f"<TradingStrategy(strategy_id={self.strategy_id})>"
