from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    MarketCredential

# No resource directory specified, so an in-memory database will be used
app = create_app()
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="<your_market>",
        trading_symbol="<your_trading_symbol>"
    )
)
app.add_market_credential(
    MarketCredential(
        api_key="<your_api_key>",
        market="<your_market>",
        secret_key="<your_secret_key>"
    )
)

if __name__ == "__main__":
    app.run()
