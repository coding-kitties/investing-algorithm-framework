import os
import json

from dataclasses import dataclass, field
from typing import List, Dict
import numpy as np
import pandas as pd
from datetime import timezone

from .backtest_metrics import BacktestMetrics


@dataclass
class BacktestPermutationTest:
    """
    Represents the result of a permutation test on backtest metrics.

    Attributes:
        real_metrics (BacktestMetrics): The real backtest metrics.
        permutated_metrics (List[BacktestMetrics]): A list of backtest
            metrics objects from permuted backtests.
        p_values (Dict[str, float]): A dictionary mapping metric names
            to their permutation test p-values.
    """

    # Default set of metrics for permutation testing
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
    backtest_start_date: pd.Timestamp = None
    backtest_end_date: pd.Timestamp = None
    backtest_date_range_name: str = None

    def compute_p_values(
        self, metrics: List[str] = None, one_sided: bool = True
    ) -> None:
        """
        Compute p-values for the selected metrics based on the
        permutation distribution.

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
        Save the permutation test results to disk (JSON + Parquet).

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
    def open(path: str) -> "BacktestPermutationTest":
        """
        Load the permutation test results from disk (JSON + Parquet).

        Args:
            path (str): The directory path where the results are saved.

        Returns:
            BacktestPermutationTest: The loaded permutation test results.
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

        return BacktestPermutationTest(
            real_metrics=real_metrics,
            permutated_metrics=permutated_metrics,
            p_values=p_values,
            backtest_start_date=backtest_start_date,
            backtest_end_date=backtest_end_date,
            backtest_date_range_name=backtest_date_range_name
        )

    def create_directory_name(self) -> str:
        """
        Create a directory name for the backtest run based on its attributes.

        Returns:
            str: A string representing the directory name.
        """
        start_str = self.real_metrics.backtest_start_date.strftime("%Y%m%d")
        end_str = self.real_metrics.backtest_end_date.strftime("%Y%m%d")
        dir_name = f"permutation_test_{start_str}_{end_str}"
        return dir_name

    def to_dict(self) -> Dict:
        """
        Convert the permutation test results to a dictionary.

        Returns:
            dict: A dictionary representation of the permutation test results.
        """
        return {
            "real_metrics": self.real_metrics.to_dict(),
            "permutated_metrics": [
                pm.to_dict() for pm in self.permutated_metrics
            ],
            "p_values": self.p_values,
            # Note: DataFrames are not included in the dict representation
        }
