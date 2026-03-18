import os
import tempfile
from unittest import TestCase
from datetime import datetime, timezone

from investing_algorithm_framework import (
    Backtest,
    BacktestRun,
    BacktestMetrics,
)
from investing_algorithm_framework.cli.validate_backtest_checkpoints import (
    validate_and_create_checkpoints
)


class TestValidateCheckpoints(TestCase):

    def test_validate_checkpoints(self):
        """Test the validate_and_create_checkpoints function."""
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            backtest1_dir = os.path.join(temp_dir, "backtest_algo_001")
            os.makedirs(backtest1_dir)

            start_date1 = datetime(
                2024, 1, 1, tzinfo=timezone.utc
            )
            end_date1 = datetime(
                2024, 6, 30, tzinfo=timezone.utc
            )

            metrics1 = BacktestMetrics(
                backtest_start_date=start_date1,
                backtest_end_date=end_date1
            )

            run1 = BacktestRun(
                backtest_start_date=start_date1,
                backtest_end_date=end_date1,
                trading_symbol="EUR",
                backtest_metrics=metrics1,
                created_at=datetime.now(timezone.utc)
            )

            backtest1 = Backtest(algorithm_id="algo_001", backtest_runs=[run1])
            backtest1.save(backtest1_dir)

            # Backtest 2 (different date range, different algorithm)
            backtest2_dir = os.path.join(temp_dir, "backtest_algo_002")
            os.makedirs(backtest2_dir)

            start_date2 = datetime(2024, 7, 1, tzinfo=timezone.utc)
            end_date2 = datetime(2024, 12, 31, tzinfo=timezone.utc)

            metrics2 = BacktestMetrics(
                backtest_start_date=start_date2,
                backtest_end_date=end_date2
            )

            run2 = BacktestRun(
                backtest_start_date=start_date2,
                backtest_end_date=end_date2,
                backtest_metrics=metrics2,
                trading_symbol="EUR",
                created_at=datetime.now(timezone.utc)
            )

            backtest2 = Backtest(
                algorithm_id="algo_002",
                backtest_runs=[run2]
            )

            backtest2.save(backtest2_dir)

            # Backtest 3 (same date range as backtest 2, different algorithm)
            backtest3_dir = os.path.join(temp_dir, "backtest_algo_003")
            os.makedirs(backtest3_dir)

            start_date3 = datetime(2024, 7, 1, tzinfo=timezone.utc)
            end_date3 = datetime(2024, 12, 31, tzinfo=timezone.utc)

            metrics3 = BacktestMetrics(
                backtest_start_date=start_date3,
                backtest_end_date=end_date3,
            )

            run3 = BacktestRun(
                backtest_start_date=start_date3,
                backtest_end_date=end_date3,
                backtest_metrics=metrics3,
                trading_symbol="EUR",
                created_at=datetime.now(timezone.utc)
            )

            backtest3 = Backtest(
                algorithm_id="algo_003",
                backtest_runs=[run3]
            )

            backtest3.save(backtest3_dir)

            checkpoints = validate_and_create_checkpoints(
                directory_path=temp_dir,
                verbose=True,
                verbose_output_file=os.path.join(
                    temp_dir, "verbose_output.txt"
                )
            )

            expected_date_range_1 = (
                f"{start_date1.isoformat()}_{end_date1.isoformat()}"
            )
            expected_date_range_2 = (
                f"{start_date2.isoformat()}_{end_date2.isoformat()}"
            )

            self.assertIn(expected_date_range_1, checkpoints)
            self.assertIn(expected_date_range_2, checkpoints)

            self.assertIn(
                "algo_001", checkpoints[expected_date_range_1]
            )
            self.assertIn(
                "algo_002", checkpoints[expected_date_range_2]
            )
            self.assertIn(
                "algo_003", checkpoints[expected_date_range_2]
            )

            # Verify checkpoint file was created
            checkpoint_file = os.path.join(temp_dir, "checkpoints.json")
            self.assertTrue(os.path.exists(checkpoint_file))

            # Verify verbose output was written to file
            verbose_file = os.path.join(temp_dir, "verbose_output.txt")
            self.assertTrue(os.path.exists(verbose_file))

            with open(verbose_file, 'r') as f:
                verbose_content = f.read()

            self.assertIn("Scanning directory:", verbose_content)
            self.assertIn("Checkpoint validation complete!", verbose_content)
