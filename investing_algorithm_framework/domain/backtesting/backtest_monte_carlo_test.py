import os
import json

from dataclasses import dataclass, field
from typing import List, Dict
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from .backtest_metrics import BacktestMetrics
from .backtest_window import BacktestWindow


@dataclass
class BacktestMonteCarloTest:
    """Represents the result of a Monte-Carlo test on backtest metrics.

    Attributes:
        real_metrics (BacktestMetrics): The real backtest metrics.
        permutated_metrics (List[BacktestMetrics]): A list of backtest
            metrics objects from permuted backtests.
        p_values (Dict[str, float]): A dictionary mapping metric names
            to their Monte-Carlo test p-values.
        backtest_window (Optional[BacktestWindow]): The window this test
            was run on.  Exposes ``backtest_start_date``,
            ``backtest_end_date``, and ``backtest_date_range_name`` as
            read-only properties.
    """

    # Default set of metrics for Monte-Carlo testing
    DEFAULT_METRICS: List[str] = field(default_factory=lambda: [
        "cagr",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "profit_factor",
        "annual_volatility",
        "max_drawdown",
        "win_rate",
        "win_loss_ratio",
        "average_monthly_return"
    ])
    real_metrics: BacktestMetrics = None
    permutated_metrics: List[BacktestMetrics] = field(default_factory=list)
    p_values: Dict[str, float] = field(default_factory=dict)
    ohlcv_permutated_datasets: Dict[str, List[pd.DataFrame]] = \
        field(default_factory=dict)
    ohlcv_original_datasets: Dict[str, pd.DataFrame] = \
        field(default_factory=dict)
    backtest_window: BacktestWindow = field(default=None)

    def __post_init__(self):
        if self.backtest_window is None:
            raise TypeError(
                "BacktestMonteCarloTest requires a 'backtest_window'."
            )

    # ------------------------------------------------------------------
    # Backward-compat read-only properties
    # ------------------------------------------------------------------

    @property
    def backtest_start_date(self):
        """Start date derived from the window's active range."""
        if self.backtest_window is None:
            return None
        r = (
            self.backtest_window.test_range
            if self.backtest_window.test_range is not None
            else self.backtest_window.train_range
        )
        return r.start_date

    @property
    def backtest_end_date(self):
        """End date derived from the window's active range."""
        if self.backtest_window is None:
            return None
        r = (
            self.backtest_window.test_range
            if self.backtest_window.test_range is not None
            else self.backtest_window.train_range
        )
        return r.end_date

    @property
    def backtest_date_range_name(self):
        """Name of the active date range, derived from the window."""
        if self.backtest_window is None:
            return None
        r = (
            self.backtest_window.test_range
            if self.backtest_window.test_range is not None
            else self.backtest_window.train_range
        )
        return r.name

    def compute_p_values(
        self, metrics: List[str] = None, one_sided: bool = True
    ) -> None:
        """
        Compute p-values for the selected metrics based on the
        Monte-Carlo (permutation) null distribution.

        Args:
            metrics (List[str]): List of metric names to compute p-values for.
                If None, uses DEFAULT_METRICS.
            one_sided (bool): Whether to compute a one-sided
                test (default: True).
        """
        if metrics is None:
            metrics = self.DEFAULT_METRICS

        self.p_values = {}

        for metric in metrics:
            real_value = getattr(self.real_metrics, metric, None)
            if real_value is None:
                continue

            # Collect metric values across all permuted backtests
            dist = np.array([
                getattr(pm, metric, None)
                for pm in self.permutated_metrics
                if getattr(pm, metric, None) is not None
            ])

            if len(dist) == 0:
                continue

            if one_sided:
                p = np.mean(dist >= real_value)
            else:
                p = np.mean(np.abs(dist) >= abs(real_value))

            self.p_values[metric] = float(p)

    def summary(
        self, metrics: List[str] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Return a summary of real values, mean permuted values, and p-values.

        Args:
            metrics (List[str]): List of metric names to include
                in the summary. If None, uses DEFAULT_METRICS.

        Returns:
            Dict[str, Dict[str, float]]: A dictionary where each key
                is a metric name and the value is another dictionary
                with keys 'real', 'permuted_mean', and 'p_value'.
        """

        if metrics is None:
            metrics = self.DEFAULT_METRICS

        if not self.p_values:  # lazy compute
            self.compute_p_values(metrics=metrics)

        summary_dict = {}
        for metric in metrics:
            real_value = getattr(self.real_metrics, metric, None)
            if real_value is None:
                continue

            dist = np.array([
                getattr(pm, metric, None)
                for pm in self.permutated_metrics
                if getattr(pm, metric, None) is not None
            ])

            # Filter out inf / nan
            dist = dist[np.isfinite(dist)]

            real_value = getattr(self.real_metrics, metric, None)

            if real_value is None or not np.isfinite(real_value):
                continue

            if len(dist) == 0:
                continue

            summary_dict[metric] = {
                "real": float(real_value),
                "permuted_mean": float(np.mean(dist)),
                "p_value": self.p_values.get(metric, None),
            }

        return summary_dict

    def save(self, path: str) -> None:
        """
        Save the Monte-Carlo test results to disk (JSON + Parquet).

        Args:
            path (str): The directory path where to save the results.

        Returns:
            None
        """
        def ensure_iso(value):
            if hasattr(value, "isoformat"):
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                return value.isoformat()
            return value

        os.makedirs(path, exist_ok=True)

        # Save the real metrics
        self.real_metrics.save(os.path.join(path, "original_metrics.json"))

        permuted_dir = os.path.join(path, "permuted_metrics")
        os.makedirs(permuted_dir, exist_ok=True)

        for i, pm in enumerate(self.permutated_metrics):
            pm.save(os.path.join(permuted_dir, f"permuted_{i}.json"))

        # Save the P-values
        with open(os.path.join(path, "p_values.json"), "w") as f:
            json.dump(self.p_values, f)

        # Create a metadata file to store additional info such as
        # date range name, start and end dates
        metadata = {
            "backtest_start_date": ensure_iso(self.backtest_start_date),
            "backtest_date_range_name": self.backtest_date_range_name,
            "backtest_end_date": ensure_iso(self.backtest_end_date),
        }

        with open(os.path.join(path, "metadata.json"), "w") as f:
            json.dump(metadata, f)

    @staticmethod
    def open(path: str) -> "BacktestMonteCarloTest":
        """
        Load the Monte-Carlo test results from disk (JSON + Parquet).

        Args:
            path (str): The directory path where the results are saved.

        Returns:
            BacktestMonteCarloTest: The loaded Monte-Carlo test results.
        """
        original_metrics = os.path.join(path, "original_metrics.json")

        # Rehydrate BacktestMetrics
        real_metrics = BacktestMetrics.open(original_metrics)

        permuted_dir = os.path.join(path, "permuted_metrics")

        permutated_metrics = []
        if os.path.exists(permuted_dir):
            for fname in os.listdir(permuted_dir):
                if fname.startswith("permuted_"):
                    pm = BacktestMetrics.open(
                        os.path.join(permuted_dir, fname)
                    )
                    permutated_metrics.append(pm)

        p_values_path = os.path.join(path, "p_values.json")
        p_values = {}

        if os.path.exists(p_values_path):
            with open(p_values_path, "r") as f:
                p_values = json.load(f)

        # Load metadata
        metadata_path = os.path.join(path, "metadata.json")
        backtest_start_date = None
        backtest_end_date = None
        backtest_date_range_name = None

        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            backtest_start_date = pd.to_datetime(
                metadata.get("backtest_start_date"), utc=True
            )
            backtest_end_date = pd.to_datetime(
                metadata.get("backtest_end_date"), utc=True
            )
            backtest_date_range_name = metadata.get(
                "backtest_date_range_name"
            )

        # Reconstruct BacktestWindow from saved flat dates.
        backtest_window = None
        if backtest_start_date is not None:
            from .backtest_date_range import BacktestDateRange
            backtest_window = BacktestWindow(
                train_range=BacktestDateRange(
                    start_date=backtest_start_date.to_pydatetime(),
                    end_date=(
                        backtest_end_date.to_pydatetime()
                        if backtest_end_date is not None
                        else backtest_start_date.to_pydatetime()
                    ),
                    name=backtest_date_range_name,
                )
            )

        return BacktestMonteCarloTest(
            real_metrics=real_metrics,
            permutated_metrics=permutated_metrics,
            p_values=p_values,
            backtest_window=backtest_window,
        )

    def create_directory_name(self) -> str:
        """Return a filesystem-safe directory name for this test result."""
        start_str = self.backtest_start_date.strftime("%Y%m%d")
        end_str = self.backtest_end_date.strftime("%Y%m%d")
        return f"monte_carlo_test_{start_str}_{end_str}"

    def to_dict(self) -> Dict:
        """
        Convert the Monte-Carlo test results to a dictionary.

        Returns:
            dict: A dictionary representation of the Monte-Carlo test results.
        """
        def ensure_iso(value):
            if value is None:
                return None
            if hasattr(value, "isoformat"):
                if getattr(value, 'tzinfo', None) is None:
                    value = value.replace(tzinfo=timezone.utc)
                return value.isoformat()
            return value

        return {
            "real_metrics": (
                self.real_metrics.to_dict() if self.real_metrics else None
            ),
            "permutated_metrics": [
                pm.to_dict() for pm in self.permutated_metrics
            ],
            "p_values": self.p_values,
            "backtest_window": (
                self.backtest_window.to_dict()
                if self.backtest_window is not None else None
            ),
            # Flat keys kept for backward compatibility.
            "backtest_start_date": ensure_iso(self.backtest_start_date),
            "backtest_end_date": ensure_iso(self.backtest_end_date),
            "backtest_date_range_name": self.backtest_date_range_name,
            # Note: DataFrames are not included in the dict representation
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "BacktestMonteCarloTest":
        """
        Reconstruct a ``BacktestMonteCarloTest`` from the dict produced
        by :py:meth:`to_dict`. Used by the binary bundle loader (#487).
        ``permutated_dataframes`` is not round-tripped (also true of
        the directory loader).
        """
        if data is None:
            return None

        real = (
            BacktestMetrics.from_dict(data.get("real_metrics"))
            if data.get("real_metrics") else None
        )
        permuted = [
            BacktestMetrics.from_dict(pm)
            for pm in (data.get("permutated_metrics") or [])
        ]
        p_values = data.get("p_values") or {}

        def _parse_dt(v):
            if v is None or isinstance(v, datetime):
                return v
            if isinstance(v, str):
                return pd.to_datetime(v, utc=True).to_pydatetime()
            return v

        # Reconstruct BacktestWindow: prefer explicit key, else flat dates.
        bw_raw = data.get("backtest_window")
        backtest_window = None
        if bw_raw is not None and isinstance(bw_raw, dict):
            from .backtest_date_range import BacktestDateRange
            tr_raw = bw_raw.get("train_range") or {}
            te_raw = bw_raw.get("test_range")
            _train = BacktestDateRange(
                start_date=_parse_dt(tr_raw.get("start")),
                end_date=_parse_dt(tr_raw.get("end")),
                name=tr_raw.get("name"),
            )
            _test = (
                BacktestDateRange(
                    start_date=_parse_dt(te_raw.get("start")),
                    end_date=_parse_dt(te_raw.get("end")),
                    name=te_raw.get("name"),
                )
                if te_raw is not None else None
            )
            backtest_window = BacktestWindow(
                train_range=_train,
                test_range=_test,
                warmup_days=bw_raw.get("warmup_days", 0),
                fold_index=bw_raw.get("fold_index"),
                name=bw_raw.get("name"),
            )
        elif bw_raw is not None:
            backtest_window = bw_raw  # already a BacktestWindow instance
        else:
            # Legacy flat format.
            start = _parse_dt(data.get("backtest_start_date"))
            end = _parse_dt(data.get("backtest_end_date"))
            name = data.get("backtest_date_range_name")
            if start is not None:
                from .backtest_date_range import BacktestDateRange
                backtest_window = BacktestWindow(
                    train_range=BacktestDateRange(
                        start_date=start,
                        end_date=end if end is not None else start,
                        name=name,
                    )
                )

        return cls(
            real_metrics=real,
            permutated_metrics=permuted,
            p_values=p_values,
            backtest_window=backtest_window,
        )
