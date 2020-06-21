"""
Invokes investing_algorithm_framework-admin when the investing_algorithm_framework framework module is run as a script.
Example: python -m investing_algorithm_framework createalgorithm SampleAlgorithm
"""

from investing_algorithm_framework.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line()
