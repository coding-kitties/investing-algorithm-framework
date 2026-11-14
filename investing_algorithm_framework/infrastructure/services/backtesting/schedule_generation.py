from collections import defaultdict
from datetime import datetime
from typing import Dict, List


def generate_backtest_schedule(
    strategies,
    tasks,
    start_date: datetime,
    end_date: datetime
) -> Dict[datetime, Dict[str, List[str]]]:
    """
    Generates a dict-based schedule keyed by ``datetime``.

    Each entry contains:

    * ``strategy_ids``  — strategies that fire at this tick.
    * ``task_ids``      — tasks that fire at this tick.
    * ``scheduled_function_calls`` — list of
      ``(strategy_id, function_name)`` tuples for the
      v9.0 ``ScheduledFunction`` API.

    Shared by both :class:`BacktestService` (vector engine) and
    :class:`EventBacktestService` (event-driven engine) — the schedule
    dict shape and generation logic must stay identical between them,
    since both drive the same underlying event loop.

    Args:
        strategies: List of strategies to schedule.
        tasks: List of tasks to schedule.
        start_date: Start date of the backtest.
        end_date: End date of the backtest.

    Returns:
        Dict mapping datetime to strategy_ids, task_ids, and
        scheduled_function_calls due at that tick.
    """
    schedule = defaultdict(
        lambda: {
            "strategy_ids": set(),
            "task_ids": set(),
            "scheduled_function_calls": [],
        }
    )

    for strategy in strategies:
        sid = strategy.strategy_profile.strategy_id
        strat_schedule = strategy.strategy_profile.schedule
        for t in strat_schedule.iter_run_times(start_date, end_date):
            schedule[t]["strategy_ids"].add(sid)

        for sf in strategy.strategy_profile.scheduled_functions or []:
            for t in sf.schedule.iter_run_times(start_date, end_date):
                # Touch the bucket so it exists in the output, but
                # do not add to strategy_ids — the function fires
                # independently of the parent strategy tick.
                _ = schedule[t]
                schedule[t]["scheduled_function_calls"].append(
                    (sid, sf.func)
                )

    for task in tasks:
        for t in task.schedule.iter_run_times(start_date, end_date):
            schedule[t]["task_ids"].add(task.worker_id)

    return {
        ts: {
            "strategy_ids": sorted(data["strategy_ids"]),
            "task_ids": sorted(data["task_ids"]),
            "scheduled_function_calls": list(
                data["scheduled_function_calls"]
            ),
        }
        for ts, data in schedule.items()
    }
