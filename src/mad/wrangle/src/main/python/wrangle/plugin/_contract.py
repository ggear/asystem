from datetime import datetime
from typing import Any

import polars as pl

from ._throttle import Throttle
from .config import Repos


class ContractMixin:
    name: str
    local_cache: str
    remote_repos: Repos
    _db_cache_dfs: dict[str, pl.DataFrame]
    _sheet_credentials: Any
    _sheet_spreadsheets: dict[str, Any]
    _sheet_worksheets: dict[str, list[Any]]
    error_codes: dict[str, tuple[str, bool, str]]
    drive_conflicts: set[str]
    drive_download_only: tuple[str, ...]
    drive_ids: dict[str, str]
    throttles: dict[str, Throttle]

    def print_log(self, *args, **kwargs):
        raise NotImplementedError

    def now(self) -> datetime:
        raise NotImplementedError

    def add_counter(self, *args, **kwargs):
        raise NotImplementedError

    def error(self, *args, **kwargs):
        raise NotImplementedError

    def csv_read(self, *args, **kwargs) -> pl.DataFrame:
        raise NotImplementedError

    def csv_write(self, *args, **kwargs) -> pl.DataFrame:
        raise NotImplementedError

    def dataframe_new(self, *args, **kwargs) -> pl.DataFrame:
        raise NotImplementedError

    def dataframe_type_to_str(self, *args, **kwargs) -> str:
        raise NotImplementedError
