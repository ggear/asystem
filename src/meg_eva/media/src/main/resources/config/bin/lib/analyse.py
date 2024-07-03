"""
WARNING: This file is written by the build process, any manual edits will be lost!
"""

import argparse
import os
import re
import shlex
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

TARGET_SIZE_DELTA = 1 / 3
TARGET_SIZE_HIGH_GB = 12
TARGET_SIZE_MEDIUM_GB = 6
TARGET_SIZE_LOW_GB = 2


def _analyse(file_path_root, sheet_guid, verbose=False, refresh=False, clean=False):
    if not os.path.isdir(file_path_root):
        print("Error: path [{}] does not exist".format(file_path_root))
        return -1
    metadata_spread = Spread("https://docs.google.com/spreadsheets/d/" + sheet_guid, sheet="Data")
    if clean:
        print("Cleaning {} ... ".format(file_path_root), end=("\n" if verbose else ""), flush=True)
        metadata_spread.freeze(0, 0, sheet="Data")
        metadata_spread.clear_sheet(sheet="Data")
        print("{}done".format("Cleaning {} ".format(file_path_root) if verbose else ""))
        return 0
    files_analysed = 0
    metadata_list = []
    print("Analysing {} ... ".format(file_path_root), end=("\n" if verbose else ""), flush=True)
    for file_dir_path, _, file_names in os.walk(file_path_root):
        for file_name in file_names:
            file_metadata_written = False
            file_path = os.path.join(file_dir_path, file_name)
            file_relative_dir = "." + file_dir_path.replace(file_path_root, "")
            file_relative_dir_tokens = file_relative_dir.split(os.sep)
            file_name_sans_extension = os.path.splitext(file_name)[0]
            file_extension = os.path.splitext(file_name)[1].replace(".", "")
            file_metadata_path = os.path.join(file_dir_path, ".{}_metadata.yaml".format(file_name_sans_extension))
            file_media_scope = file_relative_dir_tokens[1] \
                if len(file_relative_dir_tokens) > 1 else ""
            file_media_type = file_relative_dir_tokens[2] \
                if len(file_relative_dir_tokens) > 2 else ""
            if file_extension in {"yaml", "srt", "jpg", "jpeg", "log"}:
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
            file_version_qualifier = ""
            if file_media_type == "series":
                file_version_qualifier_match = re.search(".*[sS][0-9]?[0-9]+([eE][0-9]?[0-9]+.*)\..*", file_name)
                if file_version_qualifier_match is not None:
                    file_version_qualifier = "Episode-{}".format(file_version_qualifier_match.groups()[0])
                else:
                    file_version_qualifier = file_name_sans_extension
            file_base_dir = os.sep.join(file_relative_dir_tokens[3:]).replace("/" + file_version_dir, "") \
                if len(file_relative_dir_tokens) > 3 else "."

            # TODO: Merge all _transcodes!
            #  put down after refresh
            #  make sure there is a default - add to install of media dirs
            #  files ignores at scope/type levels
            #  test that files picked up at all levels
            file_transcode_dir = os.path.join(file_path_root, file_media_scope, file_media_type, file_base_dir)
            file_transcode_path = os.path.join(file_transcode_dir, "._transcode.yaml")
            file_transcode_path_root = file_transcode_path
            while not os.path.isfile(file_transcode_path) and file_transcode_dir != file_path_root:
                file_transcode_dir = os.path.dirname(file_transcode_dir)
                file_transcode_path = os.path.join(file_transcode_dir, "._transcode.yaml")
            file_target_quality = "Medium"
            file_target_language = "eng"
            file_native_language = "eng"
            if os.path.isfile(file_transcode_path):
                with open(file_transcode_path, 'r') as file_transcode:
                    try:
                        metadata_transcode_dict = _unwrap_lists(yaml.safe_load(file_transcode))
                        if "target_quality" in metadata_transcode_dict:
                            file_target_quality = metadata_transcode_dict["target_quality"].title()
                        if "native_language" in metadata_transcode_dict:
                            file_native_language = metadata_transcode_dict["native_language"].lower()
                        if "target_language" in metadata_transcode_dict:
                            file_target_language = metadata_transcode_dict["target_language"].lower()
                    except Exception:
                        message = "skipping file due to transcode metadata cache [{}] load error".format(file_transcode)
                        if verbose:
                            print(message)
                        else:
                            print("{} [{}]".format(message, file_path))
                            print("Analysing {} ... ".format(file_path_root), end="", flush=True)
                        continue
            else:
                file_transcode_path = ""

            if refresh or not os.path.isfile(file_metadata_path):
                try:
                    file_probe = ffmpeg.probe(file_path)
                except Error as error:
                    file_probe = {}
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
                            if file_probe_stream_video_width > 0:
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
                            file_probe_stream_filtered["resolution"] = file_probe_stream_video_resolution
                            file_probe_stream_filtered["width"] = str(file_probe_stream_video_width) \
                                if file_probe_stream_video_width > 0 else ""
                            file_probe_stream_filtered["height"] = str(file_probe_stream_video_height) \
                                if file_probe_stream_video_height > 0 else ""
                        elif file_probe_stream_type == "audio":
                            file_probe_stream_filtered["codec"] = file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""
                            file_probe_stream_filtered["language"] = file_probe_stream["tags"]["language"].lower() \
                                if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"] \
                                    and file_probe_stream["tags"]["language"].lower() != "und") else file_target_language
                            file_probe_stream_filtered["channels"] = str(file_probe_stream["channels"])
                        elif file_probe_stream_type == "subtitle":
                            file_probe_stream_filtered["codec"] = file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""
                            file_probe_stream_filtered["language"] = file_probe_stream["tags"]["language"].lower() \
                                if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"] \
                                    and file_probe_stream["tags"]["language"].lower() != "und") else file_target_language
                            file_probe_stream_filtered["format"] = "Picture" \
                                if ("tags" in file_probe_stream and "width" in file_probe_stream["tags"]) else "Text"
                file_probe_bit_rate = round(int(file_probe["format"]["bit_rate"]) / 10 ** 3) \
                    if ("format" in file_probe and "bit_rate" in file_probe["format"]) else -1
                file_probe_duration_h = float(file_probe["format"]["duration"]) / 60 ** 2 \
                    if ("format" in file_probe and "duration" in file_probe["format"]) else -1
                file_probe_size_b = int(file_probe["format"]["size"]) \
                    if ("format" in file_probe and "size" in file_probe["format"]) else os.path.getsize(file_path)
                file_probe_streams_filtered["video"].sort(key=lambda stream: int(stream["width"]), reverse=True)
                file_probe_streams_filtered_audios = []
                file_probe_streams_filtered_audios_supplementary = []
                for file_probe_streams_filtered_audio in file_probe_streams_filtered["audio"]:
                    if file_probe_streams_filtered_audio["codec"] in {"AAC", "AC3", "EAC3"} and \
                            file_probe_streams_filtered_audio["language"] == file_target_language:
                        file_probe_streams_filtered_audios.append(file_probe_streams_filtered_audio)
                    else:
                        file_probe_streams_filtered_audios_supplementary.append(file_probe_streams_filtered_audio)
                if len(file_probe_streams_filtered_audios) == 0:
                    file_probe_streams_filtered_audios_supplementary = []
                    for file_probe_streams_filtered_audio in file_probe_streams_filtered["audio"]:
                        if file_probe_streams_filtered_audio["language"] == file_target_language:
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
                            file_probe_streams_filtered_subtitle["language"] == "eng":
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
                    {"target_language": file_target_language},
                    {"native_language": file_native_language},
                    {"media_directory": file_path_root},
                    {"media_scope": file_media_scope},
                    {"media_type": file_media_type},
                    {"base_directory": file_base_dir},
                    {"version_directory": file_version_dir},
                    {"version_qualifier": file_version_qualifier},
                    {"file_path": " {} ".format(shlex.quote(file_path))},
                    {"config_path": " {} ".format(shlex.quote(file_transcode_path)) if len(file_transcode_path) > 0 else ""},
                    {"config_root_path": " {} ".format(shlex.quote(file_transcode_path_root))},
                    {"file_extension": file_extension},
                    {"container_format": file_probe["format"]["format_name"].lower() \
                        if ("format" in file_probe and "format_name" in file_probe["format"]) else ""},
                    {"duration__hours": str(round(file_probe_duration_h, 2 if file_probe_duration_h > 1 else 4)) \
                        if file_probe_duration_h > 0 else ""},
                    {"size__GB": str(round(file_probe_size_b / 10 ** 9, 2 if file_probe_duration_h > 1 else 4))},
                    {"bit_rate__Kbps": str(file_probe_bit_rate) if file_probe_bit_rate > 0 else ""},
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
                             if len(column.split("__")) == 2 else column.replace("_", " ").title()) if "_" in column else column)

    metadata_enriched_list = []
    for metadata in metadata_list:
        def _add(key, value):
            metadata.update({key: value})
            metadata.move_to_end(key, last=False)

        _add("versions_count", "")
        _add("transcode_priority", "")
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
    if len(metadata_original_pl) > 0 and len(metadata_cache_pl) > 0:
        metadata_original_pl = metadata_original_pl.filter(~pl.col("Media Directory").is_in([
            media_directory[0] for media_directory in metadata_cache_pl.select("Media Directory").unique().rows()
        ]))
    metadata_updated_pl = _format_columns(
        pl.concat([metadata_original_pl, metadata_cache_pl], how="diagonal")
    )
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
                (pl.col("Target Language") == "eng") &
                (pl.col("Audio 1 Language") != "eng")
            ).then(pl.lit("Incomplete"))
            .when(
                (pl.col("Target Language") != "eng") &
                ((pl.col("Subtitle 1 Language").is_null()) |
                 (pl.col("Subtitle 1 Language") != "eng")
                 )
            ).then(pl.lit("Incomplete"))
            .otherwise(pl.lit("Complete"))
        ).alias("File State"))
    metadata_updated_pl = metadata_updated_pl.with_columns(
        (
            pl.when(
                ((pl.col("Target Quality") == "High") &
                 (pl.col("Size (GB)").cast(pl.Float32) > ((1 + TARGET_SIZE_DELTA) * TARGET_SIZE_HIGH_GB))
                 ) |
                ((pl.col("Target Quality") == "Medium") &
                 (pl.col("Size (GB)").cast(pl.Float32) > ((1 + TARGET_SIZE_DELTA) * TARGET_SIZE_MEDIUM_GB))
                 ) |
                ((pl.col("Target Quality") == "Low") &
                 (pl.col("Size (GB)").cast(pl.Float32) > ((1 + TARGET_SIZE_DELTA) * TARGET_SIZE_LOW_GB))
                 )
            ).then(pl.lit("Large"))
            .when(
                ((pl.col("Target Quality") == "High") &
                 (pl.col("Size (GB)").cast(pl.Float32) < (TARGET_SIZE_DELTA * TARGET_SIZE_HIGH_GB))
                 ) |
                ((pl.col("Target Quality") == "Medium") &
                 (pl.col("Size (GB)").cast(pl.Float32) < (TARGET_SIZE_DELTA * TARGET_SIZE_MEDIUM_GB))
                 ) |
                ((pl.col("Target Quality") == "Low") &
                 (pl.col("Size (GB)").cast(pl.Float32) < (TARGET_SIZE_DELTA * TARGET_SIZE_LOW_GB))
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
                        (pl.col("Video 1 Codec") == "MPEG4") |
                        (pl.col("Video 1 Codec") == "MJPEG")
                )) |
                ((pl.col("File Extension").str.to_lowercase() == "m2ts") & (
                        (pl.col("Video 1 Codec") == "AVC") |
                        (pl.col("Video 1 Codec") == "HEVC") |
                        (pl.col("Video 1 Codec") == "MPEG2VIDEO")
                )) |
                ((pl.col("File Extension").str.to_lowercase() == "mkv") & (
                        (pl.col("Video 1 Codec") == "AVC") |
                        (pl.col("Video 1 Codec") == "HEVC") |
                        (pl.col("Video 1 Codec") == "MPEG2VIDEO")
                )) |
                ((pl.col("File Extension").str.to_lowercase() == "mov") & (
                        (pl.col("Video 1 Codec") == "AVC") |
                        (pl.col("Video 1 Codec") == "HEVC") |
                        (pl.col("Video 1 Codec") == "MPEG2VIDEO") |
                        (pl.col("Video 1 Codec") == "MPEG4") |
                        (pl.col("Video 1 Codec") == "VC1") |
                        (pl.col("Video 1 Codec") == "VP9")
                )) |
                ((pl.col("File Extension").str.to_lowercase() == "mp4") & (
                        (pl.col("Video 1 Codec") == "AVC") |
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
                ((pl.col("Target Language") == pl.col("Audio 1 Language")) &
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
        pl.col("Base Path").count().over("Base Path")
        .alias("Versions Count")
    ).drop("Base Path")

    # TODO
    metadata_updated_pl = metadata_updated_pl.with_columns(
        (
            pl.when(
                (pl.col("File State") == "Corrupt")
            ).then(None)
            .otherwise(
                pl.lit("1")
            )
        ).alias("Transcode Priority"))
    metadata_updated_pl = metadata_updated_pl.with_columns(
        (
            pl.when(
                (pl.col("File State") == "Corrupt") |
                (pl.col("File State") == "Incomplete")
            ).then(pl.lit("Download"))
            .when(
                (pl.col("File Size") == "Small") &
                (pl.col("Target Quality") != "Low")
            ).then(pl.lit("Upscale"))
            .when(
                (pl.col("Versions Count").cast(pl.Int32) > 1)
            ).then(pl.lit("Merge"))
            .when(
                (pl.col("Plex Video") == "Transcode") |
                (pl.col("Plex Audio") == "Transcode") |
                (pl.col("Plex Subtitle") == "Transcode")
            ).then(pl.lit("Transcode"))
            .when(
                (pl.col("File Size") == "Large") |
                (pl.col("Metadata State") == "Messy")
            ).then(pl.lit("Reformat"))
            .otherwise(pl.lit("Nothing"))
        ).alias("File Action"))

    # TODO
    # with pl.Config(
    #         tbl_rows=-1,
    #         tbl_cols=-1,
    #         fmt_str_lengths=20,
    #         set_tbl_width_chars=30000,
    #         set_fmt_float="full",
    #         set_ascii_tables=True,
    #         tbl_formatting="ASCII_FULL_CONDENSED",
    #         set_tbl_hide_dataframe_shape=True,
    # ):
    #     print("")
    #     print(metadata_updated_pl)
    #     print("")

    metadata_updated_pl = metadata_updated_pl.with_columns([
        pl.when(pl.col(pl.Utf8).str.len_bytes() == 0).then(None).otherwise(pl.col(pl.Utf8)).name.keep()
    ])
    metadata_updated_pl = metadata_updated_pl[[
        column.name for column in metadata_updated_pl if not (column.null_count() == metadata_updated_pl.height)
    ]]
    if len(metadata_updated_pl) > 0:
        metadata_updated_pd = metadata_updated_pl.to_pandas()
        metadata_updated_pd = metadata_updated_pd.set_index("File Name").sort_index()
        metadata_spread.df_to_sheet(metadata_updated_pd, sheet="Data", replace=False, index=True,
                                    add_filter=True, freeze_index=True, freeze_headers=True)
    print("{}done".format("Analysing {} ".format(file_path_root) if verbose else ""))
    sys.stdout.flush()
    return files_analysed


def _unwrap_lists(lists):
    if isinstance(lists, list):
        dicts = OrderedDict()
        for item in lists:
            dicts[next(iter(item))] = _unwrap_lists(next(iter(item.values())))
        return dicts
    return lists


def _flatten_dicts(dicts, parent_key=''):
    items = []
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
