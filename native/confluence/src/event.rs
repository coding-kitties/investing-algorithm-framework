use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

type FillDecision = (Option<usize>, Option<usize>, bool);

#[allow(clippy::too_many_arguments)]
fn select_fill(
    times: &[i64],
    lows: &[f64],
    highs: &[f64],
    updated: i64,
    kind: u8,
    buy: bool,
    price: f64,
    stop: Option<f64>,
    triggered: bool,
) -> FillDecision {
    let eligible = |row: usize| times[row] >= updated;
    if kind == 0 {
        return (None, (0..times.len()).find(|&row| eligible(row)), true);
    }
    let trigger = if kind >= 2 && !triggered {
        let Some(threshold) = stop else {
            return (None, None, false);
        };
        let found = (0..times.len()).find(|&row| {
            eligible(row)
                && if buy {
                    highs[row] >= threshold
                } else {
                    lows[row] <= threshold
                }
        });
        let Some(row) = found else {
            return (None, None, false);
        };
        if kind == 2 {
            return (Some(row), Some(row), true);
        }
        Some(row)
    } else {
        None
    };
    let fill = (0..times.len()).find(|&row| {
        eligible(row)
            && trigger.map_or(true, |trigger_row| times[row] >= times[trigger_row])
            && if buy {
                lows[row] <= price
            } else {
                highs[row] >= price
            }
    });
    (trigger, fill, false)
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub fn event_fill_decision(
    py: Python<'_>,
    times: Vec<i64>,
    lows: Vec<f64>,
    highs: Vec<f64>,
    updated: i64,
    kind: u8,
    buy: bool,
    price: f64,
    stop: Option<f64>,
    triggered: bool,
) -> PyResult<FillDecision> {
    if times.len() != lows.len()
        || times.len() != highs.len()
        || kind > 3
        || !price.is_finite()
        || stop.is_some_and(|value| !value.is_finite())
        || lows.iter().chain(&highs).any(|value| !value.is_finite())
    {
        return Err(PyValueError::new_err("Invalid event fill inputs"));
    }
    Ok(py.allow_threads(|| {
        select_fill(
            &times, &lows, &highs, updated, kind, buy, price, stop, triggered,
        )
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stop_limit_search_starts_at_trigger_timestamp() {
        assert_eq!(
            select_fill(
                &[0, 1, 2],
                &[8.0, 11.0, 9.0],
                &[9.0, 12.0, 11.0],
                0,
                3,
                true,
                10.0,
                Some(12.0),
                false
            ),
            (Some(1), Some(2), false)
        );
        assert_eq!(
            select_fill(
                &[0, 1],
                &[8.0, 11.0],
                &[9.0, 12.0],
                0,
                3,
                true,
                10.0,
                Some(12.0),
                false
            ),
            (Some(1), None, false)
        );
    }

    #[test]
    fn preserves_input_order_and_inclusive_update_boundary() {
        assert_eq!(
            select_fill(
                &[2, 1],
                &[8.0, 8.0],
                &[12.0, 12.0],
                1,
                0,
                true,
                10.0,
                None,
                false
            ),
            (None, Some(0), true)
        );
        assert_eq!(
            select_fill(
                &[0, 1],
                &[8.0, 8.0],
                &[12.0, 12.0],
                1,
                2,
                false,
                10.0,
                Some(9.0),
                false
            ),
            (Some(1), Some(1), true)
        );
    }
}
