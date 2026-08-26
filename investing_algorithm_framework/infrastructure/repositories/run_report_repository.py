from investing_algorithm_framework.domain import PAGE, PER_PAGE, \
    DEFAULT_PAGE_VALUE, DEFAULT_PER_PAGE_VALUE
from investing_algorithm_framework.infrastructure.database import Session
from investing_algorithm_framework.infrastructure.models import SQLRunReport
from .repository import Repository


class SQLRunReportRepository(Repository):
    base_class = SQLRunReport
    DEFAULT_NOT_FOUND_MESSAGE = "Run report not found"

    def _apply_query_params(self, db, query, query_params):
        id_query_param = self.get_query_param("id", query_params)
        algorithm_id_query_param = self.get_query_param(
            "algorithm_id", query_params
        )
        environment_query_param = self.get_query_param(
            "environment", query_params
        )

        if id_query_param:
            query = query.filter_by(id=id_query_param)

        if algorithm_id_query_param:
            query = query.filter_by(algorithm_id=algorithm_id_query_param)

        if environment_query_param:
            query = query.filter_by(environment=environment_query_param)

        return query.order_by(SQLRunReport.completed_at.desc())

    def get_all(self, query_params=None):
        """
        Return run reports ordered most-recently-completed first.

        When ``page``/``per_page`` are present in ``query_params``
        (e.g. Flask's ``request.args`` on a REST list endpoint), the
        result is paginated: a dict with ``items`` (this page's
        reports), ``total`` (the total matching count, not just this
        page's size), ``page``, and ``per_page`` is returned instead
        of a plain list.
        """
        page = self.get_query_param(PAGE, query_params)
        per_page = self.get_query_param(PER_PAGE, query_params)

        if page is None and per_page is None:
            return super().get_all(query_params)

        page = int(page) if page is not None else DEFAULT_PAGE_VALUE
        per_page = int(per_page) if per_page is not None \
            else DEFAULT_PER_PAGE_VALUE

        with Session() as db:
            query = db.query(self.base_class)
            query = self.apply_query_params(db, query, query_params)
            total = query.count()
            items = query.offset((page - 1) * per_page) \
                .limit(per_page).all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
        }
