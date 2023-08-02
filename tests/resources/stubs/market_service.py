from investing_algorithm_framework.infrastructure.services import MarketService
from investing_algorithm_framework import OrderStatus, Order


class MarketServiceStub(MarketService):

    def __init__(self):
        self._get_market_data_called = False
        self._get_market_data_return_value = None

    def create_market_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
    ):
        pass

    def create_limit_buy_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float
    ):
        pass

    def create_limit_sell_order(
        self,
        target_symbol: str,
        trading_symbol: str,
        amount: float,
        price: float
    ):
        pass

    def get_balance(self):
        return {
            'info': [
                {'symbol': 'USDT', 'available': '1000', 'inOrder': '0'},
                {'symbol': 'BTC', 'available': '0.0013795', 'inOrder': '0'},
                {'symbol': 'DOT', 'available': '16', 'inOrder': '0'},
                {'symbol': 'EUR', 'available': '500.22', 'inOrder': '0'},
                {'symbol': 'KSM', 'available': '2.98923511', 'inOrder': '0'},
            ],
            'timestamp': None,
            'datetime': None,
            'BTC': {'free': 0.0013795, 'used': 0.0, 'total': 0.0013795},
            'DOT': {'free': 16.0, 'used': 0.0, 'total': 16.0},
            'EUR': {'free': 500.22, 'used': 0.0, 'total': 500.22},
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
                'side': 'buy',
                'orderType': order.type,
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
            'type': 'market',
            'timeInForce': 'IOC',
            'postOnly': None,
            'side': order.side,
            'price': order.price if order.type == 'limit' else 10,
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
                    'type': None, 'side': None, 'takerOrMaker': 'taker',
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
