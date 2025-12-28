import os
from pathlib import Path
from typing import List, Union, Callable
from logging import getLogger
from random import Random

from .backtest import Backtest
from investing_algorithm_framework.domain.exceptions import \
    OperationalException


logger = getLogger("investing_algorithm_framework")


def save_backtests_to_directory(
    backtests: List[Backtest],
    directory_path: Union[str, Path],
    dir_name_generation_function: Callable[[Backtest], str] = None,
    number_of_backtests_to_save: int = None,
    filter_function: Callable[[Backtest], bool] = None
) -> None:
    """
    Saves a list of Backtest objects to the specified directory.

    Args:
        backtests (List[Backtest]): List of Backtest objects to save.
        directory_path (str): Path to the directory where backtests
            will be saved.
        dir_name_generation_function (Callable[[Backtest], str], optional):
            A function that takes a Backtest object as input and returns
            a string to be used as the directory name for that backtest.
            If not provided, the backtest's metadata 'id' will be used.
            Defaults to None.
        number_of_backtests_to_save (int, optional): Maximum number of
            backtests to save. If None, all backtests will be saved.
        filter_function (Callable[[Backtest], bool], optional): A function
            that takes a Backtest object as input and returns True if the
            backtest should be saved. Defaults to None.

    Returns:
        None
    """

    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

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

            if backtest.algorithm_id is None:
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
                "Backtest metadata does not contain an 'id' field. "
                "Generating a random directory name."
            )
            dir_name = str(Random().randint(100000, 999999))

        backtest.save(os.path.join(directory_path, dir_name))


def load_backtests_from_directory(
    directory_path: Union[str, Path],
    filter_function: Callable[[Backtest], bool] = None,
    number_of_backtests_to_load: int = None
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

    for file_name in os.listdir(directory_path):

        # Check if we have reached the limit of backtests to load
        if number_of_backtests_to_load is not None:
            if number_of_backtests_to_load <= 0:
                break
            number_of_backtests_to_load -= 1

        file_path = os.path.join(directory_path, file_name)

        try:
            backtest = Backtest.open(file_path)

            if filter_function is not None:
                if not filter_function(backtest):
                    continue

            backtests.append(backtest)
        except Exception as e:
            logger.error(
                f"Failed to load backtest from {file_path}: {e}"
            )

    return backtests
