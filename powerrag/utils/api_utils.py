import logging
from flask import jsonify

from api import settings

def get_data_error_result(code=settings.RetCode.DATA_ERROR, message="Sorry! Data missing!"):
    logging.exception(Exception(message))
    result_dict = {"code": code, "message": message}
    response = {}
    for key, value in result_dict.items():
        if value is None and key != "code":
            continue
        else:
            response[key] = value
    return jsonify(response)

def get_json_result(code: settings.RetCode = settings.RetCode.SUCCESS, message="success", data=None):
    response = {"code": code, "message": message, "data": data}
    return jsonify(response)

def server_error_response(e):
    logging.exception(e)
    try:
        msg = repr(e).lower()
        if getattr(e, "code", None) == 401 or ("unauthorized" in msg) or ("401" in msg):
            return get_json_result(code=settings.RetCode.UNAUTHORIZED, message=repr(e))
    except Exception as ex:
        logging.warning(f"error checking authorization: {ex}")

    if len(e.args) > 1:
        try:
            serialized_data = serialize_for_json(e.args[1])
            return get_json_result(code=settings.RetCode.EXCEPTION_ERROR, message=repr(e.args[0]), data=serialized_data)
        except Exception:
            return get_json_result(code=settings.RetCode.EXCEPTION_ERROR, message=repr(e.args[0]), data=None)
    if repr(e).find("index_not_found_exception") >= 0:
        return get_json_result(code=settings.RetCode.EXCEPTION_ERROR,
                               message="No chunk found, please upload file and parse it.")

    return get_json_result(code=settings.RetCode.EXCEPTION_ERROR, message=repr(e))

def serialize_for_json(obj):
    """
    Recursively serialize objects to make them JSON serializable.
    Handles ModelMetaclass and other non-serializable objects.
    """
    if hasattr(obj, '__dict__'):
        # For objects with __dict__, try to serialize their attributes
        try:
            return {key: serialize_for_json(value) for key, value in obj.__dict__.items()
                    if not key.startswith('_')}
        except (AttributeError, TypeError):
            return str(obj)
    elif hasattr(obj, '__name__'):
        # For classes and metaclasses, return their name
        return f"<{obj.__module__}.{obj.__name__}>" if hasattr(obj, '__module__') else f"<{obj.__name__}>"
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    else:
        # Fallback: convert to string representation
        return str(obj)