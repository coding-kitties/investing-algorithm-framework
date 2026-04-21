import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from investing_algorithm_framework import BacktestReport, recalculate_backtests, retag_backtests


batch_one_path = os.path.join(os.path.dirname(__file__), "batch_one")

if __name__ == "__main__":
    retag_backtests("batch_one", directory_path=batch_one_path)
    report = BacktestReport.open(directory_path=batch_one_path)
    recalculate_backtests(report.backtests)
    report.show()
