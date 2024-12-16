import json
import os

from investing_algorithm_framework.domain import BacktestReport, \
    DATETIME_FORMAT_BACKTESTING


class BacktestReportWriterService:
    """
    Service to write backtest reports to a file.

    Service supports writing backtest reports to the following formats:
    - JSON
    """

    def write_report_to_json(
        self, report: BacktestReport, output_directory: str
    ) -> None:
        """
        Function to write a backtest report to a JSON file.

        Parameters:
            - report: BacktestReport
                The backtest report to write to a file.
            - output_directory: str
                The directory to store the backtest report file.

        Returns:
            - None
        """

        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
      
        json_file_path = self.create_report_file_path(
            report, output_directory, extension=".json"
        )
       
        report_dict = report.to_dict()
        # Convert dictionary to JSON
        json_data = json.dumps(report_dict, indent=4)

        # Write JSON data to a .json file
        with open(json_file_path, "w") as json_file:
            json_file.write(json_data)

    @staticmethod
    def create_report_name(report, output_directory, extension=".json"):
        backtest_start_date = report.backtest_start_date \
            .strftime(DATETIME_FORMAT_BACKTESTING)
        backtest_end_date = report.backtest_end_date \
            .strftime(DATETIME_FORMAT_BACKTESTING)
        created_at = report.created_at.strftime(DATETIME_FORMAT_BACKTESTING)
        file_path = os.path.join(
            output_directory,
            f"report_{report.name}_backtest-start-date_"
            f"{backtest_start_date}_backtest-end-date_"
            f"{backtest_end_date}_created-at_{created_at}{extension}"
        )
        return file_path
    
    @staticmethod
    def create_report_file_path(report, output_directory, extension=".json") -> str:
        """
        Function to create a file path for a backtest report.

        Parameters:
            - report: BacktestReport
                The backtest report to create a file path for.
            - output_directory: str
                The directory to store the backtest report file.
            - extension: str (default=".json") - optional
                The file extension to use for the backtest report file.
        Returns:
            - file_path: str
                The file path for the backtest report file.
        """
        backtest_start_date = report.backtest_start_date \
            .strftime(DATETIME_FORMAT_BACKTESTING)
        backtest_end_date = report.backtest_end_date \
            .strftime(DATETIME_FORMAT_BACKTESTING)
        created_at = report.created_at.strftime(DATETIME_FORMAT_BACKTESTING)
        file_path = os.path.join(
            output_directory,
            f"report_{report.name}_backtest-start-date_"
            f"{backtest_start_date}_backtest-end-date_"
            f"{backtest_end_date}_created-at_{created_at}{extension}"
        )
        return file_path
