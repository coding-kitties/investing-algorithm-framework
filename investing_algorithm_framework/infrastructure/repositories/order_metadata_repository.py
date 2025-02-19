from investing_algorithm_framework.infrastructure.models import \
    SQLOrderMetadata
from .repository import Repository


class SQLOrderMetadataRepository(Repository):
    base_class = SQLOrderMetadata
    DEFAULT_NOT_FOUND_MESSAGE = "The requested order metadata was not found"

    def _apply_query_params(self, db, query, query_params):

        if "order_id" in query_params:
            query = query.filter(
               SQLOrderMetadata.order_id == query_params["order_id"]
            )

        return query
