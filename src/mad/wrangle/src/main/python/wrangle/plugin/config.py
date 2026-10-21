import socket
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, StrEnum, auto
from os.path import abspath, basename, dirname, isfile, join, realpath
from typing import NamedTuple

import polars as pl

PL_PRINT_ROWS = 20

TIMEOUT_NETWORK_SECONDS = 60
TIMEOUT_RUN_SECONDS = 10 * 60

STACK_DUMP_FILE = "/tmp/wrangle-stack.log"

REDBARK_URL = "https://api.redbark.com"
REDBARK_PAGE_LIMIT = 200
REDBARK_PAGES_MAX = 1000

FEED_CACHE_SECONDS = 60
FEED_SYMBOL_PATTERN = r"^[A-Za-z0-9.^=-]{1,20}$"

DRIVE_IGNORE_PREFIXES = ("_", "~$")

SHEET_MANUAL_COLOUR = {"red": 0x4A / 255, "green": 0x86 / 255, "blue": 0xE8 / 255}
SHEET_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y", "%Y/%m/%d"]

LOG_KIND_ERROR = "Error"
LOG_KIND_WARNING = "Warning"
LOG_KIND_INFO = "Info"
LOG_RECORD_DAYS = 30
LOG_STATE_CURRENT = "Current"
LOG_STATE_HISTORIC = "Historic"
LOG_RAW_COLUMNS = ["Time", "Kind", "State", "Counter", "Tab", "Key", "Code", "Detail"]

LOG_SCHEMA = {
    "Date": pl.Date,
    "Time": pl.Utf8,
    "Date Raised": pl.Date,
    "Kind": pl.Utf8,
    "State": pl.Utf8,
    "Counter": pl.Utf8,
    "Tab": pl.Utf8,
    "Key": pl.Utf8,
    "Code": pl.Utf8,
    "Detail": pl.Utf8,
}

DATABASE_SCHEMA_DIRS = (
    "/asystem/etc/database",
    abspath(join(dirname(realpath(__file__)), "../../../resources/image/database")),
)

socket.setdefaulttimeout(TIMEOUT_NETWORK_SECONDS)


@dataclass(frozen=True)
class Backoff:
    statuses: frozenset[int] = frozenset({429, 503})
    retries: int = 4
    first_seconds: float = 5
    max_seconds: float = 60
    budget_seconds: float = 3 * 60
    remaining_header: str | None = "X-RateLimit-Remaining"
    reset_header: str | None = "X-RateLimit-Reset"


REDBARK_BACKOFF = Backoff()
GOOGLE_SHEETS_BACKOFF = Backoff(statuses=frozenset({429, 500, 502, 503, 504}), first_seconds=2, remaining_header=None, reset_header=None)
GOOGLE_DRIVE_BACKOFF = Backoff(statuses=frozenset({429, 500, 502, 503, 504}), first_seconds=2, remaining_header=None, reset_header=None)
YAHOO_BACKOFF = Backoff(statuses=frozenset({429}), remaining_header=None, reset_header=None)


class RepoScope(StrEnum):
    LOCAL = "local"
    PREVIEW = "preview"
    RELEASE = "release"


@dataclass
class Repos:
    _scopes: dict[str, dict[str, str]]

    def __init__(self, **scopes: dict[str, str]):
        valid: set[str] = {scope.name.lower() for scope in RepoScope}
        for name in scopes:
            if name not in valid:
                raise ValueError(f"unknown scope '{name}'; valid: {sorted(valid)}")
        required: set[str] = {scope.name.lower() for scope in RepoScope if scope != RepoScope.LOCAL}
        missing_scopes = required - set(scopes)
        if missing_scopes:
            raise ValueError(f"missing required scopes: {sorted(missing_scopes)}")
        all_keys: set[str] = set()
        for keys in scopes.values():
            all_keys.update(keys.keys())
        for scope_name, keys in scopes.items():
            missing_keys = all_keys - set(keys.keys())
            if missing_keys:
                raise ValueError(f"scope '{scope_name}' missing keys: {sorted(missing_keys)}")
        self._scopes = scopes

    def __getattr__(self, name: str) -> str | None:
        scope = config.repo_scope
        if scope == RepoScope.LOCAL:
            return None
        scope: RepoScope = config.repo_scope
        scope_name = scope.value
        keys = self._scopes[scope_name]
        if name not in keys:
            raise AttributeError(f"RepoScope has no key '{name}' for scope '{scope_name}'")
        return keys[name]


class Config:
    log_level: str = "info"
    poll_period: int = 0
    repo_scope: RepoScope = RepoScope.RELEASE
    cache_dir: str = "/asystem/mnt/data"
    force_reprocessing: bool = False
    force_downloads: bool = False
    force_uploads: bool = False
    disable_drive_uploads: bool = False
    disable_sheet_uploads: bool = False
    disable_database_uploads: bool = False
    disable_drive_downloads: bool = False
    disable_sheet_downloads: bool = False
    disable_database_downloads: bool = False
    disable_source_downloads: bool = False
    clock: datetime | None = None


config = Config()


class DownloadStatus(Enum):
    CACHED = auto()
    DOWNLOADED = auto()
    SKIPPED = auto()
    FAILED = auto()


class DriveStatus(StrEnum):
    DOWNLOADED = auto()
    CACHED = auto()
    UPLOADED = auto()
    VERIFIED = auto()
    CONFLICTED = auto()
    FAILED = auto()


class UploadStatus(Enum):
    UPLOADED = auto()
    UNCHANGED = auto()
    MOVED = auto()
    FAILED = auto()


class DownloadResult(NamedTuple):
    file_status: DownloadStatus
    file_paths: list[str]
    data_frame: pl.DataFrame | None = None
    errors: Sequence[dict] = ()


def get_file(file_name):
    if isfile(file_name):
        return file_name
    file_name = basename(file_name)
    working = dirname(abspath(__file__))
    paths = [
        f"/root/{file_name}",
        f"{working}/../../../resources/{file_name}",
        f"{working}/../../../resources/image/{file_name}",
        f"{working}/../../../../../{file_name}",
    ]
    for path in paths:
        if isfile(path):
            return path
    raise OSError(f"Could not find file [{file_name}] in the usual places {paths}")


def load_profile(profile_path):
    profile = {}
    with open(get_file(profile_path)) as profile_file:
        for profile_line in profile_file:
            profile_line = profile_line.replace("export ", "").rstrip()
            if "=" not in profile_line:
                continue
            if profile_line.startswith("#"):
                continue
            profile_key, profile_value = profile_line.split("=", 1)
            profile[profile_key] = profile_value
    return profile
