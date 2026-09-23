use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

type Event = (usize, usize, u8, u8);

fn execute(
    prices: &[Vec<f64>],
    signals: &[Vec<u8>],
    capitals: &[f64],
    initial: f64,
    rows: usize,
) -> Vec<Event> {
    let mut positions = vec![0_u8; capitals.len()];
    let mut costs = vec![0.0; capitals.len()];
    let mut allocated = 0.0;
    let mut events = Vec::new();
    for row in 0..rows {
        for symbol in 0..capitals.len() {
            let mask = signals[symbol][row];
            let mut buy = mask & 1 != 0;
            let sell = mask & 2 != 0;
            let mut short = mask & 4 != 0;
            let cover = mask & 8 != 0;
            if sell {
                if positions[symbol] == 1 {
                    allocated -= costs[symbol];
                    positions[symbol] = 0;
                    events.push((row, symbol, 1, 0));
                    buy = false;
                } else if positions[symbol] == 0 {
                    events.push((row, symbol, 1, 1));
                }
            }
            if cover {
                if positions[symbol] == 2 {
                    allocated -= costs[symbol];
                    positions[symbol] = 0;
                    events.push((row, symbol, 3, 0));
                    buy = false;
                    short = false;
                } else {
                    events.push((row, symbol, 3, 2));
                }
            }
            if buy {
                let reason = match positions[symbol] {
                    1 => 4,
                    2 => 5,
                    _ => {
                        let capital = capitals[symbol] * 100.0 / 100.0;
                        if capital <= 0.0 || allocated + capital > initial {
                            3
                        } else {
                            allocated += capital;
                            costs[symbol] = capital;
                            positions[symbol] = 1;
                            0
                        }
                    }
                };
                events.push((row, symbol, 0, reason));
            }
            if short {
                let reason = if positions[symbol] != 0 {
                    4
                } else {
                    let capital = capitals[symbol] * 100.0 / 100.0;
                    if capital <= 0.0 || allocated + capital > initial {
                        3
                    } else {
                        allocated += capital;
                        costs[symbol] = (capital / prices[symbol][row]) * prices[symbol][row];
                        positions[symbol] = 2;
                        0
                    }
                };
                events.push((row, symbol, 2, reason));
            }
        }
    }
    events
}

#[pyfunction]
pub fn run_static_netting(
    py: Python<'_>,
    prices: Vec<Bound<'_, PyBytes>>,
    signals: Vec<Bound<'_, PyBytes>>,
    capitals: Vec<f64>,
    initial: f64,
    rows: usize,
) -> PyResult<Vec<Event>> {
    let size = rows
        .checked_mul(8)
        .ok_or_else(|| PyValueError::new_err("Row overflow"))?;
    if !initial.is_finite()
        || initial < 0.0
        || capitals.iter().any(|capital| {
            !capital.is_finite() || *capital < 0.0 || !(*capital * 100.0).is_finite()
        })
        || prices.len() != capitals.len()
        || signals.len() != capitals.len()
        || prices.iter().any(|column| column.as_bytes().len() != size)
        || signals.iter().any(|column| column.as_bytes().len() != rows)
    {
        return Err(PyValueError::new_err("Invalid static netting inputs"));
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
    for symbol in 0..capitals.len() {
        let capital = capitals[symbol] * 100.0 / 100.0;
        if prices[symbol].iter().any(|price| {
            !price.is_finite()
                || *price <= 0.0
                || !(capital / price).is_finite()
                || (capital > 0.0 && capital / price == 0.0)
        }) || signals[symbol]
            .iter()
            .any(|mask| mask & !15 != 0 || mask & 5 == 5)
        {
            return Err(PyValueError::new_err(
                "Unsupported price or simultaneous entries",
            ));
        }
    }
    Ok(py.allow_threads(|| execute(&prices, &signals, &capitals, initial, rows)))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exits_precede_entries_and_capacity_is_shared() {
        let events = execute(
            &[vec![100.; 4], vec![100.; 4]],
            &[vec![1, 3, 4, 8], vec![1, 1, 2, 4]],
            &[60., 60.],
            100.,
            4,
        );
        assert_eq!(
            events,
            vec![
                (0, 0, 0, 0),
                (0, 1, 0, 3),
                (1, 0, 1, 0),
                (1, 1, 0, 0),
                (2, 0, 2, 3),
                (2, 1, 1, 0),
                (3, 0, 3, 2),
                (3, 1, 2, 0)
            ]
        );
    }

    #[test]
    fn cover_suppresses_reentry_and_open_positions_remain() {
        assert_eq!(
            execute(&[vec![10.; 3]], &[vec![4, 12, 1]], &[50.], 100., 3),
            vec![(0, 0, 2, 0), (1, 0, 3, 0), (2, 0, 0, 0)]
        );
    }
}
