import os
from logging import getLogger
from pathlib import Path
from random import Random
from typing import List, Union, Callable

from investing_algorithm_framework.domain.exceptions import \
    OperationalException
from investing_algorithm_framework.domain.utils.custom_tqdm import tqdm

from .backtest import Backtest

logger = getLogger("investing_algorithm_framework")


def save_backtests_to_directory(
    backtests: List[Backtest],
    directory_path: Union[str, Path],
    backtest_date_range=None,
    dir_name_generation_function: Callable[[Backtest], str] = None,
    number_of_backtests_to_save: int = None,
    filter_function: Callable[[Backtest], bool] = None,
    show_progress: bool = False
) -> None:
    """
    Saves a list of Backtest objects to the specified directory.

    Args:
        backtests (List[Backtest]): List of Backtest objects to save.
        directory_path (str): Path to the directory where backtests
            will be saved.
        backtest_date_range (BacktestDateRange, optional): Date range
            to filter backtests before saving. If provided, only backtest runs
            with this date range will be saved. Defaults to None.
        dir_name_generation_function (Callable[[Backtest], str], optional):
            A function that takes a Backtest object as input and returns
            a string to be used as the directory name for that backtest.
            If not provided, the backtest's algorithm_id will be used.
            Defaults to None.
        number_of_backtests_to_save (int, optional): Maximum number of
            backtests to save. If None, all backtests will be saved.
        filter_function (Callable[[Backtest], bool], optional): A function
            that takes a Backtest object as input and returns True if the
            backtest should be saved. Defaults to None.
        show_progress (bool, optional): Whether to display a progress bar
            while saving backtests. Defaults to False.

    Returns:
        None
    """

    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    if show_progress:
        backtests = tqdm(backtests, desc="Saving backtests")

    for backtest in backtests:

        # Check if we have reached the limit of backtests to save
        if number_of_backtests_to_save is not None:
            if number_of_backtests_to_save <= 0:
                break

            number_of_backtests_to_save -= 1

        if filter_function is not None:
            if not filter_function(backtest):
                continue

        if dir_name_generation_function is not None:
            dir_name = dir_name_generation_function(backtest)
        else:

            if not hasattr(backtest, "algorithm_id"):
                raise OperationalException(
                    "algorithm_id is not set in backtest instance,"
                    "cannot generate directory name automatically, "
                    "please make sure to set the algorithm_id field "
                    "in your strategies or provide "
                    "a dir_name_generation_function."
                )

            # Check if there is an ID in the backtest metadata
            dir_name = backtest.algorithm_id

        if dir_name is None:
            logger.warning(
                "Backtest algorithm_id is None. "
                "Generating a random directory name."
            )
            dir_name = str(Random().randint(100000, 999999))

        backtest.save(
            os.path.join(directory_path, dir_name),
            backtest_date_ranges=[backtest_date_range]
            if backtest_date_range else None
        )


def load_backtests_from_directory(
    directory_path: Union[str, Path],
    filter_function: Callable[[Backtest], bool] = None,
    number_of_backtests_to_load: int = None,
    show_progress: bool = False
) -> List[Backtest]:
    """
    Loads Backtest objects from the specified directory.

    Args:
        directory_path (str): Path to the directory from which backtests
            will be loaded.
        filter_function (Callable[[Backtest], bool], optional): A function
            that takes a Backtest object as input and returns True if the
            backtest should be included in the result. Defaults to None.
        number_of_backtests_to_load (int, optional): Maximum number of
            backtests to load. If None, all backtests will be loaded.
        show_progress (bool, optional): Whether to display a progress bar
            while loading backtests. Defaults to False.

    Returns:
        List[Backtest]: List of loaded Backtest objects.
    """

    backtests = []

    if not os.path.exists(directory_path):
        logger.warning(
            f"Directory {directory_path} does not exist. "
            "No backtests loaded."
        )
        return backtests

    dirs = os.listdir(directory_path)

    if show_progress:
        dirs = tqdm(dirs, desc="Loading backtests")

    for file_name in dirs:

        # Check if the filename is not the checkpoints.json file or
        # a python file
        if file_name == "checkpoints.json" or file_name.endswith(".py"):
            continue

        # Check if we have reached the limit of backtests to load
        if number_of_backtests_to_load is not None:
            if number_of_backtests_to_load <= 0:
                break
            number_of_backtests_to_load -= 1

        file_path = os.path.join(directory_path, file_name)

        try:

            # Add step-by-step debugging
            try:
                backtest = Backtest.open(file_path)
            except KeyError as ke:
                logger.error(
                    f"KeyError during Backtest.open for {file_path}: {ke}"
                )
                import traceback
                logger.error(
                    f"Backtest.open KeyError "
                    f"traceback: {traceback.format_exc()}"
                )
                continue  # Skip this backtest and continue with the next one
            except Exception as be:
                logger.error(
                    f"Other error during Backtest.open for {file_path}: {be}"
                )
                import traceback
                logger.error(
                    f"Backtest.open error traceback: {traceback.format_exc()}"
                )
                continue  # Skip this backtest and continue with the next one

            if filter_function is not None:
                try:
                    if not filter_function(backtest):
                        continue
                except Exception as fe:
                    logger.error(
                        f"Error in filter_function for {file_path}: {fe}"
                    )
                    continue

            backtests.append(backtest)

        except Exception as e:
            logger.error(
                f"Unexpected top-level error loading "
                f"backtest from {file_path}: {e}"
            )
            import traceback

    return backtests
