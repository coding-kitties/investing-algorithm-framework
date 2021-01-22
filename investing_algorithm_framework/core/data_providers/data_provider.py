from typing import List
from abc import abstractmethod
from random import randint


from investing_algorithm_framework.core.strategies import Strategy
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.context import AlgorithmContext


class AbstractDataProvider:
    id = None
    registered_strategies: List[Strategy] = None

    def __init__(self, data_provider_id: str = None):
        super().__init__()

        if self.id is None:
            self.id = data_provider_id

        # If ID is none generate a new unique ID
        if self.id is None:
            self.id = randint(10000, 100000)

    def get_id(self) -> str:
        assert getattr(self, 'id', None) is not None, (
            "{} should either include a id attribute, or override the "
            "`get_id()`, method.".format(self.__class__.__name__)
        )

        return getattr(self, 'id')

    def extract_quote(self, data, algorithm_context: AlgorithmContext):
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

    def extract_tick(self, data, algorithm_context: AlgorithmContext):
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

    def extract_order_book(self, data, algorithm_context: AlgorithmContext):
        """
        Function to extract electronic list of buy and sell orders for a
        specific security or financial instrument organized by price level.

        An order book lists the number of shares being bid on or
        offered at each price point, or market depth

        Override this function when you want to provide order book
        data for specific securities.
        """

        raise OperationalException("Not implemented")

    def provide_data(self, algorithm_context: AlgorithmContext):
        data = self.get_data(algorithm_context)
        self.provide_tick(data, algorithm_context)
        self.provide_quote(data, algorithm_context)
        self.provide_order_book(data, algorithm_context)
        self.provide_raw_data(data, algorithm_context)

    @abstractmethod
    def get_data(self, algorithm_context: AlgorithmContext):
        pass

    def provide_order_book(self, data, algorithm_context: AlgorithmContext):
        extracted_data = None

        try:
            extracted_data = self.extract_order_book(data, algorithm_context)
        except Exception as e:

            if isinstance(e, NotImplementedError):
                return

        if extracted_data is not None:

            for strategy in self.registered_strategies:

                try:
                    strategy.on_order_book(
                        self.id, extracted_data, algorithm_context
                    )
 
                except Exception as e:
                    self.handle_strategy_error(e)

    def provide_quote(self, data, algorithm_context: AlgorithmContext):
        extracted_data = None

        try:
            extracted_data = self.extract_quote(data, algorithm_context)
        except Exception as e:

            if isinstance(e, NotImplementedError):
                return

        if extracted_data is not None:

            for strategy in self.registered_strategies:

                try:
                    strategy.on_quote(
                        self.id, extracted_data, algorithm_context
                    )
                except Exception as e:
                    self.handle_strategy_error(e)

    def provide_tick(self, data, algorithm_context: AlgorithmContext):
        extracted_data = None

        try:
            extracted_data = self.extract_tick(data, algorithm_context)
        except Exception as e:

            if isinstance(e, NotImplementedError):
                return

        if extracted_data is not None:

            for strategy in self.registered_strategies:

                try:
                    strategy.on_tick(
                        self.id, extracted_data, algorithm_context
                    )
                except Exception as e:
                    self.handle_strategy_error(e)

    def provide_raw_data(self, data, algorithm_context: AlgorithmContext):

        if data is not None and self.registered_strategies:

            for strategy in self.registered_strategies:

                try:
                    strategy.on_raw_data(
                        self.id, data, algorithm_context
                    )
                except Exception as e:
                    self.handle_strategy_error(e)

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

    @staticmethod
    def handle_strategy_error(exception: Exception) -> None:

        if isinstance(exception, OperationalException) \
                and exception.error_message == 'Not implemented':
            return

        # Raise the exception again
        raise exception
