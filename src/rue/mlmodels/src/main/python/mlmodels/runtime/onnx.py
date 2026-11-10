def load_onnx(path, signature_json):
    import json

    import numpy
    import onnxruntime

    signature = json.loads(signature_json)
    session = onnxruntime.InferenceSession(path, providers=["CPUExecutionProvider"])
    outputs = signature["outputs"]

    def predict(inputs):
        feeds = {entry["name"]: numpy.array([inputs[entry["name"]]], dtype=numpy.float64) for entry in signature["inputs"] if entry["name"] in inputs}
        values = session.run([entry["name"] for entry in outputs], feeds)
        return {entry["name"]: [int(item) if entry["datatype"] == "INT64" else float(item) for item in numpy.asarray(value).flatten()] for entry, value in zip(outputs, values, strict=True)}

    return predict
