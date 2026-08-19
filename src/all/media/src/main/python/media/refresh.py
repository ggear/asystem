import argparse
import glob
import os
import sys
from enum import IntEnum
from pathlib import Path

from plexapi.server import PlexServer


class Exit(IntEnum):
    PASS = 0

    FAIL_ARGUMENTS = 1
    FAIL_FILESYSTEM = 2

    FAIL_SABNZBD = 20

    FAIL_SONARR = 30

    FAIL_PLEX_CONNECT = 40
    FAIL_PLEX_LIBRARY = 41
    FAIL_PLEX_PATHS = 42
    FAIL_PLEX_REFRESH = 43


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
        plex_server = PlexServer(_get_env("PLEX_URL"), _get_env("PLEX_TOKEN"))
        plex_sections = {section.title: section for section in plex_server.library.sections()}
    except Exception as exception:
        print(f"Error: could not connect to plex [{exception}]")
        return Exit.FAIL_PLEX_CONNECT
    updated_paths = {}
    for library_name, library_paths in _share_paths.items():
        if library_name not in plex_sections:
            print(f"Error: library [{library_name}] not found in plex")
            return Exit.FAIL_PLEX_LIBRARY
        existing_paths = sorted(plex_sections[library_name].locations)
        missing_paths = [path for path in library_paths if path not in existing_paths]
        unmatched_paths = [path for path in existing_paths if path not in library_paths]
        if unmatched_paths:
            print(f"Warning: library [{library_name}] has plex paths absent from disk {unmatched_paths}")
        if missing_paths:
            updated_paths[library_name] = sorted(existing_paths + missing_paths)
    if updated_paths:
        print("Updating Plex library paths ... ", end='')
        try:
            for library_name, library_paths in updated_paths.items():
                plex_sections[library_name].edit(location=library_paths)
        except Exception as exception:
            print(f"\nError: could not update plex library paths [{exception}]")
            return Exit.FAIL_PLEX_PATHS
        print("done")
    print("Refreshing Plex libraries ... ", end='')
    try:
        for library_name in sorted(plex_sections):
            plex_sections[library_name].update()
    except Exception as exception:
        print(f"\nError: could not refresh plex libraries [{exception}]")
        return Exit.FAIL_PLEX_REFRESH
    print("done")
    return Exit.PASS


def _refresh_sabnzbd(_share_paths):
    print("Refreshing Sabnzbd ... skipped, not implemented")  # TODO
    return Exit.PASS


def _refresh_sonarr(_share_paths):
    print("Refreshing Sonarr ... skipped, not implemented")  # TODO
    return Exit.PASS


def _refresh(_share_root):
    try:
        share_paths = _get_share_paths(_share_root)
    except Exception as exception:
        print(f"Error: {exception}")
        return Exit.FAIL_FILESYSTEM
    exit_values = [
        _refresh_sabnzbd(share_paths),
        _refresh_sonarr(share_paths),
        _refresh_plex(share_paths),
    ]
    return next(filter(None, exit_values), Exit.PASS)


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("share_root", nargs="?", default=os.environ.get("SHARE_ROOT"))
    arguments = argument_parser.parse_args()
    if not arguments.share_root:
        print("Error: no share root argument or [SHARE_ROOT] environment variable set")
        sys.exit(Exit.FAIL_ARGUMENTS)
    sys.exit(_refresh(Path(arguments.share_root).absolute().as_posix()))
