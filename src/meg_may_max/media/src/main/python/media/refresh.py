import glob
import os

from dotenv import load_dotenv
from plexapi.server import PlexServer

PLEX_URL = "http://plex.local.janeandgraham.com:32400"

load_dotenv(os.path.join(os.path.dirname(__file__), '../../../../.env'))
PLEX_TOKEN = os.environ['PLEX_TOKEN']
plex = PlexServer(PLEX_URL, PLEX_TOKEN)


def set_paths(library_name, library_paths):
    section = next((s for s in plex.library.sections() if s.title == library_name), None)
    if section:
        print(f"Updating library [{library_name}] paths ... ", end='')
        section.edit(location=library_paths)
        print("done")
    else:
        print(f"Error: Library [{library_name}] not found")


def get_paths(share_root, min_depth=2, max_depth=2, excludes={'audio'}):
    library_locations = {}
    exclude_paths = tuple(os.sep + exclude for exclude in excludes)
    base_paths = glob.glob(os.path.expanduser(f"{share_root}/share/*/media"))
    for base_path in base_paths:
        base_path = os.path.abspath(base_path)
        root_depth = base_path.rstrip(os.sep).count(os.sep)

        def walk(current_path):
            current_depth = current_path.count(os.sep) - root_depth
            if current_depth > max_depth:
                return
            try:
                with os.scandir(current_path) as it:
                    for entry in it:
                        if entry.is_dir(follow_symlinks=False):
                            entry_depth = entry.path.count(os.sep) - root_depth
                            if min_depth <= entry_depth <= max_depth:
                                if not entry.path.endswith(exclude_paths):
                                    library_location = entry.path.removeprefix(share_root)
                                    library_name = (f"{os.path.basename(os.path.dirname(library_location)).title()} "
                                                    f"{os.path.basename(library_location).title()}")
                                    if library_name not in library_locations:
                                        library_locations[library_name] = []
                                    library_locations[library_name].append(library_location)
                            if entry_depth < max_depth:
                                walk(entry.path)
            except PermissionError:
                pass

        walk(base_path)
    return library_locations


if __name__ == "__main__":

    # TODO: Wire into refresh, why is refresh.sh called twice - all scripts doing it, check if update required before doing update, warn if not mounted

    path = "/Users/graham/Desktop"
    for library_name, library_paths in get_paths(path).items():
        set_paths(library_name, sorted(library_paths))
