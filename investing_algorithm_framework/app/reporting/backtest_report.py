import os
import json
from dataclasses import dataclass


from investing_algorithm_framework.domain import OperationalException, \
    BacktestResult


@dataclass
class BacktestReport:
    html_report: str = None
    metrics = None
    results: BacktestResult = None

    def show_html_report(self):
        """
        Display the HTML report in a Jupyter notebook cell.
        """
        if self.html_report:
            from IPython.display import display, HTML
            display(HTML(self.html_report))
        else:
            print(
                "No HTML report available. Please generate the report first."
            )

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

            return BacktestReport(html_report=html_report, results=results)
        else:
            return BacktestReport.open(file_path)

    def save(self, path):
        """
        Save the backtest report. When saving the report, the metrics
        will be saved as a JSON, the backtest results will be saved as a
        JSON, and the HTML report will be saved as an HTML file.

        Args:
            path (str): The file path where the report will be saved.

        Returns:
            None
        """

        if not os.path.exists(path):
            os.makedirs(path)

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

        if self.results is not None:
            data = self.results.to_dict()

            with open(os.path.join(path, "report.json"), 'w') as json_file:
                json.dump(data, json_file, indent=4)


    @staticmethod
    def is_backtest_report(path: str) -> bool:
        """
        Function to check if a file is a backtest report file.

        Args:
            path (str): The path to the file

        Returns:
            bool: True if the file is a backtest report file, otherwise False
        """

        # # Check if the file is a JSON file
        # if path.endswith(".json"):
        #
        #     # # Check if the file name matches the backtest
        #     # # report file name pattern
        #     # if re.match(
        #     #         BACKTEST_REPORT_FILE_NAME_PATTERN, os.path.basename(path)
        #     # ):
        #         return True
        #     else:
        #         # Try to load the file as a BacktestReport
        #         try:
        #             # Read the file
        #             with open(path, "r") as json_file:
        #                 # Parse the JSON file
        #                 report = json.load(json_file)
        #                 # Convert the JSON file to a
        #                 # BacktestReport object
        #                 BacktestReport.from_dict(report)
        #                 return True
        #         except Exception:
        #             # If the file is not a valid JSON file, return False
        #             return False

        return False
