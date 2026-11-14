"""Named native-timeframe frames and execution marks must stay separate."""
from unittest import TestCase
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from investing_algorithm_framework import (
    BacktestDateRange, CSVOHLCVDataProvider, DataSource,
)
from investing_algorithm_framework.services.data_providers \
    .data_provider_service import DataProviderService


class FrameProvider:
    priority = 0

    def __init__(self, source, frame):
        self.source = source
        self.time_frame = source.time_frame
        self.frame = frame

    def has_data(self, source, **kwargs):
        return source == self.source

    def copy(self, source):
        return self

    def get_backtest_data(self, **kwargs):
        return self.frame


class TestDataProviderSourceRegistration(TestCase):
    def test_equal_timeframe_reregistration_refreshes_execution_marks(self):
        source = DataSource(
            symbol="ASSET0/EUR", market="BITVAVO", data_type="ohlcv",
            time_frame="1h", pandas=True, identifier="asset0_price",
        )
        frames = [
            pd.DataFrame(
                {"Close": prices},
                index=pd.date_range(
                    date, periods=2, freq="h", tz="UTC",
                ),
            )
            for date, prices in (
                ("2025-01-01", [100., 101.]),
                ("2025-01-02", [200., 201.]),
            )
        ]
        for registration in ("register", "backtest", "explicit"):
            with self.subTest(registration=registration):
                service = DataProviderService()
                service.backtest_mode = True
                index = service.data_provider_index
                for frame in frames:
                    provider = FrameProvider(source, frame)
                    index.data_providers = [provider]
                    date_range = BacktestDateRange(
                        start_date=frame.index[0].to_pydatetime(),
                        end_date=frame.index[-1].to_pydatetime(),
                    )
                    if registration == "register":
                        index.register(source)
                    elif registration == "backtest":
                        index.register_backtest_data_source(source, date_range)
                    else:
                        index.register_data_source_and_backtest_data_provider(
                            source, provider,
                        )
                    data = service.get_vectorized_backtest_data(
                        [source], date_range.start_date, date_range.end_date,
                    )
                    self.assertIs(data["asset0_price"], frame)
                    for market in (None, "BITVAVO"):
                        self.assertIs(service.get_ohlcv_data(
                            symbol="ASSET0/EUR", market=market, pandas=True,
                        ), frame)
                    self.assertIs(service.get_ohlcv_data(
                        symbol="ASSET0/EUR", market="BITVAVO",
                        time_frame="1h", pandas=True,
                    ), frame)

    def test_csv_windows_prepare_the_provider_used_for_execution_marks(self):
        dates = pd.date_range(
            "2025-01-01", periods=10, freq="h", tz="UTC",
        )
        values = list(map(float, range(10)))
        frame = pd.DataFrame({
            "Datetime": dates.strftime("%Y-%m-%dT%H:%M:%S.%f%z"),
            "Open": values, "High": values, "Low": values,
            "Close": values, "Volume": [1.] * 10,
        })
        source = DataSource(
            symbol="ASSET0/EUR", market="BITVAVO", data_type="ohlcv",
            time_frame="1h", warmup_window=2, identifier="asset0_price",
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            frame.to_csv(path, index=False)
            provider = CSVOHLCVDataProvider(
                storage_path=str(path), symbol="ASSET0/EUR",
                market="BITVAVO", time_frame="1h", warmup_window=2,
            )
            service = DataProviderService(default_data_providers=[provider])
            service.backtest_mode = True
            for start, end in ((2, 4), (5, 7)):
                date_range = BacktestDateRange(
                    start_date=dates[start].to_pydatetime(),
                    end_date=dates[end].to_pydatetime(),
                )
                selected = (
                    service.data_provider_index.register_backtest_data_source(
                        source, date_range,
                    )
                )
                selected.prepare_backtest_data(
                    date_range.start_date, date_range.end_date,
                )
                for market in (None, "BITVAVO"):
                    actual = service.get_ohlcv_data(
                        symbol="ASSET0/EUR", market=market,
                        date=date_range.end_date, pandas=True,
                    )
                    self.assertEqual(actual["Close"].iloc[-1], values[end])

    def test_native_frames_and_finest_marks_in_all_registration_paths(self):
        sources = [
            DataSource(
                symbol="ASSET0/EUR", market="BITVAVO", data_type="ohlcv",
                time_frame=time_frame, pandas=True, identifier=identifier,
            )
            for time_frame, identifier in (
                ("1h", "asset0_price"), ("4h", "asset0_z_score"),
            )
        ]
        frames = [
            pd.DataFrame(
                {"Close": prices},
                index=pd.date_range(
                    "2025-01-01", periods=len(prices), freq=freq, tz="UTC",
                ),
            )
            for freq, prices in (
                ("h", [100., 99., 98., 97., 96.]),
                ("4h", [200., 190.]),
            )
        ]
        date_range = BacktestDateRange(
            start_date=frames[0].index[0].to_pydatetime(),
            end_date=frames[0].index[-1].to_pydatetime(),
        )
        for registration in ("register", "backtest", "explicit"):
            for order in ((0, 1), (1, 0)):
                with self.subTest(registration=registration, order=order):
                    providers = [
                        FrameProvider(source, frame)
                        for source, frame in zip(sources, frames)
                    ]
                    service = DataProviderService(
                        default_data_providers=providers,
                    )
                    service.backtest_mode = True
                    index = service.data_provider_index
                    register_explicit = (
                        index.register_data_source_and_backtest_data_provider
                    )
                    for number in order:
                        source = sources[number]
                        if registration == "register":
                            index.register(source)
                        elif registration == "backtest":
                            index.register_backtest_data_source(
                                source, date_range,
                            )
                        else:
                            register_explicit(
                                source, providers[number],
                            )
                    data = service.get_vectorized_backtest_data(
                        sources, date_range.start_date, date_range.end_date,
                    )
                    self.assertEqual(
                        set(data), {"asset0_price", "asset0_z_score"},
                    )
                    self.assertIs(data["asset0_price"], frames[0])
                    self.assertIs(data["asset0_z_score"], frames[1])
                    for market in (None, "BITVAVO"):
                        self.assertIs(service.get_ohlcv_data(
                            symbol="ASSET0/EUR", market=market, pandas=True,
                        ), frames[0])
                    for number, timeframe in enumerate(("1h", "4h")):
                        self.assertIs(service.get_ohlcv_data(
                            symbol="ASSET0/EUR", market="BITVAVO",
                            time_frame=timeframe, pandas=True,
                        ), frames[number])
