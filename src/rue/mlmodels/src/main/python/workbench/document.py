import json

DOCUMENT_WIDTH = 200
DOCUMENT_INDENT = 2


def write_json(path, document):
    with open(path, "w") as document_file:
        document_file.write(_format(document, 0) + "\n")


def _format(value, level):
    pad = " " * (DOCUMENT_INDENT * level)
    if isinstance(value, dict) and value:
        flat = "{" + ", ".join(f"{json.dumps(key)}: {json.dumps(item, ensure_ascii=False)}" for key, item in value.items()) + "}"
        if all(_scalar(item) or _scalars(item) for item in value.values()) and len(pad) + len(flat) <= DOCUMENT_WIDTH:
            return flat
        body = ",\n".join(f"{pad}{' ' * DOCUMENT_INDENT}{json.dumps(key)}: {_format(item, level + 1)}" for key, item in value.items())
        return "{\n" + body + "\n" + pad + "}"
    if isinstance(value, list) and value:
        flat = json.dumps(value, ensure_ascii=False)
        if _scalars(value) and len(pad) + len(flat) <= DOCUMENT_WIDTH:
            return flat
        body = ",\n".join(f"{pad}{' ' * DOCUMENT_INDENT}{_format(item, level + 1)}" for item in value)
        return "[\n" + body + "\n" + pad + "]"
    return json.dumps(value, ensure_ascii=False)


def _scalar(value):
    return not isinstance(value, (dict, list))


def _scalars(value):
    return isinstance(value, list) and all(_scalar(item) for item in value)
