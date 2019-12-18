"""
This module contains a class to manage service communications (Telegram, Slack, ...)
"""
import logging
from typing import Any, Dict, List

from bot.services import Service

logger = logging.getLogger(__name__)


class ServiceManager:
    """
    Class to manage Service objects (Telegram, Slack, ...)
    """
    def __init__(self, bot) -> None:
        """ Initializes all enabled service modules """
        self.registered_modules: List[Service] = []

        # Enable telegram
        if bot.config.get('telegram', {}).get('enabled', False):
            logger.info('Enabling service.telegram ...')
            from bot.services.telegram import Telegram
            self.registered_modules.append(Telegram(bot))

    def cleanup(self) -> None:
        """ Stops all enabled service modules """
        logger.info('Cleaning up service modules ...')
        while self.registered_modules:
            mod = self.registered_modules.pop()
            logger.debug('Cleaning up service.%s ...', mod.name)
            mod.cleanup()
            del mod

    def send_msg(self, msg: Dict[str, Any]) -> None:
        """
        Send given message to all registered service modules.
        A message consists of one or more key value pairs of strings.
        e.g.:
        {
            'status': 'stopping bot'
        }
        """
        logger.info('Sending service message: %s', msg)
        for mod in self.registered_modules:
            logger.debug('Forwarding message to service.%s', mod.name)
            try:
                mod.send_msg(msg)
            except NotImplementedError:
                logger.error(f"Message type {msg['type']} not implemented by handler {mod.name}.")