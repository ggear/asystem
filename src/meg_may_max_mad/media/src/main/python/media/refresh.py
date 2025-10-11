import argparse
import glob
import os
import sys
from pathlib import Path

from plexapi.server import PlexServer


def _refresh_plex_libraries(_plex_server):
    for section in sorted(_plex_server.library.sections(), key=lambda _section: _section.title):
        print(f"Scanning '{_plex_server._baseurl}?library={section.title.replace(' ', '+')}' paths ... ", end='')
        section.update()
        section.analyze()
        print("done")


def _get_plex_paths(_plex_server):
    sections = {}
    for section in _plex_server.library.sections():
        sections[section.title] = sorted(section.locations)
    return sections


def _set_paths_plex(_plex_server, _library_name, _library_paths):
    section = next((s for s in _plex_server.library.sections() if s.title == _library_name), None)
    if section:
        print(f"Updating '{_plex_server._baseurl}?library={_library_name.replace(' ', '+')}' paths ... ", end='')
        section.edit(location=_library_paths)
        print("done")
    else:
        raise Exception(f"Library [{_library_name}] not found in plex")


def _get_filesystem_paths(_share_root, _min_depth=2, _max_depth=2, _excludes={'audio'}):
    library_locations = {}
    share_index_root = f"{_share_root}/share/*"
    share_index_media_root = f"{share_index_root}/media"
    if len(glob.glob(share_index_root)) == 0:
        raise Exception(f"No shares found  at "
                        f"[{share_index_root}], check shares are mounted")
    if len(glob.glob(share_index_root)) != len(glob.glob(share_index_media_root)):
        raise Exception(f"Could not find all share media directories at "
                        f"[{share_index_media_root}], check shares are all mounted")
    exclude_paths = tuple(os.sep + exclude for exclude in _excludes)
    base_paths = glob.glob(share_index_media_root)
    for base_path in base_paths:
        base_path = os.path.abspath(base_path)
        root_depth = base_path.rstrip(os.sep).count(os.sep)

        def walk_paths(current_path):
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
                                    library_location = entry.path.removeprefix(_share_root)
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


def _refresh(_plex_server, _share_root):
    try:
        plex_paths = _get_plex_paths(_plex_server)
        filesystem_paths = _get_filesystem_paths(_share_root)
        for library_name, library_paths in filesystem_paths.items():
            if library_name in plex_paths:
                if plex_paths[library_name] != library_paths:
                    _set_paths_plex(_plex_server, library_name, library_paths)
            else:
                raise Exception(f"Library [{library_name}] not found in plex")
        _refresh_plex_libraries(_plex_server)
    except Exception as exception:
        print(f"Error: {exception}")
        return 1
    return 0


if __name__ == "__main__":
    # TODO: Remove this when .env is in place
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '../../../../.env'))
    _plex_url = "https://plex.janeandgraham.com"
    _plex_token = os.environ['PLEX_TOKEN']
    _share_root = "/Users/graham/Desktop"
    _refresh(PlexServer(_plex_url, _plex_token), _share_root)

    # argument_parser = argparse.ArgumentParser()
    # argument_parser.add_argument("url")
    # argument_parser.add_argument("token")
    # argument_parser.add_argument("directory")
    # arguments = argument_parser.parse_args()
    # sys.exit(1 if _refresh(
    #     PlexServer(arguments.url, arguments.token),
    #     Path(arguments.directory).absolute().as_posix()
    # ) < 0 else 0)
