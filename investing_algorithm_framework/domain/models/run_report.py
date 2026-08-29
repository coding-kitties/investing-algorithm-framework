from investing_algorithm_framework.domain.models.base_model import BaseModel


class RunReport(BaseModel):
    """Snapshot of what a single ``App.run()`` invocation did.

    Built after a successful, bounded (``number_of_iterations``) run —
    the manual/stateless invocation path used by AWS Lambda, Azure
    Functions, and similar on-demand triggers — and persisted so it
    can be inspected after the (stateless) process has already exited.
    Intended to be returned directly as (or merged into) the response
    body of such a handler, so a caller can see what happened without
    inspecting logs or querying the database by hand.

    Attributes:
        id: Identifier assigned once the report is persisted. None
            for a report that has not been saved yet.
        algorithm_id: The id of the algorithm that produced this run,
            so reports from multiple bots sharing one database can be
            told apart.
        environment: The environment the run executed in (e.g.
            "prod", "test"), read from the app configuration.
        is_paper: True when every portfolio configured for this run is
            paper-traded, False otherwise (including mixed live/paper
            setups) — lets a caller avoid ever mistaking fake paper
            trades for real ones.
        number_of_iterations: The bounded iteration count passed to
            ``App.run()`` for this invocation.
        started_at: When this invocation began.
        completed_at: When this invocation finished successfully.
        orders: Orders created during this run, most-recent last. Each
            order dict already carries its own ``strategy_id``.
            Includes new orders, orders whose status changed this run
            (e.g. filled/canceled), and any order still pending at the
            venue regardless of when it was created — a still-open
            limit order keeps appearing in every report until it
            finally resolves.
        signals: Per-strategy, per-tick signal outcomes — every signal
            the strategy emitted this run, whether it turned into an
            order ("approved") or was dropped ("rejected", with the
            reason from the phase pipeline that dropped it). Each
            entry also carries a "score_cards" list of any
            ``ScoreCard``s recorded via
            ``TradingStrategy.record_score_card`` that tick,
            independent of whether a signal was actually emitted —
            useful for explaining why *no* signal fired.
        positions: All current positions across configured portfolios.
        portfolios: All current portfolios.
        trades: All current trades across configured portfolios. Each
            trade dict already carries its own ``strategy_id``.
        score_cards: Every ``ScoreCard`` recorded this run via
            ``TradingStrategy.record_score_card``, flattened across
            all strategies/ticks into one top-level list — one entry
            per symbol per run, each carrying its own ``strategy_id``,
            ``symbol``, ``summary``, and ``entries``. Present even for
            a tick where no signal/order was produced at all, so a
            caller can see *why* nothing happened.
    """

    def __init__(
        self,
        id=None,
        algorithm_id=None,
        environment=None,
        is_paper=None,
        number_of_iterations=None,
        started_at=None,
        completed_at=None,
        orders=None,
        signals=None,
        positions=None,
        portfolios=None,
        trades=None,
        score_cards=None,
    ):
        self.id = id
        self.algorithm_id = algorithm_id
        self.environment = environment
        self.is_paper = is_paper
        self.number_of_iterations = number_of_iterations
        self.started_at = started_at
        self.completed_at = completed_at
        self.orders = orders if orders is not None else []
        self.signals = signals if signals is not None else []
        self.positions = positions if positions is not None else []
        self.portfolios = portfolios if portfolios is not None else []
        self.trades = trades if trades is not None else []
        self.score_cards = score_cards if score_cards is not None else []

    def to_dict(self):
        def ensure_iso(value):
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return value

        return {
            "id": self.id,
            "algorithm_id": self.algorithm_id,
            "environment": self.environment,
            "is_paper": self.is_paper,
            "number_of_iterations": self.number_of_iterations,
            "started_at": ensure_iso(self.started_at),
            "completed_at": ensure_iso(self.completed_at),
            "orders": self.orders,
            "signals": self.signals,
            "positions": self.positions,
            "portfolios": self.portfolios,
            "trades": self.trades,
            "score_cards": self.score_cards,
        }

    @staticmethod
    def from_dict(data: dict):
        return RunReport(
            id=data.get("id"),
            algorithm_id=data.get("algorithm_id"),
            environment=data.get("environment"),
            is_paper=data.get("is_paper"),
            number_of_iterations=data.get("number_of_iterations"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            orders=data.get("orders"),
            signals=data.get("signals"),
            positions=data.get("positions"),
            portfolios=data.get("portfolios"),
            trades=data.get("trades"),
            score_cards=data.get("score_cards"),
        )

    def __repr__(self):
        return self.repr(
            id=self.id,
            algorithm_id=self.algorithm_id,
            completed_at=self.completed_at,
        )
