def is_jupyter_notebook():
    """
    Check if the code is running in a Jupyter Notebook environment.

    Returns:
        bool: True if running in a Jupyter Notebook, False otherwise.
    """
    try:
        # Check for the presence of the 'IPython' module
        from IPython import get_ipython
        return 'IPKernelApp' in get_ipython().config
    except ImportError:
        return False
    except AttributeError:
        # If get_ipython() does not have 'config', it is not a Jupyter Notebook
        return False
    except Exception:
        # Catch any other exceptions and return False
        return False
