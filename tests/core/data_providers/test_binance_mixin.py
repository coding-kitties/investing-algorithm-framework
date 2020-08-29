import pytest
from investing_algorithm_framework.core.data_providers.mixins \
    import BinanceDataProviderMixin
from investing_algorithm_framework.core.exceptions import OperationalException


def test_get_price() -> None:
    provider = BinanceDataProviderMixin()
    price = provider.get_price('BTCEUR')
    assert price is not None

    with pytest.raises(OperationalException) as exc_info:
        provider.get_price('')

    assert str(exc_info.value) == 'No symbol provided'


def test_get_prices() -> None:
    provider = BinanceDataProviderMixin()
    prices = provider.get_prices()
    assert prices is not None

    prices = provider.get_prices(['BTCEUR', 'EOSBTC'])
    assert prices is not None
    assert len(prices) == 2


def test_get_book_ticker() -> None:
    provider = BinanceDataProviderMixin()
    book_ticker = provider.get_book_ticker('BTCEUR')
    assert book_ticker is not None

    with pytest.raises(OperationalException) as exc_info:
        provider.get_book_ticker('')

    assert str(exc_info.value) == 'No symbol provided'


def test_get_book_tickers() -> None:
    provider = BinanceDataProviderMixin()
    book_tickers = provider.get_book_tickers()
    assert book_tickers is not None

    book_tickers = provider.get_book_tickers(['BTCEUR', 'EOSBTC'])
    assert book_tickers is not None
    assert len(book_tickers) == 2
    print(book_tickers)
