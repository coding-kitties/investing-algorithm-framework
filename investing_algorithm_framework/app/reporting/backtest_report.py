import json
import os
import sys
import webbrowser
from dataclasses import dataclass
from IPython.display import display, HTML
from IPython import get_ipython

from investing_algorithm_framework.domain import OperationalException, \
    BacktestResult
from .generate import add_html_report, add_metrics


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
    html_report: str = None
    html_report_path: str = None
    metrics = None
    results: BacktestResult = None
    risk_free_rate: float = None

    def __post_init__(self):
        """
        Post-initialization method to create the metrics and HTML report
        """
        if self.metrics is None:
            add_metrics(self, self.risk_free_rate)

        if self.html_report is None:
            add_html_report(self)

    def show(self):
        """
        Display the HTML report in a Jupyter notebook cell.
        """
        if self.html_report:

            def in_jupyter_notebook():
                try:
                    shell = get_ipython().__class__.__name__
                    return shell == 'ZMQInteractiveShell'
                except (NameError, ImportError):
                    return False

            if in_jupyter_notebook():
                display(HTML(self.html_report))
            else:
                webbrowser.open(f"file://{self.html_report_path}")
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
        if not os.path.exists(file_path):
            raise OperationalException(
                "Backtest report file or folder does not exist"
            )

        if os.path.isdir(file_path):
            report_file_path = os.path.join(file_path, "report.json")
            results = None
            html_report = None

            # Open the results file
            if os.path.isfile(report_file_path):
                with open(report_file_path, 'r') as json_file:
                    data = json.load(json_file)

                results = BacktestResult.from_dict(data)

            # Open the html file
            html_file_path = os.path.join(file_path, "report.html")
            if os.path.isfile(html_file_path):
                with open(html_file_path, 'r') as html_file:
                    html_content = html_file.read()
                html_report = html_content

            if not results and not html_report:
                raise OperationalException(
                    "No report.json or report.html found in the directory"
                )

            return BacktestReport(
                html_report=html_report,
                results=results,
                html_report_path=html_file_path
            )
        else:
            return BacktestReport.open(file_path)

    def save(
        self,
        path,
        save_strategy=True,
        algorithm=None,
        strategy_directory_path=None
    ):
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

        Returns:
            None
        """

        if not os.path.exists(path):
            os.makedirs(path)

        print("Saving backtest report to", path)
        print(f"save_strategy: {save_strategy}")
        if save_strategy:
            # If strategy_directory_path is set, copy the strategy code to
            # the report directory
            if strategy_directory_path is not None:
                print("Saving strategy code from directory")
                # check if the strategy directory exists
                if not os.path.exists(strategy_directory_path) and \
                        not os.path.isdir(strategy_directory_path):
                    raise OperationalException(
                        "Strategy directory does not exist"
                    )

                # Copy the strategy directory to the report directory
                strategy_directory_name = os.path.basename(
                    strategy_directory_path
                )
                output_strategy_directory = os.path.join(
                    path, strategy_directory_name
                )
                if not os.path.exists(output_strategy_directory):
                    os.makedirs(output_strategy_directory)

                strategy_files = os.listdir(strategy_directory_path)
                for file in strategy_files:
                    source_file = os.path.join(strategy_directory_path, file)
                    destination_file = os.path.join(
                        output_strategy_directory, file
                    )

                    if os.path.isfile(source_file):
                        # Copy the file to the output directory
                        with open(source_file, "rb") as src:
                            with open(destination_file, "wb") as dst:
                                dst.write(src.read())

            elif algorithm is not None:
                print("saving strategy code from algorithm")
                strategy = algorithm.strategies[0]
                mod = sys.modules[strategy.__module__]
                strategy_directory_path = os.path.dirname(mod.__file__)
                strategy_directory_name = os.path.basename(
                    strategy_directory_path
                )
                strategy_files = os.listdir(strategy_directory_path)
                output_strategy_directory = os.path.join(
                    path, strategy_directory_name
                )

                if not os.path.exists(output_strategy_directory):
                    os.makedirs(output_strategy_directory)

                for file in strategy_files:
                    source_file = os.path.join(strategy_directory_path, file)
                    destination_file = os.path.join(
                        output_strategy_directory, file
                    )

                    if os.path.isfile(source_file):
                        # Copy the file to the output directory
                        with open(source_file, "rb") as src:
                            with open(destination_file, "wb") as dst:
                                dst.write(src.read())

            else:
                raise OperationalException(
                    "No strategy directory or algorithm provided to save the "
                    "strategy code."
                )

        # Save the results as a JSON file
        if self.results is not None:
            results_file_path = os.path.join(path, "report.json")
            with open(results_file_path, 'w') as json_file:
                json.dump(self.results.to_dict(), json_file, indent=4)

        # Save the HTML report
        if self.html_report is not None:
            html_file_path = os.path.join(path, "report.html")
            with open(html_file_path, 'w') as html_file:
                html_file.write(self.html_report)
            self.html_report_path = html_file_path

        if self.results is not None:
            data = self.results.to_dict()

            with open(os.path.join(path, "report.json"), 'w') as json_file:
                json.dump(data, json_file, indent=4)
