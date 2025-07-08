import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from logging import getLogger
from typing import Dict, Union

from investing_algorithm_framework.domain.exceptions \
    import OperationalException

from .backtest_metrics import BacktestMetrics
from .backtest_results import BacktestResult


logger = getLogger(__name__)


@dataclass
class Backtest:
    """
    Represents a backtest of an algorithm. It contains the backtest metrics,
    backtest results, and paths to strategy and data files.

    Attributes:
        backtest_metrics (BacktestMetrics): The metrics of the backtest.
        backtest_results (BacktestResult): The results of the backtest.
        strategy_related_paths (list[str]): List of paths to strategy related
            files. These files are copied to the report directory.
        data_file_paths (list[str]): List of paths to data files. These files
            are copied to the report directory.
        meta_data (Dict[str, str]): Metadata related to the backtest, such as
            configuration parameters or additional information about the
            strategy that was backtested. This can be used for later
            reference or analysis.
        risk_free_rate (float): The risk-free rate used in the backtest,
            typically expressed as a decimal (e.g., 0.03 for 3%). This
    """
    backtest_metrics: BacktestMetrics = field(default=None)
    backtest_results: BacktestResult = field(default=None)
    strategy_related_paths: list[str] = field(default_factory=list)
    data_file_paths: list[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    risk_free_rate: float = None

    def to_dict(self) -> dict:
        """
        Convert the Backtest instance to a dictionary.

        Returns:
            dict: A dictionary representation of the Backtest instance.
        """
        return {
            'backtest_metrics':
                (self.backtest_metrics.to_dict()
                 if self.backtest_metrics else None),
            'backtest_results':
                (self.backtest_results.to_dict()
                 if self.backtest_results else None),
            'strategy_related_paths': self.strategy_related_paths,
            'data_file_paths': self.data_file_paths
        }

    @staticmethod
    def open(directory_path: Union[str, Path]) -> 'Backtest':
        """
        Open a backtest report from a directory and return a Backtest instance.

        Args:
            directory_path (str): The path to the directory containing the
                backtest report files.

        Returns:
            Backtest: An instance of Backtest with the loaded metrics
                and results.

        Raises:
            OperationalException: If the directory does not exist or if
            there is an error loading the files.
        """

        backtest_metrics = None
        backtest_results = None
        data_file_paths = []
        strategy_related_paths = []
        metadata = {}
        risk_free_rate = None

        if not os.path.exists(directory_path):
            raise OperationalException(
                f"The directory {directory_path} does not exist."
            )

        # Load backtest metrics
        metrics_file = os.path.join(directory_path, "metrics.json")
        if os.path.isfile(metrics_file):
            backtest_metrics = BacktestMetrics.open(metrics_file)

        # Load backtest results
        results_file = os.path.join(directory_path, "results.json")

        if os.path.isfile(results_file):
            backtest_results = BacktestResult.open(results_file)

        # Load strategy related paths
        strategy_directory = os.path.join(directory_path, "strategies")
        if os.path.isdir(strategy_directory):
            strategy_related_paths = [
                os.path.join(strategy_directory, f)
                for f in os.listdir(strategy_directory)
                if os.path.isfile(os.path.join(strategy_directory, f))
            ]

        # Load data file paths
        data_directory = os.path.join(directory_path, "backtest_data")
        if os.path.isdir(data_directory):
            data_file_paths = [
                os.path.join(data_directory, f)
                for f in os.listdir(data_directory)
                if os.path.isfile(os.path.join(data_directory, f))
            ]

        # Load metadata if available
        meta_file = os.path.join(directory_path, "metadata.json")
        if os.path.isfile(meta_file):
            with open(meta_file, 'r') as f:
                metadata = json.load(f)

        # Load risk-free rate if available
        risk_free_rate_file = os.path.join(
            directory_path, "risk_free_rate.json"
        )
        if os.path.isfile(risk_free_rate_file):
            with open(risk_free_rate_file, 'r') as f:
                try:
                    risk_free_rate = json.load(f).get(
                        'risk_free_rate', None
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding risk-free rate JSON: {e}")
                    risk_free_rate = None

        return Backtest(
            backtest_metrics=backtest_metrics,
            backtest_results=backtest_results,
            strategy_related_paths=strategy_related_paths,
            data_file_paths=data_file_paths,
            metadata=metadata,
            risk_free_rate=risk_free_rate
        )

    def save(self, directory_path: Union[str, Path]) -> None:
        """
        Save the backtest metrics to a file in JSON format. The metrics will
        always be saved in a file named `metrics.json`

        Args:
            directory_path (str): The directory where the metrics
            file will be saved.

        Raises:
            OperationalException: If the directory does not exist or if
            there is an error saving the files.

        Returns:
            None: This method does not return anything, it saves the
            metrics to a file.
        """

        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        # Call the save method of BacktestMetrics
        if self.backtest_metrics:
            self.backtest_metrics.save(directory_path)

        # Call the save method of BacktestResult
        if self.backtest_results:
            self.backtest_results.save(directory_path)

        # Save the strategy
        if self.strategy_related_paths is not None:
            # Create a strategy directory if it does not exist
            strategy_directory = os.path.join(directory_path, "strategies")
            if not os.path.exists(strategy_directory):
                os.makedirs(strategy_directory)

            # Copy strategy related files to the report directory
            for file in self.strategy_related_paths:
                if not os.path.isfile(file):
                    raise OperationalException(
                        f"Strategy file {file} does not exist"
                    )

                destination_file = os.path.join(
                    strategy_directory, os.path.basename(file)
                )
                with open(file, "rb") as src:
                    with open(destination_file, "wb") as dst:
                        dst.write(src.read())

        # Save the data files
        if self.data_file_paths is not None:
            # Create a data directory if it does not exist
            data_directory = os.path.join(directory_path, "backtest_data")

            if not os.path.exists(data_directory):
                os.makedirs(data_directory)

            # Copy data files to the report directory
            for file in self.data_file_paths:

                try:
                    if not os.path.isfile(file):
                        raise OperationalException(
                            f"Data file {file} does not exist"
                        )
                    destination_file = os.path.join(
                        data_directory, os.path.basename(file)
                    )
                    with open(file, "rb") as src:
                        with open(destination_file, "wb") as dst:
                            dst.write(src.read())
                except Exception as e:
                    logger.error(f"Error copying data file {file}: {e}")

        # Save metadata if available
        if self.meta_data:
            meta_file = os.path.join(directory_path, "metadata.json")
            with open(meta_file, 'w') as f:
                json.dump(self.metadata, f, indent=4)

        # Save risk-free rate if available
        if self.risk_free_rate is not None:
            risk_free_rate_file = os.path.join(
                directory_path, "risk_free_rate.json"
            )
            with open(risk_free_rate_file, 'w') as f:
                json.dump(
                    {'risk_free_rate': self.risk_free_rate}, f, indent=4
                )

    def __repr__(self):
        """
        Return a string representation of the Backtest instance.

        Returns:
            str: A string representation of the Backtest instance.
        """
        return json.dumps(
            self.to_dict(), indent=4, sort_keys=True, default=str
        )
