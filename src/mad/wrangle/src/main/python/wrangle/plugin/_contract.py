import polars as pl

from .config import Repos


class ContractMixin:
    name: str
    local_cache: str
    remote_repos: Repos
    _db_cache_dfs: dict[str, pl.DataFrame]

    def print_log(self, *args, **kwargs):
        raise NotImplementedError

    def add_counter(self, *args, **kwargs):
        raise NotImplementedError

    def csv_read(self, *args, **kwargs) -> pl.DataFrame:
        raise NotImplementedError

    def csv_write(self, *args, **kwargs) -> pl.DataFrame:
        raise NotImplementedError

    def dataframe_new(self, *args, **kwargs) -> pl.DataFrame:
        raise NotImplementedError

    def dataframe_type_to_str(self, *args, **kwargs) -> str:
        raise NotImplementedError
