import argparse
import sys
from pathlib import Path

from subtitle_filter import Subtitles

# TODO: Remove SDH cruft, merge lines, rename titles English, English (Forced)

def _subtitles(file_path_root):
    subtitles = Subtitles("/path/to/sub.srt")
    subtitles.filter()
    subtitles.save()
    return 0


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("directory")
    arguments = argument_parser.parse_args()
    sys.exit(1 if _subtitles(
        Path(arguments.directory).absolute().as_posix(),
    ) < 0 else 0)
