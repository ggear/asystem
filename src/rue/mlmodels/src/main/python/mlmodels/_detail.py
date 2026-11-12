import os
from os.path import isfile

DETAIL_ENV = "MLMODELS_STAGE_DETAIL"


def record_detail(text):
    path = os.environ.get(DETAIL_ENV)
    if path:
        with open(path, "a") as detail_file:
            detail_file.write(f"{text}\n")


def take_detail(path):
    if not isfile(path):
        return None
    with open(path) as detail_file:
        lines = detail_file.read().splitlines()
    os.remove(path)
    return lines[-1] if lines else None
