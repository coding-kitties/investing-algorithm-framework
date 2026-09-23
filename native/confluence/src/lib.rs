use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use serde_json::Value;

mod drawdown;
mod event;
mod event_accounting;
mod event_archive;
mod event_broker;
mod event_schedule;
mod netting;
mod vector_loop;

#[derive(Clone, Debug)]
enum Operand {
    Column(usize),
    Constant(f64),
}

impl Operand {
    fn get(&self, columns: &[Vec<f64>], row: usize) -> f64 {
        match self {
            Self::Column(index) => columns[*index][row],
            Self::Constant(value) => *value,
        }
    }
}

#[derive(Clone, Debug)]
enum Expression {
    Compare(String, Operand, Operand, Option<f64>),
    Not(Box<Expression>),
    Count(usize, Vec<Expression>),
}

impl Expression {
    fn evaluate(&self, columns: &[Vec<f64>], row: usize) -> (bool, bool) {
        match self {
            Self::Compare(operator, left, right, high) => {
                let lhs = left.get(columns, row);
                let rhs = right.get(columns, row);
                if lhs.is_nan() || rhs.is_nan() {
                    return (false, false);
                }
                let matched = match operator.as_str() {
                    "gt" => lhs > rhs,
                    "gte" => lhs >= rhs,
                    "lt" => lhs < rhs,
                    "lte" => lhs <= rhs,
                    "eq" => lhs == rhs,
                    "neq" => lhs != rhs,
                    "between" => lhs >= rhs && lhs <= high.unwrap(),
                    "cross_above" | "cross_below" => {
                        if row == 0 {
                            return (false, false);
                        }
                        let previous_left = left.get(columns, row - 1);
                        let previous_right = right.get(columns, row - 1);
                        if previous_left.is_nan() || previous_right.is_nan() {
                            return (false, false);
                        }
                        if operator == "cross_above" {
                            previous_left <= previous_right && lhs > rhs
                        } else {
                            previous_left >= previous_right && lhs < rhs
                        }
                    }
                    _ => unreachable!(),
                };
                (matched, true)
            }
            Self::Not(child) => {
                let (matched, available) = child.evaluate(columns, row);
                (!matched && available, available)
            }
            Self::Count(minimum, children) => {
                let mut matches = 0;
                let mut available = true;
                for child in children {
                    let (matched, child_available) = child.evaluate(columns, row);
                    matches += usize::from(matched);
                    available &= child_available;
                }
                (matches >= *minimum && available, available)
            }
        }
    }
}

fn text<'value>(value: &'value Value, key: &str) -> Result<&'value str, String> {
    value[key]
        .as_str()
        .ok_or_else(|| format!("Missing string: {key}"))
}

fn number(value: &Value) -> Result<f64, String> {
    value
        .as_f64()
        .filter(|number| number.is_finite())
        .ok_or_else(|| "Expected finite numeric constant".to_string())
}

fn column(names: &mut Vec<String>, name: String) -> Operand {
    let index = match names.iter().position(|existing| existing == &name) {
        Some(index) => index,
        None => {
            names.push(name);
            names.len() - 1
        }
    };
    Operand::Column(index)
}

fn expression(value: &Value, names: &mut Vec<String>, depth: usize) -> Result<Expression, String> {
    if depth > 64 {
        return Err("Expression nesting exceeds 64".into());
    }
    match text(value, "type")? {
        "condition" => {
            let key = |name: &str| match value["timeframe"].as_str() {
                Some(timeframe) if !timeframe.is_empty() => format!("{timeframe}:{name}"),
                _ => name.to_string(),
            };
            let left = column(names, key(text(value, "indicator")?));
            let operator = text(value, "operator")?;
            if ![
                "gt",
                "gte",
                "lt",
                "lte",
                "eq",
                "neq",
                "between",
                "cross_above",
                "cross_below",
            ]
            .contains(&operator)
            {
                return Err("Unsupported operator".into());
            }
            let (right, high) = if operator == "between" {
                let bounds = value["value"]
                    .as_array()
                    .filter(|bounds| bounds.len() == 2)
                    .ok_or("BETWEEN requires two bounds")?;
                (
                    Operand::Constant(number(&bounds[0])?),
                    Some(number(&bounds[1])?),
                )
            } else if let Some(reference) = value["reference"].as_str() {
                (column(names, key(reference)), None)
            } else {
                (Operand::Constant(number(&value["value"])?), None)
            };
            Ok(Expression::Compare(operator.to_string(), left, right, high))
        }
        "not" => Ok(Expression::Not(Box::new(expression(
            &value["expression"],
            names,
            depth + 1,
        )?))),
        kind @ ("all_of" | "any_of" | "at_least") => {
            let children = value["expressions"]
                .as_array()
                .ok_or("Missing expressions")?
                .iter()
                .map(|child| expression(child, names, depth + 1))
                .collect::<Result<Vec<_>, _>>()?;
            let minimum = match kind {
                "all_of" => children.len(),
                "any_of" => 1,
                _ => value["minimum"].as_u64().ok_or("Invalid minimum")? as usize,
            };
            if minimum == 0 || minimum > children.len() {
                return Err("Invalid expression count".into());
            }
            Ok(Expression::Count(minimum, children))
        }
        _ => Err("Unsupported expression".into()),
    }
}

struct Rule {
    expression: Expression,
    points: f64,
}
struct Group {
    rules: Vec<Rule>,
    minimum_matches: usize,
    minimum_score: Option<f64>,
}

fn rules(value: &Value, names: &mut Vec<String>) -> Result<Vec<Rule>, String> {
    value
        .as_array()
        .ok_or("Missing rules")?
        .iter()
        .map(|rule| {
            Ok(Rule {
                expression: expression(&rule["expression"], names, 0)?,
                points: number(&rule["points"])?,
            })
        })
        .collect()
}

fn group(value: &Value, names: &mut Vec<String>) -> Result<Group, String> {
    Ok(Group {
        rules: rules(&value["rules"], names)?,
        minimum_matches: value["minimum_matches"].as_u64().ok_or("Invalid matches")? as usize,
        minimum_score: if value["minimum_score"].is_null() {
            None
        } else {
            Some(number(&value["minimum_score"])?)
        },
    })
}

#[pyclass(frozen)]
struct CompiledCard {
    columns: Vec<String>,
    primary: Option<Expression>,
    groups: Vec<Group>,
    scoring: Vec<Rule>,
    requirements: Vec<Expression>,
    vetoes: Vec<Expression>,
    minimum_score: f64,
}

impl CompiledCard {
    fn compile(definition: &str) -> Result<Self, String> {
        let value: Value = serde_json::from_str(definition).map_err(|error| error.to_string())?;
        if value["confluence_card_version"].as_u64() != Some(1) {
            return Err("Unsupported card version".into());
        }
        let mut columns = Vec::new();
        let mut groups = Vec::new();
        let primary = if value["primary"].get("expression").is_some() {
            Some(expression(
                &value["primary"]["expression"],
                &mut columns,
                0,
            )?)
        } else {
            groups.push(group(&value["primary"], &mut columns)?);
            None
        };
        for secondary in value["secondary"]
            .as_array()
            .ok_or("Missing secondary groups")?
        {
            groups.push(group(secondary, &mut columns)?);
        }
        let scoring = rules(&value["scoring"], &mut columns)?;
        let mut expressions = |key: &str| -> Result<Vec<Expression>, String> {
            value[key]
                .as_array()
                .ok_or("Missing expressions")?
                .iter()
                .map(|item| expression(&item["expression"], &mut columns, 0))
                .collect()
        };
        let requirements = expressions("requirements")?;
        let vetoes = expressions("vetoes")?;
        Ok(Self {
            columns,
            primary,
            groups,
            scoring,
            requirements,
            vetoes,
            minimum_score: number(&value["minimum_score"])?,
        })
    }

    fn run(&self, columns: &[Vec<f64>], rows: usize) -> (Vec<u8>, Vec<u8>, Vec<u8>) {
        let mut scores = Vec::with_capacity(rows * 8);
        let mut availability = Vec::with_capacity(rows);
        let mut qualification = Vec::with_capacity(rows);
        for row in 0..rows {
            let mut available = true;
            let mut qualified = true;
            let mut score = 0.0;
            let mut evaluate = |expression: &Expression| {
                let (matched, present) = expression.evaluate(columns, row);
                available &= present;
                matched
            };
            if let Some(primary) = &self.primary {
                qualified &= evaluate(primary);
            }
            for group in &self.groups {
                let mut subtotal = 0.0;
                let mut matches = 0;
                for rule in &group.rules {
                    let matched = evaluate(&rule.expression);
                    matches += usize::from(matched);
                    subtotal += f64::from(u8::from(matched)) * rule.points;
                }
                score += subtotal;
                qualified &= matches >= group.minimum_matches
                    && group
                        .minimum_score
                        .map_or(true, |minimum| subtotal >= minimum);
            }
            for rule in &self.scoring {
                score += f64::from(u8::from(evaluate(&rule.expression))) * rule.points;
            }
            for requirement in &self.requirements {
                qualified &= evaluate(requirement);
            }
            for veto in &self.vetoes {
                qualified &= !evaluate(veto);
            }
            qualified &= score >= self.minimum_score && available;
            scores.extend_from_slice(&(if available { score } else { f64::NAN }).to_le_bytes());
            availability.push(u8::from(available));
            qualification.push(u8::from(qualified));
        }
        (scores, availability, qualification)
    }
}

#[pymethods]
impl CompiledCard {
    #[new]
    fn new(definition: &str) -> PyResult<Self> {
        Self::compile(definition).map_err(PyValueError::new_err)
    }

    fn column_names(&self) -> Vec<String> {
        self.columns.clone()
    }

    fn evaluate<'py>(
        &self,
        py: Python<'py>,
        columns: Vec<Bound<'py, PyBytes>>,
        rows: usize,
    ) -> PyResult<(
        Bound<'py, PyBytes>,
        Bound<'py, PyBytes>,
        Bound<'py, PyBytes>,
    )> {
        let size = rows
            .checked_mul(8)
            .ok_or_else(|| PyValueError::new_err("Row count overflow"))?;
        if columns.len() != self.columns.len()
            || columns.iter().any(|data| data.as_bytes().len() != size)
        {
            return Err(PyValueError::new_err("Column shape mismatch"));
        }
        let owned = columns
            .iter()
            .map(|data| {
                data.as_bytes()
                    .chunks_exact(8)
                    .map(|bytes| f64::from_le_bytes(bytes.try_into().unwrap()))
                    .collect()
            })
            .collect::<Vec<Vec<f64>>>();
        let (scores, available, qualified) = py.allow_threads(|| self.run(&owned, rows));
        Ok((
            PyBytes::new(py, &scores),
            PyBytes::new(py, &available),
            PyBytes::new(py, &qualified),
        ))
    }
}

#[pymodule]
fn iaf_confluence_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("EVENT_ACCOUNTING_SEMANTICS_VERSION", "event-accounting-v1")?;
    module.add("EVENT_SETTLEMENT_SEMANTICS_VERSION", "event-settlement-v1")?;
    module.add("EVENT_LIFECYCLE_SEMANTICS_VERSION", "event-lifecycle-v1")?;
    module.add("EVENT_ARCHIVE_SEMANTICS_VERSION", "event-archive-v2")?;
    module.add_function(wrap_pyfunction!(
        event_schedule::evaluate_event_market,
        module
    )?)?;
    module.add_class::<event_archive::EventArchiveIndex>()?;
    module.add_class::<event_archive::EventArchiveCursor>()?;
    module.add_function(wrap_pyfunction!(
        event_accounting::event_reservation_plan,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        event_schedule::run_event_iteration,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(event_accounting::event_sell_plan, module)?)?;
    module.add_function(wrap_pyfunction!(
        event_accounting::event_cover_plan,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        event_accounting::event_exit_aggregates,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        event_accounting::event_exit_values,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        event_accounting::event_fee_correction,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        event_accounting::event_order_transition,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        event_accounting::event_risk_transition,
        module
    )?)?;
    module.add_class::<event_broker::EventBroker>()?;
    module.add_class::<event_broker::BrokerOrder>()?;
    module.add_class::<event_broker::BrokerPosition>()?;
    module.add_class::<event_broker::BrokerTrade>()?;
    module.add_class::<event_broker::BrokerAllocation>()?;
    module.add("SEMANTICS_VERSION", "confluence-vector-v1")?;
    module.add_class::<CompiledCard>()?;
    module.add("EXECUTION_SEMANTICS_VERSION", "static-netting-v1")?;
    module.add("NETTING_SEMANTICS_VERSION", "netting-accounting-v5")?;
    module.add("DRAWDOWN_SEMANTICS_VERSION", "drawdown-v1")?;
    module.add("EVENT_FILL_SEMANTICS_VERSION", "event-fill-v1")?;
    module.add("EVENT_SCHEDULE_SEMANTICS_VERSION", "event-schedule-v1")?;
    module.add_function(wrap_pyfunction!(
        event_schedule::run_event_schedule,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(event::event_fill_decision, module)?)?;
    module.add_function(wrap_pyfunction!(drawdown::drawdown_metrics, module)?)?;
    module.add_function(wrap_pyfunction!(drawdown::risk_metrics, module)?)?;
    module.add_class::<netting::Execution>()?;
    module.add_class::<netting::NettingResult>()?;
    module.add_function(wrap_pyfunction!(netting::run_netting, module)?)?;
    module.add_function(wrap_pyfunction!(vector_loop::run_static_netting, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crossing_uses_previous_row_and_propagates_nan() {
        let expression = Expression::Compare(
            "cross_above".into(),
            Operand::Column(0),
            Operand::Constant(2.0),
            None,
        );
        let columns = vec![vec![2.0, 3.0, f64::NAN, 4.0]];
        assert_eq!(expression.evaluate(&columns, 0), (false, false));
        assert_eq!(expression.evaluate(&columns, 1), (true, true));
        assert_eq!(expression.evaluate(&columns, 2), (false, false));
        assert_eq!(expression.evaluate(&columns, 3), (false, false));
    }

    #[test]
    fn any_of_does_not_hide_unavailable_child() {
        let expression = Expression::Count(
            1,
            vec![
                Expression::Compare(
                    "gt".into(),
                    Operand::Column(0),
                    Operand::Constant(0.0),
                    None,
                ),
                Expression::Compare(
                    "gt".into(),
                    Operand::Column(1),
                    Operand::Constant(0.0),
                    None,
                ),
            ],
        );
        assert_eq!(
            expression.evaluate(&[vec![1.0], vec![f64::NAN]], 0),
            (false, false)
        );
    }
}
