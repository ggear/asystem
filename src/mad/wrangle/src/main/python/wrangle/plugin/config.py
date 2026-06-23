import os
import socket
from dataclasses import dataclass
from enum import Enum, auto
from os.path import abspath, basename, dirname, isfile
from typing import NamedTuple

PL_PRINT_ROWS = 20

NETWORK_TIMEOUT_SECONDS = float(os.environ.get("WRANGLE_NETWORK_TIMEOUT_SECONDS", "60"))
socket.setdefaulttimeout(NETWORK_TIMEOUT_SECONDS)


class RepoScope(str, Enum):
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
        required: set[str] = {
            scope.name.lower() for scope in RepoScope if scope != RepoScope.LOCAL
        }
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
    disable_drive_uploads: bool = False
    disable_sheet_uploads: bool = False
    disable_database_uploads: bool = False
    disable_drive_downloads: bool = False
    disable_sheet_downloads: bool = False
    disable_database_downloads: bool = False
    disable_source_downloads: bool = False


config = Config()


class DownloadStatus(Enum):
    CACHED = auto()
    DOWNLOADED = auto()
    SKIPPED = auto()
    FAILED = auto()


class DownloadResult(NamedTuple):
    status: DownloadStatus
    file_path: str | None


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
