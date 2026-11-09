import hashlib
import io
import json
import logging
import os
import os.path
import time
from datetime import datetime

import polars as pl
from requests import post

from workbench.config import DATA_SOURCES, DATA_SOURCES_QUERIED, DATA_SPLITS, DATA_TIMESTAMP_FORMAT, DATA_TIMEZONE
from workbench.document import write_json
from workbench.errors import GateError

DATA_SCHEMA = 1
LOG = logging.getLogger(__name__)


def data_load(ws, split, name, *, run, source=None, query=None, params=None, database=None, csv=None, build=None, force=False):
    if split not in DATA_SPLITS:
        raise ValueError(f"unknown data split [{split}]")
    if isinstance(run, bool) or not isinstance(run, int) or run < 1:
        raise ValueError(f"run must be an integer from 1 [{run}]")
    if query is not None and params is not None:
        query = query.format(**params)
    started = time.perf_counter()
    path = os.path.join(ws.path, "data", split, str(run), f"{name}.csv")
    meta_path = f"{path[: -len('.csv')]}.json"
    if os.path.isfile(path) and not force:
        meta = _read_meta(meta_path)
        if meta is not None:
            for key, value in (("source", source), ("query", query), ("params", params)):
                if value is not None and meta.get(key) != value:
                    raise GateError("Data", "cache", f"cached [{split}/{run}/{name}] has {key} [{meta.get(key)}] and the notebook gives [{value}], pass force to capture it again")
        cached_source = source if source is not None else (meta or {}).get("source")
        frame = _read_frame(path, meta is not None and meta.get("source") in DATA_SOURCES_QUERIED)
        _log_load(split, run, name, cached_source, True, frame.height, started)
        return frame, path
    if source not in DATA_SOURCES:
        raise ValueError(f"data absent so source must be one of {list(DATA_SOURCES)} [{source}] for [{path}]")
    frame = _capture(ws, source, query, database, csv, build)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frame.write_csv(f"{path}.tmp")
    os.replace(f"{path}.tmp", path)
    with open(path, "rb") as data_file:
        digest = hashlib.sha256(data_file.read()).hexdigest()
    write_json(
        meta_path,
        {
            "schema": DATA_SCHEMA,
            "split": split,
            "run": run,
            "name": name,
            "source": source,
            "query": query,
            "params": params,
            "database": database,
            "captured": datetime.now(DATA_TIMEZONE).strftime(DATA_TIMESTAMP_FORMAT),
            "rows": frame.height,
            "sha256": digest,
        },
    )
    frame = _read_frame(path, source in DATA_SOURCES_QUERIED)
    _log_load(split, run, name, source, False, frame.height, started)
    return frame, path


def _log_load(split, run, name, source, cached, rows, started):
    LOG.info(
        "data load split [%s] run [%s] name [%s] source [%s] cached [%s] rows [%s] seconds [%.2f]",
        split,
        run,
        name,
        source,
        cached,
        rows,
        time.perf_counter() - started,
    )


def _capture(ws, source, query, database, csv, build):
    if source == "builder":
        if build is None:
            raise ValueError("source [builder] needs build")
        return pl.DataFrame(build())
    if source == "csv":
        if csv is None or not os.path.isfile(csv):
            raise FileNotFoundError(f"source [csv] needs an existing csv [{csv}]")
        return pl.read_csv(csv)
    if query is None:
        raise ValueError(f"source [{source}] needs query")
    if source == "influxdb3":
        response = post(
            url="http://{}:{}/api/v3/query_sql".format(ws.env["INFLUXDB3_IP_PROD"], ws.env["INFLUXDB3_API_PORT"]),
            headers={"Accept": "text/csv", "Content-type": "application/json", "Authorization": "Bearer {}".format(ws.env["INFLUXDB3_TOKEN_ADMIN"])},
            json={"db": database if database is not None else ws.env["INFLUXDB3_DATABASE_HOME"], "q": query, "format": "csv"},
            timeout=120,
        )
        if not response.ok:
            raise RuntimeError(f"query failed status [{response.status_code}] body [{response.text.strip()}]")
        if response.text.strip():
            return pl.read_csv(io.StringIO(response.text), try_parse_dates=True)
        select = query[query.index("SELECT") + len("SELECT") : query.index("\nFROM")] if "\nFROM" in query else ""
        return pl.DataFrame({name.strip(): [] for name in select.split(",") if name.strip()})
    suffix = (database if database is not None else "wrangle").upper()
    try:
        uri = "postgresql://{}:{}@{}:{}/{}".format(
            ws.env[f"POSTGRES_USER_{suffix}"], ws.env[f"POSTGRES_PASSWORD_{suffix}"], ws.env["POSTGRES_IP_PROD"], ws.env["POSTGRES_API_PORT"], ws.env[f"POSTGRES_DATABASE_{suffix}"]
        )
    except KeyError as error:
        raise GateError("Data", "connection", f"env is missing [{error.args[0]}] so declare postgres in run_deps.txt and run fab generate") from error
    return pl.read_database_uri(query, uri, engine="adbc")


def _read_frame(path, parse_dates):
    with open(path, "rb") as data_file:
        if not data_file.read().strip():
            return pl.DataFrame()
    return pl.read_csv(path, try_parse_dates=parse_dates)


def _read_meta(path):
    if not os.path.isfile(path):
        return None
    with open(path) as meta_file:
        return json.load(meta_file)
