from unittest import TestCase

from investing_algorithm_framework.app.reporting.generate import (
    get_time_frame_from_file_name,
)


class TestGetTimeFrameFromFileName(TestCase):

    def test_missing_time_frame_raises_value_error(self):
        with self.assertRaisesRegex(
            ValueError,
            "File name does not contain a valid time frame.",
        ):
            get_time_frame_from_file_name("OHLCV_BTC_BITVAVO")

    def test_invalid_time_frame_error_includes_file_name(self):
        file_name = (
            "OHLCV_BTC_BITVAVO_invalid_2026-01-01_2026-01-02.csv"
        )

        with self.assertRaises(ValueError) as context:
            get_time_frame_from_file_name(file_name)

        self.assertIn(file_name, str(context.exception))
        self.assertIn("got 'invalid'", str(context.exception))
