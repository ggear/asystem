import os
import sys
from pathlib import Path

import ffmpeg


# build test data with dummy file
# Analyse library on per share basis, all to do local shares only deltas, deploy to do refresh and do all
# build an item metadata yaml file, pyyaml and ffmpeg-python
# build an item transcode script if necessary, write out transcode metadata file from logs (fps, time, host, command) - mobile version as well?
# build an item replace script if necessary
# build a global xlsx, update but allow manual editing, share-dir, library, name, size, resolution (720p, 1080p, 4k), bitrate (4k, 8k, 14k), audio codec, video codec, eng audio streams, non-eng audio streams, eng subtitles, non-eng subtitles, direct play possible, required to convert, versions ready to replace
# build a global transcode script, ordered by priority, script takes in number of items to process
# build a global replace script, dry run showing which items, execute actually doing the work


def _analyse(file_path_root):
    if not os.path.isdir(file_path_root):
        print("Error: path [{}] does not exist".format(file_path_root))
        return -1
    files_analysed = 0

    ffmpeg.probe("/Users/graham/Code/asystem/src/meg_eva/media/src/test/resources/share_example_1/1/media/parents/movies/Ultra HD H264 2160p 14k DTS AC3 Eng Ger MKV (2024)/Sample Ultra HD H264 2160p 14k DTS AC3 Eng Ger MKV (2024).mkv")

    return files_analysed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: {} <media-dir>".format(sys.argv[0]))
        sys.exit(1)
    sys.exit(2 if _analyse(Path(sys.argv[1]).absolute()) < 0 else 0)
