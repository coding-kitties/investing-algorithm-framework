# from investing_algorithm_framework.configuration.constants import \
#     API_KEY, SECRET_KEY, CCXT_ENABLED, MARKET
# from tests.resources import TestBase, random_string
#
#
# class Test(TestBase):
#
#     def setUp(self):
#         super(Test, self).setUp()
#         self.algo_app.initialize(config={
#             API_KEY: random_string(10),
#             SECRET_KEY: random_string(10),
#             CCXT_ENABLED: True,
#             MARKET: "binance"
#         })
#         self.start_algorithm()
#
#     def test(self) -> None:
#         market_service = self.algo_app.algorithm
#         .get_market_service("binance")
#         self.assertIsNotNone(market_service.exchange_class)
