"""
WARNING: This file is written by the build process, any manual edits will be lost!
"""

import argparse
import glob
import os
import sys
from pathlib import Path

from plexapi.server import PlexServer

PLEX_SHARE_ROOT = "/share"


def _refresh_plex_libraries(_plex_server):
    print("Refreshing Plex libraries ... ", end='')
    for section in sorted(_plex_server.library.sections(), key=lambda _section: _section.title):
        section.update()
    print("done")


def _get_plex_paths(_plex_server):
    sections = {}
    for section in _plex_server.library.sections():
        sections[section.title] = sorted(section.locations)
    return sections


def _set_paths_plex(_plex_server, _library_paths):
    if not _library_paths:
        return
    sections = {section.title: section for section in _plex_server.library.sections()}
    for library_name in _library_paths:
        if library_name not in sections:
            raise Exception(f"Library [{library_name}] not found in plex")
    print("Updating Plex library paths ... ", end='')
    for library_name, library_paths in _library_paths.items():
        sections[library_name].edit(location=library_paths)
    print("done")


def _get_filesystem_paths(_share_root, _plex_share_root=PLEX_SHARE_ROOT,
                          _min_depth=2, _max_depth=2, _excludes=frozenset({'audio'})):
    library_locations = {}
    share_index_root = f"{_share_root}/*"
    share_index_media_root = f"{share_index_root}/media"
    if len(glob.glob(share_index_root)) == 0:
        raise Exception(f"No shares found at [{share_index_root}], check shares are mounted")
    if len(glob.glob(share_index_root)) != len(glob.glob(share_index_media_root)):
        raise Exception(f"Could not find all share media directories at [{share_index_media_root}], check shares are all mounted")
    exclude_paths = tuple(os.sep + exclude for exclude in _excludes)
    base_paths = glob.glob(share_index_media_root)
    for base_path in base_paths:
        base_path = os.path.abspath(base_path)
        root_depth = base_path.rstrip(os.sep).count(os.sep)

        def walk_paths(current_path, root_depth=root_depth):
            current_depth = current_path.count(os.sep) - root_depth
            if current_depth > _max_depth:
                return
            try:
                with os.scandir(current_path) as it:
                    for entry in it:
                        if entry.is_dir(follow_symlinks=False):
                            entry_depth = entry.path.count(os.sep) - root_depth
                            if _min_depth <= entry_depth <= _max_depth:
                                if not entry.path.endswith(exclude_paths):
                                    library_location = _plex_share_root + entry.path.removeprefix(_share_root)
                                    library_name = (
                                        f"{os.path.basename(os.path.dirname(library_location)).title()} "
                                        f"{os.path.basename(library_location).title()}")
                                    if library_name not in library_locations:
                                        library_locations[library_name] = []
                                    library_locations[library_name].append(library_location)
                            if entry_depth < _max_depth:
                                walk_paths(entry.path)
            except PermissionError:
                pass

        walk_paths(base_path)
    return {
        _library_name: sorted(_library_locations) for _library_name, _library_locations in library_locations.items()
    }


def _refresh(_plex_server, _share_root, _plex_share_root=PLEX_SHARE_ROOT):
    try:
        plex_paths = _get_plex_paths(_plex_server)
        filesystem_paths = _get_filesystem_paths(_share_root, _plex_share_root)
        updated_paths = {}
        for library_name, library_paths in filesystem_paths.items():
            if library_name not in plex_paths:
                raise Exception(f"Library [{library_name}] not found in plex")
            existing_paths = plex_paths[library_name]
            missing_paths = [path for path in library_paths if path not in existing_paths]
            unmatched_paths = [path for path in existing_paths if path not in library_paths]
            if unmatched_paths:
                print(f"Warning: library [{library_name}] has plex paths absent from disk {unmatched_paths}")
            if missing_paths:
                updated_paths[library_name] = sorted(existing_paths + missing_paths)
        _set_paths_plex(_plex_server, updated_paths)
        _refresh_plex_libraries(_plex_server)
    except Exception as exception:
        print(f"Error: {exception}")
        return 1
    return 0


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("url")
    argument_parser.add_argument("token")
    argument_parser.add_argument("share_root")
    arguments = argument_parser.parse_args()
    sys.exit(_refresh(
        PlexServer(arguments.url, arguments.token),
        Path(arguments.share_root).absolute().as_posix()
    ))
