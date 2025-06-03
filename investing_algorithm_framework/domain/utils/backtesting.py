import os
import re
import json
from datetime import datetime
from typing import List, Optional

from tabulate import tabulate

from investing_algorithm_framework.domain import DATETIME_FORMAT, \
    BacktestDateRange, TradeStatus, OrderSide, TradeRiskType
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

def format_date(date) -> str:
    """
    Format the date to the format YYYY-MM-DD HH:MM:SS
    """

    if date is None:
        return ""

    if isinstance(date, datetime):
        return date.strftime("%Y-%m-%d %H:%M")
    else:
        date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
        return date.strftime("%Y-%m-%d %H:%M")

def is_positive(number) -> bool:
    """
    Check if a number is positive.

    param number: The number
    :return: True if the number is positive, False otherwise
    """
    number = float(number)
    return number > 0


def pretty_print_profit_evaluation(
    reports, price_precision=2, percentage_precision=4
):
    profit_table = {}
    profit_table["Algorithm name"] = [
        report.name for report in reports
    ]
    profit_table["Profit"] = [
        f"{float(report.total_net_gain):.{price_precision}f} {report.trading_symbol}"
        for report in reports
    ]
    profit_table["Profit percentage"] = [
        f"{float(report.total_net_gain_percentage):.{percentage_precision}f}%" for report in reports
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
        f"{float(report.total_value):.{price_precision}f}" for report in reports
    ]
    print(tabulate(profit_table, headers="keys", tablefmt="rounded_grid"))


def pretty_print_growth_evaluation(
    reports,
    price_precision=2,
    percentage_precision=4
):
    growth_table = {}
    growth_table["Algorithm name"] = [
        report.name for report in reports
    ]
    growth_table["Growth"] = [
        f"{float(report.growth):.{price_precision}f} {report.trading_symbol}" for report in reports
    ]
    growth_table["Growth percentage"] = [
        f"{float(report.growth_rate):.{percentage_precision}f}%" for report in reports
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
        f"{float(report.total_value):.{price_precision}f}" for report in reports
    ]
    print(
        tabulate(growth_table, headers="keys", tablefmt="rounded_grid")
    )

def pretty_print_stop_losses(
    backtest_report,
    triggered_only=False,
    amount_precesion=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=0
):
    print(f"{COLOR_YELLOW}Stop losses overview{COLOR_RESET}")
    stop_loss_table = {}
    trades = backtest_report.trades
    selection = []

    def get_sold_amount(stop_loss):
        if stop_loss["sold_amount"] > 0:
            return f"{float(stop_loss['sold_amount']):.{amount_precesion}f} {stop_loss['target_symbol']}"

        return ""

    def get_status(stop_loss):

        if stop_loss.sold_amount == 0:
            return "NOT TRIGGERED"

        if stop_loss.sold_amount == stop_loss.sell_amount:
            return "TRIGGERED"

        if stop_loss.sold_amount < stop_loss.sell_amount:
            return "PARTIALLY TRIGGERED"

    def get_high_water_mark(stop_loss):
        if stop_loss["high_water_mark"] is not None:
            return f"{float(stop_loss['high_water_mark']):.{price_precision}f} {stop_loss['trading_symbol']} {format_date(stop_loss['high_water_mark_date'])}"

        return ""

    def get_stop_loss_price(take_profit):

        if TradeRiskType.TRAILING.equals(take_profit["trade_risk_type"]):
            initial_price = take_profit["open_price"]
            percentage = take_profit["percentage"]
            initial_stop_loss_price = \
                initial_price * (1 - (percentage / 100))
            return f"{float(take_profit['stop_loss_price']):.{price_precision}f} ({(initial_stop_loss_price):.{price_precision}f}) ({take_profit['percentage']})% {take_profit['trading_symbol']}"
        else:
            return f"{float(take_profit['stop_loss_price']):.{price_precision}f}({take_profit['percentage']})% {take_profit['trading_symbol']}"

    if triggered_only:
        for trade in trades:

            if trade.stop_losses is not None:
                selection += [
                    {
                        "symbol": trade.symbol,
                        "target_symbol": trade.target_symbol,
                        "trading_symbol": trade.trading_symbol,
                        "status": get_status(stop_loss),
                        "trade_id": stop_loss.trade_id,
                        "trade_risk_type": stop_loss.trade_risk_type,
                        "percentage": stop_loss.percentage,
                        "open_price": stop_loss.open_price,
                        "sell_percentage": stop_loss.sell_percentage,
                        "high_water_mark": stop_loss.high_water_mark,
                        "high_water_mark_date": stop_loss.high_water_mark_date,
                        "stop_loss_price": stop_loss.stop_loss_price,
                        "sell_amount": stop_loss.sell_amount,
                        "sold_amount": stop_loss.sold_amount,
                        "active": stop_loss.active,
                        "sell_prices": stop_loss.sell_prices
                    } for stop_loss in trade.stop_losses if stop_loss.sold_amount > 0
                ]
    else:
        for trade in trades:

            if trade.stop_losses is not None:
                for stop_loss in trade.stop_losses:
                    data = {
                        "symbol": trade.symbol,
                        "target_symbol": trade.target_symbol,
                        "trading_symbol": trade.trading_symbol,
                        "status": get_status(stop_loss),
                        "trade_id": stop_loss.trade_id,
                        "trade_risk_type": stop_loss.trade_risk_type,
                        "percentage": stop_loss.percentage,
                        "open_price": stop_loss.open_price,
                        "sell_percentage": stop_loss.sell_percentage,
                        "stop_loss_price": stop_loss.stop_loss_price,
                        "sell_amount": stop_loss.sell_amount,
                        "sold_amount": stop_loss.sold_amount,
                        "active": stop_loss.active,
                    }

                    if hasattr(stop_loss, "sell_prices"):
                        data["sell_prices"] = stop_loss.sell_prices
                    else:
                        data["sell_prices"] = None

                    if hasattr(stop_loss, "high_water_mark"):
                        data["high_water_mark"] = stop_loss.high_water_mark

                        if hasattr(stop_loss, "high_water_mark_date"):
                            data["high_water_mark_date"] = \
                                stop_loss.high_water_mark_date
                        else:
                            data["high_water_mark_date"] = None
                    else:
                        data["high_water_mark"] = None
                        data["high_water_mark_date"] = None
                    selection.append(data)

    stop_loss_table["Trade (Trade id)"] = [
        f"{stop_loss['symbol'] + ' (' + str(stop_loss['trade_id']) + ')'}"
        for stop_loss in selection
    ]
    stop_loss_table["Status"] = [
        f"{stop_loss['status']}"
        for stop_loss in selection
    ]
    stop_loss_table["Active"] = [
        f"{stop_loss['active']}"
        for stop_loss in selection
    ]
    stop_loss_table["Type"] = [
        f"{stop_loss['trade_risk_type']}" for stop_loss in selection
    ]
    stop_loss_table["Stop Loss (Initial Stop Loss)"] = [
        get_stop_loss_price(stop_loss) for stop_loss in selection
    ]
    stop_loss_table["Open price"] = [
        f"{float(stop_loss['open_price']):.{price_precision}f} {stop_loss['trading_symbol']}" for stop_loss in selection if stop_loss['open_price'] is not None
    ]
    stop_loss_table["Sell price's"] = [
        f"{stop_loss['sell_prices']}" for stop_loss in selection if stop_loss['sell_prices'] is not None
    ]
    stop_loss_table["High water mark"] = [
        f"{get_high_water_mark(stop_loss)}" for stop_loss in selection
    ]
    stop_loss_table["Percentage"] = [
        f"{float(stop_loss['sell_percentage'])}%" for stop_loss in selection
    ]
    stop_loss_table["Size"] = [
        f"{float(stop_loss['sell_amount']):.{price_precision}f} {stop_loss['target_symbol']}" for stop_loss in selection
    ]
    stop_loss_table["Sold amount"] = [
        get_sold_amount(stop_loss) for stop_loss in selection
    ]
    print(tabulate(stop_loss_table, headers="keys", tablefmt="rounded_grid"))


def pretty_print_take_profits(
    backtest_report,
    triggered_only=False,
    amount_precesion=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=0
):
    print(f"{COLOR_YELLOW}Take profits overview{COLOR_RESET}")
    take_profit_table = {}
    trades = backtest_report.trades
    selection = []

    def get_high_water_mark(take_profit):
        if take_profit["high_water_mark"] is not None:
            return f"{float(take_profit['high_water_mark']):.{price_precision}f} {take_profit['trading_symbol']} ({format_date(take_profit['high_water_mark_date'])})"

        return ""

    def get_sold_amount(take_profit):
        if take_profit["sold_amount"] > 0:
            return f"{float(take_profit['sold_amount']):.{amount_precesion}f} {take_profit['target_symbol']}"

        return ""

    def get_take_profit_price(take_profit):

        if TradeRiskType.TRAILING.equals(take_profit["trade_risk_type"]):
            initial_price = take_profit["open_price"]
            percentage = take_profit["percentage"]
            initial_take_profit_price = \
                initial_price * (1 + (percentage / 100))
            return f"{float(take_profit['take_profit_price']):.{price_precision}f} ({(initial_take_profit_price):.{price_precision}f}) ({take_profit['percentage']})% {take_profit['trading_symbol']}"
        else:
            return f"{float(take_profit['take_profit_price']):.{price_precision}f}({take_profit['percentage']})% {take_profit['trading_symbol']}"

    def get_status(take_profit):

        if take_profit.sold_amount == 0:
            return "NOT TRIGGERED"

        if take_profit.sold_amount == take_profit.sell_amount:
            return "TRIGGERED"

        if take_profit.sold_amount < take_profit.sell_amount:
            return "PARTIALLY TRIGGERED"

    if triggered_only:
        for trade in trades:

            if trade.take_profits is not None:
                selection += [
                    {
                        "symbol": trade.symbol,
                        "target_symbol": trade.target_symbol,
                        "trading_symbol": trade.trading_symbol,
                        "status": get_status(take_profit),
                        "trade_id": take_profit.trade_id,
                        "trade_risk_type": take_profit.trade_risk_type,
                        "percentage": take_profit.percentage,
                        "open_price": take_profit.open_price,
                        "sell_percentage": take_profit.sell_percentage,
                        "high_water_mark": take_profit.high_water_mark,
                        "high_water_mark_date": \
                            take_profit.high_water_mark_date,
                        "take_profit_price": take_profit.take_profit_price,
                        "sell_amount": take_profit.sell_amount,
                        "sold_amount": take_profit.sold_amount,
                        "active": take_profit.active,
                        "sell_prices": take_profit.sell_prices
                    } for take_profit in trade.take_profits if take_profit.sold_amount > 0
                ]
    else:
        for trade in trades:

            if trade.take_profits is not None:

                for take_profit in trade.take_profits:
                    data = {
                        "symbol": trade.symbol,
                        "target_symbol": trade.target_symbol,
                        "trading_symbol": trade.trading_symbol,
                        "status": get_status(take_profit),
                        "trade_id": take_profit.trade_id,
                        "trade_risk_type": take_profit.trade_risk_type,
                        "percentage": take_profit.percentage,
                        "open_price": take_profit.open_price,
                        "sell_percentage": take_profit.sell_percentage,
                        "take_profit_price": take_profit.take_profit_price,
                        "sell_amount": take_profit.sell_amount,
                        "sold_amount": take_profit.sold_amount,
                        "active": take_profit.active
                    }

                    if hasattr(take_profit, "sell_prices"):
                        data["sell_prices"] = take_profit.sell_prices
                    else:
                        data["sell_prices"] = None

                    if hasattr(take_profit, "high_water_mark"):
                        data["high_water_mark"] = take_profit.high_water_mark

                        if hasattr(take_profit, "high_water_mark_date"):
                            data["high_water_mark_date"] = \
                                take_profit.high_water_mark_date
                        else:
                            data["high_water_mark_date"] = None
                    else:
                        data["high_water_mark"] = None
                        data["high_water_mark_date"] = None

                    selection.append(data)

    take_profit_table["Trade (Trade id)"] = [
        f"{stop_loss['symbol'] + ' (' + str(stop_loss['trade_id']) + ')'}"
        for stop_loss in selection
    ]
    take_profit_table["Status"] = [
        f"{stop_loss['status']}"
        for stop_loss in selection
    ]
    take_profit_table["Active"] = [
        f"{stop_loss['active']}"
        for stop_loss in selection
    ]
    take_profit_table["Type"] = [
        f"{stop_loss['trade_risk_type']}" for stop_loss
        in selection
    ]
    take_profit_table["Take profit (Initial Take Profit)"] = [
        get_take_profit_price(stop_loss) for stop_loss in selection
    ]
    take_profit_table["Open price"] = [
        f"{float(stop_loss['open_price']):.{price_precision}f} {stop_loss['trading_symbol']}" for stop_loss in selection if stop_loss['open_price'] is not None
    ]
    take_profit_table["Sell price's"] = [
        f"{stop_loss['sell_prices']}" for stop_loss in selection
    ]
    # Print nothing if high water mark is None
    take_profit_table["High water mark"] = [
        f"{get_high_water_mark(stop_loss)}" for stop_loss in selection
    ]
    take_profit_table["Percentage"] = [
        f"{float(stop_loss['sell_percentage'])}%" for stop_loss in selection
    ]
    take_profit_table["Size"] = [
        f"{float(stop_loss['sell_amount']):.{amount_precesion}f} {stop_loss['target_symbol']}" for stop_loss in selection
    ]
    take_profit_table["Sold amount"] = [
        get_sold_amount(stop_loss) for stop_loss in selection
    ]
    print(tabulate(take_profit_table, headers="keys", tablefmt="rounded_grid"))


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


def pretty_print_orders(
    backtest_report,
    target_symbol = None,
    order_status = None,
    amount_precesion=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=2
) -> None:
    """
    Pretty print the orders of the backtest report to the console.

    Args:
        backtest_report: The backtest report
        target_symbol: The target symbol of the orders
        order_status: The status of the orders
        amount_precesion: The precision of the amount
        price_precision: The precision of the price
        time_precision: The precision of the time
        percentage_precision: The precision of the percentage

    Returns:
        None
    """

    selection = backtest_report.get_orders(
        target_symbol=target_symbol,
        order_status=order_status
    )

    print(f"{COLOR_YELLOW}Orders overview{COLOR_RESET}")
    orders_table = {}
    orders_table["Pair (Order id)"] = [
        f"{order.target_symbol}/{order.trading_symbol} ({order.id})"
        for order in selection
    ]
    orders_table["Status"] = [
        order.status for order in selection
    ]
    orders_table["Side"] = [
        order.order_side for order in selection
    ]
    orders_table["Size"] = [
        f"{float(order.get_size()):.{amount_precesion}f} {order.trading_symbol}"
        for order in selection
    ]
    orders_table["Price"] = [
        f"{float(order.price):.{amount_precesion}f} {order.trading_symbol}"
        for order in selection
    ]
    orders_table["Amount"] = [
        f"{float(order.amount):.{amount_precesion}f} {order.target_symbol}"
        for order in selection
    ]
    orders_table["Filled"] = [
        f"{float(order.filled):.{amount_precesion}f} {order.target_symbol}"
        for order in selection
    ]
    orders_table["Created at"] = [
        order.created_at.strftime("%Y-%m-%d %H:%M") for order in selection if order.created_at is not None
    ]
    print(tabulate(orders_table, headers="keys", tablefmt="rounded_grid"))


def pretty_print_positions(
    backtest_report,
    symbol = None,
    amount_precesion=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=2
) -> None:
    """
    Pretty print the positions of the backtest report to the console.

    Args:
        backtest_report: The backtest report
        target_symbol: The target symbol of the orders
        order_status: The status of the orders
        amount_precesion: The precision of the amount
        price_precision: The precision of the price
        time_precision: The precision of the time
        percentage_precision: The precision of the percentage

    Returns:
        None
    """
    selection = backtest_report.get_positions(symbol=symbol)

    print(f"{COLOR_YELLOW}Positions overview{COLOR_RESET}")
    position_table = {}
    position_table["Position"] = [
        position.symbol for position in selection
    ]
    position_table["Amount"] = [
        f"{float(position.amount):.{amount_precesion}f}" for position in
        selection
    ]
    position_table["Pending buy amount"] = [
        f"{float(position.amount_pending_buy):.{amount_precesion}f}"
        for position in selection
    ]
    position_table["Pending sell amount"] = [
        f"{float(position.amount_pending_sell):.{amount_precesion}f}"
        for position in selection
    ]
    position_table[f"Cost ({backtest_report.trading_symbol})"] = [
        f"{float(position.cost):.{price_precision}f}"
        for position in selection
    ]
    position_table[f"Value ({backtest_report.trading_symbol})"] = [
        f"{float(position.value):.{price_precision}f} {backtest_report.trading_symbol}"
        for position in selection
    ]
    position_table["Percentage of portfolio"] = [
        f"{float(position.percentage_of_portfolio):.{percentage_precision}f}%"
        for position in selection
    ]
    position_table[f"Growth ({backtest_report.trading_symbol})"] = [
        f"{float(position.growth):.{price_precision}f} {backtest_report.trading_symbol}"
        for position in selection
    ]
    position_table["Growth_rate"] = [
        f"{float(position.growth_rate):.{percentage_precision}f}%"
        for position in selection
    ]
    print(
        tabulate(position_table, headers="keys", tablefmt="rounded_grid")
    )


def pretty_print_trades(
    backtest_report,
    target_symbol = None,
    status = None,
    amount_precesion=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=2
):
    """
    Pretty print the trades of the backtest report to the console.

    Args:
        backtest_report: The backtest report
        target_symbol: The target symbol of the trades
        status: The status of the trades
        amount_precesion: The precision of the amount
        price_precision: The precision of the price
        time_precision: The precision of the time
        percentage_precision: The precision of the percentage

    Returns:
        None
    """
    selection = backtest_report.get_trades(
        target_symbol=target_symbol,
        trade_status=status
    )

    def get_status(trade):
        status = "OPEN"

        if TradeStatus.CLOSED.equals(trade.status):
            status = "CLOSED"

        if has_triggered_stop_losses(trade):
            status += ", SL"

        if has_triggered_take_profits(trade):
            status += ", TP"

        return status

    def get_close_prices(trade):

        sell_orders = [
            order for order in trade.orders
            if OrderSide.SELL.equals(order.order_side)
        ]
        text = ""
        number_of_sell_orders = 0

        for sell_order in sell_orders:

            if number_of_sell_orders > 0:
                text += ", "

            text += f"{float(sell_order.price):.{price_precision}f}"
            number_of_sell_orders += 1

        return text

    def has_triggered_take_profits(trade):

        if trade.take_profits is None:
            return False

        triggered = [
            take_profit for take_profit in trade.take_profits if take_profit.sold_amount != 0
        ]

        return len(triggered) > 0

    def has_triggered_stop_losses(trade):

        if trade.stop_losses is None:
            return False

        triggered = [
            stop_loss for stop_loss in trade.stop_losses if stop_loss.sold_amount != 0
        ]
        return len(triggered) > 0

    def get_high_water_mark(trade):
        if trade.high_water_mark is not None:
            return f"{float(trade.high_water_mark):.{price_precision}f} {trade.trading_symbol} ({format_date(trade.high_water_mark_datetime)})"

        return ""

    print(f"{COLOR_YELLOW}Trades overview{COLOR_RESET}")
    trades_table = {}
    trades_table["Pair (Trade id)"] = [
        f"{trade.target_symbol}/{trade.trading_symbol} ({trade.id})"
        for trade in selection
    ]
    trades_table["Status"] = [
        get_status(trade) for trade in selection
    ]
    trades_table["Amount (remaining)"] = [
        f"{float(trade.amount):.{amount_precesion}f} ({float(trade.remaining):.{amount_precesion}f}) {trade.target_symbol}"
        for trade in selection
    ]
    trades_table[f"Net gain ({backtest_report.trading_symbol})"] = [
        f"{float(trade.net_gain):.{price_precision}f}"
        for trade in selection
    ]
    trades_table["Open date"] = [
        trade.opened_at.strftime("%Y-%m-%d %H:%M") for trade in selection if trade.opened_at is not None
    ]
    trades_table["Close date"] = [
        trade.closed_at.strftime("%Y-%m-%d %H:%M") for trade in selection if trade.closed_at is not None
    ]
    trades_table["Duration"] = [
        f"{trade.duration:.{time_precision}f} hours" for trade in selection
    ]
    # Add (unrealized) to the net gain if the trade is still open
    trades_table[f"Net gain ({backtest_report.trading_symbol})"] = [
        f"{float(trade.net_gain_absolute):.{price_precision}f} ({float(trade.net_gain_percentage):.{percentage_precision}f}%)" + (" (unrealized)" if not TradeStatus.CLOSED.equals(trade.status) else "")
        for trade in selection
    ]
    trades_table[f"Open price ({backtest_report.trading_symbol})"] = [
        f"{trade.open_price:.{price_precision}f}"  for trade in selection
    ]
    trades_table[
        f"Close price's ({backtest_report.trading_symbol})"
    ] = [
        get_close_prices(trade) for trade in selection
    ]
    trades_table["High water mark"] = [
        get_high_water_mark(trade) for trade in selection
    ]
    print(tabulate(trades_table, headers="keys", tablefmt="rounded_grid"))


def pretty_print_backtest_reports_evaluation(
    backtest_reports_evaluation: BacktestReportsEvaluation,
    amount_precesion=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=2,
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
              .%%%%%%%%%%%%%%%%%%%%%%#      {COLOR_YELLOW}Largest overall profit:{COLOR_RESET}{COLOR_GREEN}{COLOR_RESET}{COLOR_GREEN} (Algorithm {most_profitable.name}) {float(most_profitable.total_net_gain):.{price_precision}f} {most_profitable.trading_symbol} {float(most_profitable.total_net_gain_percentage):.{percentage_precision}f}% ({most_profitable.backtest_date_range.name} {most_profitable.backtest_date_range.start_date} - {most_profitable.backtest_date_range.end_date}){COLOR_RESET}
               #%%%####%%%%%%%%**#%%%+      {COLOR_YELLOW}Largest overall growth:{COLOR_RESET}{COLOR_GREEN} (Algorithm {most_profitable.name}) {float(most_growth.growth):.{price_precision}f} {most_growth.trading_symbol} {float(most_growth.growth_rate):.{percentage_precision}f}% ({most_growth.backtest_date_range.name} {most_growth.backtest_date_range.start_date} - {most_growth.backtest_date_range.end_date}){COLOR_RESET}
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

    pretty_print_price_efficiency(reports, precision=price_precision)
    print(f"{COLOR_YELLOW}All profits ordered{COLOR_RESET}")
    pretty_print_profit_evaluation(
        backtest_reports_evaluation.get_profit_order(backtest_date_range),
        price_precision=price_precision,
        percentage_precision=percentage_precision
    )
    print(f"{COLOR_YELLOW}All growths ordered{COLOR_RESET}")
    pretty_print_growth_evaluation(
        backtest_reports_evaluation.get_growth_order(backtest_date_range),
        percentage_precision=percentage_precision,
        price_precision=price_precision
    )


def print_number_of_runs(report):

    if report.number_of_runs == 1:

        if report.inteval > 1:
            print(f"Strategy ran every {report.interval} {report.time_unit} "
                  f"for a total of {report.number_of_runs} time")


def pretty_print_backtest(
    backtest_report,
    show_positions=True,
    show_trades=True,
    show_stop_losses=True,
    show_triggered_stop_losses_only=False,
    show_take_profits=True,
    show_triggered_take_profits_only=False,
    amount_precesion=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=2
):
    """
    Pretty print the backtest report to the console.

    Args:
        backtest_report: BacktestReport - the backtest report
        show_positions: bool - show the positions
        show_trades: bool - show the trades
        show_stop_losses: bool - show the stop losses
        show_triggered_stop_losses_only: bool - show only the triggered stop losses
        show_take_profits: bool - show the take profits
        show_triggered_take_profits_only: bool - show only the triggered take profits
        amount_precesion: int - the amount precision
        price_precision: int - the price precision
        time_precision: int - the time precision
        percentage_precision: int - the percentage precision

    Returns:
        None
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
                    +%%%%%%%%%%%%%%%%%%%=         {COLOR_YELLOW}Final balance:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.total_value):.{price_precision}f}{COLOR_RESET}
                :++  .=#%%%%%%%%%%%%%*-           {COLOR_YELLOW}Total net gain:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.total_net_gain):.{price_precision}f} {float(backtest_report.total_net_gain_percentage):.{percentage_precision}f}%{COLOR_RESET}
               :++:      :+%%%%%%#-.              {COLOR_YELLOW}Growth:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.growth):.{price_precision}f} {float(backtest_report.growth_rate):.{percentage_precision}f}%{COLOR_RESET}
              :++:        .%%%%%#=                {COLOR_YELLOW}Number of trades:{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_trades}{COLOR_RESET}
              :++:        .%%%%%#=                {COLOR_YELLOW}Number of trades closed:{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_trades_closed}{COLOR_RESET}
             :++:        .#%%%%%#*=               {COLOR_YELLOW}Number of trades open(end of backtest):{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_trades_open}{COLOR_RESET}
            :++-        :%%%%%%%%%+=              {COLOR_YELLOW}Percentage positive trades:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.percentage_positive_trades):.{percentage_precision}f}%{COLOR_RESET}
           .++-        -%%%%%%%%%%%+=             {COLOR_YELLOW}Percentage negative trades:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.percentage_negative_trades):.{percentage_precision}f}%{COLOR_RESET}
          .++-        .%%%%%%%%%%%%%+=            {COLOR_YELLOW}Average trade size:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.average_trade_size):.{price_precision}f} {backtest_report.trading_symbol}{COLOR_RESET}
         .++-         *%%%%%%%%%%%%%*+:           {COLOR_YELLOW}Average trade duration:{COLOR_RESET}{COLOR_GREEN} {float(backtest_report.average_trade_duration):.{0}f} hours{COLOR_RESET}
        .++-          %%%%%%%%%%%%%%#+=
        =++........:::%%%%%%%%%%%%%%*+-
        .=++++++++++**#%%%%%%%%%%%%%++.
        """

    print(ascii_art)

    if show_positions:
        print(f"{COLOR_YELLOW}Positions overview{COLOR_RESET}")
        position_table = {}
        position_table["Position"] = [
            position.symbol for position in backtest_report.positions
        ]
        position_table["Amount"] = [
            f"{float(position.amount):.{amount_precesion}f}" for position in
            backtest_report.positions
        ]
        position_table["Pending buy amount"] = [
            f"{float(position.amount_pending_buy):.{amount_precesion}f}"
            for position in backtest_report.positions
        ]
        position_table["Pending sell amount"] = [
            f"{float(position.amount_pending_sell):.{amount_precesion}f}"
            for position in backtest_report.positions
        ]
        position_table[f"Cost ({backtest_report.trading_symbol})"] = [
            f"{float(position.cost):.{price_precision}f}"
            for position in backtest_report.positions
        ]
        position_table[f"Value ({backtest_report.trading_symbol})"] = [
            f"{float(position.value):.{price_precision}f} {backtest_report.trading_symbol}"
            for position in backtest_report.positions
        ]
        position_table["Percentage of portfolio"] = [
            f"{float(position.percentage_of_portfolio):.{percentage_precision}f}%"
            for position in backtest_report.positions
        ]
        position_table[f"Growth ({backtest_report.trading_symbol})"] = [
            f"{float(position.growth):.{price_precision}f} {backtest_report.trading_symbol}"
            for position in backtest_report.positions
        ]
        position_table["Growth_rate"] = [
            f"{float(position.growth_rate):.{percentage_precision}f}%"
            for position in backtest_report.positions
        ]
        print(
            tabulate(position_table, headers="keys", tablefmt="rounded_grid")
        )

    def has_triggered_stop_losses(trade):

        if trade.stop_losses is None:
            return False

        triggered = [
            stop_loss for stop_loss in trade.stop_losses if stop_loss.sold_amount != 0
        ]
        return len(triggered) > 0

    if show_trades:
        pretty_print_trades(
            backtest_report,
            amount_precesion=amount_precesion,
            price_precision=price_precision,
            time_precision=time_precision,
            percentage_precision=percentage_precision
        )

    if show_stop_losses:
        pretty_print_stop_losses(
            backtest_report=backtest_report,
            triggered_only=show_triggered_stop_losses_only,
            amount_precesion=amount_precesion,
            price_precision=price_precision,
            time_precision=time_precision,
            percentage_precision=percentage_precision
        )

    if show_take_profits:
        pretty_print_take_profits(
            backtest_report=backtest_report,
            triggered_only=show_triggered_take_profits_only,
            amount_precesion=amount_precesion,
            price_precision=price_precision,
            time_precision=time_precision,
            percentage_precision=percentage_precision
        )


def load_backtest_report(file_path: str) -> BacktestReport:
    """
    Load a backtest report from a file.

    Args:
        file_path (str): The path to the backtest report file or folder

    Returns:
        BacktestReport: The backtest report
    """

    if not os.path.exists(file_path):
        raise OperationalException(
            "Backtest rerport file or folder does not exist"
        )

    if os.path.isdir(file_path):
        file_path = os.path.join(file_path, "report.json")
        return load_backtest_report(file_path)

    if not os.path.isfile(file_path):
        raise OperationalException(
            f"Backtest report file {file_path} does not exist"
        )

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
    algorithm_name: Optional[str] = None,
    backtest_date_range: Optional[BacktestDateRange] = None
) -> BacktestReport | None:
    """
    Function to create a backtest report from a directory.
    This function searches for a backtest report in the given directory.

    If the algorithm name and backtest date range are provided,
    It will search for a backtest report that matches the algorithm name
    and backtest date range.

    Args:
        algorithm_name (str): The name of the algorithm
        backtest_date_range (BacktestDateRange): The backtest date range
        directory (str): The output directory

    Returns:
        BacktestReport: The backtest report if it exists, otherwise None
    """

    if not os.path.exists(directory):
        raise OperationalException(
            f"Directory {directory} does not exist"
        )

    # Loop through all files in the directory
    for root, _, files in os.walk(directory):
        for file in files:

            # Check if the file is a directory
            if os.path.isdir(os.path.join(root, file)):

                # Check if it has a report.json file
                if "report.json" in os.listdir(os.path.join(root, file)):
                    report_file = os.path.join(root, file, "report.json")

                    if is_backtest_report(report_file):
                        # Read the file
                        with open(report_file, "r") as json_file:
                            # Parse the JSON file
                            report = json.load(json_file)
                            # Convert the JSON file to a
                            # BacktestReport object
                            report = BacktestReport.from_dict(report)

                            if algorithm_name is not None and \
                                    report.name == algorithm_name:

                                if backtest_date_range is None:
                                    return report

                                if backtest_date_range.start_date == \
                                        report.backtest_start_date and \
                                        backtest_date_range.end_date == \
                                        report.backtest_end_date:
                                    return report

                            if algorithm_name is None and \
                                    backtest_date_range is None:
                                return report

            elif file.endswith(".json"):
                # Read the file
                with open(os.path.join(root, file), "r") as json_file:
                    # Parse the JSON file
                    report = json.load(json_file)
                    # Convert the JSON file to a BacktestReport object
                    report = BacktestReport.from_dict(report)

                    if algorithm_name is not None and \
                            report.name == algorithm_name:

                        if backtest_date_range is None:
                            return report

                        if backtest_date_range.start_date == \
                                report.backtest_start_date and \
                                backtest_date_range.end_date == \
                                report.backtest_end_date:
                            return report

                    if algorithm_name is None and \
                            backtest_date_range is None:
                        return report
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
        else:
            # Try to load the file as a BacktestReport
            try:
                # Read the file
                with open(path, "r") as json_file:
                    # Parse the JSON file
                    report = json.load(json_file)
                    # Convert the JSON file to a
                    # BacktestReport object
                    BacktestReport.from_dict(report)
                    return True
            except Exception:
                # If the file is not a valid JSON file, return False
                return False

    return False
