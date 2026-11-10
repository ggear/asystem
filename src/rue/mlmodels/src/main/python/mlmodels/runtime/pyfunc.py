def load_pyfunc(path, signature_json):
    import importlib.util
    import json
    import warnings

    import pandas
    from mlflow.models import model as mlflow_model

    spec = importlib.util.spec_from_file_location("project_model", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        spec.loader.exec_module(module)
    for warning in caught:
        if "type hint" not in str(warning.message):
            warnings.warn_explicit(warning.message, warning.category, warning.filename, warning.lineno)
    instance = getattr(mlflow_model, "__mlflow_model__")  # noqa: B009
    outputs = json.loads(signature_json)["outputs"]

    def predict(inputs):
        result = instance.predict(None, pandas.DataFrame(dict(inputs)))
        return {entry["name"]: [int(item) if entry["datatype"] == "INT64" else float(item) for item in result[entry["name"]]] for entry in outputs}

    return predict
