import string
import random


def random_string(n) -> str:
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))
