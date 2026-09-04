
from typing import Dict, Any, Iterable

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder, supertrend, bollinger_bands

from investing_algorithm_framework import TradingStrategy, DataSource, \
    DataType, PositionSize, StopLossRule, TakeProfitRule, \
    ScalingRule, CooldownRule, Schedule, TimeUnit, \
    Signal, SignalSeries, SignalSide, ScoreCard, ScoreCardEntry


def _schedule_from_timeframe(timeframe: str) -> Schedule:
    """Build a default ``Schedule`` from an OHLCV timeframe string
    (e.g. ``"2h"``, ``"15m"``, ``"1d"``). Used so the strategy works
    out of the box in v9 event-mode without forcing every caller to
    pass ``schedule=`` explicitly."""
    tf = timeframe.strip().lower()
    unit_map = {
        "s": TimeUnit.SECOND,
        "m": TimeUnit.MINUTE,
        "h": TimeUnit.HOUR,
        "d": TimeUnit.DAY,
    }
    suffix = tf[-1]
    if suffix not in unit_map:
        return Schedule.every(1, TimeUnit.HOUR)
    try:
        interval = int(tf[:-1]) if tf[:-1] else 1
    except ValueError:
        interval = 1
    return Schedule.every(max(1, interval), unit_map[suffix])


class SupertrendEmaConfirmationStrategy(TradingStrategy):
    """
    Trend-following strategy with the following signal hierarchy:

    * **Primary**       SuperTrend trend flip (entry on bullish flip,
                        exit on bearish flip).
    * **Confirmation**  EMA crossover / crossunder within the lookback
                        window must agree with the SuperTrend flip.
    * **Guardrails**    RSI extremes and Bollinger Bands extremes are
                        used to *block* (or, on the exit side,
                        *suppress*) signals that look like blow-off
                        tops or capitulation lows.
    """


    def __init__(
        self,
        symbols: list,
        trading_symbol: str,
        rsi_timeframe: str,
        rsi_period: int,
        rsi_overbought_threshold,
        rsi_oversold_threshold,
        ema_timeframe,
        ema_short_period,
        ema_long_period,
        ema_cross_lookback_window,
        # algorithm_id is optional -- when omitted, the base class
        # auto-derives it from the parameters passed to set_parameters()
        # below, so re-instantiating with the same params reproduces
        # the same id.
        algorithm_id: str = None,
        ema_long_result_column="ema_long",
        ema_short_result_column="ema_short",
        ema_crossunder_result_column="ema_crossunder",
        ema_crossover_result_column="ema_crossover",
        rsi_result_column="rsi",
        # SuperTrend (trend confirmation filter)
        supertrend_atr_length: int = 10,
        supertrend_factor: float = 3.0,
        use_supertrend_filter: bool = True,
        # Bollinger Bands (mean-reversion / overextension filter)
        bollinger_period: int = 20,
        bollinger_std_dev: float = 2.0,
        use_bollinger_filter: bool = True,
        schedule: Schedule = None,
        market: str = "BITVAVO",
        metadata: dict = None,
        # Risk management parameters
        stop_loss_percentage: float = 5.0,
        take_profit_percentage: float = 10.0,
        trailing_stop_loss: bool = True,
        # Scaling parameters
        max_entries: int = 1,
        scale_in_percentage: float = 100,
        cooldown_in_bars: int = 0,
        # CooldownRule parameters — side-aware signal throttling.
        # ``reentry_cooldown_bars`` blocks a new buy on the same symbol
        # for N bars after a sell (stop-out, take-profit or sell signal),
        # which kills hair-trigger re-entries on choppy reversals.
        # ``portfolio_cooldown_bars`` is a portfolio-wide both-sides
        # breather after any order — set to 0 to disable.
        reentry_cooldown_bars: int = 0,
        portfolio_cooldown_bars: int = 0,
        # Short-selling. Off by default so long-only behaviour
        # is unchanged. When enabled the strategy emits SHORT/COVER
        # signals that mirror the long-side hierarchy (SuperTrend +
        # EMA confirmation + RSI/Bollinger guardrails).
        enable_shorting: bool = False,
        # Cover-tightening knobs. The default cover trigger is the
        # mirror of the long-entry trigger which fires on *any* bullish
        # SuperTrend flip + *any* EMA crossover inside the lookback
        # window. In a sustained downtrend that closes shorts on every
        # minor bounce. These two parameters tighten cover specifically:
        #   * ``cover_requires_current_trend`` — only cover when the
        #     SuperTrend is *currently* bullish (not just flipped at
        #     some point in the lookback). Default True.
        #   * ``cover_min_confirmation_bars`` — require EMA short to
        #     be ABOVE EMA long for at least N consecutive bars (held
        #     dominance, not a fleeting cross). Default 3.
        # Set both to their disabling values (False, 0) to restore the
        # symmetric-with-entry behaviour.
        cover_requires_current_trend: bool = True,
        cover_min_confirmation_bars: int = 3,
    ):
        self.rsi_timeframe = rsi_timeframe
        self.rsi_period = rsi_period
        self.rsi_result_column = rsi_result_column
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_timeframe = ema_timeframe
        self.ema_short_result_column = ema_short_result_column
        self.ema_long_result_column = ema_long_result_column
        self.ema_crossunder_result_column = ema_crossunder_result_column
        self.ema_crossover_result_column = ema_crossover_result_column
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window

        # SuperTrend config
        self.supertrend_atr_length = supertrend_atr_length
        self.supertrend_factor = supertrend_factor
        self.use_supertrend_filter = use_supertrend_filter

        # Bollinger Bands config
        self.bollinger_period = bollinger_period
        self.bollinger_std_dev = bollinger_std_dev
        self.use_bollinger_filter = use_bollinger_filter

        # Short-selling toggle (#433).
        self.enable_shorting = enable_shorting
        self.cover_requires_current_trend = cover_requires_current_trend
        self.cover_min_confirmation_bars = int(cover_min_confirmation_bars)

        # Default schedule derived from ema_timeframe if caller didn't
        # provide one — required by v9 event-mode (vector mode ignores).
        if schedule is None:
            schedule = _schedule_from_timeframe(ema_timeframe)

        # Determine the warmup window needed (largest indicator period)
        warmup = max(
            ema_long_period,
            ema_short_period,
            rsi_period,
            supertrend_atr_length,
            bollinger_period,
        ) + 10

        data_sources = []
        position_sizes = []
        stop_losses = []
        take_profits = []
        scaling_rules = []
        cooldowns = []

        for symbol in symbols:
            full_symbol = f"{symbol}/{trading_symbol}"
            data_sources.append(
                DataSource(
                    identifier=f"rsi_data_{symbol}",
                    data_type=DataType.OHLCV,
                    time_frame=self.rsi_timeframe,
                    market=market,
                    symbol=full_symbol,
                    warmup_window=warmup,
                    pandas=True
                )
            )
            data_sources.append(
                DataSource(
                    identifier=f"ema_data_{symbol}",
                    data_type=DataType.OHLCV,
                    time_frame=self.ema_timeframe,
                    market=market,
                    symbol=full_symbol,
                    warmup_window=warmup,
                    pandas=True
                )
            )
            position_sizes.append(
                PositionSize(
                    symbol=symbol,
                    percentage_of_portfolio=100 / len(symbols)
                )
            )
            stop_losses.append(
                StopLossRule(
                    symbol=symbol,
                    percentage_threshold=stop_loss_percentage,
                    sell_percentage=100,
                    trailing=trailing_stop_loss,
                )
            )
            take_profits.append(
                TakeProfitRule(
                    symbol=symbol,
                    percentage_threshold=take_profit_percentage,
                    sell_percentage=100,
                )
            )
            scaling_rules.append(
                ScalingRule(
                    symbol=symbol,
                    max_entries=max_entries,
                    scale_in_percentage=scale_in_percentage,
                    cooldown_in_bars=cooldown_in_bars,
                )
            )
            if reentry_cooldown_bars > 0:
                cooldowns.append(
                    CooldownRule(
                        symbol=symbol,
                        trigger="sell",
                        blocks="buy",
                        bars=reentry_cooldown_bars,
                    )
                )

        # Optional portfolio-wide both-sides breather after any order.
        if portfolio_cooldown_bars > 0:
            cooldowns.append(
                CooldownRule(
                    trigger="any",
                    blocks="any",
                    bars=portfolio_cooldown_bars,
                )
            )

        super().__init__(
            algorithm_id=algorithm_id,
            symbols=symbols,
            data_sources=data_sources,
            position_sizes=position_sizes,
            stop_losses=stop_losses,
            take_profits=take_profits,
            scaling_rules=scaling_rules,
            cooldowns=cooldowns,
            schedule=schedule,
            metadata=metadata,
        )

        # trading_symbol is a display-only unit label for ScoreCardEntry
        # here (not a framework-recognized concept) -- the actual
        # settlement currency comes from the registered Universe /
        # PortfolioConfiguration.
        self.trading_symbol = trading_symbol

        # Store parameters so they get saved to parameters.json
        self.set_parameters({
            "ema_timeframe": ema_timeframe,
            "rsi_timeframe": rsi_timeframe,
            "ema_short_period": ema_short_period,
            "ema_long_period": ema_long_period,
            "ema_cross_lookback_window": ema_cross_lookback_window,
            "rsi_period": rsi_period,
            "rsi_overbought_threshold": rsi_overbought_threshold,
            "rsi_oversold_threshold": rsi_oversold_threshold,
            "supertrend_atr_length": supertrend_atr_length,
            "supertrend_factor": supertrend_factor,
            "use_supertrend_filter": use_supertrend_filter,
            "bollinger_period": bollinger_period,
            "bollinger_std_dev": bollinger_std_dev,
            "use_bollinger_filter": use_bollinger_filter,
            "stop_loss_percentage": stop_loss_percentage,
            "take_profit_percentage": take_profit_percentage,
            "trailing_stop_loss": trailing_stop_loss,
            "max_entries": max_entries,
            "scale_in_percentage": scale_in_percentage,
            "cooldown_in_bars": cooldown_in_bars,
            "reentry_cooldown_bars": reentry_cooldown_bars,
            "portfolio_cooldown_bars": portfolio_cooldown_bars,
            "enable_shorting": enable_shorting,
            "cover_requires_current_trend": cover_requires_current_trend,
            "cover_min_confirmation_bars": cover_min_confirmation_bars,
        })

    def prepare_indicators(
        self,
        rsi_data,
        ema_data
    ):
        ema_data = ema(
            ema_data,
            period=self.ema_short_period,
            source_column="Close",
            result_column=self.ema_short_result_column
        )
        ema_data = ema(
            ema_data,
            period=self.ema_long_period,
            source_column="Close",
            result_column=self.ema_long_result_column
        )
        # Detect crossover (short EMA crosses above long EMA)
        ema_data = crossover(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossover_result_column
        )
        # Detect crossunder (short EMA crosses below long EMA)
        ema_data = crossunder(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossunder_result_column
        )
        # SuperTrend on the EMA timeframe (uses High/Low/Close)
        ema_data = supertrend(
            ema_data,
            atr_length=self.supertrend_atr_length,
            factor=self.supertrend_factor,
        )
        # Bollinger Bands on the EMA timeframe
        ema_data = bollinger_bands(
            ema_data,
            source_column="Close",
            period=self.bollinger_period,
            std_dev=self.bollinger_std_dev,
        )
        rsi_data = rsi(
            rsi_data,
            period=self.rsi_period,
            source_column="Close",
            result_column=self.rsi_result_column
        )

        return ema_data, rsi_data

    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
        """v9.0 vector-backtest entry point.

        Computes the four per-side boolean panels (long entry, long
        exit, optional short entry, optional cover) using the same
        signal hierarchy documented on the legacy helpers, and yields
        one :class:`SignalSeries` per (symbol, side).
        """
        buys = self._compute_buy_signals(data)
        for symbol, series in buys.items():
            yield SignalSeries(
                symbol=symbol,
                side=SignalSide.OPEN_LONG,
                series=series,
                source="supertrend_ema",
            )
        sells = self._compute_sell_signals(data)
        for symbol, series in sells.items():
            yield SignalSeries(
                symbol=symbol,
                side=SignalSide.CLOSE_LONG,
                series=series,
                source="supertrend_ema",
            )
        if self.enable_shorting:
            shorts = self._compute_short_signals(data) or {}
            for symbol, series in shorts.items():
                yield SignalSeries(
                    symbol=symbol,
                    side=SignalSide.OPEN_SHORT,
                    series=series,
                    source="supertrend_ema",
                )
            covers = self._compute_cover_signals(data) or {}
            for symbol, series in covers.items():
                yield SignalSeries(
                    symbol=symbol,
                    side=SignalSide.CLOSE_SHORT,
                    series=series,
                    source="supertrend_ema",
                )

    def generate_signals(
        self, context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        """v9.0 event-mode entry point.

        Reuses the same ``_compute_*_signals`` helpers as the vector
        path; only the latest bar of each boolean series is consulted.
        """
        def _latest(series) -> bool:
            if series is None or len(series) == 0:
                return False
            return bool(series.iloc[-1])

        for symbol, series in self._compute_buy_signals(data).items():
            if _latest(series):
                yield Signal(
                    symbol=symbol,
                    side=SignalSide.OPEN_LONG,
                    source="supertrend_ema",
                ).with_score_card(
                    self._build_score_card(symbol, SignalSide.OPEN_LONG, data)
                )
        for symbol, series in self._compute_sell_signals(data).items():
            if _latest(series):
                yield Signal(
                    symbol=symbol,
                    side=SignalSide.CLOSE_LONG,
                    source="supertrend_ema",
                ).with_score_card(
                    self._build_score_card(symbol, SignalSide.CLOSE_LONG, data)
                )
        if self.enable_shorting:
            for symbol, series in (self._compute_short_signals(data)
                                   or {}).items():
                if _latest(series):
                    yield Signal(
                        symbol=symbol,
                        side=SignalSide.OPEN_SHORT,
                        source="supertrend_ema",
                    ).with_score_card(
                        self._build_score_card(
                            symbol, SignalSide.OPEN_SHORT, data
                        )
                    )
            for symbol, series in (self._compute_cover_signals(data)
                                   or {}).items():
                if _latest(series):
                    yield Signal(
                        symbol=symbol,
                        side=SignalSide.CLOSE_SHORT,
                        source="supertrend_ema",
                    ).with_score_card(
                        self._build_score_card(
                            symbol, SignalSide.CLOSE_SHORT, data
                        )
                    )

    @staticmethod
    def _scalar(value):
        """Coerce a pandas/numpy scalar to a plain JSON-safe Python
        scalar (``ScoreCardEntry`` rejects numpy dtypes and NaN)."""
        if value is None:
            return None
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, float):
            if pd.isna(value):
                return None
            return round(value, 6)
        return value

    def _build_score_card(
        self, symbol: str, side: SignalSide, data: Dict[str, Any]
    ) -> ScoreCard:
        """Explain a signal with the exact indicator readings (and
        guardrail outcomes) that produced it at the latest bar, so
        anyone looking at ``RunReport.signals`` (or the metadata of
        the resulting order) can see *why* without re-running the
        strategy.
        """
        ema_data, rsi_data = self.prepare_indicators(
            ema_data=data[f"ema_data_{symbol}"],
            rsi_data=data[f"rsi_data_{symbol}"],
        )
        latest = ema_data.iloc[-1]
        rsi_value = self._scalar(
            rsi_data[self.rsi_result_column].iloc[-1]
        )
        close = self._scalar(latest.get("Close"))
        ema_short = self._scalar(latest.get(self.ema_short_result_column))
        ema_long = self._scalar(latest.get(self.ema_long_result_column))
        supertrend_signal = self._scalar(latest.get("supertrend_signal"))
        supertrend_trend = self._scalar(latest.get("supertrend_trend"))

        rsi_overbought = rsi_value is not None \
            and rsi_value >= self.rsi_overbought_threshold
        rsi_oversold = rsi_value is not None \
            and rsi_value <= self.rsi_oversold_threshold

        entries = [
            ScoreCardEntry(
                "supertrend_signal", supertrend_signal, group="trend",
                description="1 = fresh bullish flip, -1 = fresh bearish "
                            "flip, 0 = no flip this bar",
            ),
            ScoreCardEntry(
                "supertrend_trend", supertrend_trend, group="trend",
                description="1 = currently bullish, 0 = currently bearish",
            ),
            ScoreCardEntry("close", close, unit=self.trading_symbol,
                           group="price"),
            ScoreCardEntry(
                self.ema_short_result_column, ema_short,
                unit=self.trading_symbol, group="trend",
            ),
            ScoreCardEntry(
                self.ema_long_result_column, ema_long,
                unit=self.trading_symbol, group="trend",
            ),
            ScoreCardEntry(
                self.ema_crossover_result_column,
                self._scalar(latest.get(self.ema_crossover_result_column)),
                group="trend",
            ),
            ScoreCardEntry(
                self.ema_crossunder_result_column,
                self._scalar(latest.get(self.ema_crossunder_result_column)),
                group="trend",
            ),
            ScoreCardEntry("rsi", rsi_value, group="momentum"),
            ScoreCardEntry(
                "rsi_overbought_threshold", self.rsi_overbought_threshold,
                group="momentum",
            ),
            ScoreCardEntry(
                "rsi_oversold_threshold", self.rsi_oversold_threshold,
                group="momentum",
            ),
        ]

        if self.use_bollinger_filter:
            entries.append(ScoreCardEntry(
                "bollinger_upper", self._scalar(latest.get("bollinger_upper")),
                unit=self.trading_symbol, group="volatility",
            ))
            entries.append(ScoreCardEntry(
                "bollinger_lower", self._scalar(latest.get("bollinger_lower")),
                unit=self.trading_symbol, group="volatility",
            ))

        summaries = {
            SignalSide.OPEN_LONG:
                "SuperTrend flipped bullish, confirmed by an EMA "
                f"crossover within {self.ema_cross_lookback_window} bars"
                + ("; blocked" if rsi_overbought
                   else "; RSI not overbought"),
            SignalSide.CLOSE_LONG:
                "SuperTrend flipped bearish, confirmed by an EMA "
                f"crossunder within {self.ema_cross_lookback_window} bars"
                + ("; suppressed by the capitulation guardrail"
                   if (rsi_oversold and self.use_bollinger_filter)
                   else ""),
            SignalSide.OPEN_SHORT:
                "SuperTrend flipped bearish, confirmed by an EMA "
                f"crossunder within {self.ema_cross_lookback_window} bars"
                + ("; blocked" if rsi_oversold
                   else "; RSI not oversold"),
            SignalSide.CLOSE_SHORT:
                "SuperTrend is bullish"
                if self.cover_requires_current_trend
                else "SuperTrend flipped bullish within the lookback "
                     "window",
        }

        return ScoreCard(entries=entries, summary=summaries.get(side))

    def _compute_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """
        Signal hierarchy (long entries):

        1. **Primary**  SuperTrend flips bullish (``supertrend_trend``
           transitions 0 -> 1, i.e. a fresh ``supertrend_signal == 1``).
        2. **Confirmation**  An EMA crossover (short above long) occurred
           within the lookback window, confirming momentum agrees with
           the trend flip.
        3. **Guardrails**  Reject the entry if:
             - RSI is already overbought (chasing a blow-off top), or
             - price is already above the Bollinger upper band
               (overextended to the upside).
        """
        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"ema_data_{symbol}"
            rsi_data_identifier = f"rsi_data_{symbol}"
            ema_data, rsi_data = self.prepare_indicators(
                ema_data=data[ema_data_identifier],
                rsi_data=data[rsi_data_identifier]
            )

            # 1. PRIMARY: SuperTrend bullish flip.
            # `supertrend_signal == 1` marks the bar where the trend
            # turned bullish. Hold the signal active for the lookback
            # window so EMA confirmation has time to arrive.
            if self.use_supertrend_filter \
                    and "supertrend_signal" in ema_data.columns:
                supertrend_flip = (
                    (ema_data["supertrend_signal"] == 1)
                    .rolling(window=self.ema_cross_lookback_window).sum()
                    > 0
                )
            else:
                # SuperTrend disabled: fall back to "trend is bullish now".
                supertrend_flip = ema_data.get(
                    "supertrend_trend", pd.Series(True, index=ema_data.index)
                ) == 1

            # 2. CONFIRMATION: EMA short crossed above EMA long
            # somewhere in the lookback window.
            ema_confirmation = (
                ema_data[self.ema_crossover_result_column]
                .rolling(window=self.ema_cross_lookback_window).sum() > 0
            )

            buy_signal = supertrend_flip & ema_confirmation

            # 3. GUARDRAILS
            # RSI: don't buy into an overbought market.
            rsi_not_overbought = rsi_data[self.rsi_result_column] \
                < self.rsi_overbought_threshold
            buy_signal = buy_signal & rsi_not_overbought.reindex(
                buy_signal.index, method="ffill"
            ).fillna(True)

            # Bollinger: don't buy when price is already above the
            # upper band (mean-reversion risk).
            if self.use_bollinger_filter \
                    and "bollinger_upper" in ema_data.columns:
                not_overextended = ema_data["Close"] \
                    < ema_data["bollinger_upper"]
                buy_signal = buy_signal & not_overextended

            buy_signal = buy_signal.fillna(False).astype(bool)
            signals[symbol] = buy_signal

        return signals

    def _compute_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        """
        Signal hierarchy (long exits):

        1. **Primary**  SuperTrend flips bearish (``supertrend_signal
           == -1`` within the lookback window).
        2. **Confirmation**  An EMA crossunder (short below long)
           occurred within the lookback window.
        3. **Guardrails**  Reject the exit if:
             - RSI is still deeply oversold (likely capitulation low,
               give the position a chance to bounce), AND
             - price is at/below the Bollinger lower band
               (mean-reversion-favourable conditions).
           If *both* guardrails fire we suppress the exit so the
           stop-loss / take-profit rules take over instead.
        """
        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"ema_data_{symbol}"
            rsi_data_identifier = f"rsi_data_{symbol}"

            ema_data, rsi_data = self.prepare_indicators(
                ema_data=data[ema_data_identifier],
                rsi_data=data[rsi_data_identifier]
            )

            # 1. PRIMARY: SuperTrend bearish flip.
            if self.use_supertrend_filter \
                    and "supertrend_signal" in ema_data.columns:
                supertrend_flip = (
                    (ema_data["supertrend_signal"] == -1)
                    .rolling(window=self.ema_cross_lookback_window).sum()
                    > 0
                )
            else:
                supertrend_flip = ema_data.get(
                    "supertrend_trend", pd.Series(True, index=ema_data.index)
                ) == 0

            # 2. CONFIRMATION: EMA short crossed below EMA long
            # somewhere in the lookback window.
            ema_confirmation = (
                ema_data[self.ema_crossunder_result_column]
                .rolling(window=self.ema_cross_lookback_window).sum() > 0
            )

            sell_signal = supertrend_flip & ema_confirmation

            # 3. GUARDRAILS — suppress the exit when both RSI and
            # Bollinger say "capitulation, don't sell here".
            rsi_deeply_oversold = rsi_data[self.rsi_result_column] \
                <= self.rsi_oversold_threshold
            rsi_deeply_oversold = rsi_deeply_oversold.reindex(
                sell_signal.index, method="ffill"
            ).fillna(False)

            if self.use_bollinger_filter \
                    and "bollinger_lower" in ema_data.columns:
                at_lower_band = ema_data["Close"] \
                    <= ema_data["bollinger_lower"]
            else:
                at_lower_band = pd.Series(False, index=sell_signal.index)

            suppress_exit = rsi_deeply_oversold & at_lower_band
            sell_signal = sell_signal & ~suppress_exit

            sell_signal = sell_signal.fillna(False).astype(bool)
            signals[symbol] = sell_signal

        return signals

    # ------------------------------------------------------------------
    # SHORT / COVER signals
    #
    # Mirror image of the long-side hierarchy:
    #
    # SHORT entry  = bearish SuperTrend flip + EMA crossunder
    #                confirmation + guardrails reject if RSI is already
    #                deeply oversold or price is below the Bollinger
    #                lower band (overextended to the downside — risk
    #                of an upward bounce).
    # COVER exit   = bullish SuperTrend flip + EMA crossover
    #                confirmation + guardrails suppress when RSI is
    #                overbought AND price is at/above the upper band
    #                (potential blow-off top; let stop / take-profit
    #                rules manage the close).
    #
    # Both methods short-circuit to ``None`` when ``enable_shorting``
    # is False so the vector engine treats shorting as disabled.
    # ------------------------------------------------------------------
    def _compute_short_signals(
        self, data: Dict[str, Any]
    ):
        if not self.enable_shorting:
            return None

        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"ema_data_{symbol}"
            rsi_data_identifier = f"rsi_data_{symbol}"
            ema_data, rsi_data = self.prepare_indicators(
                ema_data=data[ema_data_identifier],
                rsi_data=data[rsi_data_identifier]
            )

            # 1. PRIMARY: SuperTrend bearish flip in the lookback window.
            if self.use_supertrend_filter \
                    and "supertrend_signal" in ema_data.columns:
                supertrend_flip = (
                    (ema_data["supertrend_signal"] == -1)
                    .rolling(window=self.ema_cross_lookback_window).sum()
                    > 0
                )
            else:
                supertrend_flip = ema_data.get(
                    "supertrend_trend",
                    pd.Series(False, index=ema_data.index)
                ) == 0

            # 2. CONFIRMATION: EMA crossunder in the lookback window.
            ema_confirmation = (
                ema_data[self.ema_crossunder_result_column]
                .rolling(window=self.ema_cross_lookback_window).sum() > 0
            )

            short_signal = supertrend_flip & ema_confirmation

            # 3. GUARDRAILS — don't short into capitulation lows.
            rsi_not_oversold = rsi_data[self.rsi_result_column] \
                > self.rsi_oversold_threshold
            short_signal = short_signal & rsi_not_oversold.reindex(
                short_signal.index, method="ffill"
            ).fillna(True)

            if self.use_bollinger_filter \
                    and "bollinger_lower" in ema_data.columns:
                not_overextended = ema_data["Close"] \
                    > ema_data["bollinger_lower"]
                short_signal = short_signal & not_overextended

            short_signal = short_signal.fillna(False).astype(bool)
            signals[symbol] = short_signal

        return signals

    def _compute_cover_signals(
        self, data: Dict[str, Any]
    ):
        if not self.enable_shorting:
            return None

        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"ema_data_{symbol}"
            rsi_data_identifier = f"rsi_data_{symbol}"
            ema_data, rsi_data = self.prepare_indicators(
                ema_data=data[ema_data_identifier],
                rsi_data=data[rsi_data_identifier]
            )

            # 1. PRIMARY: SuperTrend trend gate.
            #    Default (``cover_requires_current_trend=True``) only
            #    covers when the trend is *currently* bullish, so a
            #    single bullish bar inside the lookback window does
            #    NOT keep firing covers for the next N bars. Falls back
            #    to the symmetric-with-entry lookback-flip behaviour
            #    when the knob is disabled.
            if self.use_supertrend_filter \
                    and "supertrend_signal" in ema_data.columns:
                if self.cover_requires_current_trend \
                        and "supertrend_trend" in ema_data.columns:
                    supertrend_flip = ema_data["supertrend_trend"] == 1
                else:
                    supertrend_flip = (
                        (ema_data["supertrend_signal"] == 1)
                        .rolling(window=self.ema_cross_lookback_window)
                        .sum() > 0
                    )
            else:
                supertrend_flip = ema_data.get(
                    "supertrend_trend",
                    pd.Series(True, index=ema_data.index)
                ) == 1

            # 2. CONFIRMATION: held EMA dominance (short > long for
            #    ``cover_min_confirmation_bars`` consecutive bars)
            #    rather than a single stale crossover in the window.
            #    Set bars=0 to restore the symmetric-with-entry rule.
            confirm_bars = max(1, self.cover_min_confirmation_bars)
            if self.cover_min_confirmation_bars > 0 \
                    and self.ema_short_result_column in ema_data.columns \
                    and self.ema_long_result_column in ema_data.columns:
                ema_above = (
                    ema_data[self.ema_short_result_column]
                    > ema_data[self.ema_long_result_column]
                )
                ema_confirmation = (
                    ema_above.rolling(window=confirm_bars).sum()
                    == confirm_bars
                )
            else:
                ema_confirmation = (
                    ema_data[self.ema_crossover_result_column]
                    .rolling(window=self.ema_cross_lookback_window)
                    .sum() > 0
                )

            cover_signal = supertrend_flip & ema_confirmation

            # 3. GUARDRAILS — suppress cover when momentum says the
            # short still has room to run (overbought + upper-band).
            rsi_overbought = rsi_data[self.rsi_result_column] \
                >= self.rsi_overbought_threshold
            rsi_overbought = rsi_overbought.reindex(
                cover_signal.index, method="ffill"
            ).fillna(False)

            if self.use_bollinger_filter \
                    and "bollinger_upper" in ema_data.columns:
                at_upper_band = ema_data["Close"] \
                    >= ema_data["bollinger_upper"]
            else:
                at_upper_band = pd.Series(False, index=cover_signal.index)

            suppress_cover = rsi_overbought & at_upper_band
            cover_signal = cover_signal & ~suppress_cover

            cover_signal = cover_signal.fillna(False).astype(bool)
            signals[symbol] = cover_signal

        return signals
