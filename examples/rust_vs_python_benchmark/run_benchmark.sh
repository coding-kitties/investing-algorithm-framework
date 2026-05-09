#!/usr/bin/env bash
# Orchestrate the Python-vs-Rust benchmark end-to-end.
#
# Steps:
#   1. Generate synthetic OHLCV data (parquet + CSV) if missing
#   2. Build the Rust binary in release mode if missing
#   3. Run the Python framework benchmark
#   4. Run the Rust reference benchmark
#   5. Print a side-by-side summary table
set -euo pipefail

cd "$(dirname "$0")"

YEARS="${YEARS:-10}"
COMBOS="${COMBOS:-25}"
PY_WORKERS="${PY_WORKERS:-1}"
RUST_WORKERS="${RUST_WORKERS:-0}"  # 0 = all cores
RUST_PERSIST="${RUST_PERSIST:-true}" # mirror framework's per-backtest SQLite
RUST_METRICS="${RUST_METRICS:-true}" # mirror framework's BacktestMetrics pass

mkdir -p data results

if [[ ! -f "data/BTC-USD.parquet" ]]; then
  echo "==> Generating synthetic data (${YEARS}y hourly × 5 symbols)"
  python generate_data.py --years "${YEARS}"
fi

if [[ ! -x "rust_bench/target/release/rust_bench" ]]; then
  echo "==> Building rust_bench (release; first build can take a few minutes)"
  ( cd rust_bench && cargo build --release )
fi

echo
echo "==> Running Python framework benchmark"
python python_bench.py --combos "${COMBOS}" --years "${YEARS}" --workers "${PY_WORKERS}"

echo
echo "==> Running Rust reference benchmark (persist=${RUST_PERSIST})"
( cd rust_bench && ./target/release/rust_bench \
    --combos "${COMBOS}" \
    --years "${YEARS}" \
    --workers "${RUST_WORKERS}" \
    --persist "${RUST_PERSIST}" \
    --metrics "${RUST_METRICS}" )

echo
echo "==> Comparison"
python compare.py
