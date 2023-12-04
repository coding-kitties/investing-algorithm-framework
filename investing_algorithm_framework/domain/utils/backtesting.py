from tabulate import tabulate

def print_number_of_runs(report):

    if report.number_of_runs == 1:

        if report.inteval > 1:
            print(f"Strategy ran every {report.interval} {report.time_unit} for a total of {report.number_of_runs} time")


def pretty_print_backtest(backtest_report, show_positions=True, show_trades=True, precision=4):
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
        position_table["Position"] = [position.symbol for position in backtest_report.positions if position.amount > 0 or position.amount_pending > 0]
        position_table["Amount"] = [f"{position.amount:.{precision}f}" for position in backtest_report.positions if position.amount > 0 or position.amount_pending > 0]
        position_table["Pending amount"] = [f"{position.amount_pending:.{precision}f}" for position in backtest_report.positions if position.amount > 0 or position.amount_pending > 0]
        position_table[f"Cost ({backtest_report.trading_symbol})"] = [f"{position.cost:.{precision}f}" for position in backtest_report.positions if position.amount > 0 or position.amount_pending > 0]
        position_table[f"Value ({backtest_report.trading_symbol})"] = [f"{position.value:.{precision}f}" for position in backtest_report.positions if position.amount > 0 or position.amount_pending > 0]
        position_table["Percentage of portfolio"] = [f"{position.percentage_of_portfolio:.{precision}f}%" for position in backtest_report.positions if position.amount > 0 or position.amount_pending > 0]
        position_table[f"Growth ({backtest_report.trading_symbol})"] = [f"{position.growth:.{precision}f}" for position in backtest_report.positions if position.amount > 0 or position.amount_pending > 0]
        position_table["Growth_rate"] = [f"{position.growth_rate:.{precision}f}%" for position in backtest_report.positions if position.amount > 0 or position.amount_pending > 0]
        print(tabulate(position_table, headers="keys", tablefmt="rounded_grid"))

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
        trades_table["Pair"] = [f"{trade.target_symbol}-{trade.trading_symbol}" for trade in backtest_report.trades]
        trades_table["Open date"] = [trade.opened_at for trade in backtest_report.trades]
        trades_table["Close date"] = [trade.closed_at for trade in backtest_report.trades]
        trades_table["Duration (hours)"] = [trade.duration for trade in backtest_report.trades]
        trades_table[f"Size ({backtest_report.trading_symbol})"] = [f"{trade.size:.{precision}f}" for trade in backtest_report.trades]
        trades_table[f"Net gain ({backtest_report.trading_symbol})"] = [f"{trade.net_gain:.{precision}f}" for trade in backtest_report.trades]
        trades_table["Net gain percentage"] = [f"{trade.net_gain_percentage:.{precision}f}%" for trade in backtest_report.trades]
        trades_table[f"Open price ({backtest_report.trading_symbol})"] = [trade.open_price for trade in backtest_report.trades]
        trades_table[f"Close price ({backtest_report.trading_symbol})"] = [trade.closed_price for trade in backtest_report.trades]
        print(tabulate(trades_table, headers="keys", tablefmt="rounded_grid"))
    print("==================================================================")
