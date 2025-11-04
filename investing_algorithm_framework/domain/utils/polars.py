import pandas as pd
from polars import DataFrame as PolarsDataFrame


def convert_polars_to_pandas(
    data: PolarsDataFrame,
    remove_duplicates=True,
    add_index=True,
    add_datetime_column=True,
    datetime_column_name="Datetime"
):
    """
    Function to convert polars dataframe to pandas dataframe.

    The function will set the index to the datetime column. The reason
    for this is that You can filter with clean, readable code in a faster way
    then with filtering on a column that is not the index.

    Args:
        data:Polars Dataframe - The original polars dataframe
        remove_duplicates: Boolean - If set to true, all duplicate
        dates will be removed from the dataframe
        add_index: Boolean - If set to true, an index will
            be added to the dataframe
        add_datetime_column: Boolean - If set to true, a datetime
            column will be added to the dataframe
        datetime_column_name: String - the column name that has the
            datetime object. By default this is set to column name Datetime
            This is only used if add_index is set to True

    Returns:
        DataFrame: Pandas DataFrame that has been converted
          from a Polars DataFrame
    """

    if not isinstance(data, PolarsDataFrame):
        raise ValueError("Data must be a Polars DataFrame")

    df = data.to_pandas().copy()

    if add_datetime_column and datetime_column_name not in df.columns:
        df[datetime_column_name] = pd.to_datetime(df.index)

    # Ensure datetime column is datetime type
    df[datetime_column_name] = pd.to_datetime(df[datetime_column_name])

    if remove_duplicates:
        df = df.drop_duplicates(subset=datetime_column_name, keep="first")

    if add_index:
        df.set_index(datetime_column_name, inplace=True)

    return df
