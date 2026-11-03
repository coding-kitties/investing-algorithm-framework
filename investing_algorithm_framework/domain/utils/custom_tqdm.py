import os
from logging import getLogger

from tqdm import notebook as notebook_backend
from tqdm.notebook import tqdm as tqdm_notebook
from tqdm import tqdm as tqdm_terminal

from .jupyter_notebook_detection import is_jupyter_notebook


logger = getLogger("investing_algorithm_framework")


def tqdm(*args, **kwargs):
    """
    Returns a tqdm progress bar that adapts to the
    environment (Jupyter Notebook or terminal).

    Set IAF_PROGRESS_BACKEND=text to bypass notebook widgets, or
    notebook to explicitly request them. The default is auto, which
    falls back to text with a warning when notebook widgets are unavailable.

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
    if backend == "notebook":
        if notebook_backend.IProgress is None:
            raise ImportError(
                "Notebook progress requires ipywidgets (IProgress). "
                "Install ipywidgets in the kernel environment or set "
                "IAF_PROGRESS_BACKEND=text."
            )
        return tqdm_notebook(*args, **kwargs)
    if is_jupyter_notebook():
        if notebook_backend.IProgress is not None:
            return tqdm_notebook(*args, **kwargs)
        if not kwargs.get("disable", False):
            logger.warning(
                "Notebook progress widgets (IProgress) are unavailable; "
                "using text progress. Install ipywidgets for widget bars."
            )
    return tqdm_terminal(*args, **kwargs)
