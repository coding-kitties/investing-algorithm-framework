"""Floating-point tolerance for asset-quantity boundary calculations."""

from math import isfinite, ulp

from investing_algorithm_framework.domain.exceptions import OperationalException


def amount_roundoff_tolerance(*amounts: float) -> float:
    """Allow accumulated arithmetic roundoff without an absolute unit floor."""
    if not amounts or not all(isfinite(amount) for amount in amounts):
        raise OperationalException("Asset quantities must contain finite numbers")
    return 16 * max(ulp(amount) for amount in amounts)
