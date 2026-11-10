import io
import logging
import os.path
import re
import time
from dataclasses import dataclass

import polars as pl
from requests import post

from mlmodels._errors import GateError

LOG = logging.getLogger(__name__)


@dataclass
class RunData:
    frame: object
    path: str
    live: bool


def log_run(run, label, cached, rows, started):
    LOG.info("Collect run [%s] [%s] with rows [%6s] cached [%s] seconds [%.2f]", run, label, rows, cached, time.perf_counter() - started)


def capture_source(ws, source, query, database, csv, build):
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
        columns, depth, current = [], 0, ""
        for character in select:
            depth += character == "("
            depth -= character == ")"
            if character == "," and depth == 0:
                columns.append(current)
                current = ""
            else:
                current += character
        columns.append(current)
        return pl.DataFrame({re.split(r"\s+(?:AS\s+)?", entry.strip())[-1]: [] for entry in columns if entry.strip()})
    suffix = (database if database is not None else "wrangle").upper()
    try:
        uri = "postgresql://{}:{}@{}:{}/{}".format(
            ws.env[f"POSTGRES_USER_{suffix}"], ws.env[f"POSTGRES_PASSWORD_{suffix}"], ws.env["POSTGRES_IP_PROD"], ws.env["POSTGRES_API_PORT"], ws.env[f"POSTGRES_DATABASE_{suffix}"]
        )
    except KeyError as error:
        raise GateError("Data", "connection", f"env is missing [{error.args[0]}] so declare postgres in run_deps.txt and run fab generate") from error
    return pl.read_database_uri(query, uri, engine="adbc")


def read_frame(path, parse_dates):
    with open(path, "rb") as data_file:
        if not data_file.read().strip():
            return pl.DataFrame()
    return pl.read_csv(path, try_parse_dates=parse_dates)
