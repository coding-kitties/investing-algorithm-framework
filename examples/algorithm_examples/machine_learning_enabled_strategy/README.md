# Machine-learning enabled strategy

A self-contained example showing how to plug a **pre-trained**
scikit-learn classifier into the signal-generation loop.

## What it shows

- Engineer features in a single helper (`_build_features`) — the
  same code path the model was trained on.
- Load a pickled classifier in `__init__` and store it on
  `self.model`.
- Convert per-bar `predict_proba` output into two boolean columns
  (`ml_enter`, `ml_exit`) and hand them to
  `signal_series_from_column` (vector) or `signals_from_column`
  (event).
- Implement **both** `generate_signal_series` (vector backtest) and
  `generate_signals` (event / paper / live) so the same model can
  run in every mode without changes.

## Run

```bash
pip install scikit-learn pyindicators

# Place your trained model next to backtest.py as model.pkl
python backtest.py
```

The pickled object only needs to expose `predict_proba(X)`; that
covers scikit-learn, XGBoost, LightGBM, CatBoost, and any custom
wrapper.

## Customising

- Swap the classifier — anything with `predict_proba` works.
- Add features in `FEATURE_COLUMNS` + `_build_features` (and
  retrain the model with the same set).
- Tune `enter_threshold` / `exit_threshold` to control how
  confident the model must be before opening or closing a
  position.
