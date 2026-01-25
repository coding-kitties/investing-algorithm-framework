import pandas as pd
import polars as pl
from typing import Union


def fill_missing_timeseries_data(
    data: Union[pd.DataFrame, pl.DataFrame, str],
    missing_dates: list = None,
    start_date=None,
    end_date=None,
    save_to_file: bool = False,
    file_path: str = None
) -> Union[pd.DataFrame, pl.DataFrame]:
    """
    Fill missing dates in time-series data using a hybrid approach:
    forward-fill by default, backward-fill only when missing dates
    are at the start of the data.

    This function handles missing rows (dates) in time-series data,
    not just missing values within existing rows. All columns are
    duplicated from the adjacent row.

    Args:
        data (pd.DataFrame | pl.DataFrame | str): Time-series data as a
            DataFrame or path to a CSV file. Index should be datetime.
        missing_dates (list, optional): List of datetime objects representing
            specific missing dates to fill. If None and start_date/end_date
            are provided, missing dates will be auto-detected.
        start_date (datetime, optional): Start date to check for missing dates.
        end_date (datetime, optional): End date to check for missing dates.
        save_to_file (bool): If True, save the result back to the CSV file.
        file_path (str, optional): Path to save/load the CSV file.

    Returns:
        pd.DataFrame | pl.DataFrame: DataFrame with missing dates filled.
    """
    is_polars = False

    # Load data if file path is provided
    if isinstance(data, str):
        file_path = data
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    elif isinstance(data, pl.DataFrame):
        is_polars = True
        # Convert polars to pandas for processing
        df = data.to_pandas()
        if 'Datetime' in df.columns:
            df = df.set_index('Datetime')
        df.index = pd.to_datetime(df.index)
    else:
        df = data.copy()

    # Store the index name
    index_name = df.index.name if df.index.name else 'Datetime'

    rows_to_add = []

    # Determine which dates need to be filled
    if missing_dates is not None and len(missing_dates) > 0:
        dates_to_fill = [d for d in missing_dates if d not in df.index]
    elif start_date is not None and end_date is not None:
        dates_to_fill = get_missing_timeseries_data_entries(
            df, start=start_date, end=end_date
        )
    else:
        dates_to_fill = []

    # Fill missing dates
    for missing_timestamp in dates_to_fill:
        # Find the index position where this timestamp should be inserted
        position = df[df.index < missing_timestamp].shape[0]

        # Edge case: missing timestamp is BEFORE all existing data
        if position == 0:
            # Use the FIRST row (backward fill)
            if len(df) > 0:
                next_row = df.iloc[0]
                new_row = next_row.to_dict()
            else:
                continue  # No data to fill from
        else:
            # Normal case: use previous row (forward fill)
            prev_row = df.iloc[position - 1]
            new_row = prev_row.to_dict()

        rows_to_add.append({index_name: missing_timestamp, **new_row})

    # Add new rows if any
    if rows_to_add:
        new_df = pd.DataFrame(rows_to_add).set_index(index_name)
        df = pd.concat([df, new_df]).sort_index()

    # Save to file if requested
    if save_to_file and file_path:
        df.to_csv(file_path)

    # Convert back to polars if input was polars
    if is_polars:
        df = df.reset_index()
        return pl.from_pandas(df)

    return df


def get_missing_timeseries_data_entries(
    data: Union[pd.DataFrame, pl.DataFrame, str],
    start=None,
    end=None,
    freq: str = None
):
    """
    Identify missing timestamps in a time series.

    Args:
        data (pd.DataFrame | pl.DataFrame | str): Time-series data as a
            DataFrame or path to a CSV file. Index should be datetime.
        start (datetime, optional): The start datetime for the expected range.
            If None, uses the first timestamp in the data.
        end (datetime, optional): The end datetime for the expected range.
            If None, uses the last timestamp in the data.
        freq (str, optional): Frequency string (e.g., 'D' for daily, 'H' for
            hourly). If None, will be inferred from the data.

    Returns:
        list: A list of missing timestamps within the specified range.
    """
    # Load data if file path is provided
    if isinstance(data, str):
        df = pd.read_csv(data, index_col=0, parse_dates=True)
    elif isinstance(data, pl.DataFrame):
        df = data.to_pandas()
        if 'Datetime' in df.columns:
            df = df.set_index('Datetime')
        df.index = pd.to_datetime(df.index)
    else:
        df = data

    # Get existing timestamps from the index
    existing_timestamps = pd.to_datetime(df.index)

    # Use data bounds if start/end not provided
    if start is None:
        start = existing_timestamps.min()
    if end is None:
        end = existing_timestamps.max()

    # Infer frequency if not provided
    if freq is None:
        freq = df.index.inferred_freq
        if freq is None and len(df) >= 2:
            diff = df.index[1] - df.index[0]
            freq = diff
        elif freq is None:
            freq = 'D'  # Default to daily

    expected_timestamps = pd.date_range(start=start, end=end, freq=freq)

    # Find missing by checking which expected timestamps are not in existing
    missing_mask = ~expected_timestamps.isin(existing_timestamps)
    missing_timestamps = expected_timestamps[missing_mask].tolist()
    return missing_timestamps