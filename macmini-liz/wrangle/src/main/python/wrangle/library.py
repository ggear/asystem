from __future__ import print_function

import copy
import datetime
import glob
import hashlib
import io
import os
import os.path
import shutil
import ssl
import traceback
import urllib2
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from datetime import datetime
from ftplib import FTP

import pandas as pd
from dateutil import parser
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
from gspread_pandas import Spread

CTR_LBL_PAD = '.'
CTR_LBL_WIDTH = 24
CTR_SRC_DATA = "Data"
CTR_SRC_FILES = "Files"
CTR_SRC_RESOURCES = "Resources"
CTR_ACT_PREVIOUS = "Previous"
CTR_ACT_CURRENT = "Current"
CTR_ACT_DELTA = "Delta"
CTR_ACT_SHEET = "Sheet"
CTR_ACT_DATABASE = "Database"
CTR_ACT_QUEUE = "Queue"
CTR_ACT_ERRORED = "Errored"
CTR_ACT_PROCESSED = "Processed"
CTR_ACT_SKIPPED = "Skipped"
CTR_ACT_DOWNLOADED = "Downloaded"
CTR_ACT_CACHED = "Cached"
CTR_ACT_PERSISTED = "Persisted"
CTR_ACT_UPLOADED = "Uploaded"


def print_log(process, message, exception=None):
    prefix = "WRANGLE_DEBUG [{}] [{}]: ".format(process, datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
    if type(message) is not list:
        message = [message]
    for line in message:
        if len(line) > 0:
            print("{}{}".format(prefix, line))
    if exception is not None:
        print("{}{}".format(prefix, ("\n" + prefix).join(traceback.format_exc(limit=2).splitlines())))


def get_file(file_name):
    working = os.path.dirname(__file__)
    paths = [
        "/root/{}".format(file_name),
        "{}/../../resources/{}".format(working, file_name),
        "{}/../../resources/config/{}".format(working, file_name),
    ]
    for path in paths:
        if os.path.isfile(path):
            return path
    raise IOError("Could not find file [{}] in the usual places {}".format(file_name, paths))


def get_dir(dir_name):
    working = os.path.dirname(__file__)
    parent_paths = [
        "/asystem/runtime",
        "{}/../../../../target".format(working),
    ]
    for parent_path in parent_paths:
        if os.path.isdir(parent_path):
            path = "{}/{}".format(parent_path, dir_name)
            if not os.path.isdir(path):
                os.makedirs(path)
            return path
    raise IOError("Could not find path in the usual places {}".format(parent_paths))


def load_profile(file_name):
    profile = {}
    for profile_line in file_name:
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
    def run(self):
        pass

    def print_log(self, message, exception=None):
        print_log(self.name, message, exception)

    def print_counters(self):
        self.print_log("Execution Summary:")
        for source in self.counters:
            for action in self.counters[source]:
                self.print_log("  {} {:3}"
                               .format("{} {} ".format(source, action).ljust(CTR_LBL_WIDTH, CTR_LBL_PAD), self.counters[source][action]))

    def add_counter(self, source, action, count=1):
        self.counters[source][action] += count

    def get_counter(self, source, action):
        return self.counters[source][action]

    def get_counters(self):
        return copy.deepcopy(self.counters)

    def reset_counters(self):
        self.counters = OrderedDict([
            (CTR_SRC_RESOURCES, OrderedDict([
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
                (CTR_ACT_PREVIOUS, 0),
                (CTR_ACT_CURRENT, 0),
                (CTR_ACT_DELTA, 0),
                (CTR_ACT_QUEUE, 0),
                (CTR_ACT_SHEET, 0),
                (CTR_ACT_DATABASE, 0),
                (CTR_ACT_ERRORED, 0),
            ])),
        ])

    def http_download(self, url_file, local_file, check=True, force=False, ignore=False):
        if not force and not check and os.path.isfile(local_file):
            self.print_log("File [{}] cached at [{}]".format(os.path.basename(local_file), local_file))
            self.counters[CTR_SRC_RESOURCES][CTR_ACT_CACHED] += 1
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
                            self.counters[CTR_SRC_RESOURCES][CTR_ACT_CACHED] += 1
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
                self.counters[CTR_SRC_RESOURCES][CTR_ACT_DOWNLOADED] += 1
                return True, True
            except Exception as exception:
                self.print_log("File [{}] not available at [{}]".format(os.path.basename(local_file), url_file, exception))
                if not ignore:
                    self.counters[CTR_SRC_RESOURCES][CTR_ACT_ERRORED] += 1
        return False, None

    def ftp_download(self, url_file, local_file, check=True, force=False, ignore=False):
        if not force and not check and os.path.isfile(local_file):
            self.print_log("File [{}] cached at [{}]".format(os.path.basename(local_file), local_file))
            self.counters[CTR_SRC_RESOURCES][CTR_ACT_CACHED] += 1
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
                        self.counters[CTR_SRC_RESOURCES][CTR_ACT_CACHED] += 1
                        client.quit()
                        return True, False
                client.retrbinary("RETR {}".format(url_path), open(local_file, 'wb').write)
                os.utime(local_file, (modified_timestamp, modified_timestamp))
                self.print_log("File [{}] downloaded to [{}]".format(os.path.basename(local_file), local_file))
                self.counters[CTR_SRC_RESOURCES][CTR_ACT_DOWNLOADED] += 1
                client.quit()
                return True, True
            except Exception as exception:
                if client is not None:
                    client.quit()
                self.print_log("File [{}] not available at [{}]".format(os.path.basename(local_file), url_file, exception))
                if not ignore:
                    self.counters[CTR_SRC_RESOURCES][CTR_ACT_ERRORED] += 1
        return False, None

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
                "hash": file_hash(local_file),
                "modified": int(os.path.getmtime(local_file))
            }
        drive_files = {}
        credentials = service_account.Credentials.from_service_account_file(
            get_file(".google_service_account.json"), scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=credentials)
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
                local_path = "{}/{}".format(local_dir, drive_file)
                if drive_file not in local_files or \
                        drive_files[drive_file]["hash"] != local_files[drive_file]["hash"] or \
                        (check and drive_files[drive_file]["modified"] != local_files[drive_file]["modified"]):
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
                    self.counters[CTR_SRC_RESOURCES][CTR_ACT_DOWNLOADED] += 1
                    self.print_log("File [{}] downloaded to [{}]".format(drive_file, local_path))
                else:
                    self.counters[CTR_SRC_RESOURCES][CTR_ACT_CACHED] += 1
                    self.print_log("File [{}] cached at [{}]".format(drive_file, local_path))
                actioned_files[drive_file] = True, file_actioned
        if upload:
            for local_file in local_files:
                file_actioned = False
                local_path = "{}/{}".format(local_dir, local_file)
                if local_file not in drive_files or \
                        drive_files[local_file]["hash"] != local_files[local_file]["hash"] or \
                        (check and drive_files[local_file]["modified"] != local_files[local_file]["modified"]):
                    request = service.files().create(
                        body={'name': local_file, 'parents': [drive_dir], 'modifiedTime':
                            datetime.utcfromtimestamp(local_files[local_file]["modified"]).strftime('%Y-%m-%dT%H:%M:%S.%fZ')},
                        media_body=MediaFileUpload(local_path)).execute()
                    file_actioned = True
                    self.counters[CTR_SRC_RESOURCES][CTR_ACT_UPLOADED] += 1
                    self.print_log("File [{}] uploaded to [{}]".format(local_file, request.get('id')))
                else:
                    self.counters[CTR_SRC_RESOURCES][CTR_ACT_PERSISTED] += 1
                    self.print_log("File [{}] persisted at [{}]".format(local_file, drive_files[local_file]["id"]))
                actioned_files[local_file] = True, file_actioned
        return actioned_files

    def drive_sync_delta(self, data_df_current, file_prefix):
        file_delta = "{}/{}_delta.csv".format(self.output, file_prefix)
        file_current = "{}/{}_current.csv".format(self.output, file_prefix)
        file_previous = "{}/{}_previous.csv".format(self.output, file_prefix)
        if not os.path.isdir(self.output):
            os.makedirs(self.output)
        if os.path.isfile(file_current):
            shutil.move(file_current, file_previous)
        data_df_current.to_csv(file_current)
        data_df_previous = pd.read_csv(file_previous, index_col=0) if os.path.isfile(file_previous) else pd.DataFrame()
        data_df_current = pd.read_csv(file_current, index_col=0)
        data_df_delta = data_df_current if len(data_df_previous) == 0 else \
            data_df_current.merge(data_df_previous, how='outer', indicator=True) \
                .loc[lambda x: x['_merge'] == 'left_only'].drop('_merge', 1)
        data_df_delta.to_csv(file_delta)
        self.counters[CTR_SRC_DATA][CTR_ACT_PREVIOUS] = len(data_df_previous)
        self.counters[CTR_SRC_DATA][CTR_ACT_CURRENT] = len(data_df_current)
        self.counters[CTR_SRC_DATA][CTR_ACT_DELTA] = len(data_df_delta)
        self.drive_sync(self.input_drive, self.input, check=True, download=False, upload=True)
        self.drive_sync(self.output_drive, self.output, check=False, download=False, upload=True)
        return data_df_delta

    def write_sheet(self, data_df, drive_url, sheet_params={}):
        Spread(drive_url).df_to_sheet(data_df, **sheet_params)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_SHEET, len(data_df))

    def write_database(self, line):
        if line.strip():
            print(line)
            self.add_counter(CTR_SRC_DATA, CTR_ACT_DATABASE)

    def __init__(self, name, input_drive, output_drive):
        self.name = name
        self.reset_counters()
        self.input_drive = input_drive
        self.output_drive = output_drive
        self.input = get_dir("data/{}/input".format(name.lower()))
        self.output = get_dir("data/{}/output".format(name.lower()))
