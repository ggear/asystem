import argparse
import os
import sys
from collections import OrderedDict
from collections.abc import MutableMapping
from pathlib import Path

import ffmpeg
import polars as pl
import yaml
from gspread_pandas import Spread


# build test data with dummy file
# Analyse library on per share basis, all to do local shares only deltas, deploy to do refresh and do all
# build an item metadata yaml file, pyyaml and ffmpeg-python
# build an item transcode script if necessary, write out transcode metadata file from logs (fps, time, host, command) - mobile version as well?
# build an item replace script if necessary
# build a global xlsx, update but allow manual editing, direct play possible, target quality, required to convert, versions ready to replace
# build a global transcode script, ordered by priority, script takes in number of items to process
# build a global replace script, dry run showing which items, execute actually doing the work


def _analyse(file_path_root, sheet_guid, verbose=False, refresh=False):
    if not os.path.isdir(file_path_root):
        print("Error: path [{}] does not exist".format(file_path_root))
        return -1
    files_analysed = 0
    metatdata_list = []
    print("Analysing {} ... ".format(file_path_root), end=("\n" if verbose else ""))
    sys.stdout.flush()
    for file_dir_path, _, file_names in os.walk(file_path_root):
        for file_name in file_names:
            file_path = os.path.join(file_dir_path, file_name)
            file_relative_dir = "." + file_dir_path.replace(file_path_root, "")
            file_relative_dir_tokens = file_relative_dir.split(os.sep)
            file_extension = os.path.splitext(file_name)[1].replace(".", "")
            file_metadata_path = os.path.join(file_dir_path, "{}.yaml".format(os.path.splitext(file_name)[0]))
            file_media_scope = file_relative_dir_tokens[1] \
                if len(file_relative_dir_tokens) > 3 else ""
            file_media_type = file_relative_dir_tokens[2] \
                if len(file_relative_dir_tokens) > 3 else ""
            if file_extension in {"yaml"}:
                continue;
            if verbose:
                print("{} ... ".format(os.path.join(file_relative_dir, file_name)), end='')
            if file_media_type not in {"movies", "series"}:
                if verbose:
                    print("ignoring library type [{}]".format(file_media_type))
                continue;
            if file_extension not in {"avi", "m2ts", "mkv", "mov", "mp4", "wmv"}:
                if verbose:
                    print("ignoring unknown file extension [{}]".format(file_extension))
                continue;
            if refresh or not os.path.isfile(file_metadata_path):
                file_probe = ffmpeg.probe(file_path)
                file_probe_streams_filtered = {
                    "video": [],
                    "audio": [],
                    "subtitle": [],
                    "other": [],
                }
                if "streams" in file_probe:
                    for file_probe_stream in file_probe["streams"]:
                        file_probe_stream_filtered = []
                        file_probe_stream_type = file_probe_stream["codec_type"].lower() \
                            if "codec_type" in file_probe_stream else ""
                        if file_probe_stream_type not in file_probe_streams_filtered:
                            file_probe_stream_type = "other"
                        file_probe_streams_filtered[file_probe_stream_type].append({
                            str(len(file_probe_streams_filtered[file_probe_stream_type]) + 1): \
                                file_probe_stream_filtered
                        })
                        file_probe_stream_filtered.append({"index": str(file_probe_stream["index"]) \
                            if "index" in file_probe_stream else ""})
                        file_probe_stream_filtered.append({"type": file_probe_stream["codec_type"].lower() \
                            if "codec_type" in file_probe_stream else ""})
                        if file_probe_stream_type == "video":
                            file_probe_stream_video_codec = file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""
                            if "H264" in file_probe_stream_video_codec or "AVC" in file_probe_stream_video_codec:
                                file_probe_stream_video_codec = "AVC"
                            if "H265" in file_probe_stream_video_codec or "HEVC" in file_probe_stream_video_codec:
                                file_probe_stream_video_codec = "HEVC"
                            file_probe_stream_filtered.append({"codec": file_probe_stream_video_codec})
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
                            file_probe_stream_filtered.append({"resolution": file_probe_stream_video_resolution})
                            file_probe_stream_filtered.append({"width": str(file_probe_stream_video_width) \
                                if file_probe_stream_video_width > 0 else ""})
                            file_probe_stream_filtered.append({"height": str(file_probe_stream_video_height) \
                                if file_probe_stream_video_height > 0 else ""})
                        elif file_probe_stream_type == "audio":
                            file_probe_stream_filtered.append({"codec": file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""})
                            file_probe_stream_filtered.append({"language": file_probe_stream["tags"]["language"].lower() \
                                if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"]) else ""})
                            file_probe_stream_filtered.append({"channels": str(file_probe_stream["channels"])})
                        elif file_probe_stream_type == "subtitle":
                            file_probe_stream_filtered.append({"codec": file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""})
                            file_probe_stream_filtered.append({"language": file_probe_stream["tags"]["language"].lower() \
                                if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"]) else ""})
                            file_probe_stream_filtered.append({"format": "Picture" \
                                if ("tags" in file_probe_stream and "width" in file_probe_stream["tags"]) else "Text"})
                    file_probe_transcode_priority = ""
                    file_probe_plex_mode = "Transcode"
                    file_probe_plex_direct_play_video = False
                    file_probe_plex_direct_play_audio = False
                    file_probe_messy_metadata = False
                    file_probe_bit_rate = round(int(file_probe["format"]["bit_rate"]) / 10 ** 3) \
                        if ("format" in file_probe and "bit_rate" in file_probe["format"]) else -1

                    # TODO: Provide greater coverage, non-eng audio/subtitles, multiple video, grade based on number of subtitles/audio/video etc
                    # for file_probe_subtitles in file_probe_streams_filtered["subtitle"]:
                    #     for file_probe_subtitle in file_probe_subtitles.values():
                    #         if (
                    #                 file_probe_subtitle[2]["format"] == "Picture"
                    #         ):
                    #             file_probe_messy_metadata = True

                    for file_probe_videos in file_probe_streams_filtered["video"]:
                        for file_probe_video in file_probe_videos.values():
                            if (
                                    file_extension == "avi" and file_probe_video[2]["codec"] in {"MPEG4", "MJPEG"} or \
                                    file_extension == "m2ts" and file_probe_video[2]["codec"] in {"AVC", "HEVC", "MPEG2VIDEO"} or \
                                    file_extension == "mkv" and file_probe_video[2]["codec"] in {"AVC", "HEVC", "MPEG2VIDEO", "MPEG4"} or \
                                    file_extension == "mov" and file_probe_video[2]["codec"] in {"AVC", "MPEG4"} or \
                                    file_extension == "mp4" and file_probe_video[2]["codec"] in {"AVC", "HEVC"} or \
                                    file_extension == "wmv" and file_probe_video[2]["codec"] in {"WMV3", "VC1"}
                            ):
                                file_probe_plex_direct_play_video = True
                    for file_probe_audios in file_probe_streams_filtered["audio"]:
                        for file_probe_audio in file_probe_audios.values():
                            if (
                                    file_extension == "avi" and \
                                    file_probe_audio[2]["codec"] in {"AAC", "EAC3", "AC3", "MP3", "PCM"} or file_extension == "m2ts" and \
                                    file_probe_audio[2]["codec"] in {"AAC", "EAC3", "AC3", "MP3", "PCM"} or file_extension == "mkv" and \
                                    file_probe_audio[2]["codec"] in {"AAC", "EAC3", "AC3", "MP3", "PCM"} or file_extension == "mov" and \
                                    file_probe_audio[2]["codec"] in {"AAC", "EAC3", "AC3"} or file_extension == "mp4" and \
                                    file_probe_audio[2]["codec"] in {"AAC", "EAC3", "AC3", "MP3"} or file_extension == "wmv" and \
                                    file_probe_audio[2]["codec"] in {"EAC3", "AC3", "WMAPRO", "WMAV2"}
                            ):
                                file_probe_plex_direct_play_audio = True
                    if file_probe_plex_direct_play_video and file_probe_plex_direct_play_audio:
                        file_probe_plex_mode = "Direct Play"
                        if file_probe_bit_rate > 12000:
                            file_probe_transcode_priority = "2"
                        elif file_probe_messy_metadata:
                            file_probe_transcode_priority = "3"
                    else:
                        file_probe_transcode_priority = "1"
                    file_probe_duration_h = float(file_probe["format"]["duration"]) / 60 ** 2 \
                        if ("format" in file_probe and "duration" in file_probe["format"]) else -1
                    file_probe_size_gb = int(file_probe["format"]["size"]) / 10 ** 9 \
                        if ("format" in file_probe and "size" in file_probe["format"]) else -1
                    file_probe_filtered = [
                        {"file_name": os.path.basename(file_probe["format"]["filename"]) \
                            if ("format" in file_probe and "filename" in file_probe["format"]) else ""},
                        {"media_directory": file_path_root},
                        {"media_scope": file_media_scope},
                        {"media_type": file_media_type},
                        {"version_directory": os.path.dirname(file_probe["format"]["filename"]) \
                            .replace(os.path.join(file_path_root, file_media_scope, file_media_type) + "/", "") \
                            if ("format" in file_probe and "filename" in file_probe["format"]) else ""},
                        {"plex_mode": file_probe_plex_mode},
                        {"plex_mode_video": "Direct Play" if file_probe_plex_direct_play_video else "Transcode"},
                        {"plex_mode_audio": "Direct Play" if file_probe_plex_direct_play_audio else "Transcode"},
                        {"metadata_state": "Messy" if file_probe_messy_metadata else "Clean"},
                        {"transcode_priority": file_probe_transcode_priority},
                        {"file_extension": file_extension},
                        {"container_format": file_probe["format"]["format_name"].lower() \
                            if ("format" in file_probe and "format_name" in file_probe["format"]) else ""},
                        {"duration__hours": str(round(file_probe_duration_h, 2 if file_probe_duration_h > 1 else 4)) \
                            if file_probe_duration_h > 0 else ""},
                        {"size__GB": str(round(file_probe_size_gb, 2 if file_probe_duration_h > 1 else 4)) \
                            if file_probe_size_gb > 0 else ""},
                        {"bit_rate__Kbps": str(file_probe_bit_rate) if file_probe_bit_rate > 0 else ""},
                        {"stream_count": str(sum(map(len, file_probe_streams_filtered.values())))}
                    ]
                    for file_probe_stream_type in file_probe_streams_filtered:
                        file_probe_filtered.append({"{}_count".format(file_probe_stream_type):
                                                        str(len(file_probe_streams_filtered[file_probe_stream_type]))})
                        if file_probe_stream_type in {"audio", "subtitle"}:
                            language_english_count = 0
                            for file_probe_streams in file_probe_streams_filtered[file_probe_stream_type]:
                                if next(iter(file_probe_streams.values()))[3]["language"] == "eng":
                                    language_english_count += 1
                            file_probe_filtered.append({"{}_english_count".format(file_probe_stream_type): str(language_english_count)})
                        file_probe_filtered.append({file_probe_stream_type:
                                                        file_probe_streams_filtered[file_probe_stream_type]})
                    with open(file_metadata_path, 'w') as file_metadata:
                        yaml.dump(file_probe_filtered, file_metadata, width=float("inf"))
                if verbose:
                    print("wrote metadata file cache")
            else:
                if verbose:
                    print("skipping, metadata file already cached")
            with open(file_metadata_path, 'r') as file_metadata:
                def _unwrap(lists):
                    if isinstance(lists, list):
                        dicts = OrderedDict()
                        for item in lists:
                            dicts[next(iter(item))] = _unwrap(next(iter(item.values())))
                        return dicts
                    return lists

                def _flatten(dicts, parent_key='', separator='_'):
                    items = []
                    for key, value in dicts.items():
                        new_key = parent_key + separator + str(key) if parent_key else str(key)
                        if isinstance(value, MutableMapping):
                            items.extend(_flatten(value, new_key, separator=separator).items())
                        else:
                            items.append((new_key, value))
                    return OrderedDict(items)

                metatdata_list.append(_flatten(_unwrap(yaml.safe_load(file_metadata))))
            files_analysed += 1
    metadata_cache_pl = pl.DataFrame(metatdata_list)
    metadata_columns = []
    metadata_columns_streams = ("video", "audio", "subtitle", "other")
    for metadata_column in metadata_cache_pl.columns:
        if not metadata_column.startswith(metadata_columns_streams):
            metadata_columns.append(metadata_column)
    for metadata_column_stream in metadata_columns_streams:
        for metadata_column in metadata_cache_pl.columns:
            if metadata_column.startswith(metadata_column_stream):
                metadata_columns.append(metadata_column)
    metadata_cache_pl = metadata_cache_pl.select(metadata_columns) \
        .rename(lambda column: \
                    (column.split("__")[0].replace("_", " ").title() + " (" + column.split("__")[1] + ")") \
                        if len(column.split("__")) == 2 else column.replace("_", " ").title())
    metadata_spread = Spread("https://docs.google.com/spreadsheets/d/" + sheet_guid, sheet="Data")
    metadata_original_list = metadata_spread._fix_merge_values(metadata_spread.sheet.get_all_values())
    if len(metadata_original_list) > 0:
        metadata_original_pl = pl.DataFrame(
            schema=metadata_original_list[0],
            data=metadata_original_list[1:],
            orient="row"
        )
    else:
        metadata_original_pl = pl.DataFrame()
    if len(metadata_original_pl) > 0 and len(metadata_cache_pl) > 0:
        metadata_original_pl = metadata_original_pl.filter(~pl.col("Media Directory").is_in(
            [media_directory[0] for media_directory in metadata_cache_pl.select("Media Directory").unique().rows()]
        ))
    metadata_updated_pl = pl.concat([metadata_original_pl, metadata_cache_pl], how="diagonal")
    if len(metadata_updated_pl) > 0:
        metadata_updated_pd = metadata_updated_pl.to_pandas()
        metadata_updated_pd = metadata_updated_pd.set_index("File Name").sort_index()
        metadata_spread.df_to_sheet(metadata_updated_pd, sheet="Data", replace=True, index=True,
                                    add_filter=True, freeze_index=True, freeze_headers=True)

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
    #     print(metadata_cache_pl)
    #     print("")
    #     print(metadata_original_pl)
    #     print("")
    #     print(metadata_updated_pl)
    #     print("")

    print("{}done".format("Analysing {} ".format(file_path_root) if verbose else ""))
    sys.stdout.flush()
    return files_analysed


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--verbose", default=False, action="store_true")
    argument_parser.add_argument("--refresh", default=False, action="store_true")
    argument_parser.add_argument("directory")
    argument_parser.add_argument("sheetguid")
    arguments = argument_parser.parse_args()
    sys.exit(2 if _analyse(
        Path(arguments.directory).absolute().as_posix(),
        arguments.sheetguid,
        arguments.verbose,
        arguments.refresh,
    ) < 0 else 0)
