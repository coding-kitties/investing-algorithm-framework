// Keep these boundaries aligned with domain/utils/cash.py.
pub(crate) fn exceeds_cash(required: f64, available: f64) -> bool {
    let tolerance = 1e-8_f64.max(1e-9 * required.abs().max(available.abs()));
    required > available + tolerance
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn equal_thirds_fit_but_real_overspend_does_not() {
        let third = 1000.0 * ((100.0 / 3.0) / 100.0);
        assert!(third * 3.0 > 1000.0);
        assert!(!exceeds_cash(third * 3.0, 1000.0));
        assert!(exceeds_cash(1000.01, 1000.0));
    }
}
