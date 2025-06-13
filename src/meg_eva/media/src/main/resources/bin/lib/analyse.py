"""
WARNING: This file is written by the build process, any manual edits will be lost!
"""

import argparse
import os
import re
import string
import sys
import typing
from collections import OrderedDict
from collections.abc import MutableMapping
from pathlib import Path

import ffmpeg
import polars as pl
import polars.selectors as cs
import yaml
from aenum import AutoNumberEnum
# noinspection PyProtectedMember
from ffmpeg._run import Error
from gspread_pandas import Spread
from polars.exceptions import ColumnNotFoundError

QUALITY_MIN = 3  # <=720
QUALITY_MID = 8  # ==1080
QUALITY_MAX = 9  # >=2160
BITRATE_HVEC_SCALE = 1.5  # H265 efficiency factor over H264
BITRATE_SIZE_LOWER_SCALE = 0.25  # Margin when assessing small size
BITRATE_SIZE_UPPER_SCALE = 1.35  # Margin when assessing large size
BITRATE_QUALITY_SCALE = 0.15  # Quality quantum
# Reasonable defaults: https://github.com/lisamelton/other_video_transcoding/blob/b063ef953eaaf0c0a36530ff97d8aa4e477973d5/other-transcode.rb#L1064
BITRATE_UNSCALED_KBPS = {
    "HD": 3000,  # <=720, <=QUALITY_MIN
    "FHD": 6000,  # ==1080, <=QUALITY_MID
    "UHD": 12000,  # >=2160, >=QUALITY_MAX
}


class FileAction(AutoNumberEnum):
    _init_ = 'has_script'
    __order__ = 'RENAME CHECK MERGE UPSCALE REFORMAT TRANSCODE DOWNSCALE NOTHING'
    RENAME = True
    CHECK = True
    MERGE = True
    UPSCALE = True
    REFORMAT = True
    TRANSCODE = True
    DOWNSCALE = True
    NOTHING = False

    @property
    def label(self):
        return "{}. {}".format(self.value, self.name.title())

    @property
    def script(self):
        return self.name.lower() if self.has_script else None


FileAction = FileAction  # type: typing.Union[typing.Type[FileAction], typing.Iterable]

MEDIA_YEAR_NUMBER_REGEXP = r"\(19[4-9][0-9]\)|\(20[0-9][0-9]\)"
MEDIA_SEASON_NUMBER_REGEXP = r"Season ([0-9]?[0-9]+)"
MEDIA_EPISODE_NUMBER_REGEXP = r".*([sS])([0-9]?[0-9]+)([-_\. ]*)([eE])([0-9]?[-]*[0-9]+)(.*)"
MEDIA_EPISODE_NAME_REGEXP = MEDIA_EPISODE_NUMBER_REGEXP + r"\..*"
MEDIA_FILE_EXTENSIONS = {"avi", "m2ts", "mkv", "mov", "mp4", "wmv", "ts"}
MEDIA_FILE_EXTENSIONS_IGNORE = {"yaml", "sh", "srt", "png", "jpg", "jpeg", "log"}
MEDIA_FILE_SCRIPTS = [_file_action.script for _file_action in FileAction if _file_action.has_script]

TOKEN_TRANSCODE = "__TRANSCODE"
TOKEN_UNKNOWABLE = "__UNKNOWABLE"

BASH_EXIT_HANDLER = "shopt -s expand_aliases\n" \
                    "[[ $(uname) == 'Darwin' ]] && alias echo=gecho\n" \
                    "[[ $(uname) == 'Darwin' ]] && alias realpath=grealpath\n\n" \
                    "sigterm_handler() {{\n{}  exit 1\n}}\n" \
                    "trap 'trap \" \" SIGINT SIGTERM SIGHUP; kill 0; wait; sigterm_handler' SIGINT SIGTERM SIGHUP\n\n"
BASH_ECHO_HEADER = ("echo \""
                    "###############################################################"
                    "###############################################################"
                    "\"\n")


# noinspection PyUnresolvedReferences,PyUnusedLocal
def _analyse(file_path_root, sheet_guid, clean=False, force=False, defaults=False, verbose=False):
    def _print_message(_prefix=None, _message=None, _context=None,
                       _header=True, _footer=True, _no_header_footer=False):
        hanging_header = False
        if _prefix is None:
            hanging_header = True
            _prefix = "Analysing '{}' ... ".format(file_path_root)
        if not _no_header_footer and not _header:
            print(_prefix, end="")
        if _message is not None:
            if verbose:
                print(_message)
            else:
                if _context is not None:
                    print("{} [{}]".format(_message, _context))
                else:
                    print(_message)
        if not _no_header_footer and _footer:
            print(_prefix, end=("\n" if verbose and hanging_header else ""))
        sys.stdout.flush()

    def _truncate_sheet(_sheet_url):
        for sheet in {"Data", "Summary"}:
            metadata_spread_data_truncate = Spread(_sheet_url, sheet=sheet)
            metadata_spread_data_truncate.freeze(0, 0, sheet=sheet)
            metadata_spread_data_truncate.clear_sheet(sheet=sheet)

    sheet_url = "https://docs.google.com/spreadsheets/d/" + sheet_guid
    file_path_root = os.path.abspath(file_path_root)
    if clean and file_path_root == "/share":
        print("Truncating '{}' ... ".format(sheet_url), end="", flush=True)
        _truncate_sheet(sheet_url)
        print("done")
        return 0, get_file_actions_dict()
    if not os.path.isdir(file_path_root):
        print("Error: path [{}] does not exist".format(file_path_root))
        return -1, get_file_actions_dict()
    file_path_root_re = re.search("(.*/share/[0-9]+)*", file_path_root)
    if file_path_root_re is None or file_path_root_re.groups()[0] is None or file_path_root_re.groups()[0] == "":
        print("Error: path [{}] is not a share".format(file_path_root))
        return -2, get_file_actions_dict()
    file_path_root_parent = file_path_root_re.groups()[0]
    file_path_root_is_nested = file_path_root != file_path_root_parent
    file_path_media = os.path.join(file_path_root_parent, "media")
    if not os.path.isdir(file_path_media):
        print("Error: path [{}] does not exist".format(file_path_media))
        return -3, get_file_actions_dict()
    if file_path_root_is_nested and not file_path_root.startswith(file_path_media):
        print("Error: path [{}] not nested in media directory [{}]" \
              .format(file_path_root, file_path_media))
        return -4, get_file_actions_dict()
    file_path_root_target = file_path_root if file_path_root_is_nested else file_path_media
    file_path_root_target_relative = file_path_root_target.replace(file_path_media, ".")
    file_path_media_is_nested = file_path_media != file_path_root_target
    file_path_scripts = file_path_root_parent
    file_path_scripts_dirs = ("tmp", "scripts", "media", ".lib")
    for file_path_scripts_dir in file_path_scripts_dirs:
        file_path_scripts = os.path.join(file_path_scripts, file_path_scripts_dir)
        if not os.path.isdir(file_path_scripts):
            os.makedirs(file_path_scripts, exist_ok=True)
            _set_permissions(file_path_scripts, 0o750)
    files_analysed = 0
    metadata_list = []
    metadata_files_written = set()
    _print_message()
    for file_dir_path, _, file_names in os.walk(file_path_root_target):
        for file_name in file_names:
            file_path = os.path.join(file_dir_path, file_name)
            file_path_media_parent = os.path.dirname(file_path_media)
            file_relative_dir = "." + file_dir_path.replace(file_path_media, "")
            file_relative_dir_tokens = file_relative_dir.split(os.sep)
            file_name_sans_extension = os.path.splitext(file_name)[0]
            file_extension = os.path.splitext(file_name)[1].replace(".", "")
            file_metadata_path = os.path.join(
                file_dir_path, "._metadata_{}_{}.yaml".format(
                    file_name_sans_extension,
                    file_extension,
                ))
            file_media_scope = file_relative_dir_tokens[1] \
                if len(file_relative_dir_tokens) > 1 else ""
            file_media_type = file_relative_dir_tokens[2] \
                if len(file_relative_dir_tokens) > 2 else ""
            if file_media_type in {"audio"} or file_extension in MEDIA_FILE_EXTENSIONS_IGNORE:
                continue
            _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)),
                           _no_header_footer=not verbose)
            if file_media_type not in {"movies", "series"}:
                _print_message(_message="skipping file due to unknown library type [{}]".format(file_media_type),
                               _context=file_path, _no_header_footer=verbose)
                continue
            if file_extension not in MEDIA_FILE_EXTENSIONS:
                _print_message(_message="skipping file due to unknown file extension [{}]".format(file_extension),
                               _context=file_path, _no_header_footer=verbose)
                continue
            file_base_tokens = 5 if (
                    file_media_type == "series" and
                    len(file_relative_dir_tokens) > 4 and
                    re.search("^" + MEDIA_SEASON_NUMBER_REGEXP, file_relative_dir_tokens[4]) is not None
            ) else 4
            file_version_dir = os.sep.join(file_relative_dir_tokens[file_base_tokens:]) \
                if len(file_relative_dir_tokens) > file_base_tokens else "."
            if file_version_dir.startswith("._") or file_version_dir.endswith("/.inProgress"):
                _print_message(_message="skipping file currently transcoding",
                               _context=file_path, _no_header_footer=verbose)
                continue
            file_base_dir = os.sep.join(file_relative_dir_tokens[3:]).replace("/" + file_version_dir, "") \
                if len(file_relative_dir_tokens) > 3 else "."
            file_base_dir_parent = file_base_dir.split("/")[0]
            file_stem = file_base_dir_parent
            file_version_qualifier = ""
            file_season_match = None
            file_episode_match = None
            if file_media_type == "series":
                file_season_match = re.search("/" + MEDIA_SEASON_NUMBER_REGEXP, file_base_dir)
                file_episode_match = re.search(MEDIA_EPISODE_NAME_REGEXP, file_name)
                if file_episode_match is not None:
                    file_version_qualifier = "".join(file_episode_match.groups()).split(TOKEN_TRANSCODE)[0]
                    file_stem = "{} {}".format(file_stem, file_version_qualifier).title()
                else:
                    file_version_qualifier = file_name_sans_extension
                    if file_name.startswith(file_base_dir_parent):
                        file_stem = file_name_sans_extension.title()
                    else:
                        file_stem = "{} {}".format(file_stem, file_version_qualifier).title()
            file_version_qualifier = file_version_qualifier.lower()
            file_dir_rename = ""
            file_name_rename = ""
            if TOKEN_TRANSCODE in file_name or file_version_dir.startswith("Plex Versions"):
                file_dir_rename = ""
                file_name_rename = ""
            else:
                file_name_normalised = "{}.{}".format(_normalise_name(file_stem), file_extension) \
                    if _normalise_name(file_stem) != "" else ""
                if file_media_type == "series":
                    file_dir_normalised = _normalise_name(file_base_dir)
                    file_season_not_matching = file_season_match is not None and \
                                               file_episode_match is not None and \
                                               file_episode_match.groups()[1].lstrip("0") != \
                                               file_season_match.groups()[0].lstrip("0")
                    if (file_version_dir != "." and file_version_dir.startswith(
                            "Plex Versions")) or file_season_not_matching:
                        file_name_rename = ""
                        file_dir_rename = TOKEN_UNKNOWABLE
                        if file_season_not_matching:
                            _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)) \
                                if verbose else None, _message="file requires season directory moving from [{}]" \
                                           .format(file_relative_dir_tokens[-1]), _context=file_path)
                        else:
                            _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)) \
                                if verbose else None, _message="file requires nested directory moving from [{}]" \
                                           .format(file_version_dir), _context=file_path)
                    else:
                        file_name_normalised = file_name_normalised.replace(
                            _normalise_name(file_base_dir) + " " + _normalise_name(file_base_dir),
                            _normalise_name(file_base_dir))
                        if file_base_dir != file_dir_normalised:
                            if file_dir_normalised == "":
                                file_dir_rename = TOKEN_UNKNOWABLE
                                _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)) \
                                    if verbose else None, _message="file requires directory moving to [{}]" \
                                               .format(_normalise_name(file_name_sans_extension)), _context=file_path)
                            else:
                                file_dir_rename = _normalise_name(file_base_dir_parent)
                                _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)) \
                                    if verbose else None, _message="file requires directory renaming to [{}]" \
                                               .format(file_dir_rename), _context=file_path)
                        elif file_name != file_name_normalised:
                            if file_name_normalised != "":
                                file_name_rename = file_name_normalised
                                _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)) \
                                    if verbose else None, _message="file requires renaming to [{}]" \
                                               .format(file_name_rename), _context=file_path)
                else:
                    file_dir_normalised = _normalise_name(file_base_dir_parent)
                    file_year_match = re.findall(MEDIA_YEAR_NUMBER_REGEXP, file_dir_normalised)
                    if file_version_dir != "." and not file_version_dir.startswith("Plex Versions") or len(
                            file_year_match) != 1:
                        file_name_rename = ""
                        file_dir_rename = TOKEN_UNKNOWABLE
                        if len(file_year_match) != 1:
                            _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)) \
                                if verbose else None, _message=("file requires year adding to name [{}]"
                                                                if len(
                                file_year_match) == 0 else "file has ambiguous year in name [{}]") \
                                           .format(file_base_dir_parent), _context=file_path)
                        else:
                            _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)) \
                                if verbose else None, _message="file requires nested directory moving from [{}]" \
                                           .format(file_version_dir), _context=file_path)
                    else:
                        if file_base_dir_parent != file_dir_normalised:
                            if file_dir_normalised == "":
                                file_dir_rename = TOKEN_UNKNOWABLE
                                _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)) \
                                    if verbose else None, _message="file requires directory moving to [{}]" \
                                               .format(_normalise_name(file_name_sans_extension)), _context=file_path)
                            else:
                                file_dir_rename = file_dir_normalised
                                _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)) \
                                    if verbose else None, _message="file requires directory renaming to [{}]" \
                                               .format(file_dir_rename), _context=file_path)
                        if file_name != file_name_normalised:
                            if file_name_normalised != "":
                                file_name_rename = file_name_normalised
                                _print_message(_prefix="{} ... ".format(os.path.join(file_relative_dir, file_name)) \
                                    if verbose else None, _message="file requires renaming to [{}]" \
                                               .format(file_name_rename), _context=file_path)

            # noinspection PyArgumentList
            def _set_default_str(_file_defaults_dict, _file_defaults_key,
                                 _bounding_set=None, _formatter=str.title):
                _file_defaults_dict[_file_defaults_key] = _formatter(
                    _file_defaults_dict[_file_defaults_key].replace(" ", "") \
                        if isinstance(_file_defaults_dict[_file_defaults_key], str) else str(
                        _file_defaults_dict[_file_defaults_key]))
                if _bounding_set is not None and _file_defaults_dict[_file_defaults_key] not in _bounding_set:
                    raise Exception("Invalid {}: {}" \
                                    .format(_file_defaults_key, file_defaults_dict[_file_defaults_key]))

            def _set_default_numeric(_file_defaults_dict, _file_defaults_key, _bounding_lower=None,
                                     _bounding_upper=None):
                _file_defaults_dict[_file_defaults_key] = _file_defaults_dict[_file_defaults_key].replace(" ", "") \
                    if isinstance(_file_defaults_dict[_file_defaults_key], str) else str(
                    _file_defaults_dict[_file_defaults_key])
                if _file_defaults_dict[_file_defaults_key] != "" and (
                        not _file_defaults_dict[_file_defaults_key].isnumeric() or
                        (_bounding_lower is not None and int(
                            _file_defaults_dict[_file_defaults_key]) < _bounding_lower) or
                        (_bounding_upper is not None and int(
                            _file_defaults_dict[_file_defaults_key]) > _bounding_upper)):
                    raise Exception(
                        "Invalid {}: {}".format(_file_defaults_key, _file_defaults_dict[_file_defaults_key]))

            if not os.path.isfile(file_metadata_path):
                file_defaults_dict = {
                    "transcode_action": "Defer",
                    "target_quality": "6",
                    "target_video": "",
                    "target_audios": "",
                    "target_subtitles": "",
                    "target_channels": "2",
                    "target_lang": "eng",
                    "native_lang": "eng",
                }
                file_defaults_paths = []
                file_defaults_load_failed = False
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
                                _set_default_str(file_defaults_dict, "transcode_action", {"Defer", "Ignore", "Merged"})
                                _set_default_numeric(file_defaults_dict, "target_quality", 1, 9)
                                _set_default_numeric(file_defaults_dict, "target_video")
                                _set_default_numeric(file_defaults_dict, "target_audios")
                                _set_default_numeric(file_defaults_dict, "target_subtitles")
                                _set_default_numeric(file_defaults_dict, "target_channels")
                                _set_default_str(file_defaults_dict, "native_lang", _formatter=str.lower)
                                _set_default_str(file_defaults_dict, "target_lang", _formatter=str.lower)
                            except Exception as exception:
                                file_defaults_load_failed = True
                                _print_message(
                                    _message="skipping file due to defaults metadata file [{}] load error [{}]" \
                                        .format(file_defaults_path, exception),
                                    _context=file_path, _no_header_footer=True)
                if file_defaults_load_failed:
                    continue
                file_defaults_analysed_path = os.path.join(
                    file_dir_path, "._defaults_analysed_{}_{}.yaml".format(
                        file_name_sans_extension, file_extension))
                with open(file_defaults_analysed_path, 'w') as file_defaults_analysed:
                    yaml.dump(file_defaults_dict, file_defaults_analysed, width=float("inf"))
                _set_permissions(file_defaults_analysed_path)
                file_defaults_merged_path = os.path.join(
                    file_dir_path, "._defaults_merged_{}_{}.yaml".format(
                        file_name_sans_extension, file_extension))
                if os.path.isfile(file_defaults_merged_path) and file_defaults_dict["transcode_action"] != "Ignore":
                    file_defaults_dict["transcode_action"] = "Merged"
                file_transcode_action = file_defaults_dict["transcode_action"]
                file_target_quality = file_defaults_dict["target_quality"]
                file_target_video = file_defaults_dict["target_video"]
                file_target_audios = file_defaults_dict["target_audios"]
                file_target_subtitles = file_defaults_dict["target_subtitles"]
                file_target_channels = file_defaults_dict["target_channels"]
                file_native_lang = file_defaults_dict["native_lang"]
                file_target_lang = file_defaults_dict["target_lang"]
                try:
                    file_probe = ffmpeg.probe(file_path)
                except Error:
                    file_probe = {}
                file_probe_bitrate = round(int(file_probe["format"]["bit_rate"]) / 10 ** 3) \
                    if ("format" in file_probe and "bit_rate" in file_probe["format"]) else -1
                file_probe_duration = float(file_probe["format"]["duration"]) / 60 ** 2 \
                    if ("format" in file_probe and "duration" in file_probe["format"]) else -1
                file_probe_size = (int(file_probe["format"]["size"])
                                   if ("format" in file_probe and "size" in file_probe["format"])
                                   else os.path.getsize(file_path)) / 10 ** 9
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
                            if "codec_type" in file_probe_stream else "unknown"
                        if file_probe_stream_type not in file_probe_streams_filtered:
                            file_probe_stream_type = "other"
                        file_probe_streams_filtered[file_probe_stream_type].append(file_probe_stream_filtered)
                        file_probe_stream_filtered["index"] = str(file_probe_stream["index"]) \
                            if "index" in file_probe_stream else ""
                        file_probe_stream_filtered["index_{}".format(file_probe_stream_type)] = ""
                        if file_probe_stream_type == "video":
                            file_probe_stream_video_codec = file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""
                            if "H264" in file_probe_stream_video_codec or "AVC" in file_probe_stream_video_codec:
                                file_probe_stream_video_codec = "AVC"
                            if "H265" in file_probe_stream_video_codec or "HEVC" in file_probe_stream_video_codec:
                                file_probe_stream_video_codec = "HEVC"
                            file_probe_stream_filtered["codec"] = file_probe_stream_video_codec
                            file_probe_stream_filtered["profile"] = file_probe_stream["profile"].title() \
                                if "profile" in file_probe_stream else ""
                            file_probe_stream_filtered["colour_range"] = "HDR" \
                                if ("color_primaries" in file_probe_stream and
                                    file_probe_stream["color_primaries"].lower() in {
                                        "bt2020",
                                        "bt2100",
                                    }) else "SDR"
                            file_probe_stream_filtered["pixel_depth"] = "10" \
                                if ("pix_fmt" in file_probe_stream and
                                    file_probe_stream["pix_fmt"].lower() in {
                                        "yuv420p10le",
                                        "yuv422p10le",
                                        "yuv444p10",
                                        "p010",
                                        "p210",
                                        "v210",
                                        "v410",
                                    }) else "8"
                            file_probe_stream_filtered["colour_spec"] = file_probe_stream["color_primaries"].lower() \
                                if "color_primaries" in file_probe_stream else ""
                            file_probe_stream_filtered["pixel_format"] = file_probe_stream["pix_fmt"].lower() \
                                if "pix_fmt" in file_probe_stream else ""
                            file_probe_stream_video_field_order = "i"
                            if "field_order" in file_probe_stream:
                                if file_probe_stream["field_order"] == "progressive":
                                    file_probe_stream_video_field_order = "p"
                            file_probe_stream_video_label = ""
                            file_probe_stream_video_resolution = ""
                            file_probe_stream_video_width = int(file_probe_stream["width"]) \
                                if "width" in file_probe_stream else -1
                            file_probe_stream_video_height = int(file_probe_stream["height"]) \
                                if "height" in file_probe_stream else -1
                            if file_probe_stream_video_width > 0:
                                if file_probe_stream_video_width <= 640:
                                    file_probe_stream_video_label = "nHD"
                                    file_probe_stream_video_resolution = "360" + file_probe_stream_video_field_order
                                elif file_probe_stream_video_width <= 960:
                                    file_probe_stream_video_label = "qHD"
                                    file_probe_stream_video_resolution = "540" + file_probe_stream_video_field_order
                                elif file_probe_stream_video_width <= 1280:
                                    file_probe_stream_video_label = "HD"
                                    file_probe_stream_video_resolution = "720" + file_probe_stream_video_field_order
                                elif file_probe_stream_video_width <= 1600:
                                    file_probe_stream_video_label = "HD+"
                                    file_probe_stream_video_resolution = "900" + file_probe_stream_video_field_order
                                elif file_probe_stream_video_width <= 1920:
                                    file_probe_stream_video_label = "FHD"
                                    file_probe_stream_video_resolution = "1080" + file_probe_stream_video_field_order
                                elif file_probe_stream_video_width <= 2560:
                                    file_probe_stream_video_label = "QHD"
                                    file_probe_stream_video_resolution = "1440" + file_probe_stream_video_field_order
                                elif file_probe_stream_video_width <= 3200:
                                    file_probe_stream_video_label = "QHD+"
                                    file_probe_stream_video_resolution = "1800" + file_probe_stream_video_field_order
                                elif file_probe_stream_video_width <= 3840:
                                    file_probe_stream_video_label = "UHD"
                                    file_probe_stream_video_resolution = "2160" + file_probe_stream_video_field_order
                                elif file_probe_stream_video_width <= 5120:
                                    file_probe_stream_video_label = "UHD"
                                    file_probe_stream_video_resolution = "2880" + file_probe_stream_video_field_order
                                elif file_probe_stream_video_width <= 7680:
                                    file_probe_stream_video_label = "UHD"
                                    file_probe_stream_video_resolution = "4320" + file_probe_stream_video_field_order
                                elif file_probe_stream_video_width <= 15360:
                                    file_probe_stream_video_label = "UHD"
                                    file_probe_stream_video_resolution = "8640" + file_probe_stream_video_field_order
                            file_probe_stream_filtered["label"] = file_probe_stream_video_label
                            file_probe_stream_filtered["height"] = str(file_probe_stream_video_height) \
                                if file_probe_stream_video_height > 0 else ""
                            file_probe_stream_filtered["width"] = str(file_probe_stream_video_width) \
                                if file_probe_stream_video_width > 0 else ""
                            file_probe_stream_filtered["resolution"] = file_probe_stream_video_resolution
                            file_probe_stream_filtered["resolution_target"] = ""
                            file_probe_stream_filtered["resolution_target_size"] = ""
                            file_stream_bitrate = round(int(file_probe_stream["bit_rate"]) / 10 ** 3) \
                                if "bit_rate" in file_probe_stream else -1
                            file_probe_stream_filtered["bitrate__Kbps"] = str(file_stream_bitrate) \
                                if file_stream_bitrate > 0 else ""
                            file_probe_stream_filtered["bitrate_estimate__Kbps"] = file_stream_bitrate \
                                if file_stream_bitrate > 0 else -1
                            file_probe_stream_filtered["bitrate_target__Kbps"] = ""
                            file_probe_stream_filtered["bitrate_target_ratio"] = ""
                            file_probe_stream_filtered["bitrate_target_size"] = ""
                            file_probe_stream_filtered["target_size"] = ""
                        elif file_probe_stream_type == "audio":
                            file_stream_codec = file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""
                            file_probe_stream_filtered["codec"] = file_stream_codec
                            file_probe_stream_filtered["lang"] = file_probe_stream["tags"]["language"].lower() \
                                if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"]
                                    and file_probe_stream["tags"]["language"].lower() != "und") else file_target_lang
                            file_stream_channels = int(file_probe_stream["channels"]) \
                                if "channels" in file_probe_stream else 2
                            file_probe_stream_filtered["channels"] = str(file_stream_channels)
                            file_probe_stream_filtered["surround"] = "Atmos" if (
                                    ("profile" in file_probe_stream and
                                     "atmos" in file_probe_stream["profile"].lower()) or
                                    ("tags" in file_probe_stream and "title" in file_probe_stream["tags"] and
                                     "atmos" in file_probe_stream["tags"]["title"].lower())
                            ) else "Standard"
                            file_probe_stream_filtered["bitrate__Kbps"] = \
                                str(round(int(file_probe_stream["bit_rate"]) / 10 ** 3)) \
                                    if "bit_rate" in file_probe_stream else ""
                        elif file_probe_stream_type == "subtitle":
                            file_probe_stream_filtered["codec"] = file_probe_stream["codec_name"].upper() \
                                if "codec_name" in file_probe_stream else ""
                            file_probe_stream_filtered["lang"] = file_probe_stream["tags"]["language"].lower() \
                                if ("tags" in file_probe_stream and "language" in file_probe_stream["tags"]
                                    and file_probe_stream["tags"]["language"].lower() != "und") else file_target_lang
                            file_probe_stream_filtered["forced"] = (
                                "Yes" if file_probe_stream["disposition"]["forced"] == 1 else "No") \
                                if ("disposition" in file_probe_stream and "forced" in file_probe_stream[
                                "disposition"]) else "No"
                            file_probe_stream_filtered["format"] = "Picture" if \
                                (file_probe_stream_filtered["codec"] in {"VOB", "VOBSUB", "DVD_SUBTITLE"} or
                                 ("tags" in file_probe_stream and "width" in file_probe_stream["tags"])) else "Text"
                for stream_label in ["video", "audio", "subtitle"]:
                    stream_index = 0
                    file_probe_streams_filtered[stream_label].sort(key=lambda _stream: _stream["index"])
                    for stream in file_probe_streams_filtered[stream_label]:
                        stream_index += 1
                        stream["index_{}".format(stream_label)] = str(stream_index)
                file_probe_streams_filtered["video"].sort(key=lambda _stream: int(_stream["width"]), reverse=True)
                for file_stream_video_index, file_stream_video in enumerate(file_probe_streams_filtered["video"]):
                    file_stream_video_quality = int(file_target_quality)
                    file_stream_video_width = int(file_stream_video["width"])
                    if file_stream_video_quality <= QUALITY_MIN:
                        file_stream_video_width_target = 1280
                        file_stream_video["resolution_target"] = "<=720p"
                    elif file_stream_video_quality <= QUALITY_MID:
                        file_stream_video_width_target = 1920
                        file_stream_video["resolution_target"] = "1080p"
                    else:
                        file_stream_video_width_target = 2560
                        file_stream_video["resolution_target"] = ">=2160"
                    if file_stream_video_width_target <= 1280:
                        bitrate_target = BITRATE_UNSCALED_KBPS["HD"]
                    elif file_stream_video_width_target <= 1920:
                        bitrate_target = BITRATE_UNSCALED_KBPS["FHD"]
                    else:
                        bitrate_target = BITRATE_UNSCALED_KBPS["UHD"]
                    if ((file_stream_video_quality <= QUALITY_MIN and file_stream_video_width > 1280) or
                            (file_stream_video_quality <= QUALITY_MID and file_stream_video_width > 1920)):
                        file_stream_video["resolution_target_size"] = "Large"
                    elif (file_stream_video_quality > 1 and (
                            (file_stream_video_quality <= QUALITY_MID and file_stream_video_width < 1280) or
                            (file_stream_video_quality >= QUALITY_MAX and file_stream_video_width < 2560))):
                        file_stream_video["resolution_target_size"] = "Small"
                    else:
                        file_stream_video["resolution_target_size"] = "Right"
                    file_stream_video_bitrate = file_stream_video["bitrate_estimate__Kbps"]
                    if file_stream_video_bitrate < 0:
                        if file_probe_bitrate > 0:
                            file_stream_audio_bitrate = 0
                            for file_stream_audio in file_probe_streams_filtered["audio"]:
                                file_stream_audio_bitrate += int(file_stream_audio["bitrate__Kbps"]) \
                                    if file_stream_audio["bitrate__Kbps"] != "" else 128
                            file_stream_video_bitrate = file_probe_bitrate - file_stream_audio_bitrate \
                                if file_probe_bitrate > file_stream_audio_bitrate else file_probe_bitrate
                    if file_stream_video_bitrate < 0:
                        file_stream_video["bitrate_estimate__Kbps"] = ""
                    else:
                        file_stream_video["bitrate_estimate__Kbps"] = str(file_stream_video_bitrate)
                        file_stream_video_bitrate_target = round(
                            bitrate_target * file_stream_video_quality * BITRATE_QUALITY_SCALE *
                            (BITRATE_HVEC_SCALE if file_stream_video["codec"] != "HEVC" else 1)
                        )
                        file_stream_video["bitrate_target__Kbps"] = str(file_stream_video_bitrate_target)
                        file_stream_video["bitrate_target_ratio"] = \
                            str(round(file_stream_video_bitrate / file_stream_video_bitrate_target, 2))
                        if file_stream_video_bitrate > (
                                BITRATE_SIZE_UPPER_SCALE * file_stream_video_bitrate_target):
                            file_stream_video["bitrate_target_size"] = "Large"
                        elif file_stream_video_bitrate < \
                                (BITRATE_SIZE_LOWER_SCALE * file_stream_video_bitrate_target):
                            file_stream_video["bitrate_target_size"] = "Small"
                        else:
                            file_stream_video["bitrate_target_size"] = "Right"
                        if file_stream_video["resolution_target_size"] == "Large" or \
                                file_stream_video["bitrate_target_size"] == "Large":
                            file_stream_video["target_size"] = "Large"
                        elif file_stream_video["resolution_target_size"] == "Small" or \
                                file_stream_video["bitrate_target_size"] == "Small":
                            file_stream_video["target_size"] = "Small"
                        else:
                            file_stream_video["target_size"] = "Right"
                file_probe_streams_filtered_audios = []
                file_probe_streams_filtered_audios_supplementary = []
                for file_probe_streams_filtered_audio in file_probe_streams_filtered["audio"]:
                    if file_probe_streams_filtered_audio["codec"] in {"AAC", "AC3", "EAC3"} and \
                            file_probe_streams_filtered_audio["lang"] == file_target_lang:
                        file_probe_streams_filtered_audios.append(file_probe_streams_filtered_audio)
                    else:
                        file_probe_streams_filtered_audios_supplementary \
                            .append(file_probe_streams_filtered_audio)
                if len(file_probe_streams_filtered_audios) == 0:
                    file_probe_streams_filtered_audios_supplementary = []
                    for file_probe_streams_filtered_audio in file_probe_streams_filtered["audio"]:
                        if file_probe_streams_filtered_audio["lang"] == file_target_lang:
                            file_probe_streams_filtered_audios.append(file_probe_streams_filtered_audio)
                        else:
                            file_probe_streams_filtered_audios_supplementary \
                                .append(file_probe_streams_filtered_audio)

                def _audio_sort(_stream):
                    return _stream["channels"].zfill(2) + ("Z" if _stream["surround"] == "Atmos" else "A")

                file_probe_streams_filtered_audios.sort(key=_audio_sort, reverse=True)
                file_probe_streams_filtered_audios_supplementary.sort(key=_audio_sort, reverse=True)
                if len(file_probe_streams_filtered_audios) > 0 and \
                        file_probe_streams_filtered_audios[0]["channels"] < file_target_channels:
                    if len(file_probe_streams_filtered_audios_supplementary) > 0 and \
                            file_probe_streams_filtered_audios_supplementary[0]["lang"] == file_target_lang and \
                            file_probe_streams_filtered_audios_supplementary[0]["channels"] >= file_target_channels:
                        file_probe_streams_filtered_audios.insert(
                            0, file_probe_streams_filtered_audios_supplementary.pop(0))
                file_probe_streams_filtered_audios.extend(file_probe_streams_filtered_audios_supplementary)
                file_probe_streams_filtered["audio"] = file_probe_streams_filtered_audios
                file_probe_streams_filtered_subtitles = []
                file_probe_streams_filtered_subtitles_supplementary = []
                for file_probe_streams_filtered_subtitle in file_probe_streams_filtered["subtitle"]:
                    if file_probe_streams_filtered_subtitle["format"] == "Text" and \
                            file_probe_streams_filtered_subtitle["lang"] == "eng":
                        file_probe_streams_filtered_subtitles.append(file_probe_streams_filtered_subtitle)
                    else:
                        file_probe_streams_filtered_subtitles_supplementary \
                            .append(file_probe_streams_filtered_subtitle)
                file_probe_streams_filtered_subtitles.sort(key=lambda _stream: _stream["index"], reverse=True)
                file_probe_streams_filtered_subtitles_supplementary.sort(
                    key=lambda _stream: _stream["index"], reverse=True)
                file_probe_streams_filtered_subtitles.extend(file_probe_streams_filtered_subtitles_supplementary)
                file_probe_streams_filtered["subtitle"] = file_probe_streams_filtered_subtitles
                file_probe_filtered = [
                    {"file_name": file_name},
                    {"transcode_action": file_transcode_action},
                    {"target_quality": file_target_quality},
                    {"target_video": file_target_video},
                    {"target_audios": file_target_audios},
                    {"target_subtitles": file_target_subtitles},
                    {"target_channels": file_target_channels},
                    {"target_lang": file_target_lang},
                    {"native_lang": file_native_lang},
                    {"media_directory": _delocalise_path(file_path_media, file_path_root, True)},
                    {"media_scope": file_media_scope},
                    {"media_type": file_media_type},
                    {"base_directory": file_base_dir},
                    {"version_directory": file_version_dir},
                    {"version_qualifier": file_version_qualifier},
                    {"file_directory": " '{}' ".format(_delocalise_path(file_dir_path, file_path_root, True, True))},
                    {"file_stem": " '{}' ".format(_escape_path(file_stem, True))},
                    {"file_extension": file_extension},
                    {"rename_directory": " '{}' ".format(_escape_path(file_dir_rename, True))},
                    {"rename_file": " '{}' ".format(_escape_path(file_name_rename, True))},
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
                    if file_probe_stream_type in {"audio", "subtitle"}:
                        file_probe_filtered.append({
                            "{}_non-eng_count".format(file_probe_stream_type):
                                str(sum(audio["lang"] != "eng" for audio in \
                                        file_probe_streams_filtered[file_probe_stream_type]))
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
                metadata_files_written.add(file_metadata_path)
            with open(file_metadata_path, 'r') as file_metadata:
                try:
                    metadata = _flatten_dicts(_unwrap_lists(yaml.safe_load(file_metadata)))
                    metadata["metadata_loaded"] = str(file_metadata_path in metadata_files_written)
                    metadata_list.append(metadata)
                    if verbose:
                        if file_metadata_path in metadata_files_written:
                            print("wrote metadata file", flush=True)
                        else:
                            print("loaded metadata file", flush=True)
                except Exception as exception:
                    _print_message(_message="skipping file due to metadata file load error [{}]".format(exception),
                                   _context=file_path, _no_header_footer=verbose)
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
            .rename(lambda column:
                    ((column.split("__")[0].replace("_", " ").title() + " (" + column.split("__")[1] + ")")
                     if len(column.split("__")) == 2 else column.replace("_", " ").title()) \
                        if "_" in column else column)

    if verbose:
        print("{}/*/._metadata_* -> #local-dataframe ... " \
              .format(file_path_root_target_relative), end='', flush=True)
    metadata_enriched_list = []
    metadata_enriched_schema = {}
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
        _add_field("file_validity", "")
        _add_field("file_action", "")
        metadata.move_to_end("file_name", last=False)
        metadata_enriched_list.append(dict(metadata))
        metadata_enriched_schema.update(metadata)
    metadata_enriched_schema = {_col: pl.String for _col in metadata_enriched_schema}
    metadata_local_pl = _format_columns(
        pl.DataFrame(metadata_enriched_list, metadata_enriched_schema, nan_to_null=True))
    if verbose:
        print("done", flush=True)
    if "Media Directory" not in metadata_local_pl.schema:
        metadata_local_pl = pl.DataFrame()
    metadata_local_media_dirs = []
    if metadata_local_pl.width > 0:
        metadata_local_media_dirs = \
            [_dir[0] for _dir in metadata_local_pl.select("Media Directory").unique().rows()]
    if verbose:
        print("#local-dataframe partition {} ... done".format(metadata_local_media_dirs), flush=True)
    if file_path_root_is_nested:
        metadata_merged_pl = metadata_local_pl
    else:
        if verbose:
            print("#local-dataframe + {} -> #merged-dataframe ... ".format(sheet_url), end='', flush=True)
        metadata_spread_data: Spread = Spread(sheet_url, sheet="Data")
        # noinspection PyProtectedMember
        metadata_sheet_list = metadata_spread_data \
            ._fix_merge_values(metadata_spread_data.sheet.get_all_values())
        if len(metadata_sheet_list) > 0:
            metadata_sheet_pl = _format_columns(pl.DataFrame(
                data=metadata_sheet_list[1:],
                schema={_col: pl.String for _col in metadata_sheet_list[0]},
                orient="row",
                nan_to_null=True,
            ))
        else:
            metadata_sheet_pl = pl.DataFrame()
        if metadata_sheet_pl.width > 0 and "Media Directory" not in metadata_sheet_pl.schema:
            _truncate_sheet(sheet_url)
            metadata_sheet_pl = pl.DataFrame()
        if metadata_local_pl.width > 0:
            if metadata_sheet_pl.width > 0:
                metadata_sheet_pl = metadata_sheet_pl.filter(
                    ~pl.col("Media Directory").is_in(metadata_local_media_dirs))
                metadata_merged_pl = \
                    pl.concat([metadata_sheet_pl, metadata_local_pl], how="diagonal_relaxed")
            else:
                metadata_merged_pl = metadata_local_pl
        else:
            metadata_merged_pl = pl.DataFrame()
        if verbose:
            print("done", flush=True)
    if verbose:
        print("#merged-dataframe -> #enriched-dataframe ... ", end='', flush=True)

    def _add_columns(_data, _columns, _default=None):
        if metadata_merged_pl.width > 0:
            for _column in _columns:
                if _column not in _data.schema:
                    _data = _data.with_columns(pl.lit(_default).cast(pl.String).alias(_column))
        return _data

    metadata_merged_pl = _format_columns(_add_columns(metadata_merged_pl, {
        "Version Directory",
        "Version Qualifier",
        "Metadata Loaded",
        "Video 1 Index",
        "Video 1 Codec",
        "Video 1 Colour Range",
        "Video 1 Width",
        "Video 1 Resolution",
        "Video 1 Resolution Target",
        "Video 1 Resolution Target Size",
        "Video 1 Bitrate Estimate (Kbps)",
        "Video 1 Bitrate Target (Kbps)",
        "Video 1 Bitrate Target Size",
        "Video 1 Target Size",
        "Audio 1 Index",
        "Audio 1 Index Audio",
        "Audio 1 Codec",
        "Audio 1 Lang",
        "Audio 1 Channels",
        "Audio 1 Surround",
        "Audio 1 Bitrate (Kbps)",
        "Subtitle 1 Lang",
        "Subtitle 1 Codec",
        "Subtitle 1 Format",
    }))
    if metadata_merged_pl.height > 0:
        try:
            metadata_merged_pl = metadata_merged_pl.with_columns(
                (
                    pl.when(
                        (pl.col("File Name").is_null()) |
                        (pl.col("File Name") == "") |
                        (pl.col("File Directory").is_null()) |
                        (pl.col("File Directory") == "") |
                        (pl.col("File Stem").is_null()) |
                        (pl.col("File Stem") == "") |
                        (pl.col("File Extension").is_null()) |
                        (pl.col("File Extension") == "") |
                        (pl.col("Media Scope").is_null()) |
                        (pl.col("Media Scope") == "") |
                        (pl.col("Media Type").is_null()) |
                        (pl.col("Media Type") == "") |
                        (pl.col("Media Directory").is_null()) |
                        (pl.col("Media Directory") == "") |
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
                        (pl.col("Transcode Action").is_null()) |
                        (pl.col("Transcode Action") == "") |
                        (pl.col("Target Quality").is_null()) |
                        (pl.col("Target Quality") == "") |
                        (pl.col("Target Channels").is_null()) |
                        (pl.col("Target Channels") == "") |
                        (pl.col("Target Lang").is_null()) |
                        (pl.col("Target Lang") == "") |
                        (pl.col("Native Lang").is_null()) |
                        (pl.col("Native Lang") == "") |
                        (pl.col("Stream Count").is_null()) |
                        (pl.col("Stream Count") == "") |
                        (pl.col("Video Count").is_null()) |
                        (pl.col("Video Count") == "") |
                        (pl.col("Video 1 Bitrate Estimate (Kbps)").is_null()) |
                        (pl.col("Video 1 Bitrate Estimate (Kbps)") == "") |
                        (pl.col("Audio Count").is_null()) |
                        (pl.col("Audio Count") == "")
                    ).then(pl.lit("Corrupt"))
                ).alias("File State"))
        except ColumnNotFoundError:
            metadata_merged_pl = metadata_merged_pl.with_columns(pl.lit("Corrupt").alias("File State"))
        metadata_merged_pl = metadata_merged_pl.with_columns(
            (
                pl.when(
                    (pl.col("File Name").str.contains(TOKEN_TRANSCODE)) |
                    (pl.col("Version Directory").str.starts_with("Plex Versions"))
                ).then(pl.lit("Transcoded"))
                .when(
                    (pl.col("Transcode Action") == "Merged")
                ).then(pl.lit("Merged"))
                .otherwise(pl.lit("Original"))
            ).alias("File Version"))
        metadata_merged_pl = metadata_merged_pl.with_columns(
            pl.col("File Stem").count().over("File Stem").alias("Version Count")
        )
        metadata_merged_pl = metadata_merged_pl.with_columns(
            (
                pl.when(
                    (pl.col("File State") == "Corrupt")
                ).then(pl.lit("Corrupt"))
                .when(
                    (pl.col("Stream Count") == "0") |
                    (pl.col("Video Count") == "0") |
                    (pl.col("Audio Count") == "0")
                ).then(pl.lit("Incomplete"))
                .otherwise(pl.lit("Complete"))
            ).alias("File State"))
        metadata_merged_pl = metadata_merged_pl.with_columns(
            pl.col("Video 1 Target Size").alias("File Size")
        )
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
                    (
                            (pl.col("Target Lang") == "eng") &
                            (pl.col("Native Lang") == "eng") &
                            (pl.col("Audio Non-Eng Count").cast(pl.Int32) > 0)
                    ) |
                    (
                            (
                                    (pl.col("Target Lang") != "eng") |
                                    (pl.col("Native Lang") != "eng")
                            ) &
                            (pl.col("Audio Non-Eng Count").cast(pl.Int32) > 1)
                    )
                ).then(pl.lit("Messy"))
                .when(
                    (pl.col("Subtitle Non-Eng Count").cast(pl.Int32) > 0)
                ).then(pl.lit("Messy"))
                .when(
                    (pl.col("Other Count").cast(pl.Int32) > 0)
                ).then(pl.lit("Messy"))
                .otherwise(pl.lit("Clean"))
            ).alias("Metadata State"))
        metadata_merged_pl = metadata_merged_pl.with_columns(
            (
                #
                # Rename
                #
                pl.when(
                    (pl.col("Rename File") != "") &
                    (pl.col("Rename File") != " '' ")
                ).then(pl.lit("Rename File"))
                .when(
                    (pl.col("Rename Directory") != "") &
                    (pl.col("Rename Directory") != " '' ")
                ).then(pl.lit("Rename Directory"))
                #
                # Check
                #
                .when(
                    (pl.col("File State") == "Corrupt")
                ).then(pl.lit("Check Corrupt Metadata"))
                .when(
                    (pl.col("File State") == "Incomplete")
                ).then(pl.lit("Check Missing Streams"))
                .when(
                    (pl.col("Target Lang") != pl.col("Audio 1 Lang"))
                ).then(pl.lit("Check Missing Target Language"))
                .when(
                    (pl.col("Target Lang") != "eng") &
                    (
                            (pl.col("Subtitle Count") == "0") |
                            (pl.col("Subtitle Count") == "Subtitle Non-Eng Count")
                    )
                ).then(pl.lit("Check Missing Subtitles"))
                .when(
                    (pl.col("File Version") == "Transcoded") &
                    (pl.col("Video 1 Resolution Target Size") == "Small")
                ).then(pl.lit("Check Low Video Resolution"))
                .when(
                    (pl.col("File Version") == "Transcoded") &
                    (pl.col("Video 1 Bitrate Target Size") == "Small")
                ).then(pl.lit("Check Low Video Bitrate"))
                .when(
                    (pl.col("File Version") == "Transcoded") &
                    (pl.col("File Size") == "Small")
                ).then(pl.lit("Check Small Size"))
                .when(
                    (pl.col("File Version") == "Transcoded") &
                    (pl.col("Audio 1 Channels") < pl.col("Target Channels"))
                ).then(pl.lit("Check Missing Audio Channels"))
                .when(
                    (pl.col("File Version") == "Transcoded") &
                    (pl.col("Target Quality") == "9") &
                    (pl.col("Audio 1 Bitrate (Kbps)") != "") &
                    (pl.col("Audio 1 Bitrate (Kbps)").cast(pl.Int32) <= 640000)
                ).then(pl.lit("Check Low Audio Bitrate"))
                .when(
                    (pl.col("File Version") == "Transcoded") &
                    (pl.col("Video 1 Colour Range") == "HDR")
                ).then(pl.lit("Check HDR Colouring"))
                .when(
                    ((pl.col("File Version") == "Original") | (pl.col("File Version") == "Merged")) &
                    (~pl.col("File Stem").str.contains(".", literal=True)) &
                    (pl.struct(
                        pl.col("Version Directory"),
                        pl.col("File Name")
                        .str.replace_all(MEDIA_YEAR_NUMBER_REGEXP, "")
                        .str.to_lowercase()
                        .str.split(".").list.first()
                        .str.strip_chars()
                    ).is_duplicated())
                ).then(pl.lit("Check Duplicate"))
                .when(
                    (pl.col("File Version") == "Transcoded") &
                    (pl.col("Version Directory") == ".") &
                    (~pl.col("File Stem").is_null()) & (pl.col("File Stem") != "") &
                    (~pl.col("Duration (hours)").is_null()) & (pl.col("Duration (hours)") != "") &
                    (pl.col("File Stem").is_duplicated()) &
                    (~pl.struct(
                        pl.col("File Stem"),
                        (pl.col("Duration (hours)").cast(pl.Float32) * 60 * 6).round(0),
                    ).is_duplicated())
                ).then(pl.lit("Check Suspect Duration"))
                #
                # Reformat
                #
                .when(
                    (pl.col("Video Count").cast(pl.Int32) > 1)
                ).then(pl.lit("Reformat Multiple Video Streams"))
                #
                # Transcode
                #
                .when(
                    (pl.col("Plex Video") == "Transcode")
                ).then(pl.lit("Transcode Video"))
                .when(
                    (pl.col("Plex Audio") == "Transcode")
                ).then(pl.lit("Transcode Audio"))
                .when(
                    (pl.col("Duration (hours)").is_null())
                ).then(pl.lit("Transcode Null Duration"))
                .when(
                    (pl.col("Bitrate (Kbps)").is_null())
                ).then(pl.lit("Transcode Null Bitrate"))
                #
                # Downscale
                #
                .when(
                    (pl.col("Video 1 Resolution Target Size") == "Large")
                ).then(pl.lit("Downscale High Video Resolution"))
                .when(
                    (pl.col("Video 1 Bitrate Target Size") == "Large")
                ).then(pl.lit("Downscale High Video Bitrate"))
                .when(
                    (pl.col("File Size") == "Large")
                ).then(pl.lit("Downscale High Size"))
                #
                # Reformat
                #
                .when(
                    (pl.col("Metadata State") == "Messy")
                ).then(pl.lit("Reformat Messy Metadata"))
                #
                # Upscale
                #
                .when(
                    (pl.col("Video 1 Resolution Target Size") == "Small")
                ).then(pl.lit("Upscale Low Video Resolution"))
                .when(
                    (pl.col("Video 1 Bitrate Target Size") == "Small")
                ).then(pl.lit("Upscale Low Video Bitrate"))
                .when(
                    (pl.col("File Size") == "Small")
                ).then(pl.lit("Upscale Small Size"))
                .when(
                    (pl.col("Audio 1 Channels") < pl.col("Target Channels"))
                ).then(pl.lit("Upscale Missing Audio Channels"))
                .when(
                    (pl.col("Target Quality") == "9") &
                    (pl.col("Audio 1 Bitrate (Kbps)") != "") &
                    (pl.col("Audio 1 Bitrate (Kbps)").cast(pl.Int32) <= 640000)
                ).then(pl.lit("Upscale Low Audio Bitrate"))
                .otherwise(pl.lit("Valid Consistent State"))
            ).alias("File Validity"))
        metadata_merged_pl = metadata_merged_pl.with_columns(
            (
                pl.when(
                    (pl.col("File Validity").str.starts_with("Rename"))
                ).then(pl.lit(FileAction.RENAME.label))
                .when(
                    (not force) &
                    (pl.col("File Validity").str.starts_with("Check"))
                ).then(pl.lit(FileAction.CHECK.label))
                .when(
                    (pl.col("File Version") == "Transcoded")
                ).then(pl.lit(FileAction.MERGE.label))
                .when(
                    (pl.col("Transcode Action") != "Ignore") &
                    (pl.col("File Validity").str.starts_with("Transcode"))
                ).then(pl.lit(FileAction.TRANSCODE.label))
                .when(
                    (pl.col("Transcode Action") != "Ignore") &
                    (pl.col("File Validity").str.starts_with("Downscale"))
                ).then(pl.lit(FileAction.DOWNSCALE.label))
                .when(
                    (pl.col("Transcode Action") != "Ignore") &
                    (pl.col("File Validity").str.starts_with("Reformat"))
                ).then(pl.lit(FileAction.REFORMAT.label))
                .when(
                    (pl.col("Transcode Action") != "Ignore") &
                    (pl.col("File Validity").str.starts_with("Upscale"))
                ).then(pl.lit(FileAction.UPSCALE.label))
                .otherwise(pl.lit(FileAction.NOTHING.label))
            ).alias("File Action"))
        metadata_merged_pl = pl.concat([
            metadata_merged_pl.filter(
                (pl.col("File Action") == FileAction.RENAME.label) |
                (pl.col("File Action") == FileAction.CHECK.label) |
                (pl.col("File Action") == FileAction.UPSCALE.label)
            ).sort("File Validity", descending=True).with_columns(
                pl.col("File Name").cum_count().cast(pl.Float32).alias("Action Index Sort")
            ),
            metadata_merged_pl.filter(
                (pl.col("File Action") == FileAction.REFORMAT.label) |
                (pl.col("File Action") == FileAction.TRANSCODE.label) |
                (pl.col("File Action") == FileAction.DOWNSCALE.label)
            ).with_columns(
                pl.col("File Size (GB)").cast(pl.Float32).alias("Action Index Sort")
            ),
            metadata_merged_pl.filter(
                (pl.col("File Action") != FileAction.RENAME.label) &
                (pl.col("File Action") != FileAction.CHECK.label) &
                (pl.col("File Action") != FileAction.UPSCALE.label) &
                (pl.col("File Action") != FileAction.REFORMAT.label) &
                (pl.col("File Action") != FileAction.TRANSCODE.label) &
                (pl.col("File Action") != FileAction.DOWNSCALE.label)
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
    if verbose:
        print("done", flush=True)
    if metadata_merged_pl.height > 0:
        metadata_scripts_pl = metadata_merged_pl.filter(
            (pl.col("Media Directory").is_in(metadata_local_media_dirs))
        ).with_columns(
            [
                pl.concat_str([
                    pl.col("File Name") \
                        .str.replace_all("`", "\\`")
                        .str.replace_all("$", "\\$", literal=True)
                ]).alias("File Name"),
                pl.concat_str([
                    pl.col("Base Directory") \
                        .str.replace_all("`", "\\`")
                        .str.replace_all("$", "\\$", literal=True)
                ]).alias("Base Directory"),
                pl.concat_str([
                    pl.col("File Directory") \
                        .str.strip_prefix(" '") \
                        .str.strip_suffix("' ") \
                        .str.replace_all("'\\\\''", "'")
                        .str.replace_all("`", "\\`")
                        .str.replace_all("$", "\\$", literal=True)
                ]).alias("File Directory"),
                pl.concat_str([
                    pl.col("File Stem") \
                        .str.strip_prefix(" '") \
                        .str.strip_suffix("' ") \
                        .str.replace_all("'\\\\''", "'")
                        .str.replace_all("`", "\\`")
                        .str.replace_all("$", "\\$", literal=True)
                ]).alias("File Stem"),
                pl.concat_str([
                    pl.col("Rename File") \
                        .str.strip_prefix(" '") \
                        .str.strip_suffix("' ") \
                        .str.replace_all("'\\\\''", "'")
                        .str.replace_all("`", "\\`")
                        .str.replace_all("$", "\\$", literal=True)
                ]).alias("Rename File"),
                pl.concat_str([
                    pl.col("Rename Directory") \
                        .str.strip_prefix(" '") \
                        .str.strip_suffix("' ") \
                        .str.replace_all("'\\\\''", "'")
                        .str.replace_all("`", "\\`")
                        .str.replace_all("$", "\\$", literal=True)
                ]).alias("Rename Directory"),
            ]
        ).with_columns(
            [
                (
                    pl.col("File Directory").map_elements(
                        lambda _dir: _localise_path(_dir, file_path_root), return_dtype=pl.String)
                ).alias("File Directory Local"),
                pl.concat_str([
                    pl.col("File Directory"),
                    pl.lit("/._transcode_"),
                    pl.col("File Stem"),
                ]).alias("Transcode Script Directory"),
                pl.concat_str([
                    pl.col("File Directory"),
                    pl.lit("/._reformat_"),
                    pl.col("File Stem"),
                ]).alias("Reformat Script Directory"),
                pl.concat_str([
                    pl.col("File Directory"),
                    pl.lit("/._rename_"),
                    pl.col("File Stem"),
                ]).alias("Rename Script Directory"),
                pl.concat_str([
                    pl.col("File Directory"),
                    pl.lit("/._downscale_"),
                    pl.col("File Stem"),
                ]).alias("Downscale Script Directory"),
                pl.concat_str([
                    pl.col("File Directory"),
                    pl.lit("/._merge_"),
                    pl.col("File Stem"),
                ]).alias("Merge Script Directory"),
                pl.concat_str([
                    pl.col("File Directory"),
                    pl.lit("/._check_"),
                    pl.col("File Stem"),
                ]).alias("Check Script Directory"),
                pl.concat_str([
                    pl.col("File Directory"),
                    pl.lit("/._upscale_"),
                    pl.col("File Stem"),
                ]).alias("Upscale Script Directory"),
                pl.concat_str([
                    pl.col("File Stem"),
                    pl.lit(TOKEN_TRANSCODE + "_"),
                    pl.col("Target Quality").str.to_uppercase(),
                    pl.lit(".mkv"),
                ]).alias("Transcode File Name"),
            ]
        ).with_columns(
            [
                pl.concat_str([
                    pl.col("Transcode Script Directory"),
                    pl.lit("/transcode.sh"),
                ]).alias("Transcode Script File"),
                pl.concat_str([
                    pl.col("Reformat Script Directory"),
                    pl.lit("/reformat.sh"),
                ]).alias("Reformat Script File"),
                pl.concat_str([
                    pl.col("Rename Script Directory"),
                    pl.lit("/rename.sh"),
                ]).alias("Rename Script File"),
                pl.concat_str([
                    pl.col("Downscale Script Directory"),
                    pl.lit("/downscale.sh"),
                ]).alias("Downscale Script File"),
                pl.concat_str([
                    pl.col("Merge Script Directory"),
                    pl.lit("/merge.sh"),
                ]).alias("Merge Script File"),
                pl.concat_str([
                    pl.col("Check Script Directory"),
                    pl.lit("/check.sh"),
                ]).alias("Check Script File"),
                pl.concat_str([
                    pl.col("Upscale Script Directory"),
                    pl.lit("/upscale.sh"),
                ]).alias("Upscale Script File"),
            ]
        ).with_columns(
            [
                (
                    pl.when(
                        (pl.col("Video 1 Codec") != "HEVC")
                    ).then(
                        (pl.col("Video 1 Bitrate Target (Kbps)").cast(pl.Int32) /
                         pl.lit(BITRATE_HVEC_SCALE)).cast(pl.Int32)
                    ).otherwise(
                        pl.col("Video 1 Bitrate Target (Kbps)")
                    )
                ).alias("Transcode Video Bitrate")
            ]
        ).with_columns(
            [
                (
                    pl.when(
                        (pl.col("Target Quality").cast(pl.Int32) <= QUALITY_MIN)
                    ).then(
                        pl.lit("720p")
                    ).when(
                        (pl.col("Target Quality").cast(pl.Int32) <= QUALITY_MID)
                    ).then(
                        pl.lit("1080p")
                    ).otherwise(
                        pl.lit("")
                    )
                ).alias("Transcode Video Resolution"),
                (
                    pl.when(
                        (pl.col("Target Quality").cast(pl.Int32) <= QUALITY_MIN)
                    ).then(
                        pl.concat_str([pl.lit("--hevc --720p --target "), pl.col("Transcode Video Bitrate"), ])
                    ).when(
                        (pl.col("Target Quality").cast(pl.Int32) <= QUALITY_MID)
                    ).then(
                        pl.concat_str([pl.lit("--hevc --1080p --target "), pl.col("Transcode Video Bitrate"), ])
                    ).otherwise(
                        pl.concat_str([pl.lit("--hevc --target "), pl.col("Transcode Video Bitrate"), ])
                    )
                ).alias("Transcode Video"),
                (
                    pl.col("Audio 1 Index Audio")
                ).alias("Transcode Audio Index"),
            ]
        ).with_columns(
            [
                (
                    pl.when(
                        (pl.col("Target Lang") == "eng") &
                        (pl.col("Native Lang") == "eng")
                    ).then(
                        pl.concat_str([pl.lit("--main-audio "), pl.col("Transcode Audio Index")])
                    ).when(
                        (pl.col("Target Lang") == "eng") &
                        (pl.col("Native Lang") != "eng")
                    ).then(
                        pl.concat_str([
                            pl.lit("--main-audio "), pl.col("Transcode Audio Index"),
                            pl.lit(" "), pl.lit("--add-audio "), pl.col("Target Lang")
                        ])
                    ).otherwise(
                        pl.concat_str([
                            pl.lit("--main-audio "), pl.col("Transcode Audio Index"),
                            pl.lit(" "), pl.lit("--add-audio eng")
                        ])
                    )
                ).alias("Transcode Audio"),
                (
                    pl.when(
                        (pl.col("Subtitle 1 Codec") == "MOV_TEXT")
                    ).then(
                        pl.lit(";")
                    ).otherwise(
                        pl.lit("--add-subtitle eng")
                    )
                ).alias("Transcode Subtitle")
            ]
        ).with_columns(
            [
                (
                    pl.when(
                        (pl.col("Audio 1 Surround") == "Atmos")
                    ).then(
                        pl.concat_str([pl.col("Transcode Audio"), pl.lit(" --eac3")])
                    ).otherwise(
                        pl.concat_str([pl.col("Transcode Audio"), pl.lit(" --eac3")])
                    )
                ).alias("Transcode Audio")
            ]
        ).with_columns(
            [
                pl.concat_str([
                    pl.lit("#!/usr/bin/env bash\n\n"),
                    pl.lit("ROOT_DIR=$(dirname \"$(readlink -f \"$0\")\")\n"),
                    pl.lit("ROOT_DIR_BASE=\"$(realpath \"${ROOT_DIR}/../\")\"\n"),
                    pl.lit("ROOT_DIR_LOCAL=\""), pl.col("File Directory Local").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("ROOT_FILE_NAME=\""), pl.col("File Name").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("ROOT_FILE_STEM=\""), pl.col("File Stem").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n\n"),
                    pl.lit(BASH_EXIT_HANDLER.format("  echo 'Killing Rename!'\n")),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("echo \"Renaming: '${ROOT_FILE_NAME}' @ '${ROOT_DIR_LOCAL}'\"\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("BASE_DIR=\""), pl.col("Base Directory").str.replace_all("\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("BASE_DIR=(\"${BASE_DIR// /_____}\")\n"),
                    pl.lit("BASE_DIR=(${BASE_DIR//\\// })\n"),
                    pl.lit("BASE_DIR=(\"${BASE_DIR//_____/ }\")\n"),
                    pl.lit("NEW_DIR=\""), pl.col("Media Directory"), pl.lit("/\"\\\n"),
                    pl.lit("\""), pl.col("Media Scope"), pl.lit("/"), pl.col("Media Type"), pl.lit("\"\n"),
                    pl.lit("NEW_DIR=\"${ROOT_DIR%%${NEW_DIR}*}${NEW_DIR}\"\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._metadata_\"*.yaml\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._defaults_analysed_\"*.yaml\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}\"/._*/*.sh\n"),
                    pl.lit("RENAME_DIR=\""), pl.col("Rename Directory").str.replace_all("\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("RENAME_FILE=\""), pl.col("Rename File").str.replace_all("\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("if [ \"${RENAME_DIR}\" != \"\" ]; then\n"),
                    pl.lit("  echo 'Renaming of directory must be validated and executed manually:' && echo ''\n"),
                    pl.lit("  if [ \"${RENAME_DIR}\" != \"" + TOKEN_UNKNOWABLE + "\" ]; then\n"),
                    pl.lit("    echo cd \\\'\"${NEW_DIR}\"\\\'\n"),
                    pl.lit("    echo [[ ! -d \\\'\"${RENAME_DIR}\"\\\' ]] \\&\\& \\\n"),
                    pl.lit("       mv -v \\\'\"${BASE_DIR}\"\\\' \\\'\"${RENAME_DIR}\"\\\' \n"),
                    pl.lit("  else\n"),
                    pl.lit("    echo cd \"$(realpath \"${ROOT_DIR}/../\")\"\n"),
                    pl.lit("  fi\n"),
                    pl.lit("  echo '' && echo -n 'Skipped (not-executed): ' && date\n"),
                    pl.lit("fi\n"),
                    pl.lit("if [ \"${RENAME_FILE}\" != \"\" ]; then\n"),
                    pl.lit("  ORIG_FILE=\"${ROOT_DIR_BASE}/${ROOT_FILE_NAME}\"\n"),
                    pl.lit("  NEW_FILE=\"${ROOT_DIR_BASE}/${RENAME_FILE}\"\n"),
                    pl.lit("  echo '' && echo \\\n"),
                    pl.lit("     \"./$(realpath --relative-to=\"${ROOT_DIR}/../../../..\" \"${ORIG_FILE}\") ->\" \\\n"),
                    pl.lit("     \"./$(realpath --relative-to=\"${ROOT_DIR}/../../../..\" \"${NEW_FILE}\")\"\n"),
                    pl.lit("  if [ ! -f \"${NEW_FILE}\" ]; then\n"),
                    pl.lit("    mv \"${ORIG_FILE}\" \"${NEW_FILE}\"\n"),
                    pl.lit("    if [ $? -eq 0 ]; then\n"),
                    pl.lit("      echo '' && echo -n 'Completed: ' && date && exit 0\n"),
                    pl.lit("    else\n"),
                    pl.lit("      echo '' && echo -n 'Failed (mv): ' && date && exit 1\n"),
                    pl.lit("    fi\n"),
                    pl.lit("  else\n"),
                    pl.lit("    echo '' && echo -n 'Skipped (pre-existing): ' && date && exit 0\n"),
                    pl.lit("  fi\n"),
                    pl.lit("fi\n"),
                    pl.lit("echo '' && exit 0\n"),
                ]).alias("Rename Script Source"),
                pl.concat_str([
                    pl.lit("#!/usr/bin/env bash\n\n"),
                    pl.lit("ROOT_DIR=$(dirname \"$(readlink -f \"$0\")\")\n"),
                    pl.lit("ROOT_DIR_BASE=\"$(realpath \"${ROOT_DIR}/../\")\"\n"),
                    pl.lit("ROOT_DIR_LOCAL=\""), pl.col("File Directory Local").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("ROOT_FILE_NAME=\""), pl.col("File Name").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("ROOT_FILE_STEM=\""), pl.col("File Stem").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n\n"),
                    pl.lit(BASH_EXIT_HANDLER.format("  echo 'Killing Merge!'\n")),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("echo \"Merging: '${ROOT_FILE_NAME}' @ '${ROOT_DIR_LOCAL}'\"\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("if [[ ${ROOT_DIR} == *\"/Plex Versions/\"* ]]; then\n"),
                    pl.lit("  ORIG_DIR=\"$(realpath \"${ROOT_DIR}/../../../..\")\"\n"),
                    pl.lit("else\n"),
                    pl.lit("  ORIG_DIR=\"$(realpath \"${ROOT_DIR}/..\")\"\n"),
                    pl.lit("fi\n"),
                    pl.lit("ORIG_FILE_META=\"$(find \"${ORIG_DIR}\" " +
                           "-name \"._metadata_${ROOT_FILE_STEM%.*}_*.yaml\" ! -name '*" + TOKEN_TRANSCODE + "_*')\"\n"),
                    pl.lit("TRAN_FILE_META=\"$(find \"${ROOT_DIR_BASE}\" " +
                           "-name \"._metadata_${ROOT_FILE_NAME%.*}*.yaml\")\"\n"),
                    pl.lit("CHECK_REQUIRED=\"\"\n"),
                    pl.lit("if [ \"" + str(force) + "\" != \"True\" ]; then\n"),
                    pl.lit("  if [ \"${ORIG_FILE_META}\" == \"\" ] || [ ! -f \"${ORIG_FILE_META}\" ]; then \n"),
                    pl.lit("    CHECK_REQUIRED=\"original-metadata-file-not-found\"\n"),
                    pl.lit("  elif [ \"${TRAN_FILE_META}\" == \"\" ] || [ ! -f \"${TRAN_FILE_META}\" ]; then \n"),
                    pl.lit("    CHECK_REQUIRED=\"transcoded-metadata-file-not-found\"\n"),
                    pl.lit("  fi\n"),
                    pl.lit("fi\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._metadata_${ROOT_FILE_STEM}\"*.yaml\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._defaults_analysed_${ROOT_FILE_STEM}\"*.yaml\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._\"*\"_${ROOT_FILE_STEM}\"/*.sh\n"),
                    pl.lit("if [ $(find \"${ORIG_DIR}\" ! -name *." +
                           " ! -name *.".join(MEDIA_FILE_EXTENSIONS_IGNORE) +
                           " -type f -name \"${ROOT_FILE_STEM}*\" | wc -l) -le 2 ] && " +
                           "[ $(find \"${ORIG_DIR}\" -name \"${ROOT_FILE_NAME}\" | wc -l) -eq 1 ]; then\n"),
                    pl.lit("  ORIG_FILE=\"$(find \"${ORIG_DIR}\" ! -name *." +
                           " ! -name *.".join(
                               MEDIA_FILE_EXTENSIONS_IGNORE) + " -type f -name \"${ROOT_FILE_STEM}\\.*\")\"\n"),
                    pl.lit("  TRAN_FILE=\"${ROOT_DIR}/../${ROOT_FILE_NAME}\"\n"),
                    pl.lit("  MERG_FILE=\"${ORIG_DIR}/${ROOT_FILE_STEM}.mkv\"\n"),
                    pl.lit("  if [ -f \"${ORIG_FILE}\" ] && [ -f \"${TRAN_FILE}\" ]; then\n"),
                    pl.lit("    if [ \"${CHECK_REQUIRED}\" != \"\" ]; then\n"),
                    pl.lit("      echo '' && echo -n \"Skipped (check-${CHECK_REQUIRED}): \" && date && exit 0\n"),
                    pl.lit("    fi\n"),
                    pl.lit("    echo ''\n"),
                    pl.lit("    ORIG_FILE_SIZE=$(du -m \"${ORIG_FILE}\" | "
                           "awk '{printf \"%.1f\", ($1/1024 + 0.05)}')\n"),
                    pl.lit("    TRAN_FILE_SIZE=$(du -m \"${TRAN_FILE}\" | "
                           "awk '{printf \"%.1f\", ($1/1024 + 0.05)}')\n"),
                    pl.lit("    rm -f \"${ORIG_FILE}\"\n"),
                    pl.lit("    mv -f \"${TRAN_FILE}\" \"${MERG_FILE}\"\n"),
                    pl.lit("    if [ $? -eq 0 ]; then\n"),
                    pl.lit("      TRAN_STEM=\"$(basename \"${TRAN_FILE}\")\"\n"),
                    pl.lit("      TRAN_DEFTS=\"$(dirname \"${TRAN_FILE}\")/"
                           "._defaults_analysed_${TRAN_STEM%.*}_${TRAN_STEM##*.}.yaml\"\n"),
                    pl.lit("      MERG_DEFTS=\"${ORIG_DIR}/._defaults_merged_${ROOT_FILE_STEM}_mkv.yaml\"\n"),
                    pl.lit("      if [ -f \"$TRAN_DEFTS\" ]; then\n"),
                    pl.lit("        mv -f \"$TRAN_DEFTS\" \"$MERG_DEFTS\"\n"),
                    pl.lit("      else\n"),
                    pl.lit("        touch \"$MERG_DEFTS\"\n"),
                    pl.lit("      fi\n"),
                    pl.lit("      echo \"./$(basename \"${TRAN_FILE}\") [${TRAN_FILE_SIZE} GB] " + \
                           "-> ./$(basename "), pl.lit("\"${ORIG_FILE}\")\" [${ORIG_FILE_SIZE} GB]\n"),
                    pl.lit("      echo '' && echo -n 'Completed: ' && date && exit 0\n"),
                    pl.lit("    else\n"),
                    pl.lit("      echo '' && echo -n 'Failed (mv): ' && date && exit 1\n"),
                    pl.lit("    fi\n"),
                    pl.lit("  else\n"),
                    pl.lit("    echo '' && echo -n 'Skipped (missing-files): ' && date && exit 0\n"),
                    pl.lit("  fi\n"),
                    pl.lit("else\n"),
                    pl.lit("  echo '' && echo -n 'Skipped (non-unique-files): ' && date && exit 0\n"),
                    pl.lit("fi\n"),
                    pl.lit("echo '' && echo -n 'Failed: ' && date && exit 2\n"),
                ]).alias("Merge Script Source"),
                pl.concat_str([
                    pl.lit("#!/usr/bin/env bash\n\n"),
                    pl.lit("ROOT_DIR=$(dirname \"$(readlink -f \"$0\")\")\n"),
                    pl.lit("ROOT_DIR_BASE=\"$(realpath \"${ROOT_DIR}/../\")\"\n"),
                    pl.lit("ROOT_DIR_LOCAL=\""), pl.col("File Directory Local").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("ROOT_FILE_NAME=\""), pl.col("File Name").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("ROOT_FILE_STEM=\""), pl.col("File Stem").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n\n"),
                    pl.lit(BASH_EXIT_HANDLER.format("  echo 'Killing Transcode!'\n  rm -f \"${ROOT_DIR}\"/*.mkv*\n")),
                    pl.lit("rm -f \"${ROOT_DIR}\"/*.mkv*\n\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("echo \"Transcoding: '${ROOT_FILE_NAME}' @ '${ROOT_DIR_LOCAL}'\"\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("ORIG_FILE_META=\"$(find \"${ROOT_DIR_BASE}\" " +
                           "-name \"._metadata_${ROOT_FILE_STEM%.*}_*.yaml\" ! -name '*" + TOKEN_TRANSCODE + "_*')\"\n"),
                    pl.lit("if [ \"${ORIG_FILE_META}\" == \"\" ]; then \n"),
                    pl.lit("  echo '' && echo 'Warning: Metadata file not found'&& exit 4\n"),
                    pl.lit("fi\n"),
                    pl.lit("echo -n 'Transcoding at ' && date\n"),
                    pl.lit("echo 'Transcoding with reason ["), pl.col("File Validity"), pl.lit("]'\n"),
                    pl.lit("echo 'Transcoding with quality ["), pl.col("Target Quality"), pl.lit("]'\n"),
                    pl.lit("echo 'Transcoding with codec [HVEC] from ['\"$(yq '.[].video? | select(.) | .[0].\"1\"[] | "
                           "select(.codec) | .codec' \"${ORIG_FILE_META}\" | sed \"s/['\\\"]//g\")\"']'\n"),
                    pl.lit("ORIG_RESOLUTION=\"$(yq '.[].video? | select(.) | .[0].\"1\"[] | "
                           "select(.resolution) | .resolution' \"${ORIG_FILE_META}\" | sed \"s/['\\\"]//g\")\"\n"),
                    pl.lit("if [ \""), pl.col("Transcode Video Resolution"), pl.lit("\" == \"\" ]; then\n"),
                    pl.lit("  TARGET_RESOLUTION=\"${ORIG_RESOLUTION}\"\n"),
                    pl.lit("else\n"),
                    pl.lit("  TARGET_RESOLUTION=\""), pl.col("Transcode Video Resolution"), pl.lit("\"\n"),
                    pl.lit("fi\n"),
                    pl.lit("echo \"Transcoding with resolution [${TARGET_RESOLUTION}] from [${ORIG_RESOLUTION}]\"\n"),
                    pl.lit("echo 'Transcoding with bitrate ["), pl.col("Transcode Video Bitrate"), pl.lit(
                        " Kbps] from ['\"$(yq '.[].video? | select(.) | .[0].\"1\"[] | "
                        "select(.bitrate_estimate__Kbps) | .bitrate_estimate__Kbps' \"${ORIG_FILE_META}\" | sed \"s/['\\\"]//g\")\" Kbps]\n"),
                    pl.lit("TRAN_FILE_NAME=\""), pl.col("Transcode File Name").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("if [ -f \"${ROOT_DIR}/../${TRAN_FILE_NAME}\" ]; then\n"),
                    pl.lit("  echo '' && echo -n 'Skipped (pre-existing): ' && date && echo '' && exit 0\n"),
                    pl.lit("fi\n"),
                    pl.lit("if [ $(df -k \"${ROOT_DIR}\" | tail -1 | awk '{print $4}') -lt 20000000 ]; then\n"),
                    pl.lit("  echo '' && echo -n 'Skipped (space): ' && date && echo '' && exit 1\n"),
                    pl.lit("fi\n"),
                    pl.lit("cd \"${ROOT_DIR}\"\n"),
                    pl.lit("if [ ! -f \"${ROOT_DIR}/../${ROOT_FILE_NAME}\" ]; then\n"),
                    pl.lit("  echo '' && echo -n 'Skipped (missing): ' && date && echo '' && exit 0\n"),
                    pl.lit("fi\n"),
                    pl.lit("if [[ $(hostname) == macmini* ]] && "
                           "[[ \"$(basename \"$0\")\" == \"transcode.sh\" ]] ; then\n"),
                    pl.lit("  echo '' && echo -n 'Skipped (poor-hardware): ' && date && echo '' && exit 0\n"),
                    pl.lit("fi\n"),
                    pl.lit("TRANSCODE_VIDEO='"), pl.col("Transcode Video"), pl.lit("'\n"),
                    pl.lit("[[ \"$(basename \"$0\")\" == \"reformat.sh\" ]] && TRANSCODE_VIDEO='--copy-video'\n"),
                    pl.lit("other-transcode \"${ROOT_DIR}/../${ROOT_FILE_NAME}\" \\\n"),
                    pl.lit("  ${TRANSCODE_VIDEO} \\\n"),
                    pl.lit("  "), pl.col("Transcode Audio"), pl.lit(" \\\n"),
                    pl.lit("  "), pl.col("Transcode Subtitle"), pl.lit("\n"),
                    pl.lit("if [ $? -eq 0 ]; then\n"),
                    pl.lit("  rm -f \"${ROOT_DIR}\"/*.mkv.log\n"),
                    pl.lit("  mv -f \"${ROOT_DIR}\"/*.mkv \"${ROOT_DIR}/../${TRAN_FILE_NAME}\"\n"),
                    pl.lit("  if [ $? -eq 0 ]; then\n"),
                    pl.lit("      echo \"./$(basename \"${ROOT_FILE_NAME}\")"),
                    pl.lit(" [$(du -m \"${ROOT_DIR}/../${ROOT_FILE_NAME}\" | "
                           "awk '{printf \"%.1f\", ($1/1024 + 0.05)}') GB] " + \
                           "-> ./$(basename "), pl.lit("\"${TRAN_FILE_NAME}\")\" " + \
                                                       "[$(du -m \"${ROOT_DIR}/../${TRAN_FILE_NAME}\" | "
                                                       "awk '{printf \"%.1f\", ($1/1024 + 0.05)}') GB]\n"),
                    pl.lit("    echo '' && echo -n 'Completed: ' && date && exit 0\n"),
                    pl.lit("  else\n"),
                    pl.lit("    echo -n 'Failed (mv): ' && date && exit 3\n"),
                    pl.lit("  fi\n"),
                    pl.lit("else\n"),
                    pl.lit("  echo -n 'Failed (other-transcode): ' && date && exit 2\n"),
                    pl.lit("fi\n"),
                    pl.lit("echo '' && exit -1\n"),
                ]).alias("Transcode Script Source"),
                pl.concat_str([
                    pl.lit("#!/usr/bin/env bash\n\n"),
                    pl.lit("ROOT_DIR=$(dirname \"$(readlink -f \"$0\")\")\n"),
                    pl.lit("ROOT_DIR_BASE=\"$(realpath \"${ROOT_DIR}/../\")\"\n"),
                    pl.lit("ROOT_DIR_LOCAL=\""), pl.col("File Directory Local").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("ROOT_FILE_NAME=\""), pl.col("File Name").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("ROOT_FILE_STEM=\""), pl.col("File Stem").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n\n"),
                    pl.lit(BASH_EXIT_HANDLER.format("  echo 'Killing Check!'\n  rm -f \"${ROOT_DIR}\"/*.mkv*\n")),
                    pl.lit("rm -f \"${ROOT_DIR}\"/*.mkv*\n\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("echo \"Checking: '${ROOT_FILE_NAME}' @ '${ROOT_DIR_LOCAL}'\"\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("FILE_META_NAME=\"._metadata_${ROOT_FILE_NAME%.*}_"
                           "$(basename \"${ROOT_FILE_NAME}\" | rev | cut -d. -f1 | rev).yaml\"\n"),
                    pl.lit("FILE_META=\"$(find \"${ROOT_DIR_BASE}\" -name \"${FILE_META_NAME}\")\"\n"),
                    pl.lit("if [ \"${FILE_META}\" == \"\" ]; then \n"),
                    pl.lit("  echo '' && echo 'Warning: Metadata file [${FILE_META_NAME}] not found'&& exit 1\n"),
                    pl.lit("fi\n"),
                    pl.lit("echo '' && echo \"Metadata file:\"\n"),
                    pl.lit("cat \"${FILE_META}\"\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._metadata_${ROOT_FILE_STEM}\"*.yaml\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._defaults_analysed_${ROOT_FILE_STEM}\"*.yaml\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._\"*\"_${ROOT_FILE_STEM}\"/*.sh\n"),
                    pl.lit("echo '' && echo \"File probe reported:"
                           " "), pl.col("File Validity"), pl.lit("\" && echo '' && exit 0\n"),
                ]).alias("Check Script Source"),
                pl.concat_str([
                    pl.lit("#!/usr/bin/env bash\n\n"),
                    pl.lit("ROOT_DIR=$(dirname \"$(readlink -f \"$0\")\")\n"),
                    pl.lit("ROOT_DIR_BASE=\"$(realpath \"${ROOT_DIR}/../\")\"\n"),
                    pl.lit("ROOT_DIR_LOCAL=\""), pl.col("File Directory Local").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("ROOT_FILE_NAME=\""), pl.col("File Name").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n"),
                    pl.lit("ROOT_FILE_STEM=\""), pl.col("File Stem").str.replace_all(
                        "\"", "\\\""), pl.lit("\"\n\n"),
                    pl.lit(BASH_EXIT_HANDLER.format("  echo 'Killing Upscale!'\n  rm -f \"${ROOT_DIR}\"/*.mkv*\n")),
                    pl.lit("rm -f \"${ROOT_DIR}\"/*.mkv*\n\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("echo \"Upscaling: '${ROOT_FILE_NAME}' @ '${ROOT_DIR_LOCAL}'\"\n"),
                    pl.lit(BASH_ECHO_HEADER),
                    pl.lit("FILE_META_NAME=\"._metadata_${ROOT_FILE_NAME%.*}_"
                           "$(basename \"${ROOT_FILE_NAME}\" | rev | cut -d. -f1 | rev).yaml\"\n"),
                    pl.lit("FILE_META=\"$(find \"${ROOT_DIR_BASE}\" -name \"${FILE_META_NAME}\")\"\n"),
                    pl.lit("if [ \"${FILE_META}\" == \"\" ]; then \n"),
                    pl.lit("  echo '' && echo 'Warning: Metadata file [${FILE_META_NAME}] not found'&& exit 1\n"),
                    pl.lit("fi\n"),
                    pl.lit("echo '' && echo \"Metadata file:\"\n"),
                    pl.lit("cat \"${FILE_META}\"\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._metadata_${ROOT_FILE_STEM}\"*.yaml\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._defaults_analysed_${ROOT_FILE_STEM}\"*.yaml\n"),
                    pl.lit("rm -f \"${ROOT_DIR_BASE}/._\"*\"_${ROOT_FILE_STEM}\"/*.sh\n"),
                    pl.lit("echo '' && echo \"File probe reported:"
                           " "), pl.col("File Validity"), pl.lit("\" && echo '' && exit 0\n"),
                ]).alias("Upscale Script Source"),
            ]
        ).sort("Action Index")

        def _write_scripts(_script_name, _script_local_rows):
            script_global_file = None
            script_global_path = _localise_path(os.path.join(file_path_scripts, _script_name), file_path_root)
            try:
                if not file_path_media_is_nested:
                    if verbose:
                        print("#enriched-dataframe -> {} ... ".format(script_global_path), end='', flush=True)
                    script_global_file = open(script_global_path, 'w')
                    script_global_file.write("#!/usr/bin/env bash\n\n")
                    script_global_file.write("ROOT_DIR=$(dirname \"$(readlink -f \"$0\")\")\n\n")
                    script_global_file.write(BASH_EXIT_HANDLER.format(""))
                    script_global_file.write("echo ''\n")
                for script_local_row in _script_local_rows:
                    if not any(map(lambda script_local_row_item: script_local_row_item is None, script_local_row)):
                        if not file_path_media_is_nested:
                            script_global_file.write(
                                "[[ -f \"${{ROOT_DIR}}/../../../../../..{}\" ]] && \"${{ROOT_DIR}}/../../../../../..{}\"\n"
                                .format(script_local_row[0].replace("\"", "\\\""),
                                        script_local_row[0].replace("\"", "\\\"")))
                        script_local_dir = _localise_path(script_local_row[1].replace("\\$", "$").replace("\\`", "`"),
                                                          file_path_root)
                        os.makedirs(script_local_dir, exist_ok=True)
                        _set_permissions(script_local_dir, 0o750)
                        script_local_path = _localise_path(script_local_row[0].replace("\\$", "$").replace("\\`", "`"),
                                                           file_path_root)
                        try:
                            with open(script_local_path, 'w') as script_local_file:
                                script_local_file.write(script_local_row[2])
                                script_local_file.flush()
                        except FileNotFoundError:
                            if verbose:
                                print("skipping file currently transcoding")
                                print("#enriched-dataframe -> {} ... ".format(script_global_path), end='', flush=True)
                        _set_permissions(script_local_path, 0o750)
                if not file_path_media_is_nested:
                    script_global_file.write(BASH_ECHO_HEADER)
                    script_global_file.write("echo 'Completed [{}]'\n".format(_script_name))
                    script_global_file.write(BASH_ECHO_HEADER)
            finally:
                if not file_path_media_is_nested and script_global_file is not None:
                    script_global_file.flush()
                    script_global_file.close()
                    _set_permissions(script_global_path, 0o750)
                if not file_path_media_is_nested:
                    if verbose:
                        print("done", flush=True)

        for script in MEDIA_FILE_SCRIPTS:
            script_metadata = [
                "{} Script File".format(script.title()),
                "{} Script Directory".format(script.title()),
                "{} Script Source".format("Transcode" if script in {"reformat", "downscale"} else script.title())
            ]
            if all(_script_metadata in metadata_scripts_pl.schema for _script_metadata in script_metadata):
                _write_scripts("{}.sh".format(script),
                               metadata_scripts_pl.filter(
                                   pl.col("File Action").str.ends_with(script.title())
                               ).select(script_metadata).rows())
        script_source_header = """
#!/usr/bin/env bash

ROOT_DIR=$(dirname "$(readlink -f "$0")")

. $(asystem-media-home)/.env_media

[[ $(hostname) == macmini* ]] && killall -9 ffmpeg >/dev/null 2>/dev/null

SCRIPT_DIR="$(basename "$(realpath "${{ROOT_DIR}}/../../..")")/tmp/scripts/media/.lib"
SCRIPT_CMD="{}"
        """
        script_source_exec_local = """
"${SHARE_ROOT}/${SCRIPT_DIR}/${SCRIPT_CMD}"
        """
        script_source_exec_remote = """
LOG=""
if sh -c ": >/dev/tty" >/dev/null 2>/dev/null; then
    LOG_DEV=/dev/tty
else
    LOG_DEV=/dev/null
fi
if [ $(uname) == "Darwin" ]; then
  for LABEL in $(basename "$(realpath $(asystem-media-home)/../../../../..)" | tr "_" "\\n"); do
    HOST_NAME="$(grep "${LABEL}" "$(asystem-media-home)/../../../../../../../.hosts" | cut -d "=" -f 2 | cut -d "," -f 1)""-${LABEL}"
    HOST_DIRS='. $(asystem-media-home)/.env_media; echo ${SHARE_DIRS_LOCAL} | grep ${SHARE_ROOT}/'"$(basename "$(realpath "${ROOT_DIR}/../../..")")"' | wc -l'
    HOST_CMD='. $(asystem-media-home)/.env_media; ${SHARE_ROOT}/'"${SCRIPT_DIR}/${SCRIPT_CMD} $@"
    if [ $(ssh "root@${HOST_NAME}" "${HOST_DIRS}") -gt 0 ]; then
        echo "Executing remotely ... "
        LOG=$(ssh "root@${HOST_NAME}" "${HOST_CMD}" | tee "${LOG_DEV}")
    fi
  done
else
  LOG=$("${SHARE_ROOT}/${SCRIPT_DIR}/${SCRIPT_CMD}" $@ | tee "${LOG_DEV}")
fi
        """
        script_source_exec_analyse = """
VERBOSE="${1:---verbose}"
SHARE_DIR="$(realpath "${ROOT_DIR}/../../../..")/${2:-/media}"
"${PYTHON_DIR}/python" "${LIB_ROOT}/analyse.py" "${VERBOSE}" "${SHARE_DIR}" "${MEDIA_GOOGLE_SHEET_GUID}" 
        """
        script_source_exec_clean = """
SHARE_DIR="$(realpath "${ROOT_DIR}/../../../..")"
"$(asystem-media-home)/lib/clean.sh" "${SHARE_DIR}"
        """
        script_source_exec_normalise = """
SHARE_DIR="$(realpath "${ROOT_DIR}/../../../..")"
"$(asystem-media-home)/lib/normalise.sh" "${SHARE_DIR}"
        """
        script_source_exec_summarise = """
echo -n "Processing '$(dirname $(dirname $(dirname "${ROOT_DIR}")))/media' ... "
declare -a RENAME_DIRS
declare -A RENAME_DIRS_SET
declare -a CHECK_DIRS
declare -A CHECK_DIRS_SET
declare -a MERGE_DIRS
declare -A MERGE_DIRS_SET
LOG=$(echo "${LOG}" | grep -E "1. Rename|2. Check|3. Merge" | grep "/share")
readarray -t LOG_LINES <<<"${LOG}"
for LOG_LINE in "${LOG_LINES[@]}"; do
  RENAME_DIR=$(grep "1. Rename"  <<< "$LOG_LINE" | cut -d'|' -f12 | xargs | sed -e "s/^\\/share//")
  if [ -n "${RENAME_DIR}" ]; then
    RENAME_DIRS_SET["${RENAME_DIR}"]=1
  fi
  CHECK_DIR=$(grep "2. Check"  <<< "$LOG_LINE" | cut -d'|' -f12 | xargs | sed -e "s/^\\/share//")
  if [ -n "${CHECK_DIR}" ]; then
    CHECK_DIRS_SET["${CHECK_DIR}"]=1
  fi
  MERGE_DIR=$(grep "3. Merge"  <<< "$LOG_LINE" | cut -d'|' -f12 | xargs | sed -e "s/^\\/share//")
  if [ -n "${MERGE_DIR}" ]; then
    MERGE_DIRS_SET["${MERGE_DIR}"]=1
  fi
done
for RENAME_DIR in "${!RENAME_DIRS_SET[@]}"; do
  RENAME_DIRS+=("'${SHARE_ROOT}${RENAME_DIR}'")
done
IFS=$'\\n' RENAME_DIRS=($(sort <<<"${RENAME_DIRS[*]}"))
unset IFS
for CHECK_DIR in "${!CHECK_DIRS_SET[@]}"; do
  CHECK_DIRS+=("'${SHARE_ROOT}${CHECK_DIR}'")
done
IFS=$'\\n' CHECK_DIRS=($(sort <<<"${CHECK_DIRS[*]}"))
unset IFS
for MERGE_DIR in "${!MERGE_DIRS_SET[@]}"; do
  MERGE_DIRS+=("'${SHARE_ROOT}${MERGE_DIR}'")
done
IFS=$'\\n' MERGE_DIRS=($(sort <<<"${MERGE_DIRS[*]}"))
unset IFS
echo "done"
if [ "${#RENAME_DIRS[@]}" -gt 0 ] || [ "${#CHECK_DIRS[@]}" -gt 0 ] || [ "${#MERGE_DIRS[@]}" -gt 0 ]; then
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    echo "Renames to run in directory ... "
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    for RENAME_DIR in "${RENAME_DIRS[@]}"; do
       echo "cd ${RENAME_DIR}"
    done
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    echo "Checks to run in directory ... "
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    for CHECK_DIR in "${CHECK_DIRS[@]}"; do
       echo "cd ${CHECK_DIR}"
    done
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    echo "Merges to run in directory ... "
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    for MERGE_DIR in "${MERGE_DIRS[@]}"; do
       echo "cd ${MERGE_DIR}"
    done
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
fi
        """
        if not file_path_media_is_nested:
            for script_name, script_source in {
                ".lib/clean": (
                        script_source_header.format("clean.sh"),
                        script_source_exec_clean),
                ".lib/normalise": (
                        script_source_header.format("normalise.sh"),
                        script_source_exec_normalise),
                ".lib/analyse": (
                        script_source_header.format("analyse.sh"),
                        script_source_exec_analyse),
                "clean": (
                        script_source_header.format("clean.sh"),
                        script_source_exec_remote),
                "normalise": (
                        script_source_header.format("normalise.sh"),
                        script_source_exec_remote),
                "analyse": (
                        script_source_header.format("analyse.sh"),
                        script_source_exec_remote, script_source_exec_summarise),
                "rename": (
                        script_source_header.format("rename.sh"),
                        script_source_exec_remote),
                "check": (
                        script_source_header.format("check.sh"),
                        script_source_exec_remote),
                "merge": (
                        script_source_header.format("merge.sh"),
                        script_source_exec_remote),
                "upscale": (
                        script_source_header.format("upscale.sh"),
                        script_source_exec_remote),
                "reformat": (
                        script_source_header.format("reformat.sh"),
                        script_source_exec_remote),
                "transcode": (
                        script_source_header.format("transcode.sh"),
                        script_source_exec_local),
                "downscale": (
                        script_source_header.format("downscale.sh"),
                        script_source_exec_local),
            }.items():
                script_path = _localise_path(os.path.join(os.path.dirname(file_path_scripts),
                                                          "{}.sh".format(script_name)), file_path_root)
                if verbose:
                    print("#enriched-dataframe -> {} ... ".format(script_path), end='', flush=True)
                with open(script_path, 'w') as script_file:
                    for script_source_section in script_source:
                        script_file.write(script_source_section.strip() + "\n\n")
                _set_permissions(script_path, 0o750)
                if verbose:
                    print("done", flush=True)
        os.sync()
    if metadata_merged_pl.height == 0:
        metadata_merged_pl = pl.DataFrame(schema={
            "File Name": pl.String,
            "File Action": pl.String,
            "Media Type": pl.String,
            "Metadata Loaded": pl.String,
        })
    else:
        metadata_merged_pl = metadata_merged_pl.select([
            column.name for column in metadata_merged_pl \
            if not (column.null_count() == metadata_merged_pl.height)
        ])
    metadata_summary_pl = pl.concat([
        metadata_merged_pl.group_by(["File Action"]) \
            .agg(pl.col("File Name").count().alias("File Count")),
        metadata_merged_pl.group_by(["Media Type"]) \
            .agg(pl.col("File Name").count().alias("File Count")),
        metadata_merged_pl.group_by(["File Action", "Media Type"]) \
            .agg(pl.col("File Name").count().alias("File Count")),
    ], how="diagonal_relaxed")
    metadata_summary_pl = pl.concat([
        metadata_summary_pl,
        metadata_summary_pl.filter(pl.col("Media Type").is_null()).select(pl.sum("File Count"))
    ], how="diagonal_relaxed") \
        .select(["File Action", "Media Type", "File Count"]) \
        .sort(["File Action", "Media Type"], nulls_last=True)
    metadata_summary_pl = metadata_summary_pl.join(
        pl.DataFrame([{
            "File Action": file_action,
            "Media Type": media_type,
            "File Count": 0
        } for file_action in [None] + [_file_action.label for _file_action in FileAction] \
            for media_type in (None, "movies", "series")]
        ), on=["File Action", "Media Type"], how="right", nulls_equal=True) \
        .select(["File Action", "Media Type", "File Count"]) \
        .sort(["File Action", "Media Type"], nulls_last=True) \
        .fill_null(0)
    if verbose:
        if metadata_merged_pl.height > 0:
            print("#metadata-delta ... ")
            _print_df(
                metadata_merged_pl \
                    .filter((pl.col("Metadata Loaded") == "True"))
                    .select(metadata_merged_pl.columns[:10] + ["File Directory"])
                    .with_columns(pl.col("File Directory").str.strip_chars().name.keep())
                    .fill_null("")
            )
        print("#metadata-summary ... ")
        _print_df(metadata_summary_pl.fill_null(""))
    if "Metadata Loaded" in metadata_merged_pl.columns:
        metadata_merged_pl = metadata_merged_pl.drop("Metadata Loaded")
    _print_message(_message="done", _header=not verbose, _footer=False)
    if metadata_merged_pl.height > 0:
        if not file_path_root_is_nested:
            if not verbose:
                print("Uploading '{}' ... ".format(sheet_url), end="", flush=True)
            else:
                print("#enriched-dataframe -> {} ... ".format(sheet_url), end='', flush=True)
            metadata_spread_data_upload = Spread(sheet_url, sheet="Data")
            metadata_spread_data_upload \
                .df_to_sheet(metadata_merged_pl.to_pandas(use_pyarrow_extension_array=True),
                             sheet="Data", replace=True, index=False, add_filter=True)
            if metadata_spread_data_upload.get_sheet_dims()[0] > 1 and \
                    metadata_spread_data_upload.get_sheet_dims()[1] > 1:
                metadata_spread_data_upload.freeze(1, 1, sheet="Data")
            Spread(sheet_url, sheet="Data") \
                .df_to_sheet(metadata_summary_pl.to_pandas(use_pyarrow_extension_array=True),
                             sheet="Summary", replace=True, index=False, add_filter=True)
            print("done", flush=True)
    metadata_summary_categories = {}
    for metadata_summary_category in metadata_summary_pl.filter(
            ~pl.col("File Action").is_null() &
            pl.col("Media Type").is_null()
    ).select("File Action", "File Count").to_dicts():
        metadata_summary_categories[metadata_summary_category["File Action"]] = \
            metadata_summary_category["File Count"]
    return files_analysed, metadata_summary_categories


def _normalise_name(_name):
    _name = _name.replace("@", " ")
    name_episode_match = re.search(MEDIA_EPISODE_NUMBER_REGEXP, _name)
    if name_episode_match is not None:
        _name = _name.replace("".join(name_episode_match.groups()), "@@")
    _name = _name.replace(".", " ").replace("-", " ").replace("_", " ").replace("/", " / ")
    _name = string.capwords(re.sub(" +", " ", _name).strip()) \
        .replace(" / ", "/")
    for name_token in {
        " i ",
        " ii ",
        " iii ",
        " iv ",
        " v ",
        " vi ",
        " vii ",
        " viii ",
        " ix ",
        " x "
    }:
        _name = _name.replace(name_token.title(), name_token.upper())
        _name = _name.replace(name_token.upper(), name_token.upper())
        _name = _name.replace(name_token.lower(), name_token.upper())
    if name_episode_match is not None:
        _name = _name.replace("@@", "S{}E{}{}".format(
            name_episode_match.groups()[1],
            name_episode_match.groups()[4],
            name_episode_match.groups()[5]
        ))
    return _name


def _escape_path(_path, _quoted=False):
    return _path.replace("'", "'\\''") if _quoted else _path.replace("'", "\\'")


def _localise_path(_path, _local_path, _escape=False, _quoted=False):
    _path = _path if ("/share/" not in _path or not _path.startswith("/share/")) \
        else "{}{}".format(_local_path.split("/share/")[0], _path)
    return _escape_path(_path, _quoted) if _escape else _path


def _delocalise_path(_path, _local_path, _escape=False, _quoted=False):
    _path = _path if ("/share/" not in _path or _path.startswith("/share/")) \
        else "{}{}".format("/share/", _path.split("/share/")[1])
    return _escape_path(_path, _quoted) if _escape else _path


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


def _print_df(data_df):
    with pl.Config(
            tbl_rows=-1,
            tbl_cols=-1,
            ascii_tables=True,
            fmt_str_lengths=200,
            fmt_float="full",
            tbl_width_chars=30000,
            tbl_formatting="ASCII_FULL_CONDENSED",
            tbl_hide_dataframe_shape=True,
            tbl_hide_column_data_types=True,
    ):
        print(data_df)


# noinspection PyUnusedLocal
def get_file_actions_dict(rename=0, delete=0, check=0, merge=0, reformat=0, transcode=0, upscale=0, downscale=0,
                          nothing=0):
    files_action = {_file_action.label: 0 for _file_action in FileAction}
    for var in vars().copy():
        if var != files_action:
            for _file_action in FileAction:
                if _file_action.name.lower() == var:
                    files_action[_file_action.label] = vars()[var]
    return files_action


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--clean", default=False, action="store_true")
    argument_parser.add_argument("--force", default=False, action="store_true")
    argument_parser.add_argument("--defaults", default=False, action="store_true")
    argument_parser.add_argument("--verbose", default=False, action="store_true")
    argument_parser.add_argument("--quiet", default=True, action="store_true")
    argument_parser.add_argument("directory")
    argument_parser.add_argument("sheetguid")
    arguments = argument_parser.parse_args()
    sys.exit(1 if _analyse(
        Path(arguments.directory).absolute().as_posix(),
        arguments.sheetguid,
        arguments.clean,
        arguments.force,
        arguments.defaults,
        arguments.verbose or not arguments.quiet
    )[0] < 0 else 0)
