"""Scalar-only, study-scoped sweep results and validated pruning."""

import os

import pandas as pd

from investing_algorithm_framework.domain import (
    Backtest, BacktestIndex, OperationalException, resolve_backtest_path,
    generate_backtest_summary_metrics,
)


SESSION_INDEX_FILENAME = "backtest_session_index.parquet"
_IDENTITY = ("algorithm_id", "study_name", "engine_type", "universe_key")


def compact_rows(
    backtest, directory, study_name, date_range, evaluated_ranges,
    engine="vector",
):
    path = resolve_backtest_path(directory, backtest.algorithm_id)
    if path is None:
        raise OperationalException(
            f"Missing persisted backtest {backtest.algorithm_id}."
        )
    window_metrics = {}
    study = backtest.get_study(study_name)
    if study is not None:
        slot = study.engine_results.get(engine)
        if slot is not None:
            # Bundles may already contain later windows from a prior sweep.
            # Pruning must see only the windows evaluated so far this time.
            slot.runs = [
                run for run in slot.runs
                if (run.backtest_start_date, run.backtest_end_date)
                in evaluated_ranges
            ]
            slot.summary = generate_backtest_summary_metrics([
                run.backtest_metrics for run in slot.runs
                if run.backtest_metrics is not None
            ])
            backtest.regenerate_summaries_by_universe()
            for run in slot.runs:
                if (
                    run.backtest_start_date == date_range.start_date
                    and run.backtest_end_date == date_range.end_date
                    and run.backtest_metrics is not None
                ):
                    window_metrics = {
                        f"window_{key}": value
                        for key, value in
                        run.backtest_metrics.to_dict().items()
                        if value is None or isinstance(
                            value, (str, int, float, bool)
                        )
                    }
                    break
    rows = []
    for row in backtest.index_rows(
        bundle_path=os.path.relpath(path, directory)
    ):
        if row.study_name != study_name or row.engine_type != engine:
            continue
        flat = {
            key: value for key, value in row.to_flat_dict().items()
            if value is None or isinstance(value, (str, int, float, bool))
        }
        flat.update(window_metrics)
        rows.append(flat)
    if not rows:
        raise OperationalException(
            f"Backtest {backtest.algorithm_id} has no {engine} results "
            f"for study {study_name!r}."
        )
    return rows


def make_index(directory, rows):
    frame = pd.DataFrame(rows)
    for column in (*_IDENTITY, "bundle_path"):
        if column not in frame:
            frame[column] = pd.Series(dtype="object")
    return BacktestIndex(directory, frame)


def validated_filter(index, callback, *args):
    # Protect the authoritative scalar rows from callback mutation.
    candidate = callback(
        BacktestIndex(index.directory, index.df.copy(deep=True)), *args
    )
    if not isinstance(candidate, BacktestIndex):
        raise OperationalException(
            "A metrics filter must return a subset BacktestIndex."
        )
    if candidate.directory.resolve() != index.directory.resolve():
        raise OperationalException(
            "A metrics filter returned a foreign index."
        )
    required = set(_IDENTITY) | {"bundle_path"}
    if not required.issubset(candidate.df.columns):
        raise OperationalException(
            "A metrics filter removed identity columns."
        )

    def keys(frame):
        return [
            tuple(None if pd.isna(value) else value for value in row)
            for row in frame[list(_IDENTITY)].itertuples(
                index=False, name=None
            )
        ]

    originals = keys(index.df)
    selected = keys(candidate.df)
    if len(set(selected)) != len(selected) or not set(selected) <= set(
        originals
    ):
        raise OperationalException(
            "A metrics filter returned duplicate or foreign "
            "algorithm/study/engine rows."
        )
    # Return authoritative rows, not user-supplied paths or fabricated metrics.
    positions = {key: position for position, key in enumerate(originals)}
    return BacktestIndex(
        index.directory,
        index.df.iloc[
            [positions[key] for key in selected]
        ].reset_index(drop=True).copy(),
    )


def persist_index(index):
    index.directory.mkdir(parents=True, exist_ok=True)
    destination = index.directory / SESSION_INDEX_FILENAME
    staging = destination.with_suffix(".parquet.pending")
    try:
        index.df.to_parquet(staging, index=False)
        with staging.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(staging, destination)
    finally:
        if staging.exists():
            staging.unlink()


def mark_filtered(directory, previous_ids, surviving_ids, date_range, guard):
    for algorithm_id in previous_ids:
        guard.require()
        path = resolve_backtest_path(directory, algorithm_id)
        if path is None:
            continue
        backtest = Backtest.open(path)
        metadata = backtest.metadata
        if metadata is None:
            metadata = backtest.metadata = {}
        filtered = algorithm_id not in surviving_ids
        changed = metadata.get("filtered_out", False) != filtered
        if filtered:
            metadata["filtered_out"] = True
            metadata["filtered_out_at_date_range"] = (
                date_range.name or
                f"{date_range.start_date.isoformat()}_"
                f"{date_range.end_date.isoformat()}"
            )
            changed = True
        elif metadata.get("filtered_out", False):
            metadata["filtered_out"] = False
            metadata.pop("filtered_out_at_date_range", None)
        if changed:
            backtest.save(path)
        del backtest
