import logging
import os
from pathlib import Path
import webbrowser
from dataclasses import dataclass
from dataclasses import field
from typing import List, Union

import pandas as pd
from IPython import get_ipython
from IPython.display import display, HTML
from jinja2 import Environment, FileSystemLoader

from investing_algorithm_framework.domain import TimeFrame, Backtest, \
    OperationalException, BacktestDateRange
from .charts import get_equity_curve_with_drawdown_chart, \
    get_rolling_sharpe_ratio_chart, get_monthly_returns_heatmap_chart, \
    get_yearly_returns_bar_chart, get_ohlcv_data_completeness_chart
from .tables import create_html_time_metrics_table, \
    create_html_trade_metrics_table, create_html_key_metrics_table, \
    create_html_trades_table

logger = logging.getLogger("investing_algorithm_framework")


def get_symbol_from_file_name(file_name: str) -> str:
    """
    Extract the symbol from the file name.

    Args:
        file_name (str): The file name from which to extract the symbol.

    Returns:
        str: The extracted symbol.
    """
    # Assuming the file name format is "symbol_timeframe.csv"
    return file_name.split('_')[0].upper()

def get_market_from_file_name(file_name: str) -> str:
    """
    Extract the market from the file name.

    Args:
        file_name (str): The file name from which to extract the market.

    Returns:
        str: The extracted market.
    """
    # Assuming the file name format is "symbol_market_timeframe.csv"
    parts = file_name.split('_')
    if len(parts) < 2:
        raise ValueError("File name does not contain a valid market.")
    return parts[1].upper()


def get_time_frame_from_file_name(file_name: str) -> TimeFrame:
    """
    Extract the time frame from the file name.

    Args:
        file_name (str): The file name from which to extract the time frame.

    Returns:
        TimeFrame: The extracted time frame.
    """
    parts = file_name.split('_')

    if len(parts) < 3:
        raise ValueError(
            "File name does not contain a valid time frame."
        )
    time_frame_str = parts[3]

    try:
        return TimeFrame.from_string(time_frame_str)
    except ValueError:
        raise ValueError(
            f"Could not extract time frame from file name: {file_path}. "
            f"Expected format 'OHLCV_<SYMBOL>_<MARKET>_<TIME_FRAME>_<START_DATE>_<END_DATE>.csv', "
            f"got '{time_frame_str}'."
        )


@dataclass
class BacktestReport:
    """
    A class to represent a backtest report. The backtest report contains
    the results of a backtest, including metrics and an HTML report. Also,
    it stores the path to the used strategy directory, which can be used to
    load the strategy code later.

    Attributes:
        html_report (str): The HTML report content.
        html_report_path (str): The file path where the HTML report is saved.
        metrics (dict): A dictionary containing various metrics from the backtest.
        results (BacktestResult): An instance of BacktestResult containing
            the results of the backtest.
        risk_free_rate (float): The risk-free rate used in the backtest.
        strategy_path (str): The path to the strategy directory used in the
            backtest.
    """
    backtest: Backtest = None
    html_report: str = None
    html_report_path: str = None

    def show(
        self,
        backtest_date_range: BacktestDateRange,
        browser: bool = False
    ):
        """
        Display the HTML report in a Jupyter notebook cell.
        """

        if not self.html_report:
            # If the HTML report is not created, create it
            self._create_html_report(backtest_date_range)

        # Save the html report to a tmp location
        path = "/tmp/backtest_report.html"
        with open(path, "w") as html_file:
            html_file.write(self.html_report)

        if browser:
            webbrowser.open(f"file://{path}")

        def in_jupyter_notebook():
            try:
                shell = get_ipython().__class__.__name__
                return shell == 'ZMQInteractiveShell'
            except (NameError, ImportError):
                return False

        if in_jupyter_notebook():
            display(HTML(self.html_report))
        else:
            webbrowser.open(f"file://{path}")

    def _create_html_report(self, backtest_date_range: BacktestDateRange):
        """
        Create an HTML report from the backtest metrics and results.

        This method generates various charts and tables from the backtest
        metrics and results, and renders them into an HTML template using
        Jinja2.

        Raises:
            OperationalException: If no backtests are available to
                create a report.

        Returns:
            None
        """
        # Get the first backtest
        if not self.backtest:
            raise OperationalException(
                "No backtest available to create a report."
            )


        metrics = self.backtest.get_backtest_metrics(backtest_date_range)
        run = self.backtest.get_backtest_run(backtest_date_range)
        # Create plots
        equity_with_drawdown_fig = get_equity_curve_with_drawdown_chart(
            metrics.equity_curve, metrics.drawdown_series
        )
        equity_with_drawdown_plot_html = equity_with_drawdown_fig.to_html(
            full_html=False, include_plotlyjs='cdn',
            config={'responsive': True}, default_width="90%"
        )
        rolling_sharpe_ratio_fig = get_rolling_sharpe_ratio_chart(
            metrics.rolling_sharpe_ratio
        )
        rolling_sharpe_ratio_plot_html = rolling_sharpe_ratio_fig.to_html(
            full_html=False, include_plotlyjs='cdn',
            config={'responsive': True}, default_width="90%"
        )
        monthly_returns_heatmap_fig = get_monthly_returns_heatmap_chart(
            metrics.monthly_returns
        )
        monthly_returns_heatmap_html = monthly_returns_heatmap_fig.to_html(
            full_html=False, include_plotlyjs='cdn',
            config={'responsive': True}
        )
        yearly_returns_histogram_fig = get_yearly_returns_bar_chart(
            metrics.yearly_returns
        )
        yearly_returns_histogram_html = yearly_returns_histogram_fig.to_html(
            full_html=False, include_plotlyjs='cdn',
            config={'responsive': True}
        )

        # Create OHLCV data completeness charts
        data_files = []
        ohlcv_data_completeness_charts_html = ""

        for file in data_files:
            try:
                if file.endswith('.csv'):
                    df = pd.read_csv(file, parse_dates=['Datetime'])
                    file_name = os.path.basename(file)
                    symbol = get_symbol_from_file_name(file_name)
                    market = get_market_from_file_name(file_name)
                    time_frame = get_time_frame_from_file_name(file_name)
                    title = f"OHLCV Data Completeness for {market} - {symbol} - {time_frame.value}"
                    ohlcv_data_completeness_chart_html = \
                        get_ohlcv_data_completeness_chart(
                            df,
                            timeframe=time_frame.value,
                            windowsize=200,
                            title=title
                        )

                    ohlcv_data_completeness_charts_html += (
                        '<div class="ohlcv-data-completeness-chart">'
                        f'{ohlcv_data_completeness_chart_html}'
                        '</div>'
                    )

            except Exception as e:
                logger.warning(
                    "Error creating OHLCV data completeness " +
                    f"chart for {file}: {e}"
                )
                continue

        # Create HTML tables
        key_metrics_table_html = create_html_key_metrics_table(
            metrics, run
        )
        trades_metrics_table_html = create_html_trade_metrics_table(
            metrics, run
        )
        time_metrics_table_html = create_html_time_metrics_table(
            metrics, run
        )
        trades_table_html = create_html_trades_table(run)

        # Jinja2 environment setup
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template('report_template.html.j2')

        # Render template with variables
        html_rendered = template.render(
            report=run,
            equity_with_drawdown_plot_html=equity_with_drawdown_plot_html,
            rolling_sharpe_ratio_plot_html=rolling_sharpe_ratio_plot_html,
            monthly_returns_heatmap_html=monthly_returns_heatmap_html,
            yearly_returns_histogram_html=yearly_returns_histogram_html,
            key_metrics_table_html=key_metrics_table_html,
            trades_metrics_table_html=trades_metrics_table_html,
            time_metrics_table_html=time_metrics_table_html,
            trades_table_html=trades_table_html,
            data_completeness_charts_html=ohlcv_data_completeness_charts_html
        )
        self.html_report = html_rendered

    @staticmethod
    def _load_backtest(backtest_path: str) -> Backtest:
        """
        Load the backtest from a give path
        and return an instance of Backtest.

        Args:
            backtest_path (str): The path to the backtest directory.

        Returns:
            Backtest: An instance of Backtest loaded from the
                backtest directory.
        """
        return Backtest.open(backtest_path)

    @staticmethod
    def _is_backtest(backtest_path: Union[str, Path]) -> bool:
        """
        Check if the given path is a valid backtest report directory.

        Args:
            backtest_path (Union[str, Path]): The path to check.

        Returns:
            bool: True if the path is a valid backtest report directory,
                False otherwise.
        """
        return (
            os.path.exists(backtest_path) and
            os.path.isdir(backtest_path) and
            os.path.isfile(os.path.join(backtest_path, "results.json"))
            and os.path.isfile(os.path.join(backtest_path, "metrics.json"))
        )

    @staticmethod
    def open(
        backtests: List[Backtest] = [],
        directory_path=None
    ) -> "BacktestReport":
        """
        Open the backtest report from a file.

        Args:
            backtests (List[Backtest], optional): A list of Backtest instances
                to include in the report. If provided, it will use these
                backtests as part of the report.
            directory_path (str, optional): The directory path from
                which the reports will be loaded.

        Returns:
            BacktestReport: An instance of BacktestReport loaded from the file.

        Raises:
            OperationalException: If the backtest path is not a valid backtest
                report directory.
        """
        loaded_backtests = []

        if directory_path is not None:
            # Check if the directory is a valid backtest report directory
            if BacktestReport._is_backtest(directory_path):
                backtests.append(
                    Backtest.open(directory_path)
                )
            else:
                # Loop over all subdirectories
                for root, dirs, _ in os.walk(directory_path):
                    for dir_name in dirs:
                        subdir_path = os.path.join(root, dir_name)
                        if BacktestReport._is_backtest(subdir_path):
                            loaded_backtests.append(
                                Backtest.open(directory_path=subdir_path)
                            )

        if len(backtests) > 0:

            for backtest in backtests:
                if not isinstance(backtest, Backtest):
                    raise OperationalException(
                        "The provided backtest is not a valid Backtest instance."
                    )

            # Add the backtests to the backtests list
            loaded_backtests.extend(backtests)

        if len(loaded_backtests) == 0:
            raise OperationalException(
                f"The directory {directory_path} is not a valid backtest report."
            )

        return BacktestReport(backtest=loaded_backtests)
