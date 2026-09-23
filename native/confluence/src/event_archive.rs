use std::collections::VecDeque;
use std::sync::{Arc, Mutex, MutexGuard};

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use rusqlite::{params, params_from_iter, types::Value, Connection, OptionalExtension};

const FIELDS: [&str; 13] = [
    "status",
    "order_id",
    "trade_id",
    "position_id",
    "target_symbol",
    "trading_symbol",
    "strategy_id",
    "order_side",
    "order_type",
    "price",
    "amount",
    "external_id",
    "created_at",
];
type SharedConnection = Arc<Mutex<Option<Connection>>>;
type Location = (String, u64, u64);
const CURSOR_BATCH_SIZE: usize = 128;

fn failure(error: impl std::fmt::Display) -> PyErr {
    PyRuntimeError::new_err(error.to_string())
}

fn locked(connection: &SharedConnection) -> PyResult<MutexGuard<'_, Option<Connection>>> {
    let guard = connection.lock().map_err(failure)?;
    if guard.is_none() {
        return Err(PyRuntimeError::new_err("Event archive index is closed"));
    }
    Ok(guard)
}

fn values(encoded: &str) -> PyResult<Vec<Value>> {
    let fields: Vec<serde_json::Value> = serde_json::from_str(encoded).map_err(failure)?;
    fields
        .into_iter()
        .map(|value| match value {
            serde_json::Value::Null => Ok(Value::Null),
            serde_json::Value::Bool(value) => Ok(Value::Integer(i64::from(value))),
            serde_json::Value::String(value) => Ok(Value::Text(value)),
            serde_json::Value::Number(value) => {
                if let Some(integer) = value.as_i64() {
                    Ok(Value::Integer(integer))
                } else if let Some(real) = value.as_f64().filter(|real| real.is_finite()) {
                    Ok(Value::Real(real))
                } else {
                    Err(PyValueError::new_err("Invalid archive scalar"))
                }
            }
            _ => Err(PyValueError::new_err("Invalid archive scalar")),
        })
        .collect()
}

#[pyclass]
pub struct EventArchiveIndex {
    connection: SharedConnection,
    next_query: u64,
}

#[pymethods]
impl EventArchiveIndex {
    #[new]
    fn new() -> PyResult<Self> {
        let connection = Connection::open("").map_err(failure)?;
        connection
            .execute_batch(&format!(
                "PRAGMA cache_size=-64; PRAGMA mmap_size=0; PRAGMA temp_store=FILE;
                 PRAGMA temp.cache_size=-64;
             CREATE TABLE locations (sequence INTEGER PRIMARY KEY,
             identity TEXT UNIQUE, offset INTEGER, size INTEGER, {});
             CREATE INDEX by_status ON locations(status);
             CREATE INDEX by_order_id ON locations(order_id);
             CREATE INDEX by_trade_id ON locations(trade_id);
             CREATE INDEX by_position_id ON locations(position_id);
             CREATE INDEX by_created_at ON locations(created_at);",
                FIELDS.join(", ")
            ))
            .map_err(failure)?;
        Ok(Self {
            connection: Arc::new(Mutex::new(Some(connection))),
            next_query: 0,
        })
    }

    fn insert(&self, identity: &str) -> PyResult<()> {
        locked(&self.connection)?
            .as_ref()
            .unwrap()
            .execute(
                "INSERT OR IGNORE INTO locations(identity, offset, size) VALUES (?, 0, 0)",
                [identity],
            )
            .map_err(failure)?;
        Ok(())
    }

    fn location(&self, identity: &str) -> PyResult<Option<(u64, u64)>> {
        locked(&self.connection)?
            .as_ref()
            .unwrap()
            .query_row(
                "SELECT offset, size FROM locations WHERE identity=?",
                [identity],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()
            .map_err(failure)
    }

    fn write(&self, identity: &str, offset: u64, size: u64, encoded: Option<&str>) -> PyResult<()> {
        let guard = locked(&self.connection)?;
        let connection = guard.as_ref().unwrap();
        if let Some(encoded) = encoded {
            let mut parameters = values(encoded)?;
            if parameters.len() != FIELDS.len() {
                return Err(PyValueError::new_err("Invalid archive field count"));
            }
            parameters.push(Value::Text(identity.to_owned()));
            let assignments = FIELDS
                .iter()
                .map(|field| format!("{field}=?"))
                .collect::<Vec<_>>()
                .join(", ");
            connection
                .execute(
                    &format!("UPDATE locations SET {assignments} WHERE identity=?"),
                    params_from_iter(parameters),
                )
                .map_err(failure)?;
        }
        connection
            .execute(
                "UPDATE locations SET offset=?, size=? WHERE identity=?",
                params![offset, size, identity],
            )
            .map_err(failure)?;
        Ok(())
    }

    fn select(
        &mut self,
        fields: Vec<String>,
        encoded: &str,
        ordering: i8,
        all: bool,
    ) -> PyResult<EventArchiveCursor> {
        let parameters = values(encoded)?;
        if fields.len() != parameters.len()
            || fields.iter().any(|field| {
                field != "identity" && field != "created_at_gt" && !FIELDS.contains(&field.as_str())
            })
        {
            return Err(PyValueError::new_err("Invalid archive query fields"));
        }
        let mut clauses = vec![if all {
            "1=1".to_owned()
        } else {
            "size>0".to_owned()
        }];
        clauses.extend(fields.iter().map(|field| {
            if field == "created_at_gt" {
                "created_at>?".to_owned()
            } else {
                format!("{field}=?")
            }
        }));
        let order = match ordering {
            0 => "sequence",
            1 => "created_at ASC, target_symbol, trading_symbol, strategy_id, order_side, order_type, price, amount, length(identity), identity",
            -1 => "created_at DESC, target_symbol, trading_symbol, strategy_id, order_side, order_type, price, amount, length(identity), identity",
            _ => return Err(PyValueError::new_err("Invalid archive ordering")),
        };
        let guard = locked(&self.connection)?;
        let connection = guard.as_ref().unwrap();
        let query = format!(
            "SELECT identity, offset, size FROM locations WHERE {} ORDER BY {order}",
            clauses.join(" AND ")
        );
        let mut pending = VecDeque::new();
        {
            let mut statement = connection
                .prepare_cached(&format!("{query} LIMIT {}", CURSOR_BATCH_SIZE + 1))
                .map_err(failure)?;
            let mut rows = statement
                .query(params_from_iter(&parameters))
                .map_err(failure)?;
            while let Some(row) = rows.next().map_err(failure)? {
                pending.push_back((
                    row.get(0).map_err(failure)?,
                    row.get(1).map_err(failure)?,
                    row.get(2).map_err(failure)?,
                ));
            }
        }
        if pending.len() <= CURSOR_BATCH_SIZE {
            return Ok(EventArchiveCursor {
                connection: Arc::clone(&self.connection),
                table: None,
                next_row: 0,
                pending,
                closed: false,
            });
        }
        let table = format!("query_{}", self.next_query);
        self.next_query += 1;
        pending.pop_back();
        connection
            .execute(
                &format!(
                    "CREATE TEMP TABLE {table} AS {query} LIMIT -1 OFFSET {CURSOR_BATCH_SIZE}"
                ),
                params_from_iter(parameters),
            )
            .map_err(failure)?;
        Ok(EventArchiveCursor {
            connection: Arc::clone(&self.connection),
            table: Some(table),
            next_row: 0,
            pending,
            closed: false,
        })
    }

    fn close(&self) -> PyResult<()> {
        self.connection.lock().map_err(failure)?.take();
        Ok(())
    }
}

#[pyclass]
pub struct EventArchiveCursor {
    connection: SharedConnection,
    table: Option<String>,
    next_row: i64,
    pending: VecDeque<Location>,
    closed: bool,
}

#[pymethods]
impl EventArchiveCursor {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self) -> PyResult<Option<Location>> {
        if self.closed {
            return Ok(None);
        }
        if self.pending.is_empty() {
            let Some(table) = self.table.as_ref() else {
                self.close()?;
                return Ok(None);
            };
            let guard = locked(&self.connection)?;
            let mut statement = guard.as_ref().unwrap().prepare(&format!(
                "SELECT rowid, identity, offset, size FROM {table} WHERE rowid>? ORDER BY rowid LIMIT {CURSOR_BATCH_SIZE}"
            )).map_err(failure)?;
            let mut rows = statement.query([self.next_row]).map_err(failure)?;
            while let Some(row) = rows.next().map_err(failure)? {
                self.next_row = row.get(0).map_err(failure)?;
                self.pending.push_back((
                    row.get(1).map_err(failure)?,
                    row.get(2).map_err(failure)?,
                    row.get(3).map_err(failure)?,
                ));
            }
        }
        let result = self.pending.pop_front();
        if result.is_none() {
            self.close()?;
        }
        Ok(result)
    }

    fn close(&mut self) -> PyResult<()> {
        if !self.closed {
            if let Some(table) = self.table.as_ref() {
                if let Some(connection) = self.connection.lock().map_err(failure)?.as_ref() {
                    connection
                        .execute(&format!("DROP TABLE IF EXISTS {table}"), [])
                        .map_err(failure)?;
                }
            }
            self.pending.clear();
            self.closed = true;
        }
        Ok(())
    }
}

impl Drop for EventArchiveCursor {
    fn drop(&mut self) {
        let _ = self.close();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounded_queries_preserve_snapshot_and_spill_at_boundary() {
        for count in [0, 1, 127, 128, 129, 300] {
            let mut index = EventArchiveIndex::new().unwrap();
            for identity in 1..=count {
                index.insert(&identity.to_string()).unwrap();
                index
                    .write(&identity.to_string(), identity, 10, None)
                    .unwrap();
            }
            let mut cursor = index.select(vec![], "[]", 0, false).unwrap();
            assert_eq!(cursor.table.is_some(), count > CURSOR_BATCH_SIZE as u64);
            assert!(cursor.pending.len() <= CURSOR_BATCH_SIZE);
            index.write("1", 999, 20, None).unwrap();
            index.insert("new").unwrap();
            index.write("new", 1000, 10, None).unwrap();
            let mut identities = Vec::new();
            while let Some(row) = cursor.__next__().unwrap() {
                identities.push(row.clone());
                assert!(cursor.pending.len() < CURSOR_BATCH_SIZE);
            }
            assert_eq!(
                identities,
                (1..=count)
                    .map(|identity| (identity.to_string(), identity, 10))
                    .collect::<Vec<_>>()
            );
            assert!(cursor.__next__().unwrap().is_none());
            let guard = locked(&index.connection).unwrap();
            let tables: u64 = guard
                .as_ref()
                .unwrap()
                .query_row(
                    "SELECT COUNT(*) FROM sqlite_temp_master WHERE type='table'",
                    [],
                    |row| row.get(0),
                )
                .unwrap();
            assert_eq!(tables, 0);
        }
    }

    #[test]
    fn bounded_queries_reuse_statements_with_fresh_parameters() {
        let mut index = EventArchiveIndex::new().unwrap();
        for identity in ["3", "20", "1"] {
            index.insert(identity).unwrap();
            index.write(identity, 0, 10, None).unwrap();
        }
        for identity in ["20", "3", "missing", "1"] {
            let mut cursor = index
                .select(
                    vec!["identity".to_owned()],
                    &serde_json::to_string(&vec![identity]).unwrap(),
                    1,
                    false,
                )
                .unwrap();
            let expected = (identity != "missing").then(|| (identity.to_owned(), 0, 10));
            assert_eq!(cursor.__next__().unwrap(), expected);
            assert!(cursor.__next__().unwrap().is_none());
        }
        let mut ordered = index.select(vec![], "[]", -1, false).unwrap();
        for identity in ["1", "3", "20"] {
            assert_eq!(ordered.__next__().unwrap().unwrap().0, identity);
        }
        ordered.close().unwrap();
        assert!(ordered.__next__().unwrap().is_none());
    }
}
