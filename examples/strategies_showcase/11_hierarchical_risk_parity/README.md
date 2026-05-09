# 11 — Hierarchical Risk Parity (HRP)

**Fit:** ✅ Same rebalance scaffolding as risk parity / Markowitz.

## Idea

López de Prado's HRP avoids the instability of mean-variance by:

1. Computing the **correlation distance** matrix.
2. Performing **single-linkage hierarchical clustering**.
3. **Quasi-diagonalising** the covariance matrix along the dendrogram order.
4. **Recursively bisecting** the clusters and allocating inversely to
   cluster variance.

It produces stable, well-diversified weights without needing μ.

## Why this fits the framework

Same monthly-rebalance pattern as #09 / #10. The HRP routine is a pure
function on the trailing covariance — no framework primitive is missing.

## Run

```bash
pip install -r requirements.txt
python backtest.py
```

## References

López de Prado, M. (2016). *Building Diversified Portfolios that Outperform
Out-of-Sample*. Journal of Portfolio Management.
