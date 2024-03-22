import pathlib

from data_sources import bitvavo_btc_eur_ohlcv_2h, bitvavo_dot_eur_ohlcv_2h, \
    bitvavo_dot_eur_ticker, bitvavo_btc_eur_ticker
from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY

app = create_app(
    config={RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()}
)
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_dot_eur_ohlcv_2h)
app.add_market_data_source(bitvavo_btc_eur_ticker)
app.add_market_data_source(bitvavo_dot_eur_ticker)
