import ast
from contextlib import redirect_stdout
from inspect import signature
from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import pandas as pd

from investing_algorithm_framework import BacktestIndex
from investing_algorithm_framework.app.app import App


NOTEBOOK = (
    Path(__file__).resolve().parents[3] / "examples" / "tutorial"
    / "notebooks" / "03_in_sample_param_sweep.ipynb"
)


class TestTutorialSweepNotebook(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads(NOTEBOOK.read_text())
        cls.source = "".join(next(
            cell["source"] for cell in cls.notebook["cells"]
            if cell.get("id") == "11"
        ))

    def setUp(self):
        self.app = Mock()
        self.app.run_backtest.return_value = BacktestIndex(
            "/unused", pd.DataFrame(columns=["universe_key"]),
        )
        self.namespace = {
            "study": SimpleNamespace(name="in-sample"),
            "strategies": [],
            "data_storage_path": Path("/unused/data"),
            "backtest_results_dir": Path("/unused/results"),
        }
        with patch(
            "investing_algorithm_framework.create_app", return_value=self.app,
        ), patch("os.cpu_count", return_value=12):
            exec(compile(self.source, str(NOTEBOOK), "exec"), self.namespace)
        self.prune = self.namespace["window_metrics_filter_function"]

    def test_every_code_cell_has_valid_python_syntax(self):
        for cell in self.notebook["cells"]:
            if cell["cell_type"] == "code":
                with self.subTest(cell=cell.get("id")):
                    ast.parse("".join(cell["source"]))

    def test_related_tutorial_cells_and_event_worker_options(self):
        for name in (
            "02_strategy_visualization.ipynb",
            "04_in_sample_event_validation.ipynb",
            "06_event_backtest.ipynb",
        ):
            notebook = json.loads((NOTEBOOK.parent / name).read_text())
            for cell in notebook["cells"]:
                if cell["cell_type"] != "code":
                    continue
                with self.subTest(notebook=name, cell=cell.get("id")):
                    tree = ast.parse("".join(cell["source"]))
                    if name.startswith("02"):
                        continue
                    for node in ast.walk(tree):
                        if not isinstance(node, ast.Call) or not isinstance(
                            node.func, ast.Attribute,
                        ) or node.func.attr != "run_backtest":
                            continue
                        options = {kw.arg: kw.value for kw in node.keywords}
                        self.assertEqual(
                            ast.literal_eval(options["n_workers"]), 4,
                        )
                        self.assertEqual(
                            ast.literal_eval(options["memory_budget_mb"]),
                            16_384,
                        )
                        self.assertEqual(
                            ast.literal_eval(
                                options["min_available_memory_mb"],
                            ), 4_096,
                        )

    def test_sweep_uses_index_mode_and_preserves_memory_settings(self):
        self.app.run_backtest.assert_called_once()
        options = self.app.run_backtest.call_args.kwargs
        signature(App.run_backtest).bind(self.app, **options)
        self.assertNotIn("result_mode", options)
        self.assertEqual(
            signature(App.run_backtest).parameters["result_mode"].default,
            "index",
        )
        self.assertEqual(options["memory_budget_mb"], 16_384)
        self.assertEqual(options["min_available_memory_mb"], 4_096)
        self.assertEqual(options["n_workers"], 9)
        self.assertTrue(options["use_checkpoints"])
        self.assertTrue(options["dynamic_position_sizing"])
        self.assertFalse(options["continue_on_error"])
        self.assertIs(options["window_metrics_filter_function"], self.prune)
        self.assertNotIn("window_filter_function", options)
        self.assertNotIn("iterative_summary_update", options)
        self.assertIs(
            self.namespace["backtests_in_sample"],
            self.app.run_backtest.return_value,
        )

    def test_pruning_preserves_thresholds_and_warmup(self):
        cases = [
            ("no-trades", 0, 1, 0, 0, 0, False),
            ("missing-trades", None, 1, 0, 0, 0, False),
            ("nan-trades", float("nan"), 1, 0, 0, 0, False),
            ("warmup", 1, 2, 1, 0, -100, True),
            ("missing-summary", 1, None, None, None, None, True),
            ("mature-winner", 1, 3, 2, 2, 1, True),
            ("inactive", 1, 3, 1, 2, 1, False),
            ("too-many-losses", 1, 3, 2, 1, 1, False),
            ("zero-gain", 1, 3, 2, 2, 0, False),
            ("negative-gain", 1, 3, 2, 2, -1, False),
            ("missing-gain", 1, 3, 2, 2, None, False),
            ("missing-activity", 1, 3, None, 2, 1, False),
            ("inclusive-ratios", 1, 4, 2, 2, 1, True),
        ]
        rows = [
            {
                "algorithm_id": name,
                "universe_key": None,
                "window_number_of_trades_closed": trades,
                "summary.number_of_windows": windows,
                "summary.number_of_windows_with_trades": active,
                "summary.number_of_profitable_windows": profitable,
                "summary.total_net_gain": gain,
            }
            for name, trades, windows, active, profitable, gain, keep in cases
        ]
        rows.append({**rows[5], "universe_key": "per-universe-copy"})
        index = BacktestIndex("/unused", pd.DataFrame(rows))
        original = index.df.copy(deep=True)
        with redirect_stdout(StringIO()):
            result = self.prune(index, SimpleNamespace(name="window"))
        self.assertEqual(
            result.df["algorithm_id"].tolist(),
            [case[0] for case in cases if case[-1]],
        )
        pd.testing.assert_frame_equal(index.df, original)

    def test_empty_index_is_valid(self):
        index = BacktestIndex(
            "/unused", pd.DataFrame(columns=["universe_key"]),
        )
        with redirect_stdout(StringIO()):
            result = self.prune(index, SimpleNamespace(name="empty"))
        self.assertEqual(len(result), 0)

    def test_small_or_unknown_cpu_count_stays_sequential_sized(self):
        for cpu_count in (1, 2, None):
            with self.subTest(cpu_count=cpu_count), patch(
                "investing_algorithm_framework.create_app",
                return_value=self.app,
            ), patch("os.cpu_count", return_value=cpu_count):
                exec(
                    compile(self.source, str(NOTEBOOK), "exec"),
                    self.namespace,
                )
                self.assertEqual(
                    self.app.run_backtest.call_args.kwargs["n_workers"], 1,
                )
