from datetime import datetime, timedelta, timezone
from contextlib import ExitStack
from importlib import import_module
from io import StringIO
from unittest import TestCase
from unittest.mock import Mock, patch
import weakref

from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_resources import BacktestResourceError, MemoryGuard


class Snapshot:
    pass


class TestEventMemoryResources(TestCase):
    def make_loop(self):
        return EventLoopService(
            context=Mock(), order_service=Mock(), trade_service=Mock(),
            portfolio_service=Mock(), configuration_service=Mock(),
            data_provider_service=Mock(), portfolio_snapshot_service=Mock(),
        )

    def schedule(self, count):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return {
            start + timedelta(hours=i): {"strategy_ids": [], "task_ids": []}
            for i in range(count)
        }

    def test_snapshot_batches_release_objects_and_save_every_snapshot(self):
        loop = self.make_loop()
        references = []
        batch_sizes = []

        def iterate(**kwargs):
            self.assertLess(sum(ref() is not None for ref in references), 8)
            snapshot = Snapshot()
            references.append(weakref.ref(snapshot))
            loop._snapshots.append(snapshot)

        def save(snapshots):
            batch_sizes.append(len(snapshots))

        loop._portfolio_snapshot_service.save_all = save
        with patch.object(loop, "_run_iteration", side_effect=iterate):
            loop.start(schedule=self.schedule(21), snapshot_batch_size=8)
        self.assertEqual(batch_sizes, [8, 8, 5])
        self.assertEqual(loop._snapshots, [])
        self.assertTrue(all(ref() is None for ref in references))

    def assert_rendered_progress(self, notebook):
        progress_module = import_module(
            "investing_algorithm_framework.domain.utils.custom_tqdm"
        )
        notebook_module = import_module("tqdm.notebook")
        if notebook and notebook_module.IProgress is None:
            self.skipTest("Notebook rendering requires ipywidgets")
        backend_name = "tqdm_notebook" if notebook else "tqdm_terminal"
        backend = getattr(progress_module, backend_name)
        for visible in (True, False):
            with self.subTest(visible=visible):
                loop = self.make_loop()
                output = StringIO()
                bars = []
                observed = []

                def create_bar(*args, **kwargs):
                    bar = backend(
                        *args, **kwargs, file=output, mininterval=0,
                        miniters=1,
                    )
                    bars.append(bar)
                    return bar

                def iterate(**kwargs):
                    if visible:
                        bar = bars[0]
                        observed.append(
                            bar.container.children[1].value if notebook
                            else bar.n
                        )

                with ExitStack() as stack:
                    stack.enter_context(patch.object(
                        progress_module, "is_jupyter_notebook",
                        return_value=notebook,
                    ))
                    stack.enter_context(patch.object(
                        progress_module, backend_name, side_effect=create_bar,
                    ))
                    display = stack.enter_context(patch.object(
                        notebook_module, "display",
                    ))
                    stack.enter_context(patch.object(
                        loop, "_run_iteration", side_effect=iterate,
                    ))
                    loop.start(schedule=self.schedule(4), show_progress=visible)

                self.assertEqual(len(bars), 1)
                self.assertEqual(bars[0].total, 4)
                if visible:
                    self.assertEqual(observed, [0, 1, 2, 3])
                    self.assertEqual(bars[0].n, 4)
                    if notebook:
                        display.assert_called_once_with(bars[0].container)
                        self.assertEqual(bars[0].container.children[1].value, 4)
                    else:
                        self.assertIn("Running event backtest", output.getvalue())
                        self.assertIn("100%", output.getvalue())
                        self.assertIn("4/4", output.getvalue())
                else:
                    display.assert_not_called()
                    self.assertEqual(output.getvalue(), "")

    def test_terminal_progress_renders_and_advances(self):
        self.assert_rendered_progress(notebook=False)

    def test_notebook_progress_displays_widget_and_advances(self):
        self.assert_rendered_progress(notebook=True)

    def test_resource_error_stops_scheduled_iterations(self):
        for show_progress in (False, True):
            with self.subTest(show_progress=show_progress):
                loop = self.make_loop()
                check = Mock(side_effect=[
                    None, None, BacktestResourceError("pressure"),
                ])
                with patch.object(loop, "_run_iteration") as iterate:
                    with self.assertRaisesRegex(
                        BacktestResourceError, "pressure",
                    ):
                        loop.start(
                            schedule=self.schedule(4),
                            show_progress=show_progress, resource_check=check,
                        )
                self.assertEqual(iterate.call_count, 1)

    def test_periodic_guard_polls_at_most_four_times_per_second(self):
        guard = MemoryGuard(memory_budget_mb=1024)
        with patch(
            "investing_algorithm_framework.infrastructure.services."
            "backtesting.vector_resources.monotonic",
            side_effect=[1, 1.1, 1.24, 1.25],
        ), patch.object(guard, "require") as require:
            for _ in range(4):
                guard.check_periodically()
        self.assertEqual(require.call_count, 2)
        with patch.object(guard, "require") as require:
            guard.enabled = False
            guard.check_periodically()
            require.assert_not_called()
