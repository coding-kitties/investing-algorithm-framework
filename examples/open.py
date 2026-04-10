import os
from investing_algorithm_framework import BacktestReport, recalculate_backtests


batch_one_path = os.path.join("examples", "batch_one")

if __name__ == "__main__":
    report = BacktestReport.open(directory_path=batch_one_path)
    recalculate_backtests(report.backtests)
    report.show()
