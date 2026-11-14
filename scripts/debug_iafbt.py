#!/usr/bin/env python3
"""
Throwaway debugging script: show exactly what is stored inside a .iafbt bundle.

Usage:
    python scripts/debug_iafbt.py <path.iafbt>
    python scripts/debug_iafbt.py <directory/>   # scans for first .iafbt found

Prints:
  - Raw envelope header (magic, version, sizes)
  - Top-level document keys and their types/sizes
  - Per-study breakdown (multi-study bundles)
  - Per-run summary (date range, scalar metrics, orders/trades counts)
  - Blob keys (the embedded Parquet time-series)
  - A fully-decoded Backtest via open_bundle() for cross-checking
"""

import sys
import os
from pathlib import Path
from pprint import pformat

# ---------------------------------------------------------------------------
# Locate the file
# ---------------------------------------------------------------------------

def _find_bundle(arg: str) -> Path:
    p = Path(arg)
    if p.is_file():
        return p
    if p.is_dir():
        candidates = sorted(p.rglob("*.iafbt"))
        if not candidates:
            sys.exit(f"No .iafbt files found under {p}")
        print(f"[auto-select] {candidates[0]}\n")
        return candidates[0]
    sys.exit(f"Path not found: {p}")


# ---------------------------------------------------------------------------
# Low-level decode (no framework imports needed)
# ---------------------------------------------------------------------------

def _decode_raw(path: Path):
    try:
        import zstandard as zstd
        import msgpack
    except ImportError as e:
        sys.exit(f"Missing dependency: {e}. Run: pip install zstandard msgpack")

    _MAGIC = b"IAFB"
    blob = path.read_bytes()

    if not blob.startswith(_MAGIC):
        sys.exit("ERROR: Not a valid .iafbt bundle (missing IAFB magic).")

    version = int.from_bytes(blob[4:8], "little")
    raw = zstd.ZstdDecompressor().decompress(blob[8:])
    doc = msgpack.unpackb(raw, raw=False)
    return version, blob, raw, doc


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

SEP = "─" * 72

def _hdr(title: str):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def _scalar(label: str, value):
    print(f"  {label:<38} {value!r}")


def _type_summary(val) -> str:
    if isinstance(val, dict):
        return f"dict ({len(val)} keys)"
    if isinstance(val, list):
        inner = type(val[0]).__name__ if val else "?"
        return f"list[{len(val)}×{inner}]"
    if isinstance(val, bytes):
        return f"bytes ({len(val):,} B)"
    if isinstance(val, str) and len(val) > 80:
        return f"str({len(val)}) = {val[:60]!r}..."
    return f"{type(val).__name__} = {val!r}"


def _walk_dict(obj, indent=0, max_depth=3, max_list_items=3):
    prefix = "    " * indent
    if not isinstance(obj, dict) or indent >= max_depth:
        return
    for k in sorted(obj.keys()):
        v = obj[k]
        if isinstance(v, dict):
            print(f"{prefix}  {k}/ → dict ({len(v)} keys)")
            _walk_dict(v, indent + 1, max_depth)
        elif isinstance(v, list):
            inner = type(v[0]).__name__ if v else "?"
            print(f"{prefix}  {k} → list[{len(v)} × {inner}]")
            if v and isinstance(v[0], dict) and indent < max_depth - 1:
                for i, item in enumerate(v[:max_list_items]):
                    print(f"{prefix}    [{i}]:")
                    _walk_dict(item, indent + 2, max_depth)
                if len(v) > max_list_items:
                    print(f"{prefix}    ... ({len(v) - max_list_items} more)")
        elif isinstance(v, bytes):
            print(f"{prefix}  {k} → bytes ({len(v):,} B)")
        elif isinstance(v, str) and len(v) > 80:
            print(f"{prefix}  {k} → str({len(v)}) = {v[:60]!r}...")
        else:
            print(f"{prefix}  {k} = {v!r}")


def _runs_summary(runs: list, label: str):
    if not runs:
        print(f"  (no {label})")
        return
    print(f"  {label}: {len(runs)} run(s)")
    for i, r in enumerate(runs):
        bw = r.get("backtest_window") or {}
        tr = bw.get("train_range") or {}
        start = tr.get("start_date", "?")
        end = tr.get("end_date", "?")
        algo = r.get("algorithm_id", "?")
        n_orders = len(r.get("orders") or [])
        n_trades = len(r.get("trades") or [])
        n_snaps  = len(r.get("portfolio_snapshots") or [])
        metrics  = r.get("backtest_metrics") or {}
        sharpe   = metrics.get("sharpe_ratio", "n/a")
        mdd      = metrics.get("max_drawdown", "n/a")
        cagr     = metrics.get("cagr", "n/a")

        print(f"    run[{i}]  algo={algo!r}")
        print(f"             date: {start} → {end}")
        print(f"             orders={n_orders}  trades={n_trades}  snapshots={n_snaps}")
        print(f"             sharpe={sharpe}  max_dd={mdd}  cagr={cagr}")

        blob_fields = [k for k, v in metrics.items()
                       if isinstance(v, dict) and "@blob" in v]
        inline_series = [k for k, v in metrics.items()
                         if isinstance(v, list) and v]
        if blob_fields:
            print(f"             blob refs: {blob_fields}")
        if inline_series:
            print(f"             inline series: {inline_series}")


def _study_breakdown(doc: dict):
    studies = doc.get("studies") or {}
    if not studies:
        return
    _hdr("STUDIES (multi-study bundle)")
    print(f"  Studies : {sorted(studies.keys())}")
    for sname, sdata in studies.items():
        print(f"\n  ── Study: {sname!r} ──")
        print(f"     engine_type : {sdata.get('engine_type')!r}")
        vr = sdata.get("vector_runs") or []
        er = sdata.get("event_runs") or []
        br = sdata.get("backtest_runs") or []
        _runs_summary(vr, "vector_runs")
        _runs_summary(er, "event_runs")
        _runs_summary(br, "backtest_runs (legacy)")


# ---------------------------------------------------------------------------
# High-level decode via framework
# ---------------------------------------------------------------------------

def _open_via_framework(path: Path):
    try:
        sys.path.insert(0, str(path.parents[1]))  # repo root
        from investing_algorithm_framework.domain.backtesting.bundle import open_bundle
        return open_bundle(path)
    except Exception as e:
        return f"(framework decode failed: {e})"


def _print_studies_only(path: Path):
    """Print just the study names and their attributes."""
    version, blob, raw, doc = _decode_raw(path)
    studies = doc.get("studies") or {}

    _hdr(f"STUDIES  ({len(studies)} total)  —  {path.name}")
    if not studies:
        print("  (no studies found in this bundle)")
        print(f"\n{SEP}\n")
        return

    for sname, sdata in studies.items():
        print(f"\n  ── Study: {sname!r} ──")
        if not isinstance(sdata, dict):
            print(f"     (unexpected type: {type(sdata).__name__})")
            continue
        for attr, val in sorted(sdata.items()):
            if attr in ("vector_runs", "event_runs", "backtest_runs"):
                count = len(val) if isinstance(val, list) else ("?" if val else 0)
                print(f"     {attr:<38} {count} run(s)")
            elif isinstance(val, dict):
                print(f"     {attr:<38} dict({len(val)} keys): {sorted(val.keys())}")
            elif isinstance(val, list):
                inner = type(val[0]).__name__ if val else "?"
                print(f"     {attr:<38} list[{len(val)} × {inner}]")
            elif isinstance(val, bytes):
                print(f"     {attr:<38} bytes({len(val):,} B)")
            else:
                print(f"     {attr:<38} {val!r}")

    print(f"\n{SEP}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <path.iafbt|directory> [--studies]")
        sys.exit(0)

    args = sys.argv[1:]
    studies_only = "--studies" in args
    path_arg = next(a for a in args if not a.startswith("--"))
    path = _find_bundle(path_arg)

    if studies_only:
        _print_studies_only(path)
        return

    version, blob, raw, doc = _decode_raw(path)

    # ── 1. Header ─────────────────────────────────────────────────────────
    _hdr("HEADER")
    _scalar("File", str(path))
    _scalar("On-disk size", f"{len(blob):,} B  ({len(blob)/1024:.1f} KB)")
    _scalar("Decompressed size", f"{len(raw):,} B  ({len(raw)/1024:.1f} KB)")
    _scalar("Compression ratio", f"{len(raw)/max(len(blob),1):.1f}×")
    _scalar("Format version", version)
    _scalar("Magic bytes", blob[:4])

    # ── 2. Top-level keys ─────────────────────────────────────────────────
    _hdr("TOP-LEVEL DOCUMENT KEYS")
    for k in sorted(doc.keys()):
        print(f"  {k:<30} {_type_summary(doc[k])}")

    # ── 3. Scalar metadata ────────────────────────────────────────────────
    _hdr("SCALAR METADATA")
    for field in ("algorithm_id", "name", "engine_type", "tag",
                  "risk_free_rate", "created_at", "description"):
        if field in doc:
            _scalar(field, doc[field])

    # ── 4. Blob map ───────────────────────────────────────────────────────
    blobs = doc.get("blobs") or {}
    _hdr(f"EMBEDDED PARQUET BLOBS  ({len(blobs)} total)")
    if blobs:
        for k, v in sorted(blobs.items()):
            print(f"  {k:<55} {len(v):>8,} B")
    else:
        print("  (none — v1 bundle or no heavy series)")

    # ── 5. Runs breakdown ─────────────────────────────────────────────────
    engine_type = doc.get("engine_type")
    _hdr(f"RUNS  (engine_type={engine_type!r})")
    vr = doc.get("vector_runs") or []
    er = doc.get("event_runs") or []
    br = doc.get("backtest_runs") or []
    _runs_summary(vr, "vector_runs")
    _runs_summary(er, "event_runs")
    _runs_summary(br, "backtest_runs (legacy)")

    # ── 6. Summary metrics ────────────────────────────────────────────────
    for sm_key in ("vector_metrics", "event_metrics", "backtest_summary"):
        sm = doc.get(sm_key)
        if sm and isinstance(sm, dict):
            _hdr(f"SUMMARY METRICS  ({sm_key})")
            for mk, mv in sorted(sm.items()):
                if isinstance(mv, (int, float, str, bool, type(None))):
                    _scalar(mk, mv)
                elif isinstance(mv, list):
                    print(f"  {mk:<38} list[{len(mv)}]")
                elif isinstance(mv, dict) and "@blob" in mv:
                    print(f"  {mk:<38} {{@blob: {mv['@blob']!r}}}")

    # ── 7. Multi-study breakdown ──────────────────────────────────────────
    _study_breakdown(doc)

    # ── 8. OHLCV manifest ─────────────────────────────────────────────────
    ohlcv = doc.get("ohlcv")
    if ohlcv:
        _hdr("OHLCV SIDE-STORE")
        _scalar("store_dir", ohlcv.get("store_dir"))
        manifest = ohlcv.get("manifest") or {}
        print(f"  manifest entries: {len(manifest)}")
        for k, v in list(manifest.items())[:5]:
            print(f"    {k} → {v}")
        if len(manifest) > 5:
            print(f"    ... ({len(manifest) - 5} more)")

    # ── 9. Framework cross-check ──────────────────────────────────────────
    _hdr("FRAMEWORK CROSS-CHECK  (open_bundle)")
    bt = _open_via_framework(path)
    if isinstance(bt, str):
        print(f"  {bt}")
    else:
        print(f"  algorithm_id   : {bt.algorithm_id!r}")
        print(f"  engines active : {bt.engines}")
        all_runs = bt.get_all_backtest_runs()
        print(f"  total runs     : {len(all_runs)}")
        if all_runs:
            r0 = all_runs[0]
            print(f"  run[0] orders  : {len(r0.orders)}")
            print(f"  run[0] trades  : {len(r0.trades)}")
            print(f"  run[0] snaps   : {len(r0.portfolio_snapshots)}")
            m = r0.backtest_metrics
            if m:
                print(f"  run[0] sharpe  : {getattr(m, 'sharpe_ratio', 'n/a')}")
                print(f"  run[0] max_dd  : {getattr(m, 'max_drawdown', 'n/a')}")
                eq = getattr(m, 'equity_curve', None)
                print(f"  run[0] equity_curve points : {len(eq) if eq else 0}")
        studies = getattr(bt, "studies", None) or {}
        if studies:
            print(f"  named studies  : {sorted(studies.keys())}")

    print(f"\n{SEP}\n")


if __name__ == "__main__":
    main()
