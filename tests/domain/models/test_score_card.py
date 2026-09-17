from unittest import TestCase

from investing_algorithm_framework import (
    DecisionTrace, DecisionTraceEntry, Signal, SignalSide,
)
from investing_algorithm_framework.domain.models.decision_trace import (
    DECISION_TRACE_METADATA_KEY, DECISION_TRACE_VERSION,
)


class TestScoreCardEntry(TestCase):

    def test_requires_non_empty_name(self):
        with self.assertRaises(ValueError):
            DecisionTraceEntry(name="", value=1)

    def test_rejects_non_scalar_value(self):
        with self.assertRaises(ValueError):
            DecisionTraceEntry(name="rsi_14", value=[1, 2, 3])

    def test_accepts_json_scalars(self):
        for value in ("oversold", 28, 28.4, True, None):
            entry = DecisionTraceEntry(name="rsi_14", value=value)
            self.assertEqual(value, entry.value)

    def test_to_dict_and_from_dict_round_trip(self):
        entry = DecisionTraceEntry(
            name="rsi_14", value=28.4, unit="%",
            description="14-period RSI", group="momentum",
        )
        data = entry.to_dict()
        restored = DecisionTraceEntry.from_dict(data)
        self.assertEqual(entry, restored)


class TestScoreCard(TestCase):

    def test_legacy_imports_and_canonical_version_precedence(self):
        from investing_algorithm_framework.domain.models.score_card import (
            ScoreCard, ScoreCardEntry, SCORE_CARD_METADATA_KEY,
        )
        self.assertIs(ScoreCard, DecisionTrace)
        self.assertIs(ScoreCardEntry, DecisionTraceEntry)
        self.assertEqual("score_card", SCORE_CARD_METADATA_KEY)
        trace = DecisionTrace.from_dict({
            "decision_trace_version": 2, "score_card_version": 1,
        })
        self.assertEqual(2, trace.version)
        self.assertEqual(2, trace.to_dict()["score_card_version"])

    def test_to_dict_includes_version(self):
        card = DecisionTrace.of(
            DecisionTraceEntry("rsi_14", 28.4),
            summary="RSI oversold",
        )
        data = card.to_dict()
        self.assertEqual(
            DECISION_TRACE_VERSION, data["decision_trace_version"]
        )
        self.assertEqual("RSI oversold", data["summary"])
        self.assertEqual(1, len(data["entries"]))
        self.assertEqual("rsi_14", data["entries"][0]["name"])

    def test_from_dict_round_trip(self):
        card = DecisionTrace(
            entries=[
                DecisionTraceEntry("rsi_14", 28.4, unit="%"),
                DecisionTraceEntry("close", 41500.0, unit="EUR"),
            ],
            summary="RSI oversold and price above the 200d SMA",
        )
        restored = DecisionTrace.from_dict(card.to_dict())
        self.assertEqual(card, restored)

    def test_from_dict_defaults_missing_version(self):
        restored = DecisionTrace.from_dict({"entries": []})
        self.assertEqual(DECISION_TRACE_VERSION, restored.version)

    def test_from_dict_accepts_legacy_score_card_version(self):
        restored = DecisionTrace.from_dict({
            "score_card_version": 7,
            "entries": [],
        })
        self.assertEqual(7, restored.version)


class TestSignalWithScoreCard(TestCase):

    def test_tracing_example_main_prints_decision_trace(self):
        import json
        from contextlib import redirect_stdout
        from io import StringIO
        from examples.framework_features.decision_tree_tracing import main

        output = StringIO()
        with redirect_stdout(output):
            main()

        trace = DecisionTrace.from_dict(json.loads(output.getvalue()))
        self.assertEqual(
            "RSI oversold while price remains above EMA200", trace.summary
        )
        self.assertEqual(
            {"rsi_14": 28.4, "close": 41500.0, "ema_200": 41230.5},
            {entry.name: entry.value for entry in trace.entries},
        )

    def test_tracing_example_emits_and_records_canonical_traces(self):
        from examples.framework_features.decision_tree_tracing import (
            ExplainedSignalStrategy,
        )
        from investing_algorithm_framework.app.eventloop import (
            _build_signal_report,
        )
        from investing_algorithm_framework import INDEX_DATETIME
        from unittest.mock import Mock

        strategy = ExplainedSignalStrategy()
        signals = list(strategy.generate_signals(None, {"indicators": {
            "rsi_14": 28.4, "close": 41500, "ema_200": 41230,
        }}))
        self.assertIn("decision_trace", signals[0].metadata)

        def collect(state):
            state.raw_signals = list(state.strategy.generate_signals(
                state.context, state.data,
            ))

        phase = Mock()
        phase.run.side_effect = collect
        strategy.phases = [phase]
        strategy.run_strategy(Mock(config={INDEX_DATETIME: None}), {
            "indicators": {"rsi_14": 55, "close": 41500, "ema_200": 41230},
        })
        report = _build_signal_report(strategy)
        self.assertEqual([], report["signals"])
        self.assertEqual(1, len(report["decision_traces"]))
        self.assertEqual(report["decision_traces"], report["score_cards"])

    def test_signal_accepts_legacy_metadata_without_mutating_it(self):
        legacy = {"score_card": {"score_card_version": 3, "entries": []}}
        signal = Signal(symbol="BTC", side=SignalSide.OPEN_LONG,
                        metadata=legacy)
        self.assertEqual(3, signal.metadata["decision_trace"][
            "decision_trace_version"
        ])
        self.assertNotIn("decision_trace", legacy)
        self.assertNotIn("decision_trace_version", legacy["score_card"])

    def test_legacy_method_writes_both_metadata_keys_without_mutation(self):
        trace = DecisionTrace.of(DecisionTraceEntry("ready", True))
        original = Signal(symbol="BTC", side=SignalSide.OPEN_LONG,
                          metadata={"source": "test"})
        signal = original.with_score_card(trace)
        self.assertEqual({"source": "test"}, original.metadata)
        self.assertEqual(signal.metadata["decision_trace"],
                         signal.metadata["score_card"])
        self.assertEqual(
            1, signal.metadata["score_card"]["score_card_version"]
        )

    def test_attaches_score_card_under_reserved_metadata_key(self):
        card = DecisionTrace.of(DecisionTraceEntry("rsi_14", 28.4))
        signal = Signal(
            symbol="BTC", side=SignalSide.OPEN_LONG
        ).with_decision_trace(card)

        self.assertIn(DECISION_TRACE_METADATA_KEY, signal.metadata)
        self.assertEqual(
            card.to_dict(), signal.metadata[DECISION_TRACE_METADATA_KEY]
        )

    def test_preserves_existing_metadata(self):
        card = DecisionTrace.of(DecisionTraceEntry("rsi_14", 28.4))
        signal = Signal(
            symbol="BTC", side=SignalSide.OPEN_LONG,
            metadata={"signal_source": "ema_cross"},
        ).with_decision_trace(card)

        self.assertEqual("ema_cross", signal.metadata["signal_source"])
        self.assertIn(DECISION_TRACE_METADATA_KEY, signal.metadata)
