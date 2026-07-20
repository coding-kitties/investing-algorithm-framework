from datetime import timedelta
from typing import Optional

from investing_algorithm_framework.domain.backtesting.backtest_date_range \
    import BacktestDateRange


class BacktestWindow:
    """
    Represents a single backtest window, containing a training (in-sample)
    period and an optional testing (out-of-sample) period.

    test_range is optional: you can create a window for in-sample work
    first and attach the out-of-sample test_range later (e.g. via
    ``window.test_range = out_of_sample_range``).

    gap_days is derived from the difference between test_range.start_date
    and train_range.end_date when a test_range is present, keeping it
    always consistent with the ranges.

    Attributes:
        key (Optional[str]): A unique key for this window, e.g. "window_1". If None, a key will be generated based on the train_range and test_range.
        name (Optional[str]): An optional name for the window, e.g. "Window 1".
        train_range (BacktestDateRange): The full date range used for
            training, including any warmup period.
        test_range (Optional[BacktestDateRange]): The date range used for
            out-of-sample testing. None until assigned.
        warmup_days (int): Number of days at the start of train_range
            reserved for warming up indicators (e.g., a 26-day EMA needs
            26 warmup days). Not counted as effective training. Default is 0.
        fold_index (Optional[int]): Zero-based fold index when this window
            is part of a k-fold split. None for rolling windows.
    """

    def __init__(
        self,
        train_range: BacktestDateRange,
        test_range: Optional[BacktestDateRange] = None,
        warmup_days: int = 0,
        fold_index: Optional[int] = None,
        name: Optional[str] = None,
    ):
        if warmup_days < 0:
            raise ValueError("warmup_days must be >= 0")

        train_duration = (train_range.end_date - train_range.start_date).days

        if warmup_days > 0 and warmup_days >= train_duration:
            raise ValueError(
                f"warmup_days ({warmup_days}) must be less than the total "
                f"training duration ({train_duration} days)"
            )

        self._name = name
        self._train_range = train_range
        self._warmup_days = warmup_days
        self._fold_index = fold_index
        self.test_range = test_range  # goes through the setter

    def generate_key(self) -> str:
        """
        Generate a stable key based on the name, train_range, test_range,
        warmup_days, and fold_index.
        """
        key = f"name_{self._name}" if self._name is not None else "window"
        key = f"{self._train_range.start_date.isoformat()}_"
        key += f"{self._train_range.end_date.isoformat()}"
        key = (
            f"{self._test_range.start_date.isoformat()}_"
            f"{self._test_range.end_date.isoformat()}"
            if self._test_range is not None else "None"
        )
        key = f"warmup_{self._warmup_days}"
        key = f"fold_{self._fold_index}" if self._fold_index is not None else "fold_None"
        return f"{key}|{train_key}|{test_key}|{warmup_key}|{fold_key}"

    @property
    def test_range(self) -> Optional[BacktestDateRange]:
        return self._test_range

    @test_range.setter
    def test_range(self, value: Optional[BacktestDateRange]) -> None:
        if value is not None:
            if value.start_date < self._train_range.end_date:
                raise ValueError(
                    "test_range must start on or after train_range ends. "
                    f"(train_range.end_date={self._train_range.end_date}, "
                    f"test_range.start_date={value.start_date})"
                )
        self._test_range = value

    @classmethod
    def from_dict(cls, d: dict) -> "BacktestWindow":
        """
        Create a BacktestWindow from a dict as returned by
        generate_rolling_backtest_windows, e.g.:
            {
                "train_range": BacktestDateRange(...),
                "test_range": BacktestDateRange(...),  # optional
                "warmup_days": 0,
                "name": "Window 1",  # optional
            }
        """
        return cls(
            name=d.get("name"),
            train_range=d["train_range"],
            test_range=d.get("test_range"),
            warmup_days=d.get("warmup_days", 0),
            fold_index=d.get("fold_index"),
        )

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def train_range(self) -> BacktestDateRange:
        return self._train_range

    @property
    def gap_days(self) -> Optional[int]:
        """Days between the end of training and the start of testing.
        Derived from the ranges, so always consistent. None if no test_range."""
        if self._test_range is None:
            return None
        return (self._test_range.start_date - self._train_range.end_date).days

    @property
    def fold_index(self) -> Optional[int]:
        """Zero-based fold index for k-fold windows. None for rolling windows."""
        return self._fold_index

    @property
    def warmup_days(self) -> int:
        return self._warmup_days

    @property
    def effective_train_range(self) -> BacktestDateRange:
        """
        The training range with the warmup period stripped from the start.
        This is the period actually used for strategy evaluation during
        training, after indicators have had time to warm up.
        """
        effective_start = (
            self._train_range.start_date + timedelta(days=self._warmup_days)
        )
        return BacktestDateRange(
            start_date=effective_start,
            end_date=self._train_range.end_date,
            name=self._train_range.name,
        )

    def __repr__(self) -> str:
        return (
            f"BacktestWindow("
            f"name={self._name!r}, "
            f"train_range={self._train_range!r}, "
            f"test_range={self._test_range!r}, "
            f"gap_days={self.gap_days!r}, "
            f"warmup_days={self._warmup_days!r}, "
            f"fold_index={self._fold_index!r})"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, BacktestWindow):
            return False

        return (
            self._name == other._name
            and self._train_range == other._train_range
            and self._test_range == other._test_range
            and self._warmup_days == other._warmup_days
            and self._fold_index == other._fold_index
        )

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict for this window."""
        def _range_to_dict(r: BacktestDateRange) -> dict:
            return {
                "name": r.name,
                "start": r.start_date.isoformat()
                if hasattr(r.start_date, "isoformat") else r.start_date,
                "end": r.end_date.isoformat()
                if hasattr(r.end_date, "isoformat") else r.end_date,
            }

        return {
            "name": self._name,
            "train_range": _range_to_dict(self._train_range),
            "test_range": _range_to_dict(self._test_range)
            if self._test_range is not None else None,
            "warmup_days": self._warmup_days,
            "fold_index": self._fold_index,
        }
