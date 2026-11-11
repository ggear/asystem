import subprocess
from os.path import basename, splitext

from mlmodels._constants import FOLD_KEYS, PROJECT_EVALUATION, PROJECT_SIGNATURE
from mlmodels._lint_project import file_sha256

PARAM_WIDTH = 500


def tracking_context(ws, record):
    params = {"model": record.model, "label": record.label, "flavour": record.flavour, "runs": ",".join(str(run) for run in record.runs)}
    params.update({f"constant.{name}": value for name, value in {**record.fitted, **(record.constants or {})}.items()})
    params.update({f"param.{name}": value for name, value in ws.params.items()})
    params.update({f"rows.{name}": split.frame.height for name, split in ws.splits.items()})
    metrics = {}
    if ws.folds:
        params.update({"folds": len(ws.folds), "fold_scheme": ws.folds[0]["scheme"], "fold_gap": ws.folds[0]["gap"]})
        metrics = {f"fold_{entry['fold']}/{name}": value for entry in ws.folds for name, value in entry.items() if name not in FOLD_KEYS}
    datasets = {
        name: [{"name": splitext(basename(member.path))[0], "frame": member.frame.to_pandas(), "digest": file_sha256(member.path)[:16], "source": member.path} for member in split.members]
        for name, split in ws.splits.items()
    }
    return {
        "params": params,
        "metrics": metrics,
        "datasets": datasets,
        "figures": record.figures,
        "tables": record.predictions,
        "description": f"{record.label}\n\n{_describe(ws.signature)}",
    }


def project_tracking(project_dir, manifest):
    import json
    from os.path import join

    import pandas

    datasets = {}
    if PROJECT_EVALUATION in manifest["files"]:
        with open(join(project_dir, PROJECT_EVALUATION)) as evaluation_file:
            evaluation = json.load(evaluation_file)
        datasets = {
            split: [{"name": splitext(basename(entry["path"]))[0], "frame": pandas.DataFrame(), "digest": entry["sha256"][:16], "source": None} for entry in entries]
            for split, entries in evaluation["datasets"].items()
        }
    with open(join(project_dir, PROJECT_SIGNATURE)) as signature_file:
        description = _describe(json.load(signature_file))
    return {"params": {}, "metrics": {}, "datasets": datasets, "figures": {}, "tables": {}, "description": description}


def log_tracking(tracking):
    from mlflow.data.pandas_dataset import from_pandas

    import mlflow

    mlflow.log_params({name: str(value)[:PARAM_WIDTH] for name, value in tracking["params"].items()})
    mlflow.log_metrics(tracking["metrics"])
    for split, entries in tracking["datasets"].items():
        for entry in entries:
            mlflow.log_input(from_pandas(entry["frame"], source=entry["source"], name=entry["name"], digest=entry["digest"]), context=split)
    for name, figure in tracking["figures"].items():
        mlflow.log_figure(figure, f"figures/{name}.png")
    for split, frame in tracking["tables"].items():
        mlflow.log_table(frame.to_pandas(), f"evaluation/{split}.json")


def source_tags(directory):
    try:
        completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=directory, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    return {"mlflow.source.git.commit": completed.stdout.strip()} if completed.returncode == 0 and completed.stdout.strip() else {}


def _describe(signature):
    rows = [
        f"| {section.capitalize()} | `{entry['name']}` | {entry['datatype']} | {entry['parameters']['unit']} | {'required' if entry['parameters']['required'] else 'optional'} |"
        for section in ("inputs", "outputs")
        for entry in signature[section]
    ]
    return "\n".join(["| Kind | Name | Datatype | Unit | Presence |", "|---|---|---|---|---|", *rows])
