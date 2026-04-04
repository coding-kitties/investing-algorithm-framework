### 2026-04-04: TimeFrame enum expansion (issue #412)
**By:** Richard (Backend Dev)
**What:** Added TWENTY_MINUTE ("20m"), SIX_HOUR ("6h"), EIGHT_HOUR ("8h"), THREE_DAY ("3d") to TimeFrame enum with corresponding amount_of_minutes entries. No changes to from_string — existing loop logic handles all new values automatically.
**Why:** Common exchange candle intervals (Bybit, others) were missing, causing ValueError when users passed these timeframes.
