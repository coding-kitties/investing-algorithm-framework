# from investing_algorithm_framework.core.models import TimeFrame, \
#     SQLLitePortfolio
# from investing_algorithm_framework.core.performance import SnapShotQueue, \
#     SnapshotAssetPriceCollection
# from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
#
#
# class TestOrderModel(TestBase, TestOrderAndPositionsObjectsMixin):
#
#     def setUp(self) -> None:
#         super(TestOrderModel, self).setUp()
#         self.start_algorithm()
#
#     def tearDown(self) -> None:
#         super(TestOrderModel, self).tearDown()
#
#     def test(self):
#         portfolio = SQLLitePortfolio.query.first()
#
#         snapshots_asset_price_collection = SnapshotAssetPriceCollection(
#             portfolio,
#             TimeFrame.ONE_HOUR
#         )
#
#         snapshots = snapshots_asset_price_collection.snapshots
#         self.assertTrue(len(snapshots) > 0)
#
#         snapshot_queue = SnapShotQueue(snapshots)
#
#         self.assertTrue(snapshot_queue.size > 0)
#         self.assertFalse(snapshot_queue.empty())
#
#         while not snapshot_queue.empty():
#             current_snapshot = snapshot_queue.pop()
#             peek_snapshot = snapshot_queue.peek()
#
#             if peek_snapshot is not None:
#                 self.assertTrue(
#                     current_snapshot.created_at < peek_snapshot.created_at
#                 )
