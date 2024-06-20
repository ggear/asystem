import argparse
import os
import sys
from collections import OrderedDict
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


def _analyse(file_path_root, verbose=False, refresh=False):
    if not os.path.isdir(file_path_root):
        print("Error: path [{}] does not exist".format(file_path_root))
        return -1
    files_analysed = 0
    print("Analysing {} ... ".format(file_path_root), end=("\n" if verbose else ""))
    for file_dir_path, _, file_names in os.walk(file_path_root):
        for file_name in file_names:
            file_source_path = os.path.join(file_dir_path, file_name)
            file_source_relative_dir = "." + file_dir_path.replace(file_path_root, "")
            file_source_relative_dir_path_tokens = file_source_relative_dir.split(os.sep)
            file_metadata_path = os.path.join(file_dir_path, "{}.yaml".format(os.path.splitext(file_name)[0]))

            # TODO: Make work if path more specific, walk up tree, unit test, add command line for specific file, switch on verbosity
            file_library_scope = file_source_relative_dir_path_tokens[1] \
                if len(file_source_relative_dir_path_tokens) > 3 else ""
            file_library_type = file_source_relative_dir_path_tokens[2] \
                if len(file_source_relative_dir_path_tokens) > 3 else ""

            if verbose:
                print("{} ... ".format(os.path.join(file_source_relative_dir, file_name)), end='')
            if file_library_type not in {"movies", "series"}:
                if verbose:
                    print("ignoring library type [{}]".format(file_library_type))
                break;
            file_extension = os.path.splitext(file_name)[1]
            if file_extension not in {".mkv", ".mp4", ".avi"}:
                if file_extension not in {".yaml"}:
                    if verbose:
                        print("ignoring unknown file extension [{}]".format(file_extension))
                break;
            file_probe = ffmpeg.probe(file_source_path)
            file_probe_duration_h = float(file_probe["format"]["duration"]) / 60 ** 2 \
                if ("format" in file_probe and "duration" in file_probe["format"]) else -1
            file_probe_size_gb = int(file_probe["format"]["size"]) / 10 ** 9 \
                if ("format" in file_probe and "size" in file_probe["format"]) else -1
            file_probe_filtered = [
                {"file_name": os.path.basename(file_probe["format"]["filename"]) \
                    if ("format" in file_probe and "filename" in file_probe["format"]) else ""},
                {"file_path": file_probe["format"]["filename"] \
                    if ("format" in file_probe and "filename" in file_probe["format"]) else ""},
                {"library_scope": file_library_scope},
                {"library_type": file_library_type},
                {"container_format": file_probe["format"]["format_name"].lower() \
                    if ("format" in file_probe and "format_name" in file_probe["format"]) else ""},
                {"duration_h": round(file_probe_duration_h, 2 if file_probe_duration_h > 1 else 4)},
                {"size_gb": round(file_probe_size_gb, 2 if file_probe_duration_h > 1 else 4)},
                {"bit_rate_kbps": round(int(file_probe["format"]["bit_rate"]) / 10 ** 3) \
                    if ("format" in file_probe and "bit_rate" in file_probe["format"]) else -1},
            ]
            file_probe_streams_filtered = {
                "video": [],
                "audio": [],
                "subtitle": [],
                "other": [],
            }
            for file_probe_stream_type in file_probe_streams_filtered:
                file_probe_filtered.append({
                    file_probe_stream_type: file_probe_streams_filtered[file_probe_stream_type]
                })
            if "streams" in file_probe:
                for file_probe_stream in file_probe["streams"]:
                    file_probe_stream_filtered = []
                    file_probe_stream_type = file_probe_stream["codec_type"].lower() \
                        if "codec_type" in file_probe_stream else ""
                    if file_probe_stream_type not in file_probe_streams_filtered:
                        file_probe_stream_type = "other"
                    file_probe_streams_filtered[file_probe_stream_type].append({
                        file_probe_stream["index"]: file_probe_stream_filtered
                    })
                    file_probe_stream_filtered.append({"codec_type": file_probe_stream["codec_type"].lower() \
                        if "codec_type" in file_probe_stream else ""})
                    if file_probe_stream_type == "video":
                        file_probe_stream_video_codec = file_probe_stream["codec_name"].upper() \
                            if "codec_name" in file_probe_stream else ""
                        if "H264" in file_probe_stream_video_codec or "AVC" in file_probe_stream_video_codec:
                            file_probe_stream_video_codec = "AVC (H264)"
                        if "H265" in file_probe_stream_video_codec or "HEVC" in file_probe_stream_video_codec:
                            file_probe_stream_video_codec = "HEVC (H265)"
                        file_probe_stream_filtered.append({"codec_name": file_probe_stream_video_codec})
                        file_probe_stream_video_field_order = ""
                        if "field_order" in file_probe_stream:
                            if file_probe_stream["field_order"] == "progressive":
                                file_probe_stream_video_field_order = "p"
                            elif file_probe_stream["field_order"] == "interlaced":
                                file_probe_stream_video_field_order = "i"
                        file_probe_stream_video_resolution = ""
                        file_probe_stream_video_width = int(file_probe_stream["width"]) \
                            if "width" in file_probe_stream else -1
                        file_probe_stream_video_height = int(file_probe_stream["height"]) \
                            if "height" in file_probe_stream else -1
                        if file_probe_stream_video_width <= 640:
                            file_probe_stream_video_resolution = "nHD 360" + file_probe_stream_video_field_order
                        elif file_probe_stream_video_width <= 960:
                            file_probe_stream_video_resolution = "qHD 540" + file_probe_stream_video_field_order
                        elif file_probe_stream_video_width <= 1280:
                            file_probe_stream_video_resolution = "HD 720" + file_probe_stream_video_field_order
                        elif file_probe_stream_video_width <= 1600:
                            file_probe_stream_video_resolution = "HD+ 900" + file_probe_stream_video_field_order
                        elif file_probe_stream_video_width <= 1920:
                            file_probe_stream_video_resolution = "FHD 1080" + file_probe_stream_video_field_order
                        elif file_probe_stream_video_width <= 2560:
                            file_probe_stream_video_resolution = "QHD 1440" + file_probe_stream_video_field_order
                        elif file_probe_stream_video_width <= 3200:
                            file_probe_stream_video_resolution = "QHD+ 1800" + file_probe_stream_video_field_order
                        elif file_probe_stream_video_width <= 3840:
                            file_probe_stream_video_resolution = "UHD 2160" + file_probe_stream_video_field_order
                        elif file_probe_stream_video_width <= 5120:
                            file_probe_stream_video_resolution = "UHD 2880" + file_probe_stream_video_field_order
                        elif file_probe_stream_video_width <= 7680:
                            file_probe_stream_video_resolution = "UHD 4320" + file_probe_stream_video_field_order
                        elif file_probe_stream_video_width <= 15360:
                            file_probe_stream_video_resolution = "UHD 8640" + file_probe_stream_video_field_order
                        file_probe_stream_filtered.append({"resolution": file_probe_stream_video_resolution})
                        file_probe_stream_filtered.append({"width": file_probe_stream_video_width})
                        file_probe_stream_filtered.append({"height": file_probe_stream_video_height})
                    elif file_probe_stream_type == "audio":
                        file_probe_stream_filtered.append({"codec_name": file_probe_stream["codec_name"].upper() \
                            if "codec_name" in file_probe_stream else ""})
                        file_probe_stream_filtered.append({"language": file_probe_stream["tags"]["language"].lower() \
                            if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"]) else ""})
                        file_probe_stream_filtered.append({"channels": file_probe_stream["channels"]})
                    elif file_probe_stream_type == "subtitle":
                        file_probe_stream_filtered.append({"codec_name": file_probe_stream["codec_name"].upper() \
                            if "codec_name" in file_probe_stream else ""})
                        file_probe_stream_filtered.append({"language": file_probe_stream["tags"]["language"].lower() \
                            if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"]) else ""})
                with open(file_metadata_path, 'w') as file_metadata:
                    yaml.dump(file_probe_filtered, file_metadata, width=float("inf"))

                file_probe_filtered = {}
                with open(file_metadata_path, 'r') as file_metadata:
                    def unwrap_list_dicts(list_dicts):
                        if isinstance(list_dicts, list):
                            list_dicts_unwrapped = OrderedDict()
                            for list_dict in list_dicts:
                                list_dicts_unwrapped[next(iter(list_dict))] = unwrap_list_dicts(next(iter(list_dict.values())))
                            return list_dicts_unwrapped
                        return list_dicts

                    file_probe_filtered = unwrap_list_dicts(yaml.safe_load(file_metadata))

            if verbose:
                print("wrote metadata file cache")
            files_analysed += 1
    print("{}done".format("Analysing {} ".format(file_path_root) if verbose else ""))
    return files_analysed


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--verbose", default=False, action="store_true")
    argument_parser.add_argument("--refresh", default=False, action="store_true")
    argument_parser.add_argument("media_dir")
    arguments = argument_parser.parse_args()
    sys.exit(2 if _analyse(
        Path(arguments.media_dir).absolute().as_posix(),
        arguments.verbose,
        arguments.refresh,
    ) < 0 else 0)
