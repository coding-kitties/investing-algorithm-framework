"""
Invokes investing_bot_framework-admin when the investing_bot_framework framework module is run as a script.
Example: python -m investing_bot_framework createbot SampleBot
"""

from investing_bot_framework.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line()
