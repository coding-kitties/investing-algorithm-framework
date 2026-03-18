import warnings
# Allow SQLAlchemy deprecation, but error on ours
warnings.filterwarnings('ignore', category=DeprecationWarning, module='sqlalchemy')
warnings.simplefilter('error', RuntimeWarning)
warnings.filterwarnings('error', category=DeprecationWarning, message='.*window_size.*')

# Test 1: DataSource with warmup_window should NOT warn
from investing_algorithm_framework.domain.models.data.data_source import DataSource
ds = DataSource(warmup_window=200)
print('DataSource with warmup_window: OK')

# Test 2: std on small series
from investing_algorithm_framework.services.metrics.standard_deviation import (
    get_standard_deviation_downside_returns,
    get_standard_deviation_returns,
    get_daily_returns_std,
    get_downside_std_of_daily_returns
)
from datetime import datetime, timezone

class FakeSnapshot:
    def __init__(self, value, dt):
        self.total_value = value
        self.created_at = dt

# Only 2 snapshots -> 1 return -> std with ddof=1 would fail before fix
snaps = [
    FakeSnapshot(100, datetime(2024, 1, 1, tzinfo=timezone.utc)),
    FakeSnapshot(90, datetime(2024, 1, 2, tzinfo=timezone.utc)),
]
r1 = get_standard_deviation_downside_returns(snaps)
r2 = get_standard_deviation_returns(snaps)
r3 = get_daily_returns_std(snaps)
r4 = get_downside_std_of_daily_returns(snaps)
print(f'std functions with 2 snapshots: OK (results: {r1}, {r2}, {r3}, {r4})')
print('All checks passed!')
