import re
from .algorithm import Algorithm
from investing_algorithm_framework.domain import OperationalException


def validate_algorithm_name(name, illegal_chars=r"[\/:*?\"<>|]"):
    """
    Validate an algorithm name for illegal characters and throw an
        exception if any are found.

    Args:
        name (str): The name to validate.
        illegal_chars (str): A regex pattern for characters considered
            illegal (default: r"[/:*?\"<>|]").

    Raises:
        ValueError: If illegal characters are found in the filename.
    """
    if re.search(illegal_chars, name):
        raise OperationalException(
            f"Illegal characters detected in filename: {name}. "
            f"Illegal characters: {illegal_chars}"
        )


class AlgorithmFactory:
    """
    Factory class for creating an algorithm instance.
    """

    @staticmethod
    def create_algorithm_name(algorithm):
        """
        Create a name for the algorithm based on its
        strategies.

        Args:
            algorithm (Algorithm): Instance of Algorithm.

        Returns:
            str: Name of the algorithm.
        """
        first_strategy = algorithm.strategies[0] \
            if algorithm.strategies else None

        if first_strategy is not None:
            return f"{first_strategy.__class__.__name__}"

        return "DefaultAlgorithm"

    @staticmethod
    def create_algorithm(
        name=None,
        algorithm=None,
        strategy=None,
        strategies=None,
        tasks=None,
        on_strategy_run_hooks=None,
    ) -> Algorithm:
        """
        Create an instance of the specified algorithm type.

        Args:
            name (str): Name of the algorithm.
            algorithm (Algorithm): Instance of Algorithm to be used.
            strategy (TradingStrategy): Single TradingStrategy instance.
            strategies (list): List of TradingStrategy instances.
            tasks (list): List of Task instances.
            on_strategy_run_hooks (list): List of hooks to be called
                when a strategy is run.

        Returns:
            Algorithm: Instance of Algorithm.
        """
        name = name
        strategies = strategies or []
        tasks = tasks or []
        on_strategy_run_hooks = on_strategy_run_hooks or []
        data_sources = []

        if algorithm is not None and isinstance(algorithm, Algorithm):
            if name is None:
                name = algorithm.name

            strategies.extend(algorithm.strategies)
            tasks.extend(algorithm.tasks)
            on_strategy_run_hooks.extend(algorithm.on_strategy_run_hooks)

            if hasattr(algorithm, 'data_sources'):
                data_sources.extend(algorithm.data_sources)

        if strategy is not None:
            strategies.append(strategy)
            data_sources.extend(strategy.data_sources)

        for strategy_entry in strategies:
            if strategy_entry.data_sources is not None \
                    and len(strategy_entry.data_sources):
                data_sources.extend(strategy_entry.data_sources)

        algorithm = Algorithm(
            name=name,
            strategies=strategies,
            tasks=tasks,
            on_strategy_run_hooks=on_strategy_run_hooks,
            data_sources=data_sources
        )

        if algorithm.name is None:
            algorithm.name = AlgorithmFactory.create_algorithm_name(algorithm)

        # Validate the algorithm name
        validate_algorithm_name(algorithm.name)
        return algorithm
