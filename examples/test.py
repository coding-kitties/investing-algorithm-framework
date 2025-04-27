from investing_algorithm_framework import download


if __name__ == "__main__":
    data = download(
        symbol="BTC/USDT",
        market="binance",
        data_type="ohlcv",
        start_date="2023-01-01",
        end_date="2023-10-01",
        window_size=200,
        pandas=True,
        save=True,
        storage_dir="./data"
    )
    print(data)
