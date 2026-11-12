from mlmodels._constants import PROJECT_NAME, PROJECT_SCHEMA, PROJECT_SIGNATURE_ERROR, SIGNATURE_VERSION_FIRST, SIGNATURE_VERSION_KEY


def registered_name(module, model, notebook):
    return "_".join(check_name(part) for part in (module, model, notebook))


def served_name(name, signature):
    return f"{name}_{signature.get(SIGNATURE_VERSION_KEY, SIGNATURE_VERSION_FIRST)}"


def check_name(name):
    if not PROJECT_NAME.match(name):
        raise ValueError(f"name must be lowercase letters, digits and underscores in module and dimension style [{name}]")
    return name


def signature_input(name, unit, description, datatype="FP64", required=True, shape=None):
    return _signature_tensor(name, unit, description, datatype, required, shape)


def signature_output(name, unit, description, datatype="INT64", required=True, shape=None):
    return _signature_tensor(name, unit, description, datatype, required, shape)


def build_signature(name, inputs, outputs, state=(), signature_version=None):
    version = {} if signature_version is None else {SIGNATURE_VERSION_KEY: signature_version}
    return {
        "schema": PROJECT_SCHEMA,
        **version,
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


def banner(prefix):
    rule = prefix * (80 // len(prefix))
    return [rule, f"{prefix} WARNING: This file is written by the build process, any manual edits will be lost!", rule, ""]


def render_rust(signature, project=None):
    required_inputs = [entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]]
    required_outputs = [entry["name"] for entry in signature["outputs"] if entry["parameters"]["required"]]
    lines = [*banner("//")]
    if project is not None:
        lines += [f"// project {project[0]} sha256 {project[1]}", ""]
        lines += ["use std::path::Path;", ""]
    lines.append("use serde::{Deserialize, Serialize};")
    if project is not None:
        lines += ["", "use super::loader::{Kind, Model, ModelError, Tensors};"]
    lines += [
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
    if project is not None:
        lines += _rust_conversions(signature)
    return "\n".join(lines) + "\n"


def _rust_conversions(signature):
    to_float = "serde_json::Number::from({}).as_f64().unwrap_or(f64::NAN)"
    lines = ["", "impl From<Request> for Tensors {", "    fn from(request: Request) -> Self {", "        let mut tensors = Tensors::new();"]
    for entry in signature["inputs"]:
        name, integer, series = entry["name"], entry["datatype"] == "INT64", entry["shape"] == [-1]
        required = entry["parameters"]["required"]
        value = f"request.{name}" if required else "value"
        body = f"vec![{to_float.format(value) if integer else value}]"
        if series:
            body = f"{value}.into_iter().map(|item| {to_float.format('item')}).collect()" if integer else value
        if required:
            lines.append(f'        tensors.insert("{name}".to_string(), {body});')
        else:
            lines += [f"        if let Some(value) = request.{name} {{", f'            tensors.insert("{name}".to_string(), {body});', "        }"]
    lines += [
        "        tensors",
        "    }",
        "}",
        "",
        "impl TryFrom<Tensors> for Response {",
        "    type Error = ModelError;",
        "",
        "    fn try_from(tensors: Tensors) -> Result<Self, Self::Error> {",
        "        Ok(Self {",
    ]
    for entry in signature["outputs"]:
        name, integer, series, required = entry["name"], entry["datatype"] == "INT64", entry["shape"] == [-1], entry["parameters"]["required"]

        def failure(reason, name=name):
            return f'ModelError {{ kind: Kind::Signature, gate: "response".to_string(), cause: "output [{name}] {reason}".to_string() }}'

        if series:
            expression = (
                f'tensors.get("{name}")'
                + (".map(|values| values.iter().map(|item| *item as i64).collect())" if integer else ".cloned()")
                + (f".ok_or_else(|| {failure('is absent')})?" if required else "")
            )
        else:
            value = "*value as i64" if integer else "*value"
            arms = f"Some([value]) => {value}" if required else f"None => None, Some([value]) => Some({value})"
            expression = f'match tensors.get("{name}").map(Vec::as_slice) {{ {arms}, _ => return Err({failure("is absent or not one value")}) }}'
        lines.append(f"            {name}: {expression},")
    lines += [
        "        })",
        "    }",
        "}",
        "",
        "pub fn load(directory: &Path) -> Result<Model, ModelError> {",
        "    let model = Model::load(directory)?;",
        "    let signature = model.signature();",
        "    let names = |section: &str, required: bool| -> Vec<&str> {",
        "        signature[section]",
        "            .as_array()",
        "            .into_iter()",
        "            .flatten()",
        '            .filter(|entry| !required || entry["parameters"]["required"] == true)',
        '            .filter_map(|entry| entry["name"].as_str())',
        "            .collect()",
        "    };",
        '    let slots = signature["parameters"]["state"].as_array().map_or(0, Vec::len);',
        "    if model.info().name != NAME",
        "        || slots != STATE_SLOTS",
        '        || names("inputs", false) != INPUT_NAMES',
        '        || names("outputs", false) != OUTPUT_NAMES',
        '        || names("inputs", true) != REQUIRED_INPUT_NAMES',
        '        || names("outputs", true) != REQUIRED_OUTPUT_NAMES',
        "    {",
        "        return Err(ModelError {",
        "            kind: Kind::Signature,",
        '            gate: "contract".to_string(),',
        '            cause: format!("signature differs from the compiled constants [{NAME}]"),',
        "        });",
        "    }",
        "    Ok(model)",
        "}",
    ]
    return lines


def render_go(signature, package, project=None):
    def exported(name):
        return "".join(part.capitalize() for part in name.split("_"))

    required_inputs = [entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]]
    required_outputs = [entry["name"] for entry in signature["outputs"] if entry["parameters"]["required"]]
    lines = [*banner("//")]
    if project is not None:
        lines += [f"// project {project[0]} sha256 {project[1]}", ""]
    lines += [f"package {package}", ""]
    if project is not None:
        lines += ["import (", '\t"slices"', "", f'\t"{project[2]}"', ")", ""]
    lines += [
        f'const Name = "{signature["name"]}"',
        f"const StateSlots = {len(signature['parameters'].get('state', []))}",
        "",
        f"var InputNames = []string{{{', '.join(_quoted(entry['name']) for entry in signature['inputs'])}}}",
        f"var OutputNames = []string{{{', '.join(_quoted(entry['name']) for entry in signature['outputs'])}}}",
        f"var RequiredInputNames = []string{{{', '.join(_quoted(name) for name in required_inputs)}}}",
        f"var RequiredOutputNames = []string{{{', '.join(_quoted(name) for name in required_outputs)}}}",
    ]
    for struct, section in (("Request", "inputs"), ("Response", "outputs")):
        lines += ["", f"type {struct} struct {{"]
        for entry in signature[section]:
            base = {"FP64": "float64", "INT64": "int64"}[entry["datatype"]]
            vector = entry["shape"] == [-1]
            required = entry["parameters"]["required"]
            go_type = f"[]{base}" if vector else (base if required else f"*{base}")
            tag = entry["name"] if required else f"{entry['name']},omitempty"
            lines.append(f'\t{exported(entry["name"])} {go_type} `json:"{tag}"`')
        lines.append("}")
    if project is not None:
        lines += _go_conversions(signature, exported)
    return "\n".join(lines) + "\n"


def _go_conversions(signature, exported):
    def convert(entry, value):
        return value if entry["datatype"] == "FP64" else f"int64({value})"

    def to_float(entry, value):
        return value if entry["datatype"] == "FP64" else f"float64({value})"

    lines = ["", "func (r Request) ToTensors() model.Tensors {", "\ttensors := model.Tensors{}"]
    for entry in signature["inputs"]:
        name, field = entry["name"], exported(entry["name"])
        vector, required = entry["shape"] == [-1], entry["parameters"]["required"]
        if vector:
            lines += [
                f"\tif r.{field} != nil {{",
                f"\t\tvalues := make([]float64, len(r.{field}))",
                f"\t\tfor index, value := range r.{field} {{",
                f"\t\t\tvalues[index] = {to_float(entry, 'value')}",
                "\t\t}",
                f'\t\ttensors["{name}"] = values',
                "\t}",
            ]
        elif required:
            lines.append(f'\ttensors["{name}"] = []float64{{{to_float(entry, f"r.{field}")}}}')
        else:
            lines += [f"\tif r.{field} != nil {{", f'\t\ttensors["{name}"] = []float64{{{to_float(entry, f"*r.{field}")}}}', "\t}"]
    lines += ["\treturn tensors", "}", "", "func FromTensors(tensors model.Tensors) (Response, error) {", "\tvar response Response"]
    for entry in signature["outputs"]:
        name, field = entry["name"], exported(entry["name"])
        vector, required = entry["shape"] == [-1], entry["parameters"]["required"]
        base = {"FP64": "float64", "INT64": "int64"}[entry["datatype"]]
        absent = "is absent" if vector else "is absent or not one value"
        failure = f'return response, &model.ModelError{{Kind: model.KindSignature, Gate: "response", Cause: "output [{name}] {absent}"}}'
        lines.append(f'\tif values, ok := tensors["{name}"]; ok {{')
        if vector:
            lines += [f"\t\tresponse.{field} = make([]{base}, len(values))", "\t\tfor index, value := range values {", f"\t\t\tresponse.{field}[index] = {convert(entry, 'value')}", "\t\t}"]
        else:
            lines += ["\t\tif len(values) != 1 {", f"\t\t\t{failure}", "\t\t}", f"\t\tvalue := {convert(entry, 'values[0]')}", f"\t\tresponse.{field} = {'value' if required else '&value'}"]
        lines.append("\t}" if not required else "\t} else {")
        if required:
            lines += [f"\t\t{failure}", "\t}"]
    lines += [
        "\treturn response, nil",
        "}",
        "",
        "func Load(directory string) (*model.Model, error) {",
        "\tloaded, err := model.Load(directory)",
        "\tif err != nil {",
        "\t\treturn nil, err",
        "\t}",
        "\tsignature := loaded.Signature()",
        '\tparameters, _ := signature["parameters"].(map[string]any)',
        '\tstate, _ := parameters["state"].([]any)',
        "\tif loaded.Info().Name != Name || len(state) != StateSlots ||",
        '\t\t!slices.Equal(names(signature, "inputs", false), InputNames) ||',
        '\t\t!slices.Equal(names(signature, "outputs", false), OutputNames) ||',
        '\t\t!slices.Equal(names(signature, "inputs", true), RequiredInputNames) ||',
        '\t\t!slices.Equal(names(signature, "outputs", true), RequiredOutputNames) {',
        '\t\treturn nil, &model.ModelError{Kind: model.KindSignature, Gate: "contract", Cause: "signature differs from the compiled constants [" + Name + "]"}',
        "\t}",
        "\treturn loaded, nil",
        "}",
        "",
        "func names(signature map[string]any, section string, onlyRequired bool) []string {",
        "\tvar found []string",
        "\titems, _ := signature[section].([]any)",
        "\tfor _, item := range items {",
        "\t\tentry, _ := item.(map[string]any)",
        '\t\tparameters, _ := entry["parameters"].(map[string]any)',
        '\t\tif required, _ := parameters["required"].(bool); required || !onlyRequired {',
        '\t\t\tname, _ := entry["name"].(string)',
        "\t\t\tfound = append(found, name)",
        "\t\t}",
        "\t}",
        "\treturn found",
        "}",
    ]
    return lines


def render_python(signature, project=None):
    required_inputs = [entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]]
    required_outputs = [entry["name"] for entry in signature["outputs"] if entry["parameters"]["required"]]
    lines = [*banner("#")]
    if project is not None:
        lines += [f"# project {project[0]} sha256 {project[1]}", ""]
    lines += [
        "from dataclasses import dataclass",
        "",
    ]
    if project is not None:
        lines += ["from . import loader", ""]
    lines += [
        f'NAME = "{signature["name"]}"',
        f"STATE_SLOTS = {len(signature['parameters'].get('state', []))}",
        f"INPUT_NAMES = ({''.join(_quoted(entry['name']) + ', ' for entry in signature['inputs'])})",
        f"OUTPUT_NAMES = ({''.join(_quoted(entry['name']) + ', ' for entry in signature['outputs'])})",
        f"REQUIRED_INPUT_NAMES = ({''.join(_quoted(name) + ', ' for name in required_inputs)})",
        f"REQUIRED_OUTPUT_NAMES = ({''.join(_quoted(name) + ', ' for name in required_outputs)})",
    ]
    for struct, section in (("Request", "inputs"), ("Response", "outputs")):
        lines += ["", "", "@dataclass(kw_only=True)", f"class {struct}:"]
        for entry in signature[section]:
            base = {"FP64": "float", "INT64": "int"}[entry["datatype"]]
            python_type = f"list[{base}]" if entry["shape"] == [-1] else base
            if entry["parameters"]["required"]:
                lines.append(f"    {entry['name']}: {python_type}")
            else:
                lines.append(f"    {entry['name']}: {python_type} | None = None")
        if project is not None:
            lines += _python_conversion(signature[section], section == "inputs")
    if project is not None:
        lines += _python_load()
    return "\n".join(lines) + "\n"


def _python_conversion(entries, request):
    if request:
        lines = ["", "    def to_tensors(self):", "        tensors = {}"]
        for entry in entries:
            name, vector, required = entry["name"], entry["shape"] == [-1], entry["parameters"]["required"]
            value = f"[float(item) for item in self.{name}]" if vector else f"[float(self.{name})]"
            if required:
                lines.append(f'        tensors["{name}"] = {value}')
            else:
                lines += [f"        if self.{name} is not None:", f'            tensors["{name}"] = {value}']
        return [*lines, "        return tensors"]
    lines = ["", "    @classmethod", "    def from_tensors(cls, tensors):", "        fields = {}"]
    for entry in entries:
        name, vector, required = entry["name"], entry["shape"] == [-1], entry["parameters"]["required"]
        convert = "int" if entry["datatype"] == "INT64" else "float"
        absent = "is absent" if vector else "is absent or not one value"
        failure = f'raise loader.ModelError("Signature", "response", "output [{name}] {absent}")'
        lines.append(f'        values = tensors.get("{name}")')
        if vector:
            lines += ["        if values is not None:", f'            fields["{name}"] = [{convert}(item) for item in values]']
        else:
            lines += ["        if values is not None and len(values) != 1:", f"            {failure}", "        if values is not None:", f'            fields["{name}"] = {convert}(values[0])']
        if required:
            lines += [f'        if "{name}" not in fields:', f"            {failure}"]
        else:
            lines.append(f'        fields.setdefault("{name}", None)')
    return [*lines, "        return cls(**fields)"]


def _python_load():
    return [
        "",
        "",
        "def load(directory):",
        "    model = loader.load(directory)",
        "    signature = model.signature()",
        "",
        "    def names(section, required):",
        '        return tuple(entry["name"] for entry in signature[section] if not required or entry["parameters"]["required"])',
        "",
        "    if (",
        "        model.info().name != NAME",
        '        or len(signature["parameters"].get("state", [])) != STATE_SLOTS',
        '        or names("inputs", False) != INPUT_NAMES',
        '        or names("outputs", False) != OUTPUT_NAMES',
        '        or names("inputs", True) != REQUIRED_INPUT_NAMES',
        '        or names("outputs", True) != REQUIRED_OUTPUT_NAMES',
        "    ):",
        '        raise loader.ModelError("Signature", "contract", f"signature differs from the compiled constants [{NAME}]")',
        "    return model",
    ]


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
