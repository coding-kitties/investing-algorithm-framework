import json
from typing import List
from dataclasses import field
import os
import sys
import webbrowser
import logging
from dataclasses import dataclass
from IPython.display import display, HTML
from IPython import get_ipython

from investing_algorithm_framework.domain import OperationalException, \
    BacktestResult
from .generate import add_html_report, add_metrics


logger = logging.getLogger("investing_algorithm_framework")


@dataclass
class BacktestReport:
    """
    A class to represent a backtest report. The backtest report contains
    the results of a backtest, including metrics and an HTML report. Also,
    it stores the path to the used strategy directory, which can be used to
    load the strategy code later.

    Attributes:
        html_report (str): The HTML report content.
        html_report_path (str): The file path where the HTML report is saved.
        metrics (dict): A dictionary containing various metrics from the backtest.
        results (BacktestResult): An instance of BacktestResult containing
            the results of the backtest.
        risk_free_rate (float): The risk-free rate used in the backtest.
        strategy_path (str): The path to the strategy directory used in the
            backtest.
    """
    strategy_related_paths: List[str] = field(default_factory=list)
    html_report: str = None
    html_report_path: str = None
    metrics: dict = field(default_factory=dict)
    results: BacktestResult = None
    risk_free_rate: float = None
    algorithm: object = None
    data_files: list = None

    @staticmethod
    def create(
        results: BacktestResult,
        risk_free_rate: float = None,
        data_files: list = None,
        algorithm: object = None,
        strategy_directory_path: str = None,
    ):
        """
        Create a new BacktestReport instance with the provided results,
        risk-free rate, data files, algorithm, and strategy directory path.

        Args:
            results (BacktestResult): The results of the backtest.
            risk_free_rate (float, optional): The risk-free rate used in the
                backtest. Defaults to None.
            data_files (list, optional): A list of data files used in the
                backtest. Defaults to None.
            algorithm (object, optional): The algorithm used in the backtest.
                Defaults to None.
            strategy_directory_path (str, optional): The path to the strategy
                directory used in the backtest. Defaults to None.

        Returns:
            BacktestReport: An instance of BacktestReport with the provided
                parameters.
        """

        # List all strategy related files in the strategy directory
        strategy_related_paths = []

        if strategy_directory_path is not None:
            if not os.path.exists(strategy_directory_path) or \
                    not os.path.isdir(strategy_directory_path):
                raise OperationalException(
                    "Strategy directory does not exist"
                )

            strategy_files = os.listdir(strategy_directory_path)
            for file in strategy_files:
                source_file = os.path.join(strategy_directory_path, file)
                if os.path.isfile(source_file):
                    strategy_related_paths.append(source_file)
        else:
            if algorithm is not None and hasattr(algorithm, 'strategies'):
                for strategy in algorithm.strategies:
                    mod = sys.modules[strategy.__module__]
                    strategy_directory_path = os.path.dirname(mod.__file__)
                    strategy_files = os.listdir(strategy_directory_path)
                    for file in strategy_files:
                        source_file = os.path.join(
                            strategy_directory_path, file
                        )
                        if os.path.isfile(source_file):
                            strategy_related_paths.append(source_file)

        report = BacktestReport(
            results=results,
            risk_free_rate=risk_free_rate,
            data_files=data_files,
            strategy_related_paths=strategy_related_paths
        )
        add_metrics(report, risk_free_rate)
        add_html_report(report)
        return report

    def show(self, browser: bool = False):
        """
        Display the HTML report in a Jupyter notebook cell.
        """

        if self.html_report:
            # Save the html report to a tmp location
            path = "/tmp/backtest_report.html"
            with open(path, "w") as html_file:
                html_file.write(self.html_report)

            if browser:
                webbrowser.open(f"file://{path}")

            def in_jupyter_notebook():
                try:
                    shell = get_ipython().__class__.__name__
                    return shell == 'ZMQInteractiveShell'
                except (NameError, ImportError):
                    return False

            if in_jupyter_notebook():
                display(HTML(self.html_report))
            else:
                webbrowser.open(f"file://{path}")
        else:
            raise OperationalException("No HTML report available to display.")

    @staticmethod
    def open(file_path) -> "BacktestReport":
        """
        Open the backtest report from a file.

        Args:
            file_path (str): The file path from which the report will
                be loaded.

        Returns:
            BacktestReport: An instance of BacktestReport loaded from the file.
        """
        # Load all strategy related files if there is a strategy directory
        strategy_related_paths = []
        strategy_directory = os.path.join(file_path, "strategies")
        if os.path.exists(strategy_directory) and os.path.isdir(strategy_directory):
            strategy_files = os.listdir(strategy_directory)
            for file in strategy_files:
                source_file = os.path.join(strategy_directory, file)
                if os.path.isfile(source_file):
                    strategy_related_paths.append(source_file)

        # Load the data files if there is a data directory
        data_files = []
        data_directory = os.path.join(file_path, "backtest_data")
        if os.path.exists(data_directory) and os.path.isdir(data_directory):
            data_files = [
                os.path.join(data_directory, file)
                for file in os.listdir(data_directory)
                if os.path.isfile(os.path.join(data_directory, file))
            ]

        # Load the metrics from the JSON file
        metrics_file_path = os.path.join(file_path, "metrics.json")
        metrics = None
        if os.path.exists(metrics_file_path):
            with open(metrics_file_path, 'r') as json_file:
                metrics = json.load(json_file)

        # Load the results from the JSON file
        results_file_path = os.path.join(file_path, "results.json")
        results = None
        if os.path.exists(results_file_path):
            with open(results_file_path, 'r') as json_file:
                results = BacktestResult.from_dict(json.load(json_file))

        # Load the HTML report from the HTML file
        html_file_path = os.path.join(file_path, "report.html")
        html_report = None
        if os.path.exists(html_file_path):
            with open(html_file_path, 'r') as html_file:
                html_report = html_file.read()

        # Create the BacktestReport instance
        return BacktestReport(
            strategy_related_paths=strategy_related_paths,
            html_report=html_report,
            metrics=metrics,
            results=results,
            risk_free_rate=None,  # Risk-free rate is not saved in the report
            data_files=data_files
        )

    def save(self, path):
        """
        Save the backtest report. When saving the report, the metrics
        will be saved as a JSON, the backtest results will be saved as a
        JSON, and the HTML report will be saved as an HTML file.

        Args:
            path (str): The file path where the report will be saved.
            save_strategy (bool): If True, the strategy code will be copied
                to the report directory. Defaults to True.
            algorithm (Algorithm, optional): The algorithm used for the
                backtest. If provided, the strategy code will be copied to
                the report directory.
            strategy_directory_path (str, optional): The path to the
                strategy directory. If provided, the strategy code will be
                copied to the report directory.
            data_source_files (list, optional): A list of data source files
                to be included in the report. If provided, these files will
                be copied to the report directory.

        Returns:
            None
        """

        if not os.path.exists(path):
            os.makedirs(path)

        # Save the strategy
        if self.strategy_related_paths is not None:
            # Create a strategy directory if it does not exist
            strategy_directory = os.path.join(path, "strategies")
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
        if self.data_files is not None:
            # Create a data directory if it does not exist
            data_directory = os.path.join(path, "backtest_data")

            if not os.path.exists(data_directory):
                os.makedirs(data_directory)

            # Copy data files to the report directory
            for file in self.data_files:

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

        # Save the metrics as a JSON file
        if self.metrics is not None:
            metrics_file_path = os.path.join(path, "metrics.json")
            with open(metrics_file_path, 'w') as json_file:
                json.dump(self.metrics, json_file, indent=4, default=str)

        # Save the HTML report
        if self.html_report is not None:
            html_file_path = os.path.join(path, "report.html")
            with open(html_file_path, 'w') as html_file:
                html_file.write(self.html_report)
            self.html_report_path = html_file_path

        # Save the results as a JSON file
        if self.results is not None:
            results_file_path = os.path.join(path, "results.json")
            with open(results_file_path, 'w') as json_file:
                json.dump(self.results.to_dict(), json_file, indent=4)
