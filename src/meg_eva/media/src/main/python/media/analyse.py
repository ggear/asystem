import argparse
import os
import re
import sys
from collections import OrderedDict
from collections.abc import MutableMapping
from pathlib import Path

import ffmpeg
import polars as pl
import yaml
from ffmpeg._run import Error
from gspread_pandas import Spread

# build test data with dummy file
# Analyse library on per share basis, all to do local shares only deltas, deploy to do refresh and do all
# build an item metadata yaml file, pyyaml and ffmpeg-python
# build an item transcode script if necessary, write out transcode metadata file from logs (fps, time, host, command) - mobile version as well?
# build an item replace script if necessary
# build a global xlsx, update but allow manual editing, direct play possible, target quality, required to convert, versions ready to replace
# build a global transcode script, ordered by priority, script takes in number of items to process
# build a global replace script, dry run showing which items, execute actually doing the work

TARGET_SIZE_MIN_GB = 2
TARGET_SIZE_MID_GB = 6
TARGET_SIZE_MAX_GB = 12
TARGET_SIZE_DELTA = 1 / 3

TARGET_BITRATE_VIDEO_MIN_KBPS = 4000
TARGET_BITRATE_VIDEO_MID_KBPS = 8000
TARGET_BITRATE_VIDEO_MAX_KBPS = 14000

BASH_SIGTERM_HANDLER = "sigterm_handler() {{\n{}  exit 1\n}}\n" \
                       "trap 'trap \" \" SIGINT SIGTERM SIGHUP; kill 0; wait; sigterm_handler' SIGINT SIGTERM SIGHUP\n\n"
BASH_ECHO_HEADER = "echo \"#######################################################################################\"\n"


def _analyse(file_path_root, sheet_guid, verbose=False, refresh=False, clean=False):
    if not os.path.isdir(file_path_root):
        print("Error: path [{}] does not exist".format(file_path_root))
        return -1
    metadata_spread = Spread("https://docs.google.com/spreadsheets/d/" + sheet_guid, sheet="Data")
    if clean:
        print("Cleaning {} ... ".format(file_path_root), end=("\n" if verbose else ""), flush=True)
        metadata_spread.freeze(0, 0, sheet="Data")
        metadata_spread.clear_sheet(1, 2, sheet="Data")
        print("{}done".format("Cleaning {} ".format(file_path_root) if verbose else ""))
        return 0
    file_path_media = os.path.join(file_path_root, "media")
    if not os.path.isdir(file_path_media):
        print("Error: path [{}] does not exist".format(file_path_media))
        return -2
    file_path_scripts = os.path.join(file_path_root, "tmp", "scripts")
    if not os.path.isdir(file_path_scripts):
        os.makedirs(file_path_scripts, exist_ok=True)
        _set_permissions(file_path_scripts, 0o750)
    files_analysed = 0
    metadata_list = []
    print("Analysing {} ... ".format(file_path_root), end=("\n" if verbose else ""), flush=True)
    for file_dir_path, _, file_names in os.walk(file_path_media):
        for file_name in file_names:
            file_metadata_written = False
            file_path = os.path.join(file_dir_path, file_name)
            file_path_media_parent = os.path.dirname(file_path_media)
            file_relative_dir = "." + file_dir_path.replace(file_path_media, "")
            file_relative_dir_tokens = file_relative_dir.split(os.sep)
            file_name_sans_extension = os.path.splitext(file_name)[0]
            file_extension = os.path.splitext(file_name)[1].replace(".", "")
            file_metadata_path = os.path.join(file_dir_path, "._metadata_{}.yaml".format(file_name_sans_extension))
            file_media_scope = file_relative_dir_tokens[1] \
                if len(file_relative_dir_tokens) > 1 else ""
            file_media_type = file_relative_dir_tokens[2] \
                if len(file_relative_dir_tokens) > 2 else ""
            if file_extension in {"yaml", "sh", "srt", "jpg", "jpeg", "log"}:
                continue;
            if verbose:
                print("{} ... ".format(os.path.join(file_relative_dir, file_name)), end='', flush=True)
            if file_media_type not in {"movies", "series"}:
                if file_media_type not in {"audio"}:
                    message = "skipping file due to unknown library type [{}]".format(file_media_type)
                    if verbose:
                        print(message)
                    else:
                        print("{} [{}]".format(message, file_path))
                        print("Analysing {} ... ".format(file_path_root), end="", flush=True)
                continue;
            if file_extension not in {"avi", "m2ts", "mkv", "mov", "mp4", "wmv"}:
                message = "skipping file due to unknown file extension [{}]".format(file_extension)
                if verbose:
                    print(message)
                else:
                    print("{} [{}]".format(message, file_path))
                    print("Analysing {} ... ".format(file_path_root), end="", flush=True)
                continue;
            file_base_tokens = 5 if (
                    file_media_type == "series" and
                    len(file_relative_dir_tokens) > 4 and
                    re.search("^Season [1-9]+[0-9]*", file_relative_dir_tokens[4]) is not None
            ) else 4
            file_version_dir = os.sep.join(file_relative_dir_tokens[file_base_tokens:]) \
                if len(file_relative_dir_tokens) > file_base_tokens else "."
            file_base_dir = os.sep.join(file_relative_dir_tokens[3:]).replace("/" + file_version_dir, "") \
                if len(file_relative_dir_tokens) > 3 else "."
            file_stem = file_base_dir.split("/")[0]
            file_version_qualifier = ""
            if file_media_type == "series":
                file_version_qualifier_match = re.search(
                    ".*([sS][0-9]?[0-9]+[eE][0-9]?[-]*[0-9]+.*)\..*", file_name)
                if file_version_qualifier_match is not None:
                    file_version_qualifier = file_version_qualifier_match.groups()[0]
                else:
                    file_version_qualifier = file_name_sans_extension
                file_stem = "{}_{}".format(
                    file_stem.title().replace(" ", "-"),
                    file_version_qualifier.lower()
                )
            file_version_qualifier = file_version_qualifier.lower().removesuffix("___transcode")
            if refresh or not os.path.isfile(file_metadata_path):
                file_defaults_dict = {
                    "target_quality": "Mid",
                    "target_lang": "eng",
                    "native_lang": "eng",
                }
                file_defaults_paths = []
                file_defaults_dir = os.path.join(file_path_media, file_media_scope, file_media_type, file_base_dir)
                while file_defaults_dir != file_path_media_parent:
                    file_defaults_path = os.path.join(file_defaults_dir, "._defaults.yaml")
                    if os.path.isfile(file_defaults_path):
                        file_defaults_paths.append(file_defaults_path)
                    file_defaults_dir = os.path.dirname(file_defaults_dir)
                for file_defaults_path in reversed(file_defaults_paths):
                    if os.path.isfile(file_defaults_path):
                        with open(file_defaults_path, 'r') as file_defaults:
                            try:
                                file_defaults_dict.update(_unwrap_lists(yaml.safe_load(file_defaults)))
                            except Exception as e:
                                message = "skipping file due to defaults metadata cache [{}] load error" \
                                    .format(file_defaults_path)
                                if verbose:
                                    print(message)
                                else:
                                    print("{} [{}]".format(message, file_path))
                                    print("Analysing {} ... ".format(file_path_root), end="", flush=True)
                                continue
                if "target_quality" in file_defaults_dict:
                    file_target_quality = file_defaults_dict["target_quality"].title()
                if "native_lang" in file_defaults_dict:
                    file_native_lang = file_defaults_dict["native_lang"].lower()
                if "target_lang" in file_defaults_dict:
                    file_target_lang = file_defaults_dict["target_lang"].lower()
                try:
                    file_probe = ffmpeg.probe(file_path)
                except Error as error:
                    file_probe = {}
                file_probe_bitrate = round(int(file_probe["format"]["bit_rate"]) / 10 ** 3) \
                    if ("format" in file_probe and "bit_rate" in file_probe["format"]) else -1
                file_probe_duration = float(file_probe["format"]["duration"]) / 60 ** 2 \
                    if ("format" in file_probe and "duration" in file_probe["format"]) else -1
                file_probe_size = (int(file_probe["format"]["size"]) \
                                       if ("format" in file_probe and "size" in file_probe["format"]) \
                                       else os.path.getsize(
                    file_path)) / 10 ** 9
                file_probe_streams_filtered = {
                    "video": [],
                    "audio": [],
                    "subtitle": [],
                    "other": [],
                }
                if "streams" in file_probe:
                    for file_probe_stream in file_probe["streams"]:
                        file_probe_stream_filtered = OrderedDict()
                        file_probe_stream_type = file_probe_stream["codec_type"].lower() \
                            if "codec_type" in file_probe_stream else ""
                        if file_probe_stream_type not in file_probe_streams_filtered:
                            file_probe_stream_type = "other"
                        file_probe_streams_filtered[file_probe_stream_type].append(file_probe_stream_filtered)
                        file_probe_stream_filtered["index"] = str(file_probe_stream["index"]) \
                            if "index" in file_probe_stream else ""
                        if file_probe_stream_type == "video":
                            file_probe_stream_video_codec = file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""
                            if "H264" in file_probe_stream_video_codec or "AVC" in file_probe_stream_video_codec:
                                file_probe_stream_video_codec = "AVC"
                            if "H265" in file_probe_stream_video_codec or "HEVC" in file_probe_stream_video_codec:
                                file_probe_stream_video_codec = "HEVC"
                            file_probe_stream_filtered["codec"] = file_probe_stream_video_codec
                            file_probe_stream_video_field_order = "i"
                            if "field_order" in file_probe_stream:
                                if file_probe_stream["field_order"] == "progressive":
                                    file_probe_stream_video_field_order = "p"
                            file_probe_stream_video_label = ""
                            file_probe_stream_video_res = ""
                            file_probe_stream_video_res_min = ""
                            file_probe_stream_video_res_mid = ""
                            file_probe_stream_video_res_max = ""
                            file_probe_stream_video_width = int(file_probe_stream["width"]) \
                                if "width" in file_probe_stream else -1
                            file_probe_stream_video_height = int(file_probe_stream["height"]) \
                                if "height" in file_probe_stream else -1
                            if file_probe_stream_video_width > 0:
                                if file_probe_stream_video_width <= 640:
                                    file_probe_stream_video_label = "nHD"
                                    file_probe_stream_video_res = "360" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "720p"
                                    file_probe_stream_video_res_mid = "720p"
                                    file_probe_stream_video_res_max = "720p"
                                elif file_probe_stream_video_width <= 960:
                                    file_probe_stream_video_label = "qHD"
                                    file_probe_stream_video_res = "540" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "720p"
                                    file_probe_stream_video_res_mid = "720p"
                                    file_probe_stream_video_res_max = "720p"
                                elif file_probe_stream_video_width <= 1280:
                                    file_probe_stream_video_label = "HD"
                                    file_probe_stream_video_res = "720" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "720p"
                                    file_probe_stream_video_res_mid = "720p"
                                    file_probe_stream_video_res_max = "720p"
                                elif file_probe_stream_video_width <= 1600:
                                    file_probe_stream_video_label = "HD+"
                                    file_probe_stream_video_res = "900" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "720p"
                                    file_probe_stream_video_res_mid = "720p"
                                    file_probe_stream_video_res_max = "720p"
                                elif file_probe_stream_video_width <= 1920:
                                    file_probe_stream_video_label = "FHD"
                                    file_probe_stream_video_res = "1080" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "1080p"
                                    file_probe_stream_video_res_mid = "1080p"
                                    file_probe_stream_video_res_max = "1080p"
                                elif file_probe_stream_video_width <= 2560:
                                    file_probe_stream_video_label = "QHD"
                                    file_probe_stream_video_res = "1440" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "1080p"
                                    file_probe_stream_video_res_mid = "1080p"
                                    file_probe_stream_video_res_max = "1080p"
                                elif file_probe_stream_video_width <= 3200:
                                    file_probe_stream_video_label = "QHD+"
                                    file_probe_stream_video_res = "1800" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "1080p"
                                    file_probe_stream_video_res_mid = "1080p"
                                    file_probe_stream_video_res_max = "1080p"
                                elif file_probe_stream_video_width <= 3840:
                                    file_probe_stream_video_label = "UHD"
                                    file_probe_stream_video_res = "2160" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "1080p"
                                    file_probe_stream_video_res_mid = "1080p"
                                    file_probe_stream_video_res_max = "2160p"
                                elif file_probe_stream_video_width <= 5120:
                                    file_probe_stream_video_label = "UHD"
                                    file_probe_stream_video_res = "2880" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "1080p"
                                    file_probe_stream_video_res_mid = "1080p"
                                    file_probe_stream_video_res_max = "2160p"
                                elif file_probe_stream_video_width <= 7680:
                                    file_probe_stream_video_label = "UHD"
                                    file_probe_stream_video_res = "4320" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "1080p"
                                    file_probe_stream_video_res_mid = "1080p"
                                    file_probe_stream_video_res_max = "2160p"
                                elif file_probe_stream_video_width <= 15360:
                                    file_probe_stream_video_label = "UHD"
                                    file_probe_stream_video_res = "8640" + file_probe_stream_video_field_order
                                    file_probe_stream_video_res_min = "1080p"
                                    file_probe_stream_video_res_mid = "1080p"
                                    file_probe_stream_video_res_max = "2160p"
                            file_probe_stream_filtered["label"] = file_probe_stream_video_label
                            file_probe_stream_filtered["res"] = file_probe_stream_video_res
                            file_probe_stream_filtered["res_min"] = file_probe_stream_video_res_min
                            file_probe_stream_filtered["res_mid"] = file_probe_stream_video_res_mid
                            file_probe_stream_filtered["res_max"] = file_probe_stream_video_res_max
                            file_probe_stream_filtered["width"] = str(file_probe_stream_video_width) \
                                if file_probe_stream_video_width > 0 else ""
                            file_probe_stream_filtered["height"] = str(file_probe_stream_video_height) \
                                if file_probe_stream_video_height > 0 else ""
                            file_stream_bitrate = round(int(file_probe_stream["bit_rate"]) / 10 ** 3) \
                                if "bit_rate" in file_probe_stream else -1
                            file_probe_stream_filtered["bitrate__Kbps"] = str(file_stream_bitrate) \
                                if file_stream_bitrate > 0 else ""
                            file_probe_stream_filtered["bitrate_est__Kbps"] = file_stream_bitrate \
                                if file_stream_bitrate > 0 else -1
                            file_probe_stream_filtered["bitrate_min__Kbps"] = -1
                            file_probe_stream_filtered["bitrate_mid__Kbps"] = -1
                            file_probe_stream_filtered["bitrate_max__Kbps"] = -1
                        elif file_probe_stream_type == "audio":
                            file_stream_codec = file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""
                            file_probe_stream_filtered["codec"] = file_stream_codec
                            file_probe_stream_filtered["lang"] = file_probe_stream["tags"]["language"].lower() \
                                if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"] \
                                    and file_probe_stream["tags"]["language"].lower() != "und") else file_target_lang
                            file_stream_channels = int(file_probe_stream["channels"]) \
                                if "channels" in file_probe_stream else 2
                            file_probe_stream_filtered["channels"] = str(file_stream_channels)
                            file_probe_stream_filtered["bitrate__Kbps"] = \
                                str(round(int(file_probe_stream["bit_rate"]) / 10 ** 3)) \
                                    if "bit_rate" in file_probe_stream else ""
                        elif file_probe_stream_type == "subtitle":
                            file_probe_stream_filtered["codec"] = file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""
                            file_probe_stream_filtered["lang"] = file_probe_stream["tags"]["language"].lower() \
                                if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"] \
                                    and file_probe_stream["tags"]["language"].lower() != "und") else file_target_lang
                            file_probe_stream_filtered["format"] = "Picture" \
                                if ("tags" in file_probe_stream and "width" in file_probe_stream["tags"]) else "Text"
                file_probe_streams_filtered["video"].sort(key=lambda stream: int(stream["width"]), reverse=True)
                for file_stream_video_index, file_stream_video in enumerate(file_probe_streams_filtered["video"]):
                    if file_stream_video_index == 0:
                        file_stream_video_bitrate = file_stream_video["bitrate_est__Kbps"]
                        if file_stream_video_bitrate < 0:
                            if file_probe_bitrate > 0:
                                file_stream_audio_bitrate = 0
                                for file_stream_audio in file_probe_streams_filtered["audio"]:
                                    file_stream_audio_bitrate += int(file_stream_audio["bitrate__Kbps"]) \
                                        if file_stream_audio["bitrate__Kbps"] != "" else 192
                                file_stream_video_bitrate = file_probe_bitrate - file_stream_audio_bitrate \
                                    if file_probe_bitrate > file_stream_audio_bitrate else 0
                        if file_stream_video_bitrate < 0:
                            file_stream_video["bitrate_est__Kbps"] = " "
                            file_stream_video["bitrate_min__Kbps"] = " "
                            file_stream_video["bitrate_mid__Kbps"] = " "
                            file_stream_video["bitrate_max__Kbps"] = " "
                        else:
                            file_stream_video["bitrate_est__Kbps"] = \
                                str(file_stream_video_bitrate)
                            file_stream_video["bitrate_min__Kbps"] = \
                                str(min(file_stream_video_bitrate, TARGET_BITRATE_VIDEO_MIN_KBPS))
                            file_stream_video["bitrate_mid__Kbps"] = \
                                str(min(file_stream_video_bitrate, TARGET_BITRATE_VIDEO_MID_KBPS))
                            file_stream_video["bitrate_max__Kbps"] = \
                                str(min(file_stream_video_bitrate, TARGET_BITRATE_VIDEO_MAX_KBPS))
                    else:
                        del file_stream_video["res_min"]
                        del file_stream_video["res_mid"]
                        del file_stream_video["res_max"]
                        del file_stream_video["bitrate_est__Kbps"]
                        del file_stream_video["bitrate_min__Kbps"]
                        del file_stream_video["bitrate_mid__Kbps"]
                        del file_stream_video["bitrate_max__Kbps"]
                file_probe_streams_filtered_audios = []
                file_probe_streams_filtered_audios_supplementary = []
                for file_probe_streams_filtered_audio in file_probe_streams_filtered["audio"]:
                    if file_probe_streams_filtered_audio["codec"] in {"AAC", "AC3", "EAC3"} and \
                            file_probe_streams_filtered_audio["lang"] == file_target_lang:
                        file_probe_streams_filtered_audios.append(file_probe_streams_filtered_audio)
                    else:
                        file_probe_streams_filtered_audios_supplementary.append(file_probe_streams_filtered_audio)
                if len(file_probe_streams_filtered_audios) == 0:
                    file_probe_streams_filtered_audios_supplementary = []
                    for file_probe_streams_filtered_audio in file_probe_streams_filtered["audio"]:
                        if file_probe_streams_filtered_audio["lang"] == file_target_lang:
                            file_probe_streams_filtered_audios.append(file_probe_streams_filtered_audio)
                        else:
                            file_probe_streams_filtered_audios_supplementary.append(file_probe_streams_filtered_audio)
                file_probe_streams_filtered_audios.sort(key=lambda stream: int(stream["channels"]), reverse=True)
                file_probe_streams_filtered_audios_supplementary.sort(key=lambda stream: int(stream["channels"]), reverse=True)
                file_probe_streams_filtered_audios.extend(file_probe_streams_filtered_audios_supplementary)
                file_probe_streams_filtered["audio"] = file_probe_streams_filtered_audios
                file_probe_streams_filtered_subtitles = []
                file_probe_streams_filtered_subtitles_supplementary = []
                for file_probe_streams_filtered_subtitle in file_probe_streams_filtered["subtitle"]:
                    if file_probe_streams_filtered_subtitle["format"] == "Text" and \
                            file_probe_streams_filtered_subtitle["lang"] == "eng":
                        file_probe_streams_filtered_subtitles.append(file_probe_streams_filtered_subtitle)
                    else:
                        file_probe_streams_filtered_subtitles_supplementary.append(file_probe_streams_filtered_subtitle)
                file_probe_streams_filtered_subtitles.sort(key=lambda stream: stream["index"], reverse=True)
                file_probe_streams_filtered_subtitles_supplementary.sort(key=lambda stream: stream["index"], reverse=True)
                file_probe_streams_filtered_subtitles.extend(file_probe_streams_filtered_subtitles_supplementary)
                file_probe_streams_filtered["subtitle"] = file_probe_streams_filtered_subtitles
                file_probe_filtered = [
                    {"file_name": file_name},
                    {"target_quality": file_target_quality},
                    {"target_lang": file_target_lang},
                    {"native_lang": file_native_lang},
                    {"media_directory": file_path_media},
                    {"media_scope": file_media_scope},
                    {"media_type": file_media_type},
                    {"base_directory": file_base_dir},
                    {"version_directory": file_version_dir},
                    {"version_qualifier": file_version_qualifier},
                    {"file_directory": " '{}' ".format(file_dir_path)},
                    {"file_stem": " '{}' ".format(file_stem)},
                    {"file_extension": file_extension},
                    {"container_format": file_probe["format"]["format_name"].lower() \
                        if ("format" in file_probe and "format_name" in file_probe["format"]) else ""},
                    {"duration__hours": str(round(file_probe_duration, 2 if file_probe_duration > 1 else 4)) \
                        if file_probe_duration > 0 else ""},
                    {"file_size__GB": str(round(file_probe_size, 2 if file_probe_size > 1 else 4))},
                    {"bitrate__Kbps": str(file_probe_bitrate) if file_probe_bitrate > 0 else ""},
                    {"stream_count": str(sum(map(len, file_probe_streams_filtered.values())))},
                ]
                for file_probe_stream_type in file_probe_streams_filtered:
                    file_probe_filtered.append({
                        "{}_count".format(file_probe_stream_type):
                            str(len(file_probe_streams_filtered[file_probe_stream_type]))
                    })
                    file_probe_streams_indexed = []
                    file_probe_filtered.append({file_probe_stream_type: file_probe_streams_indexed})
                    file_probe_stream_typed_count = 1
                    for file_probe_stream_typed in file_probe_streams_filtered[file_probe_stream_type]:
                        file_probe_stream_wrapped = []
                        file_probe_streams_indexed.append({
                            str(file_probe_stream_typed_count): file_probe_stream_wrapped
                        })
                        for file_probe_stream_type_key in file_probe_stream_typed:
                            file_probe_stream_wrapped.append({
                                file_probe_stream_type_key: file_probe_stream_typed[file_probe_stream_type_key]
                            })
                        file_probe_stream_typed_count += 1
                with open(file_metadata_path, 'w') as file_metadata:
                    yaml.dump(file_probe_filtered, file_metadata, width=float("inf"))
                _set_permissions(file_metadata_path)
                file_metadata_written = True
            with open(file_metadata_path, 'r') as file_metadata:
                try:
                    metadata_list.append(_flatten_dicts(_unwrap_lists(yaml.safe_load(file_metadata))))
                    if verbose:
                        if file_metadata_written:
                            print("wrote and loaded metadata file cache")
                        else:
                            print("loaded metadata file cache")
                except Exception:
                    message = "skipping file due to metadata cache load error"
                    if verbose:
                        print(message)
                    else:
                        print("{} [{}]".format(message, file_path))
                        print("Analysing {} ... ".format(file_path_root), end="", flush=True)
                    continue
            files_analysed += 1

    def _format_columns(metadata_pl):
        metadata_columns = []
        metadata_columns_streams = ("video", "audio", "subtitle", "other")
        for metadata_column in metadata_pl.columns:
            if not metadata_column.lower().startswith(metadata_columns_streams):
                metadata_columns.append(metadata_column)
        for metadata_column_stream in metadata_columns_streams:
            for metadata_column in metadata_pl.columns:
                if metadata_column.lower().startswith(metadata_column_stream):
                    metadata_columns.append(metadata_column)
        return metadata_pl.select(metadata_columns) \
            .rename(lambda column: \
                        ((column.split("__")[0].replace("_", " ").title() + " (" + column.split("__")[1] + ")") \
                             if len(column.split("__")) == 2 else column.replace("_", " ").title()) \
                            if "_" in column else column)

    metadata_enriched_list = []
    for metadata in metadata_list:
        def _add(key, value):
            metadata.update({key: value})
            metadata.move_to_end(key, last=False)

        _add("version_count", "")
        _add("action_index", "")
        _add("metadata_state", "")
        _add("plex_subtitle", "")
        _add("plex_audio", "")
        _add("plex_video", "")
        _add("file_size", "")
        _add("file_state", "")
        _add("file_action", "")
        metadata.move_to_end("file_name", last=False)
        metadata_enriched_list.append(dict(metadata))
    metadata_cache_pl = _format_columns(pl.DataFrame(metadata_enriched_list))
    metadata_original_list = metadata_spread._fix_merge_values(metadata_spread.sheet.get_all_values())
    if len(metadata_original_list) > 0:
        metadata_original_pl = _format_columns(pl.DataFrame(
            schema=metadata_original_list[0],
            data=metadata_original_list[1:],
            orient="row"
        ))
    else:
        metadata_original_pl = pl.DataFrame()
    metadata_cache_media_dirs = []
    metadata_cache_pl = metadata_cache_pl if metadata_cache_pl.shape[0] > 0 else pl.DataFrame()
    metadata_original_pl = metadata_original_pl if metadata_original_pl.shape[0] > 0 else pl.DataFrame()
    if len(metadata_cache_pl) > 0:
        metadata_cache_media_dirs = [media_directory[0] for media_directory in \
                                     metadata_cache_pl.select("Media Directory").unique().rows()]
        if len(metadata_original_pl) > 0:
            metadata_original_pl = metadata_original_pl.filter(
                ~pl.col("Media Directory").is_in(metadata_cache_media_dirs))
            metadata_updated_pl = _format_columns(
                pl.concat([metadata_original_pl, metadata_cache_pl], how="diagonal")
            )
        else:
            metadata_updated_pl = metadata_cache_pl
    else:
        metadata_updated_pl = pl.DataFrame()
    if len(metadata_updated_pl) > 0:
        metadata_updated_pl = metadata_updated_pl.with_columns(
            (
                pl.when(
                    (pl.col("Container Format") == "")
                ).then(pl.lit("Corrupt"))
                .when(
                    (pl.col("Base Directory") == ".")
                ).then(pl.lit("Corrupt"))
                .when(
                    (pl.col("Video Count") == "0") |
                    (pl.col("Audio Count") == "0")
                ).then(pl.lit("Incomplete"))
                .when(
                    (pl.col("Target Lang") == "eng") &
                    (pl.col("Audio 1 Lang") != "eng")
                ).then(pl.lit("Incomplete"))
                .when(
                    (pl.col("Target Lang") != "eng") &
                    ((pl.col("Subtitle 1 Lang").is_null()) |
                     (pl.col("Subtitle 1 Lang") != "eng")
                     )
                ).then(pl.lit("Incomplete"))
                .otherwise(pl.lit("Complete"))
            ).alias("File State"))
        metadata_updated_pl = metadata_updated_pl.with_columns(
            (
                pl.when(
                    ((pl.col("Target Quality") == "Max") &
                     (pl.col("File Size (GB)").cast(pl.Float32) > ((1 + TARGET_SIZE_DELTA) * TARGET_SIZE_MAX_GB))
                     ) |
                    ((pl.col("Target Quality") == "Mid") &
                     (pl.col("File Size (GB)").cast(pl.Float32) > ((1 + TARGET_SIZE_DELTA) * TARGET_SIZE_MID_GB))
                     ) |
                    ((pl.col("Target Quality") == "Min") &
                     (pl.col("File Size (GB)").cast(pl.Float32) > ((1 + TARGET_SIZE_DELTA) * TARGET_SIZE_MIN_GB))
                     )
                ).then(pl.lit("Large"))
                .when(
                    ((pl.col("Target Quality") == "Max") &
                     (pl.col("File Size (GB)").cast(pl.Float32) < (TARGET_SIZE_DELTA * TARGET_SIZE_MAX_GB))
                     ) |
                    ((pl.col("Target Quality") == "Mid") &
                     (pl.col("File Size (GB)").cast(pl.Float32) < (TARGET_SIZE_DELTA * TARGET_SIZE_MID_GB))
                     ) |
                    ((pl.col("Target Quality") == "Min") &
                     (pl.col("File Size (GB)").cast(pl.Float32) < (TARGET_SIZE_DELTA * TARGET_SIZE_MIN_GB))
                     )
                ).then(pl.lit("Small"))
                .otherwise(pl.lit("Right"))
            ).alias("File Size"))
        metadata_updated_pl = metadata_updated_pl.with_columns(
            (
                pl.when(
                    (pl.col("File State") == "Corrupt")
                ).then(None)
                .when(
                    ((pl.col("File Extension").str.to_lowercase() == "avi") & (
                            (pl.col("Video 1 Codec") == "AVC") |
                            (pl.col("Video 1 Codec") == "MPEG2VIDEO") |
                            (pl.col("Video 1 Codec") == "MJPEG") |
                            (pl.col("Video 1 Codec") == "MPEG4")
                    )) |
                    ((pl.col("File Extension").str.to_lowercase() == "m2ts") & (
                            (pl.col("Video 1 Codec") == "AVC") |
                            (pl.col("Video 1 Codec") == "HEVC") |
                            (pl.col("Video 1 Codec") == "MPEG2VIDEO") |
                            (pl.col("Video 1 Codec") == "MJPEG") |
                            (pl.col("Video 1 Codec") == "MPEG4")
                    )) |
                    ((pl.col("File Extension").str.to_lowercase() == "mkv") & (
                            (pl.col("Video 1 Codec") == "AVC") |
                            (pl.col("Video 1 Codec") == "HEVC") |
                            (pl.col("Video 1 Codec") == "MPEG2VIDEO") |
                            (pl.col("Video 1 Codec") == "MJPEG") |
                            (pl.col("Video 1 Codec") == "MPEG4")
                    )) |
                    ((pl.col("File Extension").str.to_lowercase() == "mov") & (
                            (pl.col("Video 1 Codec") == "AVC") |
                            (pl.col("Video 1 Codec") == "HEVC") |
                            (pl.col("Video 1 Codec") == "MPEG2VIDEO") |
                            (pl.col("Video 1 Codec") == "MJPEG") |
                            (pl.col("Video 1 Codec") == "MPEG4") |
                            (pl.col("Video 1 Codec") == "VC1") |
                            (pl.col("Video 1 Codec") == "VP9")
                    )) |
                    ((pl.col("File Extension").str.to_lowercase() == "mp4") & (
                            (pl.col("Video 1 Codec") == "AVC") |
                            (pl.col("Video 1 Codec") == "HEVC") |
                            (pl.col("Video 1 Codec") == "MPEG2VIDEO") |
                            (pl.col("Video 1 Codec") == "MJPEG") |
                            (pl.col("Video 1 Codec") == "MPEG4")
                    )) |
                    ((pl.col("File Extension").str.to_lowercase() == "wmv") & (
                            (pl.col("Video 1 Codec") == "WMV3") |
                            (pl.col("Video 1 Codec") == "VC1")
                    ))
                ).then(pl.lit("Direct Play"))
                .otherwise(pl.lit("Transcode"))
            ).alias("Plex Video"))
        metadata_updated_pl = metadata_updated_pl.with_columns(
            (
                pl.when(
                    (pl.col("File State") == "Corrupt")
                ).then(None)
                .when(
                    ((pl.col("Target Lang") == pl.col("Audio 1 Lang")) &
                     (((pl.col("File Extension").str.to_lowercase() == "avi") & (
                             (pl.col("Audio 1 Codec") == "AAC") |
                             (pl.col("Audio 1 Codec") == "AC3") |
                             (pl.col("Audio 1 Codec") == "EAC3") |
                             (pl.col("Audio 1 Codec") == "MP3") |
                             (pl.col("Audio 1 Codec") == "PCM")
                     )) |
                      ((pl.col("File Extension").str.to_lowercase() == "m2ts") & (
                              (pl.col("Audio 1 Codec") == "AAC") |
                              (pl.col("Audio 1 Codec") == "AC3") |
                              (pl.col("Audio 1 Codec") == "EAC3") |
                              (pl.col("Audio 1 Codec") == "MP2") |
                              (pl.col("Audio 1 Codec") == "MP3") |
                              (pl.col("Audio 1 Codec") == "PCM")
                      )) |
                      ((pl.col("File Extension").str.to_lowercase() == "mkv") & (
                              (pl.col("Audio 1 Codec") == "AAC") |
                              (pl.col("Audio 1 Codec") == "AC3") |
                              (pl.col("Audio 1 Codec") == "EAC3") |
                              (pl.col("Audio 1 Codec") == "MP3") |
                              (pl.col("Audio 1 Codec") == "PCM")
                      )) |
                      ((pl.col("File Extension").str.to_lowercase() == "mov") & (
                              (pl.col("Audio 1 Codec") == "AAC") |
                              (pl.col("Audio 1 Codec") == "AC3") |
                              (pl.col("Audio 1 Codec") == "EAC3")
                      )) |
                      ((pl.col("File Extension").str.to_lowercase() == "mp4") & (
                              (pl.col("Audio 1 Codec") == "AAC") |
                              (pl.col("Audio 1 Codec") == "AC3") |
                              (pl.col("Audio 1 Codec") == "EAC3") |
                              (pl.col("Audio 1 Codec") == "MP3")
                      )) |
                      ((pl.col("File Extension").str.to_lowercase() == "wmv") & (
                              (pl.col("Audio 1 Codec") == "AC3") |
                              (pl.col("Audio 1 Codec") == "WMAPRO") |
                              (pl.col("Audio 1 Codec") == "WMAV2")
                      ))))
                ).then(pl.lit("Direct Play"))
                .otherwise(pl.lit("Transcode"))
            ).alias("Plex Audio"))
        metadata_updated_pl = metadata_updated_pl.with_columns(
            (
                pl.when(
                    (pl.col("File State") == "Corrupt")
                ).then(None)
                .when(
                    (pl.col("Subtitle Count").cast(pl.Int32) == 0) |
                    (pl.col("Subtitle 1 Format").is_null()) |
                    (pl.col("Subtitle 1 Format") == "") |
                    (pl.col("Subtitle 1 Format") == "Text")
                ).then(pl.lit("Direct Play"))
                .otherwise(pl.lit("Transcode"))
            ).alias("Plex Subtitle"))
        metadata_updated_pl = metadata_updated_pl.with_columns(
            (
                pl.when(
                    (pl.col("File State") == "Corrupt")
                ).then(None)
                .when(
                    (pl.col("Video Count").cast(pl.Int32) > 1)
                ).then(pl.lit("Messy"))
                .when(
                    (pl.col("Audio Count").cast(pl.Int32) > 1)
                ).then(pl.lit("Messy"))
                .when(
                    (pl.col("Subtitle Count").cast(pl.Int32) > 2)
                ).then(pl.lit("Messy"))
                .when(
                    (pl.col("Other Count").cast(pl.Int32) > 0)
                ).then(pl.lit("Messy"))
                .otherwise(pl.lit("Clean"))
            ).alias("Metadata State"))
        metadata_updated_pl = metadata_updated_pl.with_columns(
            pl.concat_str([
                pl.col("Media Directory"),
                pl.col("Media Scope"),
                pl.col("Media Type"),
                pl.col("Base Directory"),
                pl.col("Version Qualifier"),
            ], separator="/",
            ).alias("Base Path")
        ).with_columns(
            (pl.col("Base Path").count().over("Base Path"))
            .alias("Version Count")
        ).drop("Base Path")
        metadata_updated_pl = metadata_updated_pl.with_columns(
            (
                pl.when(
                    (pl.col("Version Count").cast(pl.Int32) > 1)
                ).then(pl.lit("5. Merge"))
                .when(
                    (pl.col("File State") == "Corrupt") |
                    (pl.col("File State") == "Incomplete")
                ).then(pl.lit("1. Download"))
                .when(
                    (pl.col("File Size") == "Small") &
                    (pl.col("Target Quality") != "Min")
                ).then(pl.lit("2. Upscale"))
                .when(
                    (pl.col("Plex Video") == "Transcode") |
                    (pl.col("Plex Audio") == "Transcode") |
                    (pl.col("Plex Subtitle") == "Transcode") |
                    (pl.col("Duration (hours)").is_null()) |
                    (pl.col("Bitrate (Kbps)").is_null())
                ).then(pl.lit("3. Transcode"))
                .when(
                    (pl.col("File Size") == "Large") |
                    (pl.col("Metadata State") == "Messy")
                ).then(pl.lit("4. Reformat"))
                .otherwise(pl.lit("6. Nothing"))
            ).alias("File Action"))
        metadata_updated_pl = metadata_updated_pl.with_columns(
            pl.col("File Size (GB)").cast(pl.Float32).alias("Action Index Sort")
        ).select(
            (pl.all().sort_by("Action Index Sort", descending=True).over("File Action"))
        ).with_columns(
            (pl.col("File Action").str.split(by=".").list.get(0, null_on_oob=True).cast(pl.Int32) * 1000000)
            .alias("Action Index Base")
        ).with_columns(
            (pl.col("File Action").cum_count().over("File Action"))
            .alias("Action Index Count")
        ).with_columns(
            (pl.col("Action Index Base") + pl.col("Action Index Count"))
            .alias("Action Index")
        ).drop(["Action Index Sort", "Action Index Base", "Action Index Count"]).sort("Action Index")
        metadata_updated_pl = metadata_updated_pl.with_columns([
            pl.when(pl.col(pl.Utf8).str.len_bytes() == 0) \
                .then(None).otherwise(pl.col(pl.Utf8)).name.keep()
        ])
        metadata_updated_pl = metadata_updated_pl[[
            column.name for column in metadata_updated_pl \
            if not (column.null_count() == metadata_updated_pl.height)
        ]]

        # TODO: Write out file and global merge scripts
        # TODO: Make a media-transcode/merge scripts to context determine all scripts under path or accross local shares if none - maybe make all other scripts do the same?
        metadata_transcode_pl = metadata_updated_pl.filter(
            pl.col("File Action").str.ends_with("Transcode"),
            pl.col("Version Directory").str.ends_with("."),
            pl.col("Media Directory").is_in(metadata_cache_media_dirs),
        ).with_columns(
            [
                pl.concat_str([
                    pl.col("File Directory").str.strip_prefix(" '").str.strip_suffix("' "),
                ]).alias("File Directory"),
                pl.concat_str([
                    pl.col("File Stem").str.strip_prefix(" '").str.strip_suffix("' "),
                ]).alias("File Stem"),
                (
                    pl.when(
                        (pl.col("Target Quality") == "Max")
                    ).then(
                        pl.concat_str([pl.col("Video 1 Res Max"), pl.lit("="), pl.col("Video 1 Bitrate Max (Kbps)")])
                    ).when(
                        (pl.col("Target Quality") == "Mid")
                    ).then(
                        pl.concat_str([pl.col("Video 1 Res Mid"), pl.lit("="), pl.col("Video 1 Bitrate Mid (Kbps)")])
                    ).otherwise(
                        pl.concat_str([pl.col("Video 1 Res Min"), pl.lit("="), pl.col("Video 1 Bitrate Min (Kbps)")])
                    )
                ).alias("Transcode Target")
            ]
        ).with_columns(
            [
                pl.concat_str([
                    pl.col("File Directory"),
                    pl.lit("/._transcode_"),
                    pl.col("File Stem"),
                ]).alias("Script Directory"),
                pl.concat_str([
                    pl.col("File Stem"),
                    pl.lit("___TRANSCODE"),
                    pl.lit(".mkv"),
                ]).alias("Transcode File Name"),
                pl.when(
                    (pl.col("Video 1 Res Max") == "720p")
                ).then(
                    pl.concat_str([pl.col("Transcode Target"), pl.lit(" --720p")])
                ).otherwise(
                    pl.col("Transcode Target")
                ).alias("Transcode Target")
            ]
        ).with_columns(
            [
                pl.concat_str([
                    pl.col("Script Directory"),
                    pl.lit("/transcode.sh"),
                ]).alias("Script Path"),
            ]
        ).with_columns(
            [
                pl.concat_str([
                    pl.lit("../.."),
                    pl.col("Script Path").str.strip_prefix(file_path_root),
                ]).alias("Script Relative Path"),
                pl.concat_str([
                    pl.lit("# !/bin/bash\n\n"),
                    pl.lit("cd \"$(dirname \"${0}\")\"\n\n"),
                    pl.lit(BASH_SIGTERM_HANDLER.format("  echo 'Killing Transcode!!!!'\n  rm -f *.mkv*\n")),
                    pl.lit("[[ -f '../"), pl.col("Transcode File Name"), pl.lit("' ]] && exit 1\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("echo \"Transcoding '"), pl.col("File Name"), pl.lit("' ... \"\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("rm -rvf *.mkv*\n"),
                    pl.lit("other-transcode '../"), pl.col("File Name"), pl.lit("' \\\n"),
                    pl.lit("  --target "), pl.col("Transcode Target"), pl.lit(" \\\n"),
                    pl.lit("  --hevc\n"),
                    pl.lit("rm -rvf *.mkv.log\n"),
                    pl.lit("mv -v *.mkv '../"), pl.col("Transcode File Name"), pl.lit("'\n"),
                    pl.lit("echo \"\"\n"),
                ]).alias("Script Source"),
            ]
        ).sort("Action Index").select(["Script Path", "Script Relative Path", "Script Directory", "Script Source"])
        transcode_script_global = os.path.join(file_path_scripts, "transcode.sh")
        with open(transcode_script_global, 'w') as transcode_global_file:
            transcode_global_file.write("# !/bin/bash\n\n")
            transcode_global_file.write("cd \"$(dirname \"${0}\")\"\n\n")
            transcode_global_file.write(BASH_SIGTERM_HANDLER.format(""))
            transcode_global_file.write("echo \"\"\n")
            for transcode_script_local in metadata_transcode_pl.rows():
                transcode_global_file.write("'{}'\n".format(transcode_script_local[1]))
                os.makedirs(transcode_script_local[2], exist_ok=True)
                _set_permissions(transcode_script_local[2], 0o750)
                with open(transcode_script_local[0], 'w') as transcode_local_file:
                    transcode_local_file.write(transcode_script_local[3])
                _set_permissions(transcode_script_local[0], 0o750)
        _set_permissions(transcode_script_global, 0o750)
        metadata_updated_pd = metadata_updated_pl.to_pandas()
        if "File Name" in metadata_updated_pd:
            metadata_updated_pd = metadata_updated_pd.set_index("File Name")
        if "Action Index" in metadata_updated_pd:
            metadata_updated_pd = metadata_updated_pd.sort_values("Action Index")
        metadata_spread.freeze(0, 0, sheet="Data")
        metadata_spread.df_to_sheet(metadata_updated_pd, sheet="Data", replace=False, index=True, \
                                    add_filter=True, freeze_index=True, freeze_headers=True)
    print("{}done".format("Analysing {} ".format(file_path_root) if verbose else ""))
    sys.stdout.flush()
    return files_analysed


def _set_permissions(path, mode=0o644):
    os.chmod(path, mode)
    try:
        os.chown(path, 1000, 100)
    except PermissionError:
        pass


def _unwrap_lists(lists):
    if lists is None:
        lists = []
    if isinstance(lists, list):
        dicts = OrderedDict()
        for item in lists:
            dicts[next(iter(item))] = _unwrap_lists(next(iter(item.values())))
        return dicts
    return lists


def _flatten_dicts(dicts, parent_key=''):
    items = []
    if dicts is None:
        dicts = {}
    for key, value in dicts.items():
        new_key = parent_key + '_' + str(key) if parent_key else str(key)
        if isinstance(value, MutableMapping):
            items.extend(_flatten_dicts(value, new_key).items())
        else:
            items.append((new_key, value))
    return OrderedDict(items)


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--verbose", default=False, action="store_true")
    argument_parser.add_argument("--refresh", default=False, action="store_true")
    argument_parser.add_argument("--clean", default=False, action="store_true")
    argument_parser.add_argument("directory")
    argument_parser.add_argument("sheetguid")
    arguments = argument_parser.parse_args()
    sys.exit(2 if _analyse(
        Path(arguments.directory).absolute().as_posix(),
        arguments.sheetguid,
        arguments.verbose,
        arguments.refresh,
        arguments.clean,
    ) < 0 else 0)
