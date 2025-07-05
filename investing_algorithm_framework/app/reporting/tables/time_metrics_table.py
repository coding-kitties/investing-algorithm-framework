import pandas as pd

from .utils import safe_format, safe_format_percentage, safe_format_date


def create_html_time_metrics_table(results, report):
    copy_results = results.copy()
    start_date = report.backtest_date_range.start_date
    end_date = report.backtest_date_range.end_date
    # Format dates
    copy_results['Start Date'] = safe_format_date(start_date, "%Y-%m-%d %H:%M")
    copy_results['End Date'] = safe_format_date(end_date, "%Y-%m-%d %H:%M")
    copy_results['Percentage Winning Months'] = safe_format_percentage(copy_results['Percentage Winning Months'], "{:.2f}%")
    copy_results['Percentage Winning Years'] = safe_format_percentage(copy_results['Percentage Winning Years'], "{:.2f}%")
    copy_results['Average Monthly Return'] = safe_format_percentage(copy_results['Average Monthly Return'], "{:.2f}%")
    copy_results['Average Monthly Return (Losing Months)'] = safe_format_percentage(copy_results['Average Monthly Return (Losing Months)'], "{:.2f}%")
    copy_results['Average Monthly Return (Winning Months)'] = safe_format_percentage(copy_results['Average Monthly Return (Winning Months)'], "{:.2f}%")

    if isinstance(copy_results['Best Month'], tuple):
        percentage = copy_results['Best Month'][0]
        date = copy_results['Best Month'][1]
        copy_results['Best Month'] = f"{safe_format_percentage(
            percentage, '{:.2f}'
        )}% {safe_format_date(date, '%b %Y')}"

    if isinstance(copy_results['Worst Month'], tuple):
        percentage = copy_results['Worst Month'][0]
        date = copy_results['Worst Month'][1]
        copy_results['Worst Month'] = f"{safe_format_percentage(
            percentage, '{:.2f}'
        )}% {safe_format_date(date, '%b %Y')}"

    if isinstance(copy_results['Best Year'], tuple):
        percentage = copy_results['Best Year'][0]
        date = copy_results['Best Year'][1]
        copy_results['Best Year'] = f"{safe_format_percentage(
            percentage, '{:.2f}'
        )}% {safe_format_date(date, '%b %Y')}"
    if isinstance(copy_results['Worst Year'], tuple):
        percentage = copy_results['Worst Year'][0]
        date = copy_results['Worst Year'][1]
        copy_results['Worst Year'] = f"{safe_format_percentage(
            percentage, '{:.2f}'
        )}% {safe_format_date(date, '%b %Y')}"

    stats = {
        "Metric": [
            "Start Date",
            "End Date",
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
            copy_results['Start Date'],
            copy_results['End Date'],
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
