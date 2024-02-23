import os
import sys
from pathlib import Path

if __name__ == "__main__":

    # TODO
    sys.argv = ["main", "/Users/graham/Code/asystem/src/meg_eva/media/src/test/resources/share_tmp_example_1"]

    if len(sys.argv) != 2:
        print("Usage: {} <media-tmp-dir>".format(sys.argv[0]))
        sys.exit(1)
    if not os.path.isdir(sys.argv[1]):
        print("Error: path [{}] does not exist".format(sys.argv[1]))
        sys.exit(2)
    file_path_root = Path(sys.argv[1]).absolute()
    for file_source in ["usbdrive", "usenet/finished"]:
        for file_type in ["mkv", "mp4", "avi", "rar", "m2ts"]:
            for file_path in Path(os.path.join(file_path_root, file_source)).rglob("*." + file_type):
                file_name = file_path.name
                file_parents = (file_path.as_posix()
                                .replace(os.path.join(file_path_root.as_posix(), file_source) + "/", "").split("/"))

                file_category = "series"
                file_category = "movies"
                # If Series:
                #
                # - Move up to processed
                # Elif Movie:
                #
                # - Move up to processed
                # Else
                # - Rename dirs and file by removing all crap but leave in place

                print("{} {}".format(file_name, file_parents))
