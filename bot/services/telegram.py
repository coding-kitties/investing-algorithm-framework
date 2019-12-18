import logging
from typing import Any, Callable, Dict, List

from telegram import ParseMode, ReplyKeyboardMarkup, Update
from telegram.error import NetworkError, TelegramError
from telegram.ext import CallbackContext, CommandHandler, Updater, ConversationHandler, MessageHandler, Filters

from bot import __version__, OperationalException
from bot.services.service import Service, ServiceException

logger = logging.getLogger(__name__)

logger.debug('Included module service.telegram ...')

MAX_TELEGRAM_MESSAGE_LENGTH = 4096

# Telegram keyboard buttons
DEFAULT_KEYBOARD_BUTTONS = [
    ['/add_tickers'],
    ['/help', '/version']
]

ADDING_TICKERS_CONVERSATION_BUTTONS = [
    ['/cancel']
]


def authorized_only(command_handler: Callable[..., None]) -> Callable[..., Any]:
    """
    Decorator to check if the message comes from the correct chat_id
    :param command_handler: Telegram CommandHandler
    :return: decorated function
    """
    def wrapper(self, *args, **kwargs):
        """ Decorator logic """
        update = kwargs.get('update') or args[0]

        # Reject unauthorized messages
        chat_id = int(self._bot.config['telegram']['chat_id'])

        if int(update.message.chat_id) != chat_id:
            logger.info(
                'Rejected unauthorized message from: %s',
                update.message.chat_id
            )
            return wrapper

        logger.info(
            'Executing handler: %s for chat_id: %s',
            command_handler.__name__,
            chat_id
        )
        try:
            return command_handler(self, *args, **kwargs)
        except Exception:
            logger.exception('Exception occurred within Telegram module')

    return wrapper


class Telegram(Service):
    """  This class handles all telegram communication """

    # Conversation states
    class AddTickersConversationState:
        ADDING, TYPING_REPLY, TYPING_CHOICE = range(3)

    def __init__(self, bot) -> None:
        """
        Init the Telegram call, and init the super class service
        :param bot: Instance of a MrValue bot
        :return: None
        """
        super().__init__(bot)

        self._updater: Updater = None
        self.startup()

    def startup(self) -> None:
        self._updater = Updater(token=self._bot.config['telegram']['token'], workers=0,
                                use_context=True)

        # States of adding a ticker
        ticker_conversation_handler = ConversationHandler(
            entry_points=[CommandHandler('add_tickers', self._start_adding_tickers)],
            states={
                self.AddTickersConversationState.ADDING: [MessageHandler(Filters.text, self._add_tickers)],
            },
            fallbacks=[CommandHandler('cancel', self._cancel_conversation)]
        )

        # Register command handler and start telegram message polling
        handles = [
            CommandHandler('help', self._help),
            CommandHandler('version', self._version),
            ticker_conversation_handler
        ]

        for handle in handles:
            self._updater.dispatcher.add_handler(handle)

        self._updater.start_polling(
            clean=True,
            bootstrap_retries=-1,
            timeout=30,
            read_latency=60,
        )

        bot_name = self._bot.config.get("telegram", {}).get("bot_name", "value investing bot")

        reply_markup = ReplyKeyboardMarkup(DEFAULT_KEYBOARD_BUTTONS)
        msg = "Hello my name is {}, I am an investment bot based on value investing principles. " \
              "How can I help you?".format(bot_name)

        self._updater.bot.send_message(
            self._bot.config['telegram']['chat_id'],
            text=msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    def cleanup(self) -> None:
        """
        Stops all running telegram threads.
        :return: None
        """
        self._updater.stop()

    @authorized_only
    def _help(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /help. That shows commands of the bot
        :param update: message update
        :return: None
        """

        message = "*/help:* `This help message`\n" \
                  "*/version:* `Show version`\n" \
                  "*/add_tickers:* `Add tickers to the registry, so they can be analyzed.`\n"

        self._send_msg(message)

    def _send_msg(self, msg: str, parse_mode: ParseMode = ParseMode.MARKDOWN,
                  keyboard_buttons: List[List[str]] = None) -> None:
        """
        Send given markdown message
        :param msg: message
        :param parse_mode: telegram parse mode
        :keyboard_buttons: list of strings representing the buttons
        :return: None
        """

        if keyboard_buttons is None:
            keyboard_buttons = DEFAULT_KEYBOARD_BUTTONS

        reply_markup = ReplyKeyboardMarkup(keyboard_buttons)

        try:
            try:
                self._updater.bot.send_message(
                    self._bot.config['telegram']['chat_id'],
                    text=msg,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
            except NetworkError as network_err:
                # Sometimes the telegram server resets the current connection,
                # if this is the case we send the message again.
                logger.warning(
                    'Telegram NetworkError: %s! Trying one more time.',
                    network_err.message
                )
                self._updater.bot.send_message(
                    self._bot.config['telegram']['chat_id'],
                    text=msg,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
        except TelegramError as telegram_err:
            logger.warning(
                'TelegramError: %s! Giving up on that message.',
                telegram_err.message
            )

    @authorized_only
    def _version(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /version.
        Show version information
        :param update: message update
        :return: None
        """
        self._send_msg('*Version:* `{}`'.format(__version__))

    @authorized_only
    def _start_adding_tickers(self, update: Update, context: CallbackContext):
        self._send_msg("Please provide the tickers separated by commas, if you submit "
                       "one ticker you can leave out the comma", keyboard_buttons=ADDING_TICKERS_CONVERSATION_BUTTONS)
        return self.AddTickersConversationState.ADDING

    @authorized_only
    def _add_tickers(self, update: Update, context: CallbackContext):
        text = update.message.text
        tickers = [ticker.strip() for ticker in text.split(',')]
        added_tickers = []

        for ticker in tickers:

            try:
                self._add_ticker(ticker)
                added_tickers.append(ticker)
            except OperationalException as e:
                self._send_msg(str(e))

        if added_tickers:
            self._send_msg("{} added".format(added_tickers))

        return ConversationHandler.END

    @authorized_only
    def _remove_tickers(self, update: Update, context: CallbackContext):
        text = update.message.text
        tickers = [ticker.strip() for ticker in text.split(',')]
        added_tickers = []
        return ConversationHandler.END

    @authorized_only
    def _cancel_conversation(self, update: Update, context: CallbackContext):
        logger.info("Conversation is canceled")
        message = "Process has been canceled"
        self._send_msg(message)

        return ConversationHandler.END

