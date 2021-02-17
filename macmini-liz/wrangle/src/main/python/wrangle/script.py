from __future__ import print_function

import copy
import glob
import hashlib
import io
import os
import os.path
import ssl
import traceback
import urllib2
from abc import ABCMeta, abstractmethod
from collections import OrderedDict

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

CTR_LBL_PAD = '.'
CTR_LBL_WIDTH = 24
CTR_SRC_DATA = "Data"
CTR_SRC_FILES = "Files"
CTR_SRC_RESOURCES = "Resources"
CTR_ACT_PREVIOUS = "Previous"
CTR_ACT_CURRENT = "Current"
CTR_ACT_DELTA = "Delta"
CTR_ACT_ERRORED = "Errored"
CTR_ACT_PROCESSED = "Processed"
CTR_ACT_SKIPPED = "Skipped"
CTR_ACT_DOWNLOADED = "Downloaded"
CTR_ACT_CACHED = "Cached"
CTR_ACT_UPLOADED = "Uploaded"


def print_log(process, message, exception=None):
    prefix = "WRANGLE_DEBUG [{}]: ".format(process)
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


class Script(object):
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

    def drive_sync(self, drive_dir, local_dir, direction="down"):
        def file_md5sum(file_name):
            file_hash = hashlib.md5()
            with open(file_name, "rb") as f:
                for block in iter(lambda: f.read(8 * 1024), b""):
                    file_hash.update(block)
            return file_hash.hexdigest()

        local_files = {}
        downloaded_files = []
        for file_name in glob.glob("{}/*".format(local_dir)):
            local_files[os.path.basename(file_name)] = {"hash": file_md5sum(file_name)}
        credentials = service_account.Credentials.from_service_account_file(
            get_file(".google_service_account.json"), scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=credentials)
        token = None
        while True:
            response = service.files().list(q="'{}' in parents".format(drive_dir), spaces='drive',
                                            fields='nextPageToken, files(id, name, md5Checksum)', pageToken=token).execute()
            for drive_file in response.get('files', []):
                local_path = "{}/{}".format(local_dir, drive_file["name"])
                if drive_file["name"] not in local_files or drive_file["md5Checksum"] != local_files[drive_file["name"]]["hash"]:
                    done = False
                    downloaded_files.append(drive_file["name"])
                    request = service.files().get_media(fileId=drive_file["id"])
                    buffer_file = io.BytesIO()
                    downloader = MediaIoBaseDownload(buffer_file, request)
                    while not done:
                        _, done = downloader.next_chunk()
                    with open(local_path, 'wb') as local_file:
                        local_file.write(buffer_file.getvalue())
                    self.counters[CTR_SRC_RESOURCES][CTR_ACT_DOWNLOADED] += 1
                    self.print_log("File [{}] downloaded to [{}]".format(drive_file["name"], local_path))
                else:
                    self.counters[CTR_SRC_RESOURCES][CTR_ACT_CACHED] += 1
                    self.print_log("File [{}] cached at [{}]".format(drive_file["name"], local_path))
            token = response.get('nextPageToken', None)
            if token is None:
                break
        return downloaded_files

    def http_download(self, url_file, local_file, force=False):
        available = False
        if not force and os.path.isfile(local_file):
            self.print_log("File [{}] cached at [{}]".format(os.path.basename(local_file), local_file))
            available = True
        else:
            try:
                month_xls = urllib2.urlopen(urllib2.Request(url_file, headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 '
                                  'Safari/537.11',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
                    'Accept-Encoding': 'none',
                    'Accept-Language': 'en-US,en;q=0.8',
                    'Connection': 'keep-alive'
                }), context=ssl._create_unverified_context())
                with open(local_file, 'wb') as output:
                    output.write(month_xls.read())
                self.print_log("File [{}] downloaded to [{}]".format(os.path.basename(local_file), local_file))
                self.counters[CTR_SRC_RESOURCES][CTR_ACT_DOWNLOADED] += 1
                available = True
            except Exception as exception:
                self.print_log("File [{}] not available at [{}]".format(os.path.basename(local_file), url_file, exception))
        return available

    def fs_write(self, data_df, local_file):
        data_df.to_csv(local_file)
        self.counters[CTR_SRC_DATA][CTR_ACT_CURRENT] = len(data_df)
        self.print_log("File [{}] written to [{}]".format(os.path.basename(local_file), local_file))

    def lineprotocol_print(self, lineprotocol):
        print(lineprotocol)

    def __init__(self, name):
        self.name = name
        self.counters = OrderedDict([
            (CTR_SRC_RESOURCES, OrderedDict([
                (CTR_ACT_DOWNLOADED, 0),
                (CTR_ACT_CACHED, 0),
                (CTR_ACT_UPLOADED, 0),
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
                (CTR_ACT_ERRORED, 0),
            ])),
        ])
        self.input = get_dir("data/{}/input".format(name.lower()))
        self.output = get_dir("data/{}/output".format(name.lower()))
