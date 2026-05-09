# 26 — High-Frequency ML Inference

**Fit:** 🔴 Currently not possible at high frequency.

## Why it is currently not possible

Calling an ML model inside `run_strategy` is **fully supported today** —
there is no problem loading a `sklearn` / `xgboost` / `pytorch` model and
predicting at each bar. Many of the showcase strategies above could trivially
be ML-backed (replace the rule with `model.predict(features)`).

What is **not possible** is doing this at *high frequency*. The
combination of:

1. Python interpreter overhead (~10-100 µs per call).
2. Framework bar-loop overhead (~ms per iteration).
3. Model inference latency (10-1000 µs for a small tree, 1-100 ms for a
   small neural net, much more for an LLM).
4. Bar-driven scheduling (1-minute minimum).

…makes it a **bar-frequency** ML setup, not a high-frequency one. That is
a different beast.

## What you can do today

- **Bar-frequency ML overlay.** Train a model offline, register it as a
  feature engineer in the strategy, and use it as a signal at hourly /
  daily cadence. This is the standard quant-research workflow and is
  already supported.
- **Online learning.** Update a model on each bar with the latest
  observation; the bookkeeping fits cleanly into a `TradingStrategy`.

## What would change this

Sub-bar ML inference would need:

- The sub-second event loop discussed in folders 21 / 25.
- A model-server abstraction so inference can run in a dedicated process
  with shared-memory / IPC, not blocking the event loop.
- ONNX / TorchScript / C++ inference paths for sub-millisecond latency.

This is HFT plumbing (folder 23), not framework plumbing.
