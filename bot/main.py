import sys
import logging
from typing import Any, List

# Call settings for general configuration
from bot import setup

from bot import OperationalException
from bot.configuration import Arguments


logger = logging.getLogger(__name__)


def main(sysargv: List[str] = None) -> None:
    """
    This function will initiate all the services.
    """

    return_code: Any = 1
    try:
        arguments = Arguments(sysargv)
        args = arguments.parsed_args

        # Call subcommand.
        if 'func' in args:
            return_code = args['func'](args)
        else:
            # No subcommand was issued.
            raise OperationalException(
                "Usage of the bot requires a sub command to be specified.\n"
                "To see the full list of options available, please use "
                "`bot --help` or `bot <command> --help`."
            )

    except SystemExit as e:
        return_code = e
    except KeyboardInterrupt:
        logger.info('SIGINT received, aborting ...')
        return_code = 0
    except OperationalException as e:
        logger.error(str(e))
        return_code = 2
    except Exception:
        logger.exception('Fatal exception!')
    finally:
        sys.exit(return_code)


if __name__ == "__main__":
    main()
