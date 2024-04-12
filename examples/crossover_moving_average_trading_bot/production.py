from app import app
from investing_algorithm_framework import MarketCredential

# Configure your market credentials here
bitvavo_market_credential = MarketCredential(
    api_key="",
    secret_key="",
    market="BITVAVO"
)
app.add_market_credential(bitvavo_market_credential)

if __name__ == "__main__":
    app.run()
