import os
import sys
from pathlib import Path

import ffmpeg
import yaml


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

    # TODO: Loop over all files

    file_source_path = os.path.join(file_path_root, "parents/movies/Sample Ultra HD H264 2160p 14k DTS AC3 Eng Ger MKV (2024)/"
                                                    "Sample Ultra HD H264 2160p 14k DTS AC3 Eng Ger MKV (2024).mkv")
    file_metadata_path = os.path.join(file_path_root, "parents/movies/Sample Ultra HD H264 2160p 14k DTS AC3 Eng Ger MKV (2024)/"
                                                      ".metadata.yaml")
    file_probe = ffmpeg.probe(file_source_path)

    file_probe_filtered = []
    file_probe_filtered.append({"filename": os.path.basename(file_probe["format"]["filename"])})
    file_probe_filtered.append({"format_name": file_probe["format"]["format_name"]})
    file_probe_filtered.append({"bit_rate": int(file_probe["format"]["bit_rate"])})
    file_probe_filtered.append({"size": int(file_probe["format"]["size"])})
    file_probe_filtered.append({"nb_streams": int(file_probe["format"]["nb_streams"])})

    # TODO: Break up into video, audio, subtitle, other streams
    file_probe_streams_filtered = []
    file_probe_filtered.append({"streams": file_probe_streams_filtered})
    for file_probe_stream in file_probe["streams"]:
        file_probe_stream_filtered = []
        file_probe_streams_filtered.append({file_probe_stream["index"]: file_probe_stream_filtered})
        file_probe_stream_filtered_type = file_probe_stream["codec_type"]
        file_probe_stream_filtered.append({"codec_type": file_probe_stream_filtered_type})
        file_probe_stream_filtered.append({"codec_name": file_probe_stream["codec_name"]})

    with open(file_metadata_path, 'w') as file_metadata:
        yaml.dump(file_probe_filtered, file_metadata)
    with open(file_metadata_path, 'r') as file_metadata:
        print(file_metadata.read())

    # TODO: Unwrap lists into dicts, root and streams
    with open(file_metadata_path, 'r') as file_metadata:
        print(yaml.safe_load(file_metadata))

    return files_analysed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: {} <media-dir>".format(sys.argv[0]))
        sys.exit(1)
    sys.exit(2 if _analyse(Path(sys.argv[1]).absolute()) < 0 else 0)
