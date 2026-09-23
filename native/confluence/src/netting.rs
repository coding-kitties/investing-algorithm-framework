use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

type Spec = (f64, Option<f64>, Option<f64>, f64, f64, f64);
type Cooldown = (Option<usize>, u8, u8, usize);
type Risk = (bool, f64);
type Controls = (Vec<Cooldown>, Vec<Vec<Risk>>);

#[pyclass(frozen, get_all)]
#[derive(Clone, Debug)]
pub struct Execution {
    row: usize,
    symbol: usize,
    side: u8,
    reason: u8,
    has_fill: bool,
    price: f64,
    amount: f64,
    cost: f64,
    fee: f64,
    total_fees: f64,
    net_gain: f64,
    slippage: f64,
}

impl Execution {
    fn outcome(row: usize, symbol: usize, side: u8, reason: u8) -> Self {
        Self {
            row,
            symbol,
            side,
            reason,
            has_fill: false,
            price: 0.0,
            amount: 0.0,
            cost: 0.0,
            fee: 0.0,
            total_fees: 0.0,
            net_gain: 0.0,
            slippage: 0.0,
        }
    }
}

#[derive(Clone, Default)]
struct Position {
    side: u8,
    open_price: f64,
    amount: f64,
    cost: f64,
    fees: f64,
}

struct ReplayTrade {
    symbol: usize,
    short: bool,
    opened: usize,
    closed: Option<usize>,
    amount: f64,
    cost: f64,
    gain: f64,
}

#[pyclass(frozen)]
pub struct NettingResult {
    #[pyo3(get)]
    events: Vec<Execution>,
    #[pyo3(get)]
    last_prices: Vec<Option<f64>>,
    #[pyo3(get)]
    cash_start_row: usize,
    snapshots: Vec<u8>,
    positions: Vec<u8>,
}

#[pymethods]
impl NettingResult {
    fn snapshot_bytes<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        PyBytes::new(py, &self.snapshots)
    }
    fn position_bytes<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        PyBytes::new(py, &self.positions)
    }
}

fn snapshots(
    events: Vec<Execution>,
    prices: &[Vec<f64>],
    rows: usize,
    initial: f64,
    deposits: &[(usize, f64)],
) -> NettingResult {
    let mut trades: Vec<ReplayTrade> = Vec::new();
    let mut current = vec![None; prices.len()];
    for event in &events {
        if !event.has_fill {
            continue;
        }
        if event.side == 0 || event.side == 2 {
            current[event.symbol] = Some(trades.len());
            trades.push(ReplayTrade {
                symbol: event.symbol,
                short: event.side == 2,
                opened: event.row,
                closed: None,
                amount: event.amount,
                cost: event.cost,
                gain: 0.0,
            });
        } else {
            let slot = current[event.symbol].take().unwrap();
            trades[slot].closed = Some(event.row);
            trades[slot].gain = event.net_gain;
        }
    }
    let mut lifecycle = vec![Vec::new(); rows];
    for (slot, trade) in trades.iter().enumerate() {
        lifecycle[trade.opened].push(slot);
        if let Some(closed) = trade.closed {
            if closed != trade.opened {
                lifecycle[closed].push(slot);
            }
        }
    }
    let mut result = NettingResult {
        events,
        last_prices: vec![None; trades.len()],
        cash_start_row: rows,
        snapshots: Vec::new(),
        positions: Vec::new(),
    };
    let mut open = Vec::new();
    let mut cash = initial;
    let mut realized = 0.0;
    let mut deposit = 0;
    current.fill(None);
    for (row, slots) in lifecycle.iter().enumerate() {
        let mut cash_flow = 0.0;
        while deposit < deposits.len() && deposits[deposit].0 <= row {
            result.cash_start_row = result.cash_start_row.min(row);
            cash += deposits[deposit].1;
            cash_flow += deposits[deposit].1;
            deposit += 1;
        }
        for slot in slots {
            result.cash_start_row = result.cash_start_row.min(row);
            let trade = &trades[*slot];
            if trade.opened == row {
                if trade.short {
                    cash += trade.cost;
                } else {
                    cash -= trade.cost;
                }
                open.push(*slot);
                current[trade.symbol] = Some(*slot);
            }
            if trade.closed == Some(row) {
                if trade.short {
                    cash -= trade.cost - trade.gain;
                } else {
                    cash += trade.cost + trade.gain;
                }
                realized += trade.gain;
                open.retain(|existing| existing != slot);
                current[trade.symbol] = None;
            }
        }
        let mut allocated = 0.0;
        for slot in &open {
            let trade = &trades[*slot];
            let price = prices[trade.symbol][row];
            result.last_prices[*slot] = Some(price);
            if trade.short {
                allocated -= trade.amount * price;
            } else {
                allocated += trade.amount * price;
            }
        }
        for value in [cash, cash + allocated, realized, cash_flow] {
            result.snapshots.extend_from_slice(&value.to_le_bytes());
        }
        for slot in &current {
            let values = if let Some(slot) = slot {
                let trade = &trades[*slot];
                if trade.short {
                    [
                        -trade.amount,
                        trade.cost,
                        0.0,
                        trade.amount,
                        0.0,
                        trade.cost,
                    ]
                } else {
                    [trade.amount, trade.cost, trade.amount, 0.0, trade.cost, 0.0]
                }
            } else {
                [0.0; 6]
            };
            for value in values {
                result.positions.extend_from_slice(&value.to_le_bytes());
            }
        }
    }
    result
}

struct Engine<'data> {
    specs: &'data [Spec],
    cooldowns: &'data [Cooldown],
    risks: &'data [Vec<Risk>],
    last_cooldown: Vec<Option<usize>>,
    dynamic: bool,
    flip: bool,
    initial: f64,
    cash: f64,
    allocated: f64,
    positions: Vec<Position>,
    values: Vec<(usize, f64)>,
    events: Vec<Execution>,
}

fn ordered_sum(values: &[(usize, f64)]) -> f64 {
    let mut high: f64 = 0.0;
    let mut low: f64 = 0.0;
    for (_, value) in values {
        let total = high + value;
        low += if high.abs() >= value.abs() {
            (high - total) + value
        } else {
            (value - total) + high
        };
        high = total;
    }
    if low != 0.0 && low.is_finite() {
        high + low
    } else {
        high
    }
}

impl Engine<'_> {
    fn risk_exit(&mut self, symbol: usize, price: f64, row: usize) {
        let position = &self.positions[symbol];
        if position.side == 0 {
            return;
        }
        let short = position.side == 2;
        let reason = self.risks[symbol]
            .iter()
            .find_map(|(take_profit, percentage)| {
                let upward = *take_profit != short;
                let threshold = position.open_price
                    * if upward {
                        1.0 + percentage / 100.0
                    } else {
                        1.0 - percentage / 100.0
                    };
                let triggered = if upward {
                    price >= threshold
                } else {
                    price <= threshold
                };
                triggered.then_some(if *take_profit { 8 } else { 9 })
            });
        if let Some(reason) = reason {
            self.exit(row, symbol, price, short);
            self.events.last_mut().unwrap().reason = reason;
            self.record(symbol, if short { 0 } else { 1 }, row);
        }
    }

    fn blocked(&self, symbol: usize, side: u8, row: usize) -> bool {
        self.cooldowns
            .iter()
            .zip(&self.last_cooldown)
            .any(|(rule, last)| {
                (rule.0.is_none() || rule.0 == Some(symbol))
                    && (rule.2 == 2 || rule.2 == side)
                    && last.is_some_and(|last| row - last < rule.3)
            })
    }

    fn record(&mut self, symbol: usize, side: u8, row: usize) {
        for (rule, last) in self.cooldowns.iter().zip(&mut self.last_cooldown) {
            if (rule.0.is_none() || rule.0 == Some(symbol)) && (rule.1 == 2 || rule.1 == side) {
                *last = Some(row);
            }
        }
    }

    fn capital(&self, symbol: usize) -> f64 {
        let spec = self.specs[symbol];
        let base = if self.dynamic {
            let value = self.cash + ordered_sum(&self.values);
            spec.1.unwrap_or_else(|| value * (spec.2.unwrap() / 100.0))
        } else {
            spec.0
        };
        let capital = base * 100.0 / 100.0;
        if self.dynamic {
            capital.min(self.cash)
        } else if self.allocated + capital > self.initial {
            0.0
        } else {
            capital
        }
    }

    fn entry(&mut self, row: usize, symbol: usize, price: f64, short: bool) {
        let side = if short { 2 } else { 0 };
        let current_side = self.positions[symbol].side;
        if current_side != 0 {
            let reason = if !short && current_side == 2 { 5 } else { 4 };
            self.events
                .push(Execution::outcome(row, symbol, side, reason));
            return;
        }
        let capital = self.capital(symbol);
        if capital <= 0.0 {
            self.events.push(Execution::outcome(row, symbol, side, 3));
            return;
        }
        let spec = self.specs[symbol];
        let fill = price
            * if short {
                1.0 - spec.5 / 100.0
            } else {
                1.0 + spec.5 / 100.0
            };
        let (amount, cost, fee) = if short {
            let amount = capital / fill;
            let gross = amount * fill;
            (amount, gross, gross * spec.3 / 100.0 + spec.4)
        } else {
            let fee = capital * spec.3 / 100.0 + spec.4;
            let net = capital - fee;
            (net / fill, net, fee)
        };
        if (short && (amount <= 0.0 || cost - fee <= 0.0)) || (!short && cost <= 0.0) {
            if !short {
                self.events.push(Execution::outcome(row, symbol, side, 0));
            }
            return;
        }
        self.positions[symbol] = Position {
            side: if short { 2 } else { 1 },
            open_price: fill,
            amount,
            cost,
            fees: fee,
        };
        if self.dynamic {
            self.cash += if short { cost - fee } else { -capital };
            self.values.push((symbol, if short { 0.0 } else { cost }));
        } else {
            self.allocated += capital;
        }
        self.events.push(Execution {
            row,
            symbol,
            side,
            reason: 0,
            has_fill: true,
            price: fill,
            amount,
            cost,
            fee,
            total_fees: fee,
            net_gain: 0.0,
            slippage: if short { price - fill } else { fill - price },
        });
    }

    fn exit(&mut self, row: usize, symbol: usize, price: f64, short: bool) {
        let position = &self.positions[symbol];
        let spec = self.specs[symbol];
        let fill = price
            * if short {
                1.0 + spec.5 / 100.0
            } else {
                1.0 - spec.5 / 100.0
            };
        let gross = fill * position.amount;
        let fee = gross * spec.3 / 100.0 + spec.4;
        let gain = if short {
            position.cost - gross - fee
        } else {
            gross - fee - position.cost
        };
        if self.dynamic {
            if short {
                self.cash -= gross + fee;
            } else {
                self.cash += position.cost + gain;
            }
            self.values.retain(|(slot, _)| *slot != symbol);
        } else {
            self.allocated -= position.cost;
        }
        self.events.push(Execution {
            row,
            symbol,
            side: if short { 3 } else { 1 },
            reason: 0,
            has_fill: true,
            price: fill,
            amount: position.amount,
            cost: position.cost,
            fee,
            total_fees: position.fees + fee,
            net_gain: gain,
            slippage: if short { fill - price } else { price - fill },
        });
        self.positions[symbol] = Position::default();
    }

    fn run(
        mut self,
        prices: &[Vec<f64>],
        signals: &[Vec<u8>],
        rows: usize,
        deposits: &[(usize, f64)],
    ) -> Result<Vec<Execution>, String> {
        let mut deposit = 0;
        for row in 0..rows {
            while deposit < deposits.len() && deposits[deposit].0 <= row {
                self.cash += deposits[deposit].1;
                deposit += 1;
            }
            for symbol in 0..self.specs.len() {
                let price = prices[symbol][row];
                self.risk_exit(symbol, price, row);
                let mask = signals[symbol][row];
                let mut buy = mask & 1 != 0;
                let mut short = mask & 4 != 0;
                let mut sell = mask & 2 != 0;
                let mut cover = mask & 8 != 0;
                let mut block_buy = self.blocked(symbol, 0, row);
                let mut block_sell = self.blocked(symbol, 1, row);
                if self.flip && short && self.positions[symbol].side == 1 && !block_sell {
                    self.exit(row, symbol, price, false);
                    self.events.last_mut().unwrap().reason = 6;
                    sell = false;
                } else if self.flip && buy && self.positions[symbol].side == 2 && !block_buy {
                    self.exit(row, symbol, price, true);
                    self.events.last_mut().unwrap().reason = 6;
                    cover = false;
                }
                if sell {
                    if self.positions[symbol].side == 1 && block_sell {
                        self.events.push(Execution::outcome(row, symbol, 1, 7));
                    } else if self.positions[symbol].side == 1 {
                        self.exit(row, symbol, price, false);
                        self.record(symbol, 1, row);
                        block_buy = self.blocked(symbol, 0, row);
                        block_sell = self.blocked(symbol, 1, row);
                        buy = false;
                    } else if self.positions[symbol].side == 0 {
                        self.events.push(Execution::outcome(row, symbol, 1, 1));
                    }
                }
                if cover {
                    if self.positions[symbol].side == 2 {
                        self.exit(row, symbol, price, true);
                        self.record(symbol, 0, row);
                        buy = false;
                        short = false;
                    } else {
                        self.events.push(Execution::outcome(row, symbol, 3, 2));
                    }
                }
                if buy {
                    if self.positions[symbol].side == 0 && block_buy {
                        self.events.push(Execution::outcome(row, symbol, 0, 7));
                    } else {
                        self.entry(row, symbol, price, false);
                        if self.events.last().is_some_and(|event| event.reason == 0) {
                            self.record(symbol, 0, row);
                        }
                    }
                }
                if short {
                    if self.positions[symbol].side == 0 && block_sell {
                        self.events.push(Execution::outcome(row, symbol, 2, 7));
                    } else {
                        let count = self.events.len();
                        self.entry(row, symbol, price, true);
                        if self.events.len() > count && self.events.last().unwrap().reason == 0 {
                            self.record(symbol, 1, row);
                        }
                    }
                }
            }
            if self.dynamic {
                for (symbol, value) in &mut self.values {
                    let position = &self.positions[*symbol];
                    let live = position.amount * prices[*symbol][row];
                    *value = if position.side == 2 {
                        position.cost - live
                    } else {
                        live
                    };
                }
            }
            if !self.cash.is_finite()
                || !self.allocated.is_finite()
                || self.values.iter().any(|(_, value)| !value.is_finite())
            {
                return Err("Nonfinite native portfolio state".into());
            }
        }
        if self.events.iter().any(|event| {
            [
                event.price,
                event.amount,
                event.cost,
                event.fee,
                event.total_fees,
                event.net_gain,
                event.slippage,
            ]
            .iter()
            .any(|value| !value.is_finite())
        }) {
            return Err("Nonfinite native execution result".into());
        }
        Ok(self.events)
    }
}

#[pyfunction]
pub fn run_netting(
    py: Python<'_>,
    prices: Vec<Bound<'_, PyBytes>>,
    signals: Vec<Bound<'_, PyBytes>>,
    specs: Vec<Spec>,
    settings: (usize, f64, bool, bool),
    deposits: Vec<(usize, f64)>,
    controls: Controls,
) -> PyResult<NettingResult> {
    let (rows, initial, dynamic, flip) = settings;
    let (cooldowns, risks) = controls;
    let size = rows
        .checked_mul(8)
        .ok_or_else(|| PyValueError::new_err("Row overflow"))?;
    if !initial.is_finite()
        || initial < 0.0
        || prices.len() != specs.len()
        || signals.len() != specs.len()
        || risks.len() != specs.len()
        || risks
            .iter()
            .flatten()
            .any(|(_, threshold)| !threshold.is_finite() || *threshold < 0.0)
        || prices.iter().any(|column| column.as_bytes().len() != size)
        || signals.iter().any(|column| column.as_bytes().len() != rows)
        || specs.iter().any(|spec| {
            [
                spec.0,
                spec.1.unwrap_or(0.0),
                spec.2.unwrap_or(0.0),
                spec.3,
                spec.4,
                spec.5,
            ]
            .iter()
            .any(|value| !value.is_finite() || *value < 0.0)
                || !(spec.0 * 100.0).is_finite()
                || spec.5 >= 100.0
                || (spec.1.is_none() && spec.2.is_none())
        })
        || deposits.iter().any(|(_, amount)| !amount.is_finite())
        || cooldowns
            .iter()
            .any(|rule| rule.0.is_some_and(|slot| slot >= specs.len()) || rule.1 > 2 || rule.2 > 2)
        || deposits.windows(2).any(|pair| pair[0].0 > pair[1].0)
    {
        return Err(PyValueError::new_err("Invalid native netting inputs"));
    }
    let prices: Vec<Vec<f64>> = prices
        .iter()
        .map(|column| {
            column
                .as_bytes()
                .chunks_exact(8)
                .map(|bytes| f64::from_le_bytes(bytes.try_into().unwrap()))
                .collect()
        })
        .collect();
    let signals: Vec<Vec<u8>> = signals
        .iter()
        .map(|column| column.as_bytes().to_vec())
        .collect();
    if prices
        .iter()
        .flatten()
        .any(|price| !price.is_finite() || *price <= 0.0)
        || signals
            .iter()
            .flatten()
            .any(|mask| mask & !15 != 0 || mask & 5 == 5)
    {
        return Err(PyValueError::new_err(
            "Unsupported price or simultaneous entries",
        ));
    }
    let engine = Engine {
        specs: &specs,
        dynamic,
        flip,
        initial,
        cash: initial,
        allocated: 0.0,
        cooldowns: &cooldowns,
        risks: &risks,
        last_cooldown: vec![None; cooldowns.len()],
        positions: vec![Position::default(); specs.len()],
        values: Vec::new(),
        events: Vec::new(),
    };
    py.allow_threads(|| {
        engine
            .run(&prices, &signals, rows, &deposits)
            .map(|events| snapshots(events, &prices, rows, initial, &deposits))
    })
    .map_err(PyValueError::new_err)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dynamic_fees_and_deposits_change_entry_capital() {
        let specs = [(100.0, None, Some(50.0), 1.0, 0.0, 0.0)];
        let engine = Engine {
            specs: &specs,
            dynamic: true,
            flip: false,
            initial: 200.0,
            cash: 200.0,
            cooldowns: &[],
            risks: &[vec![]],
            last_cooldown: vec![],
            allocated: 0.0,
            positions: vec![Position::default()],
            values: vec![],
            events: vec![],
        };
        let events = engine
            .run(
                &[vec![10.0, 20.0, 10.0]],
                &[vec![1, 2, 1]],
                3,
                &[(2, 100.0)],
            )
            .unwrap();
        assert_eq!(events[0].cost, 99.0);
        assert!((events[1].net_gain - 97.02).abs() < 1e-12);
        assert!((events[2].fee - 1.9801).abs() < 1e-12);
    }

    #[test]
    fn compensated_sum_matches_cancellation() {
        assert_eq!(ordered_sum(&[(0, 1e16), (1, 1.0), (2, -1e16)]), 1.0);
    }

    #[test]
    fn snapshot_replay_keeps_closed_trade_last_price() {
        let specs = [(50.0, Some(50.0), None, 0.0, 0.0, 0.0)];
        let engine = Engine {
            specs: &specs,
            dynamic: false,
            flip: false,
            initial: 100.0,
            cash: 100.0,
            cooldowns: &[],
            risks: &[vec![]],
            last_cooldown: vec![],
            allocated: 0.0,
            positions: vec![Position::default()],
            values: vec![],
            events: vec![],
        };
        let prices = [vec![10.0, 12.0, 14.0]];
        let events = engine.run(&prices, &[vec![1, 0, 2]], 3, &[]).unwrap();
        let result = snapshots(events, &prices, 3, 100.0, &[]);
        assert_eq!(result.last_prices, vec![Some(12.0)]);
        let values: Vec<f64> = result
            .snapshots
            .chunks_exact(8)
            .map(|bytes| f64::from_le_bytes(bytes.try_into().unwrap()))
            .collect();
        assert_eq!(
            values,
            vec![50.0, 100.0, 0.0, 0.0, 50.0, 110.0, 0.0, 0.0, 120.0, 120.0, 20.0, 0.0]
        );
    }
}
