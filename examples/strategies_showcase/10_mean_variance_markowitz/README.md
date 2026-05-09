# 10 — Mean-Variance (Markowitz) Optimization

**Fit:** ✅ Same monthly-rebalance pattern as risk parity.

## Idea

At each rebalance, estimate the **expected returns** μ (using the trailing
sample mean) and the **covariance matrix** Σ from a 90-day window, and
solve for the long-only minimum-variance portfolio targeting a fixed
expected return.

`scipy.optimize.minimize` with SLSQP is used for the constrained QP — it
keeps the requirements list small (no `cvxpy`).

## Why this fits the framework

The framework provides per-symbol price history and order placement; the
optimisation is a pure function on top.

## Run

```bash
pip install -r requirements.txt
python backtest.py
```

## Caveats

- Sample-mean μ is a notoriously noisy estimator. In production replace it
  with a **shrinkage estimator** or a forward-looking signal (e.g. factor model).
- Σ also benefits from **Ledoit-Wolf shrinkage**.
- This example is a **structural template** — do not run it with real money.
