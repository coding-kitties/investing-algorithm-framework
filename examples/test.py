import requests

if __name__ == "__main__":
    # Endpoint for Treasury Yield Curve Rates API
    url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates?filter=record_date:gte:2024-01-01"

    # Make a GET request to the API
    response = requests.get(url)

    if response.status_code == 200:
        # Extract risk-free rate from API response (e.g., 10-year Treasury yield)
        treasury_yield_data = response.json()
        entries = treasury_yield_data["data"]
        for entry in entries:
            print(entry)
        print(entries[-1])
        print(entries[-1]["avg_interest_rate_amt"])
        # print(treasury_yield_data)
        # ten_year_yield = treasury_yield_data["data"][0]["value"]
        # risk_free_rate = ten_year_yield / 100  # Convert percentage to decimal
        # print("10-Year Treasury Yield (Risk-Free Rate):", risk_free_rate)
    else:
        print("Failed to retrieve Treasury yield data. Status code:", response.status_code)