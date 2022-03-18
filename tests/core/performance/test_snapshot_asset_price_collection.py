# from datetime import timedelta, datetime
#
# from investing_algorithm_framework.core.models import Portfolio, TimeFrame, \
#     TimeInterval, PortfolioSnapshot, OrderSide, db, SQLLitePortfolio, \
#     SQLLitePortfolioSnapshot
# from investing_algorithm_framework.core.performance import \
#     SnapshotAssetPriceCollection
# from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
#
#
# class TestClass(TestBase, TestOrderAndPositionsObjectsMixin):
#
#     def setUp(self) -> None:
#         super(TestClass, self).setUp()
#         self.start_algorithm()
#
#     def test_unique_symbols(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_HOUR
#         )
#
#         self.assertEqual(
#             1, len(asset_price_collection._retrieve_unique_symbols())
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_HOUR
#         )
#
#         self.assertEqual(
#             2, len(asset_price_collection._retrieve_unique_symbols())
#         )
#
#     def test_asset_prices_collection_one_minute(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_HOUR
#         )
#
#         self.assertEqual(3, len(asset_price_collection.asset_prices))
#
#         for asset_prices_entry in asset_price_collection.asset_prices:
#             self.assertEqual(
#                 TimeInterval.MINUTES_ONE.amount_of_data_points(),
#                 len(asset_prices_entry)
#             )
#
#     def test_asset_prices_collection_fifteen_minute(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_DAY
#         )
#
#         self.assertEqual(3, len(asset_price_collection.asset_prices))
#
#         for asset_prices_entry in asset_price_collection.asset_prices:
#             self.assertEqual(
#                 TimeInterval.MINUTES_FIFTEEN.amount_of_data_points(),
#                 len(asset_prices_entry)
#             )
#
#     def test_asset_prices_collection_one_hour(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_WEEK
#         )
#
#         self.assertEqual(3, len(asset_price_collection.asset_prices))
#
#         for asset_price_entry in asset_price_collection.asset_prices:
#             self.assertEqual(
#                 TimeInterval.HOURS_ONE.amount_of_data_points(),
#                 len(asset_price_entry)
#             )
#
#     def test_asset_prices_collection_four_hour(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_MONTH
#         )
#
#         self.assertEqual(3, len(asset_price_collection.asset_prices))
#
#         for asset_price_entry in asset_price_collection.asset_prices:
#             self.assertEqual(
#                 TimeInterval.HOURS_FOUR.amount_of_data_points(),
#                 len(asset_price_entry)
#             )
#
#     def test_asset_prices_collection_days(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow(),
#             side=OrderSide.BUY.value,
#             execution_datetime=None,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_YEAR
#         )
#
#         self.assertEqual(3, len(asset_price_collection.asset_prices))
#
#         for asset_prices_entry in asset_price_collection.asset_prices:
#             self.assertEqual(
#                 TimeInterval.DAYS_ONE.amount_of_data_points(),
#                 len(asset_prices_entry)
#             )
#
#     def test_iteration_operation_with_pre_range_snapshot(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.assertEqual(1, SQLLitePortfolioSnapshot.query.count())
#
#         first_snapshot = SQLLitePortfolioSnapshot.query.filter_by(
#             portfolio_id=portfolio.id
#         ).first()
#
#         # Snapshot before range
#         first_snapshot.created_at = datetime.utcnow() - timedelta(minutes=70)
#         db.session.commit()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow() - timedelta(minutes=50),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow() - timedelta(minutes=40),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow() - timedelta(minutes=30),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_HOUR
#         )
#
#         self.assertEqual(7, SQLLitePortfolioSnapshot.query.count())
#         self.assertEqual(7, len(asset_price_collection.snapshots))
#
#         index = 0
#
#         for interval_date, snapshot, asset_prices in asset_price_collection:
#
#             if index == 0:
#                 self.assertIsNotNone(snapshot)
#                 self.assertTrue(snapshot.created_at <= interval_date)
#
#             index += 1
#             # 3 prices per entry
#             self.assertEqual(3, len(asset_prices))
#             self.assertIsNotNone(interval_date)
#
#             peek_date, _ = asset_price_collection.asset_prices_queue.peek()
#             peek_snapshot = asset_price_collection.snapshot_queue.peek()
#
#             if peek_date is not None:
#                 self.assertTrue(interval_date < peek_date)
#
#             if snapshot is not None and peek_snapshot is not None:
#                 self.assertTrue(snapshot.created_at < peek_snapshot.created_at)
#
#     def test_iterate_operation_one_hour(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.assertEqual(
#             1,
#             SQLLitePortfolioSnapshot.query.filter_by(portfolio_id=portfolio.id).count()
#         )
#
#         first_snapshot = SQLLitePortfolioSnapshot.query.filter_by(
#             portfolio_id=portfolio.id
#         ).first()
#
#         first_snapshot.created_at = datetime.utcnow() - timedelta(minutes=100)
#         db.session.commit()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow() - timedelta(minutes=50),
#             side=OrderSide.BUY.value,
#             execution_datetime=datetime.utcnow() - timedelta(minutes=49),
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow() - timedelta(minutes=40),
#             side=OrderSide.BUY.value,
#             execution_datetime=datetime.utcnow() - timedelta(minutes=39),
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow() - timedelta(minutes=30),
#             side=OrderSide.BUY.value,
#             execution_datetime=datetime.utcnow() - timedelta(minutes=29),
#             executed=True,
#         )
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_HOUR
#         )
#
#         self.assertEqual(7, len(asset_price_collection.snapshots))
#
#         total_amount_of_snapshots_visited = 0
#         first_snapshot_passed = False
#         current_snapshot = None
#
#         for interval_date, snapshot, asset_prices in asset_price_collection:
#
#             # 3 prices per entry
#             self.assertEqual(3, len(asset_prices))
#             self.assertIsNotNone(interval_date)
#
#             peek_date, _ = asset_price_collection.asset_prices_queue.peek()
#             peek_snapshot = asset_price_collection.snapshot_queue.peek()
#
#             if peek_date is not None:
#                 self.assertTrue(interval_date < peek_date)
#
#             if snapshot is not None:
#
#                 if not first_snapshot_passed:
#                     total_amount_of_snapshots_visited += 1
#                     current_snapshot = snapshot
#                     first_snapshot_passed = True
#
#                 if current_snapshot is not None:
#                     if current_snapshot != snapshot:
#                         total_amount_of_snapshots_visited += 1
#                         current_snapshot = snapshot
#
#                 if peek_snapshot is not None:
#                     self.assertTrue(
#                         snapshot.created_at < peek_snapshot.created_at
#                     )
#
#         # 7 snapshots should be visited, including the snapshot created at
#         # the start
#         self.assertEqual(7, total_amount_of_snapshots_visited)
#
#     def test_iterate_operation_one_day(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.assertEqual(
#             1,
#             SQLLitePortfolioSnapshot.query.filter_by(
#                 portfolio_id=portfolio.id).count()
#         )
#
#         first_snapshot = SQLLitePortfolioSnapshot.query.filter_by(
#             portfolio_id=portfolio.id
#         ).first()
#
#         first_snapshot.created_at = datetime.utcnow() - timedelta(hours=40)
#         db.session.commit()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow() - timedelta(hours=20),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow() - timedelta(hours=18),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow() - timedelta(hours=15),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_DAY
#         )
#
#         self.assertEqual(7, len(asset_price_collection.snapshots))
#
#         total_amount_of_snapshots_visited = 0
#         first_snapshot_passed = False
#         current_snapshot = None
#
#         for interval_date, snapshot, asset_prices in asset_price_collection:
#
#             # 3 prices per entry
#             self.assertEqual(3, len(asset_prices))
#             self.assertIsNotNone(interval_date)
#
#             peek_date, _ = asset_price_collection.asset_prices_queue.peek()
#             peek_snapshot = asset_price_collection.snapshot_queue.peek()
#
#             if peek_date is not None:
#                 self.assertTrue(interval_date < peek_date)
#
#             if snapshot is not None:
#
#                 if not first_snapshot_passed:
#                     total_amount_of_snapshots_visited += 1
#
#                     self.assertEqual(
#                         snapshot.created_at, first_snapshot.created_at
#                     )
#                     current_snapshot = snapshot
#                     first_snapshot_passed = True
#
#                 if current_snapshot is not None:
#                     if current_snapshot.created_at != snapshot.created_at:
#                         total_amount_of_snapshots_visited += 1
#                         current_snapshot = snapshot
#
#                 if peek_snapshot is not None:
#                     self.assertTrue(
#                         snapshot.created_at < peek_snapshot.created_at
#                     )
#
#         # 7 snapshots should be visited, including the snapshot created at
#         # the start
#         self.assertEqual(7, total_amount_of_snapshots_visited)
#
#     def test_iterate_operation_one_week(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.assertEqual(
#             1,
#             SQLLitePortfolioSnapshot.query.filter_by(
#                 portfolio_id=portfolio.id).count()
#         )
#
#         first_snapshot = SQLLitePortfolioSnapshot.query.filter_by(
#             portfolio_id=portfolio.id
#         ).first()
#
#         first_snapshot.created_at = datetime.utcnow() - timedelta(days=10)
#         db.session.commit()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow() - timedelta(days=6),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow() - timedelta(days=5),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow() - timedelta(days=4),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_WEEK
#         )
#
#         self.assertEqual(7, len(asset_price_collection.snapshots))
#
#         total_amount_of_snapshots_visited = 0
#         first_snapshot_passed = False
#         current_snapshot = None
#
#         for interval_date, snapshot, asset_prices in asset_price_collection:
#
#             # 3 prices per entry
#             self.assertEqual(3, len(asset_prices))
#             self.assertIsNotNone(interval_date)
#
#             peek_date, _ = asset_price_collection.asset_prices_queue.peek()
#             peek_snapshot = asset_price_collection.snapshot_queue.peek()
#
#             if peek_date is not None:
#                 self.assertTrue(interval_date < peek_date)
#
#             if snapshot is not None:
#
#                 if not first_snapshot_passed:
#                     total_amount_of_snapshots_visited += 1
#
#                     self.assertEqual(
#                         snapshot.created_at, first_snapshot.created_at
#                     )
#                     current_snapshot = snapshot
#                     first_snapshot_passed = True
#
#                 if current_snapshot is not None:
#                     if current_snapshot.created_at != snapshot.created_at:
#                         total_amount_of_snapshots_visited += 1
#                         current_snapshot = snapshot
#
#                 if peek_snapshot is not None:
#                     self.assertTrue(
#                         snapshot.created_at < peek_snapshot.created_at
#                     )
#
#         # 7 snapshots should be visited, including the snapshot created at
#         # the start
#         self.assertEqual(7, total_amount_of_snapshots_visited)
#
#     def test_iterate_operation_one_month(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.assertEqual(
#             1,
#             SQLLitePortfolioSnapshot.query.filter_by(
#                 portfolio_id=portfolio.id).count()
#         )
#
#         first_snapshot = SQLLitePortfolioSnapshot.query.filter_by(
#             portfolio_id=portfolio.id
#         ).first()
#
#         first_snapshot.created_at = datetime.utcnow() - timedelta(days=40)
#         db.session.commit()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow() - timedelta(days=20),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow() - timedelta(days=18),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow() - timedelta(days=15),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_MONTH
#         )
#
#         self.assertEqual(7, len(asset_price_collection.snapshots))
#
#         total_amount_of_snapshots_visited = 0
#         first_snapshot_passed = False
#         current_snapshot = None
#
#         for interval_date, snapshot, asset_prices in asset_price_collection:
#
#             # 3 prices per entry
#             self.assertEqual(3, len(asset_prices))
#             self.assertIsNotNone(interval_date)
#
#             peek_date, _ = asset_price_collection.asset_prices_queue.peek()
#             peek_snapshot = asset_price_collection.snapshot_queue.peek()
#
#             if peek_date is not None:
#                 self.assertTrue(interval_date < peek_date)
#
#             if snapshot is not None:
#
#                 if not first_snapshot_passed:
#                     total_amount_of_snapshots_visited += 1
#
#                     self.assertEqual(
#                         snapshot.created_at, first_snapshot.created_at
#                     )
#                     current_snapshot = snapshot
#                     first_snapshot_passed = True
#
#                 if current_snapshot is not None:
#                     if current_snapshot.created_at != snapshot.created_at:
#                         total_amount_of_snapshots_visited += 1
#                         current_snapshot = snapshot
#
#                 if peek_snapshot is not None:
#                     self.assertTrue(
#                         snapshot.created_at < peek_snapshot.created_at
#                     )
#
#         # 7 snapshots should be visited, including the snapshot created at
#         # the start
#         self.assertEqual(7, total_amount_of_snapshots_visited)
#
#     def test_iterate_operation_one_year(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.assertEqual(
#             1,
#             SQLLitePortfolioSnapshot.query.filter_by(
#                 portfolio_id=portfolio.id).count()
#         )
#
#         first_snapshot = SQLLitePortfolioSnapshot.query.filter_by(
#             portfolio_id=portfolio.id
#         ).first()
#
#         first_snapshot.created_at = datetime.utcnow() - timedelta(weeks=40)
#         db.session.commit()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow() - timedelta(weeks=20),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow() - timedelta(weeks=18),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow() - timedelta(weeks=15),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_YEAR
#         )
#
#         self.assertEqual(7, len(asset_price_collection.snapshots))
#
#         total_amount_of_snapshots_visited = 0
#         first_snapshot_passed = False
#         current_snapshot = None
#
#         for interval_date, snapshot, asset_prices in asset_price_collection:
#
#             # 3 prices per entry
#             self.assertEqual(3, len(asset_prices))
#             self.assertIsNotNone(interval_date)
#
#             peek_date, _ = asset_price_collection.asset_prices_queue.peek()
#             peek_snapshot = asset_price_collection.snapshot_queue.peek()
#
#             if peek_date is not None:
#                 self.assertTrue(interval_date < peek_date)
#
#             if snapshot is not None:
#
#                 if not first_snapshot_passed:
#                     total_amount_of_snapshots_visited += 1
#
#                     self.assertEqual(
#                         snapshot.created_at, first_snapshot.created_at
#                     )
#                     current_snapshot = snapshot
#                     first_snapshot_passed = True
#
#                 if current_snapshot is not None:
#                     if current_snapshot.created_at != snapshot.created_at:
#                         total_amount_of_snapshots_visited += 1
#                         current_snapshot = snapshot
#
#                 if peek_snapshot is not None:
#                     self.assertTrue(
#                         snapshot.created_at < peek_snapshot.created_at
#                     )
#
#         # 7 snapshots should be visited, including the snapshot created at
#         # the start
#         self.assertEqual(7, total_amount_of_snapshots_visited)
#
#     def test_iteration_operation_with_inner_snapshots(self):
#         amount_of_snapshots_visited = 0
#
#         portfolio = SQLLitePortfolio.query.first()
#
#         self.assertEqual(1, SQLLitePortfolioSnapshot.query.count())
#
#         first_snapshot = SQLLitePortfolioSnapshot.query.filter_by(
#             portfolio_id=portfolio.id
#         ).first()
#
#         # Snapshot before range
#         first_snapshot.created_at = datetime.utcnow() - timedelta(minutes=70)
#         db.session.commit()
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_A,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_A).price,
#             creation_datetime=datetime.utcnow() - timedelta(minutes=50),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_B,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_B).price,
#             creation_datetime=datetime.utcnow() - timedelta(minutes=49),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         self.create_limit_order(
#             portfolio,
#             self.TARGET_SYMBOL_C,
#             amount=1,
#             price=self.get_price(self.TARGET_SYMBOL_C).price,
#             creation_datetime=datetime.utcnow() - timedelta(minutes=48),
#             side=OrderSide.BUY.value,
#             executed=True,
#         )
#
#         asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio, TimeFrame.ONE_DAY
#         )
#
#         self.assertEqual(7, len(asset_price_collection.snapshots))
#
#         index = 0
#
#         old_snapshot = None
#
#         for interval_date, snapshot, asset_prices in asset_price_collection:
#
#             if old_snapshot != snapshot:
#                 amount_of_snapshots_visited += 1
#
#             index += 1
#             # 3 prices per entry
#             self.assertEqual(3, len(asset_prices))
#             self.assertIsNotNone(interval_date)
#
#             peek_date, _ = asset_price_collection.asset_prices_queue.peek()
#             peek_snapshot = asset_price_collection.snapshot_queue.peek()
#
#             if peek_date is not None:
#                 self.assertTrue(interval_date < peek_date)
#
#             if snapshot is not None and peek_snapshot is not None:
#                 self.assertTrue(snapshot.created_at < peek_snapshot.created_at)
#
#             old_snapshot = snapshot
