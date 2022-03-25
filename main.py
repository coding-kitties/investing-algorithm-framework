import os
from investing_algorithm_framework import App, AlgorithmContext

app = App(
    resource_directory=os.path.abspath(os.path.join(os.path.realpath(__file__), os.pardir)),
    config={
        "PORTFOLIOS": {
            "BINANCE_PORTFOLIO": {
                "API_KEY": "KT8ow8gCc0iGoDTyNNqOwC4MtzsEKHJUgHPA8odSPHlRrWYu05LTiYc2o7Ub32sF",
                "SECRET_KEY": "dgVJrBmKYhwl3NF7C7vhcvv1PwuA7Nrgb1DeKrWtC5KFjzAbUpuYOxt9sakTyEha",
                "TRADING_SYMBOL": "USDT",
                "MARKET": "binance"
            }
        }
    }
)


@app.algorithm.strategy(
    time_unit="SECOND",
    interval=5,
    market="BINANCE",
    target_symbol="BTC",
    trading_data_type="TICKER",
    trading_symbol="USDT"
)
def perform_strategy(context: AlgorithmContext, ticker, **kwargs):
    print(f"BTC/USDT ticker data from binance {ticker}")


if __name__ == "__main__":
    app.start()
