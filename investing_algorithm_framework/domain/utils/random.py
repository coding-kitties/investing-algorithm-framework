import random
import string


def random_string(n, spaces: bool = False):
    """
    Function to generate a random string of n characters.

    Args:
        n: number of characters
        spaces: if True, include spaces in the string

    Returns:
        str: Random string of n characters
    """

    if spaces:
        return ''.join(
            random.choice(string.ascii_lowercase + ' ') for _ in range(n)
        )

    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))


def random_number(n, variable_size: bool = False):
    """
    Function to generate a random number of n digits.

    Args:
        n: number of digits
        variable_size: if True, the number of digits will be variable
            between 1 and n

    Returns:
        int: Random number of n digits
    """

    if variable_size:
        n = random.randint(1, n)

    return int(''.join(random.choice(string.digits) for _ in range(n)))
