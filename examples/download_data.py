from investing_algorithm_framework import download

if __name__ == "__main__":
    btceur_ohlcv = download(
        symbol="btc/eur",
        market="bitvavo",
        time_frame="1d",
        start_date="2023-01-01",
        end_date="2023-12-31",
        pandas=False,
        save=True,
        storage_path="./data"
    )
