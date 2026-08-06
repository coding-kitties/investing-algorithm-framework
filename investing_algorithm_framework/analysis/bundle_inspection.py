from pathlib import Path
from typing import List, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from investing_algorithm_framework.domain.backtesting.backtest import (
        Backtest,
    )


def print_bundle_summary(
    source: Union[str, Path, List["Backtest"], List[Union[str, Path]]],
) -> None:
    """Print studies and universes for every ``.obtf`` bundle.

    Args:
        source: One of:
            * A directory path (str or Path) — all ``*<BUNDLE_EXT>`` files
              in that directory are opened.
            * A list of file paths (str or Path) — each path is opened
              as a bundle.
            * A list of :class:`Backtest` objects — used directly.
    """
    from investing_algorithm_framework.domain.backtesting.backtest import (
        Backtest,
    )

    bundles = _resolve_bundles(source, Backtest)

    print(f"\n{'=' * 60}")
    print(f"  {len(bundles)} bundle(s)")
    print(f"{'=' * 60}")

    for i, bt in enumerate(bundles):
        print(f"\n[{i}] algorithm_id={bt.algorithm_id!r}")
        print("  studies:")

        for s in bt.get_studies():
            print(
                f"    - {s['name']!r} "
                f"engines={s['engines']} n_runs={s['n_runs']} "
                f"universes={s['universes']} n_windows={s['n_windows']}"
            )
            if s.get("description"):
                print(f"      description: {s['description']}")

        print("  universes:")
        for u in bt.get_universes():
            print(
                f"    - key={u['key']!r} market={u['market']!r} "
                f"trading_symbol={u['trading_symbol']!r} "
                f"symbols={u['symbols']} "
                f"engines={u['engines']} studies={u['studies']}"
            )

        # Monte Carlo tests (stored per-study).
        _print_monte_carlo_tests(bt)


def _print_monte_carlo_tests(bt) -> None:
    """Print Monte Carlo test p-values for every study that has them.

    Monte-Carlo tests live on each :class:`EngineSlot` (their null
    distribution is engine-specific), so we iterate ``vector`` and
    ``event`` slots per study and label each row with its engine.
    """
    has_any = False

    for name, study in bt.studies.items():
        for engine in ("vector", "event"):
            slot = study.engine_results.get(engine)
            if slot is None:
                continue
            mc_tests = slot.monte_carlo_tests
            if not mc_tests:
                continue

            if not has_any:
                print("  monte carlo tests:")
                has_any = True

            for mct in mc_tests:
                window_label = mct.backtest_date_range_name or (
                    f"{mct.backtest_start_date} -> {mct.backtest_end_date}"
                )
                n_perms = (
                    len(mct.permutated_metrics)
                    if mct.permutated_metrics else 0
                )
                print(
                    f"    - study={name!r} engine={engine!r} "
                    f"window={window_label!r} n_permutations={n_perms}"
                )
                p_values = mct.p_values or {}
                if p_values:
                    for metric, pval in sorted(p_values.items()):
                        sig = " *" if pval is not None and pval < 0.05 else ""
                        print(f"        {metric:30s} p={pval}{sig}")


def _resolve_bundles(source, backtest_cls):
    """Normalise *source* into a list of Backtest objects."""
    # Already a list of Backtest instances.
    if (isinstance(source, list)
            and source
            and isinstance(source[0], backtest_cls)):
        return source

    # A list of file paths.
    if isinstance(source, list):
        return [backtest_cls.open(p) for p in sorted(source)]

    # A single directory or file path.
    path = Path(source)
    if path.is_dir():
        from investing_algorithm_framework.domain.backtesting.bundle import (
            BUNDLE_EXT,
        )
        return [
            backtest_cls.open(p)
            for p in sorted(path.glob(f"*{BUNDLE_EXT}"))
        ]

    # Single file.
    return [backtest_cls.open(path)]
