import logging
from datetime import datetime

from investing_algorithm_framework.services.repository_service import \
    RepositoryService

logger = logging.getLogger(__name__)


class TradeStopLossService(RepositoryService):

    def mark_triggered(
        self,
        stop_loss_ids,
        trigger_date: datetime
    ) -> None:
        """
        Mark stop losses as triggered.

        Args:
            stop_loss_ids (List[str]): List of stop loss IDs to
                mark as triggered.
            trigger_date (datetime): The date when the stop loss
                was triggered.

        Returns:
            None
        """
        update_data = {
            "triggered": True,
            "triggered_at": trigger_date,
            "updated_at":  trigger_date
        }

        for id in stop_loss_ids:
            try:
                self.update(id, update_data)
            except Exception as e:
                logger.error(f"Error marking stop loss {id} as triggered: {e}")
