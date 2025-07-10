import pandas as pd
from investing_algorithm_framework.domain import BacktestDateRange, \
    OperationalException
from typing import List, Union


def select_backtest_date_ranges(
    df: pd.DataFrame, window: Union[str, int] = '365D'
) -> List[BacktestDateRange]:
    """
    Identifies the best upturn, worst downturn, and sideways periods
    for the given window duration. This allows you to quickly select
    interesting periods for backtesting.
    """
    df = df.copy()
    df = df.sort_index()

    if isinstance(window, int):
        window = pd.Timedelta(days=window)
    elif isinstance(window, str):
        window = pd.to_timedelta(window)
    else:
        raise OperationalException("window must be a string or integer")

    if len(df) < 2 or df.index[-1] - df.index[0] < window:
        raise OperationalException(
            "DataFrame must contain at least two rows and span "
            "the full window duration"
        )

    best_upturn = {
        "name": "UpTurn", "return": float('-inf'), "start": None, "end": None
    }
    worst_downturn = {
        "name": "DownTurn", "return": float('inf'), "start": None, "end": None
    }
    most_sideways = {
        "name": "SideWays",
        "volatility": float('inf'),
        "return": None,
        "start": None,
        "end": None
    }

    for i in range(len(df)):
        start_time = df.index[i]
        end_time = start_time + window
        window_df = df[(df.index >= start_time) & (df.index <= end_time)]

        if len(window_df) < 2 or (window_df.index[-1] - start_time) < window:
            continue

        start_price = window_df['Close'].iloc[0]
        end_price = window_df['Close'].iloc[-1]
        ret = (end_price / start_price) - 1  # relative return
        volatility = window_df['Close'].std()

        # Ensure datetime for BacktestDateRange
        start_time = pd.Timestamp(start_time).to_pydatetime()
        end_time = pd.Timestamp(window_df.index[-1]).to_pydatetime()

        if ret > best_upturn["return"]:
            best_upturn.update(
                {"return": ret, "start": start_time, "end": end_time}
            )

        if ret < worst_downturn["return"]:
            worst_downturn.update(
                {"return": ret, "start": start_time, "end": end_time}
            )

        if volatility < most_sideways["volatility"]:
            most_sideways.update({
                "return": ret,
                "volatility": volatility,
                "start": start_time,
                "end": end_time
            })

    return [
        BacktestDateRange(
            start_date=best_upturn['start'],
            end_date=best_upturn['end'],
            name=best_upturn['name']
        ),
        BacktestDateRange(
            start_date=worst_downturn['start'],
            end_date=worst_downturn['end'],
            name=worst_downturn['name']
        ),
        BacktestDateRange(
            start_date=most_sideways['start'],
            end_date=most_sideways['end'],
            name=most_sideways['name']
        )
    ]
