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

    # def get_tickers(self, symbols):
    #     return {'BTC/EUR': {'symbol': 'BTC/EUR', 'timestamp': 1682344906543,
    #                  'datetime': '2023-04-24T14:01:46.543Z', 'high': 25574.14,
    #                  'low': 24774.88, 'bid': 25148.37, 'bidVolume': 0.00551,
    #                  'ask': 25151.41, 'askVolume': 0.05492,
    #                  'vwap': 25100.30316741, 'open': 25208.4,
    #                  'close': 25148.99, 'last': 25148.99,
    #                  'previousClose': 25206.38, 'change': -59.41,
    #                  'percentage': -0.236, 'average': 25178.695,
    #                  'baseVolume': 1002.04119, 'quoteVolume': 25151537.655228,
    #                  'info': {'symbol': 'BTCEUR',
    #                           'priceChange': '-59.41000000',
    #                           'priceChangePercent': '-0.236',
    #                           'weightedAvgPrice': '25100.30316741',
    #                           'prevClosePrice': '25206.38000000',
    #                           'lastPrice': '25148.99000000',
    #                           'lastQty': '0.00551000',
    #                           'bidPrice': '25148.37000000',
    #                           'bidQty': '0.00551000',
    #                           'askPrice': '25151.41000000',
    #                           'askQty': '0.05492000',
    #                           'openPrice': '25208.40000000',
    #                           'highPrice': '25574.14000000',
    #                           'lowPrice': '24774.88000000',
    #                           'volume': '1002.04119000',
    #                           'quoteVolume': '25151537.65522800',
    #                           'openTime': '1682258506543',
    #                           'closeTime': '1682344906543',
    #                           'firstId': '120709746', 'lastId': '120776508',
    #                           'count': '66763'}},
    #      'ETH/EUR': {'symbol': 'ETH/EUR', 'timestamp': 1682344906550,
    #                  'datetime': '2023-04-24T14:01:46.550Z', 'high': 1725.63,
    #                  'low': 1671.11, 'bid': 1699.51, 'bidVolume': 0.4987,
    #                  'ask': 1699.59, 'askVolume': 0.8683,
    #                  'vwap': 1691.43939645, 'open': 1709.96, 'close': 1699.3,
    #                  'last': 1699.3, 'previousClose': 1709.72,
    #                  'change': -10.66, 'percentage': -0.623,
    #                  'average': 1704.63, 'baseVolume': 10304.8821,
    #                  'quoteVolume': 17430083.559682,
    #                  'info': {'symbol': 'ETHEUR',
    #                           'priceChange': '-10.66000000',
    #                           'priceChangePercent': '-0.623',
    #                           'weightedAvgPrice': '1691.43939645',
    #                           'prevClosePrice': '1709.72000000',
    #                           'lastPrice': '1699.30000000',
    #                           'lastQty': '0.36560000',
    #                           'bidPrice': '1699.51000000',
    #                           'bidQty': '0.49870000',
    #                           'askPrice': '1699.59000000',
    #                           'askQty': '0.86830000',
    #                           'openPrice': '1709.96000000',
    #                           'highPrice': '1725.63000000',
    #                           'lowPrice': '1671.11000000',
    #                           'volume': '10304.88210000',
    #                           'quoteVolume': '17430083.55968200',
    #                           'openTime': '1682258506550',
    #                           'closeTime': '1682344906550',
    #                           'firstId': '86201967', 'lastId': '86237119',
    #                           'count': '35153'}}}
