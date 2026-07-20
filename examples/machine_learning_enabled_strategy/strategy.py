"""
Machine-learning enabled trading strategy.

Demonstrates how to plug a pre-trained scikit-learn classifier into
the signal-generation loop of a trading strategy class.

The model is trained offline and pickled to disk. The strategy
loads it once in ``__init__`` and uses ``predict_proba`` inside the
signal function to decide when to open or close a position.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, Iterable

import numpy as np
import pandas as pd
from pyindicators import rsi

from investing_algorithm_framework import (
    DataSource,
    DataType,
    Schedule,
    Signal,
    SignalSeries,
    SignalSide,
    TimeUnit,
    TradingStrategy,
    signal_series_from_column,
    signals_from_column,
)


FEATURE_COLUMNS = [
    "ret_1",
    "ret_3",
    "ret_5",
    "mom_10",
    "vol_10",
    "rsi_14",
]


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Append the engineered feature columns the model was trained on."""
    out = df.copy()
    close = out["Close"]

    out["ret_1"] = close.pct_change(1)
    out["ret_3"] = close.pct_change(3)
    out["ret_5"] = close.pct_change(5)
    out["mom_10"] = close / close.shift(10) - 1.0
    out["vol_10"] = close.pct_change().rolling(10).std()

    out = rsi(out, period=14, source_column="Close", result_column="rsi_14")
    out["rsi_14"] = out["rsi_14"] / 100.0

    return out


class MachineLearningStrategy(TradingStrategy):
    """Long-only strategy driven by a pre-trained classifier."""

    algorithm_id = "ml-classifier"
    schedule = Schedule.every(24, TimeUnit.HOUR)
    market = "BITVAVO"
    trading_symbol = "EUR"

    def __init__(
        self,
        model_path: str | Path,
        symbol: str = "BTC/EUR",
        time_frame: str = "1d",
        enter_threshold: float = 0.55,
        exit_threshold: float = 0.45,
    ):
        self.symbol = symbol
        self.time_frame = time_frame
        self.enter_threshold = enter_threshold
        self.exit_threshold = exit_threshold

        # Load the pre-trained classifier once at construction time.
        # Any object exposing ``predict_proba`` works here
        # (scikit-learn, XGBoost, LightGBM, ...).
        with open(model_path, "rb") as fh:
            self.model = pickle.load(fh)

        symbols = [symbol.split("/")[0]]
        data_sources = [
            DataSource(
                identifier=f"{symbol}-ohlcv",
                data_type=DataType.OHLCV,
                market=self.market,
                symbol=symbol,
                time_frame=time_frame,
                # Must cover the longest feature lookback (mom_10
                # needs 10 bars; pad a bit for safety).
                warmup_window=30,
                pandas=True,
            )
        ]
        super().__init__(
            algorithm_id=self.algorithm_id,
            symbols=symbols,
            trading_symbol=self.trading_symbol,
            data_sources=data_sources,
        )
        self.set_parameters({
            "symbol": symbol,
            "time_frame": time_frame,
            "enter_threshold": enter_threshold,
            "exit_threshold": exit_threshold,
            "model_path": str(model_path),
        })

    # ------------------------------------------------------------------ #
    # Inference                                                          #
    # ------------------------------------------------------------------ #

    def _predict(self, df: pd.DataFrame) -> pd.Series:
        """Return a series of P(up) aligned with ``df.index``."""
        X = df[FEATURE_COLUMNS]
        mask = X.notna().all(axis=1)
        probs = pd.Series(np.nan, index=df.index, dtype=float)
        if mask.any():
            preds = self.model.predict_proba(X.loc[mask].to_numpy())[:, 1]
            probs.loc[mask] = preds
        return probs

    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
        df = _build_features(data[f"{self.symbol}-ohlcv"])

        df["p_up"] = self._predict(df)
        df["ml_enter"] = (df["p_up"] > self.enter_threshold).fillna(False)
        df["ml_exit"] = (df["p_up"] < self.exit_threshold).fillna(False)

        yield signal_series_from_column(
            df, "ml_enter",
            side=SignalSide.OPEN_LONG,
            symbol=self.symbols[0],
            source="ml_classifier",
            strength_column="p_up",
        )
        yield signal_series_from_column(
            df, "ml_exit",
            side=SignalSide.CLOSE_LONG,
            symbol=self.symbols[0],
            source="ml_classifier",
        )

    def generate_signals(
        self, context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        """
        Event mode: generate signals one bar at a time.
        """
        df = _build_features(data[f"{self.symbol}-ohlcv"])

        df["p_up"] = self._predict(df)
        df["ml_enter"] = (df["p_up"] > self.enter_threshold).fillna(False)
        df["ml_exit"] = (df["p_up"] < self.exit_threshold).fillna(False)

        # signals_from_column inspects the LAST row only, which is
        # exactly the "one bar = one decision" semantics of event mode.
        yield from signals_from_column(
            df, "ml_enter",
            side=SignalSide.OPEN_LONG,
            symbol=self.symbols[0],
            source="ml_classifier",
        )
        yield from signals_from_column(
            df, "ml_exit",
            side=SignalSide.CLOSE_LONG,
            symbol=self.symbols[0],
            source="ml_classifier",
        )
