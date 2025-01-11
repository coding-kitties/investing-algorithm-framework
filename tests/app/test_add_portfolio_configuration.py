# from investing_algorithm_framework import PortfolioConfiguration, \
#     MarketCredential
# from tests.resources import TestBase


# class Test(TestBase):
#     portfolio_configurations = [
#         PortfolioConfiguration(
#             market="BITVAVO",
#             trading_symbol="EUR"
#         )
#     ]
#     market_credentials = [
#         MarketCredential(
#             market="BITVAVO",
#             api_key="api_key",
#             secret_key="secret_key"
#         )
#     ]
#     external_balances = {
#         "EUR": 1000,
#     }

#     def test_add(self):
#         self.assertEqual(1, self.app.algorithm.portfolio_service.count())
#         self.assertEqual(1, self.app.algorithm.position_service.count())
#         self.assertEqual(1000, self.app.algorithm.get_unallocated())

#         # Make sure that the portfolio is initialized
#         portfolio = self.app.algorithm.get_portfolio()
#         self.assertTrue(portfolio.initialized)
