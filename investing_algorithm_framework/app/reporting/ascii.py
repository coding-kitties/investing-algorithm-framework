import os
from datetime import datetime
from typing import List

from tabulate import tabulate

from investing_algorithm_framework.domain import DATETIME_FORMAT, Backtest, \
    BacktestDateRange, TradeStatus, OrderSide
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
        f"{float(report.growth_percentage):.{percentage_precision}f}%" for report in reports
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
    backtest,
    backtest_date_range: BacktestDateRange = None,
    triggered_only=False,
    amount_precision=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=0
):
    print(f"{COLOR_YELLOW}Stop losses overview{COLOR_RESET}")
    stop_loss_table = {}
    results = backtest.get_backtest_run(backtest_date_range)
    trades = results.get_trades()
    selection = []

    def get_sold_amount(stop_loss):
        if stop_loss["sold_amount"] > 0:
            return f"{float(stop_loss['sold_amount']):.{amount_precision}f} {stop_loss['target_symbol']}"

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

        if take_profit["trailing"]:
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
                        "trailing": stop_loss.trailing,
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
                        "trailing": stop_loss.trailing,
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
        f"{stop_loss['trailing']}" for stop_loss in selection
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
    backtest: Backtest,
    backtest_date_range: BacktestDateRange = None,
    triggered_only=False,
    amount_precision=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=0
):
    print(f"{COLOR_YELLOW}Take profits overview{COLOR_RESET}")
    take_profit_table = {}
    results = backtest.get_backtest_run(backtest_date_range)
    trades = results.get_trades()
    selection = []

    def get_high_water_mark(take_profit):
        if take_profit["high_water_mark"] is not None:
            return f"{float(take_profit['high_water_mark']):.{price_precision}f} {take_profit['trading_symbol']} ({format_date(take_profit['high_water_mark_date'])})"

        return ""

    def get_sold_amount(take_profit):
        if take_profit["sold_amount"] > 0:
            return f"{float(take_profit['sold_amount']):.{amount_precision}f} {take_profit['target_symbol']}"

        return ""

    def get_take_profit_price(take_profit):

        if take_profit["trailing"]:
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
                        "trailing": take_profit.trailing,
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
                        "trailing": take_profit.trailing,
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
        f"{take_profit['trailing']}" for take_profit
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
        f"{float(stop_loss['sell_amount']):.{amount_precision}f} {stop_loss['target_symbol']}" for stop_loss in selection
    ]
    take_profit_table["Sold amount"] = [
        get_sold_amount(stop_loss) for stop_loss in selection
    ]
    print(tabulate(take_profit_table, headers="keys", tablefmt="rounded_grid"))


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


def pretty_print_orders(
    backtest: Backtest,
    backtest_date_range: BacktestDateRange = None,
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
        backtest: The backtest
        backtest_date_range: The date range of the backtest
        target_symbol: The target symbol of the orders
        order_status: The status of the orders
        amount_precesion: The precision of the amount
        price_precision: The precision of the price
        time_precision: The precision of the time
        percentage_precision: The precision of the percentage

    Returns:
        None
    """
    run = backtest.get_backtest_run(backtest_date_range)
    selection = run.get_orders(
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
    backtest,
    backtest_date_range: BacktestDateRange = None,
    symbol = None,
    amount_precision=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=2
) -> None:
    """
    Pretty print the positions of the backtest report to the console.

    Args:
        backtest: The backtest report
        backtest_date_range: The date range of the backtest
        amount_precision: The precision of the amount
        price_precision: The precision of the price
        time_precision: The precision of the time
        percentage_precision: The precision of the percentage

    Returns:
        None
    """
    results = backtest.get_backtest_run(backtest_date_range)
    selection = results.get_positions(symbol=symbol)

    print(f"{COLOR_YELLOW}Positions overview{COLOR_RESET}")
    position_table = {}
    position_table["Position"] = [
        position.symbol for position in selection
    ]
    position_table["Amount"] = [
        f"{float(position.amount):.{amount_precision}f}" for position in
        selection
    ]
    position_table["Pending buy amount"] = [
        f"{float(position.amount_pending_buy):.{amount_precision}f}"
        for position in selection
    ]
    position_table["Pending sell amount"] = [
        f"{float(position.amount_pending_sell):.{amount_precision}f}"
        for position in selection
    ]
    position_table[f"Cost ({results.trading_symbol})"] = [
        f"{float(position.cost):.{price_precision}f}"
        for position in selection
    ]
    position_table[f"Value ({results.trading_symbol})"] = [
        f"{float(position.value):.{price_precision}f} {results.trading_symbol}"
        for position in selection
    ]
    position_table["Percentage of portfolio"] = [
        f"{float(position.percentage_of_portfolio):.{percentage_precision}f}%"
        for position in selection
    ]
    position_table[f"Growth ({results.trading_symbol})"] = [
        f"{float(position.growth):.{price_precision}f} {results.trading_symbol}"
        for position in selection
    ]
    position_table["Growth_percentage"] = [
        f"{float(position.growth_percentage):.{percentage_precision}f}%"
        for position in selection
    ]
    print(
        tabulate(position_table, headers="keys", tablefmt="rounded_grid")
    )


def pretty_print_trades(
    backtest: Backtest,
    backtest_date_range: BacktestDateRange = None,
    target_symbol = None,
    status = None,
    amount_precision=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=2
):
    """
    Pretty print the trades of the backtest report to the console.

    Args:
        backtest: The backtest report
        backtest_date_range: The date range of the backtest
        target_symbol: The target symbol of the trades
        status: The status of the trades
        amount_precision: The precision of the amount
        price_precision: The precision of the price
        time_precision: The precision of the time
        percentage_precision: The precision of the percentage

    Returns:
        None
    """
    run = backtest.get_backtest_run(backtest_date_range)
    selection = run.get_trades(
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
        f"{float(trade.amount):.{amount_precision}f} ({float(trade.remaining):.{amount_precision}f}) {trade.target_symbol}"
        for trade in selection
    ]
    trades_table[f"Net gain ({run.trading_symbol})"] = [
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
    trades_table[f"Net gain ({run.trading_symbol})"] = [
        f"{float(trade.net_gain_absolute):.{price_precision}f} ({float(trade.net_gain_percentage):.{percentage_precision}f}%)" + (" (unrealized)" if not TradeStatus.CLOSED.equals(trade.status) else "")
        for trade in selection
    ]
    trades_table[f"Open price ({run.trading_symbol})"] = [
        f"{trade.open_price:.{price_precision}f}"  for trade in selection
    ]
    trades_table[
        f"Close price's ({run.trading_symbol})"
    ] = [
        get_close_prices(trade) for trade in selection
    ]
    trades_table["High water mark"] = [
        get_high_water_mark(trade) for trade in selection
    ]
    print(tabulate(trades_table, headers="keys", tablefmt="rounded_grid"))


def print_number_of_runs(report):

    if report.number_of_runs == 1:

        if report.inteval > 1:
            print(f"Strategy ran every {report.interval} {report.time_unit} "
                  f"for a total of {report.number_of_runs} time")


def pretty_print_backtest(
    backtest: Backtest,
    backtest_date_range: BacktestDateRange = None,
    show_positions=True,
    show_trades=True,
    show_stop_losses=True,
    show_triggered_stop_losses_only=False,
    show_take_profits=True,
    show_triggered_take_profits_only=False,
    amount_precision=4,
    price_precision=2,
    time_precision=1,
    percentage_precision=2
):
    """
    Pretty print the backtest report to the console.

    Args:
        backtest: Backtest - the backtest report
        show_positions: bool - show the positions
        show_trades: bool - show the trades
        show_stop_losses: bool - show the stop losses
        show_triggered_stop_losses_only: bool - show only the triggered stop losses
        show_take_profits: bool - show the take profits
        show_triggered_take_profits_only: bool - show only the triggered take profits
        amount_precision: int - the amount precision
        price_precision: int - the price precision
        time_precision: int - the time precision
        percentage_precision: int - the percentage precision

    Returns:
        None
    """
    backtest_results = backtest.get_backtest_run(backtest_date_range)
    backtest_metrics = backtest.get_backtest_metrics(backtest_date_range)
    ascii_art = f"""
                  :%%%#+-          .=*#%%%        {COLOR_GREEN}Backtest report{COLOR_RESET}
                  *%%%%%%%+------=*%%%%%%%-       {COLOR_GREEN}---------------------------{COLOR_RESET}
                  *%%%%%%%%%%%%%%%%%%%%%%%-       {COLOR_YELLOW}Start date:{COLOR_RESET}{COLOR_GREEN} {backtest_results.backtest_start_date}{COLOR_RESET}
                  .%%%%%%%%%%%%%%%%%%%%%%#        {COLOR_YELLOW}End date:{COLOR_RESET}{COLOR_GREEN} {backtest_results.backtest_end_date}{COLOR_RESET}
                   #%%%####%%%%%%%%**#%%%+        {COLOR_YELLOW}Number of days:{COLOR_RESET}{COLOR_GREEN}{COLOR_RESET}{COLOR_GREEN} {backtest_results.number_of_days}{COLOR_RESET}
             .:-+*%%%%- {COLOR_PURPLE}-+..#{COLOR_RESET}%%%+.{COLOR_PURPLE}+-  +{COLOR_RESET}%%%#*=-:   {COLOR_YELLOW}Number of runs:{COLOR_RESET}{COLOR_GREEN} {backtest_results.number_of_runs}{COLOR_RESET}
              .:-=*%%%%. {COLOR_PURPLE}+={COLOR_RESET} .%%#  {COLOR_PURPLE}-+.-{COLOR_RESET}%%%%=-:..   {COLOR_YELLOW}Number of orders:{COLOR_RESET}{COLOR_GREEN} {backtest_results.number_of_orders}{COLOR_RESET}
              .:=+#%%%%%*###%%%%#*+#%%%%%%*+-:    {COLOR_YELLOW}Initial balance:{COLOR_RESET}{COLOR_GREEN} {backtest_results.initial_unallocated}{COLOR_RESET}
                    +%%%%%%%%%%%%%%%%%%%=         {COLOR_YELLOW}Final balance:{COLOR_RESET}{COLOR_GREEN} {float(backtest_metrics.final_value):.{price_precision}f}{COLOR_RESET}
                :++  .=#%%%%%%%%%%%%%*-           {COLOR_YELLOW}Total net gain:{COLOR_RESET}{COLOR_GREEN} {float(backtest_metrics.total_net_gain):.{price_precision}f} {float(backtest_metrics.total_net_gain_percentage):.{percentage_precision}f}%{COLOR_RESET}
               :++:      :+%%%%%%#-.              {COLOR_YELLOW}Growth:{COLOR_RESET}{COLOR_GREEN} {float(backtest_metrics.growth):.{price_precision}f} {float(backtest_metrics.growth_percentage):.{percentage_precision}f}%{COLOR_RESET}
              :++:        .%%%%%#=                {COLOR_YELLOW}Number of trades:{COLOR_RESET}{COLOR_GREEN} {backtest_results.number_of_trades}{COLOR_RESET}
              :++:        .%%%%%#=                {COLOR_YELLOW}Number of trades closed:{COLOR_RESET}{COLOR_GREEN} {backtest_results.number_of_trades_closed}{COLOR_RESET}
             :++:        .#%%%%%#*=               {COLOR_YELLOW}Number of trades open(end of backtest):{COLOR_RESET}{COLOR_GREEN} {backtest_results.number_of_trades_open}{COLOR_RESET}
            :++-        :%%%%%%%%%+=              {COLOR_YELLOW}Percentage positive trades:{COLOR_RESET}{COLOR_GREEN} {float(backtest_metrics.percentage_positive_trades):.{percentage_precision}f}%{COLOR_RESET}
           .++-        -%%%%%%%%%%%+=             {COLOR_YELLOW}Percentage negative trades:{COLOR_RESET}{COLOR_GREEN} {float(backtest_metrics.percentage_negative_trades):.{percentage_precision}f}%{COLOR_RESET}
          .++-        .%%%%%%%%%%%%%+=            {COLOR_YELLOW}Average trade size:{COLOR_RESET}{COLOR_GREEN} {float(backtest_metrics.average_trade_size):.{price_precision}f} {backtest_results.trading_symbol}{COLOR_RESET}
         .++-         *%%%%%%%%%%%%%*+:           {COLOR_YELLOW}Average trade duration:{COLOR_RESET}{COLOR_GREEN} {float(backtest_metrics.average_trade_duration):.{0}f} hours{COLOR_RESET}
        .++-          %%%%%%%%%%%%%%#+=
        =++........:::%%%%%%%%%%%%%%*+-
        .=++++++++++**#%%%%%%%%%%%%%++.
        """

    print(ascii_art)

    if show_positions:
        print(f"{COLOR_YELLOW}Positions overview{COLOR_RESET}")
        pretty_print_positions(backtest)

    if show_trades:
        pretty_print_trades(
            backtest=backtest,
            amount_precision=amount_precision,
            price_precision=price_precision,
            time_precision=time_precision,
            percentage_precision=percentage_precision
        )

    if show_stop_losses:
        pretty_print_stop_losses(
            backtest=backtest,
            triggered_only=show_triggered_stop_losses_only,
            amount_precision=amount_precision,
            price_precision=price_precision,
            time_precision=time_precision,
            percentage_precision=percentage_precision
        )

    if show_take_profits:
        pretty_print_take_profits(
            backtest=backtest,
            triggered_only=show_triggered_take_profits_only,
            amount_precision=amount_precision,
            price_precision=price_precision,
            time_precision=time_precision,
            percentage_precision=percentage_precision
        )

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
