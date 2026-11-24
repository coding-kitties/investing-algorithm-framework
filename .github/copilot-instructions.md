# Repository guidance

Investing Algorithm Framework is a Python/Poetry framework for developing,
backtesting and deploying trading algorithms. Use
[pyproject.toml](../pyproject.toml) for the current package version, supported
Python versions and dependencies.

## Contribution workflow

- Branch from and target `dev` in `coding-kitties/investing-algorithm-framework`.
- Keep changes focused and follow existing patterns and public APIs.
- Add focused regression tests for changed behavior and update related docs.
- Record user-visible changes in [CHANGELOG.md](../CHANGELOG.md).
- See the [contributing guide](../docusaurus/docs/Contributing%20Guide/contributing.md)
  for the broader development and review process.

## Commands and validation

Run Python tests from the repository root so imports of `tests.resources` work.
Poetry includes the test dependency group, including pytest.

```bash
poetry install
poetry run flake8 ./investing_algorithm_framework
poetry run python -m unittest tests.services.test_order_backtest_service -v
poetry run coverage run -m unittest discover -s tests -v
```

Prefer the smallest relevant test selection. The
[test workflow](workflows/test.yml) defines CI installation and full-suite
commands; [.flake8](../.flake8) defines lint exclusions.

Documentation-only changes do not require application tests unless a relevant
documentation check exists. Validate changed links and commands as appropriate.
Report the checks actually run, any checks not run, and pre-existing failures
separately from failures introduced by the change.

## Architecture and behavior

- Start with the [architecture index](../docs/architecture/README.md), then read
  the relevant subsystem documentation and implementation. Some older docs still
  mention Flask or `.iafbt`; the current web layer uses FastAPI and bundles use
  `.obtf`.
- Keep dependencies directed inward toward the domain. Extend the public API
  through [package exports](../investing_algorithm_framework/__init__.py) and
  register injectable components in
  [dependency_container.py](../investing_algorithm_framework/dependency_container.py).
- Accounting, order and trade changes may affect both vector and event backtest
  engines. Check the [parity guidance](../docs/architecture/backtest/vector-vs-event-engine-parity.md)
  and relevant tests before declaring behavior preserved.
- Python is the default backend; Rust is optional. Follow the
  [native kernel guide](../native/confluence/README.md) and
  [native CI workflow](workflows/native.yml) for builds, semantic versions and
  Python/Rust parity checks. Do not assume native paths are faster.
- Use [TestBase](../tests/resources/test_base.py) and existing fixtures where
  appropriate. Test orders remain pending by default; use `auto_fill_orders`
  when a test requires immediate fills.
- Public docs live in `docusaurus/`; internal architecture and design references
  live in `docs/`. Follow the [release workflow](workflows/publish.yml) for tag
  and version rules.

## Metric conventions

- Return metrics and `win_rate` use decimal fractions: `0.10` means a 10% return
  and `0.60` means a 60% win rate. Verify units in the metric producer before
  converting for display; not every field named "percentage" uses fractions.
- Weight trade gain/loss averages by actual positive/negative trade counts.
  Breakeven trades are not losses. Ensure these counts are computed even when
  callers request only the corresponding averages.
