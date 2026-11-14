import inspect

from fastapi.responses import JSONResponse


def create_response(data, serializer, status_code=200):

    if inspect.isclass(serializer):
        serializer = serializer()

    if isinstance(data, dict):
        item_selection = data["items"]
        data["items"] = serializer.dump(item_selection, many=True)
        return JSONResponse(content=data, status_code=status_code)
    elif isinstance(data, list):
        data = serializer.dump(data, many=True)
        return JSONResponse(
            content={"items": data, "total": len(data)},
            status_code=status_code,
        )
    else:
        data = serializer.dump(data)
        return JSONResponse(content=data, status_code=status_code)
