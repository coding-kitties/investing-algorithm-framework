from flask import jsonify


def normalize_query_param(value):
    """
    Given a non-flattened query parameter value,
    and if the value is a list only containing 1 item,
    then the value is flattened.

    :param value: a value from a query parameter
    :return: a normalized query parameter value
    """

    if len(value) == 1 and value[0].lower() in ["true", "false"]:

        if value[0].lower() == "true":
            return True
        return False

    return value if len(value) > 1 else value[0]


def normalize_query(params):
    """
    Converts query parameters from only containing one value for each parameter,
    to include parameters with multiple values as lists.

    :param params: a flask query parameters data_provider structure
    :return: a dict of normalized query parameters
    """
    params_non_flat = params.to_dict(flat=False)
    return {k: normalize_query_param(v) for k, v in params_non_flat.items()}


def has_query_param(key, params):
    query_params = normalize_query(params)
    return key in query_params


def get_query_param(key, params, default=None, many=False):
    query_params = normalize_query(params)
    selection = query_params.get(key, default)

    if isinstance(selection, list) and len(selection) > 1 and not many:
        return selection[0]

    return selection


def split(list_a, chunk_size):

    for i in range(0, len(list_a), chunk_size):
        yield list_a[i:i + chunk_size]


def create_paginated_response(query_set, serializer, page=1, per_page=20):
    """
    Creates a paginated response from a query set. The given query set
    is paginated the function.

    :param query_set: a lazy query
    :param serializer: an instance of an marshmallow schema
    :return: a json of paginated query
    """

    if isinstance(query_set, list):
        chunks = list(split(query_set, per_page))

        if len(chunks) > 0:
            items = chunks[page - 1]
        else:
            items = []

        return jsonify(
            {
                'total': len(query_set),
                'page': page,
                'per_page': per_page,
                'items': serializer.dump(items, many=True)
            }
        )
    else:
        paginated_query_set = query_set.paginate()

    return jsonify(
        {
            'total': paginated_query_set.total,
            'page': paginated_query_set.page,
            'per_page': paginated_query_set.per_page,
            'items': serializer.dump(paginated_query_set.items, many=True)
        }
    )
