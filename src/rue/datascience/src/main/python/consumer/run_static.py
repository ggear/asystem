import json


def load_static(constants_json, signature_json):
    constants = json.loads(constants_json)
    outputs = {name: [value] for name, value in constants.items()}
    return lambda _inputs: dict(outputs)
