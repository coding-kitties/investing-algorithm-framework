from enum import Enum


class BacktestEngine(Enum):
    VECTOR = "vector"
    EVENT_DRIVEN = "event_driven"

    @staticmethod
    def from_string(engine_str: str) -> "BacktestEngine":
        """
        Convert a string to a BacktestEngine enum member.

        Args:
            engine_str (str): The string representation of the backtest
                engine.

        Returns:
            BacktestEngine: The corresponding BacktestEngine enum member.

        Raises:
            ValueError: If the provided string does not match any
                BacktestEngine.
        """
        try:
            return BacktestEngine(engine_str)
        except ValueError:
            raise ValueError(
                f"Invalid backtest engine '{engine_str}'. "
                f"Valid options are: {[e.value for e in BacktestEngine]}"
            )

    @staticmethod
    def from_value(value) -> "BacktestEngine":
        """
        Convert a value to a BacktestEngine enum member.

        Args:
            value: The value representation of the backtest engine.

        Returns:
            BacktestEngine: The corresponding BacktestEngine enum member.

        Raises:
            ValueError: If the provided value does not match any
                BacktestEngine.
        """
        if isinstance(value, BacktestEngine):
            return value

        if isinstance(value, str):
            return BacktestEngine.from_string(value)

        raise ValueError(
            f"Invalid backtest engine value '{value}'. "
            f"Valid options are: {[e.value for e in BacktestEngine]}"
        )
