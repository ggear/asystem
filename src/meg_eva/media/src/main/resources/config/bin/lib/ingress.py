"""
WARNING: This file is written by the build process, any manual edits will be lost!
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path


def _rename(file_path_root, verbose=False):
    if not os.path.isdir(file_path_root):
        print("Error: path [{}] does not exist".format(file_path_root))
        return -1
    files_renamed = 0
    print("Renaming {} ... ".format(file_path_root), end=("\n" if verbose else ""))
    sys.stdout.flush()
    file_path_root = Path(file_path_root)
    file_path_roots_to_delete = []
    for file_source in ["usbdrive", "usenet/finished", "finished"]:
        file_path_source = Path(os.path.join(file_path_root, file_source))
        file_path_processed = Path(file_path_source, "__RENAMED")
        for file_type in ["mkv", "mp4", "avi", "m2ts"]:
            for file_path in Path(os.path.join(file_path_root, file_source)).rglob("*." + file_type):
                file_to_be_renamed = False
                file_path_source_relative = file_path.as_posix().replace(os.path.join(file_path_root, file_source) + "/", "")
                if not file_path_source_relative.startswith('_'):
                    file_path_new = None
                    file_name_new = None
                    file_to_be_renamed = True
                    file_name = file_path.name
                    file_parents = file_path_source_relative.removeprefix("series/").removeprefix("movies/").split("/")
                    file_parents.reverse()
                    file_path_root_source = file_path.parent
                    while file_path_root_source.parent.name not in ["series", "movies", "finished"] and \
                            file_path_root_source.parent != file_path_source:
                        file_path_root_source = file_path_root_source.parent
                    if file_path_root_source.name not in ["series", "movies", "finished"]:
                        file_path_roots_to_delete.append(file_path_root_source)
                    file_series_search_groups = None
                    file_series_search = re.search("(.*)[sS]([0-9]?[0-9]+)[eE]([0-9]?[0-9]+).*\." + file_type, file_name)
                    if file_series_search is None:
                        file_series_search = re.search("(.*[^a-zA-Z0-9 ]+)[eE]([0-9]?[0-9]+).*\." + file_type, file_name)
                        if file_series_search is not None:
                            file_series_search_groups = [file_series_search.groups()[0], "01"] + list(file_series_search.groups()[1:])
                    else:
                        file_series_search_groups = file_series_search.groups()
                    if file_series_search_groups is not None:
                        file_category = "series"
                        file_dir_new = (file_series_search_groups[0]
                                        .replace('.', ' ').strip().replace(' ', '-'))
                        file_year_search = re.search("(20[0-9][0-9])", file_dir_new)
                        if file_year_search is not None:
                            file_dir_new = file_dir_new.replace(file_year_search.groups()[0], "") \
                                .replace('-', ' ').strip().replace(' ', '-')
                        file_dir_new = file_dir_new.replace('-', ' ').strip()
                        file_dir_new = re.sub(r'[^a-zA-Z0-9 ]+', '', file_dir_new).strip()
                        file_name_new = "{} S{}E{}.{}".format(
                            file_dir_new,
                            file_series_search_groups[1],
                            file_series_search_groups[2],
                            file_type
                        )
                        file_path_new = "{}/{}/{}/Season {}/{}".format(
                            file_path_processed,
                            file_category,
                            file_dir_new,
                            int(file_series_search_groups[1]),
                            file_name_new
                        )
                    else:
                        file_category = "movies"
                        for file_metadata in file_parents:
                            file_year_search_groups = re.findall("19[4-9][0-9]|20[0-9][0-9]", file_metadata)
                            if len(file_year_search_groups) > 0:
                                file_name_new = file_metadata.split(file_year_search_groups[0])[0].replace('.', ' ').strip().title()
                                file_name_new = re.sub(r'[^a-zA-Z0-9 ]+', '', file_name_new).strip()
                                file_name_new = "{} ({})".format(file_name_new, file_year_search_groups[0])
                                file_path_new = "{}/{}/{}/{}.{}".format(
                                    file_path_processed,
                                    file_category,
                                    file_name_new,
                                    file_name_new,
                                    file_type,
                                )
                                file_name_new = "{}.{}".format(file_name_new, file_type)
                                break
                        if file_name_new is None:
                            file_name_new = "-".join(file_parents[1:])
                            file_name_new = "{}-{}".format(file_name_new, file_name.replace("." + file_type, ""))
                            file_name_new = re.sub(r'[^a-zA-Z0-9 ]+', ' ', file_name_new).strip().replace(' ', '-')
                            file_name_new = re.sub(r'[-][-]+', ' ', file_name_new).strip().replace(' ', '-')
                            file_path_new = "{}/{}/{}/{}.{}".format(
                                file_path_processed,
                                file_category,
                                file_name_new,
                                file_name_new,
                                file_type,
                            )
                            file_name_new = "{}.{}".format(file_name_new, file_type)
                if file_to_be_renamed:
                    file_path_new = Path(' '.join(file_path_new.split()))
                    if len(file_path_new.name) > 100:
                        file_path_new = Path("{}/{}/{}.{}".format(
                            file_path_new.parent.parent,
                            file_path_new.name[:100],
                            file_path_new.name[:100],
                            file_type
                        ))

                    suffix = 0
                    while os.path.isfile(file_path_new):
                        file_path_new = Path("{}_{}.{}".format(
                            file_path_new.as_posix().replace("." + file_type, ""),
                            suffix,
                            file_type,
                        ))
                    os.makedirs(file_path_new.parent, exist_ok=True)
                    _set_permissions(file_path_new.parent, 0o777)
                    if verbose:
                        print(".{} -> .{}".format(
                            file_path.as_posix().replace(file_path_root.as_posix(), ""),
                            file_path_new.as_posix().replace(file_path_root.as_posix(), ""))
                        )
                    shutil.move(file_path, file_path_new)
                    _set_permissions(file_path_new, 0o777)
                    files_renamed += 1
    for file_path_root_to_delete in file_path_roots_to_delete:
        shutil.rmtree(file_path_root_to_delete, ignore_errors=True)
    for file_path_processed_dir, file_path_processed_dirs, file_path_processed_names in os.walk(file_path_processed):
        _set_permissions(file_path_processed_dir, 0o777)
        for filename in file_path_processed_names:
            _set_permissions(os.path.join(file_path_processed_dir, filename), 0o777)
    print("{}done".format("Renaming {} ".format(file_path_root) if verbose else ""))
    sys.stdout.flush()
    return files_renamed


def _set_permissions(_path, _mode=0o644):
    os.chmod(_path, _mode)
    try:
        os.chown(_path, 1000, 100)
    except PermissionError:
        pass


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--verbose", default=False, action="store_true")
    argument_parser.add_argument("directory")
    arguments = argument_parser.parse_args()
    sys.exit(2 if _rename(
        Path(arguments.directory).absolute().as_posix(),
        arguments.verbose,
    ) < 0 else 0)
