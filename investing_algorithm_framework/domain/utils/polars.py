from pandas import to_datetime
from polars import DataFrame as PolarsDataFrame


def convert_polars_to_pandas(
    data: PolarsDataFrame,
    remove_duplicates=True,
    add_index=True,
    datetime_column_name="Datetime"
):
    """
    Function to convert polars dataframe to pandas dataframe.

    Args:
        data:Polars Dataframe - The original polars dataframe
        remove_duplicates: Boolean - If set to true, all duplicate
        dates will be removed from the dataframe
        add_index: Boolean - If set to true, an index will
            be added to the dataframe
        datetime_column_name: String - the column name that has the
            datetime object. By default this is set to column name Datetime
            This is only used if add_index is set to True

    Returns:
        DataFrame: Pandas DataFrame that has been converted
          from a Polars DataFrame
    """

    if not isinstance(data, PolarsDataFrame):
        raise ValueError("Data must be a Polars DataFrame")

    data = data.to_pandas().copy()

    if add_index:
        # Convert 'Datetime' column to datetime format if it's not already
        data[datetime_column_name] = to_datetime(data[datetime_column_name])

        # Set 'Datetime' column as the index
        data.set_index(datetime_column_name, inplace=True)

    if remove_duplicates:

        # Remove duplicate dates
        data = data[~data.index.duplicated(keep='first')]

    # Make sure that the datetime column is still in the dataframe
    if datetime_column_name not in data.columns:
        data[datetime_column_name] = data.index

    return data
