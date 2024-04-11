from typing import List, Dict, Tuple
from datetime import datetime
from .backtest_report import BacktestReport


class BacktestReportsEvaluation:
    """
    A class to evaluate backtest reports.
    """
    report_groupings: Dict[Tuple[datetime, datetime], List[BacktestReport]]

    def __init__(self, backtest_reports: List[BacktestReport]):
        self.backtest_reports = backtest_reports
        self.group_reports(self.backtest_reports)
        self.profit_order = {}

        self.growth_order = {}
        self.percentage_positive_trades_order = {}

        for key in self.report_groupings:
            self.profit_order[key] = self.order_on_profit(
                self.report_groupings[key].copy()
            )
            self.growth_order[key] = self.order_on_growth(
                self.report_groupings[key].copy()
            )
            self.percentage_positive_trades_order[key] = \
                self.order_on_positive_trades(
                    self.report_groupings[key].copy()
                )
            self.profit_order_all = self.order_on_profit(
                self.backtest_reports.copy()
            )
            self.growth_order_all = self.order_on_growth(
                self.backtest_reports.copy()
            )

    def order_on_profit(self, reports: List[BacktestReport]):
        return sorted(reports, key=lambda x: x.total_net_gain, reverse=True)

    def order_on_growth(self, reports: List[BacktestReport]):
        return sorted(reports, key=lambda x: x.growth_rate, reverse=True)

    def order_on_positive_trades(self, reports: List[BacktestReport]):
        return sorted(
            reports, key=lambda x: x.percentage_positive_trades, reverse=True
        )

    def group_reports(self, reports: List[BacktestReport]):
        """
        Group reports by backtest start and end date.
        """
        self.report_groupings = {}

        for report in reports:
            key = (report.backtest_start_date, report.backtest_end_date)
            if key not in self.report_groupings:
                self.report_groupings[key] = []
            self.report_groupings[key].append(report)

    def get_date_ranges(self):
        """
        Get the date ranges of the backtest reports.
        """
        return list(self.report_groupings.keys())
