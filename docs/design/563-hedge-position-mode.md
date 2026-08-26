# Hedge Position Mode

Status: accepted final design for issue #563.

## Scope

The framework keeps exactly one `Position` per `(portfolio, symbol)`. A
position stores two independent, nonnegative legs: `long_amount`,
`short_amount`, `long_cost`, and `short_cost`. `Trade.is_short` remains the
directional identity of a trade; position legs do not replace it.

`PositionMode.NETTING` is the default and preserves current behavior.
`PositionMode.HEDGE` permits both legs to be nonzero. Event and vector
backtests opt into leg-aware matching, execution, risk, cooldown, persistence,
and reporting through the portfolio configuration.

## Invariants and compatibility

- Leg amounts and costs are finite and nonnegative.
- `amount` is always net exposure: `long_amount - short_amount`.
- Gross exposure is `long_amount + short_amount`.
- In NETTING mode at most one amount leg is nonzero.
- In HEDGE mode both amount legs may be nonzero.
- Legacy construction or mutation through `amount` and `cost` has NETTING
  semantics: it replaces both legs from the signed amount, assigning the
  nonnegative cost to the occupied leg. It never creates a hedged position.
- Legacy `cost` retains NETTING semantics: it is the nonnegative basis of the
  side left after netting (`long_cost` for nonnegative net exposure and
  `short_cost` for negative net exposure). This preserves the framework's
  existing positive short-entry proceeds. For an exactly flat hedged position
  it is zero. `net_cost` is the signed view `long_cost - short_cost`, while
  `gross_cost` is `long_cost + short_cost`.
- Explicit leg construction is authoritative. Serialized legacy payloads
  without leg fields are upgraded using the signed `amount`; payloads with leg
  fields derive the legacy net views from those fields.

## Fill semantics

NETTING fills continue to use the existing signed amount/cost mutation path.
In HEDGE mode, long buys and long sells affect only the long leg; short opens
and covers affect only the short leg. A fill does not reduce the opposite leg.
`Trade.is_short` routes fills and closes to the correct leg.

## Side-aware risk and cooldowns

Risk limits, stop-loss/take-profit evaluation, conflict resolution, and
cooldowns key state by `(portfolio, symbol, side)` in HEDGE mode. NETTING keeps
the current `(portfolio, symbol)` behavior. Side-specific closes never close
or block the opposite leg.

## Engines

Event and vector engines consume `position_mode` and produce equivalent leg
mutations. Both can open long and short trades for one symbol on the same bar,
close each leg independently, attribute PnL by side, and apply side-aware risk
and cooldown rules. A run records its effective mode in
`metadata["position_mode"]`.

## Persistence and migration

SQL position and position-snapshot tables gain four nullable-compatible,
nonnegative leg columns. Startup migration is additive and idempotent. Existing
rows are backfilled as follows:

- `amount >= 0`: `long_amount = amount`, `short_amount = 0`, legacy `cost` is
  assigned to `long_cost`, and `short_cost = 0`.
- `amount < 0`: `long_amount = 0`, `short_amount = abs(amount)`, legacy `cost`
  is assigned by magnitude to `short_cost`, and `long_cost = 0`.

The legacy `amount` and `cost` columns remain present. No row is split and the
unique `(portfolio_id, symbol)` constraint remains unchanged.

## Reporting and live venues

Backtest bundles round-trip the portfolio mode and all position and snapshot
leg fields. Reports expose net and gross exposure plus long and short
breakdowns while retaining the legacy net fields.

Live HEDGE startup uses an explicit two-adapter capability contract. The
selected `OrderExecutor` and `PortfolioProvider` must both return `True` from
`supports_position_mode(market, PositionMode.HEDGE)`. Existing custom adapters
default to NETTING-only and must opt in after they can route directional
orders and reconcile independent long/short legs. The check is local and does
not initialize credentials or call the venue.

The bundled CCXT adapters currently remain NETTING-only. Although an exchange
may advertise `setPositionMode` or `fetchPositions`, the executor does not yet
provide verified venue-specific directional order parameters and the provider
currently reconciles spot balances rather than derivative position legs.
Application startup therefore fails fast for live CCXT HEDGE configurations
with the unsupported adapter capability in the error message. Backtests bypass
this live capability check.
