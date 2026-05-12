# OHLCV Deduplication Protocol — Public Specification

**Status:** Draft. Reference implementation pending.
**Companion to:** [bundle-format-v2.md](./bundle-format-v2.md)
**Audience:** Backtest archival / upload services (e.g. Finterion).

This document specifies a content-addressed protocol for uploading
backtest bundles without re-uploading shared OHLCV (price) data. The
framework ships only the protocol; the server is out of scope and
proprietary to whoever runs it.

---

## Problem

A user has run 1,000 vector backtests over the same universe of 50
crypto pairs at 1-hour resolution for 2024–2026. Each `.iafbt`
bundle, if saved with `include_ohlcv=True`, embeds the same ~50 OHLCV
Parquet blobs. The OHLCV is roughly 2 MB per pair, so 100 MB per
bundle, 100 GB across the 1,000 bundles — but only 100 MB of unique
OHLCV.

The framework already content-addresses OHLCV at rest (each
`<sha256>.parquet` is stored once in the local OHLCV side store). The
protocol below extends that identity beyond the local filesystem.

---

## Identity

Each OHLCV blob is identified by the lowercase hex SHA-256 of its
**Parquet bytes** as written by `_df_to_parquet_bytes()`:

```python
sha256(parquet_bytes_with_zstd_level_5).hexdigest()
```

Crucially, the hash is computed **after** Parquet encoding, not on
the raw DataFrame. This means two clients writing the same logical
DataFrame with different Parquet writer settings (compression level,
column ordering, dictionary encoding) will produce different
identities, which is intentional: byte-identical inputs produce
byte-identical outputs.

When `float32_ohlcv=True` is used (see bundle v2 spec), the hash
covers the float32 bytes — float32 and float64 representations of
the "same" data are different OHLCV blobs.

---

## Wire format

All requests and responses are JSON unless noted otherwise. Binary
blobs use `application/octet-stream`. The protocol assumes HTTPS and
a bearer-token auth scheme; both are out of scope here.

### 1. Negotiate

The client lists the OHLCV hashes it intends to upload. The server
replies with the subset it does NOT yet have.

```
POST /api/v1/ohlcv/negotiate
Content-Type: application/json

{
  "hashes": [
    "a1b2c3d4...",
    "e5f6g7h8...",
    ...
  ]
}
```

```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "missing": [
    "e5f6g7h8..."
  ]
}
```

The server SHOULD respond in <200ms even for large inputs; treat the
endpoint as a set-difference query against a hash index.

The client MAY chunk the `hashes` array (recommended chunk size:
1,000) for very large uploads. The server MUST accept at least 10,000
hashes per request.

### 2. Upload missing OHLCV

For each hash in the `missing` list, the client uploads the raw
Parquet bytes. Order doesn't matter; uploads MAY be parallel.

```
PUT /api/v1/ohlcv/<sha256>
Content-Type: application/octet-stream
Content-Length: <bytes>

<raw parquet bytes>
```

```
HTTP/1.1 201 Created
```

The server MUST verify `sha256(body) == <sha256>` before storing,
and reject with `400 Bad Request` on mismatch. This prevents a buggy
client from poisoning the shared store.

A `409 Conflict` MAY be returned if the blob already exists (race
between negotiate and upload). The client SHOULD treat 409 as
success.

### 3. Upload bundle envelope

After all OHLCV blobs are stored on the server, the client uploads
the bundle envelope. The envelope is a normal `.iafbt` file MINUS
the OHLCV bytes — the manifest in the bundle still references the
OHLCV by hash, but the side-store files are NOT shipped.

```
PUT /api/v1/backtests/<algorithm_id>
Content-Type: application/vnd.investing-algorithm-framework.bundle+zstd
Content-Length: <bytes>

<bundle bytes>
```

```
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": "...",
  "ohlcv_hashes": ["a1b2c3d4...", ...]
}
```

The server MUST verify that every hash referenced by the bundle's
OHLCV manifest exists in the OHLCV store before accepting the
bundle, returning `424 Failed Dependency` with the missing hashes if
not. The client should re-run the negotiate + upload-missing steps
and retry.

The bundle's `ohlcv.store_dir` field is meaningless on the server
side — the server resolves blobs by hash, not by path. The field is
preserved on the wire for round-trip fidelity.

---

## Client algorithm

```python
def upload_backtests(paths, endpoint, api_key, parallelism=4):
    # Phase 1: discover hashes across all bundles
    bundle_hashes = {path: read_ohlcv_hashes(path) for path in paths}
    all_hashes = list({h for hs in bundle_hashes.values() for h in hs})

    # Phase 2: negotiate (chunked)
    missing = []
    for chunk in batched(all_hashes, 1000):
        missing += negotiate(endpoint, api_key, chunk)
    missing = set(missing)

    # Phase 3: upload missing OHLCV in parallel
    with ThreadPoolExecutor(parallelism) as ex:
        list(ex.map(
            lambda h: upload_ohlcv(endpoint, api_key, h),
            missing
        ))

    # Phase 4: upload bundle envelopes (envelope only, not OHLCV)
    with ThreadPoolExecutor(parallelism) as ex:
        list(ex.map(
            lambda p: upload_bundle(endpoint, api_key, p),
            paths
        ))
```

Concrete reference implementation lives outside the framework
(intentionally — see the rationale in
[bundle-format-v2.md](./bundle-format-v2.md)).

---

## Security & abuse considerations

- **Hash poisoning:** mitigated by server-side hash verification on
  upload (step 2).
- **Cross-tenant leakage:** servers SHOULD scope the OHLCV store
  per-tenant if their pricing model treats OHLCV as proprietary
  data; a global shared store is appropriate only when all OHLCV
  comes from public sources.
- **Replay attacks:** out of scope; rely on transport-layer auth.
- **Storage exhaustion:** the server SHOULD enforce per-tenant
  quotas on the OHLCV store independently of bundle quotas.

---

## Versioning

This protocol uses URL versioning (`/api/v1/...`). Breaking changes
require a new major version. Additive changes (new optional fields
in JSON bodies) MUST be safe for clients that ignore unknown fields.
