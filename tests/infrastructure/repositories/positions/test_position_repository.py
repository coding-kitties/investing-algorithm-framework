# from unittest import TestCase
#
# from investing_algorithm_framework.infrastructure import \
#     PandasPositionRepository, PandasUnitOfWork
# from tests.resources import random_string
#
#
# class TestSQLPositionRepository(TestCase):
#
#     def setUp(self):
#         self.repository = PandasPositionRepository(PandasUnitOfWork())
#
#     def create_position(self, **kwargs):
#         default_data = {
#             "symbol": random_string(10),
#             "amount": 100,
#             "portfolio_id": None,  # Assuming portfolio_id is optional
#         }
#         default_data.update(kwargs)
#         return self.repository.create(default_data)
#
#     def test_filter_by_id(self):
#         position_one = self.create_position(id=1)
#         print(position_one)
#         self.create_position(id=2)
#         self.create_position(id=3)
#         result = self.repository.get_all({"id": position_one.id})
#         self.assertEqual(len(result), 1)
#
#     def test_filter_by_amount(self):
#         self.create_portfolio(identifier="test_portfolio_id", market="bitvavo")
#         self.create_portfolio(identifier="test_portfolio_id_two", market="binance")
#         self.create_portfolio(identifier="test_portfolio_id_three", market="bitvavo")
#         result = self.repository.get_all({"market": "binance"})
#         self.assertEqual(len(result), 1)
#         result = self.repository.get_all({"market": "bitvavo"})
#         self.assertEqual(len(result), 2)
#
#     def test_filter_by_symbol(self):
#         self.create_portfolio(identifier="test_portfolio_id")
#         self.create_portfolio(identifier="test_portfolio_id_two")
#         self.create_portfolio(identifier="test_portfolio_id_three")
#         result = self.repository.get_all({"identifier": "test_portfolio_id"})
#         self.assertEqual(len(result), 1)
#
#     def test_filter_by_portfolio(self):
#         # Assuming position data exists and is properly joined in the pandas layer
#         positions = self.app.container.position_service().get_all()
#         if positions:
#             position = positions[0]
#             result = self.repository.get_all({"position": position.id})
#             self.assertGreaterEqual(len(result), 1)
#             for p in result:
#                 self.assertIn("id", dir(p))  # Basic check that portfolio data is returned
#         else:
#             self.skipTest("No positions available to test filter_by_position")
#
#     def test_filter_by_amount_gt_query_param(self):
#         # Assuming position data exists and is properly joined in the pandas layer
#         positions = self.app.container.position_service().get_all()
#         if positions:
#             position = positions[0]
#             result = self.repository.get_all({"position": position.id})
#             self.assertGreaterEqual(len(result), 1)
#             for p in result:
#                 self.assertIn("id", dir(p))  # Basic check that portfolio data is returned
#         else:
#             self.skipTest("No positions available to test filter_by_position")
#
#     def test_filter_by_amount_gte_query_param(self):
#         # Assuming position data exists and is properly joined in the pandas layer
#         positions = self.app.container.position_service().get_all()
#         if positions:
#             position = positions[0]
#             result = self.repository.get_all({"position": position.id})
#             self.assertGreaterEqual(len(result), 1)
#             for p in result:
#                 self.assertIn("id", dir(p))  # Basic check that portfolio data is returned
#         else:
#             self.skipTest("No positions available to test filter_by_position")
#
#     def test_filter_by_amount_lt_query_param(self):
#         pass
#
#     def test_filter_by_amount_lte_query_param(self):
#         pass
#
#     def test_filter_by_order_id_query_param(self):
#         pass
