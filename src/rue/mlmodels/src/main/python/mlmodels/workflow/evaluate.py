import logging

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from mlmodels._constants import ACCEPTANCE_SPLITS
from mlmodels._errors import GateError
from mlmodels._project import evaluation_build

LOG = logging.getLogger(__name__)


def evaluate_model(ws, model, split):
    record = _record(ws, model)
    frame = getattr(ws, split)
    required = [entry["name"] for entry in ws.signature["inputs"] if entry["parameters"]["required"]]
    state_in = [entry["name"] for entry in ws.signature["inputs"] if entry["shape"] == [-1]]
    state_out = [entry["name"] for entry in ws.signature["outputs"] if entry["shape"] == [-1]]
    outputs = [name for name in ws.outputs if name not in state_out]
    predicted = {name: [] for name in outputs}
    state = None
    for row in frame.iter_rows(named=True):
        inputs = {name: [row[name]] for name in ws.inputs if name in row and row[name] is not None and name not in state_in}
        if state is not None:
            inputs.update(dict.fromkeys(state_in, state))
        if not set(required) <= inputs.keys():
            for name in outputs:
                predicted[name].append(None)
            continue
        answer = record.predict(inputs)
        for name in outputs:
            predicted[name].append(answer[name][0])
        if state_out and state_out[0] in answer:
            state = answer[state_out[0]]
    kept = [name for name in frame.columns if name == "time" or (name not in ws.inputs and name not in ws.outputs)]
    return pl.DataFrame(
        {
            **{name: frame[name] for name in kept if name == "time"},
            **{name: pl.Series(name, values, dtype=pl.Float64) for name, values in predicted.items()},
            **{name: frame[name] for name in kept if name != "time"},
        }
    )


def evaluate_metrics(truth, predicted):
    truth = np.asarray(truth, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if truth.size == 0 or truth.shape != predicted.shape:
        raise ValueError(f"metrics need equal non-empty samples [{truth.shape}] [{predicted.shape}]")
    error = predicted - truth
    spread = float(np.sum((truth - truth.mean()) ** 2))
    constant = truth.size < 2 or float(truth.std()) == 0.0 or float(predicted.std()) == 0.0
    return {
        "rmse": float(np.sqrt(np.mean(error**2))),
        "mae": float(np.mean(np.abs(error))),
        "max_abs_error": float(np.max(np.abs(error))),
        "bias": float(np.mean(error)),
        "p95_abs_error": float(np.percentile(np.abs(error), 95)),
        "r2": None if spread == 0.0 else float(1.0 - np.sum(error**2) / spread),
        "pearson_r": None if constant else float(np.corrcoef(truth, predicted)[0, 1]),
    }


def evaluate_gate(ws, model, checks):
    record = _record(ws, model)
    datasets = {split: ws.splits[split].paths for split in ACCEPTANCE_SPLITS if split in ws.splits}
    record.evaluation = evaluation_build(checks, datasets)
    if ws.folds:
        record.evaluation["folds"] = ws.folds
    for entry in record.evaluation["checks"]:
        LOG.info(
            "Evaluate model [%s] [%s] on [%s] check [%s] measured [%s] limit [%s] passed [%s]",
            model,
            record.label,
            entry["split"],
            entry["name"],
            round(entry["value"], 2),
            entry["limit"],
            entry["passed"],
        )
    return record.evaluation


def evaluate_models(ws):
    for model, record in sorted(ws.models.items()):
        LOG.info("Evaluate model [%s] [%s] as [%s] verdict [%s]", model, record.label, record.flavour, _verdict(record))


def evaluate_plot(ws, models, split, *, reference=None, title=None):
    frame = getattr(ws, split)
    output = ws.outputs[0]
    axis = frame["time"] if "time" in frame.columns else frame[ws.inputs[0]]
    figure, (top, bottom) = plt.subplots(2, 1, figsize=(16, 10), sharex=True)
    predictions = {model: evaluate_model(ws, model, split)[output].to_numpy() for model in models}
    for model, predicted in predictions.items():
        record = _record(ws, model)
        passed = record.evaluation is not None and record.evaluation["passed"]
        style = {"linewidth": 2.5, "alpha": 1.0} if passed else {"linewidth": 1.0, "alpha": 0.5}
        top.plot(axis, predicted, label=f"{model} {record.label}, {_verdict(record)}", **style)
        if reference is not None:
            bottom.plot(axis, predicted - predictions[reference], label=f"{model} {record.label}", **style)
    if reference is not None:
        bottom.axhline(0, color="black", linewidth=1)
        bottom.set_title(f"Difference of each model from model {reference}, above 0 reads higher")
        bottom.set_ylabel("difference")
    if title is not None:
        figure.suptitle(title)
    top.set_title(f"Prediction of each model on {split}")
    top.set_ylabel(output)
    for axes in (top, bottom):
        axes.grid(alpha=0.3)
        axes.legend(loc="best")
    figure.tight_layout()


def _verdict(record):
    if record.evaluation is None:
        return "not gated"
    failed = [entry["name"] for entry in record.evaluation["checks"] if entry["gate"] and not entry["passed"]]
    return f"failed on {', '.join(failed)}" if failed else "passed"


def _record(ws, model):
    if model not in ws.models:
        raise GateError("Evaluate", "model", f"model [{model}] was not defined, call define_model first")
    return ws.models[model]
