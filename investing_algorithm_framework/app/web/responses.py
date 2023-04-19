import inspect

from flask import jsonify


def create_response(data, serializer, status_code=200):

    if inspect.isclass(serializer):
        serializer = serializer()

    if isinstance(data, dict):
        item_selection = data["items"]
        data["items"] = serializer.dump(item_selection, many=True)
        return data, status_code
    elif isinstance(data, list):
        data = serializer.dump(data, many=True)
        return jsonify({"items": data, "total": len(data)}), status_code
    else:
        data = serializer.dump(data)
        return jsonify(data), status_code
