import pandas as pd


def safe_format(value, format_str, default_value='N/A'):
    if value is None:
        return default_value

    if isinstance(value, (int, float)):
        return format_str.format(value)
    return value


def safe_format_percentage(value, format_str, default_value='N/A'):
    if value is None:
        return default_value

    if isinstance(value, (int, float)):
        return format_str.format(value * 100)

    return value


def safe_format_date(value, format_str, default_value='N/A'):
    if value is None:
        return default_value

    if isinstance(value, pd.Timestamp):
        return value.strftime(format_str)
    return value
