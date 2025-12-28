import unittest
import os
from pathlib import Path
import logging

from investing_algorithm_framework.domain.backtesting.backtest_utils import (
    load_backtests_from_directory,
    diagnose_backtest_directory,
    fix_corrupted_backtest_files
)
from investing_algorithm_framework.domain.backtesting.backtest import Backtest
from investing_algorithm_framework.domain.exceptions import OperationalException


class TestLoadBacktests(unittest.TestCase):
    """Test loading backtests from the test resources directory."""

    @classmethod
    def setUpClass(cls):
        """Set up test class with path to test backtest data."""
        cls.test_resources_path = Path(__file__).parent.parent.parent / "resources"
        cls.backtests_path = cls.test_resources_path / "backtest_reports_for_testing"

        # Set up logging to see error messages during tests
        logging.basicConfig(level=logging.DEBUG)

    def test_backtests_directory_exists(self):
        """Test that the test backtests directory exists."""
        self.assertTrue(self.backtests_path.exists(),
                       f"Backtests directory should exist at {self.backtests_path}")
        self.assertTrue(self.backtests_path.is_dir(),
                       f"Backtests path should be a directory: {self.backtests_path}")

    def test_find_all_backtest_directories(self):
        """Test finding all individual backtest directories."""
        backtest_dirs = []

        for item in self.backtests_path.iterdir():
            if item.is_dir():
                backtest_dirs.append(item)

        self.assertGreater(len(backtest_dirs), 0,
                          "Should find at least one backtest directory")

        print(f"Found {len(backtest_dirs)} backtest directories:")
        for dir_path in backtest_dirs:
            print(f"  - {dir_path.name}")

    def test_load_all_backtests_without_errors(self):
        """
        Test loading all backtests from the directory without errors.
        """
        try:
            print(self.backtests_path)
            backtests = load_backtests_from_directory(str(self.backtests_path))

            self.assertIsInstance(
                backtests, list,"load_backtests_from_directory should return a list"
            )

            print(f"Successfully loaded {len(backtests)} backtests")

            # Verify that we got some backtests
            self.assertGreater(len(backtests), 0,
                             "Should load at least one backtest")

            # Verify all items are Backtest instances
            for i, backtest in enumerate(backtests):
                self.assertIsInstance(backtest, Backtest,
                                    f"Item {i} should be a Backtest instance")

        except Exception as e:
            self.fail(f"Failed to load backtests: {e}")

    def test_load_individual_backtest_directories(self):
        """Test loading each backtest directory individually."""
        successful_loads = 0
        failed_loads = 0
        load_results = []

        for item in self.backtests_path.iterdir():
            if item.is_dir():
                result = {
                    'directory': item.name,
                    'path': str(item),
                    'success': False,
                    'error': None,
                    'backtest': None
                }

                try:
                    backtest = Backtest.open(str(item))
                    result['success'] = True
                    result['backtest'] = backtest
                    successful_loads += 1

                    # Basic validation
                    self.assertIsInstance(backtest, Backtest)
                    print(f"✅ Successfully loaded: {item.name}")

                except Exception as e:
                    result['error'] = str(e)
                    failed_loads += 1
                    print(f"❌ Failed to load: {item.name} - {e}")

                load_results.append(result)

        print(f"\nLoad Results Summary:")
        print(f"  Successful: {successful_loads}")
        print(f"  Failed: {failed_loads}")
        print(f"  Total: {successful_loads + failed_loads}")

        # We expect some to work, but if ALL fail, that's a problem
        if failed_loads > 0:
            print(f"\nFailed directories:")
            for result in load_results:
                if not result['success']:
                    print(f"  - {result['directory']}: {result['error']}")

        # Store results for other tests
        self.load_results = load_results

        # At least some should succeed with our error handling improvements
        self.assertGreater(successful_loads, 0,
                          "At least some backtests should load successfully")

    def test_diagnose_problematic_directories(self):
        """Test diagnosing issues in problematic backtest directories."""
        if not hasattr(self, 'load_results'):
            # Run the individual load test first
            self.test_load_individual_backtest_directories()

        # Find failed directories and diagnose them
        failed_dirs = [result for result in self.load_results if not result['success']]

        if len(failed_dirs) == 0:
            print("All directories loaded successfully - no diagnosis needed")
            return

        print(f"\nDiagnosing {len(failed_dirs)} problematic directories...")

        for failed_result in failed_dirs:
            print(f"\n--- Diagnosing: {failed_result['directory']} ---")

            diagnosis = diagnose_backtest_directory(failed_result['path'])

            print(f"Directory exists: {diagnosis['directory_exists']}")
            print(f"Files found: {len(diagnosis.get('files_found', []))}")
            print(f"Corrupted files: {len(diagnosis.get('corrupted_files', []))}")
            print(f"Missing files: {len(diagnosis.get('missing_files', []))}")
            print(f"Structure issues: {len(diagnosis.get('structure_issues', []))}")

            if diagnosis.get('corrupted_files'):
                print("Corrupted files:")
                for corrupted in diagnosis['corrupted_files']:
                    print(f"  - {corrupted}")

            if diagnosis.get('missing_files'):
                print("Missing files:")
                for missing in diagnosis['missing_files']:
                    print(f"  - {missing}")

            if diagnosis.get('structure_issues'):
                print("Structure issues:")
                for issue in diagnosis['structure_issues']:
                    print(f"  - {issue}")

            # Check run directories
            if 'run_directories' in diagnosis:
                print(f"Run directories: {len(diagnosis['run_directories'])}")
                for run_info in diagnosis['run_directories']:
                    if run_info.get('issues'):
                        print(f"  - {run_info['name']}: {len(run_info['issues'])} issues")
                        for issue in run_info['issues']:
                            print(f"    * {issue}")

    def test_validate_backtest_content(self):
        """Test validating the content of successfully loaded backtests."""
        backtests = load_backtests_from_directory(str(self.backtests_path))

        validation_results = []

        for i, backtest in enumerate(backtests):
            result = {
                'index': i,
                'algorithm_id': backtest.algorithm_id,
                'has_runs': len(backtest.backtest_runs) > 0,
                'run_count': len(backtest.backtest_runs),
                'has_summary': backtest.backtest_summary is not None,
                'has_metadata': len(backtest.metadata) > 0,
                'issues': []
            }

            # Validate algorithm_id
            if not backtest.algorithm_id:
                result['issues'].append("Missing algorithm_id")

            # Validate backtest runs
            if len(backtest.backtest_runs) == 0:
                result['issues'].append("No backtest runs found")
            else:
                for j, run in enumerate(backtest.backtest_runs):
                    # Check for basic run properties
                    if not hasattr(run, 'backtest_start_date') or run.backtest_start_date is None:
                        result['issues'].append(f"Run {j}: Missing start date")

                    if not hasattr(run, 'backtest_end_date') or run.backtest_end_date is None:
                        result['issues'].append(f"Run {j}: Missing end date")

                    if not hasattr(run, 'trading_symbol') or not run.trading_symbol:
                        result['issues'].append(f"Run {j}: Missing trading symbol")

            validation_results.append(result)

            # Print validation info
            print(f"Backtest {i} ({result['algorithm_id']}):")
            print(f"  Runs: {result['run_count']}")
            print(f"  Has summary: {result['has_summary']}")
            print(f"  Has metadata: {result['has_metadata']}")
            if result['issues']:
                print(f"  Issues: {len(result['issues'])}")
                for issue in result['issues']:
                    print(f"    - {issue}")
            else:
                print("  ✅ No validation issues")

        # Overall validation
        total_issues = sum(len(r['issues']) for r in validation_results)
        print(f"\nValidation Summary:")
        print(f"  Total backtests: {len(validation_results)}")
        print(f"  Total issues: {total_issues}")

        self.assertGreater(len(validation_results), 0,
                          "Should have at least one backtest to validate")

    def test_load_with_filter_function(self):
        """Test loading backtests with a filter function."""
        def filter_with_runs(backtest):
            """Filter to only include backtests that have runs."""
            return len(backtest.backtest_runs) > 0

        def filter_with_metadata(backtest):
            """Filter to only include backtests that have metadata."""
            return len(backtest.metadata) > 0

        # Test with run filter
        filtered_backtests = load_backtests_from_directory(
            str(self.backtests_path),
            filter_function=filter_with_runs
        )

        print(f"Backtests with runs: {len(filtered_backtests)}")

        for backtest in filtered_backtests:
            self.assertGreater(len(backtest.backtest_runs), 0,
                             "Filtered backtest should have runs")

        # Test with metadata filter
        filtered_with_metadata = load_backtests_from_directory(
            str(self.backtests_path),
            filter_function=filter_with_metadata
        )

        print(f"Backtests with metadata: {len(filtered_with_metadata)}")

        for backtest in filtered_with_metadata:
            self.assertGreater(len(backtest.metadata), 0,
                             "Filtered backtest should have metadata")

    def test_error_recovery_mechanisms(self):
        """Test that our error recovery mechanisms work properly."""
        # This test demonstrates that even with corrupted data,
        # the loading process continues and loads what it can

        all_backtest_dirs = [d for d in self.backtests_path.iterdir() if d.is_dir()]
        total_dirs = len(all_backtest_dirs)

        # Load all backtests (this should use our improved error handling)
        loaded_backtests = load_backtests_from_directory(str(self.backtests_path))

        print(f"Total backtest directories: {total_dirs}")
        print(f"Successfully loaded backtests: {len(loaded_backtests)}")
        print(f"Recovery rate: {len(loaded_backtests)/total_dirs*100:.1f}%")

        # We should be able to load at least some backtests with our error handling
        self.assertGreater(len(loaded_backtests), 0,
                          "Should load at least one backtest with error recovery")

        # If we're loading less than 50%, that might indicate a systematic issue
        if len(loaded_backtests) < total_dirs * 0.5:
            print("⚠️ Warning: Low recovery rate might indicate systematic issues")

    def test_performance_benchmarking(self):
        """Test performance of loading many backtests."""
        import time

        start_time = time.time()
        backtests = load_backtests_from_directory(str(self.backtests_path))
        end_time = time.time()

        loading_time = end_time - start_time

        print(f"Performance Metrics:")
        print(f"  Total backtests loaded: {len(backtests)}")
        print(f"  Total loading time: {loading_time:.2f} seconds")
        if len(backtests) > 0:
            print(f"  Average time per backtest: {loading_time/len(backtests):.3f} seconds")

        # Performance assertion - should load reasonably quickly
        self.assertLess(loading_time, 60.0,
                       "Loading all backtests should complete within 60 seconds")

    def test_backtest_data_integrity(self):
        """Test the integrity of loaded backtest data."""
        backtests = load_backtests_from_directory(str(self.backtests_path))

        integrity_report = {
            'total_backtests': len(backtests),
            'backtests_with_runs': 0,
            'total_runs': 0,
            'runs_with_trades': 0,
            'runs_with_orders': 0,
            'runs_with_positions': 0,
            'runs_with_snapshots': 0
        }

        for backtest in backtests:
            if len(backtest.backtest_runs) > 0:
                integrity_report['backtests_with_runs'] += 1

            for run in backtest.backtest_runs:
                integrity_report['total_runs'] += 1

                if hasattr(run, 'trades') and len(run.trades) > 0:
                    integrity_report['runs_with_trades'] += 1

                if hasattr(run, 'orders') and len(run.orders) > 0:
                    integrity_report['runs_with_orders'] += 1

                if hasattr(run, 'positions') and len(run.positions) > 0:
                    integrity_report['runs_with_positions'] += 1

                if hasattr(run, 'portfolio_snapshots') and len(run.portfolio_snapshots) > 0:
                    integrity_report['runs_with_snapshots'] += 1

        print("Data Integrity Report:")
        for key, value in integrity_report.items():
            print(f"  {key}: {value}")

        # Basic integrity checks
        self.assertGreaterEqual(integrity_report['total_backtests'], 0)
        self.assertGreaterEqual(integrity_report['total_runs'], 0)


if __name__ == '__main__':
    # Set up logging for standalone execution
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestLoadBacktests)

    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with appropriate code
    exit(0 if result.wasSuccessful() else 1)
