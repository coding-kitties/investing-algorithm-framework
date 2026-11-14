"""Standalone scheduled `Task` — a building block independent of any
strategy or signal.

Tasks are useful for periodic work that isn't trading logic at all:
housekeeping, alerting, reporting, health checks. Register with
`app.add_task(...)`.
"""
from investing_algorithm_framework import Schedule, Task, TimeUnit


class PortfolioHeartbeatTask(Task):
    """Logs total portfolio value on its own schedule, independent of
    any strategy's tick."""
    schedule = Schedule.every(12, TimeUnit.HOUR)

    def run(self, context):
        print(f"[heartbeat] portfolio value: {context.get_portfolio_value():.2f}")
