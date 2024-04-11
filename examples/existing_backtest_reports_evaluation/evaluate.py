from investing_algorithm_framework import BacktestReportsEvaluation, \
    pretty_print_backtest_reports_evaluation, load_backtest_reports

if __name__ == "__main__":
    reports = load_backtest_reports("backtest_reports")
    evaluation = BacktestReportsEvaluation(reports)
    pretty_print_backtest_reports_evaluation(evaluation)
