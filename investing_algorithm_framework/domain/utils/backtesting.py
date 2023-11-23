

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
        print(f"* Number of positions at the end of backtest: {backtest_report.number_of_positions}")
        print(f"* Total cost of current positions: "
              f"{backtest_report.total_cost:.{precision}f} "
              f"{backtest_report.trading_symbol}")
        for position in backtest_report.positions:
            print(
                f"{position.symbol}, "
                f"amount: {position.amount:.{precision}f}, "
                f"cost: {position.cost:.{precision}f} "
                f"{backtest_report.trading_symbol}, "
                f"value: {position.value:.{precision}f} "
                f"{backtest_report.trading_symbol}, "
                f"growth: {position.growth:.{precision}f} "
                f"{backtest_report.trading_symbol} "
                f"({position.growth_rate:.{precision}f}%)."
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
        for trade in backtest_report.trades:
            print(
                f"{trade.target_symbol} -> {trade.trading_symbol}, "
                f"open date: {trade.opened_at}, "
                f"close date: {trade.closed_at}, "
                f"size: {trade.size:.{precision}f} {trade.trading_symbol}, "
                f"net gain: {trade.net_gain:.{precision}f}, "
                f"net gain percentage: "
                f"{trade.net_gain_percentage:.{precision}f}%, "
                f"duration: {trade.duration} hours, "
                f"open price: {trade.open_price}, "
                f"close price: {trade.closed_price}"
            )
    print("==================================================================")
