"""
Invokes bot-admin when the bot framework module is run as a script.
Example: python -m investing_bot_framework createbot SampleBot
"""

from bot.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line()
