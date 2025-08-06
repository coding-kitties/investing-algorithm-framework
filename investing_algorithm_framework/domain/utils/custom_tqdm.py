from tqdm.notebook import tqdm as tqdm_notebook
from tqdm import tqdm as tqdm_terminal

from .jupyter_notebook_detection import is_jupyter_notebook


def tqdm(*args, **kwargs):
    """
    Returns a tqdm progress bar that adapts to the
    environment (Jupyter Notebook or terminal).

    Args:
        *args: Positional arguments for tqdm.
        **kwargs: Keyword arguments for tqdm.

    Returns:
        tqdm object: A tqdm progress bar.
    """
    if is_jupyter_notebook():
        return tqdm_notebook(*args, **kwargs)
    else:
        return tqdm_terminal(*args, **kwargs)
