"""Attach a portable decision explanation from inside a strategy.

Run with:

    python3 examples/framework_features/decision_tree_tracing.py
"""
import json

from investing_algorithm_framework import (
    Schedule,
    DecisionTrace,
    DecisionTraceEntry,
    Signal,
    SignalSide,
    TimeUnit,
    TradingStrategy,
)


class ExplainedSignalStrategy(TradingStrategy):
    schedule = Schedule.every(1, TimeUnit.HOUR)
    symbols = ["BTC"]

    def generate_signals(self, context, data):
        indicators = data["indicators"]
        rsi = float(indicators["rsi_14"])
        close = float(indicators["close"])
        ema_200 = float(indicators["ema_200"])

        decision_trace = DecisionTrace.of(
            DecisionTraceEntry(
                name="rsi_14",
                value=rsi,
                description="RSI is in the oversold region",
                group="momentum",
            ),
            DecisionTraceEntry(
                name="close",
                value=close,
                unit="EUR",
                description="Latest closing price",
                group="price",
            ),
            DecisionTraceEntry(
                name="ema_200",
                value=ema_200,
                unit="EUR",
                description="Price is above the long-term trend",
                group="trend",
            ),
            summary="RSI oversold while price remains above EMA200",
        )

        if rsi < 30 and close > ema_200:
            yield Signal(
                symbol="BTC",
                side=SignalSide.OPEN_LONG,
                source="rsi-reversal",
            ).with_decision_trace(decision_trace)
        else:
            self.record_decision_trace(decision_trace, symbol="BTC")


def main() -> None:
    strategy = ExplainedSignalStrategy()

    data = {
        "indicators": {
            "rsi_14": 28.4,
            "close": 41500.0,
            "ema_200": 41230.5,
        },
    }
    signal = next(iter(strategy.generate_signals(None, data)))
    print(json.dumps(signal.metadata["decision_trace"], indent=2))


if __name__ == "__main__":
    main()
