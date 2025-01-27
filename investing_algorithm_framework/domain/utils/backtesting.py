import os
import re
import json
from datetime import datetime
from typing import List

from tabulate import tabulate

from investing_algorithm_framework.domain import DATETIME_FORMAT, \
    BacktestDateRange, TradeStatus
from investing_algorithm_framework.domain.exceptions import \
    OperationalException
from investing_algorithm_framework.domain.models.backtesting import \
    BacktestReportsEvaluation, BacktestReport
from investing_algorithm_framework.domain.constants import \
    DATETIME_FORMAT_BACKTESTING

COLOR_RED = '\033[91m'
COLOR_PURPLE = '\033[95m'
COLOR_RESET = '\033[0m'
COLOR_GREEN = '\033[92m'
COLOR_YELLOW = '\033[93m'
BACKTEST_REPORT_FILE_NAME_PATTERN = (
    r"^report_\w+_backtest-start-date_\d{4}-\d{2}-\d{2}:\d{2}:\d{2}_"
    r"backtest-end-date_\d{4}-\d{2}-\d{2}:\d{2}:\d{2}_"
    r"created-at_\d{4}-\d{2}-\d{2}:\d{2}:\d{2}\.json$"
)

def is_positive(number) -> bool:
    """
    Check if a number is positive.

    param number: The number
    :return: True if the number is positive, False otherwise
    """
    number = float(number)
    return number > 0


def pretty_print_profit_evaluation(reports, precision=4):
    profit_table = {}
    profit_table["Algorithm name"] = [
        report.name for report in reports
    ]
    profit_table["Profit"] = [
        f"{float(report.total_net_gain):.{precision}f} {report.trading_symbol}"
        for report in reports
    ]
    profit_table["Profit percentage"] = [
        f"{float(report.total_net_gain_percentage):.{precision}f}%" for report in reports
    ]
    profit_table["Percentage positive trades"] = [
        f"{float(report.percentage_positive_trades):.{0}f}%"
        for report in reports
    ]
    profit_table["Date range"] = [
        f"{report.backtest_date_range.name} {report.backtest_date_range.start_date} - {report.backtest_date_range.end_date}"
        for report in reports
    ]
    profit_table["Total value"] = [
        f"{float(report.total_value):.{precision}f}" for report in reports
    ]
    print(tabulate(profit_table, headers="keys", tablefmt="rounded_grid"))


def pretty_print_growth_evaluation(reports, precision=4):
    growth_table = {}
    growth_table["Algorithm name"] = [
        report.name for report in reports
    ]
    growth_table["Growth"] = [
        f"{float(report.growth):.{precision}f} {report.trading_symbol}" for report in reports
    ]
    growth_table["Growth percentage"] = [
        f"{float(report.growth_rate):.{precision}f}%" for report in reports
    ]
    growth_table["Percentage positive trades"] = [
        f"{float(report.percentage_positive_trades):.{0}f}%"
        for report in reports
    ]
    growth_table["Date range"] = [
        f"{report.backtest_date_range.name} {report.backtest_date_range.start_date} - {report.backtest_date_range.end_date}"
        for report in reports
    ]
    growth_table["Total value"] = [
        f"{float(report.total_value):.{precision}f}" for report in reports
    ]
    print(
        tabulate(growth_table, headers="keys", tablefmt="rounded_grid")
    )

def pretty_print_percentage_positive_trades_evaluation(
    evaluation: BacktestReportsEvaluation,
    backtest_date_range: BacktestDateRange,
    precision=0,
    number_of_reports=3
):
    order = evaluation.get_percentage_positive_trades_order(backtest_date_range=backtest_date_range)
    print(f"{COLOR_YELLOW}Trades:{COLOR_RESET} {COLOR_GREEN}Top {number_of_reports}{COLOR_RESET}")
    profit_table = {}
    profit_table["Algorithm name"] = [
        report.name for report in order[:number_of_reports]
    ]
    profit_table["Percentage positive trades"] = [
        f"{float(report.percentage_positive_trades):.{precision}f}%"
        for report in order[:number_of_reports]
    ]
    profit_table["Total amount of trades"] = [
        f"{report.number_of_trades_closed}" for report in order[:number_of_reports]
    ]
    print(
        tabulate(profit_table, headers="keys", tablefmt="rounded_grid")
    )

    least = order[-number_of_reports:]
    table = {}
    table["Algorithm name"] = [
        report.name for report in least
    ]
    table["Percentage positive trades"] = [
        f"{float(report.percentage_positive_trades):.{precision}f}%"
        for report in least
    ]
    table["Total amount of trades"] = [
        f"{report.number_of_trades_closed}" for report in
        least
    ]

    print(
        f"{COLOR_RED}Worst trades:{COLOR_RESET} {COLOR_GREEN}"
        f"Top {number_of_reports}{COLOR_RESET}"
    )
    print(
        tabulate(
            table, headers="keys", tablefmt="rounded_grid"
        )
    )


def pretty_print_date_ranges(date_ranges: List[BacktestDateRange]) -> None:
    """
    Pretty print the date ranges to the console.

    param date_ranges: The date ranges
    """
    print(f"{COLOR_YELLOW}Date ranges of backtests:{COLOR_RESET}")
    for date_range in date_ranges:
        start_date = date_range.start_date
        end_date = date_range.end_date

        if isinstance(start_date, datetime):
            start_date = start_date.strftime(DATETIME_FORMAT)

        if isinstance(end_date, datetime):
            end_date = end_date.strftime(DATETIME_FORMAT)

        if date_range.name is not None:
            print(f"{COLOR_GREEN}{date_range.name}: {start_date} - {end_date}{COLOR_RESET}")
        else:
            print(f"{COLOR_GREEN}{start_date} - {end_date}{COLOR_RESET}")


def pretty_print_price_efficiency(reports, precision=4):
    """
    Pretty print the price efficiency of the backtest reports evaluation
    to the console.
    """
    # Get all symbols of the reports
    print(f"{COLOR_YELLOW}Price noise{COLOR_RESET}")
    rows = []

    for report in reports:

        if report.metrics is not None and "efficiency_ratio" in report.metrics:
            price_efficiency = report.metrics["efficiency_ratio"]

            for symbol in price_efficiency:
                row = {}
                row["Symbol"] = symbol
                row["Efficiency ratio / Noise"] = f"{float(price_efficiency[symbol]):.{precision}f}"
                row["Date"] = f"{report.backtest_start_date} - {report.backtest_end_date}"




                if report.backtest_date_range.name is not None:
                    row["Date"] = f"{report.backtest_date_range.name} " \
                                  f"{report.backtest_date_range.start_date}" \
                                  f" - {report.backtest_date_range.end_date}"
                else:
                    row["Date"] = f"{report.backtest_start_date} - " \
                                   f"{report.backtest_end_date}"

                rows.append(row)

    # Remove all duplicate rows with the same symbol and date range
    unique_rows = []

    # Initialize an empty set to track unique (symbol, date) pairs
    seen = set()
    # Initialize a list to store the filtered dictionaries
    filtered_data = []

    # Iterate through each dictionary in the list
    for entry in rows:
        # Extract the (symbol, date) pair
        pair = (entry["Symbol"], entry["Date"])
        # Check if the pair is already in the set
        if pair not in seen:
            # If not, add the pair to the set and
            # the entry to the filtered list
            seen.add(pair)
            filtered_data.append(entry)

    print(
        tabulate(
            filtered_data,
            headers="keys",
            tablefmt="rounded_grid"
        )
    )


def pretty_print_most_profitable(
    evaluation: BacktestReportsEvaluation,
    backtest_date_range: BacktestDateRange,
    precision=4,
):
    profits = evaluation.get_profit_order(backtest_date_range=backtest_date_range)
    profit = profits[0]
    print(f"{COLOR_YELLOW}Most profitable:{COLOR_RESET} {COLOR_GREEN}Algorithm {profit.name} {float(profit.total_net_gain):.{precision}f} {profit.trading_symbol} {float(profit.total_net_gain_percentage):.{precision}f}%{COLOR_RESET}")


def pretty_print_most_growth(
    evaluation: BacktestReportsEvaluation,
    backtest_date_range: BacktestDateRange,
    precision=4,
):
    profits = evaluation.get_growth_order(backtest_date_range=backtest_date_range)
    profit = profits[0]
    print(f"{COLOR_YELLOW}Most growth:{COLOR_RESET} {COLOR_GREEN}Algorithm {profit.name} {float(profit.growth):.{precision}f} {profit.trading_symbol} {float(profit.growth_rate):.{precision}f}%{COLOR_RESET}")


def pretty_print_percentage_positive_trades(
    evaluation: BacktestReportsEvaluation,
    backtest_date_range: BacktestDateRange,
    precision=0
):
    percentages = evaluation.get_percentage_positive_trades_order(backtest_date_range=backtest_date_range)
    percentages = percentages[0]
    print(f"{COLOR_YELLOW}Most positive trades:{COLOR_RESET} {COLOR_GREEN}Algorithm {percentages.name} {float(percentages.percentage_positive_trades):.{precision}f}%{COLOR_RESET}")


def pretty_print_trades(backtest_report, precision=4):
    print(f"{COLOR_YELLOW}Trades overview{COLOR_RESET}")
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
        f"{float(trade.size):.{precision}f}" for trade in backtest_report.trades
    ]
    trades_table[f"Net gain ({backtest_report.trading_symbol})"] = [
        f"{float(trade.net_gain):.{precision}f}" + (" (unrealized)" if trade.closed_price is None else "")
        for trade in backtest_report.trades
    ]
    trades_table["Net gain percentage"] = [
        f"{float(trade.net_gain_percentage):.{precision}f}%" + (" (unrealized)" if trade.closed_price is None else "")
        for trade in backtest_report.trades
    ]
    trades_table[f"Open price ({backtest_report.trading_symbol})"] = [
        trade.open_price for trade in backtest_report.trades
    ]
    trades_table[f"Close price ({backtest_report.trading_symbol})"] = [
        trade.closed_price for trade in backtest_report.trades
    ]
    print(tabulate(trades_table, headers="keys", tablefmt="rounded_grid"))


def pretty_print_backtest_reports_evaluation(
    backtest_reports_evaluation: BacktestReportsEvaluation,
    precision=4,
    backtest_date_range: BacktestDateRange = None
) -> None:
    """
    Pretty print the backtest reports evaluation to the console.
    """
    if backtest_date_range is not None:
        reports = backtest_reports_evaluation.get_reports(backtest_date_range=backtest_date_range)

        if len(reports) == 0:
            print(f"No reports available for date range {backtest_date_range}")
            return
    else:
        reports = backtest_reports_evaluation.backtest_reports

    number_of_backtest_reports = len(reports)
    most_profitable = backtest_reports_evaluation.get_profit_order(backtest_date_range)[0]
    most_growth = backtest_reports_evaluation.get_growth_order(backtest_date_range)[0]

    ascii_art = f"""
              :%%%#+-          .=*#%%%      {COLOR_GREEN}Backtest reports evaluation{COLOR_RESET}
              *%%%%%%%+------=*%%%%%%%-     {COLOR_GREEN}---------------------------{COLOR_RESET}
              *%%%%%%%%%%%%%%%%%%%%%%%-     {COLOR_YELLOW}Number of reports:{COLOR_RESET} {COLOR_GREEN}{number_of_backtest_reports} backtest reports{COLOR_RESET}
              .%%%%%%%%%%%%%%%%%%%%%%#      {COLOR_YELLOW}Largest overall profit:{COLOR_RESET}{COLOR_GREEN}{COLOR_RESET}{COLOR_GREEN} (Algorithm {most_profitable.name}) {float(most_profitable.total_net_gain):.{precision}f} {most_profitable.trading_symbol} {float(most_profitable.total_net_gain_percentage):.{precision}f}% ({most_profitable.backtest_date_range.name} {most_profitable.backtest_date_range.start_date} - {most_profitable.backtest_date_range.end_date}){COLOR_RESET}
               #%%%####%%%%%%%%**#%%%+      {COLOR_YELLOW}Largest overall growth:{COLOR_RESET}{COLOR_GREEN} (Algorithm {most_profitable.name}) {float(most_growth.growth):.{precision}f} {most_growth.trading_symbol} {float(most_growth.growth_rate):.{precision}f}% ({most_growth.backtest_date_range.name} {most_growth.backtest_date_range.start_date} - {most_growth.backtest_date_range.end_date}){COLOR_RESET}
         .:-+*%%%%- {COLOR_PURPLE}-+..#{COLOR_RESET}%%%+.{COLOR_PURPLE}+-  +{COLOR_RESET}%%%#*=-:
          .:-=*%%%%. {COLOR_PURPLE}+={COLOR_RESET} .%%#  {COLOR_PURPLE}-+.-{COLOR_RESET}%%%%=-:..
          .:=+#%%%%%*###%%%%#*+#%%%%%%*+-:
                +%%%%%%%%%%%%%%%%%%%=
            :++  .=#%%%%%%%%%%%%%*-
           :++:      :+%%%%%%#-.
          :++:        .%%%%%#=
         :++:        .#%%%%%#*=
        :++-        :%%%%%%%%%+=
       .++-        -%%%%%%%%%%%+=
      .++-        .%%%%%%%%%%%%%+=
     .++-         *%%%%%%%%%%%%%*+:
    .++-          %%%%%%%%%%%%%%#+=
    =++........:::%%%%%%%%%%%%%%*+-
    .=++++++++++**#%%%%%%%%%%%%%++.
    """

    if len(backtest_reports_evaluation.backtest_reports) == 0:
        print("No backtest reports available in your evaluation")
        return

    print(ascii_art)
    if backtest_date_range is None:
        pretty_print_date_ranges(backtest_reports_evaluation.get_date_ranges())
        print("")

    pretty_print_price_efficiency(reports, precision=precision)
    print(f"{COLOR_YELLOW}All profits ordered{COLOR_RESET}")
    pretty_print_profit_evaluation(
        backtest_reports_evaluation.get_profit_order(backtest_date_range), precision
    )
    print(f"{COLOR_YELLOW}All growths ordered{COLOR_RESET}")
    pretty_print_growth_evaluation(
        backtest_reports_evaluation.get_growth_order(backtest_date_range), precision
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

    ascii_art = f"""
                  :%%%#+-          .=*#%%%        {COLOR_GREEN}Backtest report{COLOR_RESET}
                  *%%%%%%%+------=*%%%%%%%-       {COLOR_GREEN}---------------------------{COLOR_RESET}
                  *%%%%%%%%%%%%%%%%%%%%%%%-       {COLOR_YELLOW}Start date:{COLOR_RESET}{COLOR_GREEN} {backtest_report.backtest_start_date}{COLOR_RESET}
                  .%%%%%%%%%%%%%%%%%%%%%%#        {COLOR_YELLOW}End date:{COLOR_RESET}{COLOR_GREEN} {backtest_report.backtest_end_date}{COLOR_RESET}
                   #%%%####%%%%%%%%**#%%%+        {COLOR_YELLOW}Number of days:{COLOR_RESET}{COLOR_GREEN}{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_days}{COLOR_RESET}
             .:-+*%%%%- {COLOR_PURPLE}-+..#{COLOR_RESET}%%%+.{COLOR_PURPLE}+-  +{COLOR_RESET}%%%#*=-:   {COLOR_YELLOW}Number of runs:{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_runs}{COLOR_RESET}
              .:-=*%%%%. {COLOR_PURPLE}+={COLOR_RESET} .%%#  {COLOR_PURPLE}-+.-{COLOR_RESET}%%%%=-:..   {COLOR_YELLOW}Number of orders:{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_orders}{COLOR_RESET}
              .:=+#%%%%%*###%%%%#*+#%%%%%%*+-:    {COLOR_YELLOW}Initial balance:{COLOR_RESET}{COLOR_GREEN} {backtest_report.initial_unallocated}{COLOR_RESET}
                    +%%%%%%%%%%%%%%%%%%%=         {COLOR_YELLOW}Final balance:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.total_value):.{precision}f}{COLOR_RESET}
                :++  .=#%%%%%%%%%%%%%*-           {COLOR_YELLOW}Total net gain:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.total_net_gain):.{precision}f} {float(backtest_report.total_net_gain_percentage):.{precision}}%{COLOR_RESET}
               :++:      :+%%%%%%#-.              {COLOR_YELLOW}Growth:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.growth):.{precision}f} {float(backtest_report.growth_rate):.{precision}}%{COLOR_RESET}
              :++:        .%%%%%#=                {COLOR_YELLOW}Number of trades closed:{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_trades_closed}{COLOR_RESET}
             :++:        .#%%%%%#*=               {COLOR_YELLOW}Number of trades open(end of backtest):{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_trades_open}{COLOR_RESET}
            :++-        :%%%%%%%%%+=              {COLOR_YELLOW}Percentage positive trades:{COLOR_RESET}{COLOR_GREEN} {backtest_report.percentage_positive_trades}%{COLOR_RESET}
           .++-        -%%%%%%%%%%%+=             {COLOR_YELLOW}Percentage negative trades:{COLOR_RESET}{COLOR_GREEN} {backtest_report.percentage_negative_trades}%{COLOR_RESET}
          .++-        .%%%%%%%%%%%%%+=            {COLOR_YELLOW}Average trade size:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.average_trade_size):.{precision}f} {backtest_report.trading_symbol}{COLOR_RESET}
         .++-         *%%%%%%%%%%%%%*+:           {COLOR_YELLOW}Average trade duration:{COLOR_RESET}{COLOR_GREEN} {backtest_report.average_trade_duration} hours{COLOR_RESET}
        .++-          %%%%%%%%%%%%%%#+=
        =++........:::%%%%%%%%%%%%%%*+-
        .=++++++++++**#%%%%%%%%%%%%%++.
        """

    print(ascii_art)
    # pretty_print_price_efficiency([backtest_report], precision=precision)

    if show_positions:
        print(f"{COLOR_YELLOW}Positions overview{COLOR_RESET}")
        position_table = {}
        position_table["Position"] = [
            position.symbol for position in backtest_report.positions
        ]
        position_table["Amount"] = [
            f"{float(position.amount):.{precision}f}" for position in
            backtest_report.positions
        ]
        position_table["Pending buy amount"] = [
            f"{float(position.amount_pending_buy):.{precision}f}"
            for position in backtest_report.positions
        ]
        position_table["Pending sell amount"] = [
            f"{float(position.amount_pending_sell):.{precision}f}"
            for position in backtest_report.positions
        ]
        position_table[f"Cost ({backtest_report.trading_symbol})"] = [
            f"{float(position.cost):.{precision}f}"
            for position in backtest_report.positions
        ]
        position_table[f"Value ({backtest_report.trading_symbol})"] = [
            f"{float(position.value):.{precision}f}"
            for position in backtest_report.positions
        ]
        position_table["Percentage of portfolio"] = [
            f"{float(position.percentage_of_portfolio):.{precision}f}%"
            for position in backtest_report.positions
        ]
        position_table[f"Growth ({backtest_report.trading_symbol})"] = [
            f"{float(position.growth):.{precision}f}"
            for position in backtest_report.positions
        ]
        position_table["Growth_rate"] = [
            f"{float(position.growth_rate):.{precision}f}%"
            for position in backtest_report.positions
        ]
        print(
            tabulate(position_table, headers="keys", tablefmt="rounded_grid")
        )

    if show_trades:
        print(f"{COLOR_YELLOW}Trades overview{COLOR_RESET}")
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
        trades_table[f"Cost ({backtest_report.trading_symbol})"] = [
            f"{float(trade.cost):.{precision}f}" for trade in backtest_report.trades
        ]
        trades_table[f"Net gain ({backtest_report.trading_symbol})"] = [
            f"{float(trade.net_gain):.{precision}f}"
            for trade in backtest_report.trades
        ]

        # Add (unrealized) to the net gain if the trade is still open
        trades_table[f"Net gain ({backtest_report.trading_symbol})"] = [
            f"{float(trade.net_gain_absolute):.{precision}f}" + (" (unrealized)" if not TradeStatus.CLOSED.equals(trade.status) else "")
            for trade in backtest_report.trades
        ]
        trades_table["Net gain percentage"] = [
            f"{float(trade.net_gain_percentage):.{precision}f}%" + (" (unrealized)" if not TradeStatus.CLOSED.equals(trade.status) else "")
            for trade in backtest_report.trades
        ]
        trades_table[f"Open price ({backtest_report.trading_symbol})"] = [
            trade.open_price for trade in backtest_report.trades
        ]
        trades_table[
            f"Last reported price ({backtest_report.trading_symbol})"
        ] = [
            trade.last_reported_price for trade in backtest_report.trades
        ]
        trades_table["Stop loss triggered"] = [
            trade.stop_loss_triggered for trade in backtest_report.trades
        ]
        print(tabulate(trades_table, headers="keys", tablefmt="rounded_grid"))


def load_backtest_report(file_path: str) -> BacktestReport:
    """
    Load a backtest report from a file.

    param file_path: The file path
    :return: The backtest report
    """

    if not os.path.isfile(file_path):
        raise OperationalException("File does not exist")

    if not file_path.endswith(".json"):
        raise OperationalException("File is not a json file")

    with open(file_path, 'r') as json_file:
        data = json.load(json_file)

    return BacktestReport.from_dict(data)


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
        if not file.endswith(".json"):
            continue
        file_path = os.path.join(folder_path, file)
        report = load_backtest_report(file_path)
        backtest_reports.append(report)

    return backtest_reports


def get_backtest_report(
    directory: str,
    algorithm_name: str,
    backtest_date_range: BacktestDateRange=None
) -> BacktestReport:
    """
    Function to get a report based on the algorithm name and
    backtest date range if it exists.

    Args:
        algorithm_name (str): The name of the algorithm
        backtest_date_range (BacktestDateRange): The backtest date range
        directory (str): The output directory

    Returns:
        BacktestReport: The backtest report if it exists, otherwise None
    """

    # Loop through all files in the output directory
    for root, _, files in os.walk(directory):
        for file in files:
            # Check if the file contains the algorithm name
            # and backtest date range
            if is_backtest_report(os.path.join(root, file)):
                # Read the file
                with open(os.path.join(root, file), "r") as json_file:

                    name = \
                        get_algorithm_name_from_backtest_report_file(
                            os.path.join(root, file)
                        )

                    if name == algorithm_name:

                        if backtest_date_range is None:
                            # Parse the JSON file
                            report = json.load(json_file)
                            # Convert the JSON file to a
                            # BacktestReport object
                            return BacktestReport.from_dict(report)

                        backtest_start_date = \
                            get_start_date_from_backtest_report_file(
                                os.path.join(root, file)
                            )
                        backtest_end_date = \
                            get_end_date_from_backtest_report_file(
                                os.path.join(root, file)
                            )

                        if backtest_start_date == \
                                backtest_date_range.start_date \
                                and backtest_end_date == \
                                backtest_date_range.end_date:
                            # Parse the JSON file
                            report = json.load(json_file)
                            # Convert the JSON file to a
                            # BacktestReport object
                            return BacktestReport.from_dict(report)

    return None


def get_start_date_from_backtest_report_file(path: str) -> datetime:
    """
    Function to get the backtest start date from a backtest report file.

    Parameters:
        path (str): The path to the backtest report file

    Returns:
        datetime: The backtest start date
    """

    # Get the backtest start date from the file name
    backtest_start_date = os.path.basename(path).split("_")[3]
    # Parse the backtest start date
    return datetime.strptime(
        backtest_start_date, DATETIME_FORMAT_BACKTESTING
    )


def get_end_date_from_backtest_report_file(path: str) -> datetime:
    """
    Function to get the backtest end date from a backtest report file.

    Parameters:
        path (str): The path to the backtest report file

    Returns:
        datetime: The backtest end date
    """

    # Get the backtest end date from the file name
    backtest_end_date = os.path.basename(path).split("_")[5]
    # Parse the backtest end date
    return datetime.strptime(
        backtest_end_date, DATETIME_FORMAT_BACKTESTING
    )


def get_algorithm_name_from_backtest_report_file(path: str) -> str:
    """
    Function to get the algorithm name from a backtest report file.

    Parameters:
        path (str): The path to the backtest report file

    Returns:
        str: The algorithm name
    """
    # Get the word between "report_" and "_backtest_start_date"
    # it can contain _
    # Get the algorithm name from the file name
    algorithm_name = os.path.basename(path).split("_")[1]
    return algorithm_name


def is_backtest_report(path: str) -> bool:
    """
    Function to check if a file is a backtest report file.

    Args:
        path (str): The path to the file

    Returns:
        bool: True if the file is a backtest report file, otherwise False
    """

    # Check if the file is a JSON file
    if path.endswith(".json"):

        # Check if the file name matches the backtest
        # report file name pattern
        if re.match(
            BACKTEST_REPORT_FILE_NAME_PATTERN, os.path.basename(path)
        ):
            return True

    return False
