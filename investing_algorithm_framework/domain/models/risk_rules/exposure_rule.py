class ExposureRule:
    """
    Caps the total percentage of portfolio value that may be
    invested (allocated across all open positions combined) at any
    one time.

    Unlike :class:`ScalingRule.max_position_percentage`, which caps a
    *single symbol's* position size, ``ExposureRule`` caps the
    *portfolio-wide* total across every symbol combined — e.g. "never
    have more than 80% of the portfolio invested, always keep at
    least 20% as a cash buffer."

    Set it once on a strategy (it is portfolio-wide, so — unlike
    ``position_sizes``/``scaling_rules`` — there is only ever one,
    not a per-symbol list) and :class:`ApplyRiskBudgetPhase` enforces
    it automatically alongside the existing available-cash check:
    cash-consuming intents (``OPEN_LONG``/``SCALE_IN``) are scaled
    down, or dropped if the cap is already reached, before being
    emitted as orders. Closing intents (``CLOSE_LONG``/
    ``CLOSE_SHORT``/``SCALE_OUT``) are never affected.

    Attributes:
        max_portfolio_percentage (float): Maximum percentage,
            in the range (0, 100], of total portfolio value that may
            be invested at once, across all positions combined.

    Example:
        >>> strategy.exposure_rule = ExposureRule(
        ...     max_portfolio_percentage=80
        ... )
    """

    def __init__(self, max_portfolio_percentage: float):
        if max_portfolio_percentage is None or not (
            0 < max_portfolio_percentage <= 100
        ):
            raise ValueError(
                "ExposureRule.max_portfolio_percentage must be a "
                f"number in the range (0, 100], got "
                f"{max_portfolio_percentage!r}"
            )
        self.max_portfolio_percentage = float(max_portfolio_percentage)

    def get_max_allocatable(self, portfolio_value: float) -> float:
        """The maximum quote-currency amount that may be allocated
        (invested) given the current total portfolio value."""
        return portfolio_value * (self.max_portfolio_percentage / 100)

    def __repr__(self):
        return (
            f"ExposureRule(max_portfolio_percentage="
            f"{self.max_portfolio_percentage})"
        )
