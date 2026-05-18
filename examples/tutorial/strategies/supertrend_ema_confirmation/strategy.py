
from typing import Dict, Any

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder, supertrend, bollinger_bands

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, PositionSize, StopLossRule, TakeProfitRule, \
    ScalingRule, TradingCost, CooldownRule


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
        algorithm_id: str,
        symbols: list[str],
        trading_symbol: str,
        rsi_timeframe: str,
        rsi_period: int,
        rsi_overbought_threshold,
        rsi_oversold_threshold,
        ema_timeframe,
        ema_short_period,
        ema_long_period,
        ema_cross_lookback_window,
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
        time_unit: TimeUnit = TimeUnit.HOUR,
        interval: int = 2,
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
        # Trading cost parameters
        fee_percentage: float = 0.1,
        slippage_percentage: float = 0.05,
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
        trading_costs = []
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
                    percentage_of_portfolio=1 / len(symbols)
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
            trading_costs.append(
                TradingCost(
                    symbol=symbol,
                    fee_percentage=fee_percentage,
                    slippage_percentage=slippage_percentage,
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
            trading_symbol=trading_symbol,
            data_sources=data_sources,
            position_sizes=position_sizes,
            stop_losses=stop_losses,
            take_profits=take_profits,
            scaling_rules=scaling_rules,
            trading_costs=trading_costs,
            cooldowns=cooldowns,
            time_unit=time_unit,
            interval=interval,
            metadata=metadata,
        )

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
            "fee_percentage": fee_percentage,
            "slippage_percentage": slippage_percentage,
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

    def generate_buy_signals(
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

    def generate_sell_signals(
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
