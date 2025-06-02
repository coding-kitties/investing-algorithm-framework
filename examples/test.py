#%%
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from investing_algorithm_framework import get_backtest_report, \
    get_cumulative_profit_factor_series, download, get_profit_factor, \
    get_sharpe_ratio



if __name__ == "__main__":
    report = get_backtest_report(directory="./resources/backtest_report")
    btceur_ohlcv = download(
        symbol="btc/eur",
        market="bitvavo",
        time_frame="1d",
        start_date=report.backtest_date_range.start_date,
        end_date=report.backtest_date_range.end_date,
        pandas=True,
        save=True,
        storage_path="./data"
    )

    # Example usage of get_backtest_report
    profit_factor_series = get_cumulative_profit_factor_series(
        backtest_report=report
    )

    profit_factor = get_profit_factor(
        backtest_report=report
    )
    print(f"Profit Factor: {profit_factor}")

    sharp_ratio = get_sharpe_ratio(backtest_report=report, frequency="weekly", risk_free_rate=0.025)
    print(f"Sharp Ratio: {sharp_ratio}")
    print(report.number_of_days)
    print(report.total_net_gain_percentage)

    # Simulated price data
    dates = pd.date_range(start="2016-01-01", periods=1000, freq='D')
    prices = pd.Series(np.random.lognormal(mean=0.0005, sigma=0.01, size=len(dates)), index=dates).cumprod()
    prices_btceur = btceur_ohlcv['Close']

    # # Ensure the index is a datetime index
    dates_btceur = btceur_ohlcv.index

    # Calculate log close for BTC/EUR
    log_close_btceur = np.log(btceur_ohlcv['Close'])


