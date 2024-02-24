import os
import sys
from pathlib import Path


def rename(file_path_root, file_path_root_processed):
    if not os.path.isdir(file_path_root):
        print("Error: path [{}] does not exist".format(file_path_root))
        return 200
    file_path_root = Path(file_path_root)
    os.makedirs(file_path_root_processed, exist_ok=True)
    file_path_root_processed = Path(file_path_root_processed)
    for file_source in ["usbdrive", "usenet/finished"]:
        for file_type in ["mkv", "mp4", "avi", "m2ts"]:
            for file_path in Path(os.path.join(file_path_root, file_source)).rglob("*." + file_type):
                file_name = file_path.name
                file_parents = (file_path.as_posix()
                                .replace(os.path.join(file_path_root.as_posix(), file_source) + "/", "").split("/"))

                file_category = "series"
                file_category = "movies"
                # If Series:
                #
                # - Move up to processed/renamed
                # Elif Movie:
                #
                # - Move up to processed/renamed
                # Else
                # - Rename dirs and file by removing all crap but leave in place

                print("{} {}".format(file_name, file_parents))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: {} <media-tmp-dir> <media-processed-dir>".format(sys.argv[0]))
        sys.exit(100)
    sys.exit(rename(Path(sys.argv[1]).absolute(), Path(sys.argv[2]).absolute()))
