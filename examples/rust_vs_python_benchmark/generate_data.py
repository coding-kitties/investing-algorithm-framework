"""
Generate synthetic OHLCV data for the Python-vs-Rust benchmark.

Geometric Brownian motion with realistic-ish volatility per asset class.
Self-contained, deterministic (seeded), no network or API keys required.

Output layout::

    data/
      BTC-USD.parquet   # Rust side reads parquet directly
      BTC-USD.csv       # Framework CSVOHLCVDataProvider format
      ...

Each parquet/CSV has columns: ``Datetime, Open, High, Low, Close, Volume``.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd


# (symbol, annual_drift, annual_vol, start_price)
ASSETS = [
    ("BTC-USD", 0.40, 0.65, 30_000.0),
    ("ETH-USD", 0.30, 0.80, 1_800.0),
    ("SOL-USD", 0.25, 1.10, 25.0),
    ("ADA-USD", 0.10, 0.95, 0.30),
    ("DOT-USD", 0.08, 0.90, 5.50),
]


def _gbm_ohlcv(
    n_bars: int, dt_hours: float, mu: float, sigma: float, s0: float, rng
) -> pd.DataFrame:
    """One geometric Brownian motion path turned into a synthetic OHLCV."""
    dt = dt_hours / (365.25 * 24.0)
    drift = (mu - 0.5 * sigma * sigma) * dt
    diffusion = sigma * np.sqrt(dt)

    # Close path
    increments = drift + diffusion * rng.standard_normal(n_bars)
    log_closes = np.log(s0) + np.cumsum(increments)
    closes = np.exp(log_closes)

    # Opens are previous close (first open == s0)
    opens = np.empty(n_bars)
    opens[0] = s0
    opens[1:] = closes[:-1]

    # Intra-bar high/low: random fraction of bar range above/below max(open, close)
    # Use a small extra noise so ranges are non-trivial
    bar_noise = sigma * np.sqrt(dt) * 0.5
    upper = rng.random(n_bars) * bar_noise
    lower = rng.random(n_bars) * bar_noise
    base = np.maximum(opens, closes)
    floor = np.minimum(opens, closes)
    highs = base * (1.0 + upper)
    lows = floor * (1.0 - lower)

    # Synthetic volume — lognormal, scaled by price
    volumes = rng.lognormal(mean=np.log(1e6 / s0), sigma=0.4, size=n_bars)

    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        }
    )


def generate(
    out_dir: Path, years: float, time_frame_hours: int, seed: int
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    n_bars = int(years * 365.25 * 24 / time_frame_hours)
    end = datetime(2024, 12, 31, 23, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=time_frame_hours * (n_bars - 1))
    index = pd.date_range(
        start=start, end=end, periods=n_bars, tz="UTC", name="Datetime"
    )

    written: list[Path] = []
    rng_master = np.random.default_rng(seed)
    for symbol, mu, sigma, s0 in ASSETS:
        rng = np.random.default_rng(rng_master.integers(0, 2**31 - 1))
        df = _gbm_ohlcv(n_bars, time_frame_hours, mu, sigma, s0, rng)
        df.index = index
        parquet_path = out_dir / f"{symbol}.parquet"
        df.to_parquet(parquet_path)
        # Framework CSVOHLCVDataProvider expects a `Datetime` column
        # parseable by polars (ISO-8601 string is fine; it casts to
        # ms-precision UTC internally).
        csv_path = out_dir / f"{symbol}.csv"
        df_csv = df.reset_index().rename(columns={"index": "Datetime"})
        df_csv["Datetime"] = df_csv["Datetime"].dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        df_csv.to_csv(csv_path, index=False)
        written.append(parquet_path)
        print(
            f"  wrote {parquet_path.name:<14} + {csv_path.name:<14} "
            f"bars={len(df):>7,d}  "
            f"first_close={df['Close'].iloc[0]:>10,.4f}  "
            f"last_close={df['Close'].iloc[-1]:>10,.4f}"
        )
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--years", type=float, default=10.0,
        help="Years of history per symbol (default: 10)."
    )
    parser.add_argument(
        "--time-frame-hours", type=int, default=1,
        help="Bar size in hours (default: 1 = hourly)."
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(
        f"Generating {args.years}y of {args.time_frame_hours}h bars "
        f"for {len(ASSETS)} symbols into {args.out_dir}/ ..."
    )
    generate(args.out_dir, args.years, args.time_frame_hours, args.seed)


if __name__ == "__main__":
    main()
