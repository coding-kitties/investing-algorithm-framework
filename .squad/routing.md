# Routing Rules

## Domain Routing

| Domain | Primary | Fallback |
|--------|---------|----------|
| Architecture, scope, design decisions | Sully | — |
| Code review, PR review | Sully | Vasquez |
| Framework internals, services, models | Vasquez | Sully |
| Backtesting engine, data sources | Vasquez | Sully |
| Trading strategies, indicators | Vasquez | Sully |
| CLI commands | Vasquez | Sully |
| Infrastructure, deployment, Azure, AWS | Vasquez | Sully |
| Tests, test infrastructure, coverage | Hudson | Vasquez |
| Edge cases, regression tests | Hudson | Vasquez |
| Documentation, Docusaurus site | Burke | — |
| Examples, tutorials, blog posts | Burke | Vasquez |
| README, API docs | Burke | Vasquez |

## Signal Routing

| Signal | Route to |
|--------|----------|
| "Sully" mentioned | Sully |
| "Vasquez" mentioned | Vasquez |
| "Hudson" mentioned | Hudson |
| "Burke" mentioned | Burke |
| "team" or multi-domain | Fan-out to relevant agents |
| Bug fix request | Vasquez + Hudson |
| New feature | Sully (design) → Vasquez (implement) → Hudson (test) |
| Docs update | Burke |
| Refactor | Vasquez + Hudson |
| Test failure | Hudson → Vasquez |

