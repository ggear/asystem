import collections
import contextlib
import copy
import datetime
import fcntl
import hashlib
import json
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import orjson

from .config import TIMEOUT_RUN_SECONDS
from .logger import print_log

HISTORY_RAW_RUN_LENGTH = 50
HISTORY_AGG_DAY_LENGTH = 350

HISTORY_RAW_LABELS = {
    15: "12h",
    30: "1d",
    60: "2d",
    90: "3d",
    120: "4d",
    180: "1w",
}

CTR_SRC_DATA = "Data"
CTR_SRC_FILES = "Files"
CTR_SRC_EGRESS = "Egress"
CTR_SRC_SOURCES = "Sources"
CTR_SRC_TIMING = "Timings"

CTR_ACT_PREVIOUS_ROWS = "Previous Rows"
CTR_ACT_PREVIOUS_COLUMNS = "Previous Columns"
CTR_ACT_CURRENT_ROWS = "Current Rows"
CTR_ACT_CURRENT_COLUMNS = "Current Columns"
CTR_ACT_UPDATE_ROWS = "Update Rows"
CTR_ACT_UPDATE_COLUMNS = "Update Columns"
CTR_ACT_DELTA_ROWS = "Delta Rows"
CTR_ACT_DELTA_COLUMNS = "Delta Columns"
CTR_ACT_SHEET_ROWS = "Sheet Rows"
CTR_ACT_SHEET_COLUMNS = "Sheet Columns"
CTR_ACT_DATABASE_ROWS = "Database Rows"
CTR_ACT_DATABASE_COLUMNS = "Database Columns"
CTR_ACT_ERRORED = "Errored"
CTR_ACT_PROCESSED = "Processed"
CTR_ACT_SKIPPED = "Skipped"
CTR_ACT_DOWNLOADED = "Downloaded"
CTR_ACT_CACHED = "Cached"
CTR_ACT_PERSISTED = "Persisted"
CTR_ACT_UPLOADED = "Uploaded"
CTR_ACT_MARSHALL_MILLIS = "Marshall Millis"
CTR_ACT_PROCESS_MILLIS = "Process Millis"
CTR_ACT_EGRESS_MILLIS = "Egress Millis"
CTR_ACT_TOTAL_MILLIS = "Total Millis"

AGG_SUM, AGG_MIN, AGG_MAX, AGG_MEAN = "sum", "min", "max", "mean"

CTR_LBL_PAD = '.'
CTR_LBL_WIDTH = 26
CTR_TZ = datetime.timezone(datetime.timedelta(hours=8))

__all__ = [
    # Primary classes
    "View",
    "Snapshot",
    "RunHistory",
    "Counter",
    "CountersMixin",
    "COUNTERS",
    "aggregate_summary",
    # Counter sources
    "CTR_SRC_SOURCES",
    "CTR_SRC_FILES",
    "CTR_SRC_DATA",
    "CTR_SRC_EGRESS",
    "CTR_SRC_TIMING",
    # Counter actions
    "CTR_ACT_ERRORED",
    "CTR_ACT_PROCESSED",
    "CTR_ACT_SKIPPED",
    "CTR_ACT_DOWNLOADED",
    "CTR_ACT_CACHED",
    "CTR_ACT_PERSISTED",
    "CTR_ACT_UPLOADED",
    "CTR_ACT_PREVIOUS_ROWS",
    "CTR_ACT_PREVIOUS_COLUMNS",
    "CTR_ACT_CURRENT_ROWS",
    "CTR_ACT_CURRENT_COLUMNS",
    "CTR_ACT_UPDATE_ROWS",
    "CTR_ACT_UPDATE_COLUMNS",
    "CTR_ACT_DELTA_ROWS",
    "CTR_ACT_DELTA_COLUMNS",
    "CTR_ACT_SHEET_ROWS",
    "CTR_ACT_SHEET_COLUMNS",
    "CTR_ACT_DATABASE_ROWS",
    "CTR_ACT_DATABASE_COLUMNS",
    "CTR_ACT_MARSHALL_MILLIS",
    "CTR_ACT_PROCESS_MILLIS",
    "CTR_ACT_EGRESS_MILLIS",
    "CTR_ACT_TOTAL_MILLIS",
    # Aggregation modes
    "AGG_SUM",
    "AGG_MIN",
    "AGG_MAX",
    "AGG_MEAN",
    # History constants
    "HISTORY_RAW_RUN_LENGTH",
    "HISTORY_AGG_DAY_LENGTH",
    "HISTORY_RAW_LABELS",
    # Label formatting
    "CTR_TZ",
    "CTR_LBL_PAD",
    "CTR_LBL_WIDTH",
]


@dataclass(frozen=True)
class Counter:
    source: str
    action: str
    label: str
    aggregator: str
    format: str
    error: bool = False


COUNTERS: dict[tuple[str, str], Counter] = {(c.source, c.action): c for c in [
    Counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED, "Sources Downloaded", AGG_SUM, "count"),
    Counter(CTR_SRC_SOURCES, CTR_ACT_CACHED, "Sources Cached", AGG_SUM, "count"),
    Counter(CTR_SRC_SOURCES, CTR_ACT_SKIPPED, "Sources Skipped", AGG_SUM, "count"),
    Counter(CTR_SRC_SOURCES, CTR_ACT_UPLOADED, "Sources Uploaded", AGG_SUM, "count"),
    Counter(CTR_SRC_SOURCES, CTR_ACT_PERSISTED, "Sources Persisted", AGG_SUM, "count"),
    Counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED, "Sources Errored", AGG_SUM, "count", error=True),
    Counter(CTR_SRC_FILES, CTR_ACT_PROCESSED, "Files Processed", AGG_SUM, "count"),
    Counter(CTR_SRC_FILES, CTR_ACT_SKIPPED, "Files Skipped", AGG_SUM, "count"),
    Counter(CTR_SRC_FILES, CTR_ACT_ERRORED, "Files Errored", AGG_SUM, "count", error=True),
    Counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_COLUMNS, "Data Previous Columns", AGG_MAX, "count"),
    Counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_ROWS, "Data Previous Rows", AGG_MAX, "count"),
    Counter(CTR_SRC_DATA, CTR_ACT_CURRENT_COLUMNS, "Data Current Columns", AGG_MAX, "count"),
    Counter(CTR_SRC_DATA, CTR_ACT_CURRENT_ROWS, "Data Current Rows", AGG_MAX, "count"),
    Counter(CTR_SRC_DATA, CTR_ACT_UPDATE_COLUMNS, "Data Update Columns", AGG_MAX, "count"),
    Counter(CTR_SRC_DATA, CTR_ACT_UPDATE_ROWS, "Data Update Rows", AGG_SUM, "count"),
    Counter(CTR_SRC_DATA, CTR_ACT_DELTA_COLUMNS, "Data Delta Columns", AGG_MAX, "count"),
    Counter(CTR_SRC_DATA, CTR_ACT_DELTA_ROWS, "Data Delta Rows", AGG_SUM, "count"),
    Counter(CTR_SRC_DATA, CTR_ACT_ERRORED, "Data Errored", AGG_SUM, "count", error=True),
    Counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_COLUMNS, "Egress Sheet Columns", AGG_MAX, "count"),
    Counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_ROWS, "Egress Sheet Rows", AGG_SUM, "count"),
    Counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_COLUMNS, "Egress Database Columns", AGG_MAX, "count"),
    Counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_ROWS, "Egress Database Rows", AGG_SUM, "count"),
    Counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED, "Egress Errored", AGG_SUM, "count", error=True),
    Counter(CTR_SRC_TIMING, CTR_ACT_MARSHALL_MILLIS, "Marshall Millis", AGG_MAX, "duration_ms"),
    Counter(CTR_SRC_TIMING, CTR_ACT_PROCESS_MILLIS, "Process Millis", AGG_MAX, "duration_ms"),
    Counter(CTR_SRC_TIMING, CTR_ACT_EGRESS_MILLIS, "Egress Millis", AGG_MAX, "duration_ms"),
    Counter(CTR_SRC_TIMING, CTR_ACT_TOTAL_MILLIS, "Total Millis", AGG_MAX, "duration_ms"),
]}

_EXPECTED_COUNTER_ACTIONS = {
    CTR_SRC_SOURCES: [
        CTR_ACT_DOWNLOADED, CTR_ACT_CACHED, CTR_ACT_SKIPPED,
        CTR_ACT_UPLOADED, CTR_ACT_PERSISTED, CTR_ACT_ERRORED,
    ],
    CTR_SRC_FILES: [
        CTR_ACT_PROCESSED, CTR_ACT_SKIPPED, CTR_ACT_ERRORED,
    ],
    CTR_SRC_DATA: [
        CTR_ACT_PREVIOUS_COLUMNS, CTR_ACT_PREVIOUS_ROWS,
        CTR_ACT_CURRENT_COLUMNS, CTR_ACT_CURRENT_ROWS,
        CTR_ACT_UPDATE_COLUMNS, CTR_ACT_UPDATE_ROWS,
        CTR_ACT_DELTA_COLUMNS, CTR_ACT_DELTA_ROWS,
        CTR_ACT_ERRORED,
    ],
    CTR_SRC_EGRESS: [
        CTR_ACT_SHEET_COLUMNS, CTR_ACT_SHEET_ROWS,
        CTR_ACT_DATABASE_COLUMNS, CTR_ACT_DATABASE_ROWS,
        CTR_ACT_ERRORED,
    ],
    CTR_SRC_TIMING: [
        CTR_ACT_MARSHALL_MILLIS, CTR_ACT_PROCESS_MILLIS,
        CTR_ACT_EGRESS_MILLIS, CTR_ACT_TOTAL_MILLIS,
    ],
}

_EXPECTED_COUNTER_KEYS = {
    (source, action)
    for source, actions in _EXPECTED_COUNTER_ACTIONS.items()
    for action in actions
}

assert set(COUNTERS) == _EXPECTED_COUNTER_KEYS, (
    f"COUNTERS missing: {_EXPECTED_COUNTER_KEYS - set(COUNTERS)}; "
    f"extras: {set(COUNTERS) - _EXPECTED_COUNTER_KEYS}"
)


class CountersMixin:
    _counters: dict[str, dict[str, int]]

    def reset_counters(self):
        self._counters = {}
        for (source, action) in COUNTERS:
            if source not in self._counters:
                self._counters[source] = {}
            self._counters[source][action] = 0

    def add_counter(self, source, action, count=1):
        self._counters[source][action] += count

    def get_counter(self, source, action):
        return self._counters[source][action]

    def get_counters(self):
        return copy.deepcopy(self._counters)

    def counters_set_all_errored(self, source):
        not_errored = self.get_counter(source, CTR_ACT_PROCESSED) + self.get_counter(source, CTR_ACT_SKIPPED) - self.get_counter(source, CTR_ACT_ERRORED)
        self.add_counter(source, CTR_ACT_ERRORED, not_errored)

    def print_counters(self):
        self.print_log("Execution Summary:")  # type: ignore[attr-defined]
        for source in self._counters:
            for action in self._counters[source]:
                self.print_log(  # type: ignore[attr-defined]
                    f"     {' '.join((source, action)).ljust(CTR_LBL_WIDTH, CTR_LBL_PAD)} "
                    f"{self._counters[source][action]:8}"
                )


_RAW_FILENAME = "history_raw.json"
_DAILY_FILENAME = "history_daily.json"
_ADHOC_FILENAME = "history_adhoc.json"
_RUN_LOCK_FILENAME = "wrangle-run.lock"

_SRC_ENC = {
    CTR_SRC_SOURCES: "sr",
    CTR_SRC_FILES: "fi",
    CTR_SRC_DATA: "da",
    CTR_SRC_EGRESS: "eg",
    CTR_SRC_TIMING: "ti",
}
_SRC_DEC = {v: k for k, v in _SRC_ENC.items()}

_ACT_ENC = {
    CTR_ACT_ERRORED: "er",
    CTR_ACT_PROCESSED: "pr",
    CTR_ACT_SKIPPED: "sk",
    CTR_ACT_DOWNLOADED: "dl",
    CTR_ACT_CACHED: "ca",
    CTR_ACT_PERSISTED: "pe",
    CTR_ACT_UPLOADED: "ul",
    CTR_ACT_PREVIOUS_ROWS: "pvr",
    CTR_ACT_PREVIOUS_COLUMNS: "pvc",
    CTR_ACT_CURRENT_ROWS: "cur",
    CTR_ACT_CURRENT_COLUMNS: "cuc",
    CTR_ACT_UPDATE_ROWS: "upr",
    CTR_ACT_UPDATE_COLUMNS: "upc",
    CTR_ACT_DELTA_ROWS: "dtr",
    CTR_ACT_DELTA_COLUMNS: "dtc",
    CTR_ACT_SHEET_ROWS: "shr",
    CTR_ACT_SHEET_COLUMNS: "shc",
    CTR_ACT_DATABASE_ROWS: "dbr",
    CTR_ACT_DATABASE_COLUMNS: "dbc",
    CTR_ACT_MARSHALL_MILLIS: "mms",
    CTR_ACT_PROCESS_MILLIS: "pms",
    CTR_ACT_EGRESS_MILLIS: "ems",
    CTR_ACT_TOTAL_MILLIS: "tms",
}
_ACT_DEC = {v: k for k, v in _ACT_ENC.items()}

_CELL_ENC = {"sum": "s", "min": "n", "max": "x", "count": "c"}
_CELL_DEC = {v: k for k, v in _CELL_ENC.items()}

_SCHEMA = {
    "raw_entry": ["ts", "bucket", "plugins", "errored"],
    "day_entry": ["date", "errored_runs", "buckets"],
    "bucket_cell": ["s", "n", "x", "c"],
    "key_encoding": "v2_short",
}
_SCHEMA_FINGERPRINT = hashlib.sha256(json.dumps(_SCHEMA, sort_keys=True).encode()).hexdigest()[:8]


def _period_bucket(ts: datetime.datetime, poll_period_minutes: int) -> int | None:
    if poll_period_minutes <= 0:
        return None
    return int(ts.timestamp()) // (poll_period_minutes * 60)


def _encode_raw_entry(entry: dict) -> dict:
    encoded_plugins = {}
    for plugin_name, sources in entry["plugins"].items():
        encoded_sources = {}
        for source, actions in sources.items():
            encoded_sources[_SRC_ENC.get(source, source)] = {_ACT_ENC.get(action, action): value for action, value in actions.items()}
        encoded_plugins[plugin_name] = encoded_sources
    return {"ts": entry["ts"], "bucket": entry.get("bucket"), "plugins": encoded_plugins, "errored": entry["errored"]}


def _decode_raw_entry(entry: dict) -> dict:
    decoded_plugins = {}
    for plugin_name, sources in entry["plugins"].items():
        decoded_sources = {}
        for src_key, actions in sources.items():
            decoded_sources[_SRC_DEC.get(src_key, src_key)] = {_ACT_DEC.get(act_key, act_key): value for act_key, value in actions.items()}
        decoded_plugins[plugin_name] = decoded_sources
    return {"ts": entry["ts"], "bucket": entry.get("bucket"), "plugins": decoded_plugins, "errored": entry["errored"]}


def _encode_day_entry(entry: dict) -> dict:
    encoded_buckets = {}
    for plugin_name, sources in entry["buckets"].items():
        encoded_sources = {}
        for source, actions in sources.items():
            encoded_actions = {}
            for action, cell in actions.items():
                encoded_actions[_ACT_ENC.get(action, action)] = {_CELL_ENC.get(k, k): v for k, v in cell.items()}
            encoded_sources[_SRC_ENC.get(source, source)] = encoded_actions
        encoded_buckets[plugin_name] = encoded_sources
    return {"date": entry["date"], "errored_runs": entry["errored_runs"], "buckets": encoded_buckets}


def _decode_day_entry(entry: dict) -> dict:
    decoded_buckets = {}
    for plugin_name, sources in entry["buckets"].items():
        decoded_sources = {}
        for src_key, actions in sources.items():
            decoded_actions = {}
            for act_key, cell in actions.items():
                decoded_actions[_ACT_DEC.get(act_key, act_key)] = {_CELL_DEC.get(k, k): v for k, v in cell.items()}
            decoded_sources[_SRC_DEC.get(src_key, src_key)] = decoded_actions
        decoded_buckets[plugin_name] = decoded_sources
    return {"date": entry["date"], "errored_runs": entry["errored_runs"], "buckets": decoded_buckets}


@dataclass(frozen=True)
class View:
    name: str
    label: str
    bins: int
    bin_seconds: int
    in_progress_bin: int
    timestamps: list
    series: dict
    errored: dict


@dataclass(frozen=True)
class Snapshot:
    plugins: list
    counters: dict
    views: list


def _plugin_is_errored(plugin_counters: dict) -> bool:
    for (source, action), counter in COUNTERS.items():
        if counter.error:
            src_dict = plugin_counters.get(source) or {}
            if src_dict.get(action, 0):
                return True
    return False


def aggregate_summary(plugins_data: dict) -> dict:
    summary = {}
    for plugin_counters in plugins_data.values():
        for source, actions in plugin_counters.items():
            if source not in summary:
                summary[source] = {}
            for action, value in actions.items():
                summary[source][action] = summary[source].get(action, 0) + (value or 0)
    return summary


def _empty_counter_series(bins: int) -> dict:
    result = {}
    for (source, action) in COUNTERS:
        if source not in result:
            result[source] = {}
        result[source][action] = [None] * bins
    return result


def _apply_cell_value(aggregator: str, cell: dict | None):
    if cell is None:
        return None
    count = cell.get("count", 0)
    if count == 0:
        return None
    if aggregator == AGG_SUM:
        return cell.get("sum", 0)
    if aggregator == AGG_MIN:
        return cell.get("min")
    if aggregator == AGG_MAX:
        return cell.get("max")
    if aggregator == AGG_MEAN:
        total = cell.get("sum", 0)
        return total / count if count > 0 else None
    return cell.get("sum", 0)


def _merge_cells(accumulated: dict | None, cell: dict) -> dict:
    if accumulated is None:
        return {"sum": cell["sum"], "min": cell["min"], "max": cell["max"], "count": cell["count"]}
    return {
        "sum": accumulated["sum"] + cell["sum"],
        "min": cell["min"] if accumulated["min"] is None else (min(accumulated["min"], cell["min"]) if cell["min"] is not None else accumulated["min"]),
        "max": cell["max"] if accumulated["max"] is None else (max(accumulated["max"], cell["max"]) if cell["max"] is not None else accumulated["max"]),
        "count": accumulated["count"] + cell["count"],
    }


def _acquire_file_lock(lock_fd: int) -> bool:
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


@dataclass
class _AdhocRun:
    done: threading.Event
    result: dict | None = None
    error: BaseException | None = None


class RunHistory:
    def __init__(self, plugins: list[str], cache_dir: str, poll_period_minutes: int, raw_label: str):
        self._plugins = sorted(plugins)
        self._all_plugins = ["summary"] + self._plugins
        self._poll_period_minutes = poll_period_minutes
        self._raw_label = raw_label
        self._lock = threading.Lock()
        self._raw: collections.deque[dict[str, Any]] = collections.deque(maxlen=HISTORY_RAW_RUN_LENGTH)
        self._day: collections.deque[dict[str, Any]] = collections.deque(maxlen=HISTORY_AGG_DAY_LENGTH)
        self._adhoc: dict[str, Any] | None = None
        self._raw_path = os.path.join(cache_dir, _RAW_FILENAME)
        self._daily_path = os.path.join(cache_dir, _DAILY_FILENAME)
        self._adhoc_path = os.path.join(cache_dir, _ADHOC_FILENAME)
        self._run_lock_path = os.path.join(cache_dir, _RUN_LOCK_FILENAME)
        self._run_lock = threading.Lock()
        self._adhoc_coord = threading.Lock()
        self._adhoc_current: _AdhocRun | None = None

    def add_run(self, ts: datetime.datetime, plugin_counters: dict, loop_overhead_ms: int = 0, start_ts: datetime.datetime | None = None) -> None:
        with self._lock:
            summary = aggregate_summary(plugin_counters)
            timing_summary = summary.setdefault(CTR_SRC_TIMING, {})
            timing_summary[CTR_ACT_PROCESS_MILLIS] = timing_summary.get(CTR_ACT_PROCESS_MILLIS, 0) + loop_overhead_ms
            timing_summary[CTR_ACT_TOTAL_MILLIS] = timing_summary.get(CTR_ACT_TOTAL_MILLIS, 0) + loop_overhead_ms
            all_counters = {"summary": summary, **plugin_counters}
            errored_map = {name: _plugin_is_errored(counters) for name, counters in all_counters.items()}
            ts_str = ts.isoformat()
            raw_entry = {"ts": ts_str, "bucket": _period_bucket(start_ts if start_ts is not None else ts, self._poll_period_minutes), "plugins": all_counters, "errored": errored_map}
            if self._raw and raw_entry["bucket"] is not None and self._raw[-1].get("bucket") == raw_entry["bucket"]:
                self._raw[-1] = raw_entry
            else:
                self._raw.append(raw_entry)
            date_str = ts.astimezone(CTR_TZ).date().isoformat()
            found_day_entry: dict[str, Any] | None = None
            for existing in self._day:
                if existing["date"] == date_str:
                    found_day_entry = existing
                    break
            if found_day_entry is None:
                day_entry: dict[str, Any] = {"date": date_str, "errored_runs": {name: 0 for name in self._all_plugins}, "buckets": {}}
                self._day.append(day_entry)
            else:
                day_entry = found_day_entry
            run_errored_overall = any(v for name, v in errored_map.items() if name != "summary")
            errored_runs: dict[str, int] = day_entry["errored_runs"]
            for plugin_name in self._plugins:
                if plugin_name not in errored_runs:
                    errored_runs[plugin_name] = 0
                if errored_map.get(plugin_name, False):
                    errored_runs[plugin_name] += 1
            if "summary" not in errored_runs:
                errored_runs["summary"] = 0
            if run_errored_overall:
                errored_runs["summary"] += 1
            day_buckets: dict[str, dict[str, dict[str, dict[str, int]]]] = day_entry["buckets"]
            for plugin_name, counters in all_counters.items():
                if plugin_name not in day_buckets:
                    day_buckets[plugin_name] = {}
                plugin_bucket = day_buckets[plugin_name]
                for source, actions in counters.items():
                    if source not in plugin_bucket:
                        plugin_bucket[source] = {}
                    for action, value in actions.items():
                        if (source, action) not in COUNTERS:
                            continue
                        value_num = value or 0
                        if action not in plugin_bucket[source]:
                            plugin_bucket[source][action] = {"sum": value_num, "min": value_num, "max": value_num, "count": 1}
                        else:
                            cell = plugin_bucket[source][action]
                            cell["sum"] += value_num
                            cell["min"] = min(cell["min"], value_num)
                            cell["max"] = max(cell["max"], value_num)
                            cell["count"] += 1
            self.store()
            if self._raw:
                latest = self._raw[-1]
                latest_plugins: dict[str, Any] = latest.get("plugins") or {}
                summary_counters = latest_plugins.get("summary") or {}
                print_log("Wrangle", "Execution Summary:")
                for source in [CTR_SRC_SOURCES, CTR_SRC_FILES, CTR_SRC_DATA, CTR_SRC_EGRESS, CTR_SRC_TIMING]:
                    source_counters = summary_counters.get(source) or {}
                    for action, value in source_counters.items():
                        print_log("Wrangle", f"     {' '.join((source, action)).ljust(CTR_LBL_WIDTH, CTR_LBL_PAD)} {value:8}")

    def add_adhoc_run(self, ts: datetime.datetime, plugin_counters: dict, overhead_ms: int = 0) -> None:
        with self._lock:
            summary = aggregate_summary(plugin_counters)
            timing_summary = summary.setdefault(CTR_SRC_TIMING, {})
            timing_summary[CTR_ACT_PROCESS_MILLIS] = timing_summary.get(CTR_ACT_PROCESS_MILLIS, 0) + overhead_ms
            timing_summary[CTR_ACT_TOTAL_MILLIS] = timing_summary.get(CTR_ACT_TOTAL_MILLIS, 0) + overhead_ms
            all_counters = {"summary": summary, **plugin_counters}
            errored_map = {name: _plugin_is_errored(counters) for name, counters in all_counters.items()}
            entry = {"ts": ts.isoformat(), "plugins": all_counters, "errored": errored_map}
            self._adhoc = entry
            self._store_adhoc()
            print_log("Wrangle", "Execution Summary:")
            for source in [CTR_SRC_SOURCES, CTR_SRC_FILES, CTR_SRC_DATA, CTR_SRC_EGRESS, CTR_SRC_TIMING]:
                source_counters = summary.get(source) or {}
                for action, value in source_counters.items():
                    print_log("Wrangle", f"     {' '.join((source, action)).ljust(CTR_LBL_WIDTH, CTR_LBL_PAD)} {value:8}")

    def latest_run_entry(self) -> dict | None:
        with self._lock:
            latest_raw = self._raw[-1] if self._raw else None
            latest_adhoc = self._adhoc
            if latest_raw is None and latest_adhoc is None:
                return None
            if latest_raw is None:
                return copy.deepcopy(latest_adhoc)
            if latest_adhoc is None:
                return copy.deepcopy(latest_raw)
            chosen = latest_adhoc if latest_adhoc["ts"] >= latest_raw["ts"] else latest_raw
            return copy.deepcopy(chosen)

    @contextlib.contextmanager
    def acquire_run_lock(self, timeout_seconds: float = TIMEOUT_RUN_SECONDS):
        with self._run_lock:
            os.makedirs(os.path.dirname(self._run_lock_path), exist_ok=True)
            lock_fd = os.open(self._run_lock_path, os.O_CREAT | os.O_RDWR, 0o644)
            try:
                wait_start = time.perf_counter()
                if not _acquire_file_lock(lock_fd):
                    print_log("Wrangle", f"Another wrangle process holds [{_RUN_LOCK_FILENAME}], waiting up to [{int(timeout_seconds)}s] for it to finish", level="warning")
                    while not _acquire_file_lock(lock_fd):
                        waited_seconds = time.perf_counter() - wait_start
                        if waited_seconds >= timeout_seconds:
                            raise TimeoutError(f"Timed out after [{int(waited_seconds)}s] waiting to acquire [{_RUN_LOCK_FILENAME}]")
                        print_log("Wrangle", f"Queued behind another wrangle process for [{int(waited_seconds)}s] ...", level="info")
                        time.sleep(1)
                    print_log("Wrangle", f"Acquired [{_RUN_LOCK_FILENAME}] after [{int((time.perf_counter() - wait_start) * 1000)}ms]", level="info")
                try:
                    yield
                finally:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)

    def execute_adhoc(self, run_fn: Callable[[], dict]) -> dict:
        with self._adhoc_coord:
            if self._adhoc_current is not None:
                current = self._adhoc_current
                we_run = False
            else:
                current = _AdhocRun(done=threading.Event())
                self._adhoc_current = current
                we_run = True
        if not we_run:
            current.done.wait()
            if current.error is not None:
                raise current.error
            assert current.result is not None
            return current.result
        try:
            with self.acquire_run_lock():
                result = run_fn()
            current.result = result
            return result
        except BaseException as exc:
            current.error = exc
            raise
        finally:
            with self._adhoc_coord:
                self._adhoc_current = None
            current.done.set()

    def snapshot(self) -> Snapshot:
        with self._lock:
            counters_dict = {f"{source}|{action}": {"source": c.source, "action": c.action, "label": c.label, "aggregator": c.aggregator, "format": c.format, "error": c.error} for (source, action), c
                             in COUNTERS.items()}
            views = [
                self._build_raw_view(),
                self._build_day_view(),
                self._build_week_view(),
            ]
            return Snapshot(plugins=list(self._all_plugins), counters=counters_dict, views=views)

    def is_errored(self, plugin: str = "summary") -> bool | None:
        with self._lock:
            if plugin not in self._all_plugins:
                raise KeyError(f"unknown plugin: {plugin}")
            if not self._raw:
                return None
            return self._raw[-1]["errored"].get(plugin, False)

    def _fill_raw_slot(self, series: dict, errored: dict, slot_index: int, entry: dict) -> None:
        entry_plugins: dict[str, Any] = entry.get("plugins") or {}
        entry_errored: dict[str, bool] = entry.get("errored") or {}
        for plugin_name in self._all_plugins:
            plugin_counters = entry_plugins.get(plugin_name) or {}
            for (source, action) in COUNTERS:
                source_counters = plugin_counters.get(source) or {}
                series[plugin_name][source][action][slot_index] = source_counters.get(action)
            errored[plugin_name][slot_index] = entry_errored.get(plugin_name, False)

    def _build_raw_view(self) -> View:
        bins = HISTORY_RAW_RUN_LENGTH
        bucket_seconds = self._poll_period_minutes * 60
        series = {plugin_name: _empty_counter_series(bins) for plugin_name in self._all_plugins}
        errored: dict[str, list] = {plugin_name: [None] * bins for plugin_name in self._all_plugins}
        if bucket_seconds <= 0 or not self._raw:
            raw_list = list(self._raw)
            timestamps = [entry["ts"] for entry in raw_list] + [""] * (bins - len(raw_list))
            for slot_index, entry in enumerate(raw_list):
                self._fill_raw_slot(series, errored, slot_index, entry)
            return View(name="raw", label=self._raw_label, bins=bins, bin_seconds=bucket_seconds, in_progress_bin=-1, timestamps=timestamps, series=series, errored=errored)
        bucket_lookup: dict[int, dict] = {}
        for entry in self._raw:
            bucket = entry.get("bucket")
            if bucket is None:
                bucket = int(datetime.datetime.fromisoformat(entry["ts"]).timestamp()) // bucket_seconds
            bucket_lookup[bucket] = entry
        current_bucket = int(datetime.datetime.now(tz=CTR_TZ).timestamp()) // bucket_seconds
        earliest_bucket = min(bucket_lookup)
        n_real = min(bins, current_bucket - earliest_bucket + 1)
        start_bucket = current_bucket - (n_real - 1)
        timestamps = []
        for slot_index in range(n_real):
            bucket = start_bucket + slot_index
            entry = bucket_lookup.get(bucket)
            if entry is not None:
                timestamps.append(entry["ts"])
                self._fill_raw_slot(series, errored, slot_index, entry)
            else:
                timestamps.append(datetime.datetime.fromtimestamp(bucket * bucket_seconds, tz=CTR_TZ).isoformat())
        timestamps += [""] * (bins - n_real)
        in_progress_bin = n_real - 1
        return View(name="raw", label=self._raw_label, bins=bins, bin_seconds=bucket_seconds, in_progress_bin=in_progress_bin, timestamps=timestamps, series=series, errored=errored)

    def _build_day_view(self) -> View:
        bins = HISTORY_RAW_RUN_LENGTH
        today = datetime.datetime.now(tz=CTR_TZ).date()
        if self._day:
            earliest = datetime.date.fromisoformat(min(e["date"] for e in self._day))
            n_real = min(bins, (today - earliest).days + 1)
            start = today - datetime.timedelta(days=n_real - 1)
        else:
            n_real = 0
            start = today
        ghost_count = bins - n_real
        date_grid = [(start + datetime.timedelta(days=i)).isoformat() for i in range(n_real)] + [""] * ghost_count
        day_lookup = {entry["date"]: entry for entry in self._day}
        series = {plugin_name: _empty_counter_series(bins) for plugin_name in self._all_plugins}
        errored: dict[str, list] = {plugin_name: [None] * bins for plugin_name in self._all_plugins}
        for slot_index, date_str in enumerate(date_grid):
            if not date_str:
                continue
            entry = day_lookup.get(date_str)
            if entry is None:
                continue
            entry_buckets: dict[str, Any] = entry.get("buckets") or {}
            entry_errored_runs: dict[str, int] = entry.get("errored_runs") or {}
            for plugin_name in self._all_plugins:
                plugin_bucket: dict[str, dict[str, dict]] = entry_buckets.get(plugin_name) or {}
                errored_count = entry_errored_runs.get(plugin_name, 0)
                errored[plugin_name][slot_index] = errored_count > 0
                for (source, action), counter in COUNTERS.items():
                    source_bucket: dict[str, dict] = plugin_bucket.get(source) or {}
                    cell = source_bucket.get(action)
                    if cell is not None:
                        series[plugin_name][source][action][slot_index] = _apply_cell_value(counter.aggregator, cell)
        in_progress_bin = n_real - 1 if n_real > 0 else -1
        return View(name="day", label="7w", bins=bins, bin_seconds=86400, in_progress_bin=in_progress_bin, timestamps=date_grid, series=series, errored=errored)

    def _build_week_view(self) -> View:
        bins = HISTORY_RAW_RUN_LENGTH
        today = datetime.datetime.now(tz=CTR_TZ).date()
        if self._day:
            earliest = datetime.date.fromisoformat(min(e["date"] for e in self._day))
            filled_bins = min(bins, (today - earliest).days // 7 + 1)
        else:
            filled_bins = 0
        ghost_count = bins - filled_bins
        day_lookup = {entry["date"]: entry for entry in self._day}
        timestamps = []
        series = {plugin_name: _empty_counter_series(bins) for plugin_name in self._all_plugins}
        errored: dict[str, list] = {plugin_name: [None] * bins for plugin_name in self._all_plugins}
        for bin_index in range(filled_bins):
            end_offset = (filled_bins - 1 - bin_index) * 7
            bin_end = today - datetime.timedelta(days=end_offset)
            bin_start = bin_end - datetime.timedelta(days=6)
            timestamps.append(bin_start.isoformat())
            accumulated_cells: dict[str, dict[str, dict]] = {}
            accumulated_errored: dict[str, int] = {}
            accumulated_count: dict[str, int] = {}
            for day_offset in range(7):
                day_date = (bin_start + datetime.timedelta(days=day_offset)).isoformat()
                entry = day_lookup.get(day_date)
                if entry is None:
                    continue
                entry_buckets: dict[str, Any] = entry.get("buckets") or {}
                entry_errored_runs: dict[str, int] = entry.get("errored_runs") or {}
                for plugin_name in self._all_plugins:
                    plugin_bucket: dict[str, dict[str, dict]] = entry_buckets.get(plugin_name) or {}
                    errored_count = entry_errored_runs.get(plugin_name, 0)
                    if plugin_name not in accumulated_errored:
                        accumulated_errored[plugin_name] = 0
                        accumulated_count[plugin_name] = 0
                    accumulated_errored[plugin_name] += errored_count
                    accumulated_count[plugin_name] += 1
                    if plugin_name not in accumulated_cells:
                        accumulated_cells[plugin_name] = {}
                    plugin_accumulated_cells = accumulated_cells[plugin_name]
                    for (source, action) in COUNTERS:
                        key = f"{source}|{action}"
                        source_bucket: dict[str, dict] = plugin_bucket.get(source) or {}
                        cell = source_bucket.get(action)
                        if cell is not None:
                            plugin_accumulated_cells[key] = _merge_cells(plugin_accumulated_cells.get(key), cell)
            for plugin_name in self._all_plugins:
                if plugin_name in accumulated_count and accumulated_count[plugin_name] > 0:
                    errored[plugin_name][bin_index] = accumulated_errored.get(plugin_name, 0) > 0
                if plugin_name in accumulated_cells:
                    for (source, action), counter in COUNTERS.items():
                        key = f"{source}|{action}"
                        merged = accumulated_cells[plugin_name].get(key)
                        if merged is not None:
                            series[plugin_name][source][action][bin_index] = _apply_cell_value(counter.aggregator, merged)
        timestamps += [""] * ghost_count
        in_progress_bin = filled_bins - 1 if filled_bins > 0 else -1
        return View(name="week", label="1y", bins=bins, bin_seconds=604800, in_progress_bin=in_progress_bin, timestamps=timestamps, series=series, errored=errored)

    def store(self) -> None:
        os.makedirs(os.path.dirname(self._raw_path), exist_ok=True)
        header = {
            "schema": _SCHEMA_FINGERPRINT,
            "poll_period": self._poll_period_minutes,
            "plugins": self._plugins,
        }
        started = time.perf_counter()
        raw_body = orjson.dumps({**header, "raw": [_encode_raw_entry(e) for e in self._raw]})
        raw_is_new = not os.path.isfile(self._raw_path)
        raw_tmp = self._raw_path + ".tmp"
        Path(raw_tmp).write_bytes(raw_body)
        os.rename(raw_tmp, self._raw_path)
        raw_elapsed_ms = int((time.perf_counter() - started) * 1000)
        print_log("Wrangle", f"File [{_RAW_FILENAME}] {'created' if raw_is_new else 'stored'}, [{len(raw_body):,}] bytes, [{len(self._raw)}] raw records, in [{raw_elapsed_ms}ms]",
                  level="info")
        started = time.perf_counter()
        daily_body = orjson.dumps({**header, "day": [_encode_day_entry(e) for e in self._day]})
        daily_is_new = not os.path.isfile(self._daily_path)
        daily_tmp = self._daily_path + ".tmp"
        Path(daily_tmp).write_bytes(daily_body)
        os.rename(daily_tmp, self._daily_path)
        daily_elapsed_ms = int((time.perf_counter() - started) * 1000)
        print_log("Wrangle", f"File [{_DAILY_FILENAME}] {'created' if daily_is_new else 'stored'}, [{len(daily_body):,}] bytes, [{len(self._day)}] day records, in [{daily_elapsed_ms}ms]",
                  level="info")

    def _store_adhoc(self) -> None:
        if self._adhoc is None:
            return
        os.makedirs(os.path.dirname(self._adhoc_path), exist_ok=True)
        header = {"schema": _SCHEMA_FINGERPRINT, "plugins": self._plugins}
        started = time.perf_counter()
        body = orjson.dumps({**header, "adhoc": _encode_raw_entry(self._adhoc)})
        is_new = not os.path.isfile(self._adhoc_path)
        tmp = self._adhoc_path + ".tmp"
        Path(tmp).write_bytes(body)
        os.rename(tmp, self._adhoc_path)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        print_log("Wrangle", f"File [{_ADHOC_FILENAME}] {'created' if is_new else 'stored'}, [{len(body):,}] bytes, in [{elapsed_ms}ms]", level="info")

    def load(self) -> None:
        for path, kind in [(self._raw_path, "raw"), (self._daily_path, "daily")]:
            filename = os.path.basename(path)
            if not os.path.isfile(path):
                print_log("Wrangle", f"File [{filename}] not found, starting fresh", level="info")
                continue
            started = time.perf_counter()
            try:
                file_bytes = Path(path).read_bytes()
                state = orjson.loads(file_bytes)
                if state.get("schema") != _SCHEMA_FINGERPRINT:
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    print_log("Wrangle", f"{filename} schema [{state.get('schema')}] != [{_SCHEMA_FINGERPRINT}], starting fresh after [{elapsed_ms}ms]", level="warning")
                    continue
                if kind == "raw" and state.get("poll_period") != self._poll_period_minutes:
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    print_log("Wrangle", f"{filename} poll_period [{state.get('poll_period')}] != [{self._poll_period_minutes}], starting fresh after [{elapsed_ms}ms]", level="warning")
                    continue
                if state.get("plugins") != self._plugins:
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    print_log("Wrangle", f"{filename} plugins [{state.get('plugins')}] != [{self._plugins}], starting fresh after [{elapsed_ms}ms]", level="warning")
                    continue
                if kind == "raw":
                    decoded = collections.deque((_decode_raw_entry(e) for e in state.get("raw", [])), maxlen=HISTORY_RAW_RUN_LENGTH)
                else:
                    decoded = collections.deque((_decode_day_entry(e) for e in state.get("day", [])), maxlen=HISTORY_AGG_DAY_LENGTH)
            except Exception as exc:
                print_log("Wrangle", f"{filename} unreadable, starting fresh: {exc}", level="warning")
                continue
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if kind == "raw":
                self._raw = decoded
                print_log("Wrangle", f"File [{filename}] loaded, [{len(file_bytes):,}] bytes, [{len(self._raw)}] raw records, in [{elapsed_ms}ms]", level="info")
            else:
                self._day = decoded
                print_log("Wrangle", f"File [{filename}] loaded, [{len(file_bytes):,}] bytes, [{len(self._day)}] day records, in [{elapsed_ms}ms]", level="info")
        if os.path.isfile(self._adhoc_path):
            started = time.perf_counter()
            try:
                file_bytes = Path(self._adhoc_path).read_bytes()
                state = orjson.loads(file_bytes)
                if state.get("schema") != _SCHEMA_FINGERPRINT:
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    print_log("Wrangle", f"{_ADHOC_FILENAME} schema [{state.get('schema')}] != [{_SCHEMA_FINGERPRINT}], ignoring after [{elapsed_ms}ms]", level="warning")
                elif state.get("plugins") != self._plugins:
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    print_log("Wrangle", f"{_ADHOC_FILENAME} plugins [{state.get('plugins')}] != [{self._plugins}], ignoring after [{elapsed_ms}ms]", level="warning")
                else:
                    entry = state.get("adhoc")
                    if isinstance(entry, dict) and "ts" in entry and "plugins" in entry:
                        self._adhoc = _decode_raw_entry(entry)
                        elapsed_ms = int((time.perf_counter() - started) * 1000)
                        print_log("Wrangle", f"File [{_ADHOC_FILENAME}] loaded, [{len(file_bytes):,}] bytes, in [{elapsed_ms}ms]", level="info")
            except Exception as exc:
                print_log("Wrangle", f"{_ADHOC_FILENAME} unreadable, ignoring: {exc}", level="warning")
        else:
            print_log("Wrangle", f"File [{_ADHOC_FILENAME}] not found, starting fresh", level="info")
