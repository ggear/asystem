import os
import os.path
from csv import reader
from datetime import datetime

import polars as pl
from dateutil.parser import parse
from requests import post

from workbench.config import DATA_SPLITS, DATA_TIMESTAMP_FORMAT, DATA_TIMEZONE, NOTEBOOK_DIR


def data_path(workspace, split, name, timestamp=None, notebook_dir=NOTEBOOK_DIR):
    if split not in DATA_SPLITS:
        raise ValueError(f"unknown data split [{split}]")
    split_dir = os.path.join(notebook_dir, workspace, "data", split)
    if timestamp is None:
        existing = sorted(entry for entry in os.listdir(split_dir) if os.path.isfile(os.path.join(split_dir, entry, f"{name}.csv"))) if os.path.isdir(split_dir) else []
        timestamp = existing[-1] if existing else datetime.now(DATA_TIMEZONE).strftime(DATA_TIMESTAMP_FORMAT)
    return os.path.join(split_dir, timestamp, f"{name}.csv")


def read_data(workspace, split, name, timestamp=None, notebook_dir=NOTEBOOK_DIR):
    return pl.read_csv(data_path(workspace, split, name, timestamp, notebook_dir), try_parse_dates=True)


def ensure_data(workspace, split, name, build=None, timestamp=None, notebook_dir=NOTEBOOK_DIR):
    path = data_path(workspace, split, name, timestamp, notebook_dir)
    if not os.path.isfile(path):
        if build is None:
            raise FileNotFoundError(f"{split} data absent and no builder given [{path}]")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pl.DataFrame(build()).write_csv(path)
    return pl.read_csv(path), path


def golden_data(workspace, name, build=None, timestamp=None, notebook_dir=NOTEBOOK_DIR):
    return ensure_data(workspace, "golden", name, build, timestamp, notebook_dir)


def query_influxdb3(env, query, workspace, split, name, timestamp=None, database=None, force=False, notebook_dir=NOTEBOOK_DIR):
    path = data_path(workspace, split, name, timestamp, notebook_dir)
    if os.path.isfile(path) and not force:
        with open(path) as data_file:
            return _parse_csv(data_file.read())
    response = post(
        url="http://{}:{}/api/v3/query_sql".format(env["INFLUXDB3_IP_PROD"], env["INFLUXDB3_API_PORT"]),
        headers={"Accept": "text/csv", "Content-type": "application/json", "Authorization": "Bearer {}".format(env["INFLUXDB3_TOKEN_ADMIN"])},
        json={"db": database if database is not None else env["INFLUXDB3_DATABASE_HOME"], "q": query, "format": "csv"},
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(f"query failed status [{response.status_code}] body [{response.text.strip()}]")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(f"{path}.tmp", "w") as data_file:
        data_file.write(response.text)
    os.replace(f"{path}.tmp", path)
    return _parse_csv(response.text)


def _parse_csv(text):
    lines = text.strip().split("\n")
    if len(lines) < 2:
        return []
    header = next(reader([lines[0]]))
    return [[parse(col) if key == "time" and col else col for key, col in zip(header, cols, strict=False)] for cols in reader(lines[1:])]
