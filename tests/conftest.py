"""
Global pytest fixture that ensures DuckDB sessions are closed and engine
is disposed after every test, preventing cross-test file-lock pollution.
"""
import gc
import pytest
from sqlalchemy.orm import close_all_sessions

from investing_algorithm_framework.infrastructure.database import Session


@pytest.fixture(autouse=True)
def _cleanup_duckdb_after_test():
    """Yield to the test, then close all sessions and dispose the engine."""
    yield
    try:
        close_all_sessions()
    except Exception:
        pass

    try:
        engine = Session.kw.get('bind')
        if engine is not None:
            engine.dispose()
    except Exception:
        pass

    Session.configure(bind=None)
    gc.collect()
