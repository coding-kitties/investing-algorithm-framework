import pytest
from tests.utils import random_string

from bot.constants import TimeUnit
from bot import OperationalException


def test_minute():

    for value in ['MIN', 'min', 'MINUTE', 'minute', 'MINUTES', 'minutes']:
        time_unit = TimeUnit.from_string(value)
        assert TimeUnit.MINUTE.equals(time_unit)
        assert TimeUnit.MINUTE.equals(value)

    for value in ['HR', 'hr', 'HOUR', 'hour', 'HOURS', 'hour']:
        time_unit = TimeUnit.from_string(value)
        assert TimeUnit.HOUR.equals(time_unit)
        assert TimeUnit.HOUR.equals(value)

    for value in ['SEC' 'sec', 'SECOND', 'second', 'SECONDS', 'seconds']:
        time_unit = TimeUnit.from_string(value)
        assert TimeUnit.SECOND.equals(time_unit)
        assert TimeUnit.SECOND.equals(value)

    with pytest.raises(OperationalException):
        value = random_string(10)
        TimeUnit.from_string(value)
