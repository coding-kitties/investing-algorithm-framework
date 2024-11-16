from unittest import TestCase
from datetime import datetime
import pandas as pd

from investing_algorithm_framework.domain.metrics.price_efficiency import \
    get_price_efficiency_ratio

class TestGetPriceEfficiencyRatio(TestCase):
    def test_get_price_efficiency_ratio(self):
        # Given
        data = {
            'DateTime': [
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
                datetime(2021, 1, 5)
            ],
            'Close': [100, 102, 90, 105, 110]  
        }
        df = pd.DataFrame(data)
        df.set_index('DateTime', inplace=True)

        # When
        result = get_price_efficiency_ratio(df)

        # Then
        self.assertEqual(result, 0.29411764705882354)

        # Given
        data = {
            'DateTime': [
                datetime(2021, 1, 1),
                datetime(2021, 1, 2),
                datetime(2021, 1, 3),
                datetime(2021, 1, 4),
                datetime(2021, 1, 5)
            ],
            'Close': [100, 102, 101, 105, 110]  
        }
        df = pd.DataFrame(data)
        df.set_index('DateTime', inplace=True)

        # When
        result = get_price_efficiency_ratio(df)

        # Then
        self.assertEqual(result, 0.8333333333333334)
