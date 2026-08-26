from typing import Optional
from investing_algorithm_framework.domain.exceptions import \
    OperationalException


class PositionSize:
    """
    Defines how much capital to allocate to a specific symbol.

    Attributes:
        symbol (str | None): The target symbol (e.g. "BTC"). When
            ``None``, this is a **default** applied to every symbol
            that doesn't have its own symbol-specific ``PositionSize``
            — a symbol-specific entry always takes precedence over
            the default.
    """

    def __init__(
        self,
        symbol: str = None,
        percentage_of_portfolio: Optional[float] = None,
        fixed_amount: Optional[float] = None
    ):
        self.symbol = symbol
        self.percentage_of_portfolio = percentage_of_portfolio
        self.fixed_amount = fixed_amount

    def get_size(self, portfolio, asset_price) -> float:
        """
        Calculate size in currency/units.
        """
        if self.fixed_amount is not None:
            return self.fixed_amount
        elif self.percentage_of_portfolio is not None:
            total_value = portfolio.get_unallocated() + portfolio.allocated
            return total_value * (self.percentage_of_portfolio / 100)
        else:
            raise OperationalException(
                "A position size object must have either a fixed amount or a "
                "percentage of the portfolio defined."
            )

    def __repr__(self) -> str:
        return (
            f"PositionSize(symbol={self.symbol}, "
            f"percentage_of_portfolio={self.percentage_of_portfolio}, "
            f"fixed_amount={self.fixed_amount})"
        )
