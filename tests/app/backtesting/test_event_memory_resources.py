from datetime import datetime, timedelta, timezone
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
