"""Generate deterministic synthetic OHLCV data for the advanced
strategy example.

Self-contained: no network, no API keys. Combines a slow upward drift
with a sinusoidal cycle so the price reliably trends (feeding the
EMA-crossover long side) AND swings into overbought/oversold RSI
territory (feeding the mean-reversion short side).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

CSV_PATH = Path(__file__).parent / "BTC-EUR-2h.csv"
TIME_FRAME_HOURS = 2
N_BARS = 1000
START_DATE = datetime(2023, 1, 1, tzinfo=timezone.utc)
END_DATE = START_DATE + timedelta(hours=TIME_FRAME_HOURS * (N_BARS - 1))
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.000+0000"

# The strategy's warmup_window is 60 bars — the backtest itself must
# start at least that far into the CSV, so the sliding window has real
# historical bars to look back on from the very first simulated tick.
WARMUP_BARS = 65
BACKTEST_START_DATE = START_DATE + timedelta(
    hours=TIME_FRAME_HOURS * WARMUP_BARS
)


def _generate() -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    t = np.arange(N_BARS)

    drift = 0.00015 * t
    cycle = 0.18 * np.sin(2 * np.pi * t / 120)
    noise = np.cumsum(rng.normal(0, 0.01, size=N_BARS))

    close = 25_000.0 * np.exp(drift + cycle + noise)
    open_ = np.empty(N_BARS)
    open_[0] = close[0]
    open_[1:] = close[:-1]

    intrabar_noise = np.abs(rng.normal(0, 0.004, size=N_BARS)) * close
    high = np.maximum(open_, close) + intrabar_noise
    low = np.minimum(open_, close) - intrabar_noise
    volume = rng.uniform(50, 500, size=N_BARS)

    dates = [
        (START_DATE + timedelta(hours=TIME_FRAME_HOURS * i))
        .strftime(DATETIME_FORMAT)
        for i in range(N_BARS)
    ]

    return pd.DataFrame({
        "Datetime": dates,
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


def generate_if_missing() -> Path:
    if not CSV_PATH.exists():
        df = _generate()
        df.to_csv(CSV_PATH, index=False)
        print(f"Generated {len(df)} synthetic bars -> {CSV_PATH}")
    return CSV_PATH


if __name__ == "__main__":
    generate_if_missing()
