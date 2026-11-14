"""Versioned, compressed sidecars for captured backtest evaluations."""

import gzip
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple
from uuid import uuid4

from investing_algorithm_framework.domain.exceptions import \
    OperationalException


RUN_REPORTS_PATH_COLUMN = "run_reports_path"
REPORT_SCOPE_COLUMNS = ("algorithm_id", "study_name", "engine_type")
_FORMAT_VERSION = 3


def report_scope(report: Dict[str, Any]) -> Tuple[str, str, str]:
    algorithm_id = report.get("algorithm_id")
    study_name = report.get("study_name")
    engine = report.get("engine")
    if (
        not isinstance(algorithm_id, str) or not algorithm_id
        or not isinstance(study_name, str) or not study_name
        or not isinstance(engine, str) or not engine
    ):
        raise OperationalException(
            "Persisted run reports require algorithm_id, study_name "
            "and engine strings."
        )
    return algorithm_id, study_name, engine


def save_run_reports(
    directory: Path, reports: List[Dict[str, Any]],
) -> str:
    """Atomically write one immutable sidecar for this invocation."""
    relative = Path("run_reports") / f"{uuid4().hex}.jsonl.gz"
    destination = directory / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_suffix(".gz.pending")
    try:
        with gzip.open(
            staging, "wt", encoding="utf-8", compresslevel=6,
        ) as handle:
            handle.write(json.dumps({
                "version": _FORMAT_VERSION, "count": len(reports),
            }) + "\n")
            for report in reports:
                report_scope(report)
                handle.write(json.dumps(
                    report, allow_nan=False, separators=(",", ":"),
                ) + "\n")
        with staging.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(staging, destination)
    finally:
        if staging.exists():
            staging.unlink()
    return relative.as_posix()


def iter_run_reports(
    directory: Path, reference: str,
) -> Iterator[Dict[str, Any]]:
    """Read and validate a sidecar without retaining unmatched reports."""
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts:
        raise OperationalException(
            "run_reports_path must be relative to the index directory."
        )
    path = directory / relative
    if not path.resolve().is_relative_to(directory.resolve()):
        raise OperationalException(
            "run_reports_path must remain within the index directory."
        )
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        header = json.loads(handle.readline())
        if (
            not isinstance(header, dict)
            or type(header.get("version")) is not int
            or header["version"] != _FORMAT_VERSION
            or type(header.get("count")) is not int
            or header["count"] < 0
        ):
            raise OperationalException(
                f"Invalid or unsupported run report header in {path}."
            )
        count = 0
        for line in handle:
            report = json.loads(line)
            if not isinstance(report, dict):
                raise OperationalException(
                    f"Invalid run report record in {path}."
                )
            report_scope(report)
            count += 1
            yield report
        if count != header["count"]:
            raise OperationalException(
                f"Run report count mismatch in {path}: "
                f"expected {header['count']}, read {count}."
            )
