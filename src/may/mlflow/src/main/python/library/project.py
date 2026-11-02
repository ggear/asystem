import os.path

from library.config import CONSUMER_MODEL_PATH, CONSUMER_SLOTS, MODEL_DIR, SOURCE_DIR


def consumer_project_dir(consumer, slot, source_dir=SOURCE_DIR):
    if slot not in CONSUMER_SLOTS:
        raise ValueError(f"unknown consumer slot [{slot}]")
    return os.path.join(source_dir, consumer, CONSUMER_MODEL_PATH, slot)


def provenance(source, trained_on, paths, notes="", implementation=None, model_dir=MODEL_DIR):
    document = {"source": source, "trained_on": trained_on, "inputs": [os.path.relpath(path, model_dir) for path in paths], "notes": notes}
    if implementation is not None:
        document["implementation"] = implementation
    return document
