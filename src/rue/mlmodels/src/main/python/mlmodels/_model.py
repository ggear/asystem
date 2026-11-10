import ast
import builtins
import hashlib
import inspect
import json
import os
import shutil
import symtable
import sys
import textwrap
import types
from dataclasses import dataclass
from os.path import join

from mlmodels import maths
from mlmodels._constants import MODEL_DIR, MODEL_DOCUMENT, MODEL_SCHEMA, PROJECT_MODEL_FILES, PYFUNC_BASE_IMPORTS, PYFUNC_IMPORT_NAMES
from mlmodels._document import write_json
from mlmodels._errors import GateError
from mlmodels._lint_project import file_sha256
from mlmodels._replay import load_model
from mlmodels._wasm import wasm_build, wasm_trace

PYFUNC_TEMPLATE = """import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

{constants}

{function}


INPUTS = {inputs!r}
OUTPUTS = {outputs!r}


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        results = [{name}(*values) for values in zip(*(model_input[column] for column in INPUTS), strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({{column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)}})


set_model(Model())
"""


@dataclass
class ModelRecord:
    model: int
    label: str
    flavour: str
    directory: str
    file: str | None
    sha256: str
    runs: list
    constants: dict | None
    predict: object
    evaluation: dict | None = None


def model_content(ws, flavour, source, constants):
    if flavour == "static":
        values = json.loads(source) if isinstance(source, str) else dict(source)
        return None, None, values
    if flavour == "onnx":
        if not isinstance(source, bytes):
            raise GateError("Define", "source", f"flavour [onnx] needs the bytes of the graph [{type(source).__name__}]")
        return PROJECT_MODEL_FILES[flavour], source, None
    if flavour == "wasm":
        if isinstance(source, bytes):
            return PROJECT_MODEL_FILES[flavour], source, None
        function = _named_function(source)
        _check_helpers(function, constants)
        namespace = {**function.__globals__, **constants}
        rebuilt = types.FunctionType(function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__)
        features = len(inspect.signature(function).parameters)
        return PROJECT_MODEL_FILES[flavour], wasm_build(features, wasm_trace(rebuilt, features)), None
    if callable(source):
        function = _named_function(source)
        text = PYFUNC_TEMPLATE.format(
            constants=_constant_lines(constants),
            function=textwrap.dedent(inspect.getsource(function)).strip("\n"),
            inputs=ws.inputs[: len(inspect.signature(function).parameters)],
            outputs=ws.outputs,
            name=function.__name__,
        )
    else:
        text = f"{_constant_lines(constants)}\n\n{source}" if constants else source
    _check_free_names(text, set())
    return PROJECT_MODEL_FILES[flavour], text.encode(), None


def model_install(ws, model, label, flavour, runs, file_name, content, values):
    final = join(ws.path, MODEL_DIR, str(model))
    stage = f"{final}.tmp"
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    try:
        if file_name is not None:
            with open(join(stage, file_name), "wb") as model_file:
                model_file.write(content)
            sha256 = file_sha256(join(stage, file_name))
        else:
            sha256 = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
        document = {"schema": MODEL_SCHEMA, "model": model, "label": label, "flavour": flavour, "runs": runs, "sha256": sha256}
        if values is not None:
            document["constants"] = values
        write_json(join(stage, MODEL_DOCUMENT), document)
        predict = load_model(join(stage, file_name or ""), flavour, ws.signature, values)
        _probe(ws, predict, model)
        shutil.rmtree(final, ignore_errors=True)
        os.replace(stage, final)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return ModelRecord(model, label, flavour, final, file_name, sha256, runs, values, predict)


def model_orphans(ws):
    model_dir = join(ws.path, MODEL_DIR)
    if not os.path.isdir(model_dir):
        return []
    return sorted(entry for entry in os.listdir(model_dir) if entry not in {str(model) for model in ws.models})


def model_python_deps(text):
    tree = ast.parse(text)
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module}
    packages = {module: package for package, module in PYFUNC_IMPORT_NAMES.items()}
    return sorted(packages.get(name, name).replace("_", "-") for name in imported - set(sys.stdlib_module_names) - set(PYFUNC_BASE_IMPORTS))


def _named_function(source):
    if not callable(source) or getattr(source, "__name__", "<lambda>") == "<lambda>":
        raise GateError("Define", "source", f"source must be a named function [{source!r}]")
    return source


def _constant_lines(constants):
    return "\n".join(f"{name} = {value!r}" for name, value in constants.items())


def _free_names(text):
    free = set()

    def walk(table):
        for symbol in table.get_symbols():
            if table.get_type() != "module" and symbol.is_global() and symbol.is_referenced():
                free.add(symbol.get_name())
        for child in table.get_children():
            walk(child)

    table = symtable.symtable(text, "<model>", "exec")
    defined = {symbol.get_name() for symbol in table.get_symbols() if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()}
    walk(table)
    return free - defined - set(dir(builtins))


def _check_free_names(text, allowed):
    free = _free_names(text) - allowed
    if free:
        raise GateError("Define", "source", f"the model reads names that are not constants, imports or builtins {sorted(free)}")


def _check_helpers(function, constants):
    seen, pending = set(), [function]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            text = textwrap.dedent(inspect.getsource(current))
        except (OSError, TypeError) as error:
            raise GateError("Define", "source", f"the source of [{current.__name__}] cannot be read [{error}]") from error
        for name in sorted(_free_names(text) - set(constants)):
            value = current.__globals__.get(name)
            if isinstance(value, types.ModuleType) or (name in dir(maths) and value is getattr(maths, name)):
                continue
            if isinstance(value, types.FunctionType):
                pending.append(value)
            else:
                raise GateError("Define", "source", f"the function [{current.__name__}] reads the name [{name}] which is not a constant, an import, a maths operator, a function or a builtin")
        for name, value in constants.items():
            if name in current.__globals__ and current.__globals__[name] != value:
                raise GateError("Define", "constants", f"the constant [{name}] is [{value}] and the notebook holds [{current.__globals__[name]}]")


def _probe(ws, predict, model):
    required_inputs = [entry["name"] for entry in ws.signature["inputs"] if entry["parameters"]["required"]]
    frame = ws.training if "training" in ws.splits else None
    first = frame.row(0, named=True) if frame is not None and frame.height else {}
    inputs = {name: [first[name] if first.get(name) is not None else 1.0] for name in required_inputs}
    try:
        outputs = predict(inputs)
    except Exception as error:
        raise GateError("Define", "load", f"model [{model}] failed to predict [{error}]") from error
    declared = {entry["name"] for entry in ws.signature["outputs"]}
    required = {entry["name"] for entry in ws.signature["outputs"] if entry["parameters"]["required"]}
    if not required <= set(outputs) or not set(outputs) <= declared:
        raise GateError("Define", "signature", f"model [{model}] gives outputs {sorted(outputs)} and the signature requires {sorted(required)} of {sorted(declared)}")
