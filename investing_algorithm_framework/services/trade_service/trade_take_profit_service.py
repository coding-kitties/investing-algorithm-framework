import logging
from datetime import datetime

from investing_algorithm_framework.services.repository_service import \
    RepositoryService

logger = logging.getLogger(__name__)


class TradeTakeProfitService(RepositoryService):

    def mark_triggered(
        self,
        take_profit_ids,
        trigger_date: datetime,
        mirror: bool = False,
    ) -> None:
        """
        Mark take profits as triggered.

        Args:
            take_profit_ids (List[str]): List of take profit IDs to
                mark as triggered.
            trigger_date (datetime): The date and time when the
                take profits were triggered.
            mirror (bool): When True, records that the broker-native
                mirror order (not the client-side price check) is
                what closed the position, by setting
                ``mirror_triggered``/``mirror_triggered_at`` instead
                of ``triggered``/``triggered_at``. Default False.

        Returns:
            None
        """
        if mirror:
            update_data = {
                "triggered": True,
                "triggered_at": trigger_date,
                "mirror_triggered": True,
                "mirror_triggered_at": trigger_date,
                "updated_at": trigger_date
            }
        else:
            update_data = {
                "triggered": True,
                "triggered_at": trigger_date,
                "updated_at": trigger_date
            }

        for id in take_profit_ids:
            try:
                self.update(id, update_data)
            except Exception as e:
                logger.error(
                    f"Error marking take profit {id} as triggered: {e}"
                )
