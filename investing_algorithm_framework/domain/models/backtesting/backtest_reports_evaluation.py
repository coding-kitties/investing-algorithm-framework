from typing import List
from .backtest_report import BacktestReport


class BacktestReportsEvaluation:
    """
    A class to evaluate backtest reports.
    """

    def __init__(self, backtest_reports: List[BacktestReport]):
        self.backtest_reports = backtest_reports
        self.profit_order = self.order_on_profit()
        self.growth_order = self.order_on_growth()

    def order_on_profit(self):
        copy = self.backtest_reports.copy()
        return sorted(copy, key=lambda x: x.total_net_gain, reverse=True)

    def order_on_growth(self):
        copy = self.backtest_reports.copy()
        return sorted(copy, key=lambda x: x.growth_rate, reverse=True)
