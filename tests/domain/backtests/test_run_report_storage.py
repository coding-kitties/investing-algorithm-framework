import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from investing_algorithm_framework import BacktestIndex, OperationalException
from investing_algorithm_framework.domain.backtesting.run_report_storage \
    import iter_run_reports, save_run_reports


class TestRunReportStorage(TestCase):
    def setUp(self):
        self.storage = TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.directory = Path(self.storage.name)
        self.reports = [
            {
                "algorithm_id": algorithm, "study_name": study,
                "engine": engine, "timestamp": f"2020-01-0{offset + 1}",
                "signals": [], "snapshot": {"close": None, "approved": False},
                "confluence_scores": [{
                    "strategy_id": "alpha", "card_id": "entry",
                    "side": "open_long", "score": 0, "qualified": False,
                    "groups": [{"name": "primary", "score": 0}],
                }],
                "data_sources": [{
                    "strategy_id": "alpha", "identifier": "prices",
                    "values": {"Open": 100., "Close": 101.},
                }],
            }
            for offset, (algorithm, study, engine) in enumerate((
                ("one", "train", "event"),
                ("one", "validation", "event"),
                ("one", "train", "vector"),
                ("two", "train", "event"),
            ))
        ]

    def make_index(self, reference):
        return BacktestIndex(self.directory, pd.DataFrame([
            {
                "algorithm_id": report["algorithm_id"],
                "study_name": report["study_name"],
                "engine_type": report["engine"],
                "universe_key": universe,
                "run_reports_path": reference,
            }
            for report in self.reports for universe in (None, "BTC")
        ]))

    def test_report_round_trip_and_scoped_loading_deduplicate_rows(self):
        reference = save_run_reports(self.directory, self.reports)
        index = self.make_index(reference)
        self.assertEqual(index.load_run_reports(), self.reports)
        self.assertIsNone(index.run_reports)
        self.assertEqual(
            index.filter(
                lambda row: row["study_name"] == "train"
                and row["engine_type"] == "event",
            ).load_run_reports(algorithm_id="one"),
            [self.reports[0]],
        )
        self.assertEqual(
            index.filter(
                lambda row: row["universe_key"] == "BTC",
            ).load_run_reports(),
            self.reports,
        )

    def test_multiple_sidecars_use_their_own_row_scopes(self):
        first = save_run_reports(self.directory, self.reports)
        second_report = {**self.reports[0], "study_name": "later"}
        second = save_run_reports(self.directory, [second_report])
        rows = self.make_index(first).df.iloc[[0]].copy()
        second_rows = rows.copy()
        second_rows["study_name"] = "later"
        second_rows["run_reports_path"] = second
        index = BacktestIndex(
            self.directory, pd.concat([rows, second_rows]),
        )
        self.assertEqual(
            index.load_run_reports(), [self.reports[0], second_report],
        )

    def test_qualified_but_blocked_card_preserves_its_signal_outcome(self):
        card = self.reports[0]["confluence_scores"][0]
        card.update(
            qualified=True, signal_status="rejected",
            signal_reason="resolve_conflicts.state_block_open",
        )
        reference = save_run_reports(self.directory, self.reports)
        loaded = self.make_index(reference).load_run_reports()
        self.assertEqual(
            card, loaded[0]["confluence_scores"][0],
        )
        self.assertEqual(self.reports, loaded)

    def test_missing_references_algorithms_and_files_raise(self):
        index = self.make_index("run_reports/missing.jsonl.gz")
        with self.assertRaisesRegex(OperationalException, "not present"):
            index.load_run_reports(algorithm_id="missing")
        with self.assertRaises(FileNotFoundError):
            index.load_run_reports()
        for frame in (
            index.df.drop(columns=["run_reports_path"]),
            index.df.assign(run_reports_path=None),
            index.df.assign(run_reports_path=""),
        ):
            with self.subTest(frame=frame), self.assertRaisesRegex(
                OperationalException, "persist",
            ):
                BacktestIndex(self.directory, frame).load_run_reports()

    def test_cooldown_details_survive_sidecar_and_index_loading(self):
        report = self.reports[0]
        reason = "resolve_conflicts.cooldown_rule"
        details = {"cooldown_bars": 12, "remaining_bars": 5, "scope": "portfolio"}
        report["signals"] = [{
            "strategy_id": "alpha", "timestamp": report["timestamp"],
            "symbol": "BTC", "side": "open_long", "source": "entry",
            "status": "rejected", "reason": reason, "reason_details": details,
        }]
        report["confluence_scores"][0].update(
            qualified=True, signal_status="rejected", signal_reason=reason,
            signal_reason_details=details,
        )
        reference = save_run_reports(self.directory, self.reports)
        loaded = self.make_index(reference).load_run_reports()
        self.assertEqual(self.reports, loaded)
        self.assertEqual(details, loaded[0]["signals"][0]["reason_details"])
        self.assertEqual(
            details, loaded[0]["confluence_scores"][0]["signal_reason_details"],
        )

    def test_empty_saved_capture_is_distinct_from_missing_reports(self):
        reference = save_run_reports(self.directory, [])
        self.assertEqual(list(iter_run_reports(self.directory, reference)), [])
        self.assertEqual(self.make_index(reference).load_run_reports(), [])

    def test_legacy_sidecar_version_is_rejected(self):
        path = self.directory / "legacy.jsonl.gz"
        for version in (1, 2):
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                handle.write(json.dumps({"version": version, "count": 0}) + "\n")
            with self.subTest(version=version), self.assertRaisesRegex(
                OperationalException, "unsupported",
            ):
                list(iter_run_reports(self.directory, path.name))

    def test_corrupt_and_truncated_archives_raise(self):
        reference = save_run_reports(self.directory, self.reports)
        path = self.directory / reference
        original = path.read_bytes()
        for corrupt in (b"invalid", original[:len(original) // 2]):
            path.write_bytes(corrupt)
            with self.subTest(size=len(corrupt)), self.assertRaises(
                (OSError, EOFError),
            ):
                self.make_index(reference).load_run_reports()

    def test_invalid_headers_records_and_counts_raise(self):
        cases = [
            [{"version": 99, "count": 0}],
            [{"version": True, "count": 0}],
            [{"version": 3, "count": 2}, self.reports[0]],
            [{"version": 3, "count": 1}, []],
            [{"version": 3, "count": 1}, {"algorithm_id": "one"}],
        ]
        path = self.directory / "invalid.jsonl.gz"
        for records in cases:
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record) + "\n")
            with self.subTest(records=records), self.assertRaises(
                OperationalException,
            ):
                self.make_index(path.name).load_run_reports()

    def test_failed_write_does_not_publish_partial_sidecar(self):
        invalid = {**self.reports[0], "invalid": float("nan")}
        with self.assertRaises(ValueError):
            save_run_reports(self.directory, [invalid])
        self.assertEqual(list((self.directory / "run_reports").iterdir()), [])
        with patch(
            "investing_algorithm_framework.domain.backtesting."
            "run_report_storage.os.replace",
            side_effect=OSError("Cannot publish"),
        ):
            with self.assertRaisesRegex(OSError, "Cannot publish"):
                save_run_reports(self.directory, self.reports)
        self.assertEqual(list((self.directory / "run_reports").iterdir()), [])

    def test_references_cannot_escape_the_index_directory(self):
        for reference in ("/outside.jsonl.gz", "../outside.jsonl.gz"):
            with self.subTest(reference=reference), self.assertRaisesRegex(
                OperationalException, "relative",
            ):
                self.make_index(reference).load_run_reports()
