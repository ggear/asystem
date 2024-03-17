import os
import re
import shutil
import sys
from pathlib import Path


def _rename(file_path_root):
    if not os.path.isdir(file_path_root):
        print("Error: path [{}] does not exist".format(file_path_root))
        return -1
    files_renamed = 0
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
                        file_series_search = re.search("(.*)[eE]([0-9]?[0-9]+).*\." + file_type, file_name)
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
                        file_name_new = "{}-S{}E{}.{}".format(
                            file_dir_new.replace(' ', '-'),
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
                            file_year_search = re.search("(.*)(19|20)([0-9][0-9]).*", file_metadata)
                            if file_year_search is not None:
                                file_year_search_groups = file_year_search.groups()
                                file_name_new = file_year_search_groups[0].replace('.', ' ').strip().title()
                                file_name_new = re.sub(r'[^a-zA-Z0-9 ]+', '', file_name_new).strip()
                                file_name_new = "{} ({}{})".format(file_name_new, file_year_search_groups[1], file_year_search_groups[2])
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
                    file_path_new = Path(file_path_new)
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
                    print(".{} -> .{}".format(
                        file_path.as_posix().replace(file_path_root.as_posix(), ""),
                        file_path_new.as_posix().replace(file_path_root.as_posix(), ""))
                    )
                    shutil.move(file_path, file_path_new)
                    files_renamed += 1
    for file_path_root_to_delete in file_path_roots_to_delete:
        shutil.rmtree(file_path_root_to_delete, ignore_errors=True)
    return files_renamed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: {} <media-tmp-dir>".format(sys.argv[0]))
        sys.exit(1)
    sys.exit(2 if _rename(Path(sys.argv[1]).absolute()) < 0 else 0)
