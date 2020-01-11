import pytest
from tests.utils import random_string

from bot import OperationalException
from bot.constants import ExecutionMode


def test_minute():

    for value in ['async', 'asynchronous']:
        execution_mode = ExecutionMode.from_string(value)
        assert ExecutionMode.ASYNCHRONOUS.equals(execution_mode)
        assert ExecutionMode.ASYNCHRONOUS.equals(value)

    for value in ['sync', 'synchronous']:
        execution_mode = ExecutionMode.from_string(value)
        assert ExecutionMode.SYNCHRONOUS.equals(execution_mode)
        assert ExecutionMode.SYNCHRONOUS.equals(value)

    with pytest.raises(OperationalException):
        value = random_string(10)
        ExecutionMode.from_string(value)
