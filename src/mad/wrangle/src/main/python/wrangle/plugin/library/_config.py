import os
import os.path
from dataclasses import dataclass
from enum import Enum, auto
from os.path import abspath, basename, dirname, isdir, isfile
from typing import NamedTuple

PL_PRINT_ROWS = 6
PD_PRINT_ROWS = 3

CTR_LBL_PAD = '.'
CTR_LBL_WIDTH = 26
CTR_SRC_DATA = "Data"
CTR_SRC_FILES = "Files"
CTR_SRC_EGRESS = "Egress"
CTR_SRC_SOURCES = "Sources"
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
CTR_ACT_QUEUE_ROWS = "Queue Rows"
CTR_ACT_QUEUE_COLUMNS = "Queue Columns"
CTR_ACT_ERRORED = "Errored"
CTR_ACT_PROCESSED = "Processed"
CTR_ACT_SKIPPED = "Skipped"
CTR_ACT_DOWNLOADED = "Downloaded"
CTR_ACT_CACHED = "Cached"
CTR_ACT_PERSISTED = "Persisted"
CTR_ACT_UPLOADED = "Uploaded"


class DriveScope(Enum):
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class DownloadStatus(Enum):
    CACHED = auto()
    DOWNLOADED = auto()
    FAILED = auto()


class DownloadResult(NamedTuple):
    status: DownloadStatus
    file_path: str | None


@dataclass
class Config:
    log_level: str = "info"
    drive_scope: DriveScope = DriveScope.PRODUCTION
    force_reprocessing: bool = False
    force_downloads: bool = False
    disable_uploads: bool = False
    disable_downloads: bool = False


config = Config()


class DriveScopes:
    def __init__(self, **scopes):
        valid = {s.value for s in DriveScope}
        for name in scopes:
            if name not in valid:
                raise ValueError(f"DriveScopes unknown scope '{name}'; valid: {sorted(valid)}")
        required = {s.value for s in DriveScope if s != DriveScope.TESTING}
        missing_scopes = required - set(scopes)
        if missing_scopes:
            raise ValueError(f"DriveScopes missing required scopes: {sorted(missing_scopes)}")
        all_keys = set().union(*(set(v) for v in scopes.values()))
        for scope_name, keys in scopes.items():
            missing_keys = all_keys - set(keys)
            if missing_keys:
                raise ValueError(f"DriveScopes scope '{scope_name}' missing keys: {sorted(missing_keys)}")
        object.__setattr__(self, '_scopes', scopes)

    def __getattr__(self, name):
        scope = config.drive_scope
        if scope == DriveScope.TESTING:
            return None
        keys = object.__getattribute__(self, '_scopes')[scope.value]
        if name not in keys:
            raise AttributeError(f"DriveScopes has no key '{name}' for scope '{scope.value}'")
        return keys[name]


def get_file(file_name):
    if isfile(file_name):
        return file_name
    file_name = basename(file_name)
    working = dirname(abspath(__file__))
    paths = [
        f"/root/{file_name}",
        f"/etc/telegraf/{file_name}",
        f"{working}/../../../../resources/{file_name}",
        f"{working}/../../../../resources/config/{file_name}",
        f"{working}/../../../../../../{file_name}",
    ]
    for path in paths:
        if isfile(path):
            return path
    raise IOError(f"Could not find file [{file_name}] in the usual places {paths}")


def get_dir(dir_name):
    working = dirname(abspath(__file__))
    parent_paths = [
        "/asystem/runtime",
        f"{working}/../../../../../../target",
    ]
    for parent_path in parent_paths:
        if isdir(parent_path):
            path = abspath(f"{parent_path}/{dir_name}")
            if not isdir(path):
                os.makedirs(path)
            return path
    raise IOError(f"Could not find path in the usual places {parent_paths}")


def load_profile(profile_path):
    profile = {}
    with open(get_file(profile_path), 'r') as profile_file:
        for profile_line in profile_file:
            profile_line = profile_line.replace("export ", "").rstrip()
            if "=" not in profile_line:
                continue
            if profile_line.startswith("#"):
                continue
            profile_key, profile_value = profile_line.split("=", 1)
            profile[profile_key] = profile_value
    return profile
