from typing import Dict, List, Any, Union


def create_markdown_table(data: List[Union[Dict[str, Any], Any]]):
    """
    Create a markdown table with evenly spaced columns for nice display
    in notebook output cells.

    Args:
        data (List[dict] or List[object]): List of dictionaries or objects
            containing data.

    Returns:
        str: Markdown formatted table with evenly spaced columns.
    """
    if not data or len(data) == 0:
        return ("| No Data Available |\n"
                "|-------------------|\n"
                "| No records found  |\n")

    # Determine if data contains dicts or objects
    is_dict = isinstance(data[0], dict)

    # Get columns from data
    if is_dict:
        columns = list(data[0].keys())
    else:
        # For objects, get all attributes (excluding private ones)
        columns = [
            attr for attr in dir(data[0])
            if not attr.startswith('_')
            and not callable(getattr(data[0], attr))
        ]

    # Generate header titles
    header_titles = [col.replace("_", " ").title() for col in columns]

    # Collect and format all row data
    all_rows_data = []
    for item in data:
        row_values = []
        for col in columns:
            # Get value
            if is_dict:
                value = item.get(col)
            else:
                value = getattr(item, col, None)

            # Format value
            if value is None:
                formatted_value = "N/A"
            elif isinstance(value, float):
                formatted_value = f"{value:.2f}"
            else:
                formatted_value = str(value)

            row_values.append(formatted_value)
        all_rows_data.append(row_values)

    # Calculate column widths based on both headers and data
    col_widths = []
    for i, header in enumerate(header_titles):
        max_width = len(header)
        for row in all_rows_data:
            if i < len(row):
                max_width = max(max_width, len(row[i]))
        col_widths.append(max_width)

    # Build markdown table
    markdown = ""

    # Header with padding
    header_parts = [
        title.ljust(width)
        for title, width in zip(header_titles, col_widths)
    ]
    markdown += "| " + " | ".join(header_parts) + " |\n"

    # Separator
    separator_parts = ["-" * width for width in col_widths]
    markdown += "| " + " | ".join(separator_parts) + " |\n"

    # Data rows
    for row_values in all_rows_data:
        row_parts = [
            value.ljust(width)
            for value, width in zip(row_values, col_widths)
        ]
        markdown += "| " + " | ".join(row_parts) + " |\n"

    return markdown
