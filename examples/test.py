import requests

if __name__ == "__main__":
    # # Endpoint for Treasury Yield Curve Rates API
    # url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates?filter=record_date:gte:2024-01-01"
    #
    # # Make a GET request to the API
    # response = requests.get(url)
    #
    # if response.status_code == 200:
    #     # Extract risk-free rate from API response (e.g., 10-year Treasury yield)
    #     treasury_yield_data = response.json()
    #     entries = treasury_yield_data["data"]
    #     for entry in entries:
    #         print(entry)
    #     print(entries[-1])
    #     print(entries[-1]["avg_interest_rate_amt"])
    #     # print(treasury_yield_data)
    #     # ten_year_yield = treasury_yield_data["data"][0]["value"]
    #     # risk_free_rate = ten_year_yield / 100  # Convert percentage to decimal
    #     # print("10-Year Treasury Yield (Risk-Free Rate):", risk_free_rate)
    # else:
    #     print("Failed to retrieve Treasury yield data. Status code:", response.status_code)

    from datetime import datetime, timedelta
    from investing_algorithm_framework import CCXTOHLCVMarketDataSource
    from pandas import to_datetime

    DATA_RECORDING_START_DATE = datetime(year=2024, month=1, day=1)
    DATETIME_FORMAT = "%Y-%m-%d-%H-%M"
    data_resources = ["BTC/EUR", "DOT/EUR", "ETH/EUR", "ADA/EUR"]
    data_symbols = {
        "BTC/EUR": {
            "intervals": ["15m", "2h", "1d"],
            "market": "bitvavo"
        },
        "DOT/EUR": {
            "intervals": ["15m", "2h", "1d"],
            "market": "bitvavo"
        },
        "ETH/EUR": {
            "intervals": ["15m", "2h", "1d"],
            "market": "bitvavo"
        },
        "ADA/EUR": {
            "intervals": ["15m", "2h", "1d"],
            "market": "bitvavo"
        }
    }

    # Loop over all data sources and their intervals and download
    # all data. After downloading each data source, write everything to
    # the fabric lakehous
    for symbol in data_symbols:
        config = data_symbols[symbol]

        for interval in config["intervals"]:
            data_source = CCXTOHLCVMarketDataSource(
                identifier="BTC-ohlcv",
                market=config["market"],
                symbol=symbol,
                timeframe=interval,
            )
            last_date = DATA_RECORDING_START_DATE

            data = data_source.get_data(start_date=last_date,
                                        end_date=datetime.utcnow())
            pandas_df = data.to_pandas()

            # if len(pandas_df) > 0:
            #     pandas_df['Datetime'] = to_datetime(pandas_df['Datetime'])
            #     start_date = pandas_df.head(1)["Datetime"].iloc[0].strftime(
            #         DATETIME_FORMAT)
            #     end_date = pandas_df.tail(1)["Datetime"].iloc[0].strftime(
            #         DATETIME_FORMAT)
            #     formatted_symbol = symbol.replace('/', '_')
            #     spark_df = spark.createDataFrame(pandas_df)
            #     spark_df.write.mode("overwrite").parquet(
            #         f'Files/market_data/{formatted_symbol}_{interval}_{start_date}_{end_date}.parquet')