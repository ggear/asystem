import os.path

from asystem.model import PROJECT_VERSION_FILE
from library.config import CONSUMER_MODEL_PATH, CONSUMER_SLOTS, MODEL_DIR, SOURCE_DIR


def consumer_project_dir(consumer, slot, source_dir=SOURCE_DIR, output_dir=None):
    if slot not in CONSUMER_SLOTS:
        raise ValueError(f"unknown consumer slot [{slot}]")
    output_dir = output_dir if output_dir is not None else os.environ.get("MODEL_OUTPUT_DIR")
    if output_dir:
        return os.path.join(output_dir, consumer, slot)
    return os.path.join(source_dir, consumer, CONSUMER_MODEL_PATH, slot)


def provenance(source, trained_on, paths, notes="", implementation=None, model_dir=MODEL_DIR):
    document = {"source": source, "trained_on": trained_on, "inputs": [os.path.relpath(path, model_dir) for path in paths], "notes": notes}
    if implementation is not None:
        document["implementation"] = implementation
    return document


def development_version(workspace, model_dir=MODEL_DIR):
    with open(os.path.join(model_dir, workspace, PROJECT_VERSION_FILE)) as version_file:
        return version_file.read().strip()
