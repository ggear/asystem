import json
import logging
import os.path
import time
from datetime import datetime

from mlmodels._collect import RunData, capture_source, read_frame
from mlmodels._config import DATA_SCHEMA, DATA_SOURCES, DATA_SOURCES_QUERIED, DATA_TIMESTAMP_FORMAT, DATA_TIMEZONE
from mlmodels._constants import RUN_FIRST
from mlmodels._detail import record_detail
from mlmodels._document import write_json
from mlmodels._errors import GateError
from mlmodels._lint_project import file_sha256

LOG = logging.getLogger(__name__)


def collect_run(ws, run, *, label, name=None, source=None, query=None, params=None, database=None, csv=None, build=None, live=False):
    if isinstance(run, bool) or not isinstance(run, int) or run < RUN_FIRST:
        raise ValueError(f"run must be an integer from [{RUN_FIRST}] [{run}]")
    if not isinstance(label, str) or not label.strip():
        raise ValueError(f"label must be the readable intent of run [{run}] [{label}]")
    if name is None:
        name = ws.model_name.split("_", 1)[1]
    if query is not None and params is not None:
        query = query.format(**params)
    started = time.perf_counter()

    def log_run(cached, rows):
        LOG.info("Collect run [%s] [%s] with rows [%6s] cached [%s] seconds [%.2f]", run, label, rows, cached, time.perf_counter() - started)

    data_dir = os.path.join(ws.path, "data")
    path = os.path.join(data_dir, str(run), f"{name}.csv")
    meta_path = f"{path[: -len('.csv')]}.json"
    if os.path.isfile(path) and not live:
        if not os.path.isfile(meta_path):
            raise GateError("Collect", "cache", f"cached [{run}/{name}] has a csv and no json, a capture was interrupted, delete the csv to capture it again")
        with open(meta_path) as meta_file:
            meta = json.load(meta_file)
        for key, value in (("source", source), ("query", query), ("params", params)):
            if value is not None and meta.get(key) != value:
                raise GateError("Collect", "cache", f"cached [{run}/{name}] has {key} [{meta.get(key)}] and the notebook gives [{value}], delete its csv and json to capture it again")
        frame = read_frame(path, meta.get("source") in DATA_SOURCES_QUERIED)
        log_run(True, frame.height)
    else:
        if source not in DATA_SOURCES:
            raise ValueError(f"data absent so source must be one of {list(DATA_SOURCES)} [{source}] for [{path}]")
        frame = capture_source(ws, source, query, database, csv, build)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        frame.write_csv(f"{path}.tmp")
        os.replace(f"{path}.tmp", path)
        write_json(
            meta_path,
            {
                "schema": DATA_SCHEMA,
                "run": run,
                "label": label,
                "live": live,
                "name": name,
                "source": source,
                "query": query,
                "params": params,
                "database": database,
                "captured": datetime.now(DATA_TIMEZONE).strftime(DATA_TIMESTAMP_FORMAT),
                "rows": frame.height,
                "sha256": file_sha256(path),
            },
        )
        frame = read_frame(path, source in DATA_SOURCES_QUERIED)
        log_run(False, frame.height)
    ws.runs[(run, name)] = RunData(frame, path, live)
    runs = len({number for number, _ in ws.runs})
    record_detail(f"{runs} run{'' if runs == 1 else 's'} {sum(data.frame.height for data in ws.runs.values())} rows")
