import string
import random
from pandas import DataFrame
import numpy as np


def random_string(n) -> str:
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))


def random_numpy_data_frame() -> DataFrame:
    return DataFrame(np.random.randint(1000, size=10000), columns=['p/e'])
