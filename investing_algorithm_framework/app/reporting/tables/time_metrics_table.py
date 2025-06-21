import pandas as pd


def create_html_time_metrics_table(results, report):
    copy_results = results.copy()

    # Ensure all values are numeric before formatting
    def safe_format(value, format_str):
        if isinstance(value, (int, float)):
            return format_str.format(value)
        return value  # Return the original value if it's not numeric

    copy_results['Percentage Winning Months'] = safe_format(copy_results['Percentage Winning Months'], "{:.2f}")
    copy_results['Percentage Winning Years'] = safe_format(copy_results['Percentage Winning Years'], "{:.2f}")
    copy_results['Average Monthly Return'] = safe_format(copy_results['Average Monthly Return'], "{:.2f}")
    copy_results['Average Monthly Return (Losing Months)'] = safe_format(copy_results['Average Monthly Return (Losing Months)'], "{:.2f}%")
    copy_results['Average Monthly Return (Winning Months)'] = safe_format(copy_results['Average Monthly Return (Winning Months)'], "{:.2f}%")

    if isinstance(copy_results['Best Month'], tuple):
        copy_results['Best Month'] = f"{(copy_results['Best Month'][0] * 100):.2f}% {copy_results['Best Month'][1].strftime('%b %Y')}"
    if isinstance(copy_results['Worst Month'], tuple):
        copy_results['Worst Month'] = f"{(copy_results['Worst Month'][0] * 100):.2f}% {copy_results['Worst Month'][1].strftime('%b %Y')}"
    if isinstance(copy_results['Best Year'], tuple):
        copy_results['Best Year'] = f"{(copy_results['Best Year'][0] * 100):.2f}% {copy_results['Best Year'][1].strftime('%Y')}"
    if isinstance(copy_results['Worst Year'], tuple):
        copy_results['Worst Year'] = f"{(copy_results['Worst Year'][0] * 100):.2f}% {copy_results['Worst Year'][1].strftime('%Y')}"

    stats = {
        "Metric": [
            "% Winning Months",
            "% Winning Years",
            "AVG Mo Return",
            "AVG Mo Return (Losing Months)",
            "AVG Mo Return (Winning Months)",
            "Best Month",
            "Worst Month",
            "Best Year",
            "Worst Year",
        ],
        "Value": [
            copy_results['Percentage Winning Months'],
            copy_results['Percentage Winning Years'],
            copy_results['Average Monthly Return'],
            copy_results['Average Monthly Return (Losing Months)'],
            copy_results['Average Monthly Return (Winning Months)'],
            copy_results['Best Month'],
            copy_results['Worst Month'],
            copy_results['Best Year'],
            copy_results['Worst Year'],
        ]
    }

    df_stats = pd.DataFrame(stats)

    table_html = (
        df_stats.style
        .set_table_styles([
            {'selector': 'th', 'props': [('background-color', '#f2f2f2'), ('font-weight', 'bold')]},
            {'selector': 'td', 'props': [('font-size', '14px')]},
            {'selector': 'tr:nth-child(even)', 'props': [('background-color', '#fafafa')]}
        ])
        .hide(axis='index')
        .to_html()
    )
    return table_html
