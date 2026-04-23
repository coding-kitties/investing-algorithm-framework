from abc import ABC, abstractmethod
from datetime import datetime


class FXRateProvider(ABC):
    """
    Abstract base class for foreign exchange rate providers.

    Implement this class to supply FX rates for multi-currency
    portfolio value calculations. The framework calls ``get_rate``
    whenever it needs to convert a value from one currency to another
    (e.g. when computing total portfolio value in the base currency).

    Example::

        class MyFXProvider(FXRateProvider):
            def get_rate(self, from_currency, to_currency, date=None):
                # Return the exchange rate from from_currency to to_currency
                # e.g. if from_currency="USD", to_currency="EUR" and the
                # rate is 0.92, then 1 USD = 0.92 EUR
                return 0.92

        app.add_fx_rate_provider(MyFXProvider())
    """

    @abstractmethod
    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        date: datetime = None
    ) -> float:
        """
        Return the exchange rate to convert 1 unit of
        ``from_currency`` into ``to_currency``.

        Args:
            from_currency: The source currency code (e.g. "USD").
            to_currency: The target currency code (e.g. "EUR").
            date: Optional date for historical rates. If None,
                use the latest available rate.

        Returns:
            float: The exchange rate such that
                ``amount_in_to = amount_in_from * rate``.
        """
        raise NotImplementedError

    def supports_pair(
        self, from_currency: str, to_currency: str
    ) -> bool:
        """
        Check whether this provider can supply a rate for the given
        currency pair. Override this to restrict which pairs are
        supported.

        By default returns True for all pairs.
        """
        return True


class StaticFXRateProvider(FXRateProvider):
    """
    A simple FX rate provider backed by a static dictionary of rates.

    Useful for testing or when rates are known ahead of time.

    Example::

        provider = StaticFXRateProvider({
            ("USD", "EUR"): 0.92,
            ("GBP", "EUR"): 1.17,
        })
        app.add_fx_rate_provider(provider)
    """

    def __init__(self, rates: dict = None):
        """
        Args:
            rates: Dictionary mapping ``(from_currency, to_currency)``
                tuples to float rates. Inverse rates are computed
                automatically.
        """
        self._rates = {}

        if rates:
            for (from_c, to_c), rate in rates.items():
                key = (from_c.upper(), to_c.upper())
                self._rates[key] = rate

    def add_rate(
        self, from_currency: str, to_currency: str, rate: float
    ) -> None:
        """Add or update a rate for a currency pair."""
        self._rates[(from_currency.upper(), to_currency.upper())] = rate

    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        date: datetime = None
    ) -> float:
        from_c = from_currency.upper()
        to_c = to_currency.upper()

        if from_c == to_c:
            return 1.0

        key = (from_c, to_c)

        if key in self._rates:
            return self._rates[key]

        # Try inverse
        inverse_key = (to_c, from_c)

        if inverse_key in self._rates:
            return 1.0 / self._rates[inverse_key]

        raise ValueError(
            f"No FX rate available for {from_c}/{to_c}. "
            f"Available pairs: {list(self._rates.keys())}"
        )

    def supports_pair(
        self, from_currency: str, to_currency: str
    ) -> bool:
        from_c = from_currency.upper()
        to_c = to_currency.upper()

        if from_c == to_c:
            return True

        return (
            (from_c, to_c) in self._rates
            or (to_c, from_c) in self._rates
        )
