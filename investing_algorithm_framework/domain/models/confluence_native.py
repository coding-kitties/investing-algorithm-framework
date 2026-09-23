"""Optional numeric batch backend; the pandas evaluator remains the default."""
from functools import lru_cache
import json
import math

import numpy as np
import pandas as pd


class NativeConfluenceUnsupported(TypeError):
    """The optional native backend cannot preserve this input's semantics."""


@lru_cache(maxsize=128)
def _compile(definition):
    import iaf_confluence_native

    if iaf_confluence_native.SEMANTICS_VERSION != "confluence-vector-v1":
        raise NativeConfluenceUnsupported("Native semantics version mismatch")
    try:
        return iaf_confluence_native.CompiledCard(definition)
    except ValueError as error:
        raise NativeConfluenceUnsupported(str(error)) from error


def _definition(card):
    def check(value):
        if isinstance(value, dict):
            for child in value.values():
                check(child)
        elif isinstance(value, (tuple, list)):
            for child in value:
                check(child)
        elif type(value) is int and abs(value) > 2 ** 53:
            raise NativeConfluenceUnsupported(
                "Constant exceeds exact f64 range"
            )
        elif type(value) is float and not math.isfinite(value):
            raise NativeConfluenceUnsupported("Nonfinite definition constant")

    try:
        definition = card.to_dict()
        check(definition)
        return json.dumps(definition, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as error:
        raise NativeConfluenceUnsupported(str(error)) from error


def evaluate_native_card(card, frame):
    """One FFI call per frame, with explicit copies and no Python callbacks."""
    compiled = _compile(_definition(card))
    columns = []
    for name in compiled.column_names():
        series = frame[name]
        if str(series.dtype) not in ("float64", "Float64"):
            raise NativeConfluenceUnsupported(
                f"Column {name!r} needs float64/Float64, got {series.dtype}"
            )
        columns.append(series.to_numpy(
            dtype="<f8", na_value=np.nan
        ).tobytes())
    scores, available, qualified = compiled.evaluate(columns, len(frame))
    return pd.DataFrame({
        "score": np.frombuffer(scores, dtype="<f8"),
        "available": np.frombuffer(available, dtype=np.bool_),
        "qualified": np.frombuffer(qualified, dtype=np.bool_),
    }, index=frame.index)
