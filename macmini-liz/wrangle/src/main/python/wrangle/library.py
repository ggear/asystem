from __future__ import print_function

import collections
import copy
import glob
import hashlib
import io
import logging
import os
import os.path
import shutil
import ssl
import sys
import time
import traceback
import urllib2
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from datetime import datetime
from datetime import timedelta
from ftplib import FTP

import dropbox
import numpy as np
import pandas as pd
import yfinance as yf
from dateutil import parser
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
from gspread_pandas import Spread
from pandas.tseries.offsets import BDay

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

LINE_PROTOCOL_METADATA = "{},type=metadata,period=30m,unit=scalar {}={} {:.0f}"

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

pd.options.mode.chained_assignment = None
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)


def print_log(process, message, exception=None, level="debug"):
    if os.getenv('WRANGLE_ENABLE_LOG') == 'true':
        prefix = "{} [{}] [{}]: " \
            .format(level.upper() if exception is None else 'ERROR', process, datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        if type(message) is not list:
            message = [message]
        for line in message:
            if len(line) > 0:
                print(u"{}{}".format(prefix, line))
        if exception is not None:
            print("{}{}".format(prefix, ("\n" + prefix).join(traceback.format_exc(limit=2).splitlines())))


def get_file(file_name):
    if os.path.isfile(file_name):
        return file_name
    file_name = os.path.basename(file_name)
    working = os.path.dirname(__file__)
    paths = [
        "/root/{}".format(file_name),
        "{}/../../resources/{}".format(working, file_name),
        "{}/../../resources/config/{}".format(working, file_name),
        "{}/../../../../{}".format(working, file_name),
    ]
    for path in paths:
        if os.path.isfile(path):
            return path
    raise IOError("Could not find file [{}] in the usual places {}".format(file_name, paths))


def get_dir(dir_name):
    working = os.path.dirname(__file__)
    parent_paths = [
        "/asystem/runtime",
        "{}/../../../../../wrangle/target".format(working),
    ]
    for parent_path in parent_paths:
        if os.path.isdir(parent_path):
            path = os.path.abspath("{}/{}".format(parent_path, dir_name))
            if not os.path.isdir(path):
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


class Library(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def _run(self):
        pass

    def run(self):
        time_now = time.time()
        self.print_log("Starting ...")
        self._run()
        self.print_counters()
        self.print_log("Finished in [{:.3f}] sec".format(time.time() - time_now))

    def print_log(self, message, exception=None):
        print_log(self.name, message, exception)

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

    def http_download(self, url_file, local_file, check=True, force=False, ignore=False):
        local_file = os.path.abspath(local_file)
        if not force and not check and os.path.isfile(local_file):
            self.print_log("File [{}] cached at [{}]".format(os.path.basename(local_file), local_file))
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

            def get_modified(response):
                headers = response.info().getheaders("Last-Modified")
                if len(headers) > 0:
                    return int((datetime.strptime(headers[0], '%a, %d %b %Y %H:%M:%S GMT') -
                                datetime.utcfromtimestamp(0)).total_seconds())
                return None

            if not force and check and os.path.isfile(local_file):
                modified_timestamp_cached = int(os.path.getmtime(local_file))
                try:
                    request = urllib2.Request(url_file, headers=client)
                    request.get_method = lambda: 'HEAD'
                    response = urllib2.urlopen(request, context=ssl._create_unverified_context())
                    modified_timestamp = get_modified(response)
                    if modified_timestamp is not None:
                        if modified_timestamp_cached == modified_timestamp:
                            self.print_log("File [{}] cached at [{}]".format(os.path.basename(local_file), local_file))
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                            return True, False
                except:
                    pass
            try:
                response = urllib2.urlopen(urllib2.Request(url_file, headers=client), context=ssl._create_unverified_context())
                with open(local_file, 'wb') as output:
                    output.write(response.read())
                modified_timestamp = get_modified(response)
                if modified_timestamp is not None:
                    os.utime(local_file, (modified_timestamp, modified_timestamp))
                self.print_log("File [{}] downloaded to [{}]".format(os.path.basename(local_file), local_file))
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                return True, True
            except Exception as exception:
                if not ignore:
                    self.print_log("File [{}] not available at [{}]".format(os.path.basename(local_file), url_file), exception)
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return False, False

    def ftp_download(self, url_file, local_file, check=True, force=False, ignore=False):
        local_file = os.path.abspath(local_file)
        if not force and not check and os.path.isfile(local_file):
            self.print_log("File [{}] cached at [{}]".format(os.path.basename(local_file), local_file))
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return True, False
        else:
            url_server = url_file.replace("ftp://", "").split("/")[0]
            url_path = url_file.split(url_server)[-1]
            try:
                client = FTP(url_server)
                client.login()
                modified_timestamp = int((parser.parse(client.voidcmd("MDTM {}".format(url_path))[4:].strip()) -
                                          datetime.utcfromtimestamp(0)).total_seconds())
                if not force and check and os.path.isfile(local_file):
                    modified_timestamp_cached = int(os.path.getmtime(local_file))
                    if modified_timestamp_cached == modified_timestamp:
                        self.print_log("File [{}] cached at [{}]".format(os.path.basename(local_file), local_file))
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                        client.quit()
                        return True, False
                client.retrbinary("RETR {}".format(url_path), open(local_file, 'wb').write)
                os.utime(local_file, (modified_timestamp, modified_timestamp))
                self.print_log("File [{}] downloaded to [{}]".format(os.path.basename(local_file), local_file))
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                client.quit()
                return True, True
            except Exception as exception:
                if client is not None:
                    client.quit()
                self.print_log("File [{}] not available at [{}]".format(os.path.basename(local_file), url_file), exception)
                if not ignore:
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return False, False

    def stock_download(self, local_file, ticker, start, end, end_of_day='17:00', check=True, force=False, ignore=False):
        local_file = os.path.abspath(local_file)
        now = datetime.now()
        end_exclusive = datetime.strptime(end, '%Y-%m-%d').date() + timedelta(days=1)
        if start != end_exclusive:
            if not force and not check and os.path.isfile(local_file):
                self.print_log("File [{}: {} {}] cached at [{}]".format(os.path.basename(local_file), start, end, local_file))
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return True, False
            else:
                try:
                    if not force and check and os.path.isfile(local_file):
                        if now.year == int(end.split('-')[0]) and now.month == int(end.split('-')[1]):
                            end_data = datetime.strptime(pd.read_csv(local_file).values[-1][0], '%Y-%m-%d').date()
                            end_expected = BDay().rollback(now).date()
                            if now.date() == end_expected and now.strftime('%H:%M') < end_of_day:
                                end_expected = end_expected - timedelta(days=1)
                            if end_data == end_expected:
                                self.print_log("File [{}: {} {}] cached at [{}]"
                                               .format(os.path.basename(local_file), start, end, local_file))
                                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                                return True, False
                    data_df = yf.Ticker(ticker).history(start=start, end=end_exclusive, debug=False)
                    if now.year == int(end.split('-')[0]) and now.month == int(end.split('-')[1]) \
                            and data_df.index[-1].date() == now.date() and now.strftime('%H:%M') < end_of_day:
                        data_df = data_df[:-1]
                    if len(data_df) == 0:
                        raise Exception("No data returned from Yahoo! Finance history service")
                    data_df.to_csv(local_file)
                    modified_timestamp = int((datetime.strptime(pd.read_csv(local_file).values[-1][0], '%Y-%m-%d') +
                                              timedelta(hours=8) - datetime.utcfromtimestamp(0)).total_seconds())
                    os.utime(local_file, (modified_timestamp, modified_timestamp))
                    self.print_log("File [{}: {} {}] downloaded to [{}]".format(os.path.basename(local_file), start, end, local_file))
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                    return True, True
                except Exception as exception:
                    self.print_log("File not available for [{} - {} {}]"
                                   .format(ticker, start, end_exclusive), exception)
                    if not ignore:
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return False, False

    def dropbox_download(self, dropbox_dir, local_dir, check=True):

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
            local_files[os.path.basename(local_file)] = {
                "hash": file_hash(local_file) if check else None,
                "modified": int(os.path.getmtime(local_file)) if check else None
            }
        dropbox_files = {}
        service = dropbox.Dropbox(os.getenv('DROPBOX_TOKEN'))
        cursor = None
        while True:
            response = service.files_list_folder(dropbox_dir) if cursor is None else service.files_list_folder_continue(cursor)
            for dropbox_file in response.entries:
                dropbox_files[dropbox_file.name] = {
                    "id": dropbox_file.id.encode('ascii'),
                    "hash": dropbox_file.content_hash.encode('ascii'),
                    "modified": int((dropbox_file.client_modified - datetime.utcfromtimestamp(0)).total_seconds()),
                }
            if response.has_more:
                cursor = response.cursor
            else:
                break
        actioned_files = {}
        for dropbox_file in dropbox_files:
            file_actioned = False
            local_path = os.path.abspath("{}/{}".format(local_dir, dropbox_file))
            if dropbox_file not in local_files or (check and (
                    dropbox_files[dropbox_file]["modified"] != local_files[dropbox_file]["modified"] or
                    dropbox_files[dropbox_file]["hash"] != local_files[dropbox_file]["hash"]
            )):
                with open(local_path, "wb") as local_file:
                    metadata, response = service.files_download(path="{}/{}".format(dropbox_dir, dropbox_file))
                    local_file.write(response.content)

                os.utime(local_path, (dropbox_files[dropbox_file]["modified"], dropbox_files[dropbox_file]["modified"]))
                local_files[dropbox_file] = {
                    "hash": dropbox_files[dropbox_file]["hash"],
                    "modified": dropbox_files[dropbox_file]["modified"]
                }
                file_actioned = True
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                self.print_log("File [{}] downloaded to [{}]".format(dropbox_file, local_path))
            else:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                self.print_log("File [{}] cached at [{}]".format(dropbox_file, local_path))
            actioned_files[local_path] = True, file_actioned
        return collections.OrderedDict(sorted(actioned_files.items()))

    def drive_sync(self, drive_dir, local_dir, check=True, download=True, upload=False):
        def file_hash(file_name):
            hash_md5 = hashlib.md5()
            with open(file_name, "rb") as f:
                for block in iter(lambda: f.read(8 * 1024), b""):
                    hash_md5.update(block)
            return hash_md5.hexdigest()

        local_files = {}
        for local_file in glob.glob("{}/*".format(local_dir)):
            local_files[os.path.basename(local_file)] = {
                "hash": file_hash(local_file) if check else None,
                "modified": int(os.path.getmtime(local_file)) if check else None
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
                    "id": drive_file["id"].encode('ascii'),
                    "hash": drive_file["md5Checksum"].encode('ascii'),
                    "modified": int((datetime.strptime(drive_file["modifiedTime"], '%Y-%m-%dT%H:%M:%S.%fZ') -
                                     datetime.utcfromtimestamp(0)).total_seconds()),
                }
            token = response.get('nextPageToken')
            if not token:
                break
        actioned_files = {}
        if download:
            for drive_file in drive_files:
                file_actioned = False
                local_path = os.path.abspath("{}/{}".format(local_dir, drive_file))
                if drive_file not in local_files or (check and (
                        drive_files[drive_file]["modified"] > local_files[drive_file]["modified"]
                )):
                    request = service.files().get_media(fileId=drive_files[drive_file]["id"])
                    buffer_file = io.BytesIO()
                    downloader = MediaIoBaseDownload(buffer_file, request)
                    done = False
                    while not done:
                        _, done = downloader.next_chunk()
                    with open(local_path, 'wb') as local_file:
                        local_file.write(buffer_file.getvalue())
                    os.utime(local_path, (drive_files[drive_file]["modified"], drive_files[drive_file]["modified"]))
                    local_files[drive_file] = {
                        "hash": drive_files[drive_file]["hash"],
                        "modified": drive_files[drive_file]["modified"]
                    }
                    file_actioned = True
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                    self.print_log("File [{}] downloaded to [{}]".format(drive_file, local_path))
                else:
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                    self.print_log("File [{}] cached at [{}]".format(drive_file, local_path))
                actioned_files[local_path] = True, file_actioned
        if upload:
            for local_file in local_files:
                if not local_file.startswith("_"):
                    file_actioned = False
                    local_path = os.path.abspath("{}/{}".format(local_dir, local_file))
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
                                       .format(local_file, drive_files[local_file]["id"]))
                    actioned_files[local_path] = True, file_actioned
        return collections.OrderedDict(sorted(actioned_files.items()))

    def state_cache(self, data_df_update, file_prefix):
        file_delta = os.path.abspath("{}/__{}_Delta.csv".format(self.input, file_prefix))
        file_update = os.path.abspath("{}/__{}_Update.csv".format(self.input, file_prefix))
        file_current = os.path.abspath("{}/__{}_Current.csv".format(self.input, file_prefix))
        file_previous = os.path.abspath("{}/__{}_Previous.csv".format(self.input, file_prefix))
        if not os.path.isdir(self.input):
            os.makedirs(self.input)
        if os.getenv('WRANGLE_REPROCESS_ALL_FILES') == "true":
            if os.path.isfile(file_current):
                os.remove(file_current)
        data_df_current = pd.read_csv(file_current, index_col=0, dtype=str) if os.path.isfile(file_current) else pd.DataFrame()
        data_df_current.index = pd.to_datetime(data_df_current.index)
        data_df_current.index.name = 'Date'
        data_columns = data_df_current.columns.get_values().tolist()
        for data_column in data_df_update.columns.get_values().tolist():
            if data_column not in data_columns:
                data_columns.append(data_column)
        for data_column in data_columns:
            if data_column not in data_df_current:
                data_df_current[data_column] = np.nan
        data_df_update.index.name = 'Date'
        data_df_update.index = pd.to_datetime(data_df_update.index)
        data_df_update.sort_index().to_csv(file_update)
        data_df_update = pd.read_csv(file_update, index_col=0, dtype=str)
        data_df_update.index = pd.to_datetime(data_df_update.index)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_UPDATE_COLUMNS, len(data_df_update.columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_UPDATE_ROWS, len(data_df_update))
        if os.path.isfile(file_current):
            shutil.move(file_current, file_previous)
        elif os.path.isfile(file_previous):
            os.remove(file_previous)
        data_df_previous = pd.read_csv(file_previous, index_col=0, dtype=str) if os.path.isfile(file_previous) else pd.DataFrame()
        data_df_previous.index = pd.to_datetime(data_df_previous.index)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_COLUMNS, len(data_df_previous.columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_ROWS, len(data_df_previous))
        for data_column in data_columns:
            if data_column not in data_df_previous:
                data_df_previous[data_column] = ""
        self.print_log("File [{}] written to [{}]".format(os.path.basename(file_previous), file_previous))
        data_df_current = pd.concat([data_df_current, data_df_update], sort=True)
        data_df_current = data_df_current[~data_df_current.index.duplicated(keep='last')]
        data_df_current = data_df_current[data_columns]
        data_df_current.sort_index().to_csv(file_current)
        data_df_current = pd.read_csv(file_current, index_col=0, dtype=str)
        data_df_current.index = pd.to_datetime(data_df_current.index)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_CURRENT_COLUMNS, len(data_df_current.columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_CURRENT_ROWS, len(data_df_current))
        self.print_log("File [{}] written to [{}]".format(os.path.basename(file_current), file_current))
        self.print_log("File [{}] written to [{}]".format(os.path.basename(file_update), file_update))
        data_df_delta = data_df_current if len(data_df_previous) == 0 else \
            data_df_current.merge(data_df_previous, on=data_columns, how='outer', left_index=True, right_index=True, indicator=True) \
                .loc[lambda x: x['_merge'] != 'both'].drop('_merge', 1).drop_duplicates()
        data_df_delta = data_df_delta[data_columns]
        data_df_delta.sort_index().to_csv(file_delta)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_DELTA_COLUMNS, len(data_df_delta.columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_DELTA_ROWS, len(data_df_delta))
        self.print_log("File [{}] written to [{}]".format(os.path.basename(file_delta), file_delta))
        return data_df_delta, data_df_current, data_df_previous

    def state_write(self):
        try:
            self.drive_sync(self.input_drive, self.input, check=True, download=False, upload=True)
            self.print_log("Directory [{}] uploaded to [https://drive.google.com/drive/folders/{}]"
                           .format(os.path.basename(self.input), self.input_drive))
        except Exception as exception:
            self.print_log("Directory [{}] failed to upload to [https://drive.google.com/drive/folders/{}]"
                           .format(self.input, self.input_drive))

    def drive_write(self, local_file, drive_dir, modified_time, service, drive_id=None):
        try:
            data = MediaFileUpload(local_file)
            metadata = {'modifiedTime': datetime.utcfromtimestamp(modified_time).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
            if os.getenv('WRANGLE_DISABLE_EXTERNAL_SERVICES') is None or os.getenv('WRANGLE_DISABLE_EXTERNAL_SERVICES') == "false":
                if drive_id is None:
                    metadata['name'] = os.path.basename(local_file)
                    metadata['parents'] = [drive_dir]
                    request = service.files().create(body=metadata, media_body=data).execute()
                else:
                    request = service.files().update(fileId=drive_id, body=metadata, media_body=data).execute()
                self.print_log("File [{}] uploaded to [https://drive.google.com/file/d/{}]"
                               .format(os.path.basename(local_file), request.get('id') if drive_id is None else drive_id))
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_UPLOADED)
        except Exception as exception:
            self.print_log("File [{}] failed to upload to [https://drive.google.com/drive/folders/{}]"
                           .format(local_file, drive_dir), exception)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)

    def sheet_write(self, data_df, drive_url, sheet_params={}):
        try:
            if os.getenv('WRANGLE_DISABLE_EXTERNAL_SERVICES') is None or os.getenv('WRANGLE_DISABLE_EXTERNAL_SERVICES') == "false":
                Spread(drive_url).df_to_sheet(data_df, **sheet_params)
                self.print_log("Dataframe uploaded to [{}]".format(drive_url))
                self.add_counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_COLUMNS, len(data_df.columns))
                self.add_counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_ROWS, len(data_df))
        except Exception as exception:
            self.print_log("Dataframe failed to upload to [{}]".format(drive_url), exception)
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)

    def database_write(self, lines):
        if lines.strip():
            for line in lines.split('\n'):
                tokens = line.split(' ')
                if len(tokens) == 3:
                    self.stdout_write(line)
                    self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_ROWS, len(tokens[1].split(',')))
                else:
                    self.print_log("Database write failed with invalid line format [{}]".format(line))
                    self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)
        sys.stdout.flush()
        if self.get_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_ROWS) > 0 and \
                self.get_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_COLUMNS) == 0:
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_COLUMNS)

    def stdout_write(self, line):
        print(line)

    def counter_write(self):
        timestamp = time.time() * 10 ** 9
        for source in self.counters:
            for action in self.counters[source]:
                self.stdout_write(LINE_PROTOCOL_METADATA.format(
                    self.name.lower(),
                    "{}_{}".format(source, action).lower().replace(" ", "_"),
                    self.counters[source][action],
                    timestamp
                ))

    def __init__(self, name, input_drive):
        self.name = name
        self.reset_counters()
        self.input_drive = input_drive
        self.input = os.path.abspath(get_dir("data/{}".format(name.lower())))
