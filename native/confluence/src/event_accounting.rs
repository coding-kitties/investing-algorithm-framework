use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

type Updates = Vec<(String, f64)>;
type OrderUpdates = (Updates, Updates, Updates);
type RiskUpdate = (bool, Option<f64>, Option<f64>, bool);

fn put(updates: &mut Updates, key: &str, value: f64) {
    updates.push((key.to_owned(), value));
}

type CoverTrade = (f64, f64, f64, f64, f64, f64);
type CoverFill = (usize, f64, f64, f64, f64, f64, f64, f64, f64);
type CoverPlan = (Vec<CoverFill>, f64, f64);
type SellAllocation = (usize, f64, f64, f64, f64, f64, f64, f64, f64, f64);
type SellFill = (usize, f64, f64, f64, f64, f64, f64, f64);
type SellPlan = (Vec<SellFill>, f64, f64);

fn sift_reservations(heap: &mut [usize], rows: &[(i64, f64, bool)], mut position: usize) {
    let value = heap[position];
    while position > 0 {
        let parent = (position - 1) / 2;
        if rows[value].0 >= rows[heap[parent]].0 {
            break;
        }
        heap[position] = heap[parent];
        position = parent;
    }
    heap[position] = value;
}

#[pyfunction]
pub fn event_reservation_plan(
    rows: Vec<(i64, f64, bool)>,
    amount: f64,
    requested: Option<Vec<(usize, f64)>>,
) -> PyResult<Vec<(usize, f64, f64)>> {
    if !amount.is_finite() || rows.iter().any(|row| !row.1.is_finite()) {
        return Err(PyValueError::new_err("Invalid reservation input"));
    }
    let mut available: Vec<f64> = rows.iter().map(|row| row.1).collect();
    let mut plan = Vec::new();
    if let Some(requested) = requested {
        for (index, portion) in requested {
            if index >= rows.len() || !portion.is_finite() {
                return Err(PyValueError::new_err("Invalid explicit reservation"));
            }
            if rows[index].2 {
                return Err(PyValueError::new_err(
                    "SELL orders can only close long trades",
                ));
            }
            available[index] -= portion;
            plan.push((index, portion, available[index]));
        }
    } else {
        let mut heap = Vec::new();
        let mut total = 0.0;
        for (index, row) in rows.iter().enumerate() {
            if !row.2 && row.1 > 0.0 {
                total += row.1;
                heap.push(index);
                let position = heap.len() - 1;
                sift_reservations(&mut heap, &rows, position);
            }
        }
        if total < amount {
            return Err(PyValueError::new_err(
                "Not enough amount to close in trades.",
            ));
        }
        let mut remaining = amount;
        while remaining > 0.0 && !heap.is_empty() {
            let index = heap[0];
            let last = heap.pop().unwrap();
            if !heap.is_empty() {
                heap[0] = last;
                let mut position = 0;
                let mut child = 1;
                while child < heap.len() {
                    let right = child + 1;
                    if right < heap.len() && rows[heap[child]].0 >= rows[heap[right]].0 {
                        child = right;
                    }
                    heap[position] = heap[child];
                    position = child;
                    child = position * 2 + 1;
                }
                heap[position] = last;
                sift_reservations(&mut heap, &rows, position);
            }
            let portion = remaining.min(available[index]);
            available[index] -= portion;
            remaining -= portion;
            plan.push((index, portion, available[index]));
        }
    }
    if plan.iter().any(|row| !row.2.is_finite()) {
        return Err(PyValueError::new_err("Reservation overflow"));
    }
    Ok(plan)
}

#[pyfunction]
pub fn event_sell_plan(
    allocations: Vec<SellAllocation>,
    mut trades: Vec<(f64, f64)>,
    filled: f64,
    price: f64,
    fee_delta: f64,
) -> PyResult<SellPlan> {
    if !filled.is_finite()
        || filled <= 0.0
        || !price.is_finite()
        || !fee_delta.is_finite()
        || trades
            .iter()
            .any(|row| !row.0.is_finite() || !row.1.is_finite())
        || allocations.iter().any(|row| {
            row.0 >= trades.len()
                || [
                    row.1, row.2, row.3, row.4, row.5, row.6, row.7, row.8, row.9,
                ]
                .iter()
                .any(|value| !value.is_finite())
        })
    {
        return Err(PyValueError::new_err("Invalid sell plan input"));
    }
    let mut remaining = filled;
    let mut cost = 0.0;
    let mut gain = 0.0;
    let mut fills = Vec::new();
    for (index, row) in allocations.iter().enumerate() {
        if remaining <= 0.0 {
            break;
        }
        let (
            trade,
            amount,
            pending,
            open,
            close,
            buy_fee,
            sell_fee,
            contribution,
            entry_fee,
            entry_filled,
        ) = *row;
        let portion = pending.min(remaining);
        remaining -= portion;
        if portion <= 0.0 {
            continue;
        }
        let (entry, exit, realized, profit) = event_exit_values(
            false,
            open,
            price,
            portion,
            entry_fee,
            entry_filled,
            fee_delta,
            filled,
        )?;
        let previous_filled = amount - pending;
        let next_close = (close * previous_filled + price * portion) / (previous_filled + portion);
        let next_buy_fee = buy_fee + entry;
        let next_sell_fee = sell_fee + exit;
        let next_contribution = contribution + profit;
        trades[trade].0 += profit;
        trades[trade].1 = trades[trade].1 + entry + exit;
        cost += realized;
        gain += profit;
        if [
            next_close,
            next_buy_fee,
            next_sell_fee,
            next_contribution,
            trades[trade].0,
            trades[trade].1,
            cost,
            gain,
        ]
        .iter()
        .any(|value| !value.is_finite())
        {
            return Err(PyValueError::new_err("Sell settlement overflow"));
        }
        fills.push((
            index,
            pending - portion,
            next_close,
            next_buy_fee,
            next_sell_fee,
            next_contribution,
            trades[trade].0,
            trades[trade].1,
        ));
    }
    Ok((fills, cost, gain))
}

#[test]
fn sell_plan_accumulates_repeated_trade_allocations() {
    let (fills, cost, gain) = event_sell_plan(
        vec![
            (0, 1.0, 1.0, 100.0, 0.0, 0.0, 0.0, 0.0, 4.0, 2.0),
            (0, 1.0, 1.0, 100.0, 0.0, 0.0, 0.0, 0.0, 4.0, 2.0),
        ],
        vec![(3.0, 1.0)],
        1.5,
        120.0,
        1.5,
    )
    .unwrap();
    assert_eq!(fills[0], (0, 0.0, 120.0, 2.0, 1.0, 17.0, 20.0, 4.0));
    assert_eq!(fills[1], (1, 0.5, 120.0, 1.0, 0.5, 8.5, 28.5, 5.5));
    assert_eq!((cost, gain), (150.0, 25.5));
}

#[pyfunction]
pub fn event_exit_aggregates(
    short: bool,
    basis: f64,
    portfolio: (f64, f64, f64),
    realized: (f64, f64),
    fill: (f64, f64),
) -> PyResult<(f64, f64, f64, f64)> {
    let (cost, gain) = realized;
    let (amount, price) = fill;
    let next_basis = if short {
        (basis - cost).max(0.0)
    } else {
        basis - cost
    };
    let next_gain = portfolio.0 + gain;
    let next_size = portfolio.1 + gain;
    let next_revenue = portfolio.2 + if short { cost } else { amount * price };
    if [
        basis,
        portfolio.0,
        portfolio.1,
        portfolio.2,
        cost,
        gain,
        amount,
        price,
        next_basis,
        next_gain,
        next_size,
        next_revenue,
    ]
    .iter()
    .any(|value| !value.is_finite())
    {
        return Err(PyValueError::new_err("Invalid exit aggregates"));
    }
    Ok((next_basis, next_gain, next_size, next_revenue))
}

#[pyfunction]
pub fn event_cover_plan(
    trades: Vec<CoverTrade>,
    requested: Vec<usize>,
    filled: f64,
    price: f64,
    fee_delta: f64,
) -> PyResult<CoverPlan> {
    if !filled.is_finite()
        || filled <= 0.0
        || !price.is_finite()
        || !fee_delta.is_finite()
        || requested.iter().any(|index| *index >= trades.len())
        || trades.iter().any(|row| {
            [row.0, row.1, row.2, row.3, row.4, row.5]
                .iter()
                .any(|value| !value.is_finite())
        })
    {
        return Err(PyValueError::new_err("Invalid cover plan input"));
    }
    let mut selected = vec![false; trades.len()];
    for index in &requested {
        selected[*index] = true;
    }
    let order = requested.into_iter().chain(
        selected
            .iter()
            .enumerate()
            .filter_map(|(index, selected)| (!selected).then_some(index)),
    );
    let mut remaining = filled;
    let mut cost = 0.0;
    let mut gain = 0.0;
    let mut fills = Vec::new();
    for index in order {
        if remaining <= 0.0 {
            break;
        }
        let (available, open, previous_gain, previous_fees, entry_fee, entry_filled) =
            trades[index];
        if available <= 0.0 {
            continue;
        }
        let portion = available.min(remaining);
        let (buy_fee, sell_fee, realized_cost, contribution) = event_exit_values(
            true,
            open,
            price,
            portion,
            entry_fee,
            entry_filled,
            fee_delta,
            filled,
        )?;
        let next_available = available - portion;
        let next_gain = previous_gain + contribution;
        let next_fees = previous_fees + buy_fee + sell_fee;
        cost += realized_cost;
        gain += contribution;
        remaining -= portion;
        if [next_available, next_gain, next_fees, cost, gain, remaining]
            .iter()
            .any(|value| !value.is_finite())
        {
            return Err(PyValueError::new_err("Cover settlement overflow"));
        }
        fills.push((
            index,
            portion,
            buy_fee,
            sell_fee,
            realized_cost,
            contribution,
            next_available,
            next_gain,
            next_fees,
        ));
    }
    Ok((fills, cost, gain))
}

#[test]
fn cover_plan_prioritizes_explicit_trades_then_consumes_fifo() {
    let (fills, cost, gain) = event_cover_plan(
        vec![
            (1.0, 100.0, 0.0, 0.0, 2.0, 1.0),
            (2.0, 120.0, 3.0, 1.0, 4.0, 2.0),
        ],
        vec![1],
        2.5,
        80.0,
        2.5,
    )
    .unwrap();
    assert_eq!(fills[0], (1, 2.0, 4.0, 2.0, 240.0, 74.0, 0.0, 77.0, 7.0));
    assert_eq!(fills[1], (0, 0.5, 1.0, 0.5, 50.0, 8.5, 0.5, 8.5, 1.5));
    assert_eq!((cost, gain), (290.0, 82.5));
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn event_exit_values(
    short: bool,
    open: f64,
    close: f64,
    amount: f64,
    entry_fee: f64,
    entry_filled: f64,
    fee_delta: f64,
    fill_amount: f64,
) -> PyResult<(f64, f64, f64, f64)> {
    let buy_fee = if entry_fee != 0.0 && entry_filled != 0.0 {
        entry_fee * (amount / entry_filled)
    } else {
        0.0
    };
    let sell_fee = fee_delta * (amount / fill_amount);
    let cost = open * amount;
    let gain = if short {
        (open - close) * amount
    } else {
        close * amount - cost
    } - buy_fee
        - sell_fee;
    if [buy_fee, sell_fee, cost, gain]
        .iter()
        .any(|value| !value.is_finite())
    {
        return Err(PyValueError::new_err("Invalid exit accounting"));
    }
    Ok((buy_fee, sell_fee, cost, gain))
}

#[pyfunction]
pub fn event_fee_correction(
    fee: f64,
    filled: f64,
    amount: f64,
    pending: f64,
    recorded: f64,
    gain: f64,
) -> PyResult<(f64, f64, f64)> {
    let executed = amount - pending;
    let corrected = fee
        * if filled != 0.0 {
            executed / filled
        } else {
            0.0
        };
    let delta = corrected - recorded;
    let next_gain = gain - delta;
    if [corrected, delta, next_gain]
        .iter()
        .any(|value| !value.is_finite())
    {
        return Err(PyValueError::new_err("Invalid fee correction"));
    }
    Ok((corrected, delta, next_gain))
}

#[pyfunction]
pub fn event_order_transition(
    operation: &str,
    side: &str,
    state: Vec<f64>,
    order: Vec<f64>,
    hedge: bool,
) -> PyResult<OrderUpdates> {
    if state.len() != 9
        || order.len() != 9
        || state.iter().chain(&order).any(|value| !value.is_finite())
        || !["BUY", "SELL", "SHORT", "COVER"].contains(&side)
    {
        return Err(PyValueError::new_err("Invalid event accounting input"));
    }
    let (cash, quote, total_cost, volume) = (state[0], state[1], state[2], state[3]);
    let (long, long_cost, short, amount) = (state[4], state[5], state[6], state[8]);
    let (
        size,
        filled,
        previous_filled,
        price,
        reservation,
        previous_size,
        fee,
        previous_fee,
        reserved_size,
    ) = (
        order[0], order[1], order[2], order[3], order[4], order[5], order[6], order[7], order[8],
    );
    let mut portfolio = Updates::new();
    let mut target = Updates::new();
    let mut currency = Updates::new();
    match operation {
        "fee" => {
            let delta = fee - previous_fee;
            if delta != 0.0 {
                put(&mut portfolio, "unallocated", cash - delta);
                put(&mut currency, "amount", quote - delta);
            }
        }
        "create" => {
            if side == "SELL" {
                put(
                    &mut target,
                    if hedge { "long_amount" } else { "amount" },
                    if hedge { long - size } else { amount - size },
                );
                if filled > 0.0 {
                    let gross = filled * price;
                    put(&mut portfolio, "unallocated", cash + gross);
                    put(&mut portfolio, "total_trade_volume", volume + gross);
                    put(&mut currency, "amount", quote + gross);
                }
            } else {
                put(&mut portfolio, "unallocated", cash - reserved_size);
                put(&mut currency, "amount", quote - reserved_size);
            }
        }
        "cancel" => {
            let remaining = size - filled;
            if side == "SELL" {
                put(
                    &mut target,
                    if hedge { "long_amount" } else { "amount" },
                    if hedge {
                        long + remaining
                    } else {
                        amount + remaining
                    },
                );
            } else {
                let refund = remaining * reservation;
                put(&mut portfolio, "unallocated", cash + refund);
                put(&mut currency, "amount", quote + refund);
            }
        }
        "fill" => {
            let difference = filled - previous_filled;
            if difference <= 0.0 {
                return Ok((portfolio, target, currency));
            }
            let gross = difference * price;
            let released = difference * reservation;
            let delta = match side {
                "SELL" => gross,
                "SHORT" => released + gross,
                _ => released - gross,
            };
            let mut next_cash = cash;
            let mut next_quote = quote;
            if side != "BUY" || delta != 0.0 {
                next_cash += delta;
                next_quote += delta;
            }
            if side != "SELL" && size != previous_size {
                let adjustment = (size - previous_size) * reservation;
                next_cash -= adjustment;
                next_quote -= adjustment;
            }
            if side != "BUY" || delta != 0.0 || size != previous_size {
                put(&mut portfolio, "unallocated", next_cash);
                put(&mut currency, "amount", next_quote);
            }
            put(&mut portfolio, "total_trade_volume", volume + gross);
            match side {
                "BUY" => {
                    put(&mut portfolio, "total_cost", total_cost + gross);
                    put(&mut target, "long_amount", long + difference);
                    put(&mut target, "long_cost", long_cost + gross);
                }
                "SHORT" => {
                    put(&mut target, "short_amount", short + difference);
                    put(&mut target, "short_cost", state[7] + gross);
                }
                "COVER" => put(&mut target, "short_amount", short - difference),
                "SELL" if size != previous_size => {
                    let adjustment = size - previous_size;
                    put(
                        &mut target,
                        if hedge { "long_amount" } else { "amount" },
                        if hedge {
                            long - adjustment
                        } else {
                            amount - adjustment
                        },
                    );
                }
                _ => {}
            }
        }
        _ => return Err(PyValueError::new_err("Unknown accounting transition")),
    }
    if portfolio
        .iter()
        .chain(&target)
        .chain(&currency)
        .any(|(_, value)| !value.is_finite())
    {
        return Err(PyValueError::new_err("Event accounting overflow"));
    }
    Ok((portfolio, target, currency))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn event_risk_transition(
    stop: bool,
    trailing: bool,
    short: bool,
    active: bool,
    sold: f64,
    amount: f64,
    open: f64,
    percentage: f64,
    current: f64,
    watermark: Option<f64>,
    threshold: Option<f64>,
    check: bool,
) -> PyResult<RiskUpdate> {
    if [sold, amount, open, percentage, current]
        .iter()
        .chain(watermark.iter())
        .chain(threshold.iter())
        .any(|value| !value.is_finite())
    {
        return Err(PyValueError::new_err("Risk inputs must be finite"));
    }
    if stop && (!active || sold == amount) {
        return Ok((false, watermark, threshold, false));
    }
    let favorable = |level| {
        if short {
            current < level
        } else {
            current > level
        }
    };
    let adverse = |level| {
        if short {
            current >= level
        } else {
            current <= level
        }
    };
    let pullback = |level| {
        if short {
            current > level
        } else {
            current < level
        }
    };
    let reached = |level| {
        if short {
            current <= level
        } else {
            current >= level
        }
    };
    let fraction = percentage / 100.0;
    let following = current
        * if short {
            1.0 + fraction
        } else {
            1.0 - fraction
        };
    let required = || threshold.ok_or_else(|| PyValueError::new_err("Missing risk threshold"));
    if stop {
        let level = required()?;
        let extreme = watermark.ok_or_else(|| PyValueError::new_err("Missing stop watermark"))?;
        if check && adverse(level) {
            return Ok((true, watermark, threshold, false));
        }
        if trailing && adverse(level) {
            return Ok((false, watermark, threshold, false));
        }
        if favorable(extreme) && (trailing || !check) {
            return Ok((
                false,
                Some(current),
                if trailing { Some(following) } else { threshold },
                trailing && !check,
            ));
        }
    } else if !trailing {
        let level = required()?;
        if check {
            return Ok((reached(level), watermark, threshold, false));
        }
        if reached(level) && watermark.map_or(true, favorable) {
            return Ok((false, Some(current), threshold, true));
        }
    } else if let Some(extreme) = watermark {
        let level = required()?;
        if check && pullback(level) {
            return Ok((true, watermark, threshold, false));
        }
        if favorable(extreme) {
            let improve = if short {
                following < level
            } else {
                following > level
            };
            return Ok((
                false,
                Some(current),
                if improve { Some(following) } else { threshold },
                !check,
            ));
        }
    } else {
        let initial = open
            * if short {
                1.0 - fraction
            } else {
                1.0 + fraction
            };
        if reached(initial) {
            return Ok((false, Some(current), Some(following), !check));
        }
    }
    Ok((false, watermark, threshold, false))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn partial_buy_fill_releases_reservation_at_actual_price() {
        let result = event_order_transition(
            "fill",
            "BUY",
            vec![600.0, 600.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            vec![4.0, 1.0, 0.0, 90.0, 100.0, 4.0, 0.0, 0.0, 400.0],
            false,
        )
        .unwrap();
        assert!(result.0.contains(&("unallocated".into(), 610.0)));
        assert!(result.1.contains(&("long_cost".into(), 90.0)));
    }

    #[test]
    fn trailing_take_profit_arms_before_testing_pullback() {
        let armed = event_risk_transition(
            false, true, false, true, 0.0, 1.0, 100.0, 5.0, 110.0, None, None, true,
        )
        .unwrap();
        assert_eq!(armed, (false, Some(110.0), Some(104.5), false));
        let triggered = event_risk_transition(
            false, true, false, true, 0.0, 1.0, 100.0, 5.0, 104.0, armed.1, armed.2, true,
        )
        .unwrap();
        assert!(triggered.0);
    }
}
