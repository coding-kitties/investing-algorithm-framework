import os
import json

from dataclasses import dataclass, field
from typing import List, Dict
import numpy as np
import pandas as pd

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
                "real": real_value,
                "permuted_mean": float(np.mean(dist)),
                "p_value": self.p_values.get(metric, None),
            }

        return summary_dict

    def save(self, path: str) -> None:
        """
        Save the permutation test results to disk (JSON + Parquet).
        """
        os.makedirs(path, exist_ok=True)

        # Save the real metrics
        self.real_metrics.save(os.path.join(path, "original_metrics"))

        permuted_dir = os.path.join(path, "permuted_metrics")
        os.makedirs(permuted_dir, exist_ok=True)

        for i, pm in enumerate(self.permutated_metrics):
            pm.save(os.path.join(permuted_dir, f"permuted_{i}"))

        # Save the P-values
        with open(os.path.join(path, "p_values.json"), "w") as f:
            json.dump(self.p_values, f)

    @staticmethod
    def open(path: str) -> "BacktestPermutationTest":
        """
        Load the permutation test results from disk (JSON + Parquet).
        """
        with open(os.path.join(path, "results.json"), "r") as f:
            results = json.load(f)

        # Rehydrate BacktestMetrics
        real_metrics = BacktestMetrics(**results["real_metrics"])
        permutated_metrics = [
            BacktestMetrics(**pm) for pm in results["permutated_metrics"]
        ]

        # Reload DataFrames
        ohlcv_original_datasets = {}
        ohlcv_permutated_datasets = {}
        for file in os.listdir(path):
            if file.startswith("original_") and file.endswith(".parquet"):
                key = file.replace("original_", "").replace(".parquet", "")
                ohlcv_original_datasets[key] = pd.read_parquet(
                    os.path.join(path, file)
                )
            elif file.startswith("permuted_") and file.endswith(".parquet"):
                key = file.replace("permuted_", "").replace(".parquet", "")
                ohlcv_permutated_datasets[key] = pd.read_parquet(
                    os.path.join(path, file)
                )

        return BacktestPermutationTest(
            real_metrics=real_metrics,
            permutated_metrics=permutated_metrics,
            p_values=results["p_values"],
            ohlcv_original_datasets=ohlcv_original_datasets,
            ohlcv_permutated_datasets=ohlcv_permutated_datasets
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
        """
        return {
            "real_metrics": self.real_metrics.to_dict(),
            "permutated_metrics": [
                pm.to_dict() for pm in self.permutated_metrics
            ],
            "p_values": self.p_values,
            # Note: DataFrames are not included in the dict representation
        }
