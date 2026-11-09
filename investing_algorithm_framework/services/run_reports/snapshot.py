from copy import deepcopy
from datetime import timezone
from logging import getLogger

import pandas as pd
import polars as pl

from investing_algorithm_framework.domain import ENVIRONMENT, Environment, \
    OrderStatus, DataType
from investing_algorithm_framework.domain.models.run_report import \
    create_run_report_id, normalize_report_value
from investing_algorithm_framework.services.indicator_engine import \
    _completion, _normalize


logger = getLogger("investing_algorithm_framework")


def data_source_snapshots(*, strategy_id, timestamp, sources, data):
    """Record the latest causal source row, never the entire input window."""
    as_of = pd.Timestamp(timestamp)
    as_of = (
        as_of.tz_localize("UTC") if as_of.tz is None
        else as_of.tz_convert("UTC")
    )
    records = []
    for source in sources or []:
        identifier = source.get_identifier()
        raw = data[identifier]
        source_timestamp, values = None, {}
        if source.data_type is DataType.OHLCV and raw is not None \
                and not isinstance(raw, (pd.DataFrame, pl.DataFrame)):
            raise TypeError(
                f"OHLCV source {identifier} requires a pandas or polars "
                "DataFrame"
            )
        if isinstance(raw, (pd.DataFrame, pl.DataFrame)):
            if source.data_type is DataType.OHLCV \
                    and source.time_frame is None:
                raise ValueError(
                    f"OHLCV source {identifier} requires a time_frame"
                )
            frame = _normalize(raw, identifier, preserve=True)
            availability = (
                _completion(frame.index, source.time_frame.value)
                if source.data_type is DataType.OHLCV else frame.index
            )
            eligible = frame.loc[availability <= as_of]
            if not eligible.empty:
                source_timestamp = eligible.index[-1].to_pydatetime()
                values = {
                    str(key): (
                        None if value is pd.NA or value is pd.NaT else value
                    )
                    for key, value in eligible.iloc[-1].items()
                }
        elif isinstance(raw, dict):
            values = raw
            observed = raw.get("datetime", raw.get("timestamp"))
            if observed is not None:
                stamp = pd.to_datetime(
                    observed, utc=True,
                    **(
                        {"unit": "ms"}
                        if isinstance(observed, (int, float)) else {}
                    ),
                )
                if pd.isna(stamp):
                    raise ValueError(
                        f"Source {identifier} has an invalid timestamp"
                    )
                if stamp > as_of:
                    values = {}
                else:
                    source_timestamp = stamp.to_pydatetime()
        elif isinstance(raw, (list, tuple)):
            raise TypeError(
                f"Source {identifier} requires timestamped DataFrames "
                "for row sequences"
            )
        elif raw is not None:
            values = {"value": raw}
        records.append({
            "strategy_id": strategy_id, "timestamp": timestamp,
            "identifier": identifier, "symbol": source.symbol,
            "data_type": source.data_type, "time_frame": source.time_frame,
            "market": source.market, "source_timestamp": source_timestamp,
            "values": values,
        })
    return normalize_report_value(records)


def indicator_snapshots(
    *, strategy_id, timestamp, evaluated, decision_traces, signals,
):
    """Combine native outputs and indicator trace entries for one tick."""
    records = {}

    def add(symbol, name, value):
        records.setdefault((symbol, name), {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "timestamp": timestamp,
            "name": name,
            "value": value,
        })

    for record in evaluated:
        add(record["symbol"], record["name"], record["value"])
    traces = [
        (item.get("symbol"), item["decision_trace"])
        for item in decision_traces
    ] + [
        (signal["symbol"], signal["metadata"]["decision_trace"])
        for signal in signals
        if "decision_trace" in signal["metadata"]
    ]
    for symbol, trace in traces:
        for entry in trace.get("entries", []):
            if entry.get("group") == "indicators":
                add(symbol, entry["name"], entry["value"])
    return list(records.values())


def confluence_position_snapshots(strategy, context):
    symbols = set(strategy.symbols or [])
    symbols.update(
        source.symbol.split("/")[0]
        for source in strategy.data_sources or [] if source.symbol
    )
    records = {}
    for symbol in symbols:
        trades = [
            trade for trade in context.get_open_trades(target_symbol=symbol)
            if trade.filled_amount > 0
        ]
        long_entries = sum(not trade.is_short for trade in trades)
        short_entries = sum(trade.is_short for trade in trades)
        scaling = strategy.get_scaling_rule(symbol)
        records[symbol] = {
            "side": (
                "hedged" if long_entries and short_entries else
                "long" if long_entries else "short" if short_entries else "flat"
            ),
            "long_entries": long_entries, "short_entries": short_entries,
            "maximum_entries": scaling.max_entries if scaling else None,
        }
    return records


def confluence_score_snapshots(*, evaluated, signals, positions_before=None):
    """Attach this tick's signal outcome without changing card qualification."""
    outcomes = {
        (signal["symbol"], signal["side"], signal["source"]): signal
        for signal in signals or []
    }
    records = []
    for evaluated_card in evaluated:
        card = deepcopy(evaluated_card)
        signal = outcomes.get((
            card["symbol"], card["side"], card["card_id"],
        ))
        if signal is not None:
            status, reason = signal["status"], signal["reason"]
        elif signals is None:
            status, reason = "unknown", "strategy.execution_incomplete"
        elif card.get("evaluation_status") == "skipped":
            status, reason = "not_triggered", card["signal_reason"]
        elif not card["ready"]:
            status, reason = "not_emitted", "confluence.indicators_not_ready"
        elif not card["qualified"]:
            status, reason = "not_emitted", "confluence.not_qualified"
        else:
            status = "not_emitted"
            reason = card.get("signal_reason") or "confluence.signal_not_emitted"
        card.update(signal_status=status, signal_reason=reason)
        card["signal_strength"] = signal.get("strength") if signal else None
        card.pop("signal_reason_details", None)
        if signal is not None and signal.get("reason_details") is not None:
            card["signal_reason_details"] = deepcopy(signal["reason_details"])
        if positions_before is not None and card["symbol"] in positions_before:
            card["position_before"] = deepcopy(positions_before[card["symbol"]])
        records.append(card)
    return records


def protective_exit_snapshots(orders, trades=()):
    """Separate actual protective triggers and cumulative fill updates."""
    output = {"stop_losses": [], "take_profits": []}
    trade_map = {trade["id"]: trade for trade in trades}
    for order in orders:
        metadata = order.get("metadata") or {}
        reason = metadata.get("order_reason")
        if reason not in (
            "stop_loss", "take_profit", "stop_loss_mirror", "take_profit_mirror",
        ):
            continue
        kind = reason.removesuffix("_mirror")
        collection = "stop_losses" if kind == "stop_loss" else "take_profits"
        mirror = reason.endswith("_mirror")
        trigger = metadata.get("protective_trigger") or {}
        references = trigger.get("trades", [])
        if mirror:
            trade_id = metadata.get("_mirror_trade_id")
            references = [] if trade_id is None else [{
                "trade_id": trade_id, "amount": order["amount"],
            }]
        strategy_ids = {
            trade_map[ref["trade_id"]].get("strategy_id")
            for ref in references if ref["trade_id"] in trade_map
        } - {None}
        strategy_id = (
            order.get("strategy_id") or metadata.get("strategy_id")
            or (next(iter(strategy_ids)) if len(strategy_ids) == 1 else None)
        )
        triggered_at = (
            order.get("triggered_at") if mirror else
            trigger.get("timestamp") or order.get("created_at")
        )
        filled = order.get("filled") or 0
        if mirror and triggered_at is None and filled > 0:
            fills = metadata.get("protective_fills", [])
            triggered_at = (
                fills[0]["timestamp"] if fills else order.get("updated_at")
            )
        if triggered_at is None:
            continue
        rules = trigger.get("rules", metadata.get("protective_rules", []))
        trigger_price = (
            order.get("stop_price") if mirror
            else trigger.get("price", order.get("price"))
        )
        record = {
            "order_id": order["id"], "strategy_id": strategy_id,
            "symbol": order["target_symbol"],
            "direction": (
                "short" if order.get("order_side", "").lower() == "cover"
                else "long"
            ),
            "amount": order["amount"], "order_amount": order["amount"],
            "filled_amount": filled,
            "order_status": order["status"],
            "price": trigger_price,
            "price_source": (
                "threshold" if mirror else "trigger_observation"
                if trigger.get("price") is not None else "legacy_order_price"
            ),
            "rules": rules, "trades": references, "mirror": mirror,
        }
        stamp = pd.to_datetime(triggered_at, utc=True)
        if pd.isna(stamp):
            raise ValueError("Protective events require a valid timestamp")
        output[collection].append({
            **record, "event_type": "trigger",
            "timestamp": stamp.to_pydatetime(),
        })
        fills = metadata.get("protective_fills", [])
        if filled > 0 and not fills:
            if order.get("updated_at") is None:
                raise ValueError("Protective fills require an update timestamp")
            fills = [{
                "timestamp": order["updated_at"], "filled_amount": filled,
                "amount": filled, "price": order.get("price"),
                "order_status": order["status"],
                "sequence": f"legacy:{order['updated_at']}:{filled}",
            }]
        for sequence, fill in enumerate(fills):
            stamp = pd.to_datetime(fill["timestamp"], utc=True)
            if pd.isna(stamp):
                raise ValueError("Protective events require a valid timestamp")
            output[collection].append({
                **record, **fill, "event_type": "fill",
                "sequence": fill.get("sequence", sequence),
                "timestamp": stamp.to_pydatetime(),
                "price_source": "order_execution" if "protective_fills" in metadata else "legacy_order_price",
            })
    return normalize_report_value(output)


def run_report_snapshot(
    *,
    algorithm_id,
    started_at,
    completed_at,
    signal_log,
    config,
    order_service,
    position_service,
    portfolio_service,
    trade_service,
    portfolio_configuration_service,
    snapshot_state=True,
    number_of_iterations=None,
    status="completed",
    error=None,
    strategy_ids=None,
    indicators=None,
    confluence_scores=None,
    data_sources=None,
):
    def aware(value):
        return (
            value.replace(tzinfo=timezone.utc)
            if value is not None and value.tzinfo is None else value
        )

    started_at = aware(started_at)

    def include_order(order):
        created_at = aware(order.created_at)
        updated_at = aware(order.updated_at)
        return (
            created_at is not None and created_at >= started_at
        ) or (
            updated_at is not None and updated_at >= started_at
        ) or OrderStatus.is_pending(order.status)

    orders, positions, portfolios, trades = [], [], [], []
    if snapshot_state:
        try:
            orders = [
                order.to_dict() for order in order_service.get_all()
                if include_order(order)
            ]
            positions = [
                position.to_dict() for position in position_service.get_all()
            ]
            portfolios = [
                portfolio.to_dict()
                for portfolio in portfolio_service.get_all()
            ]
            trades = [trade.to_dict() for trade in trade_service.get_all()]
        except Exception:
            if status not in ("execution_error", "interrupted"):
                raise
            logger.exception("Could not snapshot failed run state")

    outcomes = list(signal_log)
    signals = [
        {
            **signal,
            "strategy_id": entry["strategy_id"],
            "timestamp": entry["timestamp"],
        }
        for entry in outcomes for signal in entry["signals"]
    ]
    decision_traces = [
        {
            "strategy_id": entry.get("strategy_id"),
            "timestamp": entry["timestamp"],
            "symbol": item.get("symbol"),
            **item["decision_trace"],
        }
        for entry in outcomes
        for item in entry.get("decision_traces", [])
    ]
    configurations = portfolio_configuration_service.get_all()
    protective = protective_exit_snapshots(orders, trades)
    return deepcopy({
        "id": create_run_report_id(algorithm_id, started_at),
        "algorithm_id": algorithm_id,
        "strategy_ids": strategy_ids if strategy_ids is not None else sorted({
            entry["strategy_id"] for entry in outcomes
            if entry.get("strategy_id") is not None
        }),
        "status": status,
        "error": error,
        "environment": Environment.for_portfolios(
            config[ENVIRONMENT], configurations,
        ).value,
        "number_of_iterations": number_of_iterations,
        "started_at": started_at,
        "completed_at": aware(completed_at),
        "orders": orders,
        "signals": signals,
        **protective,
        "indicators": indicators if indicators is not None else [],
        "confluence_scores": (
            confluence_scores if confluence_scores is not None else []
        ),
        "data_sources": data_sources if data_sources is not None else [],
        "positions": positions,
        "portfolios": portfolios,
        "trades": trades,
        "decision_traces": decision_traces,
    })
