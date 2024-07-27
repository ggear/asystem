"""
WARNING: This file is written by the build process, any manual edits will be lost!
"""

import argparse
import os
import re
import sys
from collections import OrderedDict
from collections.abc import MutableMapping
from pathlib import Path

import ffmpeg
import polars as pl
import polars.selectors as cs
import yaml
from ffmpeg._run import Error
from gspread_pandas import Spread

TARGET_SIZE_MIN_GB = 2
TARGET_SIZE_MID_GB = 6
TARGET_SIZE_MAX_GB = 12
TARGET_SIZE_DELTA = 1 / 3

# Reference: https://github.com/lisamelton/more-video-transcoding
TARGET_BITRATE_VIDEO_MIN_KBPS = 2500
TARGET_BITRATE_VIDEO_MID_KBPS = 5000
TARGET_BITRATE_VIDEO_MAX_KBPS = 7500

MEDIA_FILE_EXTENSIONS = {"avi", "m2ts", "mkv", "mov", "mp4", "wmv"}

FIELDS_STRING = [
    "File Name",
    "File Action",
    "File Version",
    "File State",
    "File Size",
    "Plex Video",
    "Plex Audio",
    "Plex Subtitle",
    "Metadata State",
    "Action Index",
    "Transcode Action",
    "Target Quality",
    "Target Lang",
    "Native Lang",
    "Media Directory",
    "Media Scope",
    "Media Type",
    "Base Directory",
    "Version Directory",
    "Version Qualifier",
    "File Directory",
    "File Stem",
    "File Extension",
    "Container Format",
    "Duration (hours)",
    "File Size (GB)",
    "Bitrate (Kbps)",
    "Video 1 Index",
    "Video 1 Codec",
    "Video 1 Label",
    "Video 1 Res",
    "Video 1 Res Min",
    "Video 1 Res Mid",
    "Video 1 Res Max",
    "Video 1 Width",
    "Video 1 Height",
    "Video 1 Bitrate Est (Kbps)",
    "Video 1 Bitrate Min (Kbps)",
    "Video 1 Bitrate Mid (Kbps)",
    "Video 1 Bitrate Max (Kbps)",
    "Audio 1 Index",
    "Audio 1 Codec",
    "Audio 1 Lang",
    "Audio 1 Channels",
    "Audio 1 Surround",
    "Subtitle 1 Index",
    "Subtitle 1 Codec",
    "Subtitle 1 Lang",
    "Subtitle 1 Forced",
    "Subtitle 1 Format",
]

FIELDS_INT = [
    "Version Count",
    "Stream Count",
    "Video Count",
    "Audio Count",
    "Subtitle Count",
    "Other Count",
]

BASH_SIGTERM_HANDLER = "sigterm_handler() {{\n{}  exit 1\n}}\n" \
                       "trap 'trap \" \" SIGINT SIGTERM SIGHUP; kill 0; wait; sigterm_handler' SIGINT SIGTERM SIGHUP\n\n"
BASH_ECHO_HEADER = "echo '#######################################################################################'\n"


def _analyse(file_path_root, sheet_guid, clean=False, verbose=False):
    def _truncate_sheet():
        for sheet in {"Data", "Summary"}:
            metadata_spread_data = Spread(sheet_url, sheet=sheet)
            metadata_spread_data.freeze(0, 0, sheet=sheet)
            metadata_spread_data.clear_sheet(sheet=sheet)

    sheet_url = "https://docs.google.com/spreadsheets/d/" + sheet_guid
    if clean and file_path_root == "/share":
        print("Truncating 'http://docs.google.com/sheet' ... ", end=("\n" if verbose else ""), flush=True)
        _truncate_sheet()
        print("{}done".format("Truncating 'http://docs.google.com/sheet' " if verbose else ""))
        return 0
    if not os.path.isdir(file_path_root):
        print("Error: path [{}] does not exist".format(file_path_root))
        return -1
    file_path_root_re = re.search("(.*/share/[0-9]+)*", file_path_root)
    if file_path_root_re is None or file_path_root_re.groups()[0] is None or file_path_root_re.groups()[0] == "":
        print("Error: path [{}] is not a share".format(file_path_root))
        return -2
    file_path_root_parent = file_path_root_re.groups()[0]
    file_path_root_is_nested = file_path_root != file_path_root_parent
    file_path_media = os.path.join(file_path_root_parent, "media")
    if not os.path.isdir(file_path_media):
        print("Error: path [{}] does not exist".format(file_path_media))
        return -3
    if file_path_root_is_nested and not file_path_root.startswith(file_path_media):
        print("Error: path [{}] not nested in media directory [{}]".format(file_path_root, file_path_media))
        return -4
    file_path_root_target = file_path_root if file_path_root_is_nested else file_path_media
    file_path_root_target_relative = file_path_root_target.replace(file_path_media, ".")
    file_path_scripts = os.path.join(file_path_root_parent, "tmp", "scripts")
    if not os.path.isdir(file_path_scripts):
        os.makedirs(file_path_scripts, exist_ok=True)
        _set_permissions(file_path_scripts, 0o750)
    files_analysed = 0
    metadata_list = []
    print("Analysing '{}' ... ".format(file_path_root), end=("\n" if verbose else ""), flush=True)
    for file_dir_path, _, file_names in os.walk(file_path_root_target):
        for file_name in file_names:
            metadata_file_written = False
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
            if file_media_type in {"audio"} or file_extension in {"yaml", "sh", "srt", "jpg", "jpeg", "log"}:
                continue;
            if verbose:
                print("{} ... ".format(os.path.join(file_relative_dir, file_name)), end='', flush=True)
            if file_media_type not in {"movies", "series"}:
                message = "skipping file due to unknown library type [{}]".format(file_media_type)
                if verbose:
                    print(message, flush=True)
                else:
                    print("{} [{}]".format(message, file_path))
                    print("Analysing '{}' ... ".format(file_path_root), end="", flush=True)
                continue;
            if file_extension not in MEDIA_FILE_EXTENSIONS:
                message = "skipping file due to unknown file extension [{}]".format(file_extension)
                if verbose:
                    print(message, flush=True)
                else:
                    print("{} [{}]".format(message, file_path))
                    print("Analysing '{}' ... ".format(file_path_root), end="", flush=True)
                continue;
            file_base_tokens = 5 if (
                    file_media_type == "series" and
                    len(file_relative_dir_tokens) > 4 and
                    re.search("^Season [1-9]+[0-9]*", file_relative_dir_tokens[4]) is not None
            ) else 4
            file_version_dir = os.sep.join(file_relative_dir_tokens[file_base_tokens:]) \
                if len(file_relative_dir_tokens) > file_base_tokens else "."
            if file_version_dir.startswith("._transcode_") or file_version_dir.endswith("/.inProgress"):
                message = "skipping file currently transcoding"
                if verbose:
                    print(message, flush=True)
                else:
                    print("{} [{}]".format(message, file_path))
                    print("Analysing '{}' ... ".format(file_path_root), end="", flush=True)
                continue
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
            if not os.path.isfile(file_metadata_path):
                file_defaults_dict = {
                    "transcode_action": "Analyse",
                    "target_quality": "Mid",
                    "target_channels": "2",
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
                                file_defaults_dict["transcode_action"] = file_defaults_dict["transcode_action"].title()
                                if file_defaults_dict["transcode_action"] not in {"Analyse", "Ignore"}:
                                    raise Exception("Invalid transcode action: {}".format(file_defaults_dict["transcode_action"]))
                                file_defaults_dict["target_quality"] = file_defaults_dict["target_quality"].title()
                                if file_defaults_dict["target_quality"] not in {"Min", "Mid", "Max"}:
                                    raise Exception("Invalid target quality: {}".format(file_defaults_dict["target_quality"]))
                                file_defaults_dict["target_channels"] = str(int(file_defaults_dict["target_channels"]))
                                file_defaults_dict["native_lang"] = file_defaults_dict["native_lang"].lower()
                                file_defaults_dict["target_lang"] = file_defaults_dict["target_lang"].lower()
                            except Exception:
                                message = "skipping file due to defaults metadata file [{}] load error" \
                                    .format(file_defaults_path)
                                if verbose:
                                    print(message, flush=True)
                                else:
                                    print("{} [{}]".format(message, file_path))
                                    print("Analysing '{}' ... ".format(file_path_root), end="", flush=True)
                                continue
                file_transcode_action = file_defaults_dict["transcode_action"]
                file_target_quality = file_defaults_dict["target_quality"]
                file_target_channels = file_defaults_dict["target_channels"]
                file_native_lang = file_defaults_dict["native_lang"]
                file_target_lang = file_defaults_dict["target_lang"]
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
                            file_probe_stream_filtered["surround"] = "Atmos" if (
                                    ("profile" in file_probe_stream and \
                                     "atmos" in file_probe_stream["profile"].lower()) or
                                    ("tags" in file_probe_stream and "title" in file_probe_stream["tags"] and \
                                     "atmos" in file_probe_stream["tags"]["title"].lower())
                            ) else "Standard"
                            file_probe_stream_filtered["bitrate__Kbps"] = \
                                str(round(int(file_probe_stream["bit_rate"]) / 10 ** 3)) \
                                    if "bit_rate" in file_probe_stream else ""
                        elif file_probe_stream_type == "subtitle":
                            file_probe_stream_filtered["codec"] = file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""
                            file_probe_stream_filtered["lang"] = file_probe_stream["tags"]["language"].lower() \
                                if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"] \
                                    and file_probe_stream["tags"]["language"].lower() != "und") else file_target_lang
                            file_probe_stream_filtered["forced"] = ("Yes" if file_probe_stream["disposition"]["forced"] == 1 else "No") \
                                if ("disposition" in file_probe_stream and "forced" in file_probe_stream["disposition"]) else "No"
                            file_probe_stream_filtered["format"] = "Picture" if \
                                (file_probe_stream_filtered["codec"] in {"VOB", "VOBSUB", "DVD_SUBTITLE"} or \
                                 ("tags" in file_probe_stream and "width" in file_probe_stream["tags"])) else "Text"
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
                    {"transcode_action": file_transcode_action},
                    {"target_quality": file_target_quality},
                    {"target_channels": file_target_channels},
                    {"target_lang": file_target_lang},
                    {"native_lang": file_native_lang},
                    {"media_directory": _delocalise_path(file_path_media, file_path_root)},
                    {"media_scope": file_media_scope},
                    {"media_type": file_media_type},
                    {"base_directory": file_base_dir},
                    {"version_directory": file_version_dir},
                    {"version_qualifier": file_version_qualifier},
                    {"file_directory": " '{}' ".format(_delocalise_path(file_dir_path, file_path_root))},
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
                metadata_file_written = True
            with open(file_metadata_path, 'r') as file_metadata:
                try:
                    if not file_path_root_is_nested or metadata_file_written:
                        metadata_list.append(_flatten_dicts(_unwrap_lists(yaml.safe_load(file_metadata))))
                        if verbose:
                            if metadata_file_written:
                                print("wrote and loaded metadata file", flush=True)
                            else:
                                print("loaded metadata file", flush=True)
                except Exception:
                    message = "skipping file due to metadata file load error"
                    if verbose:
                        print(message, flush=True)
                    else:
                        print("{} [{}]".format(message, file_path))
                        print("Analysing '{}' ... ".format(file_path_root), end="", flush=True)
                    continue
            files_analysed += 1

    def _format_columns(_data):
        _data = _data.with_columns((~cs.string()).cast(pl.Utf8)) \
            .with_columns([pl.when(pl.col(pl.Utf8).str.len_bytes() == 0) \
                          .then(None).otherwise(pl.col(pl.Utf8)).name.keep()])
        metadata_columns = []
        metadata_columns_streams = ("video", "audio", "subtitle", "other")
        for metadata_column in _data.columns:
            if not metadata_column.lower().startswith(metadata_columns_streams):
                metadata_columns.append(metadata_column)
        for metadata_column_stream in metadata_columns_streams:
            for metadata_column in _data.columns:
                if metadata_column.lower().startswith(metadata_column_stream):
                    metadata_columns.append(metadata_column)
        return _data.select(metadata_columns) \
            .rename(lambda column: \
                        ((column.split("__")[0].replace("_", " ").title() + " (" + column.split("__")[1] + ")") \
                             if len(column.split("__")) == 2 else column.replace("_", " ").title()) \
                            if "_" in column else column)

    if verbose:
        print("{}/*/._metadata_* -> #local-dataframe ... ".format(file_path_root_target_relative), end='', flush=True)
    metadata_enriched_list = []
    for metadata in metadata_list:
        def _add_field(key, value):
            metadata.update({key: value})
            metadata.move_to_end(key, last=False)

        _add_field("version_count", "")
        _add_field("action_index", "")
        _add_field("metadata_state", "")
        _add_field("plex_subtitle", "")
        _add_field("plex_audio", "")
        _add_field("plex_video", "")
        _add_field("file_size", "")
        _add_field("file_state", "")
        _add_field("file_version", "")
        _add_field("file_action", "")
        metadata.move_to_end("file_name", last=False)
        metadata_enriched_list.append(dict(metadata))
    metadata_local_pl = _format_columns(pl.DataFrame(metadata_enriched_list))
    if verbose:
        print("done", flush=True)
    if "Media Directory" not in metadata_local_pl.schema:
        metadata_local_pl = pl.DataFrame()
    metadata_local_media_dirs = []
    if metadata_local_pl.width > 0:
        metadata_local_media_dirs = [_dir[0] for _dir in metadata_local_pl.select("Media Directory").unique().rows()]
    if verbose:
        print("#local-dataframe partition '{}' ... done".format(metadata_local_media_dirs), flush=True)
    if file_path_root_is_nested:
        metadata_merged_pl = metadata_local_pl
    else:
        if verbose:
            print("#local-dataframe + {} -> #merged-dataframe ... ".format(sheet_url), end='', flush=True)
        metadata_spread_data = Spread(sheet_url, sheet="Data")
        metadata_sheet_list = metadata_spread_data._fix_merge_values(metadata_spread_data.sheet.get_all_values())
        if len(metadata_sheet_list) > 0:
            metadata_sheet_pl = _format_columns(pl.DataFrame(
                schema=metadata_sheet_list[0],
                data=metadata_sheet_list[1:],
                orient="row"
            ))
        else:
            metadata_sheet_pl = pl.DataFrame()
        if metadata_sheet_pl.width > 0 and "Media Directory" not in metadata_sheet_pl.schema:
            _truncate_sheet()
            metadata_sheet_pl = pl.DataFrame()
        if metadata_local_pl.width > 0:
            if metadata_sheet_pl.width > 0:
                metadata_sheet_pl = metadata_sheet_pl.filter(
                    ~pl.col("Media Directory").is_in(metadata_local_media_dirs))

                with pl.Config(
                        tbl_rows=-1,
                        tbl_cols=-1,
                        fmt_str_lengths=200,
                        set_tbl_width_chars=30000,
                        set_fmt_float="full",
                        set_ascii_tables=True,
                        tbl_formatting="ASCII_FULL_CONDENSED",
                        set_tbl_hide_dataframe_shape=True,
                ):
                    test = metadata_local_pl \
                        .filter(pl.col("File Name") == "Any Given Sunday (1999).mkv") \
                        .select("File Name", "^Audio.*$")
                    print(test)

                metadata_merged_pl = \
                    pl.concat([metadata_sheet_pl, metadata_local_pl], how="diagonal_relaxed")

                with pl.Config(
                        tbl_rows=-1,
                        tbl_cols=-1,
                        fmt_str_lengths=200,
                        set_tbl_width_chars=30000,
                        set_fmt_float="full",
                        set_ascii_tables=True,
                        tbl_formatting="ASCII_FULL_CONDENSED",
                        set_tbl_hide_dataframe_shape=True,
                ):
                    test = metadata_merged_pl \
                        .filter(pl.col("File Name") == "Any Given Sunday (1999).mkv") \
                        .select("File Name", "^Audio.*$")
                    print(test)

            else:
                metadata_merged_pl = metadata_local_pl
        else:
            metadata_merged_pl = pl.DataFrame()
        if verbose:
            print("done", flush=True)
    if verbose:
        print("#merged-dataframe -> #enriched-dataframe ... ", end='', flush=True)
    metadata_merged_pl = _format_columns(
        _add_cols(_add_cols(metadata_merged_pl, FIELDS_INT, "0"), FIELDS_STRING))
    if metadata_merged_pl.height > 0:
        metadata_merged_pl = metadata_merged_pl.with_columns(
            (
                pl.when(
                    (pl.col("Base Directory").is_null()) |
                    (pl.col("Base Directory") == ".") |
                    (pl.col("Container Format").is_null()) |
                    (pl.col("Container Format") == "") |
                    (pl.col("Duration (hours)").is_null()) |
                    (pl.col("Duration (hours)") == "") |
                    (pl.col("File Size (GB)").is_null()) |
                    (pl.col("File Size (GB)") == "") |
                    (pl.col("Bitrate (Kbps)").is_null()) |
                    (pl.col("Bitrate (Kbps)") == "") |
                    (pl.col("Stream Count").is_null()) |
                    (pl.col("Stream Count") == "") |
                    (pl.col("Video Count").is_null()) |
                    (pl.col("Video Count") == "") |
                    (pl.col("Audio Count").is_null()) |
                    (pl.col("Audio Count") == "")
                ).then(pl.lit("Corrupt"))
                .when(
                    (pl.col("Transcode Action") == "Ignore")
                ).then(pl.lit("Ignored"))
                .when(
                    (pl.col("Stream Count") == "0") |
                    (pl.col("Video Count") == "0") |
                    (pl.col("Audio Count") == "0")
                ).then(pl.lit("Incomplete"))
                .when(
                    (pl.col("Target Lang") == "eng") &
                    (pl.col("Audio 1 Lang") != "eng")
                ).then(pl.lit("Incomplete"))
                .when(
                    (pl.col("Target Lang") != "eng") &
                    (
                            (pl.col("Subtitle Count") == "0") |
                            (pl.col("Subtitle 1 Lang").is_null()) |
                            (pl.col("Subtitle 1 Lang") != "eng")
                    )
                ).then(pl.lit("Incomplete"))
                .otherwise(pl.lit("Complete"))
            ).alias("File State"))
        metadata_merged_pl = metadata_merged_pl.filter(
            (~pl.col("File Size (GB)").is_null()) &
            (pl.col("File Size (GB)").str.len_bytes() > 0)
        ).with_columns(
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
        metadata_merged_pl = metadata_merged_pl.with_columns(
            (
                pl.when(
                    (pl.col("File Name").str.contains("___TRANSCODE")) |
                    (~pl.col("Version Directory").str.ends_with("."))
                ).then(pl.lit("Transcoded"))
                .otherwise(pl.lit("Original"))
            ).alias("File Version"))
        metadata_merged_pl = metadata_merged_pl.with_columns(
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
        metadata_merged_pl = metadata_merged_pl.with_columns(
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
        metadata_merged_pl = metadata_merged_pl.with_columns(
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
        metadata_merged_pl = metadata_merged_pl.with_columns(
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
        metadata_merged_pl = metadata_merged_pl.with_columns(
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
        metadata_merged_pl = metadata_merged_pl.with_columns(
            (
                pl.when(
                    (pl.col("File State") == "Corrupt") |
                    (pl.col("File State") == "Incomplete")
                ).then(pl.lit("1. Download"))
                .when(
                    (pl.col("Version Count").cast(pl.Int32) > 1)
                ).then(pl.lit("2. Merge"))
                .when(
                    (pl.col("Transcode Action") != "Ignore") & (
                            (pl.col("File Size") == "Small") &
                            (pl.col("Target Quality") != "Min")
                    )
                ).then(pl.lit("4. Upscale"))
                .when(
                    (pl.col("Transcode Action") != "Ignore") & (
                            (pl.col("Plex Video") == "Transcode") |
                            (pl.col("Plex Audio") == "Transcode") |
                            (pl.col("Duration (hours)").is_null()) |
                            (pl.col("Bitrate (Kbps)").is_null())
                    )
                ).then(pl.lit("3. Transcode"))
                .when(
                    (pl.col("Transcode Action") != "Ignore") & (
                            (pl.col("File Size") == "Large") |
                            (pl.col("Metadata State") == "Messy")
                    )
                ).then(pl.lit("5. Reformat"))
                .otherwise(pl.lit("6. Nothing"))
            ).alias("File Action"))
        metadata_merged_pl = pl.concat([
            metadata_merged_pl.filter(
                (pl.col("File Action").str.ends_with("Transcode")) |
                (pl.col("File Action").str.ends_with("Reformat"))
            ).with_columns(
                pl.col("File Size (GB)").cast(pl.Float32).alias("Action Index Sort")
            ),
            metadata_merged_pl.filter(
                (~pl.col("File Action").str.ends_with("Transcode")) &
                (~pl.col("File Action").str.ends_with("Reformat"))
            ).sort("File Name", descending=True).with_columns(
                pl.col("File Name").cum_count().cast(pl.Float32).alias("Action Index Sort")
            )
        ]).select(
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
        metadata_merged_pl = metadata_merged_pl[[
            column.name for column in metadata_merged_pl \
            if not (column.null_count() == metadata_merged_pl.height)
        ]]
    if verbose:
        print("done", flush=True)
    if metadata_merged_pl.height > 0:
        if verbose:
            print("#enriched-dataframe -> {}/*.sh ... ".format(file_path_root_target_relative), end='', flush=True)

        # TODO: Write out file and global merge/reformat scripts
        # TODO: Make a media-transcode/merge scripts to context determine all scripts under path or accross local shares if none - maybe make all other scripts do the same?
        metadata_transcode_pl = metadata_merged_pl.filter(
            (
                    (file_path_root_is_nested) |
                    (pl.col("File Action").str.ends_with("Merge")) |
                    (pl.col("File Action").str.ends_with("Transcode"))
            ) &
            (pl.col("File Version") != "Transcoded") &
            (pl.col("Media Directory").is_in(metadata_local_media_dirs))
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
                    pl.lit("___TRANSCODE_"),
                    pl.col("Target Quality").str.to_uppercase(),
                    pl.lit(".mkv"),
                ]).alias("Transcode File Name")
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
                    pl.lit("../../../.."),
                    pl.col("Script Path").str.strip_prefix(file_path_media),
                ]).alias("Script Relative Path"),
                pl.concat_str([
                    pl.lit("# !/bin/bash\n\n"),
                    pl.lit("ROOT_DIR=$(dirname \"$(readlink -f \"$0\")\")\n\n"),
                    pl.lit(BASH_SIGTERM_HANDLER.format("  echo 'Killing Transcode!!!!'\n  rm -f \"${ROOT_DIR}\"/*.mkv*\n")),
                    pl.lit("rm -f \"${ROOT_DIR}\"/*.mkv*\n\n"),
                    pl.lit("#other-transcode \"${ROOT_DIR}/../"), pl.col("Transcode File Name"), pl.lit("\" \\\n"),
                    pl.lit("# --add-subtitle 1 \\\n"),
                    pl.lit("# --add-subtitle 2 \\\n"),
                    pl.lit("# --copy-video\n"),
                    pl.lit("#rm -f \"${ROOT_DIR}\"/*.mkv.log\n"),
                    pl.lit("#mv -v \"${ROOT_DIR}\"/*.mkv \"${ROOT_DIR}/../"), pl.col("Transcode File Name"), pl.lit("\"\n"),
                    pl.lit("#echo ''\n\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("echo 'Transcoding: "), pl.col("File Name"), pl.lit(" ... '\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("if [ -f \"${ROOT_DIR}/../"), pl.col("Transcode File Name"), pl.lit("\" ]; then\n"),
                    pl.lit("  echo '' && echo -n 'Skipped (pre-existing): ' && date && echo '' && exit 1\n"),
                    pl.lit("fi\n"),
                    pl.lit("if [ $(df -k \"${ROOT_DIR}\" | tail -1 | awk '{print $4}') -lt 20000000 ]; then\n"),
                    pl.lit("  echo '' && echo -n 'Skipped (space): ' && date && echo '' && exit 1\n"),
                    pl.lit("fi\n"),
                    pl.lit("cd \"${ROOT_DIR}\"\n"),
                    pl.lit("other-transcode \"${ROOT_DIR}/../"), pl.col("File Name"), pl.lit("\" \\\n"),
                    pl.lit("  --target "), pl.col("Transcode Target"), pl.lit(" \\\n"),
                    pl.lit("  --main-audio "), pl.col("Audio 1 Index"), pl.lit(" \\\n"),
                    pl.lit("  --add-audio eng \\\n"),
                    pl.lit("  --add-subtitle eng \\\n"),
                    pl.lit("  --hevc \n"),
                    pl.lit("if [ $? -eq 0 ]; then\n"),
                    pl.lit("  rm -f \"${ROOT_DIR}\"/*.mkv.log\n"),
                    pl.lit("  mv -f \"${ROOT_DIR}\"/*.mkv \"${ROOT_DIR}/../"), pl.col("Transcode File Name"), pl.lit("\"\n"),
                    pl.lit("  if [ $? -eq 0 ]; then echo -n 'Completed: ' && date; else echo -n 'Failed (mv): ' && date; fi\n"),
                    pl.lit("else\n"),
                    pl.lit("  echo -n 'Failed (other-transcode): ' && date\n"),
                    pl.lit("fi\n"),
                    pl.lit("echo ''\n"),
                ]).alias("Script Source"),
            ]
        ).sort("Action Index").select(["Script Path", "Script Relative Path", "Script Directory", "Script Source"])
        transcode_script_global_file = None
        transcode_script_global_path = _localise_path(os.path.join(file_path_scripts, "transcode.sh"), file_path_root)
        try:
            if not file_path_root_is_nested:
                transcode_script_global_file = open(transcode_script_global_path, 'w')
                transcode_script_global_file.write("# !/bin/bash\n\n")
                transcode_script_global_file.write("ROOT_DIR=$(dirname \"$(readlink -f \"$0\")\")\n\n")
                transcode_script_global_file.write(BASH_SIGTERM_HANDLER.format(""))
                transcode_script_global_file.write("echo ''\n")
            for transcode_script_local in metadata_transcode_pl.rows():
                if not any(map(lambda transcode_script_local_item: transcode_script_local_item is None, transcode_script_local)):
                    if not file_path_root_is_nested:
                        transcode_script_global_file.write("\"${{ROOT_DIR}}/{}\"\n".format(
                            _localise_path(transcode_script_local[1], file_path_root)))
                    transcode_script_local_dir = _localise_path(transcode_script_local[2], file_path_root)
                    os.makedirs(transcode_script_local_dir, exist_ok=True)
                    _set_permissions(transcode_script_local_dir, 0o750)
                    transcode_script_local_path = _localise_path(transcode_script_local[0], file_path_root)
                    with open(transcode_script_local_path, 'w') as transcode_script_local_file:
                        transcode_script_local_file.write(transcode_script_local[3])
                    _set_permissions(transcode_script_local_path, 0o750)
        finally:
            if not file_path_root_is_nested and transcode_script_global_file is not None:
                transcode_script_global_file.close()
        if not file_path_root_is_nested:
            _set_permissions(transcode_script_global_path, 0o750)
        # if verbose:
        #     print("done", flush=True)
        #     with pl.Config(
        #             tbl_rows=-1,
        #             tbl_cols=-1,
        #             fmt_str_lengths=200,
        #             set_tbl_width_chars=30000,
        #             set_fmt_float="full",
        #             set_ascii_tables=True,
        #             tbl_formatting="ASCII_FULL_CONDENSED",
        #             set_tbl_hide_dataframe_shape=True,
        #     ):
        #         print("Metadata summary ... ")
        #         print(
        #             metadata_merged_pl \
        #                 .select(metadata_merged_pl.columns[:9] + ["File Directory"])
        #                 .with_columns(pl.col("File Directory").str.strip_chars().name.keep())
        #                 .fill_null("")
        #         )
        if not file_path_root_is_nested:
            if verbose:
                print("#enriched-dataframe -> {} ... ".format(sheet_url), end='', flush=True)
            metadata_updated_pd = metadata_merged_pl.to_pandas()



            # TODO
            # with pl.Config(
            #         tbl_rows=-1,
            #         tbl_cols=-1,
            #         fmt_str_lengths=200,
            #         set_tbl_width_chars=30000,
            #         set_fmt_float="full",
            #         set_ascii_tables=True,
            #         tbl_formatting="ASCII_FULL_CONDENSED",
            #         set_tbl_hide_dataframe_shape=True,
            # ):
            #     test = metadata_merged_pl \
            #           .filter(pl.col("File Name") == "Any Given Sunday (1999).mkv") \
            #           .select("File Name", "^Audio.*$")
            #     print(test)
            # import pandas as pd
            # pd.set_option('display.width', None)
            # pd.set_option('display.max_columns', None)
            # pd.set_option('display.max_rows', None)
            # print(metadata_updated_pd[metadata_updated_pd["File Name"] == "Any Given Sunday (1999).mkv"][test.columns])




            metadata_spread_data = Spread(sheet_url, sheet="Data")
            metadata_spread_data.df_to_sheet(metadata_updated_pd, sheet="Data",
                                             replace=True, index=False, add_filter=True)
            if metadata_spread_data.get_sheet_dims()[0] > 1 and \
                    metadata_spread_data.get_sheet_dims()[1] > 1:
                metadata_spread_data.freeze(1, 1, sheet="Data")
            if verbose:
                print("done", flush=True)
    print("{}done".format("Analysing '{}' ".format(file_path_root) if verbose else ""))
    sys.stdout.flush()
    return files_analysed


def _add_cols(_data, _cols, _default=None):
    for col in _cols:
        if col not in _data.schema:
            _data = _data.with_columns(pl.lit(_default).cast(pl.String).alias(col))
    return _data


def _localise_path(_path, _local_path):
    return _path if ("/share/" not in _path or not _path.startswith("/share/")) \
        else "{}{}".format(_local_path.split("/share/")[0], _path)


def _delocalise_path(_path, _local_path):
    return _path if ("/share/" not in _path or _path.startswith("/share/")) \
        else "{}{}".format("/share/", _path.split("/share/")[1])


def _set_permissions(_path, _mode=0o644):
    os.chmod(_path, _mode)
    try:
        os.chown(_path, 1000, 100)
    except PermissionError:
        pass


def _unwrap_lists(_lists):
    if _lists is None:
        _lists = []
    if isinstance(_lists, list):
        dicts = OrderedDict()
        for item in _lists:
            dicts[next(iter(item))] = _unwrap_lists(next(iter(item.values())))
        return dicts
    return _lists


def _flatten_dicts(_dicts, _parent_key=''):
    items = []
    if _dicts is None:
        _dicts = {}
    for key, value in _dicts.items():
        new_key = _parent_key + '_' + str(key) if _parent_key else str(key)
        if isinstance(value, MutableMapping):
            items.extend(_flatten_dicts(value, new_key).items())
        else:
            items.append((new_key, value))
    return OrderedDict(items)


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--verbose", default=False, action="store_true")
    argument_parser.add_argument("--clean", default=False, action="store_true")
    argument_parser.add_argument("directory")
    argument_parser.add_argument("sheetguid")
    arguments = argument_parser.parse_args()
    sys.exit(2 if _analyse(
        Path(arguments.directory).absolute().as_posix(),
        arguments.sheetguid,
        arguments.clean,
        arguments.verbose
    ) < 0 else 0)
