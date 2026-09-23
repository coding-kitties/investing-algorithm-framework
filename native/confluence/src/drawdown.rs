use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

type DrawdownResult = (Vec<f64>, f64, f64, i64, usize, usize);

fn calculate(values: &[f64], elapsed_us: &[i64]) -> DrawdownResult {
    let mut series = Vec::with_capacity(values.len());
    let mut positive_peak: Option<f64> = None;
    let mut peak = values.first().copied().unwrap_or(0.0);
    let mut minimum = 0.0_f64;
    let mut absolute = 0.0_f64;
    let mut start = None;
    let mut duration = 0;
    let mut peak_row = 0;
    let mut absolute_rows = (0, 0);
    for (row, (&value, &timestamp)) in values.iter().zip(elapsed_us).enumerate() {
        let drawdown = if value <= 0.0 {
            0.0
        } else {
            let high = positive_peak.unwrap_or(value).max(value);
            positive_peak = Some(high);
            (value - high) / high
        };
        series.push(drawdown);
        minimum = minimum.min(drawdown);
        if value < peak {
            start.get_or_insert(timestamp);
        } else {
            if let Some(begin) = start.take() {
                duration = duration.max((timestamp - begin) / 86_400_000_000);
            }
            if value > peak {
                peak_row = row;
            }
            peak = value;
        }
        if peak - value > absolute {
            absolute = peak - value;
            absolute_rows = (peak_row, row);
        }
    }
    if let (Some(begin), Some(last)) = (start, elapsed_us.last()) {
        duration = duration.max((last - begin) / 86_400_000_000);
    }
    (
        series,
        minimum.abs(),
        absolute.abs(),
        duration,
        absolute_rows.0,
        absolute_rows.1,
    )
}

#[pyfunction]
pub fn drawdown_metrics(
    py: Python<'_>,
    values: Vec<f64>,
    elapsed_us: Vec<i64>,
) -> PyResult<DrawdownResult> {
    if values.len() != elapsed_us.len()
        || values.iter().any(|value| !value.is_finite())
        || elapsed_us.first().is_some_and(|value| *value < 0)
        || elapsed_us.windows(2).any(|pair| pair[0] > pair[1])
    {
        return Err(PyValueError::new_err(
            "Expected finite equity and matching nonnegative ordered timestamps",
        ));
    }
    Ok(py.allow_threads(|| calculate(&values, &elapsed_us)))
}

#[pyfunction]
pub fn risk_metrics(
    py: Python<'_>,
    values: Vec<f64>,
    cash_flows: Vec<f64>,
    elapsed_us: Vec<i64>,
) -> PyResult<(DrawdownResult, Vec<f64>, DrawdownResult)> {
    if values.len() != elapsed_us.len()
        || values.len() != cash_flows.len()
        || values
            .iter()
            .chain(&cash_flows)
            .any(|value| !value.is_finite())
        || elapsed_us.first().is_some_and(|value| *value < 0)
        || elapsed_us.windows(2).any(|pair| pair[0] > pair[1])
    {
        return Err(PyValueError::new_err("Invalid risk metric inputs"));
    }
    py.allow_threads(|| {
        let mut growth = Vec::with_capacity(values.len());
        let mut equity = 1.0;
        for (row, value) in values.iter().enumerate() {
            if row > 0 && values[row - 1] > 0.0 {
                let change = (value - cash_flows[row]) / values[row - 1] - 1.0;
                equity *= 1.0 + change;
            }
            if !equity.is_finite() {
                return Err(PyValueError::new_err("Nonfinite TWR equity"));
            }
            growth.push(equity);
        }
        let raw = calculate(&values, &elapsed_us);
        let adjusted = calculate(&growth, &elapsed_us);
        Ok((raw, growth, adjusted))
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recovery_and_nonpositive_equity() {
        let day = 86_400_000_000;
        assert_eq!(
            calculate(
                &[100.0, 80.0, 0.0, -10.0, 100.0],
                &[0, day, 2 * day, 3 * day, 4 * day]
            ),
            (vec![0.0, -0.2, 0.0, 0.0, 0.0], 0.2, 110.0, 3, 0, 3)
        );
        assert_eq!(calculate(&[], &[]), (vec![], 0.0, 0.0, 0, 0, 0));
        assert_eq!(
            calculate(&[100.0, 50.0, 60.0], &[0, day, 3 * day]),
            (vec![0.0, -0.5, -0.4], 0.5, 50.0, 2, 0, 1)
        );
    }
}
