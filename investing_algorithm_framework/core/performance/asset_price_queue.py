from investing_algorithm_framework.core.models import TimeFrame

class AssetPricesQueue:
    """
    Asset prices queue for logical order of asset prices based on
    their date times. This data structure is useful to link
    asset prices to snapshots based on their date of creation.
    """

    def __init__(self, asset_prices_array, time_frame):
        self.asset_prices = []

        self.intervals = TimeFrame.from_value(time_frame).intervals

        for zipped_asset_prices in zip(*asset_prices_array):
            self.asset_prices.insert(0, zipped_asset_prices)

        self.size = len(self.intervals)
        self.front = self.size - 1

    def pop(self):

        if len(self.intervals) == 0:
            return None, []
        else:
            # Get the first item of the queue
            asset_prices = []

            if len(self.asset_prices) != 0:
                asset_prices = self.asset_prices.pop()

            interval = self.intervals.pop()

            self.size = len(self.intervals)
            self.front = self.size - 1

            return interval, asset_prices

    def peek(self):
        """
        Method to get the next snapshot in the queue without
        popping it from the stack.

        Returns None if the stack size is smaller than 1.
        """

        asset_prices = []

        if len(self.intervals) == 0:
            return None, None

        if len(self.asset_prices) >= 1:
            asset_prices = self.asset_prices[self.front]

        return self.intervals[self.front], asset_prices

    def empty(self):
        return len(self.intervals) == 0

