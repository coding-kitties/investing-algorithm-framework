import hashlib
from typing import Dict
import json


def generate_strategy_id(params: Dict, post_fix=None, pre_fix=None) -> str:
    """
    Generate a short, consistent unique id for the given params.
    The id will always be the same for the same params.

    Args:
        params (Dict): Strategy parameters (must be JSON serializable).
            You can optionally pass 'length' to control ID length.
        post_fix (str, optional): String to append to the end of the ID.
        pre_fix (str, optional): String to prepend to the start of the ID.

    Returns:
        str: A deterministic unique identifier for the strategy.
    """
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
