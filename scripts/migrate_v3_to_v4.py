"""Migrate ``.iafbt`` bundles from envelope v3 (v9.0) to v4 (multi-
universe / studies).

What the upgrade does:

* Re-writes the 8-byte bundle header so :func:`peek_bundle_format_version`
  reports ``4``.
* Adds the v4 envelope keys — ``study_name``, ``study_description``,
  ``universes``, and per-engine ``summaries_by_universe`` slots — at
  their defaults (``None`` / empty list / empty dict). No study or
  universe metadata is invented; that's a job for whoever re-runs the
  study, not a format upgrade.
* Leaves all summary metrics, runs, and time-series data byte-for-byte
  identical (round-tripped through msgpack+zstd, which is
  deterministic for our payload shape).

This script is a thin wrapper over ``iaf migrate-bundles --to v4``: it
discovers every ``.iafbt`` under DIRECTORY (recursively), skips bundles
already at v4, and rewrites the rest atomically (tmp file + fsync +
``os.replace``). An interrupted run leaves the source bundle intact.

Usage::

    poetry run python scripts/migrate_v3_to_v4.py ./backtest_results
    poetry run python scripts/migrate_v3_to_v4.py ./backtest_results --dry-run
    poetry run python scripts/migrate_v3_to_v4.py ./backtest_results -w 4

The script exits non-zero if the underlying CLI reports a failure;
otherwise it prints the same one-line summary
(``Upgraded N item(s) to v4 in <dir> ...``).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from click.testing import CliRunner

from investing_algorithm_framework.cli.cli import migrate_bundles_cmd
from investing_algorithm_framework.domain.backtesting.bundle import (
    BUNDLE_FORMAT_VERSION,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Upgrade .iafbt bundles from envelope v3 to v4 in place."
        ),
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory to walk recursively for .iafbt bundles.",
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=None,
        help="Parallel workers (default: min(8, CPU count)).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the bundles that would be upgraded and exit.",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Skip refreshing index.sqlite at the destination.",
    )
    args = parser.parse_args(argv)

    if BUNDLE_FORMAT_VERSION < 4:
        # Fail early instead of silently producing a v3 file.
        print(
            f"This iaf build targets envelope v{BUNDLE_FORMAT_VERSION}, "
            "not v4. Upgrade the framework before running this script.",
            file=sys.stderr,
        )
        return 2

    directory = args.directory.resolve()
    if not directory.is_dir():
        print(f"Not a directory: {directory}", file=sys.stderr)
        return 2

    cli_args: list[str] = [str(directory), "--to", "v4"]
    if args.workers is not None:
        cli_args += ["--workers", str(args.workers)]
    if args.dry_run:
        cli_args.append("--dry-run")
    if args.no_index:
        cli_args.append("--no-index")

    result = CliRunner().invoke(
        migrate_bundles_cmd, cli_args, standalone_mode=False,
    )
    if result.output:
        sys.stdout.write(result.output)
    if result.exception is not None and not isinstance(
        result.exception, SystemExit
    ):
        # Re-raise so the user sees a real traceback.
        raise result.exception
    return int(result.exit_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
