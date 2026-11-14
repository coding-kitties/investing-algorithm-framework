"""
Maximum Adverse Excursion (MAE) and Maximum Favorable Excursion (MFE)
measure, for each trade, how far price moved *against* and *in favor
of* the position before it closed — independent of where it actually
entered/exited. They are used to sanity-check stop-loss / take-profit
placement:

- A large average MAE relative to the stop-loss distance means trades
  are being stopped out on noise rather than a genuine reversal.
- A large average MFE relative to the take-profit distance (or the
  trade's realised gain) means profits are being left on the table by
  exiting too early.

| **MFE / MAE ratio** | **Interpretation**                                          |
| --------------------- | ------------------------------------------------------------ |
| **< 1.0**             | Adverse moves are typically larger than favorable ones        |
| **1.0 – 2.0**          | Roughly balanced excursions                                    |
| **> 2.0**             | Favorable moves are typically larger — room to raise targets  |

Both metrics rely on ``Trade.high_water_mark`` / ``Trade.low_water_mark``
(the highest/lowest price ever reported for the trade, tracked
regardless of direction). For a **long** trade the highest price is the
favorable extreme and the lowest price is the adverse extreme; for a
**short** trade it is the other way around:

    long:  MFE = high_water_mark - open_price   MAE = open_price - low_water_mark
    short: MFE = open_price - low_water_mark    MAE = high_water_mark - open_price

Trades that were never marked-to-market (no ``high_water_mark`` /
``low_water_mark`` recorded, e.g. opened and closed within the same
bar) are excluded since no excursion could be observed.
"""
from typing import List

from investing_algorithm_framework.domain import Trade


def get_trade_mae_mfe_statistics(trades: List[Trade]) -> dict:
    """
    Calculate aggregate Maximum Adverse/Favorable Excursion statistics
    across a list of trades.

    Args:
        trades (List[Trade]): List of Trade objects.

    Returns:
        dict: A dictionary with the following keys:
            - average_mae / average_mae_percentage
            - average_mfe / average_mfe_percentage
            - max_mae / max_mfe
            - mfe_mae_ratio
    """
    maes: List[float] = []
    mae_percentages: List[float] = []
    mfes: List[float] = []
    mfe_percentages: List[float] = []

    for trade in (trades or []):
        if trade.open_price is None or trade.open_price <= 0:
            continue
        if trade.high_water_mark is None or trade.low_water_mark is None:
            continue

        if trade.is_short:
            mfe = max(trade.open_price - trade.low_water_mark, 0.0)
            mae = max(trade.high_water_mark - trade.open_price, 0.0)
        else:
            mfe = max(trade.high_water_mark - trade.open_price, 0.0)
            mae = max(trade.open_price - trade.low_water_mark, 0.0)

        maes.append(mae)
        mae_percentages.append((mae / trade.open_price) * 100.0)
        mfes.append(mfe)
        mfe_percentages.append((mfe / trade.open_price) * 100.0)

    average_mae = sum(maes) / len(maes) if maes else 0.0
    average_mfe = sum(mfes) / len(mfes) if mfes else 0.0

    return {
        "average_mae": average_mae,
        "average_mae_percentage": (
            sum(mae_percentages) / len(mae_percentages)
            if mae_percentages else 0.0
        ),
        "average_mfe": average_mfe,
        "average_mfe_percentage": (
            sum(mfe_percentages) / len(mfe_percentages)
            if mfe_percentages else 0.0
        ),
        "max_mae": max(maes) if maes else 0.0,
        "max_mfe": max(mfes) if mfes else 0.0,
        "mfe_mae_ratio": (
            average_mfe / average_mae if average_mae > 0 else 0.0
        ),
    }
