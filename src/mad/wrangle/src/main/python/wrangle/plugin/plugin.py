import os
import time
from abc import ABCMeta, abstractmethod
from os.path import isdir, join

from ._dataframes import DataFramesMixin
from ._sources import SourcesMixin
from ._state import StateMixin
from .config import *
from .config import DownloadResult, DownloadStatus
from .counters import *  # noqa: F401,F403
from .logger import log_enabled, print_log


class Plugin(CountersMixin, SourcesMixin, DataFramesMixin, StateMixin, metaclass=ABCMeta):

    @abstractmethod
    def _run(self):
        pass

    def run(self):
        started_time = time.time()
        total_start = time.perf_counter()
        self.print_log("Starting ...")
        self._run()
        for csv_path, csv_df in self._db_cache_dfs.items():
            self.csv_write(csv_df, csv_path)
        if not config.disable_drive_uploads:
            self.drive_synchronise(self.remote_repos.drive_folder, self.local_cache, check=True, download=False, upload=True)
        total_elapsed_ms = int((time.perf_counter() - total_start) * 1000)
        marshall_ms = self.get_counter(CTR_SRC_TIMING, CTR_ACT_MARSHALL_MILLIS)
        egress_ms = self.get_counter(CTR_SRC_TIMING, CTR_ACT_EGRESS_MILLIS)
        process_ms = max(0, total_elapsed_ms - marshall_ms - egress_ms)
        self.add_counter(CTR_SRC_TIMING, CTR_ACT_PROCESS_MILLIS, process_ms)
        self.add_counter(CTR_SRC_TIMING, CTR_ACT_TOTAL_MILLIS, total_elapsed_ms)
        self.print_counters()
        self.print_log("Finished", started=started_time)

    def print_log(self, messages, data=None, started=None, exception=None, level="info"):
        effective_level = "error" if exception is not None else level
        if not log_enabled(effective_level):
            return
        if type(messages) is not list:
            messages = [messages]
        if started is not None:
            messages[-1] = messages[-1] + f" in [{time.time() - started:.3f}s]"
        if data is not None:
            messages[-1] = messages[-1] + ": "
            if type(data) is list:
                messages.extend(data)
            else:
                messages[-1] = messages[-1] + str(data)
        print_log(self.name, messages, exception, level=level)

    def counter_write(self):
        pass

    def file_list(self, file_dir: str, file_prefix: str, quiet: bool = True) -> dict[str, DownloadResult]:
        files: dict[str, DownloadResult] = {}
        for file_name in sorted(os.listdir(file_dir)):
            if file_name.startswith(file_prefix):
                file_path = join(file_dir, file_name)
                files[file_path] = DownloadResult(DownloadStatus.CACHED, file_path)
                if not quiet:
                    self.print_log(f"File [{file_name}] found at [{file_path}]")
        return files

    def __init__(self, name, order=999, repos: "Repos | None" = None, disabled=False, database=False):
        self._counters = {}
        self._db_cache_dfs = {}
        self.reset_counters()
        self.name = name
        self.order = order
        self.disabled = disabled
        self.database = database
        self.remote_repos = repos  # type: ignore[assignment]
        self.local_cache = abspath(f"{config.cache_dir}/{name.lower()}")
        if not isdir(self.local_cache):
            os.makedirs(self.local_cache)
