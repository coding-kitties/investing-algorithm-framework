
def print_number_of_runs(report):

    if report.number_of_runs == 1:

        if report.inteval > 1:
            print(f"Strategy ran every {report.interval} {report.time_unit} for a total of {report.number_of_runs} time")



def pretty_print_backtest(backtest_reports):
    print("============================================")
    if len(backtest_reports) == 1:
        print(f"Backtest report for {len(backtest_reports)} strategy")
    else:
        print(f"Backtest report for {len(backtest_reports)} strategies")

    for report in backtest_reports:
        print(f"* Strategy id: {report.strategy_id}")
        print(f"* start date: {report.backtest_start_date}")
        print(f"* end date: {report.backtest_end_date}")
        print(f"* number of days: {report.number_of_days}")
        print(f"* Run interval: {report.interval} {report.time_unit.plural_name}")
        print(f"* number of runs: {report.number_of_runs}")
        print(f"* number of orders: {report.number_of_orders}")
        print(f"* number of positions: {report.number_of_positions}")


        # if report.number_of_runs == 1:
        #
        #     if report.interval > 1:
        #         print(f"Strategy ran every {report.interval} {report.time_unit} for a total of {report.number_of_runs} time")
        #     else:
        #         print(f"Strategy ran every {report.interval} {report.time_unit} for a total of {report.number_of_runs} time")
        # else:
        #
        #     if report.interval == 1:
        #         print(f"Strategy ran every {report.interval} "
        #               f"{report.time_unit.single_name} for a total of "
        #               f"{report.number_of_runs} times")
        #     else:
        #         print(f"Strategy ran every {report.interval} "
        #               f"{report.time_unit.plural_name} for a total "
        #               f"of {report.number_of_runs} times for a total of {report.number_of_days} days")
