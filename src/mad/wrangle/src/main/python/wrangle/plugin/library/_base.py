import copy
import time
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from os.path import abspath, join

from . import _database
from ._config import (config, get_dir,
                      CTR_LBL_PAD, CTR_LBL_WIDTH,
                      CTR_SRC_SOURCES, CTR_SRC_FILES, CTR_SRC_DATA, CTR_SRC_EGRESS,
                      CTR_ACT_DOWNLOADED, CTR_ACT_CACHED, CTR_ACT_UPLOADED, CTR_ACT_PERSISTED, CTR_ACT_ERRORED,
                      CTR_ACT_PROCESSED, CTR_ACT_SKIPPED,
                      CTR_ACT_PREVIOUS_COLUMNS, CTR_ACT_PREVIOUS_ROWS,
                      CTR_ACT_CURRENT_COLUMNS, CTR_ACT_CURRENT_ROWS,
                      CTR_ACT_UPDATE_COLUMNS, CTR_ACT_UPDATE_ROWS,
                      CTR_ACT_DELTA_COLUMNS, CTR_ACT_DELTA_ROWS,
                      CTR_ACT_SHEET_COLUMNS, CTR_ACT_SHEET_ROWS,
                      CTR_ACT_DATABASE_COLUMNS, CTR_ACT_DATABASE_ROWS,
                      CTR_ACT_QUEUE_COLUMNS, CTR_ACT_QUEUE_ROWS)
from ._logging import log_enabled, print_log as _print_log
from ._sources import SourcesMixin
from ._dataframes import DataFramesMixin
from ._state import StateMixin


class Library(SourcesMixin, DataFramesMixin, StateMixin, metaclass=ABCMeta):

    @abstractmethod
    def _run(self):
        pass

    def run(self):
        started_time = time.time()
        self.print_log("Starting ...")
        self._run()
        if not config.disable_uploads:
            self.drive_synchronise(self.drives.drive_folder, self.input, check=True, download=False, upload=True)
        for csv_path, csv_df in self._db_cache_dfs.items():
            self.csv_write(csv_df, csv_path)
        self.print_counters()
        self.print_log("Finished", started=started_time)

    def print_log(self, messages, data=None, started=None, exception=None, level="info"):
        effective_level = "error" if exception is not None else level
        if not log_enabled(effective_level):
            return
        if type(messages) is not list:
            messages = [messages]
        if started is not None:
            messages[-1] = messages[-1] + f" in [{time.time() - started:.3f}] sec"
        if data is not None:
            messages[-1] = messages[-1] + ": "
            if type(data) is list:
                messages.extend(data)
            else:
                messages[-1] = messages[-1] + data
        _print_log(self.name, messages, exception, level=level)

    def print_counters(self):
        self.print_log("Execution Summary:")
        for source in self.counters:
            for action in self.counters[source]:
                self.print_log(f"     {f'{source} {action} '.ljust(CTR_LBL_WIDTH, CTR_LBL_PAD)} {self.counters[source][action]:8}")

    def add_counter(self, source, action, count=1):
        self.counters[source][action] += count

    def get_counter(self, source, action):
        return self.counters[source][action]

    def get_counters(self):
        return copy.deepcopy(self.counters)

    def reset_counters(self):
        self._db_cache_dfs = {}
        self.counters = OrderedDict([
            (CTR_SRC_SOURCES, OrderedDict([
                (CTR_ACT_DOWNLOADED, 0),
                (CTR_ACT_CACHED, 0),
                (CTR_ACT_UPLOADED, 0),
                (CTR_ACT_PERSISTED, 0),
                (CTR_ACT_ERRORED, 0),
            ])),
            (CTR_SRC_FILES, OrderedDict([
                (CTR_ACT_PROCESSED, 0),
                (CTR_ACT_SKIPPED, 0),
                (CTR_ACT_ERRORED, 0),
            ])),
            (CTR_SRC_DATA, OrderedDict([
                (CTR_ACT_PREVIOUS_COLUMNS, 0),
                (CTR_ACT_PREVIOUS_ROWS, 0),
                (CTR_ACT_CURRENT_COLUMNS, 0),
                (CTR_ACT_CURRENT_ROWS, 0),
                (CTR_ACT_UPDATE_COLUMNS, 0),
                (CTR_ACT_UPDATE_ROWS, 0),
                (CTR_ACT_DELTA_COLUMNS, 0),
                (CTR_ACT_DELTA_ROWS, 0),
                (CTR_ACT_ERRORED, 0),
            ])),
            (CTR_SRC_EGRESS, OrderedDict([
                (CTR_ACT_QUEUE_COLUMNS, 0),
                (CTR_ACT_QUEUE_ROWS, 0),
                (CTR_ACT_SHEET_COLUMNS, 0),
                (CTR_ACT_SHEET_ROWS, 0),
                (CTR_ACT_DATABASE_COLUMNS, 0),
                (CTR_ACT_DATABASE_ROWS, 0),
                (CTR_ACT_ERRORED, 0),
            ])),
        ])

    def file_list(self, file_dir, file_prefix, quiet=True):
        import os
        files = {}
        for file_name in os.listdir(file_dir):
            if file_name.startswith(file_prefix):
                file_path = join(file_dir, file_name)
                from ._config import DownloadResult, DownloadStatus
                files[file_path] = DownloadResult(DownloadStatus.CACHED, file_path)
                if not quiet:
                    self.print_log(f"File [{file_name}] found at [{file_path}]")
        return files

    def counter_write(self):
        if config.disable_uploads or _database.database is None:
            return
        values = []
        timestamp_ms = int(time.time() * 1000)
        for source in self.counters:
            for action in self.counters[source]:
                values.append(f"{f'{source}_{action}'.lower().replace(' ', '_')}={self.counters[source][action]}i")
        line = f"{self.name.lower()},type=metadata,period=30m,unit=scalar,source=wrangle {','.join(values)} {timestamp_ms}"
        try:
            _database.database.write(record=line, write_precision="ms")
        except Exception as exception:
            self.print_log("Counter write failed", exception=exception)

    def __init__(self, name, drives):
        self.name = name
        self.reset_counters()
        self.drives = drives
        self.input = abspath(get_dir(f"data/{name.lower()}"))
