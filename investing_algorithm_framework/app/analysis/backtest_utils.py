import os
from pathlib import Path
from typing import List, Union, Callable
from logging import getLogger
from random import Random

from investing_algorithm_framework.domain import Backtest


logger = getLogger("investing_algorithm_framework")


def save_backtests_to_directory(
    backtests: List[Backtest],
    directory_path: Union[str, Path],
    dir_name_generation_function: Callable[[Backtest], str] = None,
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
        filter_function (Callable[[Backtest], bool], optional): A function
            that takes a Backtest object as input and returns True if the
            backtest should be saved. Defaults to None.

    Returns:
        None
    """

    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    for backtest in backtests:

        if filter_function is not None:
            if not filter_function(backtest):
                continue

        if dir_name_generation_function is not None:
            dir_name = dir_name_generation_function(backtest)
        else:
            # Check if there is an ID in the backtest metadata
            dir_name = backtest.metadata.get('id', None)

        if dir_name is None:
            logger.warning(
                "Backtest metadata does not contain an 'id' field. "
                "Generating a random directory name."
            )
            dir_name = str(Random().randint(100000, 999999))

        backtest.save(os.path.join(directory_path, dir_name))


def load_backtests_from_directory(
    directory_path: Union[str, Path],
    filter_function: Callable[[Backtest], bool] = None
) -> List[Backtest]:
    """
    Loads Backtest objects from the specified directory.

    Args:
        directory_path (str): Path to the directory from which backtests
            will be loaded.
        filter_function (Callable[[Backtest], bool], optional): A function
            that takes a Backtest object as input and returns True if the
            backtest should be included in the result. Defaults to None.

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
