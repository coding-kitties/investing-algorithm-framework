from investing_algorithm_framework.domain.models.base_model import BaseModel


class OrderFee(BaseModel):
    def __init__(self, currency, cost, rate):
        self.currency = currency
        self.cost = cost
        self.rate = rate

    def get_currency(self):
        return self.currency

    def set_currency(self, currency):
        self.currency = currency

    def get_cost(self):
        return self.cost

    def set_cost(self, cost):
        self.cost = cost

    def get_rate(self):
        return self.rate

    @staticmethod
    def from_ccxt_fee(ccxt_fee):
        return OrderFee(
            currency=ccxt_fee.get('currency'),
            cost=ccxt_fee.get('cost'),
            rate=ccxt_fee.get('rate'),
        )

    def to_dict(self):
        return {
            "currency": self.currency,
            "cost": self.cost,
            "rate": self.rate
        }

    def __repr__(self):
        return self.repr(
            currency=self.get_currency(),
            cost=self.get_cost(),
            rate=self.get_rate(),
        )
