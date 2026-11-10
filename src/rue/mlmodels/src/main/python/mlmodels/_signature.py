from mlmodels._constants import PROJECT_NAME, PROJECT_SCHEMA, PROJECT_SIGNATURE_ERROR


def registered_name(module, model, notebook):
    return "_".join(check_name(part) for part in (module, model, notebook))


def check_name(name):
    if not PROJECT_NAME.match(name):
        raise ValueError(f"name must be lowercase letters, digits and underscores in module and dimension style [{name}]")
    return name


def signature_input(name, unit, description, datatype="FP64", required=True, shape=None):
    return _signature_tensor(name, unit, description, datatype, required, shape)


def signature_output(name, unit, description, datatype="INT64", required=True, shape=None):
    return _signature_tensor(name, unit, description, datatype, required, shape)


def build_signature(name, inputs, outputs, state=()):
    return {
        "schema": PROJECT_SCHEMA,
        "name": name,
        "platform": "mlserver",
        "parameters": {"state": [{"slot": slot, **entry} for slot, entry in enumerate(state)]},
        "inputs": list(inputs),
        "outputs": list(outputs),
    }


def golden_step(signature, step_id, inputs, outputs=None, error=None):
    request = {"id": step_id, "inputs": [_tensor(signature["inputs"], name, value) for name, value in inputs.items()]}
    if error is not None:
        return {"request": request, "error": error}
    response = {
        "model_name": signature["name"],
        "id": step_id,
        "outputs": [_tensor(signature["outputs"], name, value) for name, value in (outputs or {}).items()],
    }
    return {"request": request, "response": response}


def golden_document(sequences, tolerance=None):
    document = {"schema": PROJECT_SCHEMA, "sequences": [{"name": name, "steps": steps} for name, steps in sequences]}
    if tolerance:
        document["tolerance"] = tolerance
    return document


def golden_from_samples(signature, samples, sequence="golden", constants=None, tolerance=None):
    input_specs = {entry["name"]: entry for entry in signature["inputs"]}
    output_specs = {entry["name"]: entry for entry in signature["outputs"]}
    output_names = list(output_specs)
    steps = []
    for index, sample in enumerate(samples):
        inputs = {name: cell(spec, sample[name]) for name, spec in input_specs.items() if sample.get(name) is not None}
        step_id = f"s1-{index}"
        if sample.get("expect") == "error":
            steps.append(golden_step(signature, step_id, inputs, error=PROJECT_SIGNATURE_ERROR))
        else:
            outputs = dict(constants) if constants is not None else {name: cell(output_specs[name], sample[name]) for name in output_names if sample.get(name) is not None}
            steps.append(golden_step(signature, step_id, inputs, outputs))
    return golden_document([(sequence, steps)], tolerance)


def render_rust(signature):
    required_inputs = [entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]]
    required_outputs = [entry["name"] for entry in signature["outputs"] if entry["parameters"]["required"]]
    lines = [
        "use serde::{Deserialize, Serialize};",
        "",
        f'pub const NAME: &str = "{signature["name"]}";',
        f"pub const STATE_SLOTS: usize = {len(signature['parameters'].get('state', []))};",
        f"pub const INPUT_NAMES: &[&str] = &[{', '.join(_quoted(entry['name']) for entry in signature['inputs'])}];",
        f"pub const OUTPUT_NAMES: &[&str] = &[{', '.join(_quoted(entry['name']) for entry in signature['outputs'])}];",
        f"pub const REQUIRED_INPUT_NAMES: &[&str] = &[{', '.join(_quoted(name) for name in required_inputs)}];",
        f"pub const REQUIRED_OUTPUT_NAMES: &[&str] = &[{', '.join(_quoted(name) for name in required_outputs)}];",
    ]
    for struct, section in (("Request", "inputs"), ("Response", "outputs")):
        lines += ["", "#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]", f"pub struct {struct} {{"]
        for entry in signature[section]:
            base = {"FP64": "f64", "INT64": "i64"}[entry["datatype"]]
            rust_type = f"Vec<{base}>" if entry["shape"] == [-1] else base
            if entry["parameters"]["required"]:
                lines.append(f"    pub {entry['name']}: {rust_type},")
            else:
                lines += ['    #[serde(default, skip_serializing_if = "Option::is_none")]', f"    pub {entry['name']}: Option<{rust_type}>,"]
        lines.append("}")
    return "\n".join(lines) + "\n"


def _signature_tensor(name, unit, description, datatype, required, shape):
    return {"name": name, "datatype": datatype, "shape": list(shape) if shape is not None else [1], "parameters": {"unit": unit, "required": required, "description": description}}


def cell(spec, value):
    return [float(item) for item in value.split()] if spec["shape"] == [-1] and isinstance(value, str) else value


def _quoted(text):
    return f'"{text}"'


def _tensor(specs, name, value):
    spec = next((entry for entry in specs if entry["name"] == name), None)
    data = list(value) if isinstance(value, (list, tuple)) else [value]
    datatype = spec["datatype"] if spec is not None else "FP64"
    data = [float(item) if datatype == "FP64" else int(item) for item in data]
    return {"name": name, "datatype": datatype, "shape": [len(data)], "data": data}
