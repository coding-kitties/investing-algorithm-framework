from investing_algorithm_framework.core.models import PerformanceMetric, \
    TimeFrame
from investing_algorithm_framework.core.performance import \
    SnapshotAssetPriceCollection


class PerformanceService:

    @staticmethod
    def of_metric(portfolio, metric: PerformanceMetric, time_frame: TimeFrame):
        # Create SnapshotAssetPriceCollection object for iteration
        snapshot_asset_price_collection = SnapshotAssetPriceCollection(
            portfolio=portfolio,
            time_frame=time_frame,
        )

        if PerformanceMetric.OVERALL_PERFORMANCE.equals(metric):
            return PerformanceService().generate_overall_performance(
                snapshot_asset_price_collection
            )
        elif PerformanceMetric.DELTA.equals(metric):
            return PerformanceService().generate_delta(
                snapshot_asset_price_collection
            )

        raise NotImplementedError("Performance metric not supported")

    def generate_delta(self, snapshot_asset_price_collection):
        """
            Performance calculation with Time Weighted Return
            TWR = [(1 + HP_1) * (1 + HP_2) * ... * (1 + HP_n)] - 1

            Where
                TWR = Time weighted return
                n = Number of sub-periods
                HP = (Total Value - (Previous Total Value + Cash Flow))
                        / (Previous Total Value + Cash Flow)
                HP_n = Return for sub-period n
        """
        points = []
        previous_snapshot = None
        previous_asset_prices = None
        previous_point = 1.0
        delta = 1

        points.append(previous_point)

        for date, snapshot, asset_prices in snapshot_asset_price_collection:
            points.append(1 + self.get_hp(
                snapshot,
                previous_snapshot,
                asset_prices,
                previous_asset_prices
            ))

            previous_asset_prices = asset_prices
            previous_snapshot = snapshot

        for point in points:
            delta = delta * point

        return delta - 1

    def generate_overall_performance(self, snapshot_asset_price_collection):
        """
            Performance calculation with Time Weighted Return
            TWR = [(1 + HP_1) * (1 + HP_2) * ... * (1 + HP_n)] - 1

            Where
                TWR = Time weighted return
                n = Number of sub-periods
                HP = (Total Value - (Previous Total Value + Cash Flow))
                        / (Previous Total Value + Cash Flow)
                HP_n = Return for sub-period n
        """
        points = []
        previous_snapshot = None
        previous_asset_prices = None
        previous_point = 1.0

        for date, snapshot, asset_prices in snapshot_asset_price_collection:

            hp_value = 1 + self.get_hp(
                snapshot,
                previous_snapshot,
                asset_prices,
                previous_asset_prices
            )

            points.append(
                {
                    "datetime": date,
                    "value": (previous_point * hp_value) - 1
                }
            )

            previous_asset_prices = asset_prices
            previous_snapshot = snapshot
            previous_point = (previous_point * hp_value)

        return points

    def get_hp(
        self,
        snapshot,
        previous_snapshot,
        current_asset_prices,
        previous_asset_prices
    ):
        if snapshot is not None and previous_snapshot is not None:
            return (
                snapshot.get_total_value(current_asset_prices) -
                (previous_snapshot.get_total_value(previous_asset_prices)
                 + snapshot.cash_flow)) \
               / (previous_snapshot.get_total_value(previous_asset_prices)
                  + snapshot.cash_flow)

        return 0
