"""
WARNING: This file is written by the build process, any manual edits will be lost!
"""

import argparse
import glob
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from pathlib import Path

import requests
from plexapi.server import PlexServer

BANNER = "#" * 126

API_TIMEOUT_SECONDS = 10
API_COMMAND_TIMEOUT_SECONDS = 120
API_COMMAND_POLL_SECONDS = 0.2
PLEX_ADDED_WITHIN_DAYS = 1

SONARR_QUALITY_PROFILE = "HD-1080p"


class Exit(IntEnum):
    PASS = 0

    FAIL_ARGUMENTS = 1
    FAIL_FILESYSTEM = 2

    FAIL_SABNZBD_CONNECT = 20
    FAIL_SABNZBD_ARCHIVE = 21
    FAIL_SABNZBD_DOWNLOAD = 22

    FAIL_SONARR_CONNECT = 30
    FAIL_SONARR_CONFIGURE = 31
    FAIL_SONARR_ACTIVITY = 32
    FAIL_SONARR_REFRESH = 33
    FAIL_SONARR_MISSING = 34

    FAIL_PLEX_CONNECT = 40
    FAIL_PLEX_LIBRARY = 41
    FAIL_PLEX_PATHS = 42
    FAIL_PLEX_REFRESH = 43


def _print_error(_message, _exception=None):
    print(f"\nError: {_message}, processing interrupted")
    if _exception is not None:
        for detail in "".join(traceback.format_exception(_exception)).rstrip().split("\n"):
            print(f"    {detail}")
    print()


def _print_messages(_messages):
    if _messages:
        print()
        for message in _messages:
            print(message)
        print()


def _get_env(_name):
    value = os.environ.get(_name)
    if not value:
        raise Exception(f"Environment variable [{_name}] is not set, check the media environment is sourced")
    return value


def _get_share_paths(_share_root: str, _min_depth=2, _max_depth=2, _excludes=frozenset({'audio'})):
    library_locations = {}
    share_root = os.path.abspath(_share_root)
    share_index_root = f"{share_root}/*"
    share_index_media_root = f"{share_index_root}/media"
    share_index_paths = glob.glob(share_index_root)
    share_index_media_paths = glob.glob(share_index_media_root)
    if len(share_index_paths) == 0:
        raise Exception(f"No shares found at [{share_index_root}], check shares are mounted")
    if len(share_index_paths) != len(share_index_media_paths):
        raise Exception(f"Could not find all share media directories at [{share_index_media_root}], check shares are all mounted")
    exclude_paths = tuple(os.sep + exclude for exclude in _excludes)
    for base_path in share_index_media_paths:
        base_path = os.path.abspath(base_path)
        root_depth = base_path.rstrip(os.sep).count(os.sep)

        def walk_paths(current_path: str):
            try:
                with os.scandir(current_path) as it:
                    for entry in it:
                        if entry.is_dir(follow_symlinks=False):
                            entry_depth = entry.path.count(os.sep) - root_depth
                            if _min_depth <= entry_depth <= _max_depth:
                                if not entry.path.endswith(exclude_paths):
                                    library_location = "/share" + entry.path.removeprefix(share_root)
                                    library_name = (
                                        f"{os.path.basename(os.path.dirname(library_location)).title()} "
                                        f"{os.path.basename(library_location).title()}")
                                    if library_name not in library_locations:
                                        library_locations[library_name] = []
                                    library_locations[library_name].append(library_location)
                            if entry_depth < _max_depth:
                                walk_paths(entry.path)
            except PermissionError as exception:
                raise Exception(f"Could not read share directory [{current_path}], check share permissions") from exception

        walk_paths(base_path)
    return {
        _library_name: sorted(_library_locations) for _library_name, _library_locations in library_locations.items()
    }


def _refresh_plex(_share_paths):
    try:
        plex_server = PlexServer(_get_env("PLEX_URL"), _get_env("PLEX_TOKEN"), timeout=API_TIMEOUT_SECONDS)
        plex_sections = {section.title: section for section in plex_server.library.sections()}
    except Exception as exception:
        _print_error("could not connect to plex", exception)
        return Exit.FAIL_PLEX_CONNECT
    updated_paths = {}
    library_messages = []
    for library_name, library_paths in _share_paths.items():
        if library_name not in plex_sections:
            _print_error(f"library [{library_name}] not found in plex")
            return Exit.FAIL_PLEX_LIBRARY
        existing_paths = sorted(plex_sections[library_name].locations)
        missing_paths = [path for path in library_paths if path not in existing_paths]
        unmatched_paths = [path for path in existing_paths if path not in library_paths]
        if unmatched_paths:
            library_messages.append(
                f"Warning: library [{library_name}] has plex paths absent from disk {unmatched_paths}")
        if missing_paths:
            updated_paths[library_name] = sorted(existing_paths + missing_paths)
    _print_messages(library_messages)
    if updated_paths:
        try:
            for library_name, library_paths in updated_paths.items():
                plex_sections[library_name].edit(location=library_paths)
        except Exception as exception:
            _print_error("could not update plex library paths", exception)
            return Exit.FAIL_PLEX_PATHS
    try:
        for library_name in sorted(plex_sections):
            plex_sections[library_name].update()
    except Exception as exception:
        _print_error("could not refresh plex libraries", exception)
        return Exit.FAIL_PLEX_REFRESH
    item_messages = []
    added_within = datetime.now(timezone.utc) - timedelta(days=PLEX_ADDED_WITHIN_DAYS)
    try:
        for library_name in sorted(plex_sections):
            for item in plex_sections[library_name].search(filters={"addedAt>>": added_within}):
                if not str(getattr(item, "guid", "")).startswith("plex://"):
                    item_messages.append(f"Warning: item [{item.title}] in library [{library_name}] not matched by plex")
    except Exception as exception:
        item_messages.append(f"Warning: could not check plex matches, {exception}")
    _print_messages(item_messages)
    return Exit.PASS


def _refresh_sabnzbd(_share_paths):
    def get_sabnzbd(**_parameters):
        response = requests.get(f"{sabnzbd_url}/api", timeout=API_TIMEOUT_SECONDS, params={"output": "json", "apikey": sabnzbd_api_key, **_parameters})
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("status") is False:
            raise Exception(f"sabnzbd api returned [{payload.get('error', 'unknown error')}]")
        return payload

    def get_sabnzbd_slots(**_filters):
        slots = []
        while True:
            history = get_sabnzbd(mode="history", start=len(slots), limit=100, **_filters)["history"]
            slots += history["slots"]
            if not history["slots"] or len(slots) >= history["noofslots"]:
                return slots

    try:
        sabnzbd_url = _get_env("SABNZBD_URL")
        sabnzbd_api_key = _get_env("SABNZBD_API_KEY")
        completed_count = get_sabnzbd(mode="history", limit=1, status="Completed")["history"]["noofslots"]
        failed_slots = get_sabnzbd_slots(failed_only=1)
        queue_slots = get_sabnzbd(mode="queue")["queue"]["slots"]
    except Exception as exception:
        _print_error("could not connect to sabnzbd", exception)
        return Exit.FAIL_SABNZBD_CONNECT
    if completed_count:
        try:
            get_sabnzbd(mode="history", name="delete", value="completed", archive=1)
        except Exception as exception:
            _print_error("could not archive completed sabnzbd downloads", exception)
            return Exit.FAIL_SABNZBD_ARCHIVE
    for slot in queue_slots:
        print(f"Download [sabnzbd] of [{slot['filename']}] at [{slot['percentage']}%] with [{slot['timeleft']}] remaining")
    _print_messages([f"Error: download [{slot['name']}] failed [{slot['fail_message']}]"
                     for slot in failed_slots])
    if failed_slots:
        try:
            get_sabnzbd(mode="history", name="delete", value="failed", archive=1)
        except Exception as exception:
            _print_error("could not archive failed sabnzbd downloads", exception)
            return Exit.FAIL_SABNZBD_ARCHIVE
        return Exit.FAIL_SABNZBD_DOWNLOAD
    return Exit.PASS


def _refresh_sonarr(_share_paths):
    def get_sonarr(_resource):
        response = requests.get(f"{sonarr_api}/{_resource}", timeout=API_TIMEOUT_SECONDS, headers={"X-Api-Key": sonarr_api_key})
        response.raise_for_status()
        return response.json()

    def post_sonarr_command(**_command):
        response = requests.post(f"{sonarr_api}/command", timeout=API_TIMEOUT_SECONDS, headers={"X-Api-Key": sonarr_api_key}, json=_command)
        response.raise_for_status()
        return response.json()

    def put_sonarr(_resource, _payload):
        response = requests.put(f"{sonarr_api}/{_resource}", timeout=API_TIMEOUT_SECONDS, headers={"X-Api-Key": sonarr_api_key}, json=_payload)
        response.raise_for_status()
        return response.json()

    def wait_sonarr_command(**_command):
        command = post_sonarr_command(**_command)
        deadline = time.perf_counter() + API_COMMAND_TIMEOUT_SECONDS
        while command.get("status") in ("queued", "started"):
            if time.perf_counter() > deadline:
                raise Exception(f"timed out after [{API_COMMAND_TIMEOUT_SECONDS}] seconds waiting for command [{_command['name']}]")
            command = get_sonarr(f"command/{command['id']}")
            if command.get("status") in ("queued", "started"):
                time.sleep(API_COMMAND_POLL_SECONDS)
        if command.get("status") != "completed" or command.get("result") not in (None, "successful"):
            raise Exception(f"command [{_command['name']}] ended with status [{command.get('status')}] result [{command.get('result')}] message [{command.get('message')}]")
        return command

    def get_sonarr_queue():
        records = []
        page = 1
        while True:
            queue = get_sonarr(f"queue?page={page}&pageSize=100")
            records += queue["records"]
            if not queue["records"] or len(records) >= queue["totalRecords"]:
                return records
            page += 1

    try:
        sonarr_api = f"{_get_env('SONARR_URL')}/api/v3"
        sonarr_api_key = _get_env("SONARR_API_KEY")
        sonarr_series = get_sonarr("series")
        sonarr_profiles = {profile["id"]: profile["name"] for profile in get_sonarr("qualityProfile")}
    except Exception as exception:
        _print_error("could not connect to sonarr", exception)
        return Exit.FAIL_SONARR_CONNECT
    quality_profile_id = next(
        (profile_id for profile_id, name in sonarr_profiles.items() if name == SONARR_QUALITY_PROFILE), None)
    if quality_profile_id is None:
        _print_messages([f"Warning: quality profile [{SONARR_QUALITY_PROFILE}] not found in sonarr"])
    unconfigured_series = [series for series in sonarr_series if not series.get("monitored") or any(
        not season.get("monitored") for season in series.get("seasons", []) if season.get("seasonNumber"))
        or (quality_profile_id is not None and series.get("qualityProfileId") != quality_profile_id)]
    if unconfigured_series:
        try:
            for series in unconfigured_series:
                series["monitored"] = True
                if quality_profile_id is not None:
                    series["qualityProfileId"] = quality_profile_id
                for season in series.get("seasons", []):
                    if season.get("seasonNumber"):
                        season["monitored"] = True
                put_sonarr(f"series/{series['id']}", series)
        except Exception as exception:
            _print_error("could not configure sonarr series", exception)
            return Exit.FAIL_SONARR_CONFIGURE
    try:
        wait_sonarr_command(name="RefreshMonitoredDownloads")
        sonarr_queue = get_sonarr_queue()
    except Exception as exception:
        _print_error("could not refresh sonarr activity", exception)
        return Exit.FAIL_SONARR_ACTIVITY
    queued_series_ids = {record.get("seriesId") for record in sonarr_queue}
    series_messages = []
    missing_series = []
    for series in sonarr_series:
        try:
            wait_sonarr_command(name="RescanSeries", seriesId=series["id"])
            wait_sonarr_command(name="RefreshSeries", seriesId=series["id"])
            series = get_sonarr(f"series/{series['id']}")
        except Exception as exception:
            _print_error(f"could not refresh sonarr series [{series['title']}]", exception)
            return Exit.FAIL_SONARR_REFRESH
        statistics = series.get("statistics", {})
        missing_episodes = statistics.get("episodeCount", 0) - statistics.get("episodeFileCount", 0)
        if series.get("ended") and statistics.get("percentOfEpisodes") == 100:
            series_messages.append(f"Warning: series [{series['title']}] is complete and ended")
        if missing_episodes > 0 and series["id"] not in queued_series_ids:
            missing_series.append(series)
            series_messages.append(
                f"Error: series [{series['title']}] is missing [{missing_episodes}] episodes with no download queued")
    _print_messages(series_messages)
    if missing_series:
        return Exit.FAIL_SONARR_MISSING
    return Exit.PASS


def _refresh(_share_root):
    def refresh_service(_name, _refresh_function):
        print(f"Starting [{_name}] refresh")
        started = time.perf_counter()
        exit_value = _refresh_function(share_paths)
        print(f"Finished [{_name}] refresh in [{round(time.perf_counter() - started, 1)}] seconds")
        return exit_value

    print(BANNER)
    print("Refresh")
    print(BANNER)
    try:
        share_paths = _get_share_paths(_share_root)
    except Exception as exception:
        _print_error(f"{exception}", exception)
        print(BANNER)
        return Exit.FAIL_FILESYSTEM
    exit_values = [
        refresh_service("sabnzbd", _refresh_sabnzbd),
        refresh_service("sonarr", _refresh_sonarr),
        refresh_service("plex", _refresh_plex),
    ]
    print(BANNER)
    return next(filter(None, exit_values), Exit.PASS)


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("share_root", nargs="?", default=os.environ.get("SHARE_ROOT"))
    arguments = argument_parser.parse_args()
    if not arguments.share_root:
        _print_error("no share root argument or [SHARE_ROOT] environment variable set")
        sys.exit(Exit.FAIL_ARGUMENTS)
    sys.exit(_refresh(Path(arguments.share_root).absolute().as_posix()))
