import requests
from investing_algorithm_framework.domain import MarketDataSource, \
    BacktestMarketDataSource


class UsTreasuryYieldDataSource(MarketDataSource):
    """
    UsTreasuryYield is a subclass of MarketDataSource.
    It is used to get the US Treasury Yield data.
    """

    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        pass

    URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/" \
          "v2/accounting/od/avg_interest_rates?" \
          "filter=record_date:gte:2024-01-01"

    def get_data(
        self,
        time_stamp=None,
        from_time_stamp=None,
        to_time_stamp=None,
        **kwargs
    ):
        response = requests.get(self.URL)

        if response.status_code == 200:
            # Extract risk-free rate from API response
            # (e.g., 10-year Treasury yield)
            treasury_yield_data = response.json()
            entries = treasury_yield_data["data"]
            for entry in entries:
                print(entry)
            print(entries[-1])
            print(entries[-1]["avg_interest_rate_amt"])
            # print(treasury_yield_data)
            # ten_year_yield = treasury_yield_data["data"][0]["value"]
            # risk_free_rate = ten_year_yield / 100  # Convert
            # percentage to decimal
            # print("10-Year Treasury Yield (Risk-Free Rate):", risk_free_rate)
        else:
            print("Failed to retrieve Treasury yield data. Status code:",
                  response.status_code)

        def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
            pass
