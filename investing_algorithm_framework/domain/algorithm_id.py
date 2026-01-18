import hashlib
from typing import Dict
import json


def generate_algorithm_id(
    algorithm=None,
    strategy=None,
    params: Dict = None,
    post_fix=None,
    pre_fix=None
) -> str:
    """
    Generate a short, consistent unique id for the given params.
    The id will always be the same for the same params.

    Args:
        algorithm: (optional) Algorithm instance to generate ID for.
        strategy: (optional) Strategy instance to generate ID for.
        params (Dict, optional): Strategy parameters
            (must be JSON serializable).
            You can optionally pass 'length' to control ID length.
        post_fix (str, optional): String to append to the end of the ID.
        pre_fix (str, optional): String to prepend to the start of the ID.

    Returns:
        str: A deterministic unique identifier for the strategy.
    """

    if algorithm is not None:
        if hasattr(algorithm, "algorithm_id"):
            return algorithm.algorithm_id

        if hasattr(algorithm, "strategies") \
                and len(algorithm.strategies) > 0:
            first_strategy = algorithm.strategies[0]

            if first_strategy is not None:
                return f"{first_strategy.__class__.__name__}"

        raise ValueError(
            "Cannot generate algorithm ID from the provided algorithm "
            "instance. Please provide 'params' instead."
        )

    if strategy is not None:
        return strategy.__class__.__name__

    length = params.get("length", 8)

    # Remove "length" if present so it doesn't affect the hash
    clean_params = {k: v for k, v in params.items() if k != "length"}

    # Create a canonical string representation (sorted keys)
    params_str = json.dumps(clean_params, sort_keys=True)

    # Hash the params string
    hash_digest = hashlib.sha256(params_str.encode("utf-8")).hexdigest()

    # Return shortened hash
    result = hash_digest[:length]

    if post_fix:
        result = result + post_fix

    if pre_fix:
        result = pre_fix + result

    return result
