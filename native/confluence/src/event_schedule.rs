use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

fn ordered(timestamps: &[i64]) -> bool {
    timestamps.windows(2).all(|pair| pair[0] < pair[1])
}

#[pyfunction]
pub fn evaluate_event_market(
    py: Python<'_>,
    adapter: Py<PyAny>,
    orders: Vec<Py<PyAny>>,
    data: Py<PyAny>,
) -> PyResult<()> {
    for order in orders {
        py.check_signals()?;
        let frame = data.call_method1(py, "get", (order.getattr(py, "symbol")?,))?;
        if !frame.is_none(py) && !frame.call_method0(py, "is_empty")?.extract::<bool>(py)? {
            adapter.call_method1(py, "_check_has_executed", (order, frame))?;
        }
    }
    let query = PyDict::new(py);
    query.set_item("status", "OPEN")?;
    let trades: Vec<Py<PyAny>> = adapter
        .getattr(py, "trade_service")?
        .call_method1(py, "get_all", (query,))?
        .extract(py)?;
    if trades.is_empty() {
        return Ok(());
    }
    for trade in trades {
        py.check_signals()?;
        let frame = data.call_method1(py, "get", (trade.getattr(py, "symbol")?,))?;
        if !frame.is_none(py) && !frame.call_method0(py, "is_empty")?.extract::<bool>(py)? {
            adapter.call_method1(py, "_mark_market_trade", (trade, frame))?;
        }
    }
    adapter.call_method0(py, "_check_take_profits")?;
    adapter.call_method0(py, "_check_stop_losses")?;
    Ok(())
}

#[pyfunction]
pub fn run_event_iteration(
    py: Python<'_>,
    adapter: Py<PyAny>,
    strategies: Vec<Py<PyAny>>,
    tasks: Vec<Py<PyAny>>,
    scheduled: Vec<Py<PyAny>>,
) -> PyResult<()> {
    let state = adapter.call_method1(py, "_prepare_iteration", (&strategies,))?;
    adapter.call_method1(py, "_evaluate_iteration", (&state,))?;
    for task in tasks {
        py.check_signals()?;
        adapter.call_method1(py, "_run_iteration_task", (task,))?;
    }
    if strategies.is_empty() {
        return Ok(());
    }
    for strategy in &strategies {
        py.check_signals()?;
        adapter.call_method1(py, "_run_iteration_strategy", (strategy, &state))?;
    }
    adapter.call_method1(
        py,
        "_log_next_algorithm_run",
        (state.bind(py).get_item("date")?,),
    )?;
    for entry in scheduled {
        py.check_signals()?;
        adapter.call_method1(py, "_run_iteration_scheduled", (entry, &state))?;
    }
    adapter.call_method1(py, "_finish_iteration", (&strategies, &state))?;
    Ok(())
}

#[pyfunction]
pub fn run_event_schedule(py: Python<'_>, timestamps: Vec<i64>, tick: Py<PyAny>) -> PyResult<()> {
    if !ordered(&timestamps) {
        return Err(PyValueError::new_err(
            "Event timestamps must be strictly increasing",
        ));
    }
    if !tick.bind(py).is_callable() {
        return Err(PyValueError::new_err("Event tick must be callable"));
    }
    for (index, timestamp) in timestamps.into_iter().enumerate() {
        py.check_signals()?;
        tick.call1(py, (index, timestamp))?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn requires_strict_order_before_callbacks() {
        assert!(ordered(&[]));
        assert!(ordered(&[i64::MIN, 0, i64::MAX]));
        assert!(!ordered(&[1, 1]));
        assert!(!ordered(&[2, 1]));
    }
}
