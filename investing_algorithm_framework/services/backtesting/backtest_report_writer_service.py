import csv
import os

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
        backtest_start_date = report.backtest_start_date\
            .strftime(DATETIME_FORMAT_BACKTESTING)
        backtest_end_date = report.backtest_end_date\
            .strftime(DATETIME_FORMAT_BACKTESTING)
        created_at = report.created_at.strftime(DATETIME_FORMAT_BACKTESTING)
        csv_file_path = os.path.join(
            output_directory,
            f"report_{report.name}_backtest_start_date_"
            f"{backtest_start_date}_backtest_end_date_"
            f"{backtest_end_date}_created_at_{created_at}.csv"
        )
        report_dict = report.to_dict()

        with open(csv_file_path, 'w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=report_dict.keys())
            writer.writeheader()
            writer.writerow(report_dict)

        return csv_file_path
