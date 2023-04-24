import random
import string


def random_string(n, spaces: bool = False):

    if spaces:
        return ''.join(
            random.choice(string.ascii_lowercase + ' ') for _ in range(n)
        )

    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))
