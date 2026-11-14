#!/usr/bin/env python3
"""Print all top-level (and nested) keys of a .iafbt bundle file."""

import sys
import zstandard as zstd
import msgpack

_MAGIC = b"IAFB"


def print_keys(obj, prefix="", max_depth=4):
    """Recursively print dict keys up to *max_depth* levels."""
    if not isinstance(obj, dict) or max_depth <= 0:
        return
    for key in sorted(obj.keys()):
        val = obj[key]
        full = f"{prefix}{key}"
        type_hint = type(val).__name__
        if isinstance(val, dict):
            print(f"  {full}/ ({len(val)} keys)")
            print_keys(val, prefix=f"{full}/", max_depth=max_depth - 1)
        elif isinstance(val, list):
            print(f"  {full} [{len(val)} items, {type_hint}]")
            if val and isinstance(val[0], dict):
                print(f"    (first item keys:)")
                print_keys(
                    val[0], prefix=f"{full}[0]/",
                    max_depth=max_depth - 1,
                )
        elif isinstance(val, bytes):
            print(f"  {full} <bytes, {len(val)} B>")
        elif isinstance(val, str) and len(val) > 120:
            print(f"  {full} = {val[:120]}... ({type_hint})")
        else:
            print(f"  {full} = {val!r} ({type_hint})")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path.iafbt> [max_depth]")
        sys.exit(1)

    path = sys.argv[1]
    max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 4

    with open(path, "rb") as f:
        blob = f.read()

    if not blob.startswith(_MAGIC):
        print("ERROR: Not a valid .iafbt bundle (missing IAFB magic).")
        sys.exit(1)

    version = int.from_bytes(blob[4:8], "little")
    raw = zstd.ZstdDecompressor().decompress(blob[8:])
    doc = msgpack.unpackb(raw, raw=False)

    print(f"Bundle: {path}")
    print(f"Format version: {version}")
    print(f"Compressed size: {len(blob):,} B")
    print(f"Decompressed size: {len(raw):,} B")
    print(f"Top-level keys ({len(doc)}):\n")

    print_keys(doc, max_depth=max_depth)


if __name__ == "__main__":
    main()
