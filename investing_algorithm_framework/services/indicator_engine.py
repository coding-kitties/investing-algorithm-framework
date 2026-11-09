"""Causal native candle computations shared by event and prepared evaluation."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from datetime import datetime

import numpy as np
import pandas as pd
import polars as pl

from investing_algorithm_framework.domain.indicators import (
    ConfluenceScoreConfig, IndicatorConfig, IndicatorEvaluation,
)
from investing_algorithm_framework.domain.models.confluence import EvaluationContext
from investing_algorithm_framework.domain.models.data.data_source import DataSource
from investing_algorithm_framework.domain.models.data.data_type import DataType
from investing_algorithm_framework.domain.models.time_frame import TimeFrame
from investing_algorithm_framework.domain import (
    DecisionTrace, DecisionTraceEntry, SignalSide,
)
from investing_algorithm_framework.domain.models.confluence import (
    AllOf, AnyOf, AtLeast, ConditionExpression, ConfluenceResult, GroupEvaluation,
    Not, RuleEvaluation, ScoreType,
)
from investing_algorithm_framework.domain.models.confluence_score import (
    ConfluenceScoreCard, Rule, Threshold,
)
from .confluence_reporting import confluence_report_details, skipped_confluence_trace


_COMPARISON_LABELS = {
    "le": "<=", "lt": "<", "ge": ">=", "gt": ">", "eq": "==", "ne": "!=",
}


def _at_least_state(states, minimum):
    """Unknown inputs cannot establish either a match or its negation."""
    matched = sum(state is True for state in states)
    if matched >= minimum:
        return True
    if matched + sum(state is None for state in states) < minimum:
        return False
    return None


def _qualification_state(card, matches, readiness):
    scores, _ = card.score_rules(matches)

    def threshold_state(group, threshold):
        if not all(
            readiness[name] for name, rule in card.rules.items()
            if group in rule.group_weights
        ):
            return None
        return scores[group] >= threshold

    def expression_state(expression):
        if isinstance(expression, Rule):
            return matches[expression.name] if readiness[expression.name] else None
        if isinstance(expression, Threshold):
            return threshold_state(expression.group, expression.value)
        if isinstance(expression, ConditionExpression):
            predicate = expression.condition
            names = [predicate.indicator]
            if predicate.reference is not None:
                names.append(predicate.reference)
            if not all(readiness[name] for name in names):
                return None
            return bool(expression.evaluate(EvaluationContext(matches)))
        if isinstance(expression, Not):
            state = expression_state(expression.expression)
            return None if state is None else not state
        if isinstance(expression, (AllOf, AnyOf, AtLeast)):
            minimum = (
                len(expression.expressions) if isinstance(expression, AllOf)
                else expression.minimum if isinstance(expression, AtLeast) else 1
            )
            return _at_least_state(
                [expression_state(child) for child in expression.expressions],
                minimum,
            )
        raise TypeError(
            f"Qualification readiness does not support {type(expression).__name__}"
        )

    normal = bool(card.group_thresholds) and _at_least_state([
        threshold_state(group, threshold)
        for group, threshold in card.group_thresholds.items()
    ], len(card.group_thresholds))
    override = (
        expression_state(card.override_triggers)
        if card.override_triggers is not None else False
    )
    requirements = [expression_state(gate.expression) for gate in card.requirements]
    no_veto = []
    for gate in card.vetoes:
        state = expression_state(gate.expression)
        no_veto.append(None if state is None else not state)
    states = [*requirements, *no_veto, _at_least_state([normal, override], 1)]
    return _at_least_state(states, len(states))


def confluence_decision_trace(name, card, payload, values):
    snapshot = {
        f"{indicator}.{column}": value if np.isfinite(value) else None
        for indicator, outputs in values.items()
        for column, value in outputs.items()
    }
    if payload.get("evaluation_status") == "skipped":
        return skipped_confluence_trace(
            name, card.side, payload["signal_reason"], snapshot,
        )
    result = ConfluenceResult(
        card_name=name, primary_triggered=payload["primary_triggered"],
        requirements_passed=payload["requirements_passed"],
        veto_triggered=payload["veto_triggered"], score=payload["score"],
        minimum_score=payload["minimum_score"],
        qualified=payload["ready"] and payload["qualified"],
        groups=tuple(GroupEvaluation(**group) for group in payload["groups"]),
        evaluations=tuple(
            RuleEvaluation(**{
                **evaluation,
                "score_type": ScoreType(evaluation["score_type"])
                if evaluation["score_type"] is not None else None,
            }) for evaluation in payload["evaluations"]
        ),
    )
    trace = DecisionTrace.from_confluence_result(
        result, indicator_snapshot=snapshot,
    )
    trace.entries.extend([
        DecisionTraceEntry("signal_side", card.side.value, group="decision"),
        DecisionTraceEntry("ready", payload["ready"], group="decision"),
    ])
    if "position_opened_at" in payload:
        trace.entries.append(DecisionTraceEntry(
            "position_opened_at", payload["position_opened_at"], group="decision",
        ))
    if "initial_delay" in payload:
        trace.entries.extend(
            DecisionTraceEntry(key, payload[key], group="decision")
            for key in (
                "raw_passed", "initial_delay", "initial_delay_mode",
                "delay_elapsed", "delay_pending",
            )
        )
    for rule_name, delay in payload.get("rule_delays", {}).items():
        trace.entries.extend(
            DecisionTraceEntry(f"{rule_name}.{key}", value, group="rules")
            for key, value in delay.items()
        )
    return trace


def _ema(values, period, *, wilder=False):
    """Reset on missing observations; Wilder seeds with an SMA, EMA with first."""
    result = np.full(len(values), np.nan)
    count, state, total = 0, np.nan, 0.0
    alpha = 1 / period if wilder else 2 / (period + 1)
    for i, value in enumerate(values):
        if not np.isfinite(value):
            count, state, total = 0, np.nan, 0.0
            continue
        count += 1
        if wilder and count <= period:
            total += value
            if count == period:
                state = total / period
        else:
            state = value if count == 1 else alpha * value + (1 - alpha) * state
        if count >= period:
            result[i] = state
    return pd.Series(result, index=values.index)


def _rsi(gains, losses):
    total = gains + losses
    # No price movement has neutral RSI; no losses but gains has RSI 100.
    return (100 * gains / total).where(total != 0, 50.0)


def _copy_card_payload(payload):
    """Detach the fixed scalar/dictionary/list shape produced by _score_card."""
    return {
        **payload,
        "groups": [dict(group) for group in payload["groups"]],
        "evaluations": [
            dict(evaluation) for evaluation in payload["evaluations"]
        ],
        "matches": dict(payload["matches"]),
        "lookback_ready": dict(payload["lookback_ready"]),
    }


def compute_indicator(frame, config):
    """Compute on native observed rows only; never resample/fill price data."""
    close, period = frame["Close"], config.period
    kind = config.indicator
    if kind == "ema":
        outputs = {"value": _ema(close, period)}
    elif kind == "z_score":
        rolling = close.rolling(period)
        outputs = {"value": (close - rolling.mean()) / rolling.std(ddof=0)}
    elif kind in ("rsi", "wilders_rsi"):
        delta = close.diff()
        gains, losses = delta.clip(lower=0), -delta.clip(upper=0)
        if kind == "wilders_rsi":
            gains, losses = _ema(gains, period, wilder=True), _ema(losses, period, wilder=True)
        else:
            gains, losses = gains.rolling(period).mean(), losses.rolling(period).mean()
        outputs = {"value": _rsi(gains, losses)}
    elif kind == "macd":
        macd = _ema(close, config.short_period) - _ema(close, config.long_period)
        signal = _ema(macd, config.signal_period)
        outputs = {"macd": macd, "signal": signal, "histogram": macd - signal}
    else:
        high = frame["High"].rolling(period).max()
        low = frame["Low"].rolling(period).min()
        span = (high - low).replace(0, np.nan)
        raw = 100 * (close - low) / span
        if kind == "willr":
            outputs = {"value": -100 * (high - close) / span}
        else:
            k = raw.rolling(config.k_slowing).mean()
            outputs = {"k": k, "d": k.rolling(config.d_period).mean()}
    output = pd.DataFrame(outputs, index=frame.index) * config.scale
    return output.replace([np.inf, -np.inf], np.nan)


def _completion(index, timeframe):
    if timeframe == "1M":
        return pd.DatetimeIndex(
            [stamp + pd.DateOffset(months=1) for stamp in index], dtype=index.dtype,
        )
    if timeframe == "1Y":
        return pd.DatetimeIndex(
            [stamp + pd.DateOffset(years=1) for stamp in index], dtype=index.dtype,
        )
    minutes = TimeFrame.from_value(timeframe).amount_of_minutes
    return index + pd.Timedelta(minutes=minutes)


def _normalize(raw, source, *, preserve=False):
    if isinstance(raw, pl.DataFrame):
        raw = raw.to_pandas()
    if not isinstance(raw, pd.DataFrame):
        raise TypeError(f"Source {source} must be a pandas or polars DataFrame")
    frame = raw.copy(deep=True)
    if not isinstance(frame.index, pd.DatetimeIndex):
        columns = {str(column).lower(): column for column in frame.columns}
        timestamp = next((columns[key] for key in ("datetime", "timestamp", "date") if key in columns), None)
        if timestamp is None:
            if frame.empty:
                frame.index = pd.DatetimeIndex([], tz="UTC")
            else:
                raise ValueError(f"Source {source} requires datetime index/column")
        else:
            values = frame[timestamp] if preserve else frame.pop(timestamp)
            frame.index = pd.DatetimeIndex(pd.to_datetime(values, utc=True))
    if frame.index.tz is None:
        # Framework provider frames historically store naive UTC candles.
        frame.index = frame.index.tz_localize("UTC")
    else:
        frame.index = frame.index.tz_convert("UTC")
    frame.index = frame.index.astype("datetime64[ns, UTC]")
    if frame.index.hasnans or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError(f"Source {source} timestamps must be unique and increasing")
    if not preserve:
        frame.columns = [str(column).capitalize() for column in frame.columns]
    if frame.columns.has_duplicates:
        raise ValueError(f"Source {source} contains duplicate columns")
    return frame


class IndicatorEngine:
    """Run-local native indicator history, optionally precomputed in one pass."""

    def __init__(self, configs, cards, data_sources):
        if isinstance(configs, Mapping):
            for key, config in configs.items():
                if not isinstance(config, IndicatorConfig) or key != config.id:
                    raise ValueError("Config mapping keys must equal config.id")
            configs = configs.values()
        configs = list(configs)
        if not all(isinstance(config, IndicatorConfig) for config in configs):
            raise TypeError("configs must contain IndicatorConfig instances")
        self.configs = {config.id: config for config in configs}
        if len(self.configs) != len(configs):
            raise ValueError("Duplicate indicator id")
        sources = list(data_sources.values() if isinstance(data_sources, Mapping) else data_sources)
        if not all(isinstance(source, DataSource) for source in sources):
            raise TypeError("data_sources must contain DataSource instances")
        identifiers = [source.get_identifier() for source in sources]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate data source identifier")
        self.data_sources = dict(zip(identifiers, sources))
        if isinstance(cards, Mapping):
            self.cards = dict(cards)
        else:
            declarations = list(cards)
            if not all(isinstance(card, ConfluenceScoreConfig) for card in declarations):
                raise TypeError("cards must contain ConfluenceScoreConfig instances")
            if any(card.id is None for card in declarations):
                raise ValueError("Card list declarations require non-empty ids")
            self.cards = {card.id: card for card in declarations}
            if len(self.cards) != len(declarations):
                raise ValueError("Duplicate card id")
        if not all(isinstance(card, ConfluenceScoreConfig) for card in self.cards.values()):
            raise TypeError("cards must map names to ConfluenceScoreConfig")
        self.compiled_cards = {name: card.compile(name) for name, card in self.cards.items()}
        self.position_scoped_cards = frozenset(
            name for name, card in self.cards.items()
            if any(rule.lookback_scope == "position" for rule in card.rules.values())
        )
        self._sources, self._keys, self._computations = {}, {}, {}
        self.required_windows = {}
        for config in configs:
            source = self._resolve_source(config)
            identifier = source.get_identifier()
            self._sources[config.id] = identifier
            key = self._calculation_key(identifier, config)
            self._keys[config.id] = key
            self._computations.setdefault(key, config)
            self.required_windows[identifier] = max(
                self.required_windows.get(identifier, 0), config.required_window(),
            )
        for card in self.cards.values():
            for rule in card.rules.values():
                if rule.indicator_id not in self.configs:
                    raise ValueError(f"Unknown indicator: {rule.indicator_id}")
                config = self.configs[rule.indicator_id]
                outputs = config.outputs
                if rule.selected_output is None and (config.calculate is not None or len(outputs) > 1):
                    raise ValueError(f"{config.indicator or config.id} rules require an explicit output_column (explicit output)")
                if rule.selected_output is not None and rule.selected_output not in outputs:
                    raise ValueError(f"Unknown {config.indicator or config.id} output: {rule.selected_output}")
                source = self._sources[config.id]
                self.required_windows[source] = max(
                    self.required_windows[source],
                    config.required_window(rule.selected_output) + rule.lookback_period - 1,
                )
        for identifier, required in self.required_windows.items():
            warmup = self.data_sources[identifier].warmup_window
            if warmup is not None and warmup < required:
                raise ValueError(f"Source {identifier} warmup_window {warmup} is below required_window {required}")
        self._reset()

    @property
    def calculation_count(self):
        """Number of unique source/kind/parameter computations."""
        return len(self._computations)

    def get_confluence_score_cards(self, symbol: str) -> list[ConfluenceScoreCard]:
        """Create inspection snapshots without calculating or evaluating rules."""
        cards = []
        for name, config in self.cards.items():
            indicators, sources = {}, {}
            for rule in config.rules.values():
                identifier = self._sources[rule.indicator_id]
                source = self.data_sources[identifier]
                assert source.time_frame is not None
                indicators[rule.indicator_id] = replace(
                    self.configs[rule.indicator_id],
                    data_source=identifier, data_sources=None,
                    symbol=source.symbol, timeframe=source.time_frame.value,
                )
                sources[identifier] = source
            cards.append(replace(
                self.compiled_cards[name], symbol=symbol,
                configuration=deepcopy(config),
                indicator_configs=deepcopy(indicators),
                data_sources=deepcopy(sources),
            ))
        return cards

    def snapshot(self, evaluation: IndicatorEvaluation) -> list[dict]:
        """Flatten the evaluated outputs with their resolved target symbols."""
        records = []
        for name, outputs in evaluation.values.items():
            symbol = self.data_sources[self._sources[name]].symbol
            records.extend({
                "symbol": symbol.split("/")[0] if symbol is not None else None,
                "name": f"{name}.{column}",
                "value": value,
            } for column, value in outputs.items())
        return records

    def _resolve_source(self, config):
        identifier = config.data_source
        selected = config.source_identifiers
        if selected is not None:
            for name in selected:
                if name not in self.data_sources:
                    raise ValueError(f"Unknown data source: {name}")
        if isinstance(identifier, DataSource):
            identifier = identifier.get_identifier()
        elif isinstance(identifier, Mapping):
            if config.symbol is None:
                raise ValueError(f"Indicator {config.id} with a source mapping requires an explicit symbol")
            symbol = config.symbol.upper()
            identifier = identifier.get(symbol, identifier.get(symbol.split("/")[0]))
            if identifier is None:
                raise ValueError(f"Indicator {config.id} has no data source for {symbol}")
        candidates = [
            source for key, source in self.data_sources.items()
            if (identifier is None or identifier == key)
            and (selected is None or key in selected)
            and DataType.OHLCV.equals(source.data_type)
            and source.time_frame is not None
            and (config.timeframe is None or source.time_frame.value == config.timeframe)
            and (config.symbol is None or source.symbol == config.symbol.upper())
        ]
        if len(candidates) != 1:
            raise ValueError(f"Indicator {config.id} must resolve exactly one OHLCV source at {config.timeframe}")
        return candidates[0]

    @staticmethod
    def _calculation_key(source, config):
        if config.calculate is not None:
            # Arbitrary callables can carry state; even identical declarations
            # must not implicitly share a calculation.
            return (source, "callable", config.id)
        params = (
            (config.short_period, config.long_period, config.signal_period)
            if config.indicator == "macd" else
            (config.period, config.k_slowing, config.d_period)
            if config.indicator == "stochastic" else (config.period,)
        )
        return (source, config.indicator, config.timeframe, config.scale, *params)

    def _reset(self):
        self._history, self._outputs = {}, {}
        self._available, self._rule_outputs, self._card_outputs = {}, {}, {}
        self._initial_cards = {}
        self._prepared = False
        self._last_as_of = None
        self._backends = {}
        self._delay_states = {}
        self._rule_delay_states = {}
        self._vector_decisions = None

    def _frame(self, raw, identifier):
        configs = [config for config in self.configs.values() if self._sources[config.id] == identifier]
        if any(config.calculate is not None for config in configs):
            existing = self._history.get(identifier)
            if identifier not in self._backends or existing is None or existing.empty:
                self._backends[identifier] = raw.schema if isinstance(raw, pl.DataFrame) else None
            frame = _normalize(raw, identifier, preserve=True)
            builtins = [config for config in configs if config.calculate is None]
            required = {"Close"} if builtins else set()
            if any(config.indicator in ("willr", "stochastic") for config in builtins):
                required |= {"High", "Low"}
            missing = required - {str(column).capitalize() for column in frame.columns}
            if not frame.empty and missing:
                raise ValueError(f"Source {identifier} missing columns {sorted(missing)}")
            return frame
        frame = _normalize(raw, identifier)
        required = {"Close"}
        if any(config.indicator in ("willr", "stochastic") for config in configs):
            required |= {"High", "Low"}
        if not frame.empty and required - set(frame.columns):
            raise ValueError(f"Source {identifier} missing columns {sorted(required - set(frame.columns))}")
        frame = frame.reindex(columns=sorted(required)).astype(float)
        return frame.replace([np.inf, -np.inf], np.nan)

    def prepare(self, data):
        """Reset history; callable precomputation requires explicit opt-in."""
        self._reset()
        for identifier in self.required_windows:
            if identifier not in data:
                raise ValueError(f"Missing prepared source: {identifier}")
        self._history = {
            identifier: self._frame(data[identifier], identifier)
            for identifier in self.required_windows
        }
        self._recompute(set(self._history), preparing=True)
        self._prepare_cards()
        self._prepared = True
        return self

    def _compute(self, frame, config):
        if config.calculate is None:
            native = _normalize(frame, self._sources[config.id])
            required = ["Close"]
            if config.indicator in ("willr", "stochastic"):
                required += ["High", "Low"]
            native = native.reindex(columns=required)
            return compute_indicator(native.astype(float).replace([np.inf, -np.inf], np.nan), config)
        output = pd.DataFrame(np.nan, index=frame.index, columns=config.outputs)
        if len(frame) < config.minimum_history:
            return output
        identifier = self._sources[config.id]
        try:
            argument = frame.copy(deep=True)
            schema = self._backends.get(identifier)
            if schema is not None:
                argument = pl.from_pandas(argument.reset_index(drop=True)).cast(schema)
            result = config.calculate(argument, **deepcopy(dict(config.parameters)))
            if not isinstance(result, (pd.DataFrame, pl.DataFrame)):
                raise TypeError("calculate must return a pandas or polars DataFrame")
            if len(result) != len(frame):
                raise ValueError("Returned output length must match source history")
            result = _normalize(result, identifier, preserve=True)
            if not result.index.equals(frame.index):
                raise ValueError("Returned output timestamps/order must match source history")
            if set(config.outputs) - set(result.columns):
                raise ValueError(f"Returned output missing declared columns: {list(config.outputs)}")
            for column in config.outputs:
                if (not pd.api.types.is_numeric_dtype(result[column])
                        or pd.api.types.is_bool_dtype(result[column])
                        or pd.api.types.is_complex_dtype(result[column])):
                    raise TypeError(f"Returned output {column} must be numeric")
            output = result.loc[:, list(config.outputs)].astype(float)
            output.iloc[:config.minimum_history - 1] = np.nan
            return output.replace([np.inf, -np.inf], np.nan)
        except Exception as exc:
            raise ValueError(f"Indicator {config.id} source {identifier}: {exc}") from exc

    def _recompute(self, changed, *, preparing=False, as_of=None):
        recomputed = set()
        for key, config in self._computations.items():
            per_decision = config.calculate is not None and config.execution == "per_decision"
            if per_decision and preparing:
                continue
            if (per_decision and as_of is not None) or (not per_decision and key[0] in changed):
                frame = self._history.get(key[0], pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC")))
                timeframe = self.data_sources[key[0]].time_frame.value
                if per_decision:
                    frame = frame.loc[_completion(frame.index, timeframe) <= as_of]
                self._outputs[key] = self._compute(frame, config)
                self._available[key] = _completion(frame.index, timeframe)
                recomputed.add(key)
        for card_name, card in self.cards.items():
            for rule_name, rule in card.rules.items():
                config = self.configs[rule.indicator_id]
                key = self._keys[config.id]
                if key not in recomputed:
                    continue
                series = self._outputs[key][rule.selected_output or "value"]
                valid = np.isfinite(series)
                matched = rule.match(series) & valid
                rolled = matched.rolling(rule.lookback_period, min_periods=1).max().astype(bool)
                observations = {
                    "matched": rolled & valid,
                    "ready": valid,
                    "lookback_ready": valid.rolling(
                        rule.lookback_period, min_periods=rule.lookback_period,
                    ).sum().eq(rule.lookback_period),
                }
                if rule.lookback_scope == "position":
                    observations["last_match_at"] = pd.Series(
                        self._available[key], index=series.index,
                    ).where(matched).ffill()
                self._rule_outputs[card_name, rule_name] = pd.DataFrame(
                    observations, index=series.index,
                ).set_axis(self._available[key])

    def confluence_snapshot(self, evaluation):
        """Detach every evaluated card, including inactive scale-in stages."""
        symbols = {
            source.symbol.split("/")[0]
            for source in self.data_sources.values() if source.symbol
        }
        records = []
        for name, payload in evaluation.cards.items():
            record = (
                dict(payload) if payload.get("evaluation_status") == "skipped"
                else confluence_report_details(self.compiled_cards[name], payload)
            )
            for item in record.get("evaluations", []):
                rule = self.cards[name].rules.get(item["name"])
                if item["category"] != "score" or rule is None:
                    continue
                output = rule.selected_output or "value"
                value = evaluation.values[rule.indicator_id][output]
                item.update(
                    indicator_id=rule.indicator_id, output_column=output,
                    value=float(value) if np.isfinite(value) else None,
                    comparison=rule.comparison, threshold=rule.threshold,
                    lower_bound=rule.lower_bound, upper_bound=rule.upper_bound,
                    lookback_period=rule.lookback_period,
                    lookback_scope=rule.lookback_scope,
                    time_frame=self.data_sources[
                        self._sources[rule.indicator_id]
                    ].time_frame.value,
                    condition=(
                        f"{rule.indicator_id}.{output} "
                        f"needs {_COMPARISON_LABELS[rule.comparison]} "
                        f"{rule.threshold:g}; "
                        + (
                            f">= {rule.lower_bound:g}; "
                            if rule.lower_bound is not None else ""
                        )
                        + (
                            f"<= {rule.upper_bound:g}; "
                            if rule.upper_bound is not None else ""
                        )
                        + f"lookback {rule.lookback_period} completed bars"
                        + (
                            f" after position entry {payload['position_opened_at']}"
                            if rule.lookback_scope == "position" else ""
                        )
                    ),
                )
                if item["name"] in payload.get("rule_delays", {}):
                    item.update(payload["rule_delays"][item["name"]])
                if rule.lookback_scope == "position":
                    item["position_opened_at"] = payload["position_opened_at"]
            if "position_opened_at" in payload:
                record["position_opened_at"] = payload["position_opened_at"]
            records.append({
                **record,
                "card_id": name,
                "side": self.cards[name].side.value,
                "scale_in_stage": self.cards[name].scale_in_stage,
                "symbol": next(iter(symbols)) if len(symbols) == 1 else None,
                "decision_trace": confluence_decision_trace(
                    name, self.cards[name], payload, evaluation.values,
                ).to_dict(),
            })
        return records

    def _score_card(self, name, matches, readiness, full_readiness):
        card = self.compiled_cards[name]
        result = card.evaluate(EvaluationContext(matches))
        ready = (
            all(readiness.values())
            if self.cards[name].readiness_policy == "all_rules"
            else _qualification_state(card, matches, readiness) is not None
        )
        payload = result.to_dict()
        payload.update(
            passed=bool(result.qualified), matches=matches,
            ready=ready, lookback_ready=full_readiness,
        )
        return payload

    @staticmethod
    def _delay_result(key, as_of, triggered, delay, mode, anchor, states):
        previous = states.get(key)
        if previous is not None and previous["anchor"] != anchor:
            previous = None
        if previous is not None:
            if as_of < previous["time"]:
                raise ValueError(
                    "Delayed card evaluation cannot rewind; "
                    "prepare a fresh run"
                )
            if as_of == previous["time"]:
                return dict(previous["result"])
        elapsed = None if previous is None else previous["elapsed"]
        if elapsed is None:
            elapsed = 0 if triggered else None
        elif mode == "continuous" and not triggered:
            elapsed = None
        else:
            elapsed = min(elapsed + 1, delay)
            if elapsed == delay and not triggered:
                elapsed = None
        passed = triggered and elapsed == delay
        result = {
            "passed": passed,
            "initial_delay": delay,
            "initial_delay_mode": mode,
            "delay_elapsed": elapsed,
            "delay_pending": (
                elapsed is not None and elapsed < delay
            ),
        }
        states[key] = {
            "time": as_of, "anchor": anchor, "elapsed": elapsed, "result": result,
        }
        return dict(result)

    def _apply_delay(
        self, name, as_of, payload, *, position_opened_at=None, states=None,
    ):
        card = self.cards[name]
        if not card.initial_delay:
            return payload
        states = self._delay_states if states is None else states
        result = self._delay_result(
            name, as_of, bool(payload["ready"] and payload["passed"]),
            card.initial_delay, card.initial_delay_mode, position_opened_at, states,
        )
        payload.update(
            result, raw_passed=bool(payload["passed"]), qualified=result["passed"],
        )
        return payload

    def _delayed_payload(
        self, name, as_of, payload, readiness, *, position_opened_at=None,
        rule_states=None, card_states=None,
    ):
        states = self._rule_delay_states if rule_states is None else rule_states
        matches = dict(payload["matches"])
        delays = {}
        for rule_name, rule in self.cards[name].rules.items():
            if not rule.initial_delay:
                continue
            raw_matched = matches[rule_name]
            result = self._delay_result(
                (name, rule_name), as_of, bool(raw_matched and readiness[rule_name]),
                rule.initial_delay, rule.initial_delay_mode, position_opened_at, states,
            )
            matches[rule_name] = result.pop("passed")
            delays[rule_name] = {
                **result, "raw_matched": raw_matched, "matched": matches[rule_name],
            }
        if delays:
            scoped = payload.get("position_opened_at")
            payload = self._score_card(name, matches, readiness, payload["lookback_ready"])
            payload["rule_delays"] = delays
            if scoped is not None:
                payload["position_opened_at"] = scoped
        return self._apply_delay(
            name, as_of, payload, position_opened_at=position_opened_at, states=card_states,
        )

    def _prepare_cards(self):
        """Score at native completion boundaries once, not at decision ticks."""
        for name, card in self.cards.items():
            if any(
                self.configs[rule.indicator_id].calculate is not None
                and self.configs[rule.indicator_id].execution == "per_decision"
                for rule in card.rules.values()
            ):
                continue
            absent = {rule: False for rule in card.rules}
            self._initial_cards[name] = self._score_card(
                name, dict(absent), dict(absent), dict(absent),
            )
            timeline = pd.DatetimeIndex([], tz="UTC")
            for rule_name in card.rules:
                timeline = timeline.union(self._rule_outputs[name, rule_name].index)
            timeline = timeline.sort_values()
            arrays = {
                rule_name: self._rule_outputs[name, rule_name][
                    ["matched", "ready", "lookback_ready"]
                ].reindex(
                    timeline, method="ffill",
                ).fillna(False).to_numpy(dtype=bool)
                for rule_name in card.rules
            }
            if timeline.empty:
                self._card_outputs[name] = timeline, [], []
                continue
            # A card state changes only when a match or readiness bit changes.
            # Retain those boundaries; backward alignment preserves all ticks.
            changed = np.zeros(len(timeline), dtype=bool)
            changed[0] = True
            for array in arrays.values():
                changed[1:] |= np.any(array[1:] != array[:-1], axis=1)
            timeline = timeline[changed]
            states = np.column_stack([
                array[changed] for array in arrays.values()
            ])
            _, first, inverse = np.unique(
                np.packbits(states, axis=1), axis=0,
                return_index=True, return_inverse=True,
            )
            payloads, readiness_rows = [], []
            for state in states[first].reshape(-1, len(card.rules), 3):
                matches = {
                    rule: bool(row[0])
                    for rule, row in zip(card.rules, state)
                }
                readiness = {
                    rule: bool(row[1])
                    for rule, row in zip(card.rules, state)
                }
                full = {
                    rule: bool(row[2])
                    for rule, row in zip(card.rules, state)
                }
                payloads.append(
                    self._score_card(name, matches, readiness, full)
                    if state.any() else self._initial_cards[name]
                )
                readiness_rows.append(readiness)
            self._card_outputs[name] = (
                timeline,
                np.asarray(payloads, dtype=object)[inverse].tolist(),
                np.asarray(readiness_rows, dtype=object)[inverse].tolist(),
            )

    def _ingest(self, data, as_of):
        updates = {}
        for identifier in self.required_windows:
            if identifier not in data:
                continue
            frame = self._frame(data[identifier], identifier)
            source = self.data_sources[identifier]
            frame = frame.loc[_completion(frame.index, source.time_frame.value) <= as_of]
            existing = self._history.get(identifier)
            if existing is None:
                if not self._prepared:
                    updates[identifier] = frame
                continue
            positions = existing.index.get_indexer(frame.index)
            overlap = positions >= 0
            if not existing.iloc[positions[overlap]].equals(frame.loc[overlap]):
                raise ValueError(f"Source {identifier} changed overlapping historical values")
            new = frame.loc[~overlap]
            if self._prepared:
                if not new.empty:
                    raise ValueError(f"Source {identifier} extends prepared history; prepare a fresh run")
            elif not new.empty:
                if not existing.empty and new.index.min() <= existing.index.max():
                    raise ValueError(f"Source {identifier} inserts historical observations")
                updates[identifier] = pd.concat([existing, new])
        self._history.update(updates)
        self._recompute(set(updates), as_of=as_of)

    @property
    def decision_index(self):
        """Union of the observed native timestamps in this run."""
        index = pd.DatetimeIndex([], tz="UTC")
        for frame in self._history.values():
            index = index.union(frame.index)
        return index.sort_values()

    def card_signal_series(self, index, *, position_scoped_candidates=False):
        """Return causal ready-and-qualified masks from prepared card caches.

        Index values are decision times, not candle completion times. Callable
        indicators must opt into precompute and remain causal for every row.
        """
        if not self._prepared:
            raise ValueError(
                "Card signal series require a prepared indicator engine"
            )
        if self.fill_driven_cards and not position_scoped_candidates:
            raise ValueError(
                "Position-scoped lookbacks and delayed exits require "
                "fill-driven vector execution; "
                "static masks alone cannot evaluate them"
            )
        decisions = pd.DatetimeIndex(pd.to_datetime(index, utc=True))
        if decisions.has_duplicates or not decisions.is_monotonic_increasing:
            raise ValueError("Decision timestamps must be unique and increasing")
        output = {}
        self._vector_decisions = decisions
        for name in self.cards:
            if name not in self._card_outputs:
                raise ValueError(
                    f"Vector card {name} requires execution='precompute' "
                    "for callable indicators"
                )
            timeline, payloads, readiness_rows = self._card_outputs[name]
            flags = pd.Series(
                [
                    payload["ready"] and (
                        name in self.fill_driven_cards or payload["passed"]
                    ) for payload in payloads
                ],
                index=timeline, dtype=bool,
            )
            output[name] = flags.reindex(
                decisions, method="ffill", fill_value=False,
            )
            if (
                (self.cards[name].initial_delay
                 or any(rule.initial_delay for rule in self.cards[name].rules.values()))
                and name not in self.fill_driven_cards
            ):
                rule_states, card_states = {}, {}
                confirmed = []
                for stamp in decisions:
                    end = timeline.searchsorted(stamp, side="right")
                    payload = _copy_card_payload(
                        payloads[end - 1] if end else self._initial_cards[name],
                    )
                    readiness = readiness_rows[end - 1] if end else {
                        rule: False for rule in self.cards[name].rules
                    }
                    payload = self._delayed_payload(
                        name, stamp, payload, readiness,
                        rule_states=rule_states, card_states=card_states,
                    )
                    confirmed.append(payload["ready"] and payload["passed"])
                output[name] = pd.Series(confirmed, index=decisions, dtype=bool)
        return output

    @property
    def fill_driven_cards(self):
        return self.position_scoped_cards | {
            name for name, card in self.cards.items()
            if (card.initial_delay or any(rule.initial_delay for rule in card.rules.values()))
            and card.side in (
                SignalSide.CLOSE_LONG, SignalSide.CLOSE_SHORT,
            )
        }

    def evaluate_card(self, name, as_of, *, position_opened_at=None):
        """Score cached rule observations with an optional actual-fill boundary."""
        as_of = pd.Timestamp(as_of)
        if pd.isna(as_of) or as_of.tzinfo is None:
            raise ValueError("Card evaluation time must be timezone-aware")
        card = self.cards[name]
        scoped = name in self.position_scoped_cards
        if scoped:
            if position_opened_at is None:
                raise ValueError("Position-scoped lookbacks require an actual entry fill time")
            position_opened_at = pd.Timestamp(position_opened_at)
            if (
                pd.isna(position_opened_at) or position_opened_at.tzinfo is None
                or position_opened_at > as_of
            ):
                raise ValueError("Position entry time must be timezone-aware and not in the future")
        if self._prepared and name in self._card_outputs and not scoped:
            timeline, payloads, readiness_rows = self._card_outputs[name]
            end = timeline.searchsorted(as_of, side="right")
            payload, readiness = (
                (_copy_card_payload(payloads[end - 1]), dict(readiness_rows[end - 1]))
                if end else (
                    _copy_card_payload(self._initial_cards[name]),
                    {rule: False for rule in card.rules},
                )
            )
            return self._delayed_payload(
                name, as_of, payload, readiness, position_opened_at=position_opened_at,
            ), readiness
        matches, readiness, full_readiness = {}, {}, {}
        for rule_name, rule in card.rules.items():
            native = self._rule_outputs.get((name, rule_name))
            end = native.index.searchsorted(as_of, side="right") if native is not None else 0
            observed = native.iloc[end - 1] if end else None
            matches[rule_name] = bool(observed["matched"]) if end else False
            readiness[rule_name] = bool(observed["ready"]) if end else False
            full_readiness[rule_name] = bool(observed["lookback_ready"]) if end else False
            if rule.lookback_scope == "position" and end:
                last_match = observed["last_match_at"]
                matches[rule_name] = (
                    matches[rule_name] and pd.notna(last_match)
                    and last_match > position_opened_at
                )
                first = native.index.searchsorted(position_opened_at, side="right")
                full_readiness[rule_name] &= end - first >= rule.lookback_period
        payload = self._score_card(name, matches, readiness, full_readiness)
        if scoped:
            payload["position_opened_at"] = position_opened_at.isoformat()
        return self._delayed_payload(
            name, as_of, payload, readiness, position_opened_at=position_opened_at,
        ), readiness

    def position_scoped_exit_signal(self, as_of, position_opened_at, *, side):
        if (self._vector_decisions is not None
                and pd.Timestamp(as_of) not in self._vector_decisions):
            return False
        if position_opened_at is None:
            return False
        for name, card in self.cards.items():
            if card.side is side:
                payload, _ = self.evaluate_card(
                    name, as_of, position_opened_at=position_opened_at,
                )
                if payload["ready"] and payload["passed"]:
                    return True
        return False

    def evaluate(
        self, data, as_of, *, inactive_cards: Mapping[str, str] | None = None,
        position_opened_at: Mapping[str, datetime] | None = None,
    ):
        inactive_cards = {} if inactive_cards is None else inactive_cards
        if set(inactive_cards) - self.cards.keys():
            raise ValueError("Inactive cards reference unknown card ids")
        if position_opened_at is not None and set(position_opened_at) - self.cards.keys():
            raise ValueError("Position entry times reference unknown card ids")
        if any(not isinstance(reason, str) or not reason for reason in inactive_cards.values()):
            raise ValueError("Inactive card reasons must be nonempty strings")
        as_of = pd.Timestamp(as_of)
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        as_of = as_of.tz_convert("UTC")
        if self._last_as_of is not None and as_of < self._last_as_of:
            raise ValueError("Indicator evaluation cannot rewind; prepare a fresh run")
        self._ingest(data, as_of)
        values, ready = {}, {}
        for name, config in self.configs.items():
            native = self._outputs.get(self._keys[name])
            if native is None:
                end = 0
            else:
                available = self._available[self._keys[name]]
                end = available.searchsorted(as_of, side="right")
            latest = native.iloc[end - 1].to_dict() if end else {
                output: float("nan") for output in config.outputs
            }
            values[name] = latest
            ready[name] = all(np.isfinite(value) for value in latest.values())
        cards, rule_readiness = {}, {}
        for name in self.cards:
            if name in inactive_cards:
                self._delay_states.pop(name, None)
                for rule_name in self.cards[name].rules:
                    self._rule_delay_states.pop((name, rule_name), None)
                cards[name] = {
                    "evaluation_status": "skipped",
                    "signal_reason": inactive_cards[name],
                }
                rule_readiness[name] = {}
                continue
            cards[name], rule_readiness[name] = self.evaluate_card(
                name, as_of, position_opened_at=(position_opened_at or {}).get(name),
            )
        self._last_as_of = as_of
        return IndicatorEvaluation(values, cards, ready, rule_readiness)
