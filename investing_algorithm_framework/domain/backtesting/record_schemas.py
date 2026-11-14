"""Arrow v1 schemas and replay provenance for engine-neutral evidence."""
from .records import RECORD_VERSION, canonical_bytes, content_id


def record_schema(kind: str):
    """Return the exact typed batch boundary; Arrow is imported on demand."""
    import pyarrow as arrow

    text = arrow.string()
    integer = arrow.int64()
    binary = arrow.binary()
    real = arrow.float64()
    boolean = arrow.bool_()

    def required(name, datatype):
        return arrow.field(name, datatype, nullable=False)

    identity = [
        required("evaluation_id", text), required("attempt_id", text),
        required("sequence", integer), required("timestamp_us", integer),
        required("symbol_id", text), required("strategy_id", text),
    ]
    schemas = {
        "confluence_evaluation": identity + [
            required("card_id", text), arrow.field("score", real),
            arrow.field("qualified", boolean),
            required("primary_outcome", arrow.uint8()),
            required("matched_rule_bits", binary),
            required("requirement_bits", binary),
            required("veto_bits", binary),
            required("evaluated_bits", binary),
            required("available_bits", binary),
            required("group_scores", arrow.list_(
                arrow.field("element", real)
            )),
            arrow.field("detail_id", text),
        ],
        "generic_trace": identity + [required("trace_payload", binary)],
        "diagnostic": [
            required("detail_id", text), required("evaluation_id", text),
            required("payload", binary),
        ],
        "execution_link": [
            required("attempt_id", text), required("sequence", integer),
            required("timestamp_us", integer),
            required("evaluation_id", text),
            required("entity_kind", text), required("entity_id", text),
            arrow.field("parent_kind", text), arrow.field("parent_id", text),
            arrow.field("detail_id", text),
        ],
        "run_context": [
            required("attempt_id", text), required("algorithm_id", text),
            required("study_id", text), required("window_id", text),
            required("engine_id", text), required("provenance_id", text),
        ],
    }
    if kind not in schemas:
        raise ValueError(f"Unknown record kind: {kind}")
    return arrow.schema(schemas[kind], metadata={
        b"iaf.record_kind": kind.encode("ascii"),
        b"iaf.record_version": str(RECORD_VERSION).encode("ascii"),
        b"iaf.timestamp_unit": b"microseconds since Unix epoch UTC",
    })


def record_batch(kind: str, records):
    """Build one caller-bounded batch, enforcing required values and enums."""
    import pyarrow as arrow

    schema = record_schema(kind)
    rows = list(records)
    for row in rows:
        if set(row) - set(schema.names):
            raise ValueError("Unknown fields in a v1 record")
        for field in schema:
            if not field.nullable and row.get(field.name) is None:
                raise ValueError(f"Missing required field: {field.name}")
        if kind == "execution_link":
            if row["entity_kind"] not in (
                "signal", "risk_rejection", "order", "fill",
            ):
                raise ValueError("Unknown execution entity kind")
            parent_kind = row.get("parent_kind")
            parent_id = row.get("parent_id")
            if (parent_kind is None) != (parent_id is None) or (
                parent_kind is not None and parent_kind not in (
                    "signal", "risk_rejection", "order", "fill",
                )
            ):
                raise ValueError("Invalid execution parent reference")
    batch = arrow.RecordBatch.from_pylist(rows, schema=schema)
    batch.validate(full=True)
    return batch


def validate_provenance(document: dict) -> None:
    """Require explicit replay inputs; null means unknown, never a default."""
    required = {
        "version", "algorithm_id", "study_id", "window_id", "engine_id",
        "strategies", "market_data", "indicators", "execution", "environment",
    }
    if not required <= document.keys() or (
        document["version"] != RECORD_VERSION
    ):
        raise ValueError("Incomplete or unsupported replay provenance")
    for name in ("algorithm_id", "study_id", "window_id", "engine_id"):
        if not isinstance(document[name], str) or not document[name]:
            raise ValueError(f"Invalid provenance {name}")
    members = {
        "strategies": {"strategy_id", "version", "code_digest", "parameters",
                       "evaluator_version", "card_ids"},
        "market_data": {"symbol_id", "provider", "content_digest", "start_us",
                        "end_us", "timeframe", "adjustments"},
        "indicators": {"name", "implementation", "version", "parameters",
                       "inputs", "warmup", "alignment", "missing_policy"},
    }
    for name, keys in members.items():
        if not isinstance(document[name], list) or any(
            not isinstance(item, dict) or not keys <= item.keys()
            for item in document[name]
        ):
            raise ValueError(f"Incomplete provenance {name}")
    if not document["strategies"] or not document["market_data"]:
        raise ValueError("Provenance requires strategy and market data IDs")
    for name, keys in (
        ("execution", {"fees", "slippage", "sizing", "fill_timing", "risk",
                       "conflicts", "seed", "recording_policy"}),
        ("environment", {"framework_version", "dependencies", "platform"}),
    ):
        if not isinstance(document[name], dict) or (
            not keys <= document[name].keys()
        ):
            raise ValueError(f"Incomplete provenance {name}")
    canonical_bytes(document)


def provenance_id(document: dict) -> str:
    validate_provenance(document)
    return content_id("provenance", document)
