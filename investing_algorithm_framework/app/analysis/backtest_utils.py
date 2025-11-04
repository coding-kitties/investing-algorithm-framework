import os
from pathlib import Path
from typing import List, Union
from logging import getLogger
from random import Random

from investing_algorithm_framework.domain import Backtest


logger = getLogger("investing_algorithm_framework")


def save_backtests_to_directory(
    backtests: List[Backtest],
    directory_path: Union[str, Path]
) -> None:
    """
    Saves a list of Backtest objects to the specified directory.

    Args:
        backtests (List[Backtest]): List of Backtest objects to save.
        directory_path (str): Path to the directory where backtests
            will be saved.

    Returns:
        None
    """

    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    for backtest in backtests:
        # Check if there is an ID in the backtest metadata
        backtest_id = backtest.metadata.get('id')

        if backtest_id is None:
            logger.warning(
                "Backtest is missing 'id' in metadata. "
                "Generating a random ID as name for backtest file."
            )
            backtest_id = str(Random().randint(100000, 999999))

        backtest.save(os.path.join(directory_path, backtest_id))


def load_backtests_from_directory(
    directory_path: Union[str, Path]
) -> List[Backtest]:
    """
    Loads Backtest objects from the specified directory.

    Args:
        directory_path (str): Path to the directory from which backtests
            will be loaded.

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
            backtests.append(backtest)
        except Exception as e:
            logger.error(
                f"Failed to load backtest from {file_path}: {e}"
            )

    return backtests
