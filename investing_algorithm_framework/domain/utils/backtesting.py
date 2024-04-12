import os
from datetime import datetime
from typing import List, Tuple

from tabulate import tabulate

from investing_algorithm_framework.domain import DATETIME_FORMAT
from investing_algorithm_framework.domain.exceptions import \
    OperationalException
from investing_algorithm_framework.domain.models.backtesting import \
    BacktestReportsEvaluation, BacktestReport
from .csv import load_csv_into_dict

COLOR_RED = '\033[91m'
COLOR_PURPLE = '\033[95m'
COLOR_RESET = '\033[0m'
COLOR_GREEN = '\033[92m'
COLOR_YELLOW = '\033[93m'

def print_tables_side_by_side(*tables, spacing: int = 3):
    string_tables_split = [tabulate(t, headers="firstrow").splitlines() for t in tables]
    spacing_str = " " * spacing

    num_lines = max(map(len, string_tables_split))
    paddings = [max(map(len, s_lines)) for s_lines in string_tables_split]

    for i in range(num_lines):
        line_each_table = []
        for padding, table_lines in zip(paddings, string_tables_split):
            if len(table_lines) <= i:
                line_each_table.append(" " * (padding + spacing))
            else:
                line_table_string = table_lines[i]
                line_len = len(line_table_string)
                line_each_table.append(
                    line_table_string + (" " * (padding - line_len)) + spacing_str
                )

        final_line_string = "".join(line_each_table)
        print(final_line_string)


def is_positive(number) -> bool:
    """
    Check if a number is positive.

    param number: The number
    :return: True if the number is positive, False otherwise
    """
    number = float(number)
    return number > 0


def pretty_print_profit_evaluation(
    evaluation: BacktestReportsEvaluation,
    date_range,
    precision=4,
    number_of_reports=3
):
    profits = evaluation.profit_order[date_range]
    profit_table = {}
    profit_table["Algorithm name"] = [
        report.name for report in profits[:number_of_reports]
    ]
    profit_table["Profit"] = [
        f"{report.total_net_gain:.{precision}f} {report.trading_symbol}" for report in profits[:number_of_reports]
    ]
    profit_table["Profit percentage"] = [
        f"{report.total_net_gain_percentage:.{precision}f}%" for report in profits[:number_of_reports]
    ]

    print(f"{COLOR_YELLOW}Profit:{COLOR_RESET} {COLOR_GREEN}Top {number_of_reports}{COLOR_RESET}")
    print(tabulate(profit_table, headers="keys", tablefmt="rounded_grid"))

    least_profits = profits[-number_of_reports:]
    least_profit_table = {}
    least_profit_table["Algorithm name"] = [
        report.name for report in least_profits
    ]
    least_profit_table["Profit"] = [
        f"{report.total_net_gain:.{precision}f} {report.trading_symbol}" for
        report in least_profits
    ]
    least_profit_table["Profit percentage"] = [
        f"{report.total_net_gain_percentage:.{precision}f}%" for report in
        least_profits
    ]

    print(f"{COLOR_RED}Least profit:{COLOR_RESET} {COLOR_GREEN}Top {number_of_reports}{COLOR_RESET}")
    print(tabulate(least_profit_table, headers="keys", tablefmt="rounded_grid"))


def pretty_print_growth_evaluation(
    evaluation: BacktestReportsEvaluation,
    date_range,
    precision=4,
    number_of_reports=3
):
    growths = evaluation.growth_order[date_range]
    print(f"{COLOR_YELLOW}Growth:{COLOR_RESET} {COLOR_GREEN}Top {number_of_reports}{COLOR_RESET}")
    growth_table = {}
    growth_table["Algorithm name"] = [
        report.name for report in growths[:number_of_reports]
    ]
    growth_table["Growth"] = [
        f"{report.growth:.{precision}f} {report.trading_symbol}" for report in growths[:number_of_reports]
    ]
    growth_table["Growth percentage"] = [
        f"{report.growth_rate:.{precision}f}%" for report in growths[:number_of_reports]
    ]
    print(
        tabulate(growth_table, headers="keys", tablefmt="rounded_grid")
    )

    least_growths = growths[-number_of_reports:]
    least_growth_table = {}
    least_growth_table["Algorithm name"] = [
        report.name for report in least_growths
    ]
    least_growth_table["Growth"] = [
        f"{report.growth:.{precision}f} {report.trading_symbol}" for
        report in least_growths
    ]
    least_growth_table["Growth percentage"] = [
        f"{report.growth_rate:.{precision}f}%" for report in
        least_growths
    ]

    print(
        f"{COLOR_RED}Least growth:{COLOR_RESET} {COLOR_GREEN}"
        f"Top {number_of_reports}{COLOR_RESET}"
    )
    print(
        tabulate(
            least_growth_table, headers="keys", tablefmt="rounded_grid"
        )
    )

def pretty_print_percentage_positive_trades_evaluation(
    evaluation: BacktestReportsEvaluation,
    date_range,
    precision=0,
    number_of_reports=3
):
    order = evaluation.percentage_positive_trades_order[date_range]
    print(f"{COLOR_YELLOW}Trades:{COLOR_RESET} {COLOR_GREEN}Top {number_of_reports}{COLOR_RESET}")
    profit_table = {}
    profit_table["Algorithm name"] = [
        report.name for report in order[:number_of_reports]
    ]
    profit_table["Percentage positive trades"] = [
        f"{report.percentage_positive_trades:.{precision}f}%"
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
        f"{report.percentage_positive_trades:.{precision}f}%"
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


def pretty_print_date_ranges(date_ranges: List[Tuple[datetime]]) -> None:
    """
    Pretty print the date ranges to the console.

    param date_ranges: The date ranges
    """
    print(f"{COLOR_YELLOW}Date ranges of backtests:{COLOR_RESET}")
    for date_range in date_ranges:
        start_date = date_range[0]
        end_date = date_range[1]

        if isinstance(start_date, datetime):
            start_date = start_date.strftime(DATETIME_FORMAT)

        if isinstance(end_date, datetime):
            end_date = end_date.strftime(DATETIME_FORMAT)

        print(f"{COLOR_GREEN}{start_date} - {end_date}{COLOR_RESET}")


def pretty_print_most_profitable(
    evaluation: BacktestReportsEvaluation,
    date_range,
    precision=4,
):
    profits = evaluation.profit_order[date_range]
    profit = profits[0]
    print(f"{COLOR_YELLOW}Most profitable:{COLOR_RESET} {COLOR_GREEN}Algorithm {profit.name} {profit.total_net_gain:.{precision}f} {profit.trading_symbol} {profit.total_net_gain_percentage:.{precision}f}%{COLOR_RESET}")


def pretty_print_most_growth(
    evaluation: BacktestReportsEvaluation,
    date_range,
    precision=4,
):
    profits = evaluation.growth_order[date_range]
    profit = profits[0]
    print(f"{COLOR_YELLOW}Most growth:{COLOR_RESET} {COLOR_GREEN}Algorithm {profit.name} {profit.growth:.{precision}f} {profit.trading_symbol} {profit.growth_rate:.{precision}f}%{COLOR_RESET}")


def pretty_print_percentage_positive_trades(
    evaluation: BacktestReportsEvaluation,
    date_range,
    precision=0
):
    percentages = evaluation.percentage_positive_trades_order[date_range]
    percentages = percentages[0]
    print(f"{COLOR_YELLOW}Most positive trades:{COLOR_RESET} {COLOR_GREEN}Algorithm {percentages.name} {percentages.percentage_positive_trades:.{precision}f}%{COLOR_RESET}")


def pretty_print_backtest_reports_evaluation(
    backtest_reports_evaluation: BacktestReportsEvaluation,
    precision=4
) -> None:
    """
    Pretty print the backtest reports evaluation to the console.
    """
    number_of_backtest_reports = len(backtest_reports_evaluation.backtest_reports)
    most_profitable = backtest_reports_evaluation.profit_order_all[0]
    most_growth = backtest_reports_evaluation.growth_order_all[0]

    ascii_art = f"""
                      {COLOR_PURPLE}/{COLOR_RESET}&{COLOR_PURPLE}#{COLOR_RESET}                                      {COLOR_PURPLE}#{COLOR_RESET}&{COLOR_PURPLE}({COLOR_RESET}                 {COLOR_GREEN}Backtest reports evaluation{COLOR_RESET}
                      &&&&&&&&&&&#                       &&&&&&&&&&&&              {COLOR_GREEN}---------------------------{COLOR_RESET}
                     &&&&&&&&&&&&&&&&                (&&&&&&&&&&&&&&&              {COLOR_YELLOW}Number of reports:{COLOR_RESET} {COLOR_GREEN}{number_of_backtest_reports} backtest reports{COLOR_RESET}
                     &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&              {COLOR_YELLOW}Total number of date ranges:{COLOR_RESET}{COLOR_GREEN}{len(backtest_reports_evaluation.get_date_ranges())}{COLOR_RESET}
                     &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&              {COLOR_YELLOW}Largest overall profit:{COLOR_RESET}{COLOR_GREEN}{COLOR_RESET}{COLOR_GREEN} (Algorithm {most_profitable.name}) {most_profitable.total_net_gain:.{precision}f} {most_profitable.trading_symbol} {most_profitable.total_net_gain_percentage:.{precision}f}% ({most_profitable.backtest_start_date} - {most_profitable.backtest_end_date}){COLOR_RESET} 
                      &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&              {COLOR_YELLOW}Largest overall growth:{COLOR_RESET}{COLOR_GREEN} (Algorithm {most_profitable.name}) {most_growth.growth:.{precision}f} {most_growth.trading_symbol} {most_growth.growth_rate:.{precision}f}% ({most_growth.backtest_start_date} - {most_growth.backtest_end_date}){COLOR_RESET}
                      .&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&                
                       &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}.{COLOR_RESET}            
                      &&&&&&&#  {COLOR_PURPLE}/((({COLOR_RESET}   &&&&&&&&&&&&{COLOR_PURPLE}*((({COLOR_RESET}     .&&&&&&&{COLOR_PURPLE}.{COLOR_RESET}           
          &&&&&&&&&&&&&&&&&&&    {COLOR_PURPLE}(((({COLOR_RESET}    &&&&&&&&   {COLOR_PURPLE}(((({COLOR_RESET}     &&&&&&&&&&&&&&&&&&&
                   {COLOR_PURPLE}((({COLOR_RESET}&&&&&&&&    {COLOR_PURPLE}(((({COLOR_RESET}    &&&&&&     {COLOR_PURPLE}(((({COLOR_RESET}   &&&&&&&&&{COLOR_PURPLE}(({COLOR_RESET}         
           {COLOR_PURPLE}/(((((((((({COLOR_RESET}&&&&&&&&&&   {COLOR_PURPLE}(((,{COLOR_RESET}   &&&&&&      {COLOR_PURPLE}(((**{COLOR_RESET}&&&&&&&&&{COLOR_PURPLE}((((((((((({COLOR_RESET} 
                 &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&       
                        &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&              
                          &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&                
                 {COLOR_PURPLE}((((({COLOR_RESET}      &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}({COLOR_RESET}                  
                {COLOR_PURPLE}((((({COLOR_RESET}           &&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE},{COLOR_RESET}                       
               {COLOR_PURPLE}((((({COLOR_RESET}                 &&&&&&&&&&&&&{COLOR_PURPLE}#{COLOR_RESET}                            
              {COLOR_PURPLE}((((({COLOR_RESET}                  #&&&&&&&&&&{COLOR_PURPLE}###{COLOR_RESET}                            
             {COLOR_PURPLE}((((({COLOR_RESET}                   &&&&&&&&&&&{COLOR_PURPLE}###.{COLOR_RESET}                           
           {COLOR_PURPLE}.((((({COLOR_RESET}                   &&&&&&&&&&&&&&{COLOR_PURPLE}###({COLOR_RESET}                          
          {COLOR_PURPLE}((((({COLOR_RESET}                   &&&&&&&&&&&&&&&&{COLOR_PURPLE}#(((/{COLOR_RESET}                        
         {COLOR_PURPLE}((((({COLOR_RESET}                  &&&&&&&&&&&&&&&&&&&@{COLOR_PURPLE}(((({COLOR_RESET}                       
        {COLOR_PURPLE}((((({COLOR_RESET}                  &&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                      
       {COLOR_PURPLE}((((({COLOR_RESET}                  &&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}((((,{COLOR_RESET}                    
     {COLOR_PURPLE}.((((({COLOR_RESET}                   &&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                    
    {COLOR_PURPLE}((((({COLOR_RESET}                   &&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                   
   {COLOR_PURPLE}((((({COLOR_RESET}                    &&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                  
  {COLOR_PURPLE}((((({COLOR_RESET}                    &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                  
 {COLOR_PURPLE}((((({COLOR_RESET}                     &&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}#(((({COLOR_RESET}                  
 {COLOR_PURPLE}(((((((((((((((((((#########{COLOR_RESET}&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}((((({COLOR_RESET}                  
  {COLOR_PURPLE}(((((((((((((((((((((######{COLOR_RESET}&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                   
    """
    if len(backtest_reports_evaluation.backtest_reports) == 0:
        print("No backtest reports available in your evaluation")
        return

    print(ascii_art)
    pretty_print_date_ranges(backtest_reports_evaluation.get_date_ranges())
    print("")
    date_ranges = backtest_reports_evaluation.get_date_ranges()

    for date_range in date_ranges:
        start_date = date_range[0]
        end_date = date_range[1]

        if isinstance(start_date, datetime):
            start_date = start_date.strftime(DATETIME_FORMAT)

        if isinstance(end_date, datetime):
            end_date = end_date.strftime(DATETIME_FORMAT)

        print(
            f"{COLOR_YELLOW}Evaluation of date range:{COLOR_RESET} {COLOR_GREEN}{start_date} - {end_date}{COLOR_RESET}")
        print(
            f"{COLOR_GREEN}-------------------------------------------------------------------{COLOR_RESET}")
        pretty_print_most_profitable(
            backtest_reports_evaluation, date_range, precision
        )
        pretty_print_most_growth(
            backtest_reports_evaluation, date_range, precision
        )
        pretty_print_percentage_positive_trades(
            backtest_reports_evaluation, date_range
        )
        print("")
        pretty_print_profit_evaluation(
            backtest_reports_evaluation, date_range, precision
        )
        pretty_print_growth_evaluation(
            backtest_reports_evaluation, date_range, precision
        )
        pretty_print_percentage_positive_trades_evaluation(
            backtest_reports_evaluation, date_range, precision=0
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
                          {COLOR_PURPLE}/{COLOR_RESET}&{COLOR_PURPLE}#{COLOR_RESET}                                      {COLOR_PURPLE}#{COLOR_RESET}&{COLOR_PURPLE}({COLOR_RESET}                 {COLOR_GREEN}Backtest report{COLOR_RESET}
                          &&&&&&&&&&&#                       &&&&&&&&&&&&              {COLOR_GREEN}---------------------------{COLOR_RESET}
                         &&&&&&&&&&&&&&&&                (&&&&&&&&&&&&&&&              {COLOR_YELLOW}Start date:{COLOR_RESET}{COLOR_GREEN} {backtest_report.backtest_start_date}{COLOR_RESET}
                         &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&              {COLOR_YELLOW}End date:{COLOR_RESET}{COLOR_GREEN} {backtest_report.backtest_end_date}{COLOR_RESET}
                         &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&              {COLOR_YELLOW}Number of days:{COLOR_RESET}{COLOR_GREEN}{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_days}{COLOR_RESET} 
                          &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&              {COLOR_YELLOW}Number of runs:{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_runs}{COLOR_RESET}
                          .&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&               {COLOR_YELLOW}Number of orders:{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_orders}{COLOR_RESET}
                           &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}.{COLOR_RESET}               {COLOR_YELLOW}Initial balance:{COLOR_RESET}{COLOR_GREEN} {backtest_report.initial_unallocated}{COLOR_RESET}
                          &&&&&&&#  {COLOR_PURPLE}/((({COLOR_RESET}   &&&&&&&&&&&&{COLOR_PURPLE}*((({COLOR_RESET}     .&&&&&&&{COLOR_PURPLE}.{COLOR_RESET}              {COLOR_YELLOW}Final balance:{COLOR_RESET}{COLOR_GREEN} {backtest_report.total_value:.{precision}f}{COLOR_RESET}      
              &&&&&&&&&&&&&&&&&&&    {COLOR_PURPLE}(((({COLOR_RESET}    &&&&&&&&   {COLOR_PURPLE}(((({COLOR_RESET}     &&&&&&&&&&&&&&&&&&&   {COLOR_YELLOW}Total net gain:{COLOR_RESET}{COLOR_GREEN} {backtest_report.total_net_gain:.{precision}f} {backtest_report.total_net_gain_percentage:.{precision}}%{COLOR_RESET}  
                       {COLOR_PURPLE}((({COLOR_RESET}&&&&&&&&    {COLOR_PURPLE}(((({COLOR_RESET}    &&&&&&     {COLOR_PURPLE}(((({COLOR_RESET}   &&&&&&&&&{COLOR_PURPLE}(({COLOR_RESET}            {COLOR_YELLOW}Growth:{COLOR_RESET}{COLOR_GREEN} {backtest_report.growth:.{precision}f} {backtest_report.growth_rate:.{precision}}%{COLOR_RESET}             
               {COLOR_PURPLE}/(((((((((({COLOR_RESET}&&&&&&&&&&   {COLOR_PURPLE}(((,{COLOR_RESET}   &&&&&&      {COLOR_PURPLE}(((**{COLOR_RESET}&&&&&&&&&{COLOR_PURPLE}((((((((((({COLOR_RESET}    {COLOR_YELLOW}Number of trades closed:{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_trades_closed}{COLOR_RESET}
                     &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&          {COLOR_YELLOW}Number of trades open(end of backtest):{COLOR_RESET}{COLOR_GREEN} {backtest_report.number_of_trades_open}{COLOR_RESET}
                            &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&                 {COLOR_YELLOW}Percentage positive trades:{COLOR_RESET}{COLOR_GREEN} {backtest_report.percentage_positive_trades}%{COLOR_RESET}
                              &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&                   {COLOR_YELLOW}Percentage negative trades:{COLOR_RESET}{COLOR_GREEN} {backtest_report.percentage_negative_trades}%{COLOR_RESET}
                     {COLOR_PURPLE}((((({COLOR_RESET}      &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}({COLOR_RESET}                      {COLOR_YELLOW}Average trade size:{COLOR_RESET}{COLOR_GREEN} {backtest_report.average_trade_size:.{precision}f} {backtest_report.trading_symbol}{COLOR_RESET}
                    {COLOR_PURPLE}((((({COLOR_RESET}           &&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE},{COLOR_RESET}                          {COLOR_YELLOW}Average trade duration:{COLOR_RESET}{COLOR_GREEN} {backtest_report.average_trade_duration} hours{COLOR_RESET}
                   {COLOR_PURPLE}((((({COLOR_RESET}                 &&&&&&&&&&&&&{COLOR_PURPLE}#{COLOR_RESET}                            
                  {COLOR_PURPLE}((((({COLOR_RESET}                  #&&&&&&&&&&{COLOR_PURPLE}###{COLOR_RESET}                            
                 {COLOR_PURPLE}((((({COLOR_RESET}                   &&&&&&&&&&&{COLOR_PURPLE}###.{COLOR_RESET}                           
               {COLOR_PURPLE}.((((({COLOR_RESET}                   &&&&&&&&&&&&&&{COLOR_PURPLE}###({COLOR_RESET}                          
              {COLOR_PURPLE}((((({COLOR_RESET}                   &&&&&&&&&&&&&&&&{COLOR_PURPLE}#(((/{COLOR_RESET}                        
             {COLOR_PURPLE}((((({COLOR_RESET}                  &&&&&&&&&&&&&&&&&&&@{COLOR_PURPLE}(((({COLOR_RESET}                       
            {COLOR_PURPLE}((((({COLOR_RESET}                  &&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                      
           {COLOR_PURPLE}((((({COLOR_RESET}                  &&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}((((,{COLOR_RESET}                    
         {COLOR_PURPLE}.((((({COLOR_RESET}                   &&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                    
        {COLOR_PURPLE}((((({COLOR_RESET}                   &&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                   
       {COLOR_PURPLE}((((({COLOR_RESET}                    &&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                  
      {COLOR_PURPLE}((((({COLOR_RESET}                    &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                  
     {COLOR_PURPLE}((((({COLOR_RESET}                     &&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}#(((({COLOR_RESET}                  
     {COLOR_PURPLE}(((((((((((((((((((#########{COLOR_RESET}&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}((((({COLOR_RESET}                  
      {COLOR_PURPLE}(((((((((((((((((((((######{COLOR_RESET}&&&&&&&&&&&&&&&&&&&&&&&&&&&&{COLOR_PURPLE}(((({COLOR_RESET}                   
        """

    print(ascii_art)

    if show_positions:
        print(f"{COLOR_YELLOW}Positions overview{COLOR_RESET}")
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
