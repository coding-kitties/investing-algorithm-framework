from abc import abstractmethod
from typing import List

from investing_algorithm_framework.core.models import OrderSide, \
    OrderStatus
from investing_algorithm_framework.core.models.position import Position
from investing_algorithm_framework.core.models.order import Order


class Portfolio:

    @abstractmethod
    def get_id(self):
        pass

    @abstractmethod
    def get_identifier(self):
        pass

    @abstractmethod
    def get_trading_symbol(self):
        pass

    @abstractmethod
    def get_positions(self, symbol: str = None) -> List[Position]:
        pass

    @abstractmethod
    def get_number_of_positions(self):
        pass

    @abstractmethod
    def get_orders(
        self,
        status: OrderStatus = None,
        side: OrderSide = None,
        target_symbol: str = None,
        trading_symbol: str = None,
        lazy: bool = False
    ) -> List[Order]:
        pass

    @abstractmethod
    def get_number_of_orders(self):
        pass

    def get_market(self) -> str:
        pass

    @staticmethod
    @abstractmethod
    def from_dict(data):
        pass

    @abstractmethod
    def to_dict(self):
        pass

    @abstractmethod
    def get_unallocated(self):
        pass

    @abstractmethod
    def get_allocated(self):
        pass

    @abstractmethod
    def get_realized(self):
        pass

    @abstractmethod
    def get_total_revenue(self):
        pass

    @abstractmethod
    def snapshot(
        self, withdrawel=0, deposit=0, commit=True, creation_datetime=None
    ):
        pass

    @abstractmethod
    def create_order(
        self,
        context,
        order_type,
        symbol,
        price=None,
        amount_trading_symbol=None,
        amount_target_symbol=None,
        order_side=OrderSide.BUY.value,
    ):
        pass

    def repr(self, **fields) -> str:
        """
        Helper for __repr__
        """

        field_strings = []
        at_least_one_attached_attribute = False

        for key, field in fields.items():
            field_strings.append(f'{key}={field!r}')
            at_least_one_attached_attribute = True

        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"

        return f"<{self.__class__.__name__} {id(self)}>"

    def to_string(self):
        return self.repr(
            id=self.get_id(),
            identifier=self.get_identifier(),
            trading_symbol=self.get_trading_symbol(),
            number_of_positions=self.get_number_of_positions(),
            number_of_orders=self.get_number_of_orders(),
            unallocated=f"{self.get_unallocated()} {self.get_trading_symbol()}",
            allocated=self.get_allocated(),
            realized=f"{self.get_realized()}",
            total_revenue=f"{self.get_total_revenue()}",
        )

    def __repr__(self):
        return self.to_string()
