import inspect

from .algorithm import Algorithm
from investing_algorithm_framework.app.strategy import TradingStrategy
from investing_algorithm_framework.domain import generate_algorithm_id


class AlgorithmFactory:
    """
    Factory class for creating an algorithm instance.
    """

    @staticmethod
    def _instantiate_strategy(strategy):
        """
        Instantiate a strategy if it's a class, otherwise return as-is.

        Args:
            strategy: Either a TradingStrategy class or instance.

        Returns:
            TradingStrategy instance.
        """
        if inspect.isclass(strategy):
            if issubclass(strategy, TradingStrategy):
                return strategy()
        return strategy

    @staticmethod
    def create_algorithm(
        algorithm=None,
        strategy=None,
        strategies=None,
        tasks=None,
        on_strategy_run_hooks=None,
    ) -> Algorithm:
        """
        Create an instance of an Algorithm with the given parameters.

        If the app already has strategies, tasks, or hooks defined,
        they will be merged with the provided ones.

        If there is no algorithm id provided, an id will be generated and
        also set to each strategy within the algorithm.

        Args:
            algorithm (Algorithm): Instance of Algorithm to be used.
            strategy (TradingStrategy): Single TradingStrategy instance
                or class.
            strategies (list): List of TradingStrategy instances or classes.
            tasks (list): List of Task instances.
            on_strategy_run_hooks (list): List of hooks to be called
                when a strategy is run.

        Returns:
            Algorithm: Instance of Algorithm.
        """
        final_strategies = []
        tasks = tasks or []
        on_strategy_run_hooks = on_strategy_run_hooks or []
        algorithm_id = None

        # First, process algorithm if provided
        if algorithm is not None and isinstance(algorithm, Algorithm):
            final_strategies.extend(algorithm.strategies)
            tasks.extend(algorithm.tasks)
            on_strategy_run_hooks.extend(algorithm.on_strategy_run_hooks)
            algorithm_id = algorithm.algorithm_id

        # Then, add strategies from the strategies list
        if strategies is not None:
            for strat in strategies:
                # Instantiate if it's a class
                strat = AlgorithmFactory._instantiate_strategy(strat)
                # Avoid duplicates by checking strategy_id
                if not any(
                    s.strategy_id == strat.strategy_id
                    for s in final_strategies
                ):
                    final_strategies.append(strat)

        # Finally, add single strategy if provided and not already in list
        if strategy is not None:
            # Instantiate if it's a class
            strategy = AlgorithmFactory._instantiate_strategy(strategy)
            if not any(
                s.strategy_id == strategy.strategy_id
                for s in final_strategies
            ):
                final_strategies.append(strategy)

        # Collect data sources from all strategies (avoiding duplicates)
        data_sources = []
        seen_data_source_ids = set()

        for strategy_entry in final_strategies:
            if strategy_entry.data_sources is not None:
                for ds in strategy_entry.data_sources:
                    ds_id = ds.get_identifier() \
                        if hasattr(ds, 'get_identifier') else id(ds)
                    if ds_id not in seen_data_source_ids:
                        data_sources.append(ds)
                        seen_data_source_ids.add(ds_id)

        # Generate algorithm_id if not provided
        if algorithm_id is None and len(final_strategies) > 0:
            algorithm_id = generate_algorithm_id(
                strategy=final_strategies[0]
            )

        algorithm = Algorithm(
            algorithm_id=algorithm_id,
            strategies=final_strategies,
            tasks=tasks,
            on_strategy_run_hooks=on_strategy_run_hooks,
            data_sources=data_sources
        )
        return algorithm
