import os
from investing_algorithm_framework import BacktestReport, recalculate_backtests, retag_backtests


batch_one_path = os.path.join(os.path.dirname(__file__), "tutorial/backtest_results/in_sample")

if __name__ == "__main__":
    report = BacktestReport.open(directory_path=batch_one_path)
    report.show()
