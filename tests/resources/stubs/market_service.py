from datetime import datetime
from random import randint

from investing_algorithm_framework import OrderStatus, Order
from investing_algorithm_framework.infrastructure.services import MarketService


class MarketServiceStub(MarketService):

    def initialize(self, portfolio_configuration):
        pass

    def pair_exists(self, target_symbol: str, trading_symbol: str):
        pass

    def get_order_book(self, symbol):
        pass

    def get_order_books(self, symbols):
        pass

    def get_orders(self, symbol, since: datetime = None):
        pass

    def cancel_order(self, order_id):
        pass

    def get_open_orders(self, target_symbol: str = None,
                        trading_symbol: str = None):
        pass

    def get_closed_orders(self, target_symbol: str = None,
                          trading_symbol: str = None):
        pass

    def get_prices(self, symbols):
        pass

    def get_ohlcv(self, symbol, time_frame, from_timestamp, to_timestamp=None):
        pass

    def get_ohlcvs(self, symbols, time_frame, from_timestamp,
                   to_timestamp=None):
        pass

    def __init__(self):
        self._get_market_data_called = False
        self._get_market_data_return_value = None

    def create_market_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
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
        price: float
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
        price: float
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

    def get_balance(self):
        return {
            'info': [
                {'symbol': 'USDT', 'available': '1000', 'inOrder': '0'},
                {'symbol': 'BTC', 'available': '0.0013795', 'inOrder': '0'},
                {'symbol': 'DOT', 'available': '16', 'inOrder': '0'},
                {'symbol': 'EUR', 'available': '1000', 'inOrder': '0'},
                {'symbol': 'KSM', 'available': '2.98923511', 'inOrder': '0'},
            ],
            'timestamp': None,
            'datetime': None,
            'BTC': {'free': 0.0013795, 'used': 0.0, 'total': 0.0013795},
            'DOT': {'free': 16.0, 'used': 0.0, 'total': 16.0},
            'EUR': {'free': 1000, 'used': 0.0, 'total': 500.22},
            'KSM': {'free': 2.98923511, 'used': 0.0, 'total': 2.98923511},
            'USDT': {'free': 1000, 'used': 0.0, 'total': 200},
            'free': {
                'BTC': 0.0013795,
                'DOT': 16.0, 'EUR': 500.22,
                'KSM': 2.98923511,
                'USDT': 1000
            },
            'used': {
                'BTC': 0.0,
                'DOT': 0.0,
                'EUR': 0.0,
                'KSM': 0.0,
                'USDT': 0.0
            },
            'total': {
                'BTC': 0.0013795,
                'DOT': 16.0,
                'EUR': 500.22,
                'KSM': 2.98923511,
                'USDT': 1000
            }
        }

    def get_order(self, order):
        symbol = f"{order.target_symbol.upper()}/{order.trading_symbol.upper()}"
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
            'datetime': '2023-01-22T11:22:33.394Z',
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
                    'order_type': None, 'order_side': None, 'takerOrMaker': 'taker',
                    'price': 5.7915, 'amount': 2.99863309,
                    'cost': 17.366583540735,
                    'fee': {'cost': 0.043416459265, 'currency': 'EUR'},
                    'fees': [{'cost': 0.043416459265, 'currency': 'EUR'}]}
            ],
            'fees': [{'currency': 'EUR', 'cost': 0.043416459265}],
            'reduceOnly': None
        }
        return Order.from_ccxt_order(order_data)

    def get_tickers(self, symbols):
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

    def get_ticker(self, symbol):
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
