import logging
from os.path import join, relpath

import polars as pl

from mlmodels._config import PINS_PATH, VERSION_PATH
from mlmodels._constants import PROJECT_MANIFEST, PROJECT_SIGNATURE_ERROR
from mlmodels._errors import GateError
from mlmodels._lint_project import file_sha256
from mlmodels._metadata import record_project
from mlmodels._model import model_orphans, model_python_deps
from mlmodels._project import write_project
from mlmodels._replay import replay_project
from mlmodels._signature import cell, golden_document, golden_step

LOG = logging.getLogger(__name__)


def package_model(ws, model, golden, *, target, tolerance=None):
    if model not in ws.models:
        raise GateError("Package", "model", f"model [{model}] was not defined, call define_model first")
    orphans = model_orphans(ws)
    if orphans:
        raise GateError("Package", "orphan", f"model directories were not defined by this run {orphans}, delete them to retire the models")
    record = ws.models[model]
    if record.flavour != "static" and record.evaluation is None:
        raise GateError("Package", "evaluation", f"model [{model}] has no evaluate_gate result")
    required = {entry["name"] for entry in ws.signature["inputs"] if entry["parameters"]["required"]}
    state_in = [entry["name"] for entry in ws.signature["inputs"] if entry["shape"] == [-1]]
    state_out = [entry["name"] for entry in ws.signature["outputs"] if entry["shape"] == [-1]]
    input_specs = {entry["name"]: entry for entry in ws.signature["inputs"]}
    frame = golden if isinstance(golden, pl.DataFrame) else pl.DataFrame(golden)
    sequences, state, previous = {}, None, None
    for index, row in enumerate(frame.iter_rows(named=True)):
        sequence = row.get("sequence") or "golden"
        if sequence != previous:
            state, previous = None, sequence
        inputs = {name: cell(input_specs[name], row[name]) for name in ws.inputs if row.get(name) is not None}
        for name in state_in:
            if name not in inputs and state is not None:
                inputs[name] = state
        steps = sequences.setdefault(sequence, [])
        step_id = f"s{list(sequences).index(sequence) + 1}-{len(steps)}"
        if row.get("expect") == "error":
            if required <= inputs.keys():
                raise GateError("Package", "golden", f"golden row [{index}] expects an error and supplies every required input")
            steps.append(golden_step(ws.signature, step_id, inputs, error=PROJECT_SIGNATURE_ERROR))
            continue
        if not required <= inputs.keys():
            raise GateError("Package", "golden", f"golden row [{index}] is missing required inputs {sorted(required - inputs.keys())}")
        outputs = record.predict({name: value if isinstance(value, list) else [value] for name, value in inputs.items()})
        if state_out and state_out[0] in outputs:
            state = outputs[state_out[0]]
        steps.append(golden_step(ws.signature, step_id, inputs, outputs))
    golden_doc = golden_document(list(sequences.items()), tolerance)
    model_path = join(record.directory, record.file) if record.file else None
    static = record.flavour == "static"
    held = {path for split, selection in ws.splits.items() if split != "training" for path, _ in selection.paths}
    runs = [relpath(data.path, ws.notebook_dir) for (run, _), data in sorted(ws.runs.items()) if run in record.runs and data.path not in held]
    provenance = {"source": "static" if static else "manual", "trained_on": f"runs {record.runs}" if record.runs else "none", "inputs": runs, "notes": record.label}
    if not static:
        provenance["implementation"] = {"pyfunc": "mlflow.pyfunc model.py", "wasm": "WebAssembly traced and built by define_model", "onnx": "ONNX graph built by the notebook"}[
            record.flavour
        ] + f", model {model}"
    python_deps = None
    if record.flavour == "pyfunc":
        with open(join(record.directory, str(record.file))) as model_file:
            python_deps = model_python_deps(model_file.read())
    write_project(
        ws.project_dir,
        ws.model_name,
        record.flavour,
        ws.signature,
        golden_doc,
        provenance,
        constants=record.constants if static else None,
        model_path=model_path,
        evaluation=record.evaluation,
        python_deps=python_deps,
        model_id=model,
    )
    if model_path is not None and file_sha256(model_path) != file_sha256(join(ws.project_dir, record.file)):
        raise GateError("Package", "candidate", f"the project model file differs from model [{model}]")
    findings = replay_project(ws.project_dir)
    if findings:
        raise GateError("Package", "replay", "; ".join(f"{rule} {message}" for rule, message in findings))
    ws.target = target
    record_project(ws.path, ws.project_dir, target, PINS_PATH, VERSION_PATH)
    LOG.info("Package model [%s] [%s] as [%s] to target [%s] with project [%s]", model, record.label, record.flavour, target["kind"], file_sha256(join(ws.project_dir, PROJECT_MANIFEST))[:12])
    LOG.info("Package replayed [%s] golden steps exactly through the shipped runtime", sum(len(steps) for steps in sequences.values()))
