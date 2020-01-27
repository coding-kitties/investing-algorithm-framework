"""
Invokes bot-admin when the bot framework module is run as a script.
Example: python -m investing_bot_framework createbot SampleBot
"""

from bot.core import management

if __name__ == "__main__":
    management.execute_from_command_line()