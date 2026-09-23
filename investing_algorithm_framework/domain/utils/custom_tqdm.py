import os

from tqdm.notebook import tqdm as tqdm_notebook
from tqdm import tqdm as tqdm_terminal

from .jupyter_notebook_detection import is_jupyter_notebook


def tqdm(*args, **kwargs):
    """
    Returns a tqdm progress bar that adapts to the
    environment (Jupyter Notebook or terminal).

    Set IAF_PROGRESS_BACKEND=text to bypass notebook widgets, or
    notebook to explicitly request them. The default is auto.

    Args:
        *args: Positional arguments for tqdm.
        **kwargs: Keyword arguments for tqdm.

    Returns:
        tqdm object: A tqdm progress bar.
    """
    backend = os.environ.get("IAF_PROGRESS_BACKEND", "auto").strip().lower()
    if backend not in {"auto", "text", "notebook"}:
        raise ValueError(
            "IAF_PROGRESS_BACKEND must be auto, text, or notebook")
    if backend == "text":
        return tqdm_terminal(*args, **kwargs)
    if backend == "notebook" or is_jupyter_notebook():
        return tqdm_notebook(*args, **kwargs)
    else:
        return tqdm_terminal(*args, **kwargs)
