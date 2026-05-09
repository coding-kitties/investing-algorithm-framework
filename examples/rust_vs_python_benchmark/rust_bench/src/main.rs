//! Reference Rust backtest sweep — minimal end-to-end equivalent of
//! `python_bench.py`. Loads parquet OHLCV files, runs an EMA + RSI
//! crossover strategy across a parameter sweep on N symbols, and
//! prints throughput as JSON.
//!
//! This is the **best-case ceiling** for what an `iaf-core` Rust
//! kernel could achieve. The Python side carries the full framework
//! (data providers, strategy lifecycle, bundle write, metric
//! aggregation). The gap between the two is the optimization
//! headroom for issues #521–#526.

use std::path::{Path, PathBuf};
use std::time::Instant;

use anyhow::{Context as _, Result};
use clap::Parser;
use polars::prelude::*;
use rayon::prelude::*;
use rusqlite::{params, Connection};
use serde::Serialize;

const SYMBOLS: &[&str] = &["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "DOT-USD"];

#[derive(Parser, Debug)]
#[command(about = "Rust reference backtest sweep")]
struct Args {
    #[arg(long, default_value_t = 25)]
    combos: usize,
    #[arg(long, default_value_t = 10.0)]
    years: f64,
    /// 0 = use all logical CPUs.
    #[arg(long, default_value_t = 0)]
    workers: usize,
    #[arg(long, default_value = "../data")]
    data_dir: PathBuf,
    #[arg(long, default_value = "../results/rust_bench.json")]
    results_file: PathBuf,
    /// Persist every order + per-bar portfolio snapshot to a per-backtest
    /// SQLite database (mirrors the Python framework's behavior).
    #[arg(long, default_value_t = true, action = clap::ArgAction::Set)]
    persist: bool,
    /// Compute the standard metric pack (total return, CAGR, vol, Sharpe,
    /// Sortino, max drawdown + duration, Calmar) over the per-bar equity
    /// series of every backtest. Mirrors `BacktestMetrics` in the Python
    /// framework. Disable with `--metrics false` to isolate pure compute.
    #[arg(long, default_value_t = true, action = clap::ArgAction::Set)]
    metrics: bool,
    /// Annualisation factor for risk metrics. Defaults to hourly bars
    /// (24 * 365 = 8760), matching the synthetic data we generate.
    #[arg(long, default_value_t = 8760.0)]
    bars_per_year: f64,
    /// Annual risk-free rate used by Sharpe / Sortino. Same default as
    /// the framework (0%).
    #[arg(long, default_value_t = 0.0)]
    risk_free_rate: f64,
    /// Directory for per-backtest `.sqlite3` files (one per strategy).
    #[arg(long, default_value = "../results/rust_dbs")]
    db_dir: PathBuf,
}

#[derive(Clone, Copy, Debug)]
struct Params {
    ema_short: usize,
    ema_long: usize,
    rsi_period: usize,
    rsi_oversold: f64,
    rsi_overbought: f64,
}

#[derive(Serialize)]
struct BenchSummary {
    implementation: &'static str,
    persist: bool,
    metrics: bool,
    n_strategies: usize,
    n_symbols: usize,
    n_backtests: usize,
    years: f64,
    workers: usize,
    elapsed_seconds: f64,
    throughput_backtests_per_second: f64,
    wall_clock_per_backtest_ms: f64,
}

/// Open a per-backtest SQLite DB with the same kind of tables the
/// framework persists (orders + portfolio snapshots). PRAGMAs match a
/// reasonable "backtest write-heavy" config: WAL + NORMAL sync, which
/// is roughly what SQLAlchemy gives us out of the box on a fresh file.
fn open_backtest_db(path: &Path) -> Result<Connection> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    if path.exists() {
        std::fs::remove_file(path).ok();
    }
    let conn = Connection::open(path)?;
    conn.execute_batch(
        r#"
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;
        PRAGMA temp_store = MEMORY;
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL,
            fee REAL NOT NULL,
            bar_index INTEGER NOT NULL
        );
        CREATE TABLE portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            bar_index INTEGER NOT NULL,
            unallocated REAL NOT NULL,
            position_units REAL NOT NULL,
            total_value REAL NOT NULL
        );
        CREATE TABLE backtest_metrics (
            name TEXT PRIMARY KEY,
            value REAL
        );
        "#,
    )?;
    Ok(conn)
}

fn build_param_grid(n: usize) -> Vec<Params> {
    // Same deterministic enumeration as python_bench so results are
    // comparable: same seed, same candidate sets, same uniqueness rule.
    let short_choices = [10usize, 15, 20, 25, 30];
    let long_choices = [50usize, 75, 100, 150, 200];
    let rsi_periods = [7usize, 14, 21];
    let rsi_oversold = [25.0, 30.0, 35.0];
    let rsi_overbought = [65.0, 70.0, 75.0];

    // tiny xorshift seeded with 0 to mirror numpy default_rng(0) ordering
    // closely enough for benchmarking purposes (we only need *some*
    // realistic spread of params, not bit-identical to Python).
    let mut state: u64 = 0xDEAD_BEEF_CAFE_BABE;
    let mut next = || {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        state
    };
    let pick = |state: &mut dyn FnMut() -> u64, n: usize| -> usize {
        (state() as usize) % n
    };

    let mut grid: Vec<Params> = Vec::with_capacity(n);
    let mut seen = std::collections::HashSet::new();
    while grid.len() < n {
        let es = short_choices[pick(&mut next, short_choices.len())];
        let el = long_choices[pick(&mut next, long_choices.len())];
        if el <= es {
            continue;
        }
        let rp = rsi_periods[pick(&mut next, rsi_periods.len())];
        let ro = rsi_oversold[pick(&mut next, rsi_oversold.len())];
        let rb = rsi_overbought[pick(&mut next, rsi_overbought.len())];
        let key = (es, el, rp, ro as i64, rb as i64);
        if !seen.insert(key) {
            continue;
        }
        grid.push(Params {
            ema_short: es,
            ema_long: el,
            rsi_period: rp,
            rsi_oversold: ro,
            rsi_overbought: rb,
        });
    }
    grid
}

fn load_close(path: &std::path::Path, last_n: usize) -> Result<(Vec<f64>, Vec<f64>)> {
    let df = LazyFrame::scan_parquet(path, ScanArgsParquet::default())?
        .select([col("Open"), col("Close")])
        .collect()
        .with_context(|| format!("scan_parquet({:?})", path))?;

    let opens = df.column("Open")?.f64()?.into_no_null_iter().collect::<Vec<_>>();
    let closes = df.column("Close")?.f64()?.into_no_null_iter().collect::<Vec<_>>();

    let len = closes.len();
    let start = len.saturating_sub(last_n);
    Ok((opens[start..].to_vec(), closes[start..].to_vec()))
}

/// EMA seeded with the first close (matches pandas `ewm(span=p, adjust=False)`
/// well enough for benchmark purposes; final equity drift vs python should
/// be small).
fn ema(values: &[f64], period: usize) -> Vec<f64> {
    let alpha = 2.0 / (period as f64 + 1.0);
    let mut out = Vec::with_capacity(values.len());
    if values.is_empty() {
        return out;
    }
    let mut prev = values[0];
    out.push(prev);
    for &v in &values[1..] {
        prev = alpha * v + (1.0 - alpha) * prev;
        out.push(prev);
    }
    out
}

/// Wilder RSI. NaN-equivalent values are clamped to 50 (neutral) so a
/// naive sweep does not generate spurious signals during warmup.
fn rsi(values: &[f64], period: usize) -> Vec<f64> {
    let n = values.len();
    let mut out = vec![50.0; n];
    if n < period + 1 {
        return out;
    }
    let alpha = 1.0 / period as f64;
    let mut avg_gain = 0.0;
    let mut avg_loss = 0.0;
    for i in 1..n {
        let delta = values[i] - values[i - 1];
        let gain = delta.max(0.0);
        let loss = (-delta).max(0.0);
        if i == 1 {
            avg_gain = gain;
            avg_loss = loss;
        } else {
            avg_gain = alpha * gain + (1.0 - alpha) * avg_gain;
            avg_loss = alpha * loss + (1.0 - alpha) * avg_loss;
        }
        let rs = if avg_loss > 0.0 { avg_gain / avg_loss } else { 0.0 };
        out[i] = 100.0 - 100.0 / (1.0 + rs);
    }
    out
}

#[derive(Default)]
struct BacktestStats {
    final_equity: f64,
    trades: usize,
    wins: usize,
    /// Per-bar portfolio equity (cash + mark-to-market) for this symbol.
    /// Always populated; the per-backtest equity curve is the bar-wise
    /// sum across symbols and is what the metric pack is computed on.
    equity: Vec<f64>,
}

/// Metric pack mirroring the framework's `BacktestMetrics`. Values are
/// computed once per backtest over the per-bar portfolio equity curve
/// (sum of all symbols' equity at each bar).
#[derive(Debug, Default, Serialize)]
struct BacktestMetrics {
    total_return_pct: f64,
    cagr: f64,
    annual_volatility: f64,
    sharpe_ratio: f64,
    sortino_ratio: f64,
    max_drawdown: f64,
    max_drawdown_duration_bars: usize,
    calmar_ratio: f64,
}

fn compute_metrics(
    equity: &[f64],
    bars_per_year: f64,
    risk_free_rate: f64,
    years: f64,
) -> BacktestMetrics {
    let n = equity.len();
    if n < 2 {
        return BacktestMetrics::default();
    }
    let start = equity[0].max(1e-12);
    let end = *equity.last().unwrap();
    let total_return = end / start - 1.0;

    // Per-bar log returns
    let mut returns: Vec<f64> = Vec::with_capacity(n - 1);
    for i in 1..n {
        let prev = equity[i - 1];
        if prev > 0.0 {
            returns.push(equity[i] / prev - 1.0);
        } else {
            returns.push(0.0);
        }
    }

    let mean: f64 = returns.iter().sum::<f64>() / returns.len() as f64;
    let var: f64 =
        returns.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / returns.len() as f64;
    let std = var.sqrt();
    let annual_vol = std * bars_per_year.sqrt();

    // CAGR over the actual elapsed years
    let cagr = if years > 0.0 && start > 0.0 && end > 0.0 {
        (end / start).powf(1.0 / years) - 1.0
    } else {
        0.0
    };

    // Sharpe: (mean_excess_return * bars_per_year) / annual_vol
    let rf_per_bar = risk_free_rate / bars_per_year;
    let mean_excess = mean - rf_per_bar;
    let sharpe = if annual_vol > 0.0 {
        (mean_excess * bars_per_year) / annual_vol
    } else {
        0.0
    };

    // Sortino: only count downside deviation
    let downside: f64 = returns
        .iter()
        .map(|r| if *r < rf_per_bar { (r - rf_per_bar).powi(2) } else { 0.0 })
        .sum::<f64>()
        / returns.len() as f64;
    let downside_std = downside.sqrt() * bars_per_year.sqrt();
    let sortino = if downside_std > 0.0 {
        (mean_excess * bars_per_year) / downside_std
    } else {
        0.0
    };

    // Max drawdown + duration (single pass over the equity curve)
    let mut peak = equity[0];
    let mut peak_idx = 0usize;
    let mut max_dd = 0.0_f64;
    let mut max_dd_dur = 0usize;
    for (i, &v) in equity.iter().enumerate() {
        if v > peak {
            peak = v;
            peak_idx = i;
        }
        if peak > 0.0 {
            let dd = (v - peak) / peak; // negative
            if dd < max_dd {
                max_dd = dd;
            }
        }
        let dur = i - peak_idx;
        if dur > max_dd_dur {
            max_dd_dur = dur;
        }
    }

    let calmar = if max_dd < 0.0 { cagr / -max_dd } else { 0.0 };

    BacktestMetrics {
        total_return_pct: total_return,
        cagr,
        annual_volatility: annual_vol,
        sharpe_ratio: sharpe,
        sortino_ratio: sortino,
        max_drawdown: max_dd,
        max_drawdown_duration_bars: max_dd_dur,
        calmar_ratio: calmar,
    }
}

/// Run one symbol's worth of the backtest. Fees + slippage are charged
/// on entry and exit. Long-only, single-position-per-symbol.
///
/// When `persist` is true, every executed order and every per-bar
/// portfolio snapshot is written through the supplied prepared
/// statements. The caller is expected to have wrapped these in a
/// single SQLite transaction.
fn run_one_symbol(
    symbol: &str,
    opens: &[f64],
    closes: &[f64],
    p: &Params,
    capital: f64,
    persist: Option<&mut PersistStmts<'_>>,
) -> BacktestStats {
    let ema_s = ema(closes, p.ema_short);
    let ema_l = ema(closes, p.ema_long);
    let rsi_v = rsi(closes, p.rsi_period);

    const FEE: f64 = 0.001; // 0.1%
    const SLIP: f64 = 0.0005; // 0.05%

    let mut cash = capital;
    let mut units = 0.0_f64;
    let mut entry_value: f64 = 0.0;
    let mut wins = 0usize;
    let mut trades = 0usize;

    let n = closes.len();
    if n < 3 {
        return BacktestStats {
            final_equity: cash,
            trades,
            wins,
            equity: vec![cash; n],
        };
    }

    let mut persist = persist;
    let mut equity = Vec::with_capacity(n);
    // Bars 0 and 1 are warmup (no signal yet); record initial cash.
    equity.push(cash);
    equity.push(cash);

    for i in 2..n {
        // Use previous bar's signal, fill at this bar's open
        let cross_over =
            ema_s[i - 1] > ema_l[i - 1] && ema_s[i - 2] <= ema_l[i - 2];
        let cross_under =
            ema_s[i - 1] < ema_l[i - 1] && ema_s[i - 2] >= ema_l[i - 2];
        let buy = cross_over && rsi_v[i - 1] < p.rsi_oversold && units == 0.0;
        let sell = cross_under && rsi_v[i - 1] > p.rsi_overbought && units > 0.0;
        let fill = opens[i];
        if buy {
            let exec_price = fill * (1.0 + SLIP);
            let notional = cash;
            let fee = notional * FEE;
            let invest = notional - fee;
            units = invest / exec_price;
            cash = 0.0;
            entry_value = invest;
            if let Some(ps) = persist.as_deref_mut() {
                ps.order
                    .execute(params![symbol, "buy", exec_price, units, fee, i as i64])
                    .ok();
            }
        } else if sell {
            let exec_price = fill * (1.0 - SLIP);
            let proceeds = units * exec_price;
            let fee = proceeds * FEE;
            cash = proceeds - fee;
            if cash > entry_value {
                wins += 1;
            }
            trades += 1;
            if let Some(ps) = persist.as_deref_mut() {
                ps.order
                    .execute(params![symbol, "sell", exec_price, units, fee, i as i64])
                    .ok();
            }
            units = 0.0;
            entry_value = 0.0;
        }

        let total_value = cash + units * closes[i];
        equity.push(total_value);
        if let Some(ps) = persist.as_deref_mut() {
            ps.snap
                .execute(params![symbol, i as i64, cash, units, total_value])
                .ok();
        }
    }

    // Mark to market at final close
    let final_equity = cash + units * closes[n - 1];
    BacktestStats { final_equity, trades, wins, equity }
}

/// Prepared statements for the hot inner loop. Borrowed from a
/// transaction so all writes commit atomically when it drops.
struct PersistStmts<'a> {
    order: rusqlite::Statement<'a>,
    snap: rusqlite::Statement<'a>,
}

fn run_one_backtest(
    backtest_idx: usize,
    symbols_data: &[(String, Vec<f64>, Vec<f64>)],
    p: &Params,
    capital_per_symbol: f64,
    db_dir: Option<&Path>,
    metrics_cfg: Option<MetricsCfg>,
) -> BacktestStats {
    let mut total_equity = 0.0;
    let mut total_trades = 0;
    let mut total_wins = 0;
    let mut portfolio_curve: Vec<f64> = Vec::new();

    let merge = |portfolio_curve: &mut Vec<f64>, sym_eq: &[f64]| {
        if portfolio_curve.is_empty() {
            portfolio_curve.extend_from_slice(sym_eq);
        } else {
            let m = portfolio_curve.len().min(sym_eq.len());
            for i in 0..m {
                portfolio_curve[i] += sym_eq[i];
            }
        }
    };

    if let Some(dir) = db_dir {
        // Persisting path: one SQLite file per backtest, all writes in
        // a single transaction (matches typical SQLAlchemy session use).
        let path = dir.join(format!("backtest_{:04}.sqlite3", backtest_idx));
        let mut conn = open_backtest_db(&path).expect("open backtest db");
        let tx = conn.transaction().expect("begin tx");
        {
            let mut ps = PersistStmts {
                order: tx
                    .prepare(
                        "INSERT INTO orders (symbol, side, price, amount, fee, bar_index) \
                         VALUES (?, ?, ?, ?, ?, ?)",
                    )
                    .expect("prep order"),
                snap: tx
                    .prepare(
                        "INSERT INTO portfolio_snapshots \
                         (symbol, bar_index, unallocated, position_units, total_value) \
                         VALUES (?, ?, ?, ?, ?)",
                    )
                    .expect("prep snap"),
            };
            for (sym, opens, closes) in symbols_data {
                let stats = run_one_symbol(sym, opens, closes, p, capital_per_symbol, Some(&mut ps));
                total_equity += stats.final_equity;
                total_trades += stats.trades;
                total_wins += stats.wins;
                merge(&mut portfolio_curve, &stats.equity);
            }
        }
        // Compute and persist metrics inside the same transaction so the
        // "backtest write cost" we measure includes the metric round-trip
        // (Python framework writes metrics too).
        if let Some(cfg) = metrics_cfg {
            let m = compute_metrics(
                &portfolio_curve,
                cfg.bars_per_year,
                cfg.risk_free_rate,
                cfg.years,
            );
            let mut stmt = tx
                .prepare("INSERT INTO backtest_metrics (name, value) VALUES (?, ?)")
                .expect("prep metric");
            for (name, val) in [
                ("total_return_pct", m.total_return_pct),
                ("cagr", m.cagr),
                ("annual_volatility", m.annual_volatility),
                ("sharpe_ratio", m.sharpe_ratio),
                ("sortino_ratio", m.sortino_ratio),
                ("max_drawdown", m.max_drawdown),
                ("max_drawdown_duration_bars", m.max_drawdown_duration_bars as f64),
                ("calmar_ratio", m.calmar_ratio),
            ] {
                stmt.execute(params![name, val]).ok();
            }
        }
        tx.commit().expect("commit");
    } else {
        for (sym, opens, closes) in symbols_data {
            let stats = run_one_symbol(sym, opens, closes, p, capital_per_symbol, None);
            total_equity += stats.final_equity;
            total_trades += stats.trades;
            total_wins += stats.wins;
            merge(&mut portfolio_curve, &stats.equity);
        }
        // Still compute metrics in the no-persist path so the timing
        // reflects the cost; just don't write them anywhere.
        if let Some(cfg) = metrics_cfg {
            let _ = compute_metrics(
                &portfolio_curve,
                cfg.bars_per_year,
                cfg.risk_free_rate,
                cfg.years,
            );
        }
    }

    BacktestStats {
        final_equity: total_equity,
        trades: total_trades,
        wins: total_wins,
        equity: portfolio_curve,
    }
}

#[derive(Clone, Copy)]
struct MetricsCfg {
    bars_per_year: f64,
    risk_free_rate: f64,
    years: f64,
}

fn main() -> Result<()> {
    let args = Args::parse();

    if args.workers > 0 {
        rayon::ThreadPoolBuilder::new()
            .num_threads(args.workers)
            .build_global()
            .ok();
    }

    let n_bars = (args.years * 365.25 * 24.0) as usize;

    println!(
        "Rust benchmark: loading {} symbols × {} bars from {:?}",
        SYMBOLS.len(),
        n_bars,
        args.data_dir
    );

    let load_t0 = Instant::now();
    let symbols_data: Vec<(String, Vec<f64>, Vec<f64>)> = SYMBOLS
        .iter()
        .map(|s| {
            let path = args.data_dir.join(format!("{}.parquet", s));
            let (opens, closes) = load_close(&path, n_bars).expect("load");
            ((*s).to_string(), opens, closes)
        })
        .collect();
    println!("  loaded in {:.3}s", load_t0.elapsed().as_secs_f64());

    let grid = build_param_grid(args.combos);
    println!(
        "Rust framework benchmark: {} strategies × {} symbols, {}y of hourly data, workers={}",
        grid.len(),
        SYMBOLS.len(),
        args.years,
        if args.workers == 0 { rayon::current_num_threads() } else { args.workers }
    );

    let initial_total = 10_000.0_f64;
    let capital_per_symbol = initial_total / SYMBOLS.len() as f64;

    let db_dir = if args.persist {
        // Reset the DB dir so each run starts clean and we don't grow
        // a huge backlog on disk between iterations.
        let _ = std::fs::remove_dir_all(&args.db_dir);
        std::fs::create_dir_all(&args.db_dir).ok();
        println!(
            "Persistence: ON (writing per-backtest SQLite DBs to {:?})",
            args.db_dir
        );
        Some(args.db_dir.as_path())
    } else {
        println!("Persistence: OFF (pure in-memory backtest)");
        None
    };

    let metrics_cfg = if args.metrics {
        println!(
            "Metrics: ON (Sharpe / Sortino / max-DD / Calmar / vol / CAGR; bars/yr={})",
            args.bars_per_year
        );
        Some(MetricsCfg {
            bars_per_year: args.bars_per_year,
            risk_free_rate: args.risk_free_rate,
            years: args.years,
        })
    } else {
        println!("Metrics: OFF");
        None
    };

    let t0 = Instant::now();
    let results: Vec<BacktestStats> = grid
        .par_iter()
        .enumerate()
        .map(|(idx, p)| run_one_backtest(idx, &symbols_data, p, capital_per_symbol, db_dir, metrics_cfg))
        .collect();
    let elapsed = t0.elapsed().as_secs_f64();

    let n = results.len();
    let summary = BenchSummary {
        implementation: "rust_reference",
        persist: args.persist,
        metrics: args.metrics,
        n_strategies: n,
        n_symbols: SYMBOLS.len(),
        n_backtests: n,
        years: args.years,
        workers: if args.workers == 0 { rayon::current_num_threads() } else { args.workers },
        // Keep extra precision: a Rust sweep on small data can finish in
        // sub-millisecond time, so rounding to 3 dp would zero it out.
        elapsed_seconds: (elapsed * 1_000_000.0).round() / 1_000_000.0,
        throughput_backtests_per_second: ((n as f64 / elapsed) * 1000.0).round() / 1000.0,
        wall_clock_per_backtest_ms: ((elapsed / n as f64) * 1000.0 * 1000.0).round() / 1000.0,
    };

    if let Some(parent) = args.results_file.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    let json = serde_json::to_string_pretty(&summary)?;
    std::fs::write(&args.results_file, &json)?;
    println!();
    println!("{}", json);

    // sanity: print a few final equities so we can eyeball parity
    let mut sample: Vec<_> = results.iter().take(3).collect();
    sample.iter_mut().for_each(|_| {});
    let final_equities: Vec<String> = results
        .iter()
        .take(5)
        .map(|s| format!("${:.2} ({} trades)", s.final_equity, s.trades))
        .collect();
    eprintln!("first 5 final equities: {:?}", final_equities);

    Ok(())
}
