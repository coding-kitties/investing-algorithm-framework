import csv
import os
import json

from investing_algorithm_framework.domain import BacktestReport, \
    DATETIME_FORMAT_BACKTESTING


class BacktestReportWriterService:
    """
    Service to write backtest reports to a file.

    Service supports writing backtest reports to the following formats:
    - CSV
    """
    def write_report_to_csv(
        self, report: BacktestReport, output_directory: str
    ) -> str:
        """
        Write a backtest report to a CSV file.
        """

        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        csv_file_path = self.create_report_name(
            report, output_directory, extension=".csv"
        )
        report_dict = report.to_dict()

        with open(csv_file_path, 'w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=report_dict.keys())
            writer.writeheader()
            writer.writerow(report_dict)

        return csv_file_path

    def write_report_to_json(
        self, report: BacktestReport, output_directory: str
    ):
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        backtest_start_date = report.backtest_start_date\
            .strftime(DATETIME_FORMAT_BACKTESTING)
        backtest_end_date = report.backtest_end_date\
            .strftime(DATETIME_FORMAT_BACKTESTING)
        created_at = report.created_at.strftime(DATETIME_FORMAT_BACKTESTING)
        json_file_path = os.path.join(
            output_directory,
            f"report_{report.name}_backtest_start_date_"
            f"{backtest_start_date}_backtest_end_date_"
            f"{backtest_end_date}_created_at_{created_at}.json"
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
            f"report_{report.name}_backtest_start_date_"
            f"{backtest_start_date}_backtest_end_date_"
            f"{backtest_end_date}_created_at_{created_at}{extension}"
        )
        return file_path
