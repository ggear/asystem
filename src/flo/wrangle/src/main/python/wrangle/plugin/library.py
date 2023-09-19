import collections
import copy
import datetime
import glob
import hashlib
import io
import json
import logging
import os
import os.path
import shutil
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
import warnings
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from datetime import date
from datetime import datetime
from datetime import timedelta
from ftplib import FTP
from os.path import *

import dropbox
import influxdb
import numpy as np
import pandas as pd
import polars as pl
import requests
import yfinance as yf
from dateutil import parser
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
from gspread_pandas import Spread
from pandas.api.extensions import no_default
from pandas.tseries.offsets import BDay
from polars.datatypes import DataTypeClass
from requests import post
from tabulate import tabulate

PL_PRINT_ROWS = 6

PD_PRINT_ROWS = 3
PD_ENGINE_DEFAULT = None
PD_BACKEND_DEFAULT = no_default

CTR_LBL_PAD = '.'
CTR_LBL_WIDTH = 26
CTR_SRC_DATA = "Data"
CTR_SRC_FILES = "Files"
CTR_SRC_EGRESS = "Egress"
CTR_SRC_SOURCES = "Sources"
CTR_ACT_PREVIOUS_ROWS = "Previous Rows"
CTR_ACT_PREVIOUS_COLUMNS = "Previous Columns"
CTR_ACT_CURRENT_ROWS = "Current Rows"
CTR_ACT_CURRENT_COLUMNS = "Current Columns"
CTR_ACT_UPDATE_ROWS = "Update Rows"
CTR_ACT_UPDATE_COLUMNS = "Update Columns"
CTR_ACT_DELTA_ROWS = "Delta Rows"
CTR_ACT_DELTA_COLUMNS = "Delta Columns"
CTR_ACT_SHEET_ROWS = "Sheet Rows"
CTR_ACT_SHEET_COLUMNS = "Sheet Columns"
CTR_ACT_DATABASE_ROWS = "Database Rows"
CTR_ACT_DATABASE_COLUMNS = "Database Columns"
CTR_ACT_QUEUE_ROWS = "Queue Rows"
CTR_ACT_QUEUE_COLUMNS = "Queue Columns"
CTR_ACT_ERRORED = "Errored"
CTR_ACT_PROCESSED = "Processed"
CTR_ACT_SKIPPED = "Skipped"
CTR_ACT_DOWNLOADED = "Downloaded"
CTR_ACT_CACHED = "Cached"
CTR_ACT_PERSISTED = "Persisted"
CTR_ACT_UPLOADED = "Uploaded"

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.float_format', lambda x: '%.5f' % x)
pd.options.mode.chained_assignment = None

logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)

WRANGLE_ENABLE_LOG = 'WRANGLE_ENABLE_LOG'
WRANGLE_ENABLE_DATA_SUBSET = 'WRANGLE_ENABLE_DATA_SUBSET'
WRANGLE_ENABLE_DATA_TRUNC = 'WRANGLE_ENABLE_DATA_TRUNC'
WRANGLE_ENABLE_DATA_CACHE = 'WRANGLE_ENABLE_DATA_CACHE'
WRANGLE_DISABLE_DATA_DELTA = 'WRANGLE_DISABLE_DATA_DELTA'
WRANGLE_DISABLE_DATA_LINEPROTOCOL = 'WRANGLE_DISABLE_DATA_LINEPROTOCOL'
WRANGLE_DISABLE_FILE_UPLOAD = 'WRANGLE_DISABLE_FILE_UPLOAD'
WRANGLE_DISABLE_FILE_DOWNLOAD = 'WRANGLE_DISABLE_FILE_DOWNLOAD'


def test(variable, default=False):
    return os.getenv(variable, "{}".format(default).lower()).lower() == "true"


def print_log(process, messages, exception=None, level="debug"):
    if test(WRANGLE_ENABLE_LOG):
        prefix = "{} [{}] [{}]: " \
            .format(level.upper() if exception is None else 'ERROR', process, datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        if type(messages) is not list:
            messages = [messages]
        for line in messages:
            if len(line) > 0:
                print("{}{}".format(prefix, line), flush=True)
        if exception is not None:
            print("{}{}".format(prefix, ("\n" + prefix).join(traceback.format_exc().splitlines())), flush=True)


def get_file(file_name):
    if isfile(file_name):
        return file_name
    file_name = basename(file_name)
    working = dirname(__file__)
    paths = [
        "/root/{}".format(file_name),
        "/etc/telegraf/{}".format(file_name),
        "{}/../../../resources/{}".format(working, file_name),
        "{}/../../../resources/config/{}".format(working, file_name),
        "{}/../../../../../{}".format(working, file_name),
    ]
    for path in paths:
        if isfile(path):
            return path
    raise IOError("Could not find file [{}] in the usual places {}".format(file_name, paths))


def get_dir(dir_name):
    working = dirname(__file__)
    parent_paths = [
        "/asystem/runtime",
        "{}/../../../../../target".format(working),
    ]
    for parent_path in parent_paths:
        if isdir(parent_path):
            path = abspath("{}/{}".format(parent_path, dir_name))
            if not isdir(path):
                os.makedirs(path)
            return path
    raise IOError("Could not find path in the usual places {}".format(parent_paths))


def load_profile(profile_path):
    profile = {}
    with open(get_file(profile_path), 'r') as profile_file:
        for profile_line in profile_file:
            profile_line = profile_line.replace("export ", "").rstrip()
            if "=" not in profile_line:
                continue
            if profile_line.startswith("#"):
                continue
            profile_key, profile_value = profile_line.split("=", 1)
            profile[profile_key] = profile_value
    return profile


# noinspection DuplicatedCode
class Library(object, metaclass=ABCMeta):
    @abstractmethod
    def _run(self):
        pass

    def _trunc(self):
        if test(WRANGLE_DISABLE_DATA_DELTA) and test(WRANGLE_ENABLE_DATA_TRUNC):
            self.database_trunc()

    def run(self):
        started_time = time.time()
        self.print_log("Starting ...")
        self._trunc()
        self._run()
        self.print_counters()
        self.print_log("Finished", started=started_time)

    def print_log(self, messages, data=None, started=None, exception=None):
        if test(WRANGLE_ENABLE_LOG):
            if type(messages) is not list:
                messages = [messages]
            if started is not None:
                messages[-1] = messages[-1] + " in [{:.3f}] sec".format(time.time() - started)
            if data is not None:
                messages[-1] = messages[-1] + ": "
                if type(data) is list:
                    messages.extend(data)
                else:
                    messages[-1] = messages[-1] + data
            print_log(self.name, messages, exception)

    def print_counters(self):
        self.print_log("Execution Summary:")
        for source in self.counters:
            for action in self.counters[source]:
                self.print_log("     {} {:8}".format("{} {} ".format(source, action)
                                                     .ljust(CTR_LBL_WIDTH, CTR_LBL_PAD), self.counters[source][action]))

    def add_counter(self, source, action, count=1):
        self.counters[source][action] += count

    def get_counter(self, source, action):
        return self.counters[source][action]

    def get_counters(self):
        return copy.deepcopy(self.counters)

    # noinspection PyAttributeOutsideInit
    def reset_counters(self):
        self.counters = OrderedDict([
            (CTR_SRC_SOURCES, OrderedDict([
                (CTR_ACT_DOWNLOADED, 0),
                (CTR_ACT_CACHED, 0),
                (CTR_ACT_UPLOADED, 0),
                (CTR_ACT_PERSISTED, 0),
                (CTR_ACT_ERRORED, 0),
            ])),
            (CTR_SRC_FILES, OrderedDict([
                (CTR_ACT_PROCESSED, 0),
                (CTR_ACT_SKIPPED, 0),
                (CTR_ACT_ERRORED, 0),
            ])),
            (CTR_SRC_DATA, OrderedDict([
                (CTR_ACT_PREVIOUS_COLUMNS, 0),
                (CTR_ACT_PREVIOUS_ROWS, 0),
                (CTR_ACT_CURRENT_COLUMNS, 0),
                (CTR_ACT_CURRENT_ROWS, 0),
                (CTR_ACT_UPDATE_COLUMNS, 0),
                (CTR_ACT_UPDATE_ROWS, 0),
                (CTR_ACT_DELTA_COLUMNS, 0),
                (CTR_ACT_DELTA_ROWS, 0),
                (CTR_ACT_ERRORED, 0),
            ])),
            (CTR_SRC_EGRESS, OrderedDict([
                (CTR_ACT_QUEUE_COLUMNS, 0),
                (CTR_ACT_QUEUE_ROWS, 0),
                (CTR_ACT_SHEET_COLUMNS, 0),
                (CTR_ACT_SHEET_ROWS, 0),
                (CTR_ACT_DATABASE_COLUMNS, 0),
                (CTR_ACT_DATABASE_ROWS, 0),
                (CTR_ACT_ERRORED, 0),
            ])),
        ])

    # noinspection PyProtectedMember,PyUnresolvedReferences
    def http_download(self, url_file, local_path, check=True, force=False, ignore=False):
        started_time = time.time()
        local_path = abspath(local_path)
        if not force and not check and isfile(local_path):
            self.print_log("File [{}] cached at [{}]".format(basename(local_path), local_path), started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return True, False
        else:
            client = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
                'Accept': 'text/html,application/xhtml+xml,application/xml,text/csv,application/zip;q=0.9,*/*;q=0.8',
                'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
                'Accept-Encoding': 'none',
                'Accept-Language': 'en-US,en;q=0.8',
                'Connection': 'keep-alive'
            }

            def get_modified(headers):
                if headers["Last-Modified"]:
                    return int((datetime.strptime(headers["Last-Modified"], '%a, %d %b %Y %H:%M:%S GMT') -
                                datetime.utcfromtimestamp(0)).total_seconds())
                return None

            if not force and check and isfile(local_path):
                modified_timestamp_cached = int(getmtime(local_path))
                try:
                    request = urllib.request.Request(url_file, headers=client)
                    request.get_method = lambda: 'HEAD'
                    response = urllib.request.urlopen(request, context=ssl._create_unverified_context())
                    modified_timestamp = get_modified(response.headers)
                    if modified_timestamp is not None:
                        if modified_timestamp_cached == modified_timestamp:
                            self.print_log("File [{}] cached at [{}]"
                                           .format(basename(local_path), local_path), started=started_time)
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                            return True, False
                except (Exception,):
                    pass
            try:
                response = urllib.request.urlopen(urllib.request.Request(url_file, headers=client),
                                                  context=ssl._create_unverified_context())
                if not exists(dirname(local_path)):
                    os.makedirs(dirname(local_path))
                with open(local_path, 'wb') as local_file:
                    local_file.write(response.read())
                modified_timestamp = get_modified(response.headers)
                try:
                    if modified_timestamp is not None:
                        os.utime(local_path, (modified_timestamp, modified_timestamp))
                except Exception as exception:
                    self.print_log("File [{}] modified timestamp set failed [{}]"
                                   .format(local_path, modified_timestamp), exception=exception)
                self.print_log("File [{}] downloaded to [{}]".format(basename(local_path), local_path), started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                return True, True
            except Exception as exception:
                if not ignore:
                    self.print_log("File [{}] not available at [{}]".format(basename(local_path), url_file), exception=exception)
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return False, False

    def ftp_download(self, url_file, local_file, check=True, force=False, ignore=False):
        started_time = time.time()
        local_file = abspath(local_file)
        if not force and not check and isfile(local_file):
            self.print_log("File [{}] cached at [{}]".format(basename(local_file), local_file), started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return True, False
        else:
            url_server = url_file.replace("ftp://", "").split("/")[0]
            url_path = url_file.split(url_server)[-1]
            client = None
            try:
                client = FTP(url_server)
                client.login()
                modified_timestamp = int((parser.parse(client.voidcmd("MDTM {}".format(url_path))[4:].strip()) -
                                          datetime.utcfromtimestamp(0)).total_seconds())
                if not force and check and isfile(local_file):
                    modified_timestamp_cached = int(getmtime(local_file))
                    if modified_timestamp_cached == modified_timestamp:
                        self.print_log("File [{}] cached at [{}]".format(basename(local_file), local_file), started=started_time)
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                        client.quit()
                        return True, False
                if not exists(dirname(local_file)):
                    os.makedirs(dirname(local_file))
                client.retrbinary("RETR {}".format(url_path), open(local_file, 'wb').write)
                try:
                    os.utime(local_file, (modified_timestamp, modified_timestamp))
                except Exception as exception:
                    self.print_log("File [{}] modified timestamp set failed [{}]"
                                   .format(local_file, modified_timestamp), exception=exception)
                self.print_log("File [{}] downloaded to [{}]".format(basename(local_file), local_file), started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                client.quit()
                return True, True
            except Exception as exception:
                if client is not None:
                    client.quit()
                self.print_log("File [{}] not available at [{}]".format(basename(local_file), url_file), exception=exception)
                if not ignore:
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return False, False

    def stock_download(self, local_path, ticker, start, end, end_of_day='17:00', check=True, force=False, ignore=True,
                       engine=PD_ENGINE_DEFAULT, dtype_backend=PD_BACKEND_DEFAULT):
        started_time = time.time()
        local_path = abspath(local_path)
        now = datetime.now()
        end_exclusive = datetime.strptime(end, '%Y-%m-%d').date() + timedelta(days=1)
        if start != end_exclusive:
            if not force and not check and isfile(local_path):
                self.print_log("File [{}] cached at [{}]".format(basename(local_path), local_path), started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return True, False
            else:
                try:
                    if not force and check and isfile(local_path):
                        if now.year == int(end.split('-')[0]) and now.month == int(end.split('-')[1]):
                            data_df = self.dataframe_read_pd(local_path, engine=engine, dtype_backend=dtype_backend)
                            if len(data_df) > 0:
                                end_data = data_df.values[-1][0]
                                end_data = datetime.strptime(end_data, '%Y-%m-%d').date() \
                                    if isinstance(end_data, str) else end_data
                                end_expected = BDay().rollback(now).date()
                                if now.date() == end_expected:
                                    if -1 < now.weekday() < 5:
                                        if now.strftime('%H:%M') < end_of_day:
                                            end_expected = end_expected - timedelta(days=3 if now.weekday() == 0 else 1)
                                    else:
                                        end_expected = end_expected - timedelta(days=2 if now.weekday() == 5 else 1)
                                if end_data == end_expected:
                                    self.print_log("File [{}:] cached at [{}]"
                                                   .format(basename(local_path), local_path), started=started_time)
                                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                                    return True, False
                            else:
                                self.print_log("File [{}] cached (but empty) at [{}]"
                                               .format(basename(local_path), local_path), started=started_time)
                                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                                return True, False
                    data_df = yf.Ticker(ticker).history(start=start, end=end_exclusive)

                    # NOTE: Adapt to yfinance-0.1.70 format, removing Timezones and Capital Gains
                    data_df.index = data_df.index.tz_localize(None)
                    if "Capital Gains" in data_df:
                        data_df = data_df.drop(columns=["Capital Gains"])
                    # NOTE: End

                    if now.year == int(end.split('-')[0]) and now.month == int(end.split('-')[1]) \
                            and data_df.index[-1].date() == now.date() and now.strftime('%H:%M') < end_of_day:
                        data_df = data_df[:-1]
                    if len(data_df) == 0:
                        if ignore:
                            self.print_log("No data returned for [{} - {} {}]".format(ticker, start, end_exclusive))
                        else:
                            raise Exception("No data returned for [{} - {} {}]".format(ticker, start, end_exclusive))
                    if not exists(dirname(local_path)):
                        os.makedirs(dirname(local_path))
                    self.dataframe_write_pd(data_df, local_path)
                    if len(data_df) > 0:
                        modified = self.dataframe_read_pd(local_path, engine=engine, dtype_backend=dtype_backend).values[-1][0]
                        modified = datetime.strptime(modified, '%Y-%m-%d').date() if isinstance(modified, str) else modified
                        modified_timestamp = int((modified + timedelta(hours=8) - datetime.utcfromtimestamp(0).date()).total_seconds())
                        try:
                            os.utime(local_path, (modified_timestamp, modified_timestamp))
                        except Exception as exception:
                            self.print_log("File [{}] modified timestamp set failed [{}]"
                                           .format(local_path, modified_timestamp), exception=exception)
                    self.print_log("File [{}] downloaded to [{}]"
                                   .format(basename(local_path), local_path), started=started_time)
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                    return True, True
                except Exception as exception:
                    self.print_log("File not available for [{} - {} {}]"
                                   .format(ticker, start, end_exclusive), exception=exception)
                    if not ignore:
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return False, False

    def dropbox_download(self, dropbox_dir, local_dir, check=True):
        started_time = time.time()

        class DropboxContentHasher(object):
            BLOCK_SIZE = 4 * 1024 * 1024

            def __init__(self):
                self._overall_hasher = hashlib.sha256()
                self._block_hasher = hashlib.sha256()
                self._block_pos = 0
                self.digest_size = self._overall_hasher.digest_size

            def update(self, new_data):
                new_data_pos = 0
                while new_data_pos < len(new_data):
                    if self._block_pos == self.BLOCK_SIZE:
                        self._overall_hasher.update(self._block_hasher.digest())
                        self._block_hasher = hashlib.sha256()
                        self._block_pos = 0
                    space_in_block = self.BLOCK_SIZE - self._block_pos
                    part = new_data[new_data_pos:(new_data_pos + space_in_block)]
                    self._block_hasher.update(part)
                    self._block_pos += len(part)
                    new_data_pos += len(part)

            def _finish(self):
                if self._block_pos > 0:
                    self._overall_hasher.update(self._block_hasher.digest())
                    self._block_hasher = None
                h = self._overall_hasher
                self._overall_hasher = None
                return h

            def hexdigest(self):
                return self._finish().hexdigest()

        def file_hash(file_name):
            hasher = DropboxContentHasher()
            with open(file_name, 'rb') as f:
                while True:
                    chunk = f.read(1024)
                    if len(chunk) == 0:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()

        local_files = {}
        for local_file in glob.glob("{}/*".format(local_dir)):
            local_files[basename(local_file)] = {
                "hash": file_hash(local_file) if check else None,
                "modified": int(getmtime(local_file)) if check else None
            }
        dropbox_files = {}
        service = dropbox.Dropbox(os.getenv('DROPBOX_TOKEN'))
        cursor = None
        while True:
            response = service.files_list_folder(dropbox_dir) if cursor is None else service.files_list_folder_continue(cursor)
            for dropbox_file in response.entries:
                dropbox_files[dropbox_file.name] = {
                    "id": dropbox_file.id,
                    "hash": dropbox_file.content_hash,
                    "modified": int((dropbox_file.client_modified - datetime.utcfromtimestamp(0)).total_seconds()),
                }
            if response.has_more:
                cursor = response.cursor
            else:
                break
        self.print_log("Directory [{}] listed [{}] files from [https://www.dropbox.com/home/{}]"
                       .format(basename(local_dir), len(dropbox_files), dropbox_dir), started=started_time)
        actioned_files = {}
        for dropbox_file in dropbox_files:
            started_time_file = time.time()
            file_actioned = False
            local_path = abspath("{}/{}".format(local_dir, dropbox_file))
            if dropbox_file not in local_files or (check and (
                    dropbox_files[dropbox_file]["modified"] != local_files[dropbox_file]["modified"] or
                    dropbox_files[dropbox_file]["hash"] != local_files[dropbox_file]["hash"]
            )):
                if not exists(dirname(local_path)):
                    os.makedirs(dirname(local_path))
                with open(local_path, "wb") as local_file:
                    metadata, response = service.files_download(path="{}/{}".format(dropbox_dir, dropbox_file))
                    local_file.write(response.content)
                try:
                    os.utime(local_path, (dropbox_files[dropbox_file]["modified"], dropbox_files[dropbox_file]["modified"]))
                except Exception as exception:
                    self.print_log("File [{}] modified timestamp set failed [{}]"
                                   .format(local_path, dropbox_files[dropbox_file]["modified"]), exception=exception)
                local_files[dropbox_file] = {
                    "hash": dropbox_files[dropbox_file]["hash"],
                    "modified": dropbox_files[dropbox_file]["modified"]
                }
                file_actioned = True
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                self.print_log("File [{}] downloaded to [{}]".format(dropbox_file, local_path), started=started_time_file)
            else:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                self.print_log("File [{}] cached at [{}]".format(dropbox_file, local_path), started=started_time_file)
            actioned_files[local_path] = True, file_actioned
        self.print_log("Directory [{}] downloaded [{}] files from [https://www.dropbox.com/home/{}]"
                       .format(basename(local_dir).title(), len(actioned_files), dropbox_dir), started=started_time)
        return collections.OrderedDict(sorted(actioned_files.items()))

    def drive_sync(self, drive_dir, local_dir, check=True, download=True, upload=False):
        started_time = time.time()

        def file_hash(file_name):
            hash_md5 = hashlib.md5()
            with open(file_name, "rb") as f:
                for block in iter(lambda: f.read(8 * 1024), b""):
                    hash_md5.update(block)
            return hash_md5.hexdigest()

        local_files = {}
        for local_file in glob.glob("{}/*".format(local_dir)):
            local_files[basename(local_file)] = {
                "hash": file_hash(local_file) if check else None,
                "modified": int(getmtime(local_file)) if check else None
            }
        drive_files = {}
        credentials = service_account.Credentials.from_service_account_file(
            get_file(".google_service_account.json"), scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
        token = None
        while True:
            response = service.files().list(q="'{}' in parents".format(drive_dir), spaces='drive',
                                            fields='nextPageToken, files(id, name, modifiedTime, md5Checksum)', pageToken=token).execute()
            for drive_file in response.get('files', []):
                drive_files[drive_file["name"]] = {
                    "id": drive_file["id"],
                    "hash": drive_file["md5Checksum"],
                    "modified": int((datetime.strptime(drive_file["modifiedTime"], '%Y-%m-%dT%H:%M:%S.%fZ') -
                                     datetime.utcfromtimestamp(0)).total_seconds()),
                }
            token = response.get('nextPageToken')
            if not token:
                break
        self.print_log("Directory [{}] listed [{}] files from [https://drive.google.com/drive/folders/{}]"
                       .format(basename(local_dir), len(drive_files), drive_dir), started=started_time)
        actioned_files = {}
        for drive_file in drive_files:
            started_time_file = time.time()
            file_actioned = False
            local_path = abspath("{}/{}".format(local_dir, drive_file))
            if drive_file not in local_files or (check and (
                    drive_files[drive_file]["modified"] > local_files[drive_file]["modified"]
            )):
                if download:
                    request = service.files().get_media(fileId=drive_files[drive_file]["id"])
                    buffer_file = io.BytesIO()
                    downloader = MediaIoBaseDownload(buffer_file, request)
                    done = False
                    while not done:
                        _, done = downloader.next_chunk()
                    if not exists(dirname(local_path)):
                        os.makedirs(dirname(local_path))
                    with open(local_path, 'wb') as local_file:
                        local_file.write(buffer_file.getvalue())
                    try:
                        os.utime(local_path, (drive_files[drive_file]["modified"], drive_files[drive_file]["modified"]))
                    except Exception as exception:
                        self.print_log("File [{}] modified timestamp set failed [{}]"
                                       .format(local_path, drive_files[drive_file]["modified"]), exception=exception)
                    local_files[drive_file] = {
                        "hash": drive_files[drive_file]["hash"],
                        "modified": drive_files[drive_file]["modified"]
                    }
                    file_actioned = True
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                    self.print_log("File [{}] downloaded to [{}]".format(drive_file, local_path), started=started_time_file)
            else:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                self.print_log("File [{}] cached at [{}]".format(drive_file, local_path), started=started_time_file)
            actioned_files[local_path] = True, file_actioned
        if upload:
            for local_file in local_files:
                if not local_file.startswith("_"):
                    started_time_file = time.time()
                    file_actioned = False
                    local_path = abspath("{}/{}".format(local_dir, local_file))
                    if local_file not in drive_files or (check and (
                            drive_files[local_file]["modified"] != local_files[local_file]["modified"] or
                            drive_files[local_file]["hash"] != local_files[local_file]["hash"]
                    )):
                        self.drive_write(local_path, drive_dir, local_files[local_file]["modified"], service,
                                         drive_files[local_file]["id"] if local_file in drive_files else None)
                        file_actioned = True
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_UPLOADED)
                    else:
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_PERSISTED)
                        self.print_log("File [{}] verified at [https://drive.google.com/file/d/{}]"
                                       .format(local_file, drive_files[local_file]["id"]), started=started_time_file)
                    actioned_files[local_path] = True, file_actioned
        self.print_log("Directory [{}] synchronised [{}] files from [https://drive.google.com/drive/folders/{}]"
                       .format(basename(local_dir).title(), len(actioned_files), drive_dir), started=started_time)
        return collections.OrderedDict(sorted(actioned_files.items()))

    def state_cache(self, data_df_update, aggregate_function=None, engine=PD_ENGINE_DEFAULT, dtype_backend=PD_BACKEND_DEFAULT):
        started_time = time.time()
        file_delta = abspath("{}/__{}_Delta.csv".format(self.input, self.name.title()))
        file_update = abspath("{}/__{}_Update.csv".format(self.input, self.name.title()))
        file_current = abspath("{}/__{}_Current.csv".format(self.input, self.name.title()))
        file_previous = abspath("{}/__{}_Previous.csv".format(self.input, self.name.title()))
        if not isdir(self.input):
            os.makedirs(self.input)
        if not test(WRANGLE_DISABLE_FILE_DOWNLOAD) and test(WRANGLE_DISABLE_DATA_DELTA):
            if isfile(file_current):
                os.remove(file_current)
        data_df_current = self.dataframe_read_pd(file_current, engine=engine, dtype_backend=dtype_backend, index_col=0) \
            if isfile(file_current) else pd.DataFrame()
        data_df_current.index = pd.to_datetime(data_df_current.index)
        data_df_current.index.name = 'Date'
        if test(WRANGLE_DISABLE_FILE_DOWNLOAD):
            self.print_log("StateCache loaded ignoring updates", started=started_time)
            return data_df_current, data_df_current, data_df_current
        data_columns = data_df_current.columns.values.tolist()
        for data_column in data_df_update.columns.values.tolist():
            if data_column not in data_columns:
                data_columns.append(data_column)
        for data_column in data_columns:
            if data_column not in data_df_current:
                data_df_current[data_column] = np.nan
        data_df_update = data_df_update.copy()
        data_df_update.index.name = 'Date'
        data_df_update.index = pd.to_datetime(data_df_update.index)
        data_df_update = data_df_update.sort_index()
        self.dataframe_write_pd(data_df_update, file_update)
        data_df_update = self.dataframe_read_pd(file_update, engine=engine, dtype_backend=dtype_backend, index_col=0)
        data_df_update.index = pd.to_datetime(data_df_update.index)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_UPDATE_COLUMNS, len(data_df_update.columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_UPDATE_ROWS, len(data_df_update))
        if isfile(file_current):
            shutil.move(file_current, file_previous)
        elif isfile(file_previous):
            os.remove(file_previous)
        data_df_previous = self.dataframe_read_pd(file_previous, engine=engine, dtype_backend=dtype_backend, index_col=0) \
            if isfile(file_previous) else pd.DataFrame()
        data_df_previous.index = pd.to_datetime(data_df_previous.index)
        for data_column in data_columns:
            if data_column not in data_df_previous:
                data_df_previous[data_column] = ""
        self.add_counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_COLUMNS, len(data_df_previous.columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_ROWS, len(data_df_previous))
        data_df_current = pd.concat([data_df_current, data_df_update])
        data_df_current = data_df_current[~data_df_current.index.duplicated(keep='last')]
        data_df_current = data_df_current[data_columns]
        if aggregate_function is not None:
            data_df_current = aggregate_function(data_df_current)
        data_df_current = data_df_current.sort_index()
        self.dataframe_write_pd(data_df_current, file_current)
        data_df_current = self.dataframe_read_pd(file_current, engine=engine, dtype_backend=dtype_backend, index_col=0)
        data_df_current.index = pd.to_datetime(data_df_current.index)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_CURRENT_COLUMNS, len(data_df_current.columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_CURRENT_ROWS, len(data_df_current))
        data_df_delta = pd.concat([data_df_current, data_df_previous])
        data_df_delta['Date'] = data_df_delta.index
        data_df_delta = data_df_delta.drop_duplicates(keep=False)
        data_df_delta = data_df_delta[~data_df_delta.index.duplicated(keep='first')]
        del data_df_delta['Date']
        data_df_delta.index.name = 'Date'
        data_df_delta = data_df_delta[data_columns]
        data_df_delta = data_df_delta.sort_index()
        self.dataframe_write_pd(data_df_delta, file_delta)
        if len(data_df_delta) == 0:
            data_df_delta = pd.DataFrame()
        self.add_counter(CTR_SRC_DATA, CTR_ACT_DELTA_COLUMNS, len(data_df_delta.columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_DELTA_ROWS, len(data_df_delta))
        self.print_log("StateCache loaded", started=started_time)
        return data_df_delta, data_df_current, data_df_previous

    def state_write(self):
        try:
            if not test(WRANGLE_DISABLE_FILE_UPLOAD):
                self.drive_sync(self.input_drive, self.input, check=True, download=False, upload=True)
                self.print_log("Directory [{}] uploaded to [https://drive.google.com/drive/folders/{}]"
                               .format(basename(self.input), self.input_drive))
        except Exception as exception:
            self.print_log("Directory [{}] failed to upload to [https://drive.google.com/drive/folders/{}]"
                           .format(self.input, self.input_drive), exception=exception)

    def drive_write(self, local_file, drive_dir, modified_time, service, drive_id=None):
        started_time = time.time()
        try:
            data = MediaFileUpload(local_file)
            metadata = {'modifiedTime': datetime.utcfromtimestamp(modified_time).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
            if not test(WRANGLE_DISABLE_FILE_UPLOAD):
                if drive_id is None:
                    metadata['name'] = basename(local_file)
                    metadata['parents'] = [drive_dir]
                    request = service.files().create(body=metadata, media_body=data).execute()
                else:
                    request = service.files().update(fileId=drive_id, body=metadata, media_body=data).execute()
                self.print_log("File [{}] uploaded to [https://drive.google.com/file/d/{}]"
                               .format(basename(local_file), request.get('id') if drive_id is None else drive_id),
                               started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_UPLOADED)
        except Exception as exception:
            self.print_log("File [{}] failed to upload to [https://drive.google.com/drive/folders/{}]"
                           .format(local_file, drive_dir), exception=exception)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)

    def sheet_read(self, file_cache, drive_key, sheet_name=None, sheet_data_start=1, sheet_load_secs=10, sheet_retry_max=5,
                   column_types={}, write_cache=False, print_head=PD_PRINT_ROWS, print_tail=PD_PRINT_ROWS,
                   engine=PD_ENGINE_DEFAULT, dtype_backend=PD_BACKEND_DEFAULT):
        started_time = time.time()
        data_df = None
        drive_url = "https://docs.google.com/spreadsheets/d/" + drive_key
        file_path = abspath("{}/_{}.csv".format(self.input, file_cache))
        if not write_cache and isfile(file_path):
            data_df = self.dataframe_read_pd(file_path, column_types, print_label=file_cache, engine=engine, dtype_backend=dtype_backend)
        if data_df is None:
            retries = 0
            caught_exception = None
            try:
                while retries < sheet_retry_max:
                    try:
                        retries += 1
                        spread = Spread(drive_url, sheet=0 if sheet_name is None else sheet_name)
                        spread_sheet_cells = spread._fix_merge_values(spread.sheet.get_all_values())[sheet_data_start - 1:]
                        self.print_log("DataFrame [{}] downloaded from [{}]".format(file_cache, drive_url), started=started_time)
                        data_df = self.dataframe_new_pd(
                            data=spread_sheet_cells[1:],
                            columns=spread_sheet_cells[:1][0] if len(spread_sheet_cells) > 0 else [],
                            column_types=column_types,
                            dropna_columns=True,
                            print_label=file_cache,
                            print_head=print_head,
                            print_tail=print_tail,
                            dtype_backend=dtype_backend
                        )
                        for data_df_col in data_df:
                            if len(data_df[data_df[data_df_col] == "Loading..."]) > 0:
                                data_df = None
                                raise ValueError("DataFrame [{}] loaded from sheet that is yet to finish rendering column [{}]"
                                                 .format(file_cache, data_df_col))
                        caught_exception = None
                        break
                    except ValueError as exception:
                        time.sleep(sheet_load_secs)
                        caught_exception = exception
                if caught_exception is not None:
                    raise caught_exception
            except Exception as exception:
                self.print_log("DataFrame [{}] unavailable at [{}]{}"
                               .format(file_cache, drive_url, "" if retries < sheet_retry_max else \
                    " after retrying [{}] times over [{}] seconds".format(sheet_retry_max, sheet_retry_max * sheet_load_secs)),
                               exception=exception)
        if data_df is None:
            data_df = self.dataframe_new_pd(column_types=column_types)
        else:
            if write_cache and len(data_df) > 0:
                self.dataframe_write_pd(data_df, file_path, write_index=False, print_label=file_cache)
        return data_df

    def sheet_write(self, data_df, drive_key, sheet_params={}):
        started_time = time.time()
        drive_url = "https://docs.google.com/spreadsheets/d/" + drive_key
        try:
            if not test(WRANGLE_DISABLE_FILE_UPLOAD):
                Spread(drive_url).df_to_sheet(data_df, **sheet_params)
                self.print_log("DataFrame uploaded to [{}]".format(drive_url), started=started_time)
                self.add_counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_COLUMNS, len(data_df.columns))
                self.add_counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_ROWS, len(data_df))
        except Exception as exception:
            self.print_log("DataFrame failed to upload to [{}]".format(drive_url), exception=exception)
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)

    def database_read(self, file_cache, flux_query, column_types={}, write_cache=False,
                      print_head=PD_PRINT_ROWS, print_tail=PD_PRINT_ROWS, engine=PD_ENGINE_DEFAULT, dtype_backend=PD_BACKEND_DEFAULT):
        started_time = time.time()
        data_df = None
        file_path = abspath("{}/_{}.csv".format(self.input, file_cache))
        if not write_cache and isfile(file_path):
            data_df = self.dataframe_read_pd(file_path, column_types, print_label=file_cache, engine=engine, dtype_backend=dtype_backend)
        if data_df is None:
            rows = []
            columns = []
            query_url = "http://{}:{}/api/v2/query?org={}".format(
                os.environ["INFLUXDB_IP_PROD"],
                os.environ["INFLUXDB_HTTP_PORT"],
                os.environ["INFLUXDB_ORG"],
            )
            try:
                response = requests.post(url=query_url, headers={
                    'Accept': 'application/csv',
                    'Content-type': 'application/vnd.flux',
                    'Authorization': 'Token {}'.format(os.environ["INFLUXDB_TOKEN"])
                }, data=flux_query.replace("\n", "").replace(" ", ""))
                if not response.ok:
                    raise SystemError("HTTP [{}] returned with response [{}] after query [{}]"
                                      .format(response.status_code, response.text.strip(), flux_query))
                table = response.text.strip().split("\n")
                if len(table) > 0:
                    columns = table[0].strip().split(",")[3:]
                    for row in table[1:]:
                        cols = row.strip().split(",")
                        if len(cols) > 4:
                            rows.append([parser.parse(cols[3])] + cols[4:])
                self.print_log("DataFrame [{}] downloaded from [{}]".format(file_cache, query_url), started=started_time)
            except Exception as exception:
                rows = []
                self.print_log("DataFrame [{}] unavailable at [{}]".format(file_cache, query_url), exception=exception)
            query_log = ["DataFrame [{}] query [{}]:".format(file_cache, flux_query.replace(" ", "").replace("\n", ""))]
            query_log.extend([line.strip() for line in flux_query.split("\n")])
            self.print_log(query_log)
            data_df = self.dataframe_new_pd(data=rows, columns=columns, column_types=column_types, print_label=file_cache,
                                            print_head=print_head, print_tail=print_tail, dtype_backend=dtype_backend)
        if write_cache and len(data_df) > 0:
            self.dataframe_write_pd(data_df, file_path, write_index=False, print_label=file_cache)
        return data_df

    def database_trunc(self):
        started_time = time.time()
        for bucket in [os.environ["INFLUXDB_BUCKET_DATA_PUBLIC"], os.environ["INFLUXDB_BUCKET_DATA_PRIVATE"]]:
            trunc_url = "http://{}:{}/api/v2/delete?org={}&bucket={}".format(
                os.environ["INFLUXDB_IP"],
                os.environ["INFLUXDB_HTTP_PORT"],
                os.environ["INFLUXDB_ORG"],
                bucket,
            )
            trunc_query = json.dumps({
                "start": "1900-01-01T00:00:00Z",
                "stop": (date.today() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "predicate": "_measurement=\"" + self.name.lower() + "\""
            })
            try:
                self.print_log("Measurement [{}] truncate pending at [{}]".format(self.name.lower(), trunc_url))
                response = post(url=trunc_url, headers={
                    'Accept': 'application/csv',
                    'Content-type': 'application/vnd.flux',
                    'Authorization': 'Token {}'.format(os.environ["INFLUXDB_TOKEN"])
                }, data=trunc_query, timeout=10 * 60)
                if not response.ok:
                    self.print_log("Measurement [{}] could not be truncated with query [{}] and HTTP code [{}] at [{}]"
                                   .format(self.name.lower(), trunc_query, response.status_code, trunc_url))
                else:
                    self.print_log("Measurement [{}] truncate executed at [{}]"
                                   .format(self.name.lower(), trunc_url), started=started_time)
            except Exception as exception:
                self.print_log("Measurement [{}] could not be truncated at [{}]"
                               .format(self.name.lower(), trunc_url), exception=exception)

    def dataframe_write_pd(self, data_df, local_path, write_index=True, print_label=None, print_head=PD_PRINT_ROWS,
                           print_tail=PD_PRINT_ROWS):
        started_time = time.time()
        data_df.to_csv(local_path, index=write_index, encoding='utf-8')
        return self.dataframe_print_pd(data_df, print_label=basename(local_path).split(".")[0].removeprefix("_").removeprefix("__") \
            if print_label is None else print_label,
                                       print_verb="written", print_suffix="to [{}]".format(local_path),
                                       print_head=print_head, print_tail=print_tail, started=started_time)

    def dataframe_read_pd(self, local_path, column_types={}, dropna_columns=False, fillna_str=False, print_label=None,
                          print_head=PD_PRINT_ROWS, print_tail=PD_PRINT_ROWS,
                          engine=PD_ENGINE_DEFAULT, dtype_backend=PD_BACKEND_DEFAULT, **kwargs):
        started_time = time.time()
        data_df = pd.read_csv(local_path, dtype="str", keep_default_na=False, engine=engine, dtype_backend=dtype_backend, **kwargs)
        data_df = self.dataframe_convert_types_pd(data_df, column_types=column_types,
                                                  dropna_columns=dropna_columns, fillna_str=fillna_str, dtype_backend=dtype_backend)
        return self.dataframe_print_pd(data_df, print_label=basename(local_path).split(".")[0].removeprefix("_").removeprefix("__") \
            if print_label is None else print_label,
                                       print_suffix="from [{}]".format(local_path), print_head=print_head,
                                       print_tail=print_tail, started=started_time)

    def dataframe_new(self, data=[], schema={}, dropna_columns=False, fillna_str=False, print_label=None,
                      print_suffix=None, print_compact=False, print_rows=PL_PRINT_ROWS, started=None):
        started_time = time.time() if started is None else started
        data_df = pl.DataFrame(
            data=data if len(data) > 0 else None,
            schema=schema if len(schema) > 0 else None
        )
        if len(data) > 0 or len(schema) > 0:
            self.dataframe_print(data_df, compact=(print_compact or len(data) == 0),
                                 print_label=print_label, print_suffix=print_suffix, print_rows=print_rows, started=started_time)
        return data_df

    def dataframe_new_pd(self, data=[], columns=[], column_types={}, dropna_columns=False, fillna_str=False, print_label=None,
                         print_suffix=None, print_head=PD_PRINT_ROWS, print_tail=PD_PRINT_ROWS, dtype_backend=no_default, started=None):
        started_time = time.time() if started is None else started
        column_names = OrderedDict()
        if len(data) == 0 or isinstance(data[0], list):
            if len(columns) == 0 and len(column_types) > 0:
                columns = list(column_types)
            if len(data) > 0 and len(data[0]) > 0:
                if len(columns) > len(data[0]):
                    columns = columns.copy()[:len(data[0])]
                elif len(columns) < len(data[0]):
                    columns = columns.copy()
                    columns.extend(["" for _ in range(0, len(data[0]) - len(columns))])
            for _column_index, _column_name in enumerate(columns):
                if _column_name == "":
                    column_names["Column {}".format(_column_index + 1)] = _column_name
                elif _column_name in column_names:
                    column_names["{} {}".format(_column_name, _column_index + 1)] = _column_name
                else:
                    column_names[_column_name] = _column_name
        column_type = None
        if len(data) == 0:
            if len(column_names) > 0:
                data = {}
                for column_name in column_names:
                    data[column_name] = pd.Series(dtype=column_types[column_name] if column_name in column_types else None)
        elif len(data[0]) > 0 and len(data[0]) == len(column_types) and len(set(column_types.values())) == 1:
            column_type = next(iter(column_types.values()))
        data_df = None
        for column_type_attempt in [column_type, None]:
            try:
                data_df = pd.DataFrame(
                    data=None if len(data) == 0 else data,
                    columns=None if len(column_names) == 0 else column_names.keys(),
                    dtype=column_type_attempt)
            except Exception as exception:
                self.print_log("DataFrame{} could not be cast as type [{}], leaving as default inferred types"
                               .format("" if print_label is None else " [{}]".format(print_label), column_type_attempt))
            if data_df is not None or column_type is None:
                break
        data_df = self.dataframe_convert_types_pd(data_df, column_types=column_types, dropna_columns=dropna_columns,
                                                  fillna_str=fillna_str, dtype_backend=dtype_backend)
        if len(data) > 0 or len(column_names) > 0:
            self.dataframe_print_pd(data_df, compact=(len(data) == 0), print_label=print_label, print_suffix=print_suffix,
                                    print_head=print_head, print_tail=print_tail, started=started_time)
        return data_df

    def dataframe_convert_types_pd(self, data_df, column_types={}, dropna_columns=False, fillna_str=False, dtype_backend=no_default):
        if len(data_df) > 0:
            data_df = data_df.apply(pd.to_numeric, errors='ignore')
            for column in data_df.select_dtypes(include=["object"]):
                data_df[column] = data_df[column].replace({pd.NA: np.nan, "": np.nan, "<NA>": np.nan})
            if dropna_columns:
                data_df = data_df.dropna(axis=1, how="all")
            if fillna_str:
                for column in data_df.select_dtypes(include=["object"]):
                    data_df[column] = data_df[column].fillna("")
            for data_column in column_types:
                if data_column in data_df:
                    try:
                        data_df[data_column] = data_df[data_column].astype(column_types[data_column])
                    except Exception as exception:
                        self.print_log("DataFrame column [{}] could not be cast as type [{}], leaving as existing type [{}]"
                                       .format(data_column, column_types[data_column], data_df[data_column].dtype))
            if dtype_backend != no_default:
                data_df = data_df.convert_dtypes(dtype_backend=dtype_backend)
        return data_df

    def dataframe_to_lineprotocol_pd(self, data_df, global_tags=None, print_label=None):
        started_time = time.time()
        lines = []
        if not test(WRANGLE_DISABLE_DATA_LINEPROTOCOL):
            if global_tags is None:
                global_tags = {}
            global_tags["source"] = "wrangle"
            global_tags["version"] = os.getenv("SERVICE_VERSION_COMPACT", "-1")
            try:
                if test(WRANGLE_ENABLE_DATA_SUBSET) and len(data_df) > 0:
                    data_df = data_df.sample(1, replace=True).sort_index()
                column_rename = {}
                for column in data_df.columns:
                    column_rename[column] = column.strip().replace(' ', '-').lower()
                    data_df[column] = pd.to_numeric(data_df[column], downcast='float')
                data_df = data_df.rename(columns=column_rename)
                data_df.index = pd.to_datetime(data_df.index)

                # TODO: Implement sec precision
                # lines = influxdb.DataFrameClient()._convert_dataframe_to_lines(
                #     data_df, self.name.lower(), tag_columns=[], global_tags=global_tags, time_precision="s")
                lines = influxdb.DataFrameClient()._convert_dataframe_to_lines(
                    data_df, self.name.lower(), tag_columns=[], global_tags=global_tags)

                self.dataframe_print_pd(data_df, print_label=print_label, print_verb="serialised",
                                        print_suffix="to [{:,}] lines".format(len(lines)), started=started_time)
                self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_COLUMNS, len(data_df.columns))
                self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_ROWS, len(data_df))
            except Exception as exception:
                self.print_log("DataFrame {} serialisation failed"
                               .format("" if print_label is None else " [{}]".format(print_label)),
                               data=self.dataframe_to_str_pd(data_df, compact=False),
                               exception=exception)
                self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)
        return lines

    def dataframe_to_str(self, data_df, compact=True, print_rows=PL_PRINT_ROWS):
        if compact:
            schema = []
            for column in data_df.schema:
                schema.append("{}({})".format(column, DataTypeClass._string_repr(data_df.schema[column])))
            return "[" + ", ".join(schema) + "]"
        else:
            with pl.Config(
                    tbl_rows=print_rows,
                    tbl_cols=-1,
                    fmt_str_lengths=50,
                    set_tbl_width_chars=10000,
                    set_fmt_float="full",
                    set_ascii_tables=True,
                    tbl_formatting="ASCII_FULL_CONDENSED",
                    set_tbl_hide_dataframe_shape=True,
            ):
                data_lines = data_df.__str__().split('\n')
                return data_lines

    def dataframe_to_str_pd(self, data_df, compact=True, print_head=PD_PRINT_ROWS, print_tail=PD_PRINT_ROWS):

        def _column(_compact, _name, _type):
            return "{}{}({})".format(_name, "" if _compact else " ", _type)

        data_dict = OrderedDict()
        data_dict[_column(compact, "Index" if data_df.index.name is None else data_df.index.name, data_df.index.dtype)] = data_df.index
        for column in data_df.columns:
            data_dict[_column(compact, column, data_df[column].dtype)] = data_df[column]
        if compact:
            return "[" + ",".join(data_dict.keys()) + "]"
        else:
            data_rows_truncated = False
            data_rows_index_head = []
            data_rows_index_tail = []
            if len(data_df) > 0:
                if (print_head + print_tail) >= len(data_df):
                    data_rows_index_head.extend([*range(0, len(data_df))])
                else:
                    data_rows_truncated = True
                    data_rows_index_head.extend([*range(0, print_head)])
                    data_rows_index_tail.extend([*range(len(data_df) - print_tail, len(data_df))])
            data_rows = [data_dict.keys()]
            data_df = data_df.copy(deep=False)
            data_df.insert(0, column=str(uuid.uuid4()), value=data_df.index)
            data_rows.extend(data_df.take(data_rows_index_head).astype(str).values.tolist())
            if data_rows_truncated:
                data_rows.extend([["..." for i in range(0, len(data_df.columns))]])
            data_rows.extend(data_df.take(data_rows_index_tail).astype(str).values.tolist())
            return tabulate(data_rows, tablefmt="outline").split('\n')

    def dataframe_print(self, data_df, messages=None, compact=False, print_label=None, print_verb="loaded", print_suffix=None,
                        print_rows=PL_PRINT_ROWS, started=None):
        if test(WRANGLE_ENABLE_LOG):
            if messages is None:
                messages = "DataFrame{} {} with [{:,}] columns and [{:,}] rows{}".format(
                    "" if print_label is None else " [{}]".format(print_label),
                    print_verb,
                    len(data_df.columns),
                    len(data_df),
                    "" if print_suffix is None else " {}".format(print_suffix),
                )
            self.print_log(messages, self.dataframe_to_str(data_df, compact, print_rows), started=started)
        return data_df

    def dataframe_print_pd(self, data_df, messages=None, compact=False, print_label=None, print_verb="loaded", print_suffix=None,
                           print_head=PD_PRINT_ROWS, print_tail=PD_PRINT_ROWS, started=None):
        if test(WRANGLE_ENABLE_LOG):
            if messages is None:
                messages = "DataFrame{} {} with [{:,}] columns and [{:,}] rows{}".format(
                    "" if print_label is None else " [{}]".format(print_label),
                    print_verb,
                    len(data_df.columns),
                    len(data_df),
                    "" if print_suffix is None else " {}".format(print_suffix),
                )
            self.print_log(messages, self.dataframe_to_str_pd(data_df, compact, print_head, print_tail), started=started)
        return data_df

    def file_list(self, file_dir, file_prefix):
        files = {}
        for file_name in os.listdir(file_dir):
            if file_name.startswith(file_prefix):
                file_path = join(file_dir, file_name)
                files[file_path] = True, True
                self.print_log("File [{}] found at [{}]".format(file_name, file_path))
        return files

    # noinspection PyMethodMayBeStatic
    def stdout_write(self, lines=None):
        if lines is not None:
            if isinstance(lines, str):
                print(lines)
            else:
                for line in lines:
                    if line:
                        self.stdout_write(line)
        sys.stdout.flush()

    def counter_write(self):
        values = []
        timestamp = time.time() * 10 ** 9
        for source in self.counters:
            for action in self.counters[source]:
                values.append("{}={}".format("{}_{}".format(source, action).lower().replace(" ", "_"),
                                             self.counters[source][action]))
        self.stdout_write("{},period=30m,type=metadata,unit=scalar {} {:.0f}"
                          .format(self.name.lower(), ",".join(values), timestamp))

    def __init__(self, name, input_drive):
        self.name = name
        self.reset_counters()
        self.input_drive = input_drive
        self.input = abspath(get_dir("data/{}".format(name.lower())))
