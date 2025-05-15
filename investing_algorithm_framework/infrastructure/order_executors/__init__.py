from .ccxt_order_executor import CCXTOrderExecutor


def get_default_order_executors():
    """
    Function to get the default order executors.

    Returns:
        list: List of default order executors.
    """
    return [
        CCXTOrderExecutor(),
    ]


__all__ = [
    'CCXTOrderExecutor',
    'get_default_order_executors',
]
