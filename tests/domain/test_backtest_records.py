from datetime import datetime, timedelta, timezone
from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock

from investing_algorithm_framework import (
    ConfluenceCard, DecisionTrace, DecisionTraceEntry, EvaluationContext,
    EvidenceGroup, PrimaryGroup, Requirement, ScoreRule, ScoreType, Veto,
    condition,
)
from investing_algorithm_framework.domain.backtesting.records import (
    CardDefinition, ConfluenceEvaluation, Outcome, canonical_bytes, content_id,
    decode_canonical, decode_trace, diagnostic_record, encode_trace,
    iter_decision_traces, pack_bits, timestamp_us, unpack_bits,
)
from investing_algorithm_framework.domain.backtesting.record_schemas import (
    provenance_id, record_batch, record_schema, validate_provenance,
)


class TestRecordPrimitives(TestCase):
    def test_canonical_profile_and_identity(self):
        self.assertEqual(
            b'["map",[["a",["int","1"]],["b",'
            b'["float","3ff0000000000000"]]]]',
            canonical_bytes({"b": 1.0, "a": 1}),
        )
        self.assertEqual(content_id("card", {"b": 2, "a": 1}),
                         content_id("card", {"a": 1, "b": 2}))
        self.assertNotEqual(content_id("card", 1), content_id("rule", 1))
        self.assertNotEqual(canonical_bytes(1), canonical_bytes(1.0))
        self.assertNotEqual(canonical_bytes(0.0), canonical_bytes(-0.0))
        self.assertEqual(canonical_bytes((1, 2)), canonical_bytes([1, 2]))
        for value in (float("nan"), float("inf"), 2 ** 63, {1: "key"}):
            with self.subTest(value=value), self.assertRaises(
                (ValueError, TypeError)
            ):
                canonical_bytes(value)

    def test_arbitrary_bit_counts_and_invalid_padding(self):
        for count in (0, 1, 8, 9, 64, 65, 513):
            expected = tuple(index % 3 == 0 for index in range(count))
            self.assertEqual(expected, unpack_bits(pack_bits(expected), count))
        self.assertEqual(b'\x81\x01', pack_bits(
            [True] + [False] * 6 + [True, True]
        ))
        for packed, count in ((b'\x80', 1), (b'', 1), (b'\x00', 0)):
            with self.assertRaises(ValueError):
                unpack_bits(packed, count)

    def test_timestamp_is_exact_and_requires_timezone(self):
        self.assertEqual(-1, timestamp_us(datetime(
            1969, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc
        )))
        self.assertEqual(1, timestamp_us(datetime(
            1970, 1, 1, 1, 0, 0, 1,
            tzinfo=timezone(timedelta(hours=1)),
        )))
        with self.assertRaises(ValueError):
            timestamp_us(datetime(2026, 1, 1))


class TestConfluenceRecords(TestCase):
    def setUp(self):
        self.ready = condition("ready", "eq", value=True)
        self.card = ConfluenceCard(
            "Recorded", PrimaryGroup(rules=(
                ScoreRule("duplicate", self.ready, 2),
                ScoreRule("duplicate", self.ready, 3),
            )),
            secondary=(EvidenceGroup("evidence", (
                ScoreRule("secondary", self.ready, 1),
            ), minimum_score=1),),
            scoring=(ScoreRule("penalty", self.ready, -1,
                               ScoreType.NEGATIVE),),
            requirements=(Requirement("ready", self.ready),),
            vetoes=(Veto("blocked", condition("ready", "eq", value=False)),),
            minimum_score=4,
        )

    def make_record(self, card=None, ready=True):
        card = card or self.card
        definition = CardDefinition.from_card(card)
        result = card.evaluate(EvaluationContext({"ready": ready}))
        record = ConfluenceEvaluation.from_result(
            definition, result, attempt_id="attempt-1", sequence=7,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            symbol_id="symbol-1", strategy_id="strategy-1",
        )
        return definition, result, record

    def test_lazy_reconstruction_matches_existing_trace(self):
        for ready in (True, False):
            for card in (self.card, replace(
                self.card, primary=PrimaryGroup(self.ready)
            )):
                with self.subTest(ready=ready, card=card):
                    definition, result, record = self.make_record(card, ready)
                    snapshot = {"ready": ready, "price": 12.5, "missing": None}
                    self.assertEqual(
                        DecisionTrace.from_confluence_result(
                            result, snapshot
                        ).to_dict(),
                        record.to_trace(definition, snapshot).to_dict(),
                    )
                    self.assertEqual(record, ConfluenceEvaluation.from_record(
                        record.to_record(definition), definition
                    ))

    def test_more_than_64_rules_and_duplicate_names(self):
        definition, result, record = self.make_record(replace(
            self.card, scoring=tuple(ScoreRule("same", self.ready, 1)
                                     for _ in range(257))
        ))
        self.assertEqual(
            result.to_dict(), record.to_result(definition).to_dict()
        )
        identities = [definition.rule_id(index)
                      for index in range(len(definition.slots()))]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(record, ConfluenceEvaluation.from_record(
            record.to_record(definition), definition
        ))

    def test_unavailable_and_skipped_are_not_false(self):
        definition, _, record = self.make_record()
        for state in (Outcome.SKIPPED, Outcome.UNAVAILABLE):
            incomplete = replace(
                record, outcomes=bytes([state]) + record.outcomes[1:],
                score=None, qualified=None,
            )
            trace = incomplete.to_trace(definition)
            self.assertIsNone(trace.entries[1].value)
            self.assertIn(state.name.lower(), trace.entries[1].description)
            self.assertEqual(incomplete, ConfluenceEvaluation.from_record(
                incomplete.to_record(definition), definition
            ))
            with self.assertRaises(ValueError):
                incomplete.to_result(definition)

    def test_corrupt_or_mismatched_records_are_rejected(self):
        definition, result, record = self.make_record()
        with self.assertRaises(ValueError):
            record.to_result(CardDefinition.from_card(replace(
                self.card, name="another"
            )))
        for field, value in (
            ("evaluation_id", "bad"), ("primary_outcome", 3),
            ("matched_rule_bits", b'\xff'), ("available_bits", b'\xff'),
        ):
            data = record.to_record(definition)
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                ConfluenceEvaluation.from_record(data, definition)
        with self.assertRaises(ValueError):
            ConfluenceEvaluation.from_result(
                definition, replace(result, card_name="wrong"),
                attempt_id="attempt-1", sequence=7,
                timestamp=datetime.now(timezone.utc), symbol_id="symbol-1",
                strategy_id="strategy-1",
            )

    def test_definition_roundtrip_and_generic_trace(self):
        definition = CardDefinition.from_card(self.card)
        self.assertEqual(self.card, definition.to_card())
        self.assertEqual(self.card.to_dict(), decode_canonical(
            definition.payload
        ))
        trace = DecisionTrace.of(
            DecisionTraceEntry("custom", "paused", description="User hook"),
            DecisionTraceEntry("count", 2, unit="bars"),
            summary="Not a confluence card",
        )
        self.assertEqual(
            trace.to_dict(), decode_trace(encode_trace(trace)).to_dict()
        )
        with self.assertRaises(ValueError):
            CardDefinition.from_card(replace(self.card, version=2))
        with self.assertRaises(ValueError):
            decode_canonical(b'["int","01"]')

    def test_arrow_and_parquet_roundtrip(self):
        import pyarrow as arrow
        import pyarrow.parquet as parquet
        definition, _, record = self.make_record()
        batch = record_batch("confluence_evaluation", [
            record.to_record(definition)
        ])
        output = arrow.BufferOutputStream()
        parquet.write_table(arrow.Table.from_batches([batch]), output)
        table = parquet.read_table(arrow.BufferReader(output.getvalue()))
        self.assertTrue(table.schema.equals(
            record_schema("confluence_evaluation"), check_metadata=True
        ))
        self.assertEqual(record, ConfluenceEvaluation.from_record(
            table.to_pylist()[0], definition
        ))
        self.assertEqual(0, record_batch("confluence_evaluation", []).num_rows)
        with self.assertRaises(ValueError):
            record_batch("confluence_evaluation", [{}])

    def test_execution_links_preserve_many_to_many_causality(self):
        _, _, record = self.make_record()
        links = [{
            "attempt_id": "attempt-1", "sequence": index,
            "timestamp_us": record.timestamp_us,
            "evaluation_id": record.evaluation_id,
            "entity_kind": kind, "entity_id": f"{kind}-1",
            "parent_kind": "order" if kind == "fill" else None,
            "parent_id": "order-1" if kind == "fill" else None,
            "detail_id": None,
        } for index, kind in enumerate((
            "signal", "risk_rejection", "order", "fill"
        ))]
        self.assertEqual(links,
                         record_batch("execution_link", links).to_pylist())
        with self.assertRaises(ValueError):
            record_batch("execution_link", [
                dict(links[0], entity_kind="typo")
            ])

    def test_diagnostics_and_lazy_loading(self):
        definition, result, record = self.make_record()
        snapshot = {"z_last_price": 1.25, "a_first_indicator": None}
        detail = diagnostic_record(
            record.evaluation_id, indicator_snapshot=snapshot,
            expression_outcomes=[("primary/rules/0/expression", Outcome.TRUE)],
            details={"custom_reason": ["risk", 1]},
        )
        record = replace(record, detail_id=detail["detail_id"])
        self.assertEqual([detail], record_batch(
            "diagnostic", [detail]
        ).to_pylist())
        definition_loader = Mock(return_value=definition.payload)
        detail_loader = Mock(return_value=detail["payload"])
        traces = iter_decision_traces(
            iter([record.to_record(definition)]), definition_loader,
            detail_loader,
        )
        definition_loader.assert_not_called()
        detail_loader.assert_not_called()
        self.assertEqual(
            DecisionTrace.from_confluence_result(result, snapshot).to_dict(),
            next(traces).to_dict(),
        )
        definition_loader.assert_called_once_with(definition.card_id)
        detail_loader.assert_called_once_with(detail["detail_id"])
        with self.assertRaises(StopIteration):
            next(traces)
        with self.assertRaises(ValueError):
            diagnostic_record(record.evaluation_id,
                              indicator_snapshot={"bad": float("nan")})

    def test_generic_trace_batch_needs_no_definition(self):
        _, _, record = self.make_record()
        trace = DecisionTrace.of(DecisionTraceEntry("manual", False))
        row = {key: getattr(record, key) for key in (
            "evaluation_id", "attempt_id", "sequence", "timestamp_us",
            "symbol_id", "strategy_id",
        )}
        row["trace_payload"] = encode_trace(trace)
        rows = record_batch("generic_trace", [row]).to_pylist()
        loader = Mock(side_effect=AssertionError("No definition needed"))
        self.assertEqual(trace.to_dict(),
                         next(iter_decision_traces(rows, loader)).to_dict())


class TestReplayProvenance(TestCase):
    def test_provenance_requires_explicit_versions_and_replay_settings(self):
        document = {
            "version": 1, "algorithm_id": "algorithm-1", "study_id": "study-1",
            "window_id": "window-1", "engine_id": "engine-1",
            "strategies": [{
                "strategy_id": "strategy-1", "version": "1",
                "code_digest": "sha256:source", "parameters": {"period": 20},
                "evaluator_version": "scalar-v1", "card_ids": [],
            }],
            "market_data": [{
                "symbol_id": "symbol-1", "provider": "fixture",
                "content_digest": "sha256:input", "start_us": 0,
                "end_us": 10, "timeframe": "1h", "adjustments": [],
            }],
            "indicators": [{
                "name": "ema", "implementation": "package.ema",
                "version": "1", "parameters": {"period": 20},
                "inputs": ["close"], "warmup": 60, "alignment": "bar_close",
                "missing_policy": "unavailable",
            }],
            "execution": {
                "fees": 0.001, "slippage": 0.0, "sizing": "fixed",
                "fill_timing": "next_bar", "risk": [], "conflicts": "raise",
                "seed": 0, "recording_policy": "full",
            },
            "environment": {
                "framework_version": "9", "dependencies": {},
                "platform": "test",
            },
        }
        validate_provenance(document)
        original_id = provenance_id(document)
        changed = dict(document, execution=dict(
            document["execution"], fill_timing="same_bar"
        ))
        self.assertNotEqual(original_id, provenance_id(changed))
        for field in document:
            incomplete = dict(document)
            del incomplete[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_provenance(incomplete)
        with self.assertRaises(ValueError):
            validate_provenance(dict(document, strategies=[{}]))
