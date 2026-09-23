"""Run with python -I after installing both wheels, without source imports."""
from importlib.metadata import distribution
from pathlib import Path
import unittest

import iaf_confluence_native as native
import investing_algorithm_framework as framework


class TestInstalledWheels(unittest.TestCase):
    def test_imports_come_from_installed_distributions(self):
        for name, module in (
            ('iaf-confluence-native', native),
            ('investing-algorithm-framework', framework),
        ):
            installed = distribution(name)
            files = {
                Path(installed.locate_file(item)).resolve()
                for item in installed.files
            }
            self.assertIn(Path(module.__file__).resolve(), files)

    def test_native_contract_and_broker(self):
        expected = {
            'SEMANTICS_VERSION': 'confluence-vector-v1',
            'NETTING_SEMANTICS_VERSION': 'netting-accounting-v5',
            'EXECUTION_SEMANTICS_VERSION': 'static-netting-v1',
            'DRAWDOWN_SEMANTICS_VERSION': 'drawdown-v1',
            'EVENT_FILL_SEMANTICS_VERSION': 'event-fill-v1',
            'EVENT_SCHEDULE_SEMANTICS_VERSION': 'event-schedule-v1',
            'EVENT_ACCOUNTING_SEMANTICS_VERSION': 'event-accounting-v1',
            'EVENT_SETTLEMENT_SEMANTICS_VERSION': 'event-settlement-v1',
            'EVENT_LIFECYCLE_SEMANTICS_VERSION': 'event-lifecycle-v1',
            'EVENT_ARCHIVE_SEMANTICS_VERSION': 'event-archive-v2',
        }
        for name, value in expected.items():
            self.assertEqual(getattr(native, name), value)
        broker = native.EventBroker(1000.0)
        identity = broker.submit('BTC', 0, 2.0, 100.0)
        broker.fill(identity, 1.0, 90.0, 1.0)
        broker.cancel(identity)
        self.assertEqual(broker.cash, 909.0)
        self.assertEqual(broker.position('BTC').amount, 1.0)
        index = native.EventArchiveIndex()
        try:
            index.insert('1000000000000000000')
            index.write('1000000000000000000', 15, 30, None)
            self.assertEqual(list(index.select([], '[]', 0, False)),
                             [('1000000000000000000', 15, 30)])
        finally:
            index.close()

    def test_native_event_adapter(self):
        from investing_algorithm_framework.domain.native_event import \
            native_event_scope, native_event_engine

        with native_event_scope('rust'):
            self.assertIs(native_event_engine(), native)
            self.assertEqual(native.event_cover_plan(
                [(1.0, 100.0, 0.0, 0.0, 2.0, 1.0)], [], 1.0, 80.0, 1.0,
            ), ([(0, 1.0, 2.0, 1.0, 100.0, 17.0, 0.0, 17.0, 3.0)],
                100.0, 17.0))
            self.assertEqual(native.event_exit_values(
                True, 100.0, 80.0, 1.0, 2.0, 1.0, 1.0, 1.0,
            ), (2.0, 1.0, 100.0, 17.0))
        self.assertIsNone(native_event_engine())

    def test_installed_confluence_exact_parity(self):
        import pandas as pd

        card = framework.ConfluenceCard('wheel', framework.PrimaryGroup(
            framework.condition('value', 'gt', value=1.0),
        ))
        frame = pd.DataFrame({'value': [0.0, 2.0, float('nan'), 1.0]})
        pd.testing.assert_frame_equal(
            card.evaluate_series(frame),
            card.evaluate_series(frame, backend='rust'), check_exact=True,
        )


if __name__ == '__main__':
    unittest.main()
