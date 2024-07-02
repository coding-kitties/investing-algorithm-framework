from datetime import datetime
from random import randint
from typing import Dict

from investing_algorithm_framework import OrderStatus, Order
from investing_algorithm_framework.domain import MarketService


class MarketServiceStub(MarketService):
    _orders = []
    _ohlcv = []
    _symbols = [
        'BTC/EUR',
        'ETH/EUR',
        'ADA/EUR',
        'BNB/EUR',
        "KSM/EUR",
    ]
    _balances = {
        'EUR': 1000,
    }

    def __init__(self, market_credential_service):
        super().__init__(
            market_credential_service=market_credential_service,
        )
        self._market_credential_service = market_credential_service
        self._orders = []

    @property
    def orders(self):
        return self._orders

    @orders.setter
    def orders(self, value):
        self._orders = value

    @property
    def balances(self) -> Dict[str, float]:
        return self._balances

    @balances.setter
    def balances(self, value: Dict[str, float]):
        self._balances = value

    @property
    def symbols(self):
        return self._symbols

    @symbols.setter
    def symbols(self, value):
        self._symbols = value

    def initialize(self, portfolio_configuration):
        pass

    def pair_exists(self, target_symbol: str, trading_symbol: str, market):
        pass

    def get_order_book(self, symbol, market):
        pass

    def get_order_books(self, symbols, market):
        pass

    def get_orders(self, symbol, market, since: datetime = None):
        selection = []

        if self.orders is not None:
            for order in self.orders:

                if order.get_symbol().upper() == symbol.upper():
                    selection.append(order)
            return selection

    def cancel_order(self, order_id, market):
        pass

    def get_open_orders(
        self, market, target_symbol: str = None, trading_symbol: str = None
    ):
        pass

    def get_closed_orders(
        self, market, target_symbol: str = None, trading_symbol: str = None
    ):
        pass

    def get_prices(self, symbols):
        pass

    def get_ohlcv(
        self, symbol, time_frame, from_timestamp, market, to_timestamp=None
    ):
        pass

    def get_ohlcvs(
        self, symbols, time_frame, from_timestamp, market, to_timestamp=None
    ):
        pass

    def create_market_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        market
    ):
        return Order(
            external_id=randint(0, 1000),
            amount=amount,
            status=OrderStatus.OPEN,
            order_type="market",
            order_side="sell",
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
        )

    def create_limit_buy_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float,
        market
    ):
        return Order(
            external_id=randint(0, 1000),
            amount=amount,
            status=OrderStatus.OPEN,
            order_type="limit",
            order_side="buy",
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
            price=price
        )

    def create_limit_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float,
        market
    ):
        return Order(
            external_id=randint(0, 1000),
            amount=amount,
            status=OrderStatus.OPEN,
            order_type="limit",
            order_side="sell",
            target_symbol=target_symbol,
            trading_symbol=trading_symbol,
        )

    def get_balance(self, market) -> Dict[str, float]:
        return self._balances

    def get_order(self, order, market):
        symbol = f"{order.target_symbol.upper()}" \
                 f"/{order.trading_symbol.upper()}"
        order_data = {
            'info': {
                'orderId': 'e8f8a3f7-0930-4778-a102-5145ed7e7873',
                'market': 'DOT-EUR',
                'created': '1674386553394',
                'updated': '1674386553394',
                'status': 'closed',
                'order_side': 'buy',
                'orderType': order.order_type,
                'amountQuote': order.amount,
                'amountQuoteRemaining': '0',
                'onHold': '0',
                'onHoldCurrency': 'EUR',
                'filledAmount': order.amount,
                'filledAmountQuote': order.amount,
                'feePaid': '0.043416459265',
                'feeCurrency':
                'EUR',
                'fills': [
                    {
                        'id': '16d3b5b7-a460-472b-ab6d-964b890f7d03',
                        'timestamp': '1674386553405',
                        'amount': '2.99863309',
                        'price': '5.7915',
                        'taker': True,
                        'fee': '0.043416459265',
                        'feeCurrency': 'EUR',
                        'settled': True
                     }
                ],
                'selfTradePrevention': 'decrementAndCancel',
                'visible': False,
                'disableMarketProtection': False
            },
            'id': 'e8f8a3f7-0930-4778-a102-5145ed7e7873',
            'clientOrderId': None,
            'timestamp': 1674386553394,
            'datetime': '2023-01-22 11:22:33.394',
            'lastTradeTimestamp': 1674386553405,
            'symbol': f'{symbol}',
            'order_type': 'market',
            'timeInForce': 'IOC',
            'postOnly': None,
            'type': order.order_type,
            'side': order.order_side,
            'price': order.price if order.order_type == 'limit' else 10,
            'stopPrice': None,
            'triggerPrice': None,
            'amount': order.amount,
            'cost': order.price,
            'average': order.price,
            'filled': order.amount,
            'remaining': 0.0,
            'status': 'closed',
            'fee': {'cost': 0.043416459265, 'currency': 'EUR'},
            'trades': [
                {
                    'info': {
                        'id': '16d3b5b7-a460-472b-ab6d-964b890f7d03',
                        'timestamp': '1674386553405',
                        'amount': '2.99863309',
                        'price': '5.7915',
                        'taker': True,
                        'fee': '0.043416459265',
                        'feeCurrency': 'EUR',
                        'settled': True
                    },
                    'id': '16d3b5b7-a460-472b-ab6d-964b890f7d03',
                    'symbol': 'DOT/EUR', 'timestamp': 1674386553405,
                    'datetime': '2023-01-22T11:22:33.405Z', 'order': None,
                    'order_type': None, 'order_side': None,
                    'takerOrMaker': 'taker',
                    'price': 5.7915, 'amount': 2.99863309,
                    'cost': 17.366583540735,
                    'fee': {'cost': 0.043416459265, 'currency': 'EUR'},
                    'fees': [{'cost': 0.043416459265, 'currency': 'EUR'}]}
            ],
            'fees': [{'currency': 'EUR', 'cost': 0.043416459265}],
            'reduceOnly': None
        }
        return Order.from_ccxt_order(order_data)

    def get_tickers(self, symbols, market):
        data = {}

        for symbol in symbols:
            data[symbol] = {
                'symbol': symbol,
                'timestamp': 1682344906543,
                "bid": 25148.37,
                "ask": 25151.41,
                "last": 25148.99,
                "open": 25208.4,
                "close": 25148.99,
                "percentage": -0.236,
                "average": 25178.695,
                "baseVolume": 1002.04119,
                "quoteVolume": 25151537.655228
            }

        return data

    def get_ticker(self, symbol, market):
        return {
            'symbol': symbol,
            'timestamp': 1682344906543,
            "bid": 25148.37,
            "ask": 25151.41,
            "last": 25148.99,
            "open": 25208.4,
            "close": 25148.99,
            "percentage": -0.236,
            "average": 25178.695,
            "baseVolume": 1002.04119,
            "quoteVolume": 25151537.655228
        }

    def get_symbols(self, market):
        return self._symbols
