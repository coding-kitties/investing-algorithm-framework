import os
from typing import List
from tabulate import tabulate
from investing_algorithm_framework.domain.models.backtesting import \
    BacktestReportsEvaluation, BacktestReport
from investing_algorithm_framework.domain.exceptions import \
    OperationalException
from .csv import load_csv_into_dict


def is_positive(number) -> bool:
    """
    Check if a number is positive.

    param number: The number
    :return: True if the number is positive, False otherwise
    """
    number = float(number)
    return number > 0


def pretty_print_backtest_reports_evaluation(
    backtest_reports_evaluation: BacktestReportsEvaluation,
    precision=4
) -> None:
    """
    Pretty print the backtest reports evaluation to the console.
    """
    print("====================Backtests report evaluation===================")
    profit = backtest_reports_evaluation.profit_order[0].total_net_gain
    profit_percentage = backtest_reports_evaluation\
        .profit_order[0].total_net_gain_percentage

    if is_positive(profit):
        print(
            f"* Most profitable: "
            f"{backtest_reports_evaluation.profit_order[0].name} with "
            f"a profit "
            f"of + {profit:.{precision}} {profit_percentage:.{precision}}%"
        )
    else:
        print(
            f"* Most profitable: "
            f"{backtest_reports_evaluation.profit_order[0].name} with "
            f"a profit "
            f"of {profit:.{precision}} {profit_percentage:.{precision}}%"
        )
    print("Top 3 most profitable:")
    for report in backtest_reports_evaluation.profit_order[:3]:
        profit = report.total_net_gain
        profit_percentage = report.total_net_gain_percentage
        trading_symbol = report.trading_symbol

        if is_positive(report.total_net_gain):
            print(
                f"* {report.name} with a profit "
                f"of +{profit:.{precision}} "
                f"{trading_symbol} "
                f"{profit_percentage:.{precision}}%"
            )
        else:
            print(
                f"* {report.name} with a profit of "
                f"{report.total_net_gain:.{precision}} "
                f"{trading_symbol} "
                f"{profit_percentage:.{precision}}%"
            )

    profit = backtest_reports_evaluation.profit_order[-1].total_net_gain
    profit_percentage = backtest_reports_evaluation\
        .profit_order[-1].total_net_gain_percentage

    print(
        f"* Least profitable: "
        f"{backtest_reports_evaluation.profit_order[-1].name} with a loss "
        f"of {profit:.{precision}} "
        f"{backtest_reports_evaluation.profit_order[0].trading_symbol} "
        f"{profit_percentage:.{precision}}%"
    )
    print("Top 3 least profitable:")

    for report in backtest_reports_evaluation.profit_order[-3:]:
        profit = report.total_net_gain
        profit_percentage = report.total_net_gain_percentage
        trading_symbol = report.trading_symbol
        if is_positive(profit):
            print(
                f"* {report.name} with a profit of +{profit:.{precision}} "
                f"{trading_symbol} "
                f"{profit_percentage:.{precision}}%"
            )
        else:
            print(
                f"* {report.name} with a profit of {profit:.{precision}} "
                f"{trading_symbol} "
                f"{profit_percentage:.{precision}}%"
            )

    print("==================================================================")
    growth = backtest_reports_evaluation.growth_order[0].growth
    growth_percentage = backtest_reports_evaluation.growth_order[0].growth_rate

    if is_positive(growth):
        print(
            f"* Largest growth: "
            f"{backtest_reports_evaluation.growth_order[0].name} with a "
            f"growth "
            f"of +{growth:.{precision}} "
            f"{backtest_reports_evaluation.profit_order[0].trading_symbol} "
            f"{growth_percentage:.{precision}}%"
        )
    else:
        print(
            f"* Largest growth: "
            f"{backtest_reports_evaluation.growth_order[0].name} with a "
            f"growth "
            f"of {growth:.{precision}} "
            f"{backtest_reports_evaluation.profit_order[0].trading_symbol} "
            f"{growth_percentage:.{precision}}%"
        )


def print_number_of_runs(report):

    if report.number_of_runs == 1:

        if report.inteval > 1:
            print(f"Strategy ran every {report.interval} {report.time_unit} "
                  f"for a total of {report.number_of_runs} time")


def pretty_print_backtest(
    backtest_report, show_positions=True, show_trades=True, precision=4
):
    """
    Pretty print the backtest report to the console.

    :param backtest_report: The backtest report
    :param show_positions: Show the positions
    :param show_trades: Show the trades
    :param precision: The precision of the numbers
    """
    print("====================Backtest report===============================")
    print(f"* Start date: {backtest_report.backtest_start_date}")
    print(f"* End date: {backtest_report.backtest_end_date}")
    print(f"* Number of days: {backtest_report.number_of_days}")
    print(f"* Number of runs: {backtest_report.number_of_runs}")
    print("====================Portfolio overview============================")
    print(f"* Number of orders: {backtest_report.number_of_orders}")
    print(f"* Initial balance: "
          f"{backtest_report.initial_unallocated:.{precision}f} "
          f"{backtest_report.trading_symbol}")
    print(f"* Final balance: {backtest_report.total_value:.{precision}f} "
          f"{backtest_report.trading_symbol}")
    print(f"* Total net gain: {backtest_report.total_net_gain:.{precision}f} "
          f"{backtest_report.trading_symbol}")
    print(f"* Total net gain percentage: "
          f"{backtest_report.total_net_gain_percentage:.{precision}f}%")
    print(f"* Growth rate: "
          f"{float(backtest_report.growth_rate):.{precision}f}%")
    print(f"* Growth {backtest_report.growth:.{precision}f} "
          f"{backtest_report.trading_symbol}")

    if show_positions:
        print("====================Positions overview========================")
        position_table = {}
        position_table["Position"] = [
            position.symbol for position in backtest_report.positions
        ]
        position_table["Amount"] = [
            f"{position.amount:.{precision}f}" for position in
            backtest_report.positions
        ]
        position_table["Pending buy amount"] = [
            f"{position.amount_pending_buy:.{precision}f}"
            for position in backtest_report.positions
        ]
        position_table["Pending sell amount"] = [
            f"{position.amount_pending_sell:.{precision}f}"
            for position in backtest_report.positions
        ]
        position_table[f"Cost ({backtest_report.trading_symbol})"] = [
            f"{position.cost:.{precision}f}"
            for position in backtest_report.positions
        ]
        position_table[f"Value ({backtest_report.trading_symbol})"] = [
            f"{position.value:.{precision}f}"
            for position in backtest_report.positions
        ]
        position_table["Percentage of portfolio"] = [
            f"{position.percentage_of_portfolio:.{precision}f}%"
            for position in backtest_report.positions
        ]
        position_table[f"Growth ({backtest_report.trading_symbol})"] = [
            f"{position.growth:.{precision}f}"
            for position in backtest_report.positions
        ]
        position_table["Growth_rate"] = [
            f"{position.growth_rate:.{precision}f}%"
            for position in backtest_report.positions
        ]
        print(
            tabulate(position_table, headers="keys", tablefmt="rounded_grid")
        )

    if show_trades:
        print("====================Trades overview===========================")
        print(f"* Number of trades closed: "
              f"{backtest_report.number_of_trades_closed}")
        print(
            f"* Number of trades open: "
            f"{backtest_report.number_of_trades_open}"
        )
        print(f"* Percentage of positive trades: "
              f"{backtest_report.percentage_positive_trades}%")
        print(f"* Percentage of negative trades: "
              f"{backtest_report.percentage_negative_trades}%")
        print(f"* Average trade size: "
              f"{backtest_report.average_trade_size:.{precision}f} "
              f"{backtest_report.trading_symbol}")
        print(f"* Average trade duration: "
              f"{backtest_report.average_trade_duration} hours")
        trades_table = {}
        trades_table["Pair"] = [
            f"{trade.target_symbol}-{trade.trading_symbol}"
            for trade in backtest_report.trades
        ]
        trades_table["Open date"] = [
            trade.opened_at for trade in backtest_report.trades
        ]
        trades_table["Close date"] = [
            trade.closed_at for trade in backtest_report.trades
        ]
        trades_table["Duration (hours)"] = [
            trade.duration for trade in backtest_report.trades
        ]
        trades_table[f"Size ({backtest_report.trading_symbol})"] = [
            f"{trade.size:.{precision}f}" for trade in backtest_report.trades
        ]
        trades_table[f"Net gain ({backtest_report.trading_symbol})"] = [
            f"{trade.net_gain:.{precision}f}"
            for trade in backtest_report.trades
        ]
        trades_table["Net gain percentage"] = [
            f"{trade.net_gain_percentage:.{precision}f}%"
            for trade in backtest_report.trades
        ]
        trades_table[f"Open price ({backtest_report.trading_symbol})"] = [
            trade.open_price for trade in backtest_report.trades
        ]
        trades_table[f"Close price ({backtest_report.trading_symbol})"] = [
            trade.closed_price for trade in backtest_report.trades
        ]
        print(tabulate(trades_table, headers="keys", tablefmt="rounded_grid"))
    print("==================================================================")


def load_backtest_reports(folder_path: str) -> List[BacktestReport]:
    """
    Load backtest reports from a folder.

    param folder_path: The folder path
    :return: The backtest reports
    """
    backtest_reports = []

    if not os.path.exists(folder_path):
        raise OperationalException(f"Folder {folder_path} does not exist")

    list_of_files = os.listdir(folder_path)

    if not list_of_files:
        raise OperationalException(f"Folder {folder_path} is empty")

    for file in list_of_files:
        if not file.endswith(".csv"):
            continue
        file_path = os.path.join(folder_path, file)
        data = load_csv_into_dict(file_path)
        report = BacktestReport.from_dict(data)
        backtest_reports.append(report)

    return backtest_reports
