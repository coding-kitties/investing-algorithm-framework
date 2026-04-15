import os
import csv
import base64
import webbrowser
import logging
from dataclasses import dataclass, field
from typing import List, Union
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader

from investing_algorithm_framework.domain import (
    Backtest, OperationalException
)

logger = logging.getLogger("investing_algorithm_framework")

STRATEGY_COLORS = [
    "#22d3ee", "#10b981", "#f59e0b", "#a78bfa", "#ef4444",
    "#ec4899", "#3b82f6", "#14b8a6",
]

BENCHMARK_COLORS = [
    '#94a3b8', '#cbd5e1', '#64748b', '#475569', '#e2e8f0',
]
DCA_COLORS = [
    '#a78bfa', '#c4b5fd', '#7c3aed', '#6d28d9', '#ddd6fe',
]
RISK_FREE_COLOR = '#22d3ee'       # cyan-400
EQUAL_WEIGHT_COLOR = '#fb923c'    # orange-400
DEFAULT_RISK_FREE_RATE = 0.04     # 4% annual

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')


def _read_template(filename):
    with open(os.path.join(_TEMPLATE_DIR, filename), 'r') as f:
        return f.read()


def _read_logo_base64(filename):
    logo_dir = os.path.join(
        os.path.dirname(__file__), '..', '..', 'domain',
        'backtesting', 'templates'
    )
    path = os.path.join(logo_dir, filename)
    if not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


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


def _is_na(val):
    """Check whether *val* is a pandas-like NA/NaN sentinel."""
    try:
        import pandas as pd
        if pd.isna(val):
            return True
    except (ImportError, TypeError, ValueError):
        pass
    return False


@dataclass
class BacktestReport:
    backtests: List[Backtest] = field(default_factory=list)
    html_report: str = None
    html_report_path: str = None
    directory_path: str = None
    # Backward compat with old API (backtest: Backtest)
    backtest: object = None
    _source_tags: List[str] = field(
        default_factory=list, repr=False
    )

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
            and os.path.isfile(
                os.path.join(backtest_path, "algorithm_id.json")
            )
            and os.path.isdir(os.path.join(backtest_path, "runs"))
        )

    @staticmethod
    def open(
        backtests: List[Backtest] = None,
        directory_path: Union[str, List[str], None] = None,
    ) -> "BacktestReport":
        loaded = []
        source_tags = []

        if backtests is None:
            backtests = []

        # Normalize directory_path to a list
        if directory_path is not None:
            if isinstance(directory_path, str):
                dir_paths = [directory_path]
            else:
                dir_paths = list(directory_path)
        else:
            dir_paths = []

        for dp in dir_paths:
            tag = os.path.basename(os.path.normpath(dp))
            if BacktestReport._is_backtest(dp):
                loaded.append(Backtest.open(dp))
                source_tags.append(tag)
            else:
                for root, dirs, _ in os.walk(dp):
                    for dir_name in dirs:
                        subdir = os.path.join(
                            root, dir_name
                        )
                        if BacktestReport._is_backtest(
                            subdir
                        ):
                            loaded.append(
                                Backtest.open(subdir)
                            )
                            source_tags.append(tag)

        for bt in backtests:
            if not isinstance(bt, Backtest):
                raise OperationalException(
                    "Provided backtest is not a "
                    "valid Backtest instance."
                )
            loaded.append(bt)
            source_tags.append('')

        if not loaded:
            raise OperationalException(
                f"No valid backtests found "
                f"at {directory_path}."
            )

        # Keep first dir for backward compat
        first_dir = dir_paths[0] if dir_paths else None

        report = BacktestReport(
            backtests=loaded,
            directory_path=first_dir,
        )
        report._source_tags = source_tags
        return report

    # ------------------------------------------------------------------
    # Full HTML assembly
    # ------------------------------------------------------------------

    def _build_html(self):
        if not self.backtests:
            raise OperationalException("No backtests available.")

        css = _read_template('dashboard.css')
        js = _read_template('dashboard.js')
        logo_dark_b64 = _read_logo_base64('finterion-dark.png')
        logo_light_b64 = _read_logo_base64('finterion-light.png')

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
            logo_dark_b64=logo_dark_b64,
            logo_light_b64=logo_light_b64,
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
            benchmarks=self._build_benchmarks_data(),
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

            # Prefer persisted bt.tag, fall back to directory tag
            tag = getattr(bt, 'tag', None) or ''
            if not tag and i < len(self._source_tags):
                tag = self._source_tags[i]

            strategies.append({
                'id': f'strat-{i}',
                'name': algo_name,
                'color': color,
                'tag': tag,
                'summary': summary_dict,
                'repEQ': rep_eq,
                'runIds': run_ids,
                'runNameMap': run_name_map,
                'runLabels': run_labels_list,
                'parameters': bt.parameters or {},
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
                        y = d.year if hasattr(d, 'year') \
                            else int(str(d)[:4])
                        mo = d.month if hasattr(d, 'month') \
                            else int(str(d)[5:7])
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
                        op_dt = t.opened_at
                        cl_dt = t.closed_at
                        total_fees = getattr(t, 'total_fees', 0) or 0
                        trades_list.append({
                            'id': idx_t,
                            'sym': sym,
                            'opened': _fmt_date(op_dt) if op_dt else '',
                            'closed': _fmt_date(cl_dt) if cl_dt else '',
                            'open_price': round(
                                getattr(t, 'open_price', 0) or 0, 2
                            ),
                            'close_price': round(cp, 2),
                            'cost': round(cost, 2),
                            'total_fees': round(total_fees, 4),
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
                        'trades_per_week', 'trades_per_month',
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
                        'average_trade_duration',
                        'average_win_duration',
                        'average_loss_duration',
                        'final_value',
                        'gross_profit', 'gross_loss',
                        'percentage_winning_months',
                        'percentage_winning_years',
                        'median_trade_return',
                        'median_trade_return_percentage',
                        'number_of_positive_trades',
                        'number_of_negative_trades',
                        'percentage_positive_trades',
                        'percentage_negative_trades',
                        'average_monthly_return',
                        'var_95', 'cvar_95',
                        'max_consecutive_wins',
                        'max_consecutive_losses',
                    ):
                        metrics_dict[attr] = getattr(m, attr, None)

                    # Serialize tuple metrics (value, date)
                    for tattr in (
                        'best_month', 'worst_month',
                        'best_year', 'worst_year',
                    ):
                        tval = getattr(m, tattr, None)
                        if (
                            tval
                            and tval[0] is not None
                            and not _is_na(tval[0])
                        ):
                            metrics_dict[tattr] = {
                                'value': tval[0],
                                'date': _fmt_date(tval[1]) if tval[1]
                                else None,
                            }

                # Snapshot: raw portfolio values for Portfolio Summary
                snapshot = {}
                if run.portfolio_snapshots:
                    first = run.portfolio_snapshots[0]
                    last = run.portfolio_snapshots[-1]
                    first_val = getattr(first, 'total_value', 0) or 0
                    last_val = getattr(last, 'total_value', 0) or 0
                    net_gain_raw = last_val - first_val
                    growth_pct = round(
                        (last_val / first_val - 1) * 100, 2
                    ) if first_val else 0
                    snapshot = {
                        'initial_value': round(first_val, 2),
                        'final_value': round(last_val, 2),
                        'net_gain': round(net_gain_raw, 2),
                        'growth': growth_pct,
                        'unallocated': round(
                            getattr(last, 'unallocated', 0) or 0, 2
                        ),
                        'total_net_gain': round(
                            getattr(last, 'total_net_gain', 0) or 0, 2
                        ),
                        'total_revenue': round(
                            getattr(last, 'total_revenue', 0) or 0, 2
                        ),
                        'total_cost': round(
                            getattr(last, 'total_cost', 0) or 0, 2
                        ),
                    }

                # Orders
                orders_list = []
                if run.orders:
                    for o in run.orders:
                        o_dt = getattr(o, 'created_at', None)
                        u_dt = getattr(o, 'updated_at', None)
                        o_fee = getattr(o, 'order_fee', None)
                        if o_fee is None:
                            o_fee = getattr(o, 'fee', 0)
                        o_fee = o_fee or 0
                        o_fee_rate = getattr(
                            o, 'order_fee_rate', 0
                        ) or 0
                        orders_list.append({
                            'sym': getattr(o, 'target_symbol', '')
                            or '',
                            'side': getattr(o, 'order_side', '')
                            or '',
                            'type': getattr(o, 'order_type', '')
                            or '',
                            'status': getattr(o, 'status', '')
                            or '',
                            'price': round(
                                getattr(o, 'price', 0) or 0, 4
                            ),
                            'amount': round(
                                getattr(o, 'amount', 0) or 0, 6
                            ),
                            'filled': round(
                                getattr(o, 'filled', 0) or 0, 6
                            ),
                            'cost': round(
                                (getattr(o, 'amount', 0) or 0)
                                * (getattr(o, 'price', 0) or 0), 2
                            ),
                            'fee': round(float(o_fee), 4),
                            'fee_rate': round(
                                float(o_fee_rate), 4
                            ),
                            'created': _fmt_date(o_dt)
                            if o_dt else '',
                            'updated': _fmt_date(u_dt)
                            if u_dt else '',
                        })

                # Positions
                positions_list = []
                if run.positions:
                    for p in run.positions:
                        positions_list.append({
                            'sym': getattr(p, 'symbol', '') or '',
                            'amount': round(
                                getattr(p, 'amount', 0) or 0, 6
                            ),
                            'cost': round(
                                getattr(p, 'cost', 0) or 0, 2
                            ),
                        })

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
                    'ORDERS': orders_list,
                    'POSITIONS': positions_list,
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

    # ------------------------------------------------------------------
    # Benchmarks  (CSV files from benchmarks/ directory)
    # ------------------------------------------------------------------

    @staticmethod
    def _load_benchmark_csv(filepath):
        """Read a benchmark CSV and return sorted list of (date_str, close)."""
        rows = []
        with open(filepath, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row.get('date', '').strip()
                close = row.get('close', '').strip()
                if not date_str or not close:
                    continue
                try:
                    close_val = float(close)
                except ValueError:
                    continue
                rows.append((date_str, close_val))
        rows.sort(key=lambda r: r[0])
        return rows

    @staticmethod
    def _compute_dca_equity(dates, price_map):
        """Compute a monthly DCA equity curve.

        Simulates investing a fixed amount (1 unit) on the first
        available trading day of each calendar month.  Returns a list
        of ``[pct_return, date_str]`` pairs where *pct_return* is
        ``(portfolio_value / total_invested - 1) * 100``.
        """
        if len(dates) < 2:
            return []

        invest_amount = 1.0
        total_invested = 0.0
        total_units = 0.0
        current_month = None
        eq = []

        for d in dates:
            month_key = d[:7]  # 'YYYY-MM'
            if month_key != current_month:
                current_month = month_key
                price = price_map[d]
                if price > 0:
                    total_units += invest_amount / price
                    total_invested += invest_amount

            price = price_map[d]
            portfolio_value = total_units * price
            if total_invested > 0:
                pct_return = (portfolio_value / total_invested - 1) * 100
            else:
                pct_return = 0.0
            eq.append([pct_return, d])

        return eq

    def _build_benchmarks_data(self):
        """Build benchmark data for JS: normalized % equity per window."""

        # Collect all window date ranges
        windows = {}
        for bt in self.backtests:
            for run in bt.get_all_backtest_runs():
                name = run.backtest_date_range_name or ''
                if name not in windows:
                    windows[name] = {
                        'start': _fmt_date(run.backtest_start_date),
                        'end': _fmt_date(run.backtest_end_date),
                    }

        # ---- CSV-based benchmarks (buy-and-hold + DCA) ----
        benchmarks = []
        # Collect all price maps for equal-weight basket later
        all_price_maps = []

        bench_dir = None
        if self.directory_path:
            bench_dir = os.path.join(self.directory_path, 'benchmarks')
            if not os.path.isdir(bench_dir):
                bench_dir = None

        if bench_dir:
            csv_files = sorted([
                f for f in os.listdir(bench_dir)
                if f.lower().endswith('.csv')
            ])

            for idx, filename in enumerate(csv_files):
                filepath = os.path.join(bench_dir, filename)
                raw = self._load_benchmark_csv(filepath)
                if not raw:
                    continue

                name = os.path.splitext(filename)[0].replace('_', '/')
                color = BENCHMARK_COLORS[idx % len(BENCHMARK_COLORS)]

                # Build a date→close lookup
                price_map = {d: c for d, c in raw}
                all_price_maps.append(price_map)

                # Normalized equity curve for "summary" (full date range)
                all_dates = sorted(price_map.keys())
                if not all_dates:
                    continue
                first_close = price_map[all_dates[0]]
                if first_close == 0:
                    first_close = 1
                summary_eq = [
                    [(price_map[d] / first_close - 1) * 100, d]
                    for d in all_dates
                ]

                # Per-window equity (normalized to window start)
                window_eqs = {}
                for wname, winfo in windows.items():
                    w_start, w_end = winfo['start'], winfo['end']
                    w_dates = [
                        d for d in all_dates if w_start <= d <= w_end
                    ]
                    if len(w_dates) < 2:
                        continue
                    w_first = price_map[w_dates[0]]
                    if w_first == 0:
                        w_first = 1
                    window_eqs[wname] = [
                        [(price_map[d] / w_first - 1) * 100, d]
                        for d in w_dates
                    ]

                # Compute simple CAGR from full range
                if len(all_dates) >= 2:
                    start_p = price_map[all_dates[0]]
                    end_p = price_map[all_dates[-1]]
                    days = (
                        datetime.strptime(all_dates[-1], '%Y-%m-%d')
                        - datetime.strptime(all_dates[0], '%Y-%m-%d')
                    ).days
                    years = days / 365.25 if days > 0 else 1
                    if start_p > 0:
                        cagr = (end_p / start_p) ** (1 / years) - 1
                    else:
                        cagr = 0
                else:
                    cagr = 0

                benchmarks.append({
                    'name': name,
                    'color': color,
                    'summaryEQ': summary_eq,
                    'windowEQ': window_eqs,
                    'cagr': round(cagr, 4),
                    'lineStyle': 'dashed',
                })

                # --- DCA benchmark for the same asset ---
                dca_color = DCA_COLORS[idx % len(DCA_COLORS)]

                dca_summary = self._compute_dca_equity(all_dates, price_map)

                dca_window_eqs = {}
                for wname, winfo in windows.items():
                    w_start, w_end = winfo['start'], winfo['end']
                    w_dates = [
                        d for d in all_dates if w_start <= d <= w_end
                    ]
                    if len(w_dates) < 2:
                        continue
                    dca_window_eqs[wname] = self._compute_dca_equity(
                        w_dates, price_map
                    )

                # Approximate DCA CAGR
                if dca_summary and len(dca_summary) >= 2:
                    final_ret = dca_summary[-1][0] / 100  # fractional
                    first_d = dca_summary[0][1]
                    last_d = dca_summary[-1][1]
                    dca_days = (
                        datetime.strptime(last_d, '%Y-%m-%d')
                        - datetime.strptime(first_d, '%Y-%m-%d')
                    ).days
                    dca_years = dca_days / 365.25 if dca_days > 0 else 1
                    if final_ret > -1:
                        dca_cagr = (1 + final_ret) ** (1 / dca_years) - 1
                    else:
                        dca_cagr = -1
                else:
                    dca_cagr = 0

                benchmarks.append({
                    'name': name + ' DCA',
                    'color': dca_color,
                    'summaryEQ': dca_summary,
                    'windowEQ': dca_window_eqs,
                    'cagr': round(dca_cagr, 4),
                    'lineStyle': 'dotted',
                })

        # ---- Equal-weight basket (average of all CSV benchmarks) ----
        if len(all_price_maps) >= 2:
            benchmarks.extend(
                self._build_equal_weight_basket(
                    all_price_maps, windows
                )
            )

        # ---- Risk-free rate (always generated) ----
        benchmarks.extend(
            self._build_risk_free_benchmark(windows)
        )

        return benchmarks

    def _build_risk_free_benchmark(self, windows):
        """Generate a risk-free rate compounding line from window dates."""
        rate = DEFAULT_RISK_FREE_RATE

        # Collect the full date range across all windows
        all_starts, all_ends = [], []
        for winfo in windows.values():
            all_starts.append(winfo['start'])
            all_ends.append(winfo['end'])

        if not all_starts:
            return []

        global_start = min(all_starts)
        global_end = max(all_ends)

        def _compound_eq(start_str, end_str):
            """Build daily compounding equity from start to end."""
            start_dt = datetime.strptime(start_str, '%Y-%m-%d')
            end_dt = datetime.strptime(end_str, '%Y-%m-%d')
            total_days = (end_dt - start_dt).days
            if total_days <= 0:
                return []
            daily_rate = (1 + rate) ** (1 / 365.25) - 1
            eq = []
            for day_offset in range(total_days + 1):
                dt = start_dt + timedelta(days=day_offset)
                pct = ((1 + daily_rate) ** day_offset - 1) * 100
                eq.append([round(pct, 4), dt.strftime('%Y-%m-%d')])
            return eq

        summary_eq = _compound_eq(global_start, global_end)

        window_eqs = {}
        for wname, winfo in windows.items():
            weq = _compound_eq(winfo['start'], winfo['end'])
            if len(weq) >= 2:
                window_eqs[wname] = weq

        return [{
            'name': f'Risk-Free {rate:.0%}',
            'color': RISK_FREE_COLOR,
            'summaryEQ': summary_eq,
            'windowEQ': window_eqs,
            'cagr': round(rate, 4),
            'lineStyle': 'dotted',
        }]

    @staticmethod
    def _build_equal_weight_basket(price_maps, windows):
        """Generate an equal-weight benchmark from multiple price maps."""
        # Find all dates common to every asset
        date_sets = [set(pm.keys()) for pm in price_maps]
        common_dates = sorted(set.intersection(*date_sets))
        if len(common_dates) < 2:
            return []

        n = len(price_maps)

        def _basket_eq(dates):
            """Normalize each asset to 1.0 on first date, average them."""
            first_prices = [pm[dates[0]] or 1 for pm in price_maps]
            eq = []
            for d in dates:
                total = 0
                for i, pm in enumerate(price_maps):
                    fp = first_prices[i] if first_prices[i] != 0 else 1
                    total += pm[d] / fp
                avg_growth = (total / n - 1) * 100
                eq.append([round(avg_growth, 4), d])
            return eq

        summary_eq = _basket_eq(common_dates)

        window_eqs = {}
        for wname, winfo in windows.items():
            w_dates = [
                d for d in common_dates
                if winfo['start'] <= d <= winfo['end']
            ]
            if len(w_dates) < 2:
                continue
            window_eqs[wname] = _basket_eq(w_dates)

        # CAGR from summary
        if len(summary_eq) >= 2:
            final_ret = summary_eq[-1][0] / 100
            days = (
                datetime.strptime(common_dates[-1], '%Y-%m-%d')
                - datetime.strptime(common_dates[0], '%Y-%m-%d')
            ).days
            years = days / 365.25 if days > 0 else 1
            if final_ret > -1:
                basket_cagr = (1 + final_ret) ** (1 / years) - 1
            else:
                basket_cagr = -1
        else:
            basket_cagr = 0

        return [{
            'name': 'Equal-Weight Basket',
            'color': EQUAL_WEIGHT_COLOR,
            'summaryEQ': summary_eq,
            'windowEQ': window_eqs,
            'cagr': round(basket_cagr, 4),
            'lineStyle': 'dashed',
        }]
