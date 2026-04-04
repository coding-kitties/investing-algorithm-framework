from unittest import TestCase

from investing_algorithm_framework.domain.models.time_frame import TimeFrame


class TestTimeFrameNewEnumValues(TestCase):
    """Test that the new enum members have the correct string values."""

    def test_twenty_minute_value(self):
        self.assertEqual(TimeFrame.TWENTY_MINUTE.value, "20m")

    def test_six_hour_value(self):
        self.assertEqual(TimeFrame.SIX_HOUR.value, "6h")

    def test_eight_hour_value(self):
        self.assertEqual(TimeFrame.EIGHT_HOUR.value, "8h")

    def test_three_day_value(self):
        self.assertEqual(TimeFrame.THREE_DAY.value, "3d")


class TestTimeFrameNewAmountOfMinutes(TestCase):
    """Test that amount_of_minutes returns correct values for new members."""

    def test_twenty_minute_minutes(self):
        self.assertEqual(TimeFrame.TWENTY_MINUTE.amount_of_minutes, 20)

    def test_six_hour_minutes(self):
        self.assertEqual(TimeFrame.SIX_HOUR.amount_of_minutes, 360)

    def test_eight_hour_minutes(self):
        self.assertEqual(TimeFrame.EIGHT_HOUR.amount_of_minutes, 480)

    def test_three_day_minutes(self):
        self.assertEqual(TimeFrame.THREE_DAY.amount_of_minutes, 4320)


class TestTimeFrameNewFromString(TestCase):
    """Test from_string parsing for new members, including case variants."""

    def test_twenty_minute_lowercase(self):
        self.assertEqual(TimeFrame.from_string("20m"), TimeFrame.TWENTY_MINUTE)

    def test_six_hour_lowercase(self):
        self.assertEqual(TimeFrame.from_string("6h"), TimeFrame.SIX_HOUR)

    def test_six_hour_uppercase(self):
        self.assertEqual(TimeFrame.from_string("6H"), TimeFrame.SIX_HOUR)

    def test_eight_hour_lowercase(self):
        self.assertEqual(TimeFrame.from_string("8h"), TimeFrame.EIGHT_HOUR)

    def test_eight_hour_uppercase(self):
        self.assertEqual(TimeFrame.from_string("8H"), TimeFrame.EIGHT_HOUR)

    def test_three_day_lowercase(self):
        self.assertEqual(TimeFrame.from_string("3d"), TimeFrame.THREE_DAY)

    def test_three_day_uppercase(self):
        self.assertEqual(TimeFrame.from_string("3D"), TimeFrame.THREE_DAY)


class TestTimeFrameNewFromValue(TestCase):
    """Test from_value parsing for new members."""

    def test_twenty_minute_from_value_string(self):
        self.assertEqual(
            TimeFrame.from_value("20m"), TimeFrame.TWENTY_MINUTE
        )

    def test_six_hour_from_value_string(self):
        self.assertEqual(TimeFrame.from_value("6h"), TimeFrame.SIX_HOUR)

    def test_eight_hour_from_value_string(self):
        self.assertEqual(TimeFrame.from_value("8h"), TimeFrame.EIGHT_HOUR)

    def test_three_day_from_value_string(self):
        self.assertEqual(TimeFrame.from_value("3d"), TimeFrame.THREE_DAY)

    def test_twenty_minute_from_value_enum(self):
        self.assertEqual(
            TimeFrame.from_value(TimeFrame.TWENTY_MINUTE),
            TimeFrame.TWENTY_MINUTE,
        )

    def test_six_hour_from_value_enum(self):
        self.assertEqual(
            TimeFrame.from_value(TimeFrame.SIX_HOUR), TimeFrame.SIX_HOUR
        )

    def test_eight_hour_from_value_enum(self):
        self.assertEqual(
            TimeFrame.from_value(TimeFrame.EIGHT_HOUR), TimeFrame.EIGHT_HOUR
        )

    def test_three_day_from_value_enum(self):
        self.assertEqual(
            TimeFrame.from_value(TimeFrame.THREE_DAY), TimeFrame.THREE_DAY
        )


class TestTimeFrameNewEquals(TestCase):
    """Test equals method for new members against string and enum values."""

    def test_twenty_minute_equals_string(self):
        self.assertTrue(TimeFrame.TWENTY_MINUTE.equals("20m"))

    def test_twenty_minute_equals_enum(self):
        self.assertTrue(TimeFrame.TWENTY_MINUTE.equals(TimeFrame.TWENTY_MINUTE))

    def test_twenty_minute_not_equals_other(self):
        self.assertFalse(TimeFrame.TWENTY_MINUTE.equals(TimeFrame.THIRTY_MINUTE))

    def test_six_hour_equals_string(self):
        self.assertTrue(TimeFrame.SIX_HOUR.equals("6h"))

    def test_six_hour_equals_enum(self):
        self.assertTrue(TimeFrame.SIX_HOUR.equals(TimeFrame.SIX_HOUR))

    def test_eight_hour_equals_string(self):
        self.assertTrue(TimeFrame.EIGHT_HOUR.equals("8h"))

    def test_eight_hour_equals_enum(self):
        self.assertTrue(TimeFrame.EIGHT_HOUR.equals(TimeFrame.EIGHT_HOUR))

    def test_three_day_equals_string(self):
        self.assertTrue(TimeFrame.THREE_DAY.equals("3d"))

    def test_three_day_equals_enum(self):
        self.assertTrue(TimeFrame.THREE_DAY.equals(TimeFrame.THREE_DAY))

    def test_three_day_not_equals_other(self):
        self.assertFalse(TimeFrame.THREE_DAY.equals(TimeFrame.ONE_DAY))


class TestTimeFrameNewOrdering(TestCase):
    """Test ordering of new members relative to their neighbors."""

    # TWENTY_MINUTE sits between FIFTEEN_MINUTE and THIRTY_MINUTE
    def test_fifteen_lt_twenty_minute(self):
        self.assertLess(TimeFrame.FIFTEEN_MINUTE, TimeFrame.TWENTY_MINUTE)

    def test_twenty_lt_thirty_minute(self):
        self.assertLess(TimeFrame.TWENTY_MINUTE, TimeFrame.THIRTY_MINUTE)

    # SIX_HOUR sits between FOUR_HOUR and EIGHT_HOUR
    def test_four_hour_lt_six_hour(self):
        self.assertLess(TimeFrame.FOUR_HOUR, TimeFrame.SIX_HOUR)

    def test_six_hour_lt_eight_hour(self):
        self.assertLess(TimeFrame.SIX_HOUR, TimeFrame.EIGHT_HOUR)

    # EIGHT_HOUR sits between SIX_HOUR and TWELVE_HOUR
    def test_eight_hour_lt_twelve_hour(self):
        self.assertLess(TimeFrame.EIGHT_HOUR, TimeFrame.TWELVE_HOUR)

    # THREE_DAY sits between ONE_DAY and ONE_WEEK
    def test_one_day_lt_three_day(self):
        self.assertLess(TimeFrame.ONE_DAY, TimeFrame.THREE_DAY)

    def test_three_day_lt_one_week(self):
        self.assertLess(TimeFrame.THREE_DAY, TimeFrame.ONE_WEEK)

    # Verify >= and <= also work
    def test_twenty_minute_le_thirty_minute(self):
        self.assertLessEqual(TimeFrame.TWENTY_MINUTE, TimeFrame.THIRTY_MINUTE)

    def test_eight_hour_ge_six_hour(self):
        self.assertGreaterEqual(TimeFrame.EIGHT_HOUR, TimeFrame.SIX_HOUR)
