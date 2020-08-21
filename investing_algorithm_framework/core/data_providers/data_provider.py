from typing import List
from abc import abstractmethod

from investing_algorithm_framework.core.strategies import Strategy
from investing_algorithm_framework.core.exceptions import OperationalException


class AbstractDataProvider:
    registered_strategies: List[Strategy] = None

    def extract_quote(self, data):
        """
        A quote is the last price at which a security or commodity traded,
        meaning the most recent price to which a buyer and seller agreed and
        at which some amount of the asset was transacted. The bid or ask
        quotes are the most current prices and quantities at which the shares
        can be bought or sold.

        Quotes are displayed as: sell price – buy price.

        For example, if 125.7 – 125.9 is the quote: 125.7 is the sell
        price and 125.9 is the buy price.
        """

        raise OperationalException("Not implemented")

    def extract_tick(self, data):
        """
        A tick is the minimum incremental amount at which you can trade a
        security. A tick represents the standard upon which the price of a
        security may fluctuate. The tick provides a specific price increment,
        reflected in the local currency associated with the market in which
        the security trades, by which the overall price of the security
        can change.

        Override this function when you want to provide tick data for
        specific securities.
        """

        raise OperationalException("Not implemented")

    def extract_order_book(self, data):
        """
        Function to extract electronic list of buy and sell orders for a
        specific security or financial instrument organized by price level.

        An order book lists the number of shares being bid on or
        offered at each price point, or market depth

        Override this function when you want to provide order book
        data for specific securities.
        """

        raise OperationalException("Not implemented")

    def provide_data(self):
        data = self.get_data()
        self.provide_tick(data)
        self.provide_quote(data)
        self.provide_order_book(data)
        self.provide_raw_data(data)

    @abstractmethod
    def get_data(self):
        pass

    def provide_order_book(self, data):
        extracted_data = None

        try:
            extracted_data = self.extract_order_book(data)
        except Exception as e:

            if isinstance(e, NotImplementedError):
                return

        if extracted_data is not None:

            for strategy in self.registered_strategies:
                strategy.on_order_book(extracted_data)

    def provide_quote(self, data):
        extracted_data = None

        try:
            extracted_data = self.extract_quote(data)
        except Exception as e:

            if isinstance(e, NotImplementedError):
                return

        if extracted_data is not None:

            for strategy in self.registered_strategies:
                strategy.on_quote(extracted_data)

    def provide_tick(self, data):
        extracted_data = None

        try:
            extracted_data = self.extract_tick(data)
        except Exception as e:

            if isinstance(e, NotImplementedError):
                return

        if extracted_data is not None:

            for strategy in self.registered_strategies:
                strategy.on_tick(extracted_data)

    def provide_raw_data(self, data):

        if data is not None:

            for strategy in self.registered_strategies:
                try:
                    strategy.on_raw_data(data)
                except Exception as e:

                    if isinstance(e, OperationalException):
                        pass

    @classmethod
    def register_strategies(cls, strategies: List[Strategy]) -> None:

        for strategy in strategies:
            assert isinstance(strategy, Strategy), (
                'Given strategy must be an instance of the Strategy class'
            )

        if cls.registered_strategies is None:
            cls.registered_strategies = []

        cls.registered_strategies += strategies

    @classmethod
    def register_strategy(cls, strategy: Strategy) -> None:
        assert isinstance(strategy, Strategy), (
            'Given strategy must be an instance of the Strategy class'
        )

        if cls.registered_strategies is None:
            cls.registered_strategies = []

        cls.registered_strategies.append(strategy)
