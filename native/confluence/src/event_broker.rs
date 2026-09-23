use std::collections::BTreeMap;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[pyclass(frozen, get_all)]
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerOrder {
    pub id: u64,
    pub symbol: String,
    pub side: u8,
    pub amount: f64,
    pub filled: f64,
    pub reservation_price: f64,
    pub reserved_cash: f64,
    pub reserved_units: f64,
    pub fees: f64,
    pub status: String,
}

#[pyclass(frozen, get_all)]
#[derive(Clone, Debug, Default, PartialEq)]
pub struct BrokerPosition {
    pub amount: f64,
    pub cost: f64,
    pub reserved_units: f64,
    pub realized_gain: f64,
    pub long_amount: f64,
    pub short_amount: f64,
    pub long_cost: f64,
    pub short_cost: f64,
    pub reserved_long: f64,
    pub reserved_short: f64,
}

#[derive(Clone, Debug, PartialEq)]
struct Lot {
    order_id: u64,
    symbol: String,
    side: u8,
    amount: f64,
    remaining: f64,
    reserved: f64,
    price: f64,
}

#[derive(Clone, Debug, PartialEq)]
struct Allocation {
    lot_index: usize,
    amount: f64,
    pending: f64,
    close_value: f64,
    entry_fee: f64,
    exit_fee: f64,
}

#[pyclass(frozen, get_all)]
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerTrade {
    pub id: u64,
    pub order_id: u64,
    pub symbol: String,
    pub side: u8,
    pub amount: f64,
    pub available_amount: f64,
    pub pending_amount: f64,
    pub open_price: f64,
    pub close_price: Option<f64>,
    pub net_gain: f64,
    pub total_fees: f64,
    pub status: String,
}

#[pyclass(frozen, get_all)]
#[derive(Clone, Debug, PartialEq)]
pub struct BrokerAllocation {
    pub trade_id: u64,
    pub order_id: u64,
    pub amount: f64,
    pub amount_pending: f64,
    pub open_price: f64,
    pub close_price: Option<f64>,
    pub buy_fee: f64,
    pub sell_fee: f64,
    pub net_gain_contribution: f64,
}

struct FeeUpdate {
    exit_id: u64,
    allocation_index: usize,
    opening: bool,
    fee: f64,
}

#[pyclass]
#[derive(Clone, Debug, PartialEq)]
pub struct EventBroker {
    cash: f64,
    hedge: bool,
    deposits: f64,
    fees: f64,
    orders: BTreeMap<u64, BrokerOrder>,
    positions: BTreeMap<String, BrokerPosition>,
    lots: Vec<Lot>,
    allocations: BTreeMap<u64, Vec<Allocation>>,
    next_id: u64,
}

fn invalid(message: &str) -> PyErr {
    PyValueError::new_err(message.to_owned())
}

fn positive(value: f64) -> bool {
    value.is_finite() && value > 0.0
}

impl EventBroker {
    fn allocation_view(&self, order_id: u64, allocation: &Allocation) -> BrokerAllocation {
        let lot = &self.lots[allocation.lot_index];
        let executed = allocation.amount - allocation.pending;
        let entry_value = executed * lot.price;
        let gross_gain = if lot.side == 0 {
            allocation.close_value - entry_value
        } else {
            entry_value - allocation.close_value
        };
        BrokerAllocation {
            trade_id: allocation.lot_index as u64 + 1,
            order_id,
            amount: allocation.amount,
            amount_pending: allocation.pending,
            open_price: lot.price,
            close_price: (executed > 0.0).then(|| allocation.close_value / executed),
            buy_fee: allocation.entry_fee,
            sell_fee: allocation.exit_fee,
            net_gain_contribution: gross_gain - allocation.entry_fee - allocation.exit_fee,
        }
    }

    fn prepare_fee_updates(
        &self,
        order: &BrokerOrder,
        position: &mut BrokerPosition,
        changed_allocations: Option<&[Allocation]>,
    ) -> PyResult<Vec<FeeUpdate>> {
        let mut updates = Vec::new();
        for (exit_id, stored_allocations) in &self.allocations {
            let allocations = if *exit_id == order.id {
                changed_allocations.unwrap_or(stored_allocations)
            } else {
                stored_allocations
            };
            for (allocation_index, allocation) in allocations.iter().enumerate() {
                let lot = &self.lots[allocation.lot_index];
                let opening = lot.order_id == order.id;
                if !opening && *exit_id != order.id {
                    continue;
                }
                let executed = allocation.amount - allocation.pending;
                let fee = if order.filled > 0.0 {
                    order.fees * (executed / order.filled)
                } else {
                    0.0
                };
                let stored = if opening {
                    allocation.entry_fee
                } else {
                    allocation.exit_fee
                };
                let difference = fee - stored;
                position.realized_gain -= difference;
                if !fee.is_finite() || !position.realized_gain.is_finite() {
                    return Err(invalid("Fee accounting overflow"));
                }
                if fee != stored {
                    updates.push(FeeUpdate {
                        exit_id: *exit_id,
                        allocation_index,
                        opening,
                        fee,
                    });
                }
            }
        }
        Ok(updates)
    }

    fn apply_fee_updates(&mut self, updates: Vec<FeeUpdate>) {
        for update in updates {
            let allocation =
                &mut self.allocations.get_mut(&update.exit_id).unwrap()[update.allocation_index];
            if update.opening {
                allocation.entry_fee = update.fee;
            } else {
                allocation.exit_fee = update.fee;
            }
        }
    }
}

#[pymethods]
impl EventBroker {
    #[staticmethod]
    #[allow(clippy::too_many_arguments)]
    fn settle_allocation(
        amount: f64,
        pending: f64,
        open_price: f64,
        close_price: f64,
        buy_fee: f64,
        sell_fee: f64,
        net_gain: f64,
        fill_amount: f64,
        fill_price: f64,
        entry_fee: f64,
        exit_fee: f64,
    ) -> PyResult<(f64, f64, f64, f64, f64, f64, f64)> {
        let executed = amount - pending;
        let cost = open_price * fill_amount;
        let gain = fill_price * fill_amount - cost - entry_fee - exit_fee;
        let close = (close_price * executed + fill_price * fill_amount) / (executed + fill_amount);
        let result = (
            pending - fill_amount,
            close,
            buy_fee + entry_fee,
            sell_fee + exit_fee,
            net_gain + gain,
            cost,
            gain,
        );
        if !positive(fill_amount)
            || fill_amount > pending
            || [result.0, result.1, result.2, result.3, result.4, cost, gain]
                .iter()
                .any(|value| !value.is_finite())
        {
            return Err(invalid("Invalid allocation settlement"));
        }
        Ok(result)
    }

    #[new]
    #[pyo3(signature = (cash, hedge=false))]
    fn new(cash: f64, hedge: bool) -> PyResult<Self> {
        if !cash.is_finite() || cash < 0.0 {
            return Err(invalid("Initial cash must be finite and nonnegative"));
        }
        Ok(Self {
            cash,
            hedge,
            deposits: 0.0,
            fees: 0.0,
            orders: BTreeMap::new(),
            positions: BTreeMap::new(),
            lots: Vec::new(),
            allocations: BTreeMap::new(),
            next_id: 1,
        })
    }

    #[getter]
    fn cash(&self) -> f64 {
        self.cash
    }

    #[getter]
    fn deposits(&self) -> f64 {
        self.deposits
    }

    #[getter]
    fn fees(&self) -> f64 {
        self.fees
    }

    fn position(&self, symbol: &str) -> BrokerPosition {
        self.positions.get(symbol).cloned().unwrap_or_default()
    }

    fn order(&self, id: u64) -> PyResult<BrokerOrder> {
        self.orders
            .get(&id)
            .cloned()
            .ok_or_else(|| invalid("Unknown order"))
    }

    fn open_orders(&self) -> Vec<BrokerOrder> {
        self.orders
            .values()
            .filter(|order| order.status == "OPEN")
            .cloned()
            .collect()
    }

    fn trade(&self, id: u64) -> PyResult<BrokerTrade> {
        let index = id
            .checked_sub(1)
            .and_then(|value| usize::try_from(value).ok());
        let index = index
            .filter(|value| *value < self.lots.len())
            .ok_or_else(|| invalid("Unknown trade"))?;
        let lot = &self.lots[index];
        let mut net_gain = 0.0;
        let mut total_fees = 0.0;
        let mut close_value = 0.0;
        let mut closed_amount = 0.0;
        for (order_id, allocations) in &self.allocations {
            for allocation in allocations.iter().filter(|item| item.lot_index == index) {
                let view = self.allocation_view(*order_id, allocation);
                net_gain += view.net_gain_contribution;
                total_fees += view.buy_fee + view.sell_fee;
                close_value += allocation.close_value;
                closed_amount += allocation.amount - allocation.pending;
            }
        }
        Ok(BrokerTrade {
            id,
            order_id: lot.order_id,
            symbol: lot.symbol.clone(),
            side: lot.side,
            amount: lot.amount,
            available_amount: lot.remaining - lot.reserved,
            pending_amount: lot.reserved,
            open_price: lot.price,
            close_price: (closed_amount > 0.0).then(|| close_value / closed_amount),
            net_gain,
            total_fees,
            status: if lot.remaining == 0.0 {
                "CLOSED"
            } else {
                "OPEN"
            }
            .to_owned(),
        })
    }

    fn order_allocations(&self, id: u64) -> PyResult<Vec<BrokerAllocation>> {
        let allocations = self
            .allocations
            .get(&id)
            .ok_or_else(|| invalid("Unknown order"))?;
        Ok(allocations
            .iter()
            .map(|item| self.allocation_view(id, item))
            .collect())
    }

    #[getter]
    fn number_of_trades(&self) -> usize {
        self.lots.len()
    }

    fn deposit(&mut self, amount: f64) -> PyResult<()> {
        if !positive(amount)
            || !(self.cash + amount).is_finite()
            || !(self.deposits + amount).is_finite()
        {
            return Err(invalid("Deposit must be positive and finite"));
        }
        self.cash += amount;
        self.deposits += amount;
        Ok(())
    }

    fn update_fee(&mut self, id: u64, cumulative_fee: f64) -> PyResult<()> {
        let mut order = self.order(id)?;
        if !cumulative_fee.is_finite() || cumulative_fee < 0.0 {
            return Err(invalid("Fee must be finite and nonnegative"));
        }
        let difference = cumulative_fee - order.fees;
        let cash = self.cash - difference;
        let fees = self.fees + difference;
        if !cash.is_finite() || !fees.is_finite() {
            return Err(invalid("Fee accounting overflow"));
        }
        order.fees = cumulative_fee;
        let mut position = self.position(&order.symbol);
        let updates = self.prepare_fee_updates(&order, &mut position, None)?;
        self.cash = cash;
        self.fees = fees;
        self.positions.insert(order.symbol.clone(), position);
        self.orders.insert(id, order);
        self.apply_fee_updates(updates);
        Ok(())
    }

    fn submit(&mut self, symbol: String, side: u8, amount: f64, price: f64) -> PyResult<u64> {
        if symbol.is_empty()
            || side > 3
            || !positive(amount)
            || !positive(price)
            || !(amount * price).is_finite()
        {
            return Err(invalid("Invalid order"));
        }
        let mut position = self.position(&symbol);
        let cash = if side == 1 { 0.0 } else { amount * price };
        let units = if side == 1 || side == 3 { amount } else { 0.0 };
        if cash > self.cash {
            return Err(invalid("Insufficient cash"));
        }
        let available = if side == 3 {
            position.short_amount - position.reserved_short
        } else {
            position.long_amount - position.reserved_long
        };
        if units > 0.0 && units > available {
            return Err(invalid("Insufficient position"));
        }
        if !self.hedge
            && ((side == 0 && position.short_amount > position.reserved_short)
                || (side == 2 && position.long_amount > position.reserved_long))
        {
            return Err(invalid("Close the opposite position first"));
        }
        if !self.hedge
            && self.orders.values().any(|order| {
                order.symbol == symbol
                    && order.status == "OPEN"
                    && ((side == 0 && order.side == 2) || (side == 2 && order.side == 0))
            })
        {
            return Err(invalid("Opposing pending entries are unsupported"));
        }
        let id = self.next_id;
        let next_id = id
            .checked_add(1)
            .ok_or_else(|| invalid("Order ID exhausted"))?;
        let order = BrokerOrder {
            id,
            symbol: symbol.clone(),
            side,
            amount,
            filled: 0.0,
            reservation_price: price,
            reserved_cash: cash,
            reserved_units: units,
            fees: 0.0,
            status: "OPEN".to_owned(),
        };
        let mut allocations = Vec::new();
        let mut remaining = units;
        for (lot_index, lot) in self.lots.iter().enumerate() {
            if remaining <= 0.0 {
                break;
            }
            if lot.symbol != symbol || lot.side != if side == 1 { 0 } else { 2 } {
                continue;
            }
            let portion = remaining.min(lot.remaining - lot.reserved);
            if portion > 0.0 {
                allocations.push(Allocation {
                    lot_index,
                    amount: portion,
                    pending: portion,
                    close_value: 0.0,
                    entry_fee: 0.0,
                    exit_fee: 0.0,
                });
                remaining -= portion;
            }
        }
        if remaining > 0.0 {
            return Err(invalid("Insufficient unreserved lots"));
        }
        position.reserved_units += units;
        if side == 1 {
            position.reserved_long += units;
        } else if side == 3 {
            position.reserved_short += units;
        }
        if !position.reserved_units.is_finite() {
            return Err(invalid("Reservation overflow"));
        }
        for allocation in &allocations {
            self.lots[allocation.lot_index].reserved += allocation.pending;
        }
        self.allocations.insert(id, allocations);
        self.cash -= cash;
        self.positions.insert(symbol, position);
        self.orders.insert(id, order);
        self.next_id = next_id;
        Ok(id)
    }

    fn cancel(&mut self, id: u64) -> PyResult<()> {
        let mut order = self.order(id)?;
        if order.status != "OPEN" {
            return Err(invalid("Order is not open"));
        }
        let mut position = self.position(&order.symbol);
        let cash = self.cash + order.reserved_cash;
        if !cash.is_finite() {
            return Err(invalid("Cash overflow"));
        }
        position.reserved_units -= order.reserved_units;
        if order.side == 1 {
            position.reserved_long -= order.reserved_units;
        } else if order.side == 3 {
            position.reserved_short -= order.reserved_units;
        }
        order.reserved_cash = 0.0;
        order.reserved_units = 0.0;
        order.status = "CANCELED".to_owned();
        for allocation in self.allocations.get_mut(&id).unwrap() {
            self.lots[allocation.lot_index].reserved -= allocation.pending;
            allocation.amount -= allocation.pending;
            allocation.pending = 0.0;
        }
        self.cash = cash;
        self.positions.insert(order.symbol.clone(), position);
        self.orders.insert(id, order);
        Ok(())
    }

    fn fill(&mut self, id: u64, amount: f64, price: f64, fee: f64) -> PyResult<()> {
        let mut order = self.order(id)?;
        if order.status != "OPEN"
            || !positive(amount)
            || !positive(price)
            || !fee.is_finite()
            || fee < 0.0
            || amount > order.amount - order.filled
        {
            return Err(invalid("Invalid fill"));
        }
        let mut position = self.position(&order.symbol);
        let mut changed_lots = Vec::new();
        let mut new_lot = None;
        let mut allocations = self.allocations.get(&id).unwrap().clone();
        let gross = amount * price;
        let finished = amount == order.amount - order.filled;
        let released = if finished {
            order.reserved_cash
        } else if order.side == 1 {
            0.0
        } else {
            amount * order.reservation_price
        };
        let cash = self.cash
            + released
            + if order.side == 1 || order.side == 2 {
                gross
            } else {
                -gross
            }
            - fee;
        if order.side == 0 || order.side == 2 {
            position.amount += if order.side == 0 { amount } else { -amount };
            position.cost += gross;
            if order.side == 0 {
                position.long_amount += amount;
                position.long_cost += gross;
            } else {
                position.short_amount += amount;
                position.short_cost += gross;
            }
            new_lot = Some(Lot {
                order_id: id,
                symbol: order.symbol.clone(),
                side: order.side,
                amount,
                remaining: amount,
                reserved: 0.0,
                price,
            });
        } else {
            let mut remaining = amount;
            let mut cost = 0.0;
            let mut entry_fees = 0.0;
            for allocation in &mut allocations {
                if remaining <= 0.0 {
                    break;
                }
                let portion = remaining.min(allocation.pending);
                if portion <= 0.0 {
                    continue;
                }
                let mut lot = self.lots[allocation.lot_index].clone();
                let entry = &self.orders[&lot.order_id];
                let entry_fee = entry.fees * (portion / entry.filled);
                allocation.entry_fee += entry_fee;
                allocation.exit_fee += fee * (portion / amount);
                allocation.pending -= portion;
                allocation.close_value += price * portion;
                if !allocation.close_value.is_finite() {
                    return Err(invalid("Allocation accounting overflow"));
                }
                lot.remaining -= portion;
                lot.reserved -= portion;
                cost += lot.price * portion;
                entry_fees += entry_fee;
                remaining -= portion;
                changed_lots.push((allocation.lot_index, lot));
            }
            if remaining > 0.0 {
                return Err(invalid("Fill exceeds allocated lots"));
            }
            position.realized_gain += if order.side == 1 {
                gross - cost
            } else {
                cost - gross
            } - entry_fees
                - fee;
            position.cost -= cost;
            position.amount += if order.side == 1 { -amount } else { amount };
            position.reserved_units -= amount;
            order.reserved_units -= amount;
            if order.side == 1 {
                position.long_amount -= amount;
                position.long_cost -= cost;
                position.reserved_long -= amount;
            } else {
                position.short_amount -= amount;
                position.short_cost -= cost;
                position.reserved_short -= amount;
            }
        }
        order.reserved_cash -= released;
        order.filled += amount;
        order.fees += fee;
        if finished {
            order.status = "CLOSED".to_owned();
        }
        if [
            cash,
            gross,
            position.amount,
            position.cost,
            position.realized_gain,
            position.long_amount,
            position.short_amount,
            position.long_cost,
            position.short_cost,
            order.fees,
            self.fees + fee,
        ]
        .iter()
        .any(|value| !value.is_finite())
        {
            return Err(invalid("Nonfinite accounting result"));
        }
        let updates = self.prepare_fee_updates(&order, &mut position, Some(&allocations))?;
        self.cash = cash;
        self.fees += fee;
        for (lot_index, lot) in changed_lots {
            self.lots[lot_index] = lot;
        }
        if let Some(lot) = new_lot {
            self.lots.push(lot);
        }
        self.allocations.insert(id, allocations);
        self.positions.insert(order.symbol.clone(), position);
        self.orders.insert(id, order);
        self.apply_fee_updates(updates);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detached_allocation_transition_preserves_partial_fill_arithmetic() {
        let settled = EventBroker::settle_allocation(
            2.0, 1.0, 10.0, 12.0, 0.1, 0.2, 1.7, 0.5, 14.0, 0.05, 0.1,
        )
        .unwrap();
        assert_eq!(
            settled,
            (
                0.5,
                19.0 / 1.5,
                0.1 + 0.05,
                0.2 + 0.1,
                1.7 + (7.0 - 5.0 - 0.05 - 0.1),
                5.0,
                7.0 - 5.0 - 0.05 - 0.1
            )
        );
        assert!(EventBroker::settle_allocation(
            1.0, 0.5, 10.0, 12.0, 0.0, 0.0, 0.0, 1.0, 14.0, 0.0, 0.0,
        )
        .is_err());
    }

    #[test]
    fn hedge_exits_reserve_and_settle_only_their_own_leg() {
        let mut broker = EventBroker::new(1000.0, true).unwrap();
        let buy = broker.submit("BTC".into(), 0, 2.0, 100.0).unwrap();
        let short = broker.submit("BTC".into(), 2, 3.0, 100.0).unwrap();
        broker.fill(buy, 2.0, 100.0, 0.0).unwrap();
        broker.fill(short, 3.0, 100.0, 0.0).unwrap();
        let sell = broker.submit("BTC".into(), 1, 2.0, 120.0).unwrap();
        let cover = broker.submit("BTC".into(), 3, 3.0, 80.0).unwrap();
        assert_eq!(broker.position("BTC").reserved_long, 2.0);
        assert_eq!(broker.position("BTC").reserved_short, 3.0);
        assert!(broker.submit("BTC".into(), 1, 1.0, 120.0).is_err());
        assert!(broker.submit("BTC".into(), 3, 1.0, 80.0).is_err());
        broker.fill(sell, 1.0, 120.0, 1.0).unwrap();
        broker.cancel(sell).unwrap();
        assert_eq!(broker.position("BTC").short_amount, 3.0);
        assert_eq!(broker.position("BTC").short_cost, 300.0);
        broker.fill(cover, 3.0, 80.0, 1.0).unwrap();
        let position = broker.position("BTC");
        assert_eq!(position.long_amount, 1.0);
        assert_eq!(position.short_amount, 0.0);
        assert_eq!(position.cost, 100.0);
        assert_eq!(position.realized_gain, 78.0);
        assert_eq!(broker.trade(2).unwrap().net_gain, 59.0);
        assert_eq!(position.reserved_units, 0.0);
    }

    #[test]
    fn netting_flip_keeps_both_legs_until_reserved_exit_fills() {
        let mut broker = EventBroker::new(1000.0, false).unwrap();
        let short = broker.submit("BTC".into(), 2, 1.0, 100.0).unwrap();
        broker.fill(short, 1.0, 100.0, 0.0).unwrap();
        assert!(broker.submit("BTC".into(), 0, 1.0, 90.0).is_err());
        let cover = broker.submit("BTC".into(), 3, 1.0, 90.0).unwrap();
        let buy = broker.submit("BTC".into(), 0, 1.0, 90.0).unwrap();
        broker.fill(buy, 1.0, 90.0, 0.0).unwrap();
        assert_eq!(broker.position("BTC").long_amount, 1.0);
        assert_eq!(broker.position("BTC").short_amount, 1.0);
        broker.fill(cover, 1.0, 90.0, 0.0).unwrap();
        assert_eq!(broker.position("BTC").amount, 1.0);
        assert_eq!(broker.position("BTC").cost, 90.0);
        assert_eq!(broker.position("BTC").short_cost, 0.0);
    }

    #[test]
    fn detached_trade_reads_follow_partial_fills_cancellation_and_late_fees() {
        let mut broker = EventBroker::new(1000.0, false).unwrap();
        let buy = broker.submit("BTC".into(), 0, 2.0, 100.0).unwrap();
        broker.fill(buy, 1.0, 100.0, 1.0).unwrap();
        broker.fill(buy, 1.0, 110.0, 1.0).unwrap();
        assert_eq!(broker.number_of_trades(), 2);
        let before = broker.trade(1).unwrap();
        let sell = broker.submit("BTC".into(), 1, 1.5, 120.0).unwrap();
        assert_eq!(broker.trade(1).unwrap().pending_amount, 1.0);
        assert_eq!(broker.trade(1).unwrap().status, "OPEN");
        broker.fill(sell, 1.25, 120.0, 1.25).unwrap();
        broker.cancel(sell).unwrap();
        assert_eq!(before.available_amount, 1.0);
        assert_eq!(before.net_gain, 0.0);
        assert_eq!(broker.trade(1).unwrap().net_gain, 18.0);
        assert_eq!(broker.trade(1).unwrap().status, "CLOSED");
        assert_eq!(broker.trade(2).unwrap().available_amount, 0.75);
        assert_eq!(broker.trade(2).unwrap().pending_amount, 0.0);
        broker.update_fee(buy, 4.0).unwrap();
        assert_eq!(broker.trade(1).unwrap().net_gain, 17.0);
        assert_eq!(broker.trade(2).unwrap().net_gain, 1.75);
        let allocations = broker.order_allocations(sell).unwrap();
        assert_eq!(allocations[1].amount, 0.25);
        assert_eq!(allocations[1].amount_pending, 0.0);
        assert_eq!(allocations[1].close_price, Some(120.0));
        assert_eq!(allocations[1].net_gain_contribution, 1.75);
        assert!(broker.trade(0).is_err());
        assert!(broker.trade(u64::MAX).is_err());
        assert!(broker.order_allocations(u64::MAX).is_err());
    }

    #[test]
    fn mutations_preserve_unrelated_history_storage() {
        let mut broker = EventBroker::new(10000.0, false).unwrap();
        for _ in 0..100 {
            let buy = broker.submit("ADA".into(), 0, 1.0, 10.0).unwrap();
            broker.fill(buy, 1.0, 10.0, 0.0).unwrap();
            let sell = broker.submit("ADA".into(), 1, 1.0, 12.0).unwrap();
            broker.fill(sell, 1.0, 12.0, 0.0).unwrap();
        }
        let buy = broker.submit("BTC".into(), 0, 2.0, 100.0).unwrap();
        broker.fill(buy, 2.0, 100.0, 2.0).unwrap();
        let sell = broker.submit("BTC".into(), 1, 2.0, 120.0).unwrap();
        let lot_storage = broker.lots.as_ptr();
        let order_storage = &broker.orders[&1] as *const BrokerOrder;
        let allocation_storage = broker.allocations[&2].as_ptr();
        broker.fill(sell, 1.0, 120.0, 1.0).unwrap();
        broker.update_fee(buy, 4.0).unwrap();
        broker.fill(sell, 1.0, 120.0, 1.0).unwrap();
        assert_eq!(broker.lots.as_ptr(), lot_storage);
        assert_eq!(&broker.orders[&1] as *const BrokerOrder, order_storage);
        assert_eq!(broker.allocations[&2].as_ptr(), allocation_storage);
        assert_eq!(broker.position("BTC").realized_gain, 34.0);
        assert_eq!(broker.position("ADA").realized_gain, 200.0);
    }

    #[test]
    fn fee_reconciliation_overflow_is_atomic() {
        let mut broker = EventBroker::new(1000.0, false).unwrap();
        let buy = broker.submit("ADA".into(), 0, 2.0, 100.0).unwrap();
        broker.fill(buy, 2.0, 100.0, 0.0).unwrap();
        let sell = broker.submit("ADA".into(), 1, 2.0, 120.0).unwrap();
        broker.fill(sell, 2.0, 120.0, 0.0).unwrap();
        broker.positions.get_mut("ADA").unwrap().realized_gain = -f64::MAX;
        let before = broker.clone();
        assert!(broker.update_fee(buy, f64::MAX).is_err());
        assert_eq!(broker, before);
        let buy = broker.submit("BTC".into(), 0, 1.0, 100.0).unwrap();
        let before = broker.clone();
        assert!(broker.fill(buy, 1.0, f64::MAX, f64::MAX).is_err());
        assert_eq!(broker, before);
    }

    #[test]
    fn partial_fill_cancel_and_deposit() {
        let mut broker = EventBroker::new(1000.0, false).unwrap();
        let buy = broker.submit("BTC".into(), 0, 4.0, 100.0).unwrap();
        assert_eq!(broker.cash, 600.0);
        broker.fill(buy, 1.0, 90.0, 2.0).unwrap();
        assert_eq!(broker.cash, 608.0);
        assert_eq!(broker.order(buy).unwrap().reserved_cash, 300.0);
        broker.cancel(buy).unwrap();
        assert_eq!(broker.cash, 908.0);
        let sell = broker.submit("BTC".into(), 1, 1.0, 120.0).unwrap();
        broker.fill(sell, 0.5, 120.0, 1.0).unwrap();
        broker.cancel(sell).unwrap();
        assert_eq!(broker.position("BTC").amount, 0.5);
        assert_eq!(broker.position("BTC").cost, 45.0);
        assert_eq!(broker.position("BTC").realized_gain, 13.0);
        assert_eq!(broker.position("BTC").reserved_units, 0.0);
        broker.deposit(20.0).unwrap();
        assert_eq!(broker.cash, 987.0);
    }

    #[test]
    fn short_cover_and_rejections_are_atomic() {
        let mut broker = EventBroker::new(1000.0, false).unwrap();
        let short = broker.submit("BTC".into(), 2, 2.0, 100.0).unwrap();
        broker.fill(short, 2.0, 100.0, 1.0).unwrap();
        assert_eq!(broker.cash, 1199.0);
        let cover = broker.submit("BTC".into(), 3, 2.0, 80.0).unwrap();
        let before = broker.clone();
        assert!(broker.submit("BTC".into(), 3, 1.0, 80.0).is_err());
        assert!(broker.fill(cover, 3.0, 80.0, 0.0).is_err());
        assert!(broker.deposit(f64::NAN).is_err());
        assert_eq!(before, broker);
        broker.fill(cover, 2.0, 80.0, 1.0).unwrap();
        assert_eq!(broker.cash, 1038.0);
        assert_eq!(broker.position("BTC").realized_gain, 38.0);
        assert_eq!(broker.position("BTC").amount, 0.0);
    }

    #[test]
    fn short_entries_and_fifo_exit_fees() {
        let mut broker = EventBroker::new(1000.0, false).unwrap();
        for price in [100.0, 120.0] {
            let short = broker.submit("ADA".into(), 2, 1.0, price).unwrap();
            broker.fill(short, 1.0, price, 2.0).unwrap();
        }
        for (price, cost, gain, cash) in [(80.0, 120.0, 17.0, 1135.0), (90.0, 0.0, 44.0, 1044.0)] {
            let cover = broker.submit("ADA".into(), 3, 1.0, price).unwrap();
            broker.fill(cover, 1.0, price, 1.0).unwrap();
            assert_eq!(broker.position("ADA").cost, cost);
            assert_eq!(broker.position("ADA").realized_gain, gain);
            assert_eq!(broker.cash, cash);
        }
    }

    #[test]
    fn late_fees_reconcile_without_double_debit() {
        let mut broker = EventBroker::new(1000.0, false).unwrap();
        let buy = broker.submit("ADA".into(), 0, 2.0, 100.0).unwrap();
        broker.fill(buy, 2.0, 100.0, 2.0).unwrap();
        let sell = broker.submit("ADA".into(), 1, 2.0, 120.0).unwrap();
        broker.fill(sell, 2.0, 120.0, 2.0).unwrap();
        for _ in 0..2 {
            broker.update_fee(buy, 4.0).unwrap();
            broker.update_fee(sell, 4.0).unwrap();
        }
        assert_eq!(broker.cash, 1032.0);
        assert_eq!(broker.position("ADA").realized_gain, 32.0);
        let before = broker.clone();
        assert!(broker.update_fee(sell, f64::NAN).is_err());
        assert_eq!(broker, before);
    }
}
