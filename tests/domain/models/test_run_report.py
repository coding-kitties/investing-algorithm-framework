from datetime import datetime, timedelta, timezone
import json
from unittest import TestCase

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from investing_algorithm_framework import RunReport
from investing_algorithm_framework.domain import Environment
from investing_algorithm_framework.infrastructure.models import SQLRunReport


class TestRunReportSchema(TestCase):
    def test_execution_ids_are_unique_and_use_utc_start_time(self):
        started = datetime(
            2020, 1, 1, 2, 30, tzinfo=timezone(timedelta(hours=2)),
        )
        reports = [
            RunReport(algorithm_id="multi", started_at=started)
            for _ in range(100)
        ]
        self.assertEqual(100, len({report.id for report in reports}))
        for report in reports:
            self.assertRegex(
                report.id, r"^multi_20200101T003000\.000000Z_[0-9a-f]{32}$",
            )
            self.assertEqual(
                report.id, RunReport.from_dict(report.to_dict()).id,
            )

    def test_strategy_ids_are_sorted_unique_without_signals(self):
        report = RunReport(
            algorithm_id="multi", strategy_ids=["beta", "alpha", "beta"],
        )
        self.assertEqual(["alpha", "beta"], report.strategy_ids)
        self.assertEqual([], report.signals)
        self.assertEqual(
            report.to_dict(), RunReport.from_dict(report.to_dict()).to_dict(),
        )

    def test_strategy_attribution_can_be_inferred_from_records(self):
        report = RunReport(
            signals=[{"strategy_id": "alpha", "symbol": "BTC", "side": "open_long"}],
            orders=[{"strategy_id": "beta"}],
            trades=[{"strategy_id": "alpha"}],
            decision_traces=[{"strategy_id": "gamma", "entries": []}],
        )
        self.assertEqual(["alpha", "beta", "gamma"], report.strategy_ids)

    def test_environment_enum_is_json_serializable_in_report(self):
        self.assertEqual("PAPER", json.loads(json.dumps(
            RunReport(environment=Environment.PAPER).to_dict(),
        ))["environment"])

    def test_indicators_default_to_an_independent_empty_list(self):
        first, second = RunReport(), RunReport()
        self.assertEqual([], first.to_dict()["indicators"])
        self.assertIsNot(first.indicators, second.indicators)

    def test_indicator_values_are_json_safe_and_detached(self):
        records = [{
            "strategy_id": "alpha", "symbol": "BTC",
            "timestamp": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "name": f"indicator.{offset}", "value": value,
        } for offset, value in enumerate((
            np.float64(1.25), float("nan"), float("inf"),
            -float("inf"), np.bool_(True), None,
        ))]
        report = RunReport(indicators=records)
        output = report.to_dict()
        self.assertEqual(["alpha"], report.strategy_ids)
        self.assertEqual(
            [1.25, None, None, None, True, None],
            [record["value"] for record in output["indicators"]],
        )
        self.assertEqual(
            "2020-01-01T00:00:00+00:00",
            output["indicators"][0]["timestamp"],
        )
        json.dumps(output, allow_nan=False)
        self.assertEqual(output, RunReport.from_dict(output).to_dict())
        records[0]["value"] = -1
        output["indicators"][0]["value"] = -2
        self.assertEqual(1.25, report.indicators[0]["value"])
        with self.assertRaisesRegex(TypeError, "JSON scalars"):
            RunReport(indicators=[{"name": "invalid", "value": [1, 2]}])

    def test_sql_round_trip_exposes_execution_id_not_internal_key(self):
        engine = create_engine("sqlite:///:memory:")
        self.addCleanup(engine.dispose)
        SQLRunReport.__table__.create(engine)
        with Session(engine) as session:
            report = SQLRunReport(
                algorithm_id="multi", strategy_ids=["alpha", "beta"],
                indicators=[{
                    "strategy_id": "alpha", "symbol": "BTC",
                    "timestamp": "2020-01-01T00:00:00+00:00",
                    "name": "trend.value", "value": 123.0,
                }],
                signals=[{
                    "strategy_id": "alpha", "symbol": "BTC",
                    "side": "open_long", "timestamp": datetime(2020, 1, 1),
                    "status": "approved",
                }],
                confluence_scores=[{
                    "strategy_id": "alpha", "card_id": "entry",
                    "timestamp": datetime(2020, 1, 1),
                    "score": np.float64(3), "groups": [{"score": 3}],
                }],
                data_sources=[{
                    "strategy_id": "alpha", "identifier": "prices",
                    "timestamp": datetime(2020, 1, 1),
                    "values": {"Close": np.float64(123)},
                }],
                stop_losses=[{
                    "strategy_id": "alpha", "order_id": "stop",
                    "event_type": "trigger",
                    "timestamp": datetime(2020, 1, 1),
                }],
                take_profits=[{
                    "strategy_id": "beta", "order_id": "profit",
                    "event_type": "fill", "amount": np.float64(2),
                }],
            )
            report_id = report.id
            session.add(report)
            session.commit()
            session.expunge_all()
            stored = session.query(SQLRunReport).filter_by(id=report_id).one()
            self.assertEqual(report_id, stored.to_dict()["id"])
            self.assertIsInstance(stored.storage_id, int)
            self.assertEqual(["alpha", "beta"], stored.strategy_ids)
            self.assertEqual(report.indicators, stored.indicators)
            self.assertEqual(report.confluence_scores, stored.confluence_scores)
            self.assertEqual(report.data_sources, stored.data_sources)
            self.assertEqual(report.signals, stored.signals)
            self.assertEqual(report.stop_losses, stored.stop_losses)
            self.assertEqual(report.take_profits, stored.take_profits)
            stored.update({
                "strategy_ids": ["gamma"], "indicators": [],
                "confluence_scores": [], "data_sources": [],
                "stop_losses": [], "take_profits": [],
            })
            session.commit()
            session.expunge_all()
            self.assertEqual(
                ["gamma"],
                session.query(SQLRunReport).filter_by(id=report_id)
                .one().strategy_ids,
            )
            self.assertEqual(
                [], session.query(SQLRunReport).filter_by(id=report_id)
                .one().indicators,
            )
            self.assertEqual([], session.query(SQLRunReport).filter_by(
                id=report_id,
            ).one().confluence_scores)
            self.assertEqual([], session.query(SQLRunReport).filter_by(
                id=report_id,
            ).one().data_sources)
            self.assertEqual([], session.query(SQLRunReport).filter_by(
                id=report_id,
            ).one().stop_losses)
            self.assertEqual([], session.query(SQLRunReport).filter_by(
                id=report_id,
            ).one().take_profits)

    def test_protective_reports_are_detached_json_safe_and_attributed(self):
        events = [{"strategy_id": "risk", "amount": np.float64(2)}]
        report = RunReport(stop_losses=events)
        self.assertEqual(["risk"], report.strategy_ids)
        payload = report.to_dict()
        self.assertEqual(payload, RunReport.from_dict(payload).to_dict())
        json.dumps(payload, allow_nan=False)
        events.clear()
        payload["stop_losses"].clear()
        self.assertEqual(2, report.stop_losses[0]["amount"])
        self.assertEqual([], RunReport.from_dict({}).take_profits)

    def test_existing_database_gets_protective_columns_idempotently(self):
        from sqlalchemy import inspect
        from investing_algorithm_framework.infrastructure.database.sql_alchemy \
            import _apply_forward_only_migrations

        engine = create_engine("sqlite:///:memory:")
        self.addCleanup(engine.dispose)
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE run_reports (id TEXT)")
        _apply_forward_only_migrations(engine)
        _apply_forward_only_migrations(engine)
        names = {c["name"] for c in inspect(engine).get_columns("run_reports")}
        self.assertTrue({"stop_losses_json", "take_profits_json"} <= names)

    def test_flat_signals_and_new_lists_are_detached_and_json_safe(self):
        source = {
            "strategy_id": "source", "timestamp": datetime(2020, 1, 1),
            "values": {"Close": np.float64(12), "Volume": float("nan")},
        }
        card = {
            "strategy_id": "card", "score": np.float64(3),
            "groups": [{"matched": np.bool_(False)}],
        }
        report = RunReport(data_sources=[source], confluence_scores=[card])
        payload = report.to_dict()
        self.assertEqual(["card", "source"], report.strategy_ids)
        self.assertEqual(None, payload["data_sources"][0]["values"]["Volume"])
        json.dumps(payload, allow_nan=False)
        self.assertEqual(payload, RunReport.from_dict(payload).to_dict())
        source["values"]["Close"] = -1
        card["groups"].clear()
        payload["confluence_scores"].clear()
        self.assertEqual(12, report.data_sources[0]["values"]["Close"])
        self.assertEqual([{"matched": False}], report.confluence_scores[0]["groups"])
        with self.assertRaisesRegex(ValueError, "flat signal entries"):
            RunReport(signals=[{"strategy_id": "legacy", "signals": []}])

    def test_execution_ids_are_supported_by_event_memory_repository(self):
        from investing_algorithm_framework.infrastructure.repositories \
            .event_memory import event_memory_scope
        from investing_algorithm_framework.infrastructure.repositories \
            .run_report_repository import SQLRunReportRepository

        repository = SQLRunReportRepository()
        with event_memory_scope():
            report = repository.create({
                "algorithm_id": "multi", "strategy_ids": ["alpha", "beta"],
                "indicators": [{
                    "strategy_id": "alpha", "symbol": "BTC",
                    "name": "trend.value", "value": 123.0,
                    "timestamp": "2020-01-01T00:00:00+00:00",
                }],
            })
            self.assertIsInstance(report.id, str)
            self.assertEqual(
                report.to_dict(), repository.get(report.id).to_dict(),
            )
