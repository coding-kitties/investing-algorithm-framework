from investing_algorithm_framework.services.repository_service import \
    RepositoryService


class RunReportService(RepositoryService):
    """
    Service to persist and retrieve :class:`RunReport` snapshots — one
    per successful, bounded ``App.run()`` invocation.
    """

    def get_latest(self, algorithm_id=None):
        """
        Return the most recently completed run report, optionally
        scoped to a single algorithm.

        Args:
            algorithm_id (str): Optional algorithm id to filter by.

        Returns:
            RunReport or None: The latest run report, or None if no
                run report has been persisted yet.
        """
        query_params = {}

        if algorithm_id is not None:
            query_params["algorithm_id"] = algorithm_id

        results = self.get_all(query_params)
        return results[0] if results else None
