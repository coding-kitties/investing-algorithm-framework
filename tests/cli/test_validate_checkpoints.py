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
                verbose=True
            )

            expected_date_range_1 = f"{start_date1.isoformat()}_{end_date1.isoformat()}"
            expected_date_range_2 = f"{start_date2.isoformat()}_{end_date2.isoformat()}"

            assert expected_date_range_1 in checkpoints, \
                f"Date range {expected_date_range_1} not found in checkpoints"

            assert expected_date_range_2 in checkpoints, \
                f"Date range {expected_date_range_2} not found in checkpoints"

            assert "algo_001" in checkpoints[expected_date_range_1], \
                "algo_001 not found in first date range"

            assert "algo_002" in checkpoints[expected_date_range_2], \
                "algo_002 not found in second date range"

            assert "algo_003" in checkpoints[expected_date_range_2], \
                "algo_003 not found in second date range"

            # Verify checkpoint file was created
            checkpoint_file = os.path.join(temp_dir, "checkpoints.json")
            assert os.path.exists(checkpoint_file), "Checkpoint file was not created"
