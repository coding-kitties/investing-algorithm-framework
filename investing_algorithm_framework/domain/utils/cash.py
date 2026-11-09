"""Shared tolerance for quote-currency cash boundary checks."""

CASH_TOLERANCE_REL = 1e-9
CASH_TOLERANCE_ABS = 1e-8


def cash_tolerance(*values: float) -> float:
    """Absorb amount/price round trips and summed allocation roundoff."""
    return max(
        CASH_TOLERANCE_ABS,
        CASH_TOLERANCE_REL * max(abs(value) for value in values),
    )
