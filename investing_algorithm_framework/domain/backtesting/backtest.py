import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from logging import getLogger
from typing import Dict, Union, List

from investing_algorithm_framework.domain.exceptions \
    import OperationalException

from .backtest_metrics import BacktestMetrics
from .backtest_run import BacktestRun
from .backtest_permutation_test import BacktestPermutationTest
from .backtest_date_range import BacktestDateRange
from .backtest_summary_metrics import BacktestSummaryMetrics
from .combine_backtests import generate_backtest_summary_metrics


logger = getLogger(__name__)


@dataclass
class Backtest:
    """
    Represents a backtest of an algorithm. It contains the backtest metrics,
    backtest results, and paths to strategy and data files.

    Attributes:
        backtest_runs (List[BacktestRun]): A list of backtest runs,
            each representing the performance metrics of a single
            backtest run.
        backtest_summary (BacktestSummaryMetrics): An aggregated view of
            the backtest metrics, combining results from multiple backtests
            metrics into a single summary.
        backtest_permutation_tests (List[BacktestPermutationTestMetrics]): A
            list of backtest permutation tests,
            each representing the performance metrics of a single
            backtest permutation test.
        metadata (Dict[str, str]): Metadata related to the backtest, such as
            configuration parameters or additional information about the
            strategy that was backtested. This can be used for later
            reference or analysis.
        risk_free_rate (float): The risk-free rate used in the backtest,
            typically expressed as a decimal (e.g., 0.03 for 3%). This
        strategy_ids (List[int]): List of strategy IDs associated with
            this backtest.
        algorithm_id (int): The ID of the algorithm associated with this
            backtest.
    """
    algorithm_id: str
    backtest_runs: List[BacktestRun] = field(default_factory=list)
    backtest_summary: BacktestSummaryMetrics = field(default=None)
    backtest_permutation_tests: List[BacktestPermutationTest] = \
        field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    risk_free_rate: float = None
    strategy_ids: List[int] = field(default_factory=list)

    def get_all_backtest_runs(self) -> List[BacktestRun]:
        """
        Retrieve all BacktestRun instances from the backtest.

        Returns:
            List[BacktestRun]: A list of all BacktestRun instances.
        """
        return self.backtest_runs

    def get_backtest_run(
        self, date_range: BacktestDateRange
    ) -> Union[BacktestRun, None]:
        """
        Retrieve a specific BacktestRun based on the provided date range.

        Args:
            date_range (BacktestDateRange): The date range to search for.

        Returns:
            Union[BacktestRun, None]: The matching BacktestRun if found,
                otherwise None.
        """
        for run in self.backtest_runs:
            if (run.backtest_start_date == date_range.start_date and
                    run.backtest_end_date == date_range.end_date):
                return run
        return None

    def get_all_backtest_permutation_tests(
        self
    ) -> List[BacktestPermutationTest]:
        """
        Retrieve all BacktestPermutationTest instances from the backtest.

        Returns:
            List[BacktestPermutationTest]: A list of all
                BacktestPermutationTest instances.
        """
        return self.backtest_permutation_tests

    def get_backtest_permutation_test(
        self, date_range: BacktestDateRange
    ) -> Union[BacktestPermutationTest, None]:
        """
        Retrieve a specific BacktestPermutationTest based on
            the provided date range.

        Args:
            date_range (BacktestDateRange): The date range to search for.

        Returns:
            Union[BacktestPermutationTest, None]: The
                matching BacktestPermutationTest if found,
                otherwise None.
        """
        for perm_test in self.backtest_permutation_tests:
            if (perm_test.backtest_start_date == date_range.start_date and
                    perm_test.backtest_end_date == date_range.end_date):
                return perm_test
        return None

    def get_all_backtest_metrics(self) -> List[BacktestMetrics]:
        """
        Retrieve all BacktestMetrics from the backtest runs.

        Returns:
            List[BacktestMetrics]: A list of BacktestMetrics from
                all backtest runs.
        """
        return [
            run.backtest_metrics for run in self.backtest_runs
            if run.backtest_metrics
        ]

    def get_backtest_metrics(
        self, date_range: BacktestDateRange
    ) -> Union[BacktestMetrics, None]:
        """
        Retrieve the BacktestMetrics for a specific BacktestRun based on
        the provided date range.

        Args:
            date_range (Optional[BacktestDateRange]): The date range to
                search for.

        Returns:
            Union[BacktestMetrics, None]: The BacktestMetrics of the matching
                BacktestRun if found, otherwise None.
        """
        run = self.get_backtest_run(date_range)
        if run:
            return run.backtest_metrics
        return None

    def to_dict(self) -> dict:
        """
        Convert the Backtest instance to a dictionary.

        Returns:
            dict: A dictionary representation of the Backtest instance.
        """

        backtest_summary = self.backtest_summary.to_dict() \
            if self.backtest_summary else None
        return {
            "backtest_runs": [
                    br.to_dict() for br in self.backtest_runs
                ] if self.backtest_runs else None,
            "backtest_summary": backtest_summary,
            "backtest_permutation_tests":
                [
                    bpt.to_dict() for bpt in self.backtest_permutation_tests
                ] if self.backtest_permutation_tests else None,
            "metadata": self.metadata,
            "risk_free_rate": self.risk_free_rate,
            "strategy_ids": self.strategy_ids,
            "algorithm_id": self.algorithm_id
        }

    @staticmethod
    def open(
        directory_path: Union[str, Path],
        backtest_date_ranges: List[BacktestDateRange] = None
    ) -> 'Backtest':
        """
        Open a backtest report from a directory and return a Backtest instance.

        Args:
            directory_path (str): The path to the directory containing the
                backtest report files.
            backtest_date_ranges (List[BacktestDateRange], optional): A list of
                date ranges to filter the backtest runs. If provided, only
                backtest runs matching these date ranges will be loaded.

        Returns:
            Backtest: An instance of Backtest with the loaded metrics
                and results.

        Raises:
            OperationalException: If the directory does not exist or if
            there is an error loading the files.
        """
        algorithm_id = None
        backtest_runs = []
        backtest_summary_metrics = None
        permutation_metrics = []
        metadata = {}
        risk_free_rate = None

        if not os.path.exists(directory_path):
            raise OperationalException(
                f"The directory {directory_path} does not exist."
            )

        # Load algorithm_id if available
        id_file = os.path.join(directory_path, "algorithm_id.json")

        if os.path.isfile(id_file):
            with open(id_file, 'r') as f:
                try:
                    algorithm_id = json.load(f).get('algorithm_id', None)
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding algorithm_id JSON: {e}")
                    algorithm_id = None

        # Load all backtest runs
        runs_dir = os.path.join(directory_path, "runs")

        if os.path.isdir(runs_dir):
            for dir_name in os.listdir(runs_dir):
                run_path = os.path.join(runs_dir, dir_name)
                if os.path.isdir(run_path):

                    if backtest_date_ranges is not None:
                        temp_run = BacktestRun.open(run_path)
                        match_found = False

                        for date_range in backtest_date_ranges:
                            if (
                                temp_run.backtest_start_date ==
                                date_range.start_date and
                                temp_run.backtest_end_date ==
                                date_range.end_date
                            ):

                                if date_range.name is not None:
                                    if (
                                        temp_run.backtest_date_range_name ==
                                        date_range.name
                                    ):
                                        match_found = True
                                        break
                                else:
                                    match_found = True
                                    break

                        if not match_found:
                            continue

                    backtest_runs.append(BacktestRun.open(run_path))

        # Load combined backtests summary
        if backtest_date_ranges is not None:
            summary_file = os.path.join(directory_path, "summary.json")

            if os.path.isfile(summary_file):
                backtest_summary_metrics = \
                    BacktestSummaryMetrics.open(summary_file)
        else:
            # Generate new summary from loaded backtest runs
            temp_metrics = []
            for br in backtest_runs:
                if br.backtest_metrics:
                    temp_metrics.append(br.backtest_metrics)

            backtest_summary_metrics = \
                generate_backtest_summary_metrics(temp_metrics)

        # Load backtest permutation test metrics
        perm_test_dir = os.path.join(directory_path, "permutation_tests")

        if os.path.isdir(perm_test_dir):
            for dir_name in os.listdir(perm_test_dir):
                perm_test_file = os.path.join(perm_test_dir, dir_name)
                if os.path.isdir(perm_test_file):
                    permutation_metrics.append(
                        BacktestPermutationTest.open(perm_test_file)
                    )

        # Load metadata if available
        meta_file = os.path.join(directory_path, "metadata.json")

        if os.path.isfile(meta_file):
            with open(meta_file, 'r') as f:
                metadata = json.load(f)

        # Load risk-free rate if available
        risk_free_rate_file = os.path.join(
            directory_path, "risk_free_rate.json"
        )

        if os.path.isfile(risk_free_rate_file):
            with open(risk_free_rate_file, 'r') as f:
                try:
                    risk_free_rate = json.load(f).get(
                        'risk_free_rate', None
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding risk-free rate JSON: {e}")
                    risk_free_rate = None

        return Backtest(
            algorithm_id=algorithm_id,
            backtest_runs=backtest_runs,
            backtest_summary=backtest_summary_metrics,
            backtest_permutation_tests=permutation_metrics,
            metadata=metadata,
            risk_free_rate=risk_free_rate
        )

    def save(self, directory_path: Union[str, Path]) -> None:
        """
        Save the backtest metrics to a file in JSON format. The metrics will
        always be saved in a file named `metrics.json`

        Args:
            directory_path (str): The directory where the metrics
            file will be saved.

        Raises:
            OperationalException: If the directory does not exist or if
            there is an error saving the files.

        Returns:
            None: This method does not return anything, it saves the
            metrics to a file.
        """
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        # Call the save method of all backtest runs
        if self.backtest_runs:
            run_path = os.path.join(directory_path, "runs")
            os.makedirs(run_path, exist_ok=True)

            for br in self.backtest_runs:
                dir_name = br.create_directory_name()
                destination_run_path = os.path.join(run_path, dir_name)
                os.makedirs(destination_run_path, exist_ok=True)
                br.save(destination_run_path)

        # Save combined backtest metrics if available
        if self.backtest_summary:
            summary_file = os.path.join(
                directory_path, "summary.json"
            )
            self.backtest_summary.save(summary_file)

        if self.backtest_permutation_tests:
            permutation_dir_path = os.path.join(
                directory_path, "permutation_tests"
            )
            os.makedirs(permutation_dir_path, exist_ok=True)

            for pm in self.backtest_permutation_tests:
                dir_name = pm.create_directory_name()
                pm_path = os.path.join(permutation_dir_path, dir_name)
                pm.save(pm_path)

        # Save metadata if available
        if self.metadata:
            meta_file = os.path.join(directory_path, "metadata.json")
            with open(meta_file, 'w') as f:
                json.dump(self.metadata, f, indent=4)

        # Save risk-free rate if available
        if self.risk_free_rate is not None:
            risk_free_rate_file = os.path.join(
                directory_path, "risk_free_rate.json"
            )
            with open(risk_free_rate_file, 'w') as f:
                json.dump(
                    {'risk_free_rate': self.risk_free_rate}, f, indent=4
                )

        # Save strategy IDs if available
        if self.strategy_ids:
            strategy_ids_file = os.path.join(
                directory_path, "strategy_ids.json"
            )
            with open(strategy_ids_file, 'w') as f:
                json.dump({'strategy_ids': self.strategy_ids}, f, indent=4)

        # Save algorithm ID if available
        if self.algorithm_id is not None:
            algorithm_id_file = os.path.join(
                directory_path, "algorithm_id.json"
            )
            with open(algorithm_id_file, 'w') as f:
                json.dump(
                    {'algorithm_id': self.algorithm_id}, f, indent=4
                )

        # Save the permutation tests if available
        if self.backtest_permutation_tests:
            permutation_tests_path = os.path.join(
                directory_path, "permutation_tests"
            )
            os.makedirs(permutation_tests_path, exist_ok=True)

            for bpt in self.backtest_permutation_tests:
                dir_name = bpt.create_directory_name()
                bpt_path = os.path.join(permutation_tests_path, dir_name)
                os.makedirs(bpt_path, exist_ok=True)
                bpt.save(bpt_path)

    def __repr__(self):
        """
        Return a string representation of the Backtest instance.

        Returns:
            str: A string representation of the Backtest instance.
        """
        return json.dumps(
            self.to_dict(), indent=4, sort_keys=True, default=str
        )

    def merge(self, other: 'Backtest') -> 'Backtest':
        """
        Function to merge another Backtest instance into this one.

        Args:
            other (Backtest): The other Backtest instance to merge.

        Returns:
            Backtest: The merged Backtest instance.
        """

        merged = Backtest()
        merged.backtest_runs = self.backtest_runs + other.backtest_runs

        summary = BacktestSummaryMetrics()

        for bt_run in merged.get_all_backtest_metrics():
            summary.add(bt_run)

        merged.backtest_summary = summary
        merged.backtest_permutation_tests = \
            self.backtest_permutation_tests + other.backtest_permutation_tests

        # Merge metadata
        merged.metadata = {**self.metadata, **other.metadata}

        if self.risk_free_rate is None:
            merged.risk_free_rate = other.risk_free_rate

        if self.strategy_ids is None:
            merged.strategy_ids = other.strategy_ids

        if self.algorithm_id is None:
            merged.algorithm_id = other.algorithm_id

        return merged

    def get_metadata(self) -> Dict[str, str]:
        """
        Get the metadata of the backtest.

        Returns:
            Dict[str, str]: A dictionary containing the metadata
                of the backtest.
        """
        return self.metadata

    def get_backtest_date_ranges(self):
        """
        Get the date ranges for the backtest.

        Returns:
            List[BacktestDateRange]: A list of BacktestDateRange objects
                representing the date ranges for each backtest run.
        """
        return [
            BacktestDateRange(
                start_date=run.backtest_start_date,
                end_date=run.backtest_end_date,
                name=run.backtest_date_range_name
            )
            for run in self.backtest_runs
        ]

    def add_permutation_test(
        self, permutation_test: BacktestPermutationTest
    ) -> None:
        """
        Add a permutation test to the backtest.

        Args:
            permutation_test (BacktestPermutationTest): The permutation test
                to add.
        """
        self.backtest_permutation_tests.append(permutation_test)

    def __hash__(self):
        if self.algorithm_id is None:
            raise ValueError(
                "Cannot hash Backtest without an algorithm_id value, Please "
                "make sure the Backtest instance has an algorithm_id set."
            )

        meta_id = self.metadata.get("algorithm_id")
        return hash(meta_id)

    def __eq__(self, other):
        if not isinstance(other, Backtest):
            return False

        return self.algorithm_id == other.algorithm_id
