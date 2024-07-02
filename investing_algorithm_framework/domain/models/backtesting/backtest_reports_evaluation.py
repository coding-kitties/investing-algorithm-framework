from typing import List, Dict

from investing_algorithm_framework.domain.exceptions import \
    OperationalException
from investing_algorithm_framework.domain.models.backtesting\
    .backtest_date_range import BacktestDateRange
from .backtest_report import BacktestReport


class BacktestReportsEvaluation:
    """
    A class to evaluate backtest reports.

    This class is used to evaluate backtest reports and order them based on
    different metrics. It also groups the reports by backtest date range.

    The class has methods to get the best algorithm based on profit and growth.
    """
    report_groupings: Dict[BacktestDateRange, List[BacktestReport]]

    def __init__(self, backtest_reports: List[BacktestReport]):

        if backtest_reports is None:
            raise OperationalException("No backtest reports to evaluate")

        self.backtest_reports = backtest_reports
        self.group_reports(self.backtest_reports)
        self.profit_order = {}
        self.profit_order_grouped_by_date = {}
        self.growth_order = {}
        self.growth_order_grouped_by_date = {}
        self.percentage_positive_trades_order = {}
        self.percentage_positive_trades_order_grouped_by_date = {}

        # Calculate all metrics and group reports
        for key in self.report_groupings:
            self.profit_order_grouped_by_date[key] = self.order_on_profit(
                self.report_groupings[key].copy()
            )
            self.growth_order_grouped_by_date[key] = self.order_on_growth(
                self.report_groupings[key].copy()
            )
            self.percentage_positive_trades_order_grouped_by_date[key] = \
                self.order_on_positive_trades(
                    self.report_groupings[key].copy()
                )

        # Overall ordered reports
        self.percentage_positive_trades_order = \
            self.order_on_positive_trades(self.backtest_reports)
        self.growth_order = self.order_on_growth(self.backtest_reports)
        self.profit_order = self.order_on_profit(self.backtest_reports)

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
            key = report.backtest_date_range
            if key not in self.report_groupings:
                self.report_groupings[key] = []
            self.report_groupings[key].append(report)

    def get_date_ranges(self):
        """
        Get the date ranges of the backtest reports.
        """
        return list(self.report_groupings.keys())

    def get_profit_order(
        self, backtest_date_range: BacktestDateRange = None
    ) -> List[BacktestReport]:
        """
        Function to get profit order of all the backtest reports
        in an ordered list.

        :param backtest_date_range: Tuple with two datetime objects
        :return: List of backtest reports
        """

        if backtest_date_range is None:
            return self.profit_order
        else:

            if backtest_date_range in self.profit_order_grouped_by_date:
                return self.profit_order_grouped_by_date[backtest_date_range]

            raise OperationalException("No matches for given date range")

    def get_growth_order(
        self, backtest_date_range: BacktestDateRange = None
    ) -> List[BacktestReport]:
        """
        Function to get growth order of all the backtest reports
        in an ordered list.

        :param backtest_date_range: Tuple with two datetime objects
        :return: List of backtest reports
        """

        if backtest_date_range is None:
            return self.growth_order
        else:

            if backtest_date_range in self.growth_order_grouped_by_date:
                return self.growth_order_grouped_by_date[backtest_date_range]

            raise OperationalException("No matches for given date range")

    def get_percentage_positive_trades_order(
        self, backtest_date_range: BacktestDateRange = None
    ) -> List[BacktestReport]:
        """
        Function to get growth order of all the backtest reports
        in an ordered list.

        :param backtest_date_range: Tuple with two datetime objects
        :return: List of backtest reports
        """

        if backtest_date_range is None:
            return self.percentage_positive_trades_order
        else:

            if backtest_date_range in \
                    self.percentage_positive_trades_order_grouped_by_date:
                return self.percentage_positive_trades_order_grouped_by_date[
                    backtest_date_range
                ]

            raise OperationalException("No matches for given date range")

    def rank(
        self,
        weight_profit=0.7,
        weight_growth=0.3,
        backtest_date_range: BacktestDateRange = None
    ) -> str:
        """
        Function to get the best overall algorithm based on the
        weighted sum of profit and growth.

        :param weight_profit: Weight for profit
        :param weight_growth: Weight for growth
        :return: Name of the best algorithm
        """

        # Create a dictionary with the algorithm name as key and group
        # the reports by name
        ordered_reports = {}

        if backtest_date_range is not None:
            reports = self.report_groupings[backtest_date_range]
        else:
            reports = self.backtest_reports

        for report in reports:
            if report.name not in ordered_reports:
                ordered_reports[report.name] = []
            ordered_reports[report.name].append(report)

        best_algorithm = None
        best_score = 0
        profit_score = 0
        growth_score = 0

        for algorithm in ordered_reports:
            profit_score += sum(
                [report.total_net_gain for
                 report in ordered_reports[algorithm]]
            )
            growth_score += sum(
                [report.growth for report in
                 ordered_reports[algorithm]]
            )
            score = weight_profit * profit_score + weight_growth * growth_score

            if score > best_score:
                best_score = score
                best_algorithm = algorithm

            profit_score = 0
            growth_score = 0

        return best_algorithm

    def get_reports(
        self, name: str = None, backtest_date_range: BacktestDateRange = None
    ) -> List[BacktestReport]:
        """
        Function to get all the reports for a given algorithm name.

        :param name: Name of the algorithm
        :param backtest_date_range: Tuple with two datetime objects
        :return: List of backtest reports
        """

        if name is not None and backtest_date_range is not None:
            return [
                report for report in self.report_groupings[backtest_date_range]
                if report.name == name
            ]

        if name is not None:
            return [
                report for report in self.backtest_reports
                if report.name == name
            ]

        if backtest_date_range is not None:
            return self.report_groupings[backtest_date_range]

    def get_report(
        self, name: str, backtest_date_range: BacktestDateRange = None
    ):
        """
        Function to get the report for a given algorithm name and date range.

        :param name: Name of the algorithm
        :param backtest_date_range: Tuple with two datetime objects
        :return: Backtest report
        """
        reports = self.get_reports(name, backtest_date_range)

        if len(reports) == 0:
            raise OperationalException(
                "No matches for given name and date range"
            )

        return reports[0]
