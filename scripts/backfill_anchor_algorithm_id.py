"""Throwaway: backfill ``anchor_algorithm_id`` on tutorial bundles.

Rule (per user):
- ``examples/tutorial/backtest_results/*.iafbt`` (parent dir) stays
  untouched: these are the anchors, ``anchor_algorithm_id`` remains
  ``None``.
- ``examples/tutorial/backtest_results/top_selection/*.iafbt`` get
  ``anchor_algorithm_id = bundle.algorithm_id`` (anchor=self).

After rewriting the bundles, the SQLite Tier-1 index for
``top_selection/`` is rebuilt from scratch so the new column is
populated. The parent index is also refreshed (it's incremental, so
that's effectively a no-op for unchanged files but ensures the
``anchor_algorithm_id`` column exists in the schema).

Usage:
    poetry run python scripts/backfill_anchor_algorithm_id.py \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from investing_algorithm_framework.cli.index_command import build_index
from investing_algorithm_framework.domain.backtesting.bundle import (
    open_bundle,
    save_bundle,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PARENT_DIR = REPO_ROOT / "examples" / "tutorial" / "backtest_results"
TOP_SELECTION_DIR = PARENT_DIR / "top_selection"


def backfill_top_selection(directory: Path, *, dry_run: bool) -> int:
    n = 0
    for path in sorted(directory.glob("*.iafbt")):
        bt = open_bundle(path)
        if bt.anchor_algorithm_id == bt.algorithm_id:
            print(f"  [skip] {path.name} already tagged")
            continue
        if bt.anchor_algorithm_id is not None:
            print(
                f"  [warn] {path.name} has explicit anchor "
                f"{bt.anchor_algorithm_id!r}; leaving as-is"
            )
            continue
        print(
            f"  [set ] {path.name}  anchor_algorithm_id "
            f"-> {bt.algorithm_id!r}"
        )
        bt.anchor_algorithm_id = bt.algorithm_id
        if not dry_run:
            save_bundle(bt, path, merge=False)
        n += 1
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions but do not modify any files.",
    )
    args = parser.parse_args()

    if not TOP_SELECTION_DIR.is_dir():
        raise SystemExit(f"Missing dir: {TOP_SELECTION_DIR}")

    print(f"== Backfilling top_selection/ bundles in {TOP_SELECTION_DIR}")
    n_changed = backfill_top_selection(
        TOP_SELECTION_DIR, dry_run=args.dry_run,
    )
    print(f"   {n_changed} bundle(s) updated")

    if args.dry_run:
        print("\n[dry-run] skipping index rebuild")
        return

    print(f"\n== Rebuilding index for {TOP_SELECTION_DIR}")
    out = build_index(
        str(TOP_SELECTION_DIR), incremental=False, show_progress=False,
    )
    print(f"   wrote {out}")

    print(f"\n== Rebuilding index for {PARENT_DIR}")
    out = build_index(
        str(PARENT_DIR), incremental=False, show_progress=False,
    )
    print(f"   wrote {out}")


if __name__ == "__main__":
    main()
