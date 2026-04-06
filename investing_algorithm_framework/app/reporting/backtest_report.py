import os
import webbrowser
import logging
from dataclasses import dataclass, field
from typing import List, Union
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from investing_algorithm_framework.domain import (
    Backtest, OperationalException
)

logger = logging.getLogger("investing_algorithm_framework")

STRATEGY_COLORS = [
    "#22d3ee", "#10b981", "#f59e0b", "#a78bfa", "#ef4444",
    "#ec4899", "#3b82f6", "#14b8a6",
]

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')


def _read_template(filename):
    with open(os.path.join(_TEMPLATE_DIR, filename), 'r') as f:
        return f.read()


def _filter_pct(v):
    """Format as signed percentage: 0.15 → '+15.0%', None → 'N/A'."""
    if v is None:
        return 'N/A'
    return f"+{v * 100:.1f}%" if v >= 0 else f"{v * 100:.1f}%"


def _filter_ratio(v):
    """Format as ratio: 1.234 → '1.23', None → 'N/A'."""
    if v is None:
        return 'N/A'
    return f"{v:.2f}"


def _filter_abs_pct(v):
    """Format as absolute percentage: -0.15 → '15.0%', None → 'N/A'."""
    if v is None:
        return 'N/A'
    return f"{abs(v) * 100:.1f}%"


def _fmt_date(dt):
    if isinstance(dt, str):
        return dt
    return dt.strftime('%Y-%m-%d')


@dataclass
class BacktestReport:
    backtests: List[Backtest] = field(default_factory=list)
    html_report: str = None
    html_report_path: str = None
    # Backward compat with old API (backtest: Backtest)
    backtest: object = None

    def __post_init__(self):
        # Handle single Backtest passed as first positional arg:
        #   BacktestReport(backtest)
        if self.backtests and not isinstance(self.backtests, list):
            self.backtests = [self.backtests]
        # Handle backward compat: backtest=single or backtest=[list]
        if self.backtest is not None and not self.backtests:
            if isinstance(self.backtest, list):
                self.backtests = self.backtest
            else:
                self.backtests = [self.backtest]
            self.backtest = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self, backtest_date_range=None, browser=False):
        if not self.html_report:
            self.html_report = self._build_html()

        path = "/tmp/backtest_report.html"
        with open(path, "w") as f:
            f.write(self.html_report)

        try:
            from IPython import get_ipython
            shell = get_ipython().__class__.__name__
            if shell == 'ZMQInteractiveShell':
                from IPython.display import display, HTML
                display(HTML(self.html_report))
                if not browser:
                    return
        except (NameError, ImportError):
            pass

        webbrowser.open(f"file://{path}")

    def save(self, path):
        if not self.html_report:
            self.html_report = self._build_html()
        with open(path, "w") as f:
            f.write(self.html_report)

    @staticmethod
    def _is_backtest(backtest_path):
        return (
            os.path.exists(backtest_path)
            and os.path.isdir(backtest_path)
            and os.path.isfile(os.path.join(backtest_path, "algorithm_id.json"))
            and os.path.isdir(os.path.join(backtest_path, "runs"))
        )

    @staticmethod
    def open(
        backtests: List[Backtest] = None,
        directory_path=None,
    ) -> "BacktestReport":
        loaded = []

        if backtests is None:
            backtests = []

        if directory_path is not None:
            if BacktestReport._is_backtest(directory_path):
                loaded.append(Backtest.open(directory_path))
            else:
                for root, dirs, _ in os.walk(directory_path):
                    for dir_name in dirs:
                        subdir = os.path.join(root, dir_name)
                        if BacktestReport._is_backtest(subdir):
                            loaded.append(Backtest.open(subdir))

        for bt in backtests:
            if not isinstance(bt, Backtest):
                raise OperationalException(
                    "Provided backtest is not a valid Backtest instance."
                )
            loaded.append(bt)

        if not loaded:
            raise OperationalException(
                f"No valid backtests found at {directory_path}."
            )

        return BacktestReport(backtests=loaded)

    # ------------------------------------------------------------------
    # Full HTML assembly
    # ------------------------------------------------------------------

    def _build_html(self):
        if not self.backtests:
            raise OperationalException("No backtests available.")

        css = _read_template('dashboard.css')
        js = _read_template('dashboard.js')

        is_single = len(self.backtests) == 1
        strategies = self._build_strategies_data()
        run_data = self._build_run_data()
        windows_meta = self._build_windows_meta()
        run_labels = self._build_run_labels()

        # Pre-compute overview KPIs
        best_cagr = {'v': None, 'n': ''}
        best_sharpe = {'v': None, 'n': ''}
        best_sortino = {'v': None, 'n': ''}
        best_calmar = {'v': None, 'n': ''}
        best_win_rate = {'v': None, 'n': ''}
        lowest_dd = {'v': None, 'n': ''}
        for s in strategies:
            sm = s.get('summary', {})
            c = sm.get('cagr')
            sh = sm.get('sharpe_ratio')
            so = sm.get('sortino_ratio')
            ca = sm.get('calmar_ratio')
            wr = sm.get('win_rate')
            dd = sm.get('max_drawdown')
            if c is not None and (
                best_cagr['v'] is None or c > best_cagr['v']
            ):
                best_cagr = {'v': c, 'n': s['name']}
            if sh is not None and (
                best_sharpe['v'] is None or sh > best_sharpe['v']
            ):
                best_sharpe = {'v': sh, 'n': s['name']}
            if so is not None and (
                best_sortino['v'] is None or so > best_sortino['v']
            ):
                best_sortino = {'v': so, 'n': s['name']}
            if ca is not None and (
                best_calmar['v'] is None or ca > best_calmar['v']
            ):
                best_calmar = {'v': ca, 'n': s['name']}
            if wr is not None and (
                best_win_rate['v'] is None or wr > best_win_rate['v']
            ):
                best_win_rate = {'v': wr, 'n': s['name']}
            if dd is not None and (
                lowest_dd['v'] is None or dd < lowest_dd['v']
            ):
                lowest_dd = {'v': dd, 'n': s['name']}

        strat_names = ' \u00b7 '.join(s['name'] for s in strategies)
        title = 'Backtest Report' if is_single else 'Strategy Comparison'

        env = Environment(
            loader=FileSystemLoader(_TEMPLATE_DIR),
            autoescape=False,
        )
        env.filters['pct'] = _filter_pct
        env.filters['ratio'] = _filter_ratio
        env.filters['abs_pct'] = _filter_abs_pct
        template = env.get_template('dashboard_template.html.j2')

        return template.render(
            title=title,
            css=css,
            js=js,
            is_single=is_single,
            strategies=strategies,
            run_data=run_data,
            windows_meta=windows_meta,
            run_labels=run_labels,
            strat_names=strat_names,
            best_cagr=best_cagr,
            best_sharpe=best_sharpe,
            best_sortino=best_sortino,
            best_calmar=best_calmar,
            best_win_rate=best_win_rate,
            lowest_dd=lowest_dd,
        )

    # ------------------------------------------------------------------
    # Data transformation  (Python Backtest → JS data structures)
    # ------------------------------------------------------------------

    def _build_strategies_data(self):
        strategies = []

        for i, bt in enumerate(self.backtests):
            color = STRATEGY_COLORS[i % len(STRATEGY_COLORS)]
            runs = bt.get_all_backtest_runs()

            # Summary metrics
            summary_dict = {}
            if bt.backtest_summary is not None:
                summary_dict = bt.backtest_summary.to_dict()

            # Representative equity curve (first run, as % growth)
            rep_eq = []
            if runs:
                first_metrics = runs[0].backtest_metrics
                if first_metrics and first_metrics.equity_curve:
                    ec = first_metrics.equity_curve
                    initial = ec[0][0] if ec else 1
                    if initial == 0:
                        initial = 1
                    rep_eq = [
                        [(v / initial - 1) * 100, _fmt_date(d)]
                        for v, d in ec
                    ]

            # Run IDs / mappings / labels
            run_ids, run_name_map, run_labels_list = [], {}, []
            for j, run in enumerate(runs):
                rid = f"run-{i}-{j}"
                run_ids.append(rid)
                name = run.backtest_date_range_name or f"run_{j}"
                ts = getattr(run, 'trading_symbol', 'EUR') or 'EUR'
                label = (
                    f"{ts} {_fmt_date(run.backtest_start_date)} "
                    f"\u2192 {_fmt_date(run.backtest_end_date)}"
                )
                run_name_map[name] = rid
                run_labels_list.append([name, label])

            algo_name = bt.algorithm_id or f"strategy_{i}"
            if len(algo_name) > 8:
                algo_name = algo_name[:8]

            strategies.append({
                'id': f'strat-{i}',
                'name': algo_name,
                'color': color,
                'summary': summary_dict,
                'repEQ': rep_eq,
                'runIds': run_ids,
                'runNameMap': run_name_map,
                'runLabels': run_labels_list,
            })

        return strategies

    def _build_run_data(self):
        run_data = {}

        for i, bt in enumerate(self.backtests):
            runs = bt.get_all_backtest_runs()

            for j, run in enumerate(runs):
                rid = f"run-{i}-{j}"
                m = run.backtest_metrics
                ts = getattr(run, 'trading_symbol', 'EUR') or 'EUR'
                label = (
                    f"{ts} {_fmt_date(run.backtest_start_date)} "
                    f"\u2192 {_fmt_date(run.backtest_end_date)}"
                )

                # Equity curve → % growth
                eq, initial = [], 1
                if m and m.equity_curve:
                    initial = m.equity_curve[0][0] or 1
                    eq = [
                        [(v / initial - 1) * 100, _fmt_date(d)]
                        for v, d in m.equity_curve
                    ]

                # Drawdown series
                dd = []
                if m and m.drawdown_series:
                    dd = [
                        [v * 100 if abs(v) < 1 else v, _fmt_date(d)]
                        for v, d in m.drawdown_series
                    ]

                # Rolling Sharpe
                rs = []
                if m and m.rolling_sharpe_ratio:
                    rs = [
                        [v, _fmt_date(d)]
                        for v, d in m.rolling_sharpe_ratio
                    ]

                # Monthly returns
                mr = []
                if m and m.monthly_returns:
                    mr = [
                        [v, _fmt_date(d)]
                        for v, d in m.monthly_returns
                    ]

                # Yearly returns
                yr = []
                if m and m.yearly_returns:
                    yr = [
                        [v, str(d.year) if hasattr(d, 'year') else str(d)]
                        for v, d in m.yearly_returns
                    ]

                # Monthly heatmap  {year: {month: pct}}
                heatmap = {}
                if m and m.monthly_returns:
                    for v, d in m.monthly_returns:
                        y = d.year if hasattr(d, 'year') else int(str(d)[:4])
                        mo = d.month if hasattr(d, 'month') else int(str(d)[5:7])
                        heatmap.setdefault(y, {})[mo] = round(
                            v * 100 if abs(v) < 1 else v, 2
                        )

                # Trades
                trades_list, sym_stats = [], {}
                if run.trades:
                    for idx_t, t in enumerate(run.trades):
                        sym = getattr(t, 'target_symbol', '') or ''
                        cost = getattr(t, 'cost', 0) or 0
                        ng = getattr(t, 'net_gain', 0) or 0
                        cp = 0
                        if hasattr(t, 'closed_prices') and t.closed_prices:
                            cp = t.closed_prices[-1]
                        elif hasattr(t, 'last_reported_price'):
                            cp = t.last_reported_price or 0
                        pct = (ng / cost * 100) if cost else 0
                        trades_list.append({
                            'id': idx_t,
                            'sym': sym,
                            'opened': _fmt_date(t.opened_at) if t.opened_at else '',
                            'closed': _fmt_date(t.closed_at) if t.closed_at else '',
                            'open_price': round(getattr(t, 'open_price', 0) or 0, 2),
                            'close_price': round(cp, 2),
                            'cost': round(cost, 2),
                            'net_gain': round(ng, 2),
                            'pct': round(pct, 2),
                        })
                        sym_stats.setdefault(sym, {'count': 0, 'gain': 0})
                        sym_stats[sym]['count'] += 1
                        sym_stats[sym]['gain'] = round(
                            sym_stats[sym]['gain'] + ng, 2
                        )

                # Scalar metrics
                metrics_dict = {}
                if m:
                    for attr in (
                        'cagr', 'sharpe_ratio', 'sortino_ratio',
                        'calmar_ratio', 'profit_factor',
                        'annual_volatility', 'max_drawdown',
                        'max_drawdown_duration', 'trades_per_year',
                        'win_rate', 'current_win_rate',
                        'win_loss_ratio', 'current_win_loss_ratio',
                        'number_of_trades', 'number_of_trades_closed',
                        'cumulative_exposure', 'exposure_ratio',
                        'total_net_gain', 'total_net_gain_percentage',
                        'total_growth', 'total_growth_percentage',
                        'total_loss', 'average_trade_return',
                        'average_trade_return_percentage',
                        'average_trade_loss',
                        'average_trade_loss_percentage',
                        'average_trade_gain',
                        'average_trade_gain_percentage',
                        'max_drawdown_absolute', 'max_daily_drawdown',
                    ):
                        metrics_dict[attr] = getattr(m, attr, None)

                # Snapshot
                snapshot = {}
                if run.portfolio_snapshots:
                    last = run.portfolio_snapshots[-1]
                    tv = getattr(last, 'total_value', 0) or 0
                    snapshot = {
                        'equity': tv,
                        'unallocated': getattr(last, 'unallocated', 0) or 0,
                        'net_profit': getattr(last, 'total_net_gain', 0) or 0,
                        'growth': round(
                            (tv / initial - 1) * 100, 2
                        ) if initial else 0,
                    }

                run_data[rid] = {
                    'label': label,
                    'EQ': eq,
                    'DD': dd,
                    'CR': eq,
                    'RS': rs,
                    'MR': mr,
                    'YR': yr,
                    'MONTHLY_HEATMAP': heatmap,
                    'TRADES': trades_list,
                    'SYM_STATS': sym_stats,
                    'metrics': metrics_dict,
                    'snapshot': snapshot,
                }

        return run_data

    def _build_windows_meta(self):
        windows = {}
        for bt in self.backtests:
            for run in bt.get_all_backtest_runs():
                name = run.backtest_date_range_name or ''
                if name not in windows:
                    ts = getattr(run, 'trading_symbol', 'EUR') or 'EUR'
                    s = _fmt_date(run.backtest_start_date)
                    e = _fmt_date(run.backtest_end_date)
                    days = (
                        run.backtest_end_date - run.backtest_start_date
                    ).days
                    windows[name] = {
                        'label': f"{ts} {s} \u2192 {e}",
                        'start': s,
                        'end': e,
                        'days': days,
                        'n_strategies': 0,
                    }
                windows[name]['n_strategies'] += 1
        return list(windows.values())

    def _build_run_labels(self):
        labels, seen = [], set()
        for bt in self.backtests:
            for run in bt.get_all_backtest_runs():
                name = run.backtest_date_range_name or ''
                if name not in seen:
                    ts = getattr(run, 'trading_symbol', 'EUR') or 'EUR'
                    s = _fmt_date(run.backtest_start_date)
                    e = _fmt_date(run.backtest_end_date)
                    labels.append([name, f"{ts} {s} \u2192 {e}"])
                    seen.add(name)
        return labels
