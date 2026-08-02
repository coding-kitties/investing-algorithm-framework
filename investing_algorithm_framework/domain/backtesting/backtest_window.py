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

    gap_days records the purge period between the end of training and the
    start of testing (train_range.end_date -> test_range.start_date). It is
    stored so that producer intent is preserved on the wire, and validated
    against the actual dates when a test_range is present.

    step_days records the inter-window step used by the walk-forward
    generator that produced this window (e.g. `step_days=90` for a
    quarterly rolling walk-forward). It is None for one-off windows and
    for k-fold windows, which are not step-generated.

    Attributes:
        name (Optional[str]): An optional name for the window, e.g. "Window 1".
        train_range (BacktestDateRange): The full date range used for
            training, including any warmup period.
        test_range (Optional[BacktestDateRange]): The date range used for
            out-of-sample testing. None until assigned.
        warmup_days (int): Number of days at the start of train_range
            reserved for warming up indicators (e.g., a 26-day EMA needs
            26 warmup days). Not counted as effective training. Default is 0.
        gap_days (Optional[int]): Purge period between train_range.end_date
            and test_range.start_date. If not provided and test_range is
            set, it is computed from the dates. None when test_range is
            unset. Default is None.
        step_days (Optional[int]): Inter-window step used by the generator.
            None for k-fold and one-off windows. Default is None.
        fold_index (Optional[int]): Zero-based fold index when this window
            is part of a k-fold split. None for rolling / anchored / one-off
            windows.
    """

    def __init__(
        self,
        train_range: BacktestDateRange,
        test_range: Optional[BacktestDateRange] = None,
        warmup_days: int = 0,
        gap_days: Optional[int] = None,
        step_days: Optional[int] = None,
        fold_index: Optional[int] = None,
        name: Optional[str] = None,
    ):
        if warmup_days < 0:
            raise ValueError("warmup_days must be >= 0")

        train_duration = (train_range.end_date - train_range.start_date).days

        if not (warmup_days < train_duration):
            raise ValueError(
                f"warmup_days ({warmup_days}) must be less than the total "
                f"training duration ({train_duration} days)"
            )

        if gap_days is not None and gap_days < 0:
            raise ValueError("gap_days must be >= 0 when provided")

        if step_days is not None and step_days <= 0:
            raise ValueError("step_days must be > 0 when provided")

        self._name = name
        self._train_range = train_range
        self._warmup_days = warmup_days
        self._fold_index = fold_index
        self._step_days = step_days
        # gap_days is stored; the test_range setter fills it in or
        # verifies it against the actual dates.
        self._gap_days = gap_days
        self.test_range = test_range  # goes through the setter

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
            computed_gap = (
                value.start_date - self._train_range.end_date
            ).days
            if self._gap_days is None:
                self._gap_days = computed_gap
            elif self._gap_days != computed_gap:
                raise ValueError(
                    f"declared gap_days ({self._gap_days}) does not match "
                    f"the gap implied by the dates ({computed_gap} days). "
                    "Adjust either gap_days or test_range."
                )
        else:
            # No test_range -> gap_days has no meaning; clear it unless
            # the caller declared it explicitly.
            if self._gap_days is not None and self._test_range is not None:
                # We had a test_range before and are clearing it; clear
                # the derived gap too.
                self._gap_days = None
        self._test_range = value

    @classmethod
    def from_dict(cls, d: dict) -> "BacktestWindow":
        """
        Create a BacktestWindow from a dict as returned by
        :py:meth:`to_dict`, e.g.::

            {
                "name": "Window 1",
                "train_range": {"name": "train", "start": iso, "end": iso},
                "test_range":  {"name": "test",  "start": iso, "end": iso},
                "warmup_days": 0,
                "gap_days": 5,
                "step_days": 90,
                "fold_index": None,
            }

        Either range field may already be a :class:`BacktestDateRange`
        instance (accepted for backward compat with in-memory callers).
        """
        from datetime import datetime as _dt

        def _to_range(raw) -> Optional[BacktestDateRange]:
            if raw is None:
                return None
            if isinstance(raw, BacktestDateRange):
                return raw
            start = raw.get("start", raw.get("start_date"))
            end = raw.get("end", raw.get("end_date"))
            if isinstance(start, str):
                start = _dt.fromisoformat(start)
            if isinstance(end, str):
                end = _dt.fromisoformat(end)
            return BacktestDateRange(
                start_date=start,
                end_date=end,
                name=raw.get("name"),
            )

        train_range = _to_range(d["train_range"])
        if train_range is None:
            raise ValueError(
                "BacktestWindow.from_dict requires 'train_range'."
            )
        return cls(
            name=d.get("name"),
            train_range=train_range,
            test_range=_to_range(d.get("test_range")),
            warmup_days=d.get("warmup_days", 0),
            gap_days=d.get("gap_days"),
            step_days=d.get("step_days"),
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
        """Purge period in days between the end of training and the start
        of testing (train_range.end_date -> test_range.start_date).

        Stored on the wire. Verified against the actual dates whenever
        test_range is set. None when test_range is unset.
        """
        return self._gap_days

    @property
    def step_days(self) -> Optional[int]:
        """Inter-window step used by the generator that produced this window.

        None for k-fold and one-off windows (they are not step-generated).
        Same value on every window in a rolling / anchored sequence.
        """
        return self._step_days

    @property
    def fold_index(self) -> Optional[int]:
        """Zero-based fold index for k-fold windows. None otherwise."""
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
            f"gap_days={self._gap_days!r}, "
            f"step_days={self._step_days!r}, "
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
            and self._gap_days == other._gap_days
            and self._step_days == other._step_days
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
            "gap_days": self._gap_days,
            "step_days": self._step_days,
            "fold_index": self._fold_index,
        }
