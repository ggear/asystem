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
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from enum import Enum, auto
from ftplib import FTP
from io import StringIO
from os.path import *
from typing import NamedTuple

import dropbox
import google
import numpy as np
import pandas as pd
import polars as pl
import polars.selectors as cs
import yfinance as yf
from dateutil import parser
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
from gspread_pandas import Spread
from pandas.api.extensions import no_default
from pandas.tseries.offsets import BDay
from polars.datatypes import DataTypeClass
from polars.exceptions import SchemaError
from tabulate import tabulate


class DownloadStatus(Enum):
    CACHED = auto()
    DOWNLOADED = auto()
    FAILED = auto()


class DownloadResult(NamedTuple):
    status: DownloadStatus
    file_path: str | None


@dataclass
class Config:
    log_level: str = "info"
    clean: bool = False
    disable_uploads: bool = False
    disable_downloads: bool = False


config = Config()

database = None

DATABASE_ENV_VARS = ("WRANGLE_DATABASE_HOST", "WRANGLE_DATABASE_PORT",
                     "WRANGLE_DATABASE_NAME", "WRANGLE_DATABASE_TOKEN")

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

logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

LOG_LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40, "fatal": 50}


def log_enabled(level):
    return LOG_LEVELS.get(level, 20) >= LOG_LEVELS.get(config.log_level, 20)


def print_log(process, messages, exception=None, level="info"):
    effective_level = "error" if exception is not None else level
    if not log_enabled(effective_level):
        return
    prefix = f"{effective_level.upper()} [{process}] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}]: "
    if type(messages) is not list:
        messages = [messages]
    for line in messages:
        if len(line) > 0:
            print(f"{prefix}{line}")
    if exception is not None:
        print(f"{prefix}{(chr(10) + prefix).join(traceback.format_exc().splitlines())}")


def database_open():
    global database
    if database is not None:
        database_close()
    if config.disable_uploads and config.disable_downloads:
        return
    missing = [name for name in DATABASE_ENV_VARS if not os.environ.get(name)]
    if missing:
        print_log("wrangle",
                  f"Database disabled: missing environment variable(s) [{', '.join(missing)}]",
                  level="warning")
        return
    try:
        from influxdb_client_3 import InfluxDBClient3
        database = InfluxDBClient3(
            host=f"http://{os.environ['WRANGLE_DATABASE_HOST']}:{os.environ['WRANGLE_DATABASE_PORT']}",
            token=os.environ["WRANGLE_DATABASE_TOKEN"],
            database=os.environ["WRANGLE_DATABASE_NAME"],
        )
        print_log("wrangle", f"Database connection opened to [{os.environ['WRANGLE_DATABASE_HOST']}:{os.environ['WRANGLE_DATABASE_PORT']}/{os.environ['WRANGLE_DATABASE_NAME']}]", level="debug")
    except Exception as exception:
        database = None
        print_log("wrangle", "Database disabled: connection failed", exception=exception, level="warning")


def database_close():
    global database
    if database is None:
        return
    try:
        database.close()
        print_log("wrangle", "Database connection closed", level="debug")
    except Exception as exception:
        print_log("wrangle", "Database close failed", exception=exception)
    database = None


def get_file(file_name):
    if isfile(file_name):
        return file_name
    file_name = basename(file_name)
    working = dirname(__file__)
    paths = [
        f"/root/{file_name}",
        f"/etc/telegraf/{file_name}",
        f"{working}/../../../resources/{file_name}",
        f"{working}/../../../resources/config/{file_name}",
        f"{working}/../../../../../{file_name}",
    ]
    for path in paths:
        if isfile(path):
            return path
    raise IOError(f"Could not find file [{file_name}] in the usual places {paths}")


def get_dir(dir_name):
    working = dirname(__file__)
    parent_paths = [
        "/asystem/runtime",
        f"{working}/../../../../../target",
    ]
    for parent_path in parent_paths:
        if isdir(parent_path):
            path = abspath(f"{parent_path}/{dir_name}")
            if not isdir(path):
                os.makedirs(path)
            return path
    raise IOError(f"Could not find path in the usual places {parent_paths}")


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

    def run(self):
        started_time = time.time()
        self.print_log("Starting ...")
        self._run()
        if not config.disable_uploads:
            self.drive_synchronise(self.input_drive, self.input, check=True, download=False, upload=True)
        for csv_path, csv_df in self._db_cache_dfs.items():
            self.csv_write(csv_df, csv_path)
        self.print_counters()
        self.print_log("Finished", started=started_time)

    def print_log(self, messages, data=None, started=None, exception=None, level="info"):
        effective_level = "error" if exception is not None else level
        if not log_enabled(effective_level):
            return
        if type(messages) is not list:
            messages = [messages]
        if started is not None:
            messages[-1] = messages[-1] + f" in [{time.time() - started:.3f}] sec"
        if data is not None:
            messages[-1] = messages[-1] + ": "
            if type(data) is list:
                messages.extend(data)
            else:
                messages[-1] = messages[-1] + data
        print_log(self.name, messages, exception, level=level)

    def print_counters(self):
        self.print_log("Execution Summary:")
        for source in self.counters:
            for action in self.counters[source]:
                self.print_log(f"     {f'{source} {action} '.ljust(CTR_LBL_WIDTH, CTR_LBL_PAD)} {self.counters[source][action]:8}")

    def add_counter(self, source, action, count=1):
        self.counters[source][action] += count

    def get_counter(self, source, action):
        return self.counters[source][action]

    def get_counters(self):
        return copy.deepcopy(self.counters)

    # noinspection PyAttributeOutsideInit
    def reset_counters(self):
        self._db_cache_dfs = {}
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
        label = basename(local_path).split(".")[0]
        if not force and not check and isfile(local_path):
            self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, local_path)
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
                                datetime(1970, 1, 1)).total_seconds())
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
                            self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                            return DownloadResult(DownloadStatus.CACHED, local_path)
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
                    self.print_log(f"File [{label}] HTTP downloaded file [{local_path}] modified timestamp set failed [{modified_timestamp}]", exception=exception)
                self.print_log(f"File [{label}] downloaded to [{local_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                return DownloadResult(DownloadStatus.DOWNLOADED, local_path)
            except Exception as exception:
                if not ignore:
                    self.print_log(f"File [{label}] not available at [{url_file}]", exception=exception)
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return DownloadResult(DownloadStatus.FAILED, None)

    def ftp_download(self, url_file, local_path, check=True, force=False, ignore=False):
        started_time = time.time()
        local_path = abspath(local_path)
        label = basename(local_path).split(".")[0]
        if not force and not check and isfile(local_path):
            self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, local_path)
        else:
            url_server = url_file.replace("ftp://", "").split("/")[0]
            url_path = url_file.split(url_server)[-1]
            client = None
            try:
                client = FTP(url_server)
                client.login()
                modified_timestamp = int((parser.parse(client.voidcmd(f"MDTM {url_path}")[4:].strip()) -
                                          datetime(1970, 1, 1)).total_seconds())
                if not force and check and isfile(local_path):
                    modified_timestamp_cached = int(getmtime(local_path))
                    if modified_timestamp_cached == modified_timestamp:
                        self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                        client.quit()
                        return DownloadResult(DownloadStatus.CACHED, local_path)
                if not exists(dirname(local_path)):
                    os.makedirs(dirname(local_path))
                client.retrbinary(f"RETR {url_path}", open(local_path, 'wb').write)
                try:
                    os.utime(local_path, (modified_timestamp, modified_timestamp))
                except Exception as exception:
                    self.print_log(f"File [{label}] FTP downloaded file [{local_path}] modified timestamp set failed [{modified_timestamp}]", exception=exception)
                self.print_log(f"File [{label}] downloaded to [{local_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                client.quit()
                return DownloadResult(DownloadStatus.DOWNLOADED, local_path)
            except Exception as exception:
                if client is not None:
                    client.quit()
                self.print_log(f"File [{label}] not available at [{url_file}]", exception=exception)
                if not ignore:
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return DownloadResult(DownloadStatus.FAILED, None)

    def stock_download(self, local_path, ticker, start, end, end_of_day='17:00', check=True, force=False, ignore=True):
        started_time = time.time()
        local_path = abspath(local_path)
        label = basename(local_path).split(".")[0]
        now = datetime.now()
        end_exclusive = datetime.strptime(end, '%Y-%m-%d').date() + timedelta(days=1)
        if start != end_exclusive:
            if not force and not check and isfile(local_path):
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, local_path)
            else:
                try:
                    if not force and check and isfile(local_path):
                        if now.year == int(end.split('-')[0]) and now.month == int(end.split('-')[1]):
                            data_df = self.csv_read(local_path)
                            if len(data_df) > 0:
                                end_data = data_df.row(-1)[0]
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
                                    self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
                                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                                    return DownloadResult(DownloadStatus.CACHED, local_path)
                            else:
                                self.print_log(f"File [{label}] cached (but empty) at [{local_path}]", started=started_time)
                                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                                return DownloadResult(DownloadStatus.CACHED, local_path)
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
                            self.print_log(f"File [{label}] stock query returned no data for ticker [{ticker}] between [{start}] and [{end_exclusive}]")
                        else:
                            raise Exception(f"File [{label}] stock query returned no data for ticker [{ticker}] between [{start}] and [{end_exclusive}]")
                    if not exists(dirname(local_path)):
                        os.makedirs(dirname(local_path))
                    data_df.insert(loc=0, column='Date', value=data_df.index.strftime('%Y-%m-%d'))
                    if len(data_df) > 0 and isfile(local_path):
                        prior_df = self.csv_read(local_path)
                        if len(prior_df) == len(data_df):
                            prior_last = prior_df.row(-1)[0]
                            prior_last = datetime.strptime(prior_last, '%Y-%m-%d').date() \
                                if isinstance(prior_last, str) else prior_last
                            new_last = datetime.strptime(data_df['Date'].iloc[-1], '%Y-%m-%d').date()
                            if prior_last == new_last:
                                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
                                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                                return DownloadResult(DownloadStatus.CACHED, local_path)
                    self.csv_write(pl.from_pandas(data_df), local_path, print_verb="downloaded", started=started_time)
                    if len(data_df) > 0:
                        modified = datetime.strptime(str(data_df.values[-1][0]), '%Y-%m-%d').date()
                        modified_timestamp = int(
                            (modified + timedelta(hours=8) - datetime(1970, 1, 1).date()).total_seconds())
                        try:
                            os.utime(local_path, (modified_timestamp, modified_timestamp))
                        except Exception as exception:
                            self.print_log(f"File [{label}] stock query file [{local_path}] modified timestamp set failed [{modified_timestamp}]", exception=exception)
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                    return DownloadResult(DownloadStatus.DOWNLOADED, local_path)
                except Exception as exception:
                    self.print_log(f"File [{label}] stock query failed for ticker [{ticker}] between [{start}] and [{end_exclusive}]", exception=exception)
                    if not ignore:
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return DownloadResult(DownloadStatus.FAILED, None)

    def database_download(self, query_name, query_string, start=None, end=None, check=True, force=False, ignore=True):
        started_time = time.time()
        local_path = abspath(f"{self.input}/_Database_{query_name}.csv")
        if config.disable_downloads or database is None:
            if isfile(local_path):
                self.print_log(f"File [{query_name}] cached at [{local_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, local_path)
            self.print_log(f"File [{query_name}] query skipped: downloads disabled and no cache available")
            if not ignore:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
            return DownloadResult(DownloadStatus.FAILED, None)
        if not force and not check and isfile(local_path):
            self.print_log(f"File [{query_name}] cached at [{local_path}]", started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, local_path)
        if not force and check and isfile(local_path):
            data_df = self.csv_read(local_path, print_rows=-1)
            if len(data_df) > 0:
                data_start = data_df.head(1).rows()[0][0]
                data_end = data_df.tail(1).rows()[0][0]
                if (start is None or start >= data_start) and (end is None or end <= data_end):
                    self.print_log(f"File [{query_name}] cached at [{local_path}]", started=started_time)
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                    return DownloadResult(DownloadStatus.CACHED, local_path)
        try:
            arrow_table = database.query(query=query_string, language="sql")
            data_df = pl.from_arrow(arrow_table)
            if isinstance(data_df, pl.Series):
                data_df = data_df.to_frame()
            if data_df is None or len(data_df) == 0:
                if ignore:
                    self.print_log(f"File [{query_name}] query returned no data")
                    return DownloadResult(DownloadStatus.DOWNLOADED, local_path)
                raise Exception(f"File [{query_name}] query returned no data")
            self.csv_write(data_df, local_path, print_verb="queried", started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
            return DownloadResult(DownloadStatus.DOWNLOADED, local_path)
        except Exception as exception:
            self.print_log(f"File [{query_name}] query failed", exception=exception, started=started_time)
            if not ignore:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return DownloadResult(DownloadStatus.FAILED, None)

    def bank_download(self, file_cache, data="accounts", check=True, force=False):
        started_time = time.time()
        file_path = abspath(f"{self.input}/_Bank_{file_cache}.csv")
        if not force and not check and isfile(file_path):
            self.print_log(f"File [{file_cache}] cached at [{file_path}]", started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, file_path)
        if config.disable_downloads:
            if isfile(file_path):
                self.print_log(f"File [{file_cache}] cached at [{file_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, file_path)
            self.print_log(f"File [{file_cache}] query skipped: downloads disabled and no cache available")
            return DownloadResult(DownloadStatus.FAILED, None)
        token = os.environ.get("REDBARK_TOKEN", "")
        base_url = "https://api.redbark.co"
        req_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        def _request(path):
            req = urllib.request.Request(f"{base_url}{path}", headers=req_headers)
            response = urllib.request.urlopen(req, context=ssl._create_unverified_context())
            return json.loads(response.read().decode())

        def _has_more(result):
            pagination = result.get("pagination", result)
            return bool(pagination.get("hasMore", pagination.get("has_more", False)))

        def _all_accounts():
            rows, offset = [], 0
            while True:
                result = _request(f"/v1/accounts?limit=200&offset={offset}")
                rows.extend(result.get("data", []))
                if not _has_more(result):
                    break
                offset += len(result.get("data", []))
            return rows

        try:
            if data == "accounts":
                rows = _all_accounts()
                data_df = pl.DataFrame(rows) if rows else self.dataframe_new()
            elif data == "balances":
                account_ids = [a["id"] for a in _all_accounts()]
                rows = []
                for i in range(0, len(account_ids), 100):
                    result = _request(f"/v1/balances?accountIds={','.join(account_ids[i:i + 100])}")
                    rows.extend(result.get("data", []))
                data_df = pl.DataFrame(rows) if rows else self.dataframe_new()
            elif data == "transactions":
                accounts = _all_accounts()
                connection_ids = list(dict.fromkeys(a["connectionId"] for a in accounts if "connectionId" in a))
                rows = []
                for connection_id in connection_ids:
                    tx_offset = 0
                    while True:
                        result = _request(f"/v1/transactions?connectionId={connection_id}&limit=500&offset={tx_offset}")
                        rows.extend(result.get("data", []))
                        if not _has_more(result):
                            break
                        tx_offset += len(result.get("data", []))
                data_df = pl.DataFrame(rows) if rows else self.dataframe_new()
            elif data == "categories":
                result = _request("/v1/categories")
                rows = result.get("categories", [])
                data_df = pl.DataFrame(rows) if rows else self.dataframe_new()
            else:
                raise ValueError(f"Unknown bank data type [{data}]")
            if len(data_df) > 0:
                new_csv = data_df.sort(data_df.columns[0]).write_csv()
                new_hash = hashlib.md5(new_csv.encode()).hexdigest()
                if not force and check and isfile(file_path):
                    with open(file_path, 'r') as f:
                        if hashlib.md5(f.read().encode()).hexdigest() == new_hash:
                            self.print_log(f"File [{file_cache}] cached at [{file_path}]", started=started_time)
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                            return DownloadResult(DownloadStatus.CACHED, file_path)
                if not exists(dirname(file_path)):
                    os.makedirs(dirname(file_path))
                with open(file_path, 'w') as f:
                    f.write(new_csv)
                self.print_log(f"File [{file_cache}] downloaded to [{file_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                return DownloadResult(DownloadStatus.DOWNLOADED, file_path)
            return DownloadResult(DownloadStatus.DOWNLOADED, file_path)
        except Exception as exception:
            self.print_log(f"File [{file_cache}] download failed", exception=exception)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
            return DownloadResult(DownloadStatus.FAILED, None)

    def _sheet_cache_cleanup(self, name, current_version):
        pattern = abspath(f"{self.input}/_Sheet_{name}_v*.csv")
        for file_path in glob.glob(pattern):
            filename = basename(file_path)
            prefix = f"_Sheet_{name}_v"
            version_str = filename[len(prefix):-len(".csv")]
            if version_str.isdigit() and int(version_str) <= current_version - 2:
                os.remove(file_path)
                self.print_log(f"File [{name}] deleted old cached version [{file_path}]")

    def sheet_download(self, drive_key, workbook_name, sheet_name=None, sheet_start_row=1, sheet_load_secs=10, sheet_retry_max=5,
                       read_cache=True, write_cache=False, print_rows=PL_PRINT_ROWS):
        started_time = time.time()
        drive_url = "https://docs.google.com/spreadsheets/d/" + drive_key
        drive_version = None
        try:
            drive_version = build('drive', 'v3', credentials=Spread(drive_url).client.auth, cache_discovery=False) \
                .files().get(fileId=drive_key, fields='version').execute().get('version')
        except Exception as exception:
            self.print_log(f"Failed to get Drive version of sheet [{drive_url}]", exception=exception, level="error")
        name = workbook_name if sheet_name is None else f"{workbook_name}_{sheet_name}"
        if drive_version is not None:
            file_path = abspath(f"{self.input}/_Sheet_{name}_v{drive_version}.csv")
            self._sheet_cache_cleanup(name, int(drive_version))
            if isfile(file_path):
                self.print_log(f"File [{workbook_name}] cached at [{file_path}]", started=started_time)
                return DownloadResult(DownloadStatus.CACHED, file_path)
        else:
            prefix = f"_Sheet_{name}_v"
            versioned_files = sorted(
                [(int(basename(p)[len(prefix):-len(".csv")]), p)
                 for p in glob.glob(abspath(f"{self.input}/{prefix}*.csv"))
                 if basename(p)[len(prefix):-len(".csv")].isdigit()],
                reverse=True
            )
            if versioned_files:
                _, file_path = versioned_files[0]
                self.print_log(f"File [{workbook_name}] cached at [{file_path}]", started=started_time)
                return DownloadResult(DownloadStatus.CACHED, file_path)
            file_path = abspath(f"{self.input}/_Sheet_{name}.csv")
            if read_cache and not write_cache and isfile(file_path):
                self.print_log(f"File [{workbook_name}] cached at [{file_path}]", started=started_time)
                return DownloadResult(DownloadStatus.CACHED, file_path)
        file_path = abspath(f"{self.input}/_Sheet_{name}.csv") if drive_version is None else abspath(f"{self.input}/_Sheet_{name}_v{drive_version}.csv")
        retries = 0
        caught_exception = None

        class SheetStillLoadingError(Exception):
            pass

        try:
            while retries < sheet_retry_max:
                try:
                    retries += 1
                    spread = Spread(drive_url, sheet=0 if sheet_name is None else sheet_name)
                    spread_sheet_cells = spread._fix_merge_values(spread.sheet.get_all_values())[sheet_start_row - 1:]
                    data_df = self.dataframe_new(
                        data=spread_sheet_cells[1:],
                        orient="row",
                        print_label=workbook_name,
                        print_rows=-1
                    )
                    if len(spread_sheet_cells) > 0:
                        columns = []
                        for (default, named) in zip(data_df.columns, spread_sheet_cells[:1][0]):
                            columns.append(named if named != "" else default)
                        data_df.columns = columns
                    data_df = data_df \
                        .with_columns([pl.when(pl.col(pl.Utf8) == "#N/A").then(None) \
                                      .otherwise(pl.col(pl.Utf8)).name.keep()]) \
                        .with_columns([pl.when(pl.col(pl.Utf8).str.starts_with("$"))
                                      .then(pl.col(pl.Utf8).str.replace_all(r"(?i)\$|,", "")) \
                                      .otherwise(pl.col(pl.Utf8)).name.keep()]) \
                        .with_columns([pl.when(pl.col(pl.Utf8).str.starts_with("£")) \
                                      .then(pl.col(pl.Utf8).str.replace_all(r"(?i)£|,", "")) \
                                      .otherwise(pl.col(pl.Utf8)).name.keep()]) \
                        .with_columns([pl.when(pl.col(pl.Utf8).str.len_chars() == 0).then(None) \
                                      .otherwise(pl.col(pl.Utf8)).name.keep()])
                    data_df = data_df.select(
                        [column.name for column in data_df if not (column.null_count() == data_df.height)])
                    for column in data_df.columns:
                        if len(data_df.filter(pl.col(column) == "Loading...")) > 0:
                            data_df = None
                            raise SheetStillLoadingError(
                                f"DataFrame [{workbook_name}] loaded from sheet that is yet to finish rendering column [{column}]")
                    self.csv_write(data_df, file_path, print_label=workbook_name, print_rows=-1)
                    self.dataframe_print(data_df, print_label=workbook_name, print_verb="downloaded",
                                         print_suffix=f"from [{drive_url}][{workbook_name}{'' if sheet_name is None else f':{sheet_name}'}]",
                                         print_rows=print_rows, started=started_time)
                    caught_exception = None
                    break
                except SheetStillLoadingError as exception:
                    time.sleep(sheet_load_secs)
                    caught_exception = exception
            if caught_exception is not None:
                raise caught_exception
        except Exception as exception:
            self.print_log(f"DataFrame [{workbook_name}] unavailable at [{drive_url}]"
                           + ("" if retries < sheet_retry_max
                              else f" after retrying [{sheet_retry_max}] times over [{sheet_retry_max * sheet_load_secs}] seconds"),
                           exception=exception)
            return DownloadResult(DownloadStatus.FAILED, None)
        return DownloadResult(DownloadStatus.DOWNLOADED, file_path)

    def sheet_upload(self, data_df, drive_key, workbook_name, sheet_name=None, sheet_start_row=1, sheet_start_column="A",
                     print_label=None, print_rows=PL_PRINT_ROWS):
        started_time = time.time()
        drive_url = "https://docs.google.com/spreadsheets/d/" + drive_key
        name = workbook_name if sheet_name is None else f"{workbook_name}_{sheet_name}"
        try:
            data_df_pd = data_df.to_pandas()
            drive_version = None
            if not config.disable_uploads:
                spread = Spread(drive_url)
                spread.df_to_sheet(data_df_pd, index=False, sheet=sheet_name, start=f"{sheet_start_column}{sheet_start_row}", replace=True)
                try:
                    drive_version = build('drive', 'v3', credentials=spread.client.auth, cache_discovery=False) \
                        .files().get(fileId=drive_key, fields='version').execute().get('version')
                except Exception as exception:
                    self.print_log(f"Failed to get Drive version after upload of [{drive_url}]", exception=exception, level="error")
            suffix = f"_v{drive_version}" if drive_version is not None else ""
            file_path = abspath(f"{self.input}/_Sheet_{name}{suffix}.csv")
            self.csv_write(data_df, file_path)
            if drive_version is not None:
                self._sheet_cache_cleanup(name, int(drive_version))
            self.dataframe_print(data_df, print_label=print_label, print_verb="uploaded",
                                 print_suffix=f"to [{drive_url}][{workbook_name}{'' if sheet_name is None else f':{sheet_name}'}]",
                                 started=started_time, print_rows=print_rows)
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_COLUMNS, len(data_df.columns))
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_ROWS, len(data_df))
        except Exception as exception:
            self.print_log(f"DataFrame failed to upload to [{drive_url}]", exception=exception)
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)

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
        for local_file in glob.glob(f"{local_dir}/*"):
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
                    "modified": int((dropbox_file.client_modified - datetime(1970, 1, 1)).total_seconds()),
                }
            if response.has_more:
                cursor = response.cursor
            else:
                break
        self.print_log(f"Directory [{basename(local_dir)}] listed [{len(dropbox_files)}] files from [https://www.dropbox.com/home/{dropbox_dir}]", started=started_time)
        started_time = time.time()
        actioned_files = {}
        for dropbox_file in dropbox_files:
            started_time_file = time.time()
            file_actioned = False
            local_path = abspath(f"{local_dir}/{dropbox_file}")
            label = basename(local_path).split(".")[0]
            if dropbox_file not in local_files or (check and (
                    dropbox_files[dropbox_file]["modified"] != local_files[dropbox_file]["modified"] or
                    dropbox_files[dropbox_file]["hash"] != local_files[dropbox_file]["hash"]
            )):
                if not exists(dirname(local_path)):
                    os.makedirs(dirname(local_path))
                with open(local_path, "wb") as local_file:
                    metadata, response = service.files_download(path=f"{dropbox_dir}/{dropbox_file}")
                    local_file.write(response.content)
                try:
                    os.utime(local_path,
                             (dropbox_files[dropbox_file]["modified"], dropbox_files[dropbox_file]["modified"]))
                except Exception as exception:
                    self.print_log(f"File [{label}] downloaded file [{local_path}] modified timestamp set failed [{dropbox_files[dropbox_file]['modified']}]", exception=exception)
                local_files[dropbox_file] = {
                    "hash": dropbox_files[dropbox_file]["hash"],
                    "modified": dropbox_files[dropbox_file]["modified"]
                }
                file_actioned = True
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                self.print_log(f"File [{label}] downloaded to [{local_path}]", started=started_time_file)
            else:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time_file)
            actioned_files[local_path] = True, file_actioned
        self.print_log(f"Directory [{basename(local_dir).title()}] downloaded [{len(actioned_files)}] files from [https://www.dropbox.com/home/{dropbox_dir}]", started=started_time)
        return collections.OrderedDict(sorted(actioned_files.items()))

    def drive_synchronise(self, drive_dir, local_dir, check=True, download=True, upload=False):
        started_time = time.time()

        def file_hash(file_name):
            hash_md5 = hashlib.md5()
            with open(file_name, "rb") as f:
                for block in iter(lambda: f.read(8 * 1024), b""):
                    hash_md5.update(block)
            return hash_md5.hexdigest()

        actioned_files = {}
        local_files = {}
        for local_file in glob.glob(f"{local_dir}/*"):
            local_files[basename(local_file)] = {
                "hash": file_hash(local_file) if check else None,
                "modified": int(getmtime(local_file)) if check else None
            }
        drive_files = {}
        credentials = google.oauth2.service_account.Credentials.from_service_account_file(
            get_file(".google_service_account.json"), scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
        token = None
        while True:
            response = (service.files()
                        .list(q=f"'{drive_dir}' in parents", spaces='drive',
                              fields='nextPageToken, files(id, name, modifiedTime, md5Checksum)',
                              pageToken=token).execute())
            for drive_file in response.get('files', []):
                drive_files[drive_file["name"]] = {
                    "id": drive_file["id"],
                    "hash": drive_file["md5Checksum"],
                    "modified": int((datetime.strptime(drive_file["modifiedTime"], '%Y-%m-%dT%H:%M:%S.%fZ') -
                                     datetime(1970, 1, 1)).total_seconds()),
                }
            token = response.get('nextPageToken')
            if not token:
                break
        self.print_log(f"Directory [{basename(local_dir)}] listed [{len(drive_files)}] files from [https://drive.google.com/drive/folders/{drive_dir}]", started=started_time)
        started_time = time.time()
        for drive_file in drive_files:
            started_time_file = time.time()
            file_actioned = False
            local_path = abspath(f"{local_dir}/{drive_file}")
            label = basename(local_path).split(".")[0]
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
                        self.print_log(f"File [{label}] downloaded file [{local_path}] modified timestamp set failed [{drive_files[drive_file]['modified']}]", exception=exception)
                    local_files[drive_file] = {
                        "hash": drive_files[drive_file]["hash"],
                        "modified": drive_files[drive_file]["modified"]
                    }
                    file_actioned = True
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                    self.print_log(f"File [{label}] downloaded to [{local_path}]", started=started_time_file)
            else:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time_file)
            actioned_files[local_path] = True, file_actioned
        if upload:
            for local_file in local_files:
                if not local_file.startswith("_"):
                    started_time_file = time.time()
                    file_actioned = False
                    local_path = abspath(f"{local_dir}/{local_file}")
                    label = basename(local_path).split(".")[0]
                    if local_file not in drive_files or (check and (
                            drive_files[local_file]["modified"] != local_files[local_file]["modified"] or
                            drive_files[local_file]["hash"] != local_files[local_file]["hash"]
                    )):
                        try:
                            data = MediaFileUpload(local_file)
                            drive_id = drive_files[local_file]["id"] if local_file in drive_files else None
                            metadata = {'modifiedTime': datetime.fromtimestamp(
                                local_files[local_file]["modified"], timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
                            if not config.disable_uploads:
                                if drive_id is None:
                                    metadata['name'] = basename(local_file)
                                    metadata['parents'] = [drive_dir]
                                    request = service.files().create(body=metadata, media_body=data).execute()
                                else:
                                    request = service.files().update(fileId=drive_id, body=metadata,
                                                                     media_body=data).execute()
                            file_actioned = True
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_UPLOADED)
                            self.print_log(f"File [{label}] uploaded to [https://drive.google.com/file/d/{request.get('id') if drive_id is None else drive_id}]", started=started_time_file)
                        except Exception as exception:
                            self.print_log(f"File [{label}] failed to upload to [https://drive.google.com/drive/folders/{drive_dir}]", exception=exception)
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
                    else:
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_PERSISTED)
                        self.print_log(f"File [{label}] verified at [https://drive.google.com/file/d/{drive_files[local_file]['id']}]", started=started_time_file)
                    actioned_files[local_path] = True, file_actioned
        self.print_log(f"Directory [{basename(local_dir).title()}] synchronised [{len(actioned_files)}] files from [https://drive.google.com/drive/folders/{drive_dir}]", started=started_time)
        return collections.OrderedDict(sorted(actioned_files.items()))

    def state_cache(self, data_df_update, aggregate_function=None, key_columns=None):
        """Maintain an incremental time-series cache across runs.

        Merges ``data_df_update`` into the persisted current state, producing four CSV files
        alongside the data files:

        * ``__<Name>_Update.csv``   — the raw update rows supplied this run (after aggregate)
        * ``__<Name>_Current.csv``  — the full accumulated dataset (previous current + update)
        * ``__<Name>_Previous.csv`` — a copy of the current from the immediately preceding run
        * ``__<Name>_Delta.csv``    — rows that differ between previous and current (changed + new)

        Schema unification: the unified schema is the union of all columns from update and
        current, in update-column order with any extra current columns appended.  Columns
        present in current but absent from update are carried forward as null in the update
        frame.  Columns present in update but absent in current are backfilled as null in the
        current frame.

        Duplicate Date values in ``data_df_update`` are resolved with ``keep="last"`` (last
        occurrence by input order wins).  For dates present in both update and current, the
        update value takes precedence.

        Delta detection uses whole-row equality: a row is included in delta if and only if the
        (Date, value-columns) tuple differs between previous and current.

        If ``aggregate_function`` is provided it is applied to the incoming update and then to
        the fully merged current.  It must accept and return a Polars DataFrame and must
        preserve the ``Date`` column as the first column.

        Configuration flags (``library.config``):
        * ``disable_downloads=True`` — skip all processing; return an empty delta
          and the cached current as-is (no files are written).
        * ``clean=True`` — delete the current file before processing,
          forcing a full rebuild (previous will be empty after this run).

        Args:
            data_df_update: Polars DataFrame whose first column must be named ``Date`` and
                typed ``pl.Date``.  May be empty, in which case the current state is preserved
                and delta is empty.
            aggregate_function: Optional callable ``(pl.DataFrame) -> pl.DataFrame`` applied
                to the update and to the merged current.

        Returns:
            Tuple of ``(delta, current, previous)`` Polars DataFrames, all sorted by Date.
        """
        started_time = time.time()
        key_columns = key_columns if key_columns is not None else ["Date"]
        aggregate_function_wrapped = (lambda _data_df: _data_df) if aggregate_function is None \
            else (lambda _data_df: aggregate_function(_data_df) if len(_data_df) > 0 else _data_df)
        file_delta = abspath(f"{self.input}/__{self.name.title()}_Delta.csv")
        file_update = abspath(f"{self.input}/__{self.name.title()}_Update.csv")
        file_current = abspath(f"{self.input}/__{self.name.title()}_Current.csv")
        file_previous = abspath(f"{self.input}/__{self.name.title()}_Previous.csv")
        if not isdir(self.input):
            os.makedirs(self.input)
        if not config.disable_downloads and config.clean:
            if isfile(file_current):
                os.remove(file_current)
        if len(data_df_update) > 0:
            if len(data_df_update.columns) == 0 or data_df_update.columns[0] != "Date" or data_df_update.dtypes[0] != pl.Date:
                raise SchemaError(f"DataFrame requires first column of parameter [data_df_update] "
                                  f"to be named [Date], found [{data_df_update.columns[0]}] and of type [date], found [{self.dataframe_type_to_str(data_df_update.dtypes[0])}]")
        else:
            data_df_update = self.dataframe_new(schema={"Date": pl.Date},
                                                print_label=f"{self.name.title()}_Update")
        if config.disable_downloads:
            data_df_current = self.csv_read(file_current) \
                if isfile(file_current) else self.dataframe_new(schema={"Date": pl.Date},
                                                                print_label=f"{self.name.title()}_Current")
            self.print_log("DataFrame [State_Caches] created ignoring updates", started=started_time)
            data_df_current = data_df_current.sort(key_columns)
            return self.dataframe_new(schema=data_df_current.schema), data_df_current, data_df_current
        data_df_update = data_df_update.filter(pl.col("Date").is_not_null())
        data_df_update = aggregate_function_wrapped(data_df_update)
        data_df_current = self.csv_read(file_current) \
            if isfile(file_current) else self.dataframe_new(schema=data_df_update.schema,
                                                            print_label=f"{self.name.title()}_Current")
        data_schema_update_column_count = len(data_df_update.columns)
        data_schema = OrderedDict()
        for (data_column, data_type) in zip(data_df_update.columns, data_df_update.dtypes):
            data_schema[data_column] = data_type
        for (data_column, data_type) in zip(data_df_current.columns, data_df_current.dtypes):
            if data_column not in data_schema:
                data_schema[data_column] = data_type
                data_df_update = data_df_update.with_columns(
                    pl.lit(None).cast(data_schema[data_column]).alias(data_column))
        data_df_update = data_df_update.select(data_schema.keys()).with_columns(pl.col("Date").cast(pl.Date)).sort(
            key_columns)
        for data_column in data_schema:
            if data_column not in data_df_current:
                data_df_current = data_df_current.with_columns(
                    pl.lit(None).cast(data_schema[data_column]).alias(data_column))
            elif data_df_current[data_column].dtype != data_schema[data_column]:
                data_df_current = data_df_current.with_columns(
                    pl.col(data_column).cast(data_schema[data_column], strict=False))
        data_df_current = data_df_current.select(data_schema.keys()).with_columns(pl.col("Date").cast(pl.Date)).sort(
            key_columns)
        self.csv_write(data_df_update, file_update)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_UPDATE_COLUMNS, data_schema_update_column_count - len(key_columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_UPDATE_ROWS, len(data_df_update))
        if isfile(file_current):
            shutil.move(file_current, file_previous)
        elif isfile(file_previous):
            os.remove(file_previous)
        data_df_previous = self.csv_read(file_previous) \
            if isfile(file_previous) else self.dataframe_new(schema=data_schema,
                                                             print_label=f"{self.name.title()}_Previous")
        for data_column in data_schema:
            if data_column not in data_df_previous:
                data_df_previous = data_df_previous.with_columns(
                    pl.lit(None).cast(data_schema[data_column]).alias(data_column))
        data_df_previous = data_df_previous.select(data_schema.keys())
        self.add_counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_COLUMNS, len(data_df_previous.columns) - len(key_columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_ROWS, len(data_df_previous))
        data_df_current = pl.concat([data_df_current, data_df_update]) \
            .select(data_schema.keys()).unique(subset=key_columns, keep="last").sort(key_columns)
        data_df_current = aggregate_function_wrapped(data_df_current)
        for data_column, data_type in zip(data_df_current.columns, data_df_current.dtypes):
            if data_column in data_df_previous.columns and data_df_previous[data_column].dtype != data_type:
                data_df_previous = data_df_previous.with_columns(
                    pl.col(data_column).cast(data_type, strict=False))
        data_df_current = data_df_current.select(data_schema.keys())
        self.csv_write(data_df_current, file_current)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_CURRENT_COLUMNS, len(data_df_current.columns) - len(key_columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_CURRENT_ROWS, len(data_df_current))
        data_df_delta = pl.concat([data_df_previous, data_df_current]).select(data_schema.keys())
        data_df_delta = data_df_delta.filter(data_df_delta.is_duplicated().not_()).unique(subset=key_columns,
                                                                                          keep="last").sort(key_columns)
        self.csv_write(data_df_delta, file_delta)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_DELTA_COLUMNS,
                         len(data_schema) - len(key_columns) if data_schema_update_column_count > len(key_columns) else 0)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_DELTA_ROWS, len(data_df_delta))
        self.print_log("DataFrame [State_Caches] created", started=started_time)
        return data_df_delta.sort(key_columns), data_df_current.sort(key_columns), data_df_previous.sort(key_columns)

    def excel_read(self, local_path, schema={}, sheet_name=0, header_rows=0, skip_rows=0, na_values=[],
                   drop_na_cols=True,
                   drop_na_rows=True, float_round_places=6, print_label=None, print_rows=PL_PRINT_ROWS):
        started_time = time.time()
        data_df_pd = pd.read_excel(local_path, sheet_name=sheet_name, header=header_rows, skiprows=skip_rows,
                                   na_values=na_values)
        if drop_na_cols:
            data_df_pd = data_df_pd.dropna(axis=1, how="all")
        if drop_na_rows:
            data_df_pd = data_df_pd.dropna(axis=0, how="all")
        data_df = pl.from_pandas(data_df_pd, schema_overrides=schema if len(schema) > 0 else None) \
            .with_columns(cs.float().round(float_round_places))
        return self.dataframe_print(data_df,
                                    print_label=basename(local_path).split(".")[0].removeprefix("__").removeprefix("_") \
                                        if print_label is None else print_label,
                                    print_suffix=f"from [{local_path}]", print_rows=print_rows,
                                    started=started_time)

    def csv_write(self, data_df, local_path, print_prefix="File", print_label=None, print_verb="written",
                  print_rows=PL_PRINT_ROWS, started=None):
        started_time = time.time() if started is None else started
        data_df.write_csv(local_path)
        return self.dataframe_print(data_df,
                                    print_label=basename(local_path).split(".")[0].removeprefix("__").removeprefix("_") \
                                        if print_label is None else print_label, print_prefix=print_prefix,
                                    print_verb=print_verb,
                                    print_suffix=f"to [{local_path}]", print_rows=print_rows,
                                    started=started_time)

    def csv_read(self, local_path, schema={}, print_label=None, print_verb="loaded", print_rows=PL_PRINT_ROWS):
        started_time = time.time()
        data_df = pl.read_csv(local_path, schema_overrides=schema if len(schema) > 0 else None,
                              try_parse_dates=True, raise_if_empty=False, infer_schema_length=None)
        return self.dataframe_print(data_df,
                                    print_label=basename(local_path).split(".")[0].removeprefix("__").removeprefix("_") \
                                        if print_label is None else print_label, print_verb=print_verb,
                                    print_suffix=f"from [{local_path}]", print_rows=print_rows,
                                    started=started_time)

    def dataframe_new(self, data=[], schema={}, orient=None,
                      print_label=None, print_suffix=None, print_compact=False, print_rows=PL_PRINT_ROWS, started=None):
        started_time = time.time() if started is None else started
        data_df = pl.DataFrame(
            data=data if len(data) > 0 else None,
            schema=schema if len(schema) > 0 else None,
            orient=orient,
            nan_to_null=True,
        )
        if len(data) > 0 or len(schema) > 0:
            self.dataframe_print(data_df, compact=print_compact,
                                 print_label=print_label, print_suffix=print_suffix, print_rows=print_rows,
                                 started=started_time)
        return data_df

    def dataframe_to_lineprotocol(self, data_df, tags=None, print_label=None, chunk_rows=5000):
        started_time = time.time()
        if tags is None:
            tags = {}
        tags["source"] = "wrangle"
        if len(data_df.columns) <= 1 or len(data_df) == 0:
            return
        if data_df.select(pl.sum_horizontal(pl.all().is_null().sum())).rows()[0][0] > 0:
            raise Exception(
                "Dataframe contains null values which should be purged before line protocol serialisation")
        renamed_columns = ["timestamp"] + [column.strip().replace(' ', '-').lower() for column in
                                           data_df.columns[1:]]
        data_df = data_df.rename(dict(zip(data_df.columns, renamed_columns))) \
            .with_columns(pl.col("timestamp").cast(pl.Datetime).dt.epoch() * 1000)
        prefix = self.name.lower() + "," + ",".join([f"{tag}={tags[tag]}" for tag in tags]) + " "
        line_expressions = [pl.lit(prefix)]
        for column in data_df.columns[1:]:
            if len(line_expressions) > 1:
                line_expressions.append(pl.lit(","))
            line_expressions.extend([pl.lit(f"{column}="), pl.col(column)])
        line_expressions.extend([pl.lit(" "), pl.col("timestamp")])
        total_rows = len(data_df)
        emitted = 0
        for offset in range(0, total_rows, chunk_rows):
            chunk = data_df.slice(offset, chunk_rows)
            series = chunk.lazy().select(pl.concat_str(line_expressions)).collect().to_series()
            for line in series:
                yield line
                emitted += 1
        self.dataframe_print(data_df, print_label=print_label, print_verb="serialised", print_suffix=f"to [{emitted:,}] lines", started=started_time)
        self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_COLUMNS, len(data_df.columns))
        self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_ROWS, total_rows)

    def database_upload(self, data_df, tags=None, print_label=None, chunk_rows=5000):
        if len(data_df.columns) <= 1 or len(data_df) == 0:
            return
        if config.disable_uploads or database is None:
            for _ in self.dataframe_to_lineprotocol(data_df, tags=tags, print_label=print_label, chunk_rows=chunk_rows):
                pass
            if config.disable_uploads:
                tags_used = {k: v for k, v in (tags or {}).items() if k != "source"}
                tag_suffix = f" [{','.join(f'{k}={v}' for k, v in tags_used.items())}]" if tags_used else ""
                csv_path = abspath(f"{self.input}/_Database_{self.name}.csv")
                date_col = data_df.columns[0]
                fmt = '%Y-%m-%d' if data_df.dtypes[0] == pl.Date else '%Y-%m-%d %H:%M:%S'
                csv_df = data_df \
                    .rename({col: f"{col}{tag_suffix}" for col in data_df.columns[1:]}) \
                    .with_columns(pl.col(date_col).cast(pl.Datetime).dt.strftime(fmt).alias(date_col))
                if csv_path in self._db_cache_dfs:
                    csv_df = self._db_cache_dfs[csv_path].join(csv_df, on=date_col, how="full", coalesce=True).sort(date_col)
                self._db_cache_dfs[csv_path] = csv_df
            return
        try:
            buffer = []
            for line in self.dataframe_to_lineprotocol(data_df, tags=tags, print_label=print_label, chunk_rows=chunk_rows):
                buffer.append(line)
                if len(buffer) >= chunk_rows:
                    database.write(record=buffer, write_precision="ms")
                    buffer = []
            if buffer:
                database.write(record=buffer, write_precision="ms")
        except Exception as exception:
            self.print_log(f"DataFrame{'' if print_label is None else f' [{print_label}]'} write failed", exception=exception)
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)

    def dataframe_type_to_str(self, dtype):
        return DataTypeClass._string_repr(dtype)

    def dataframe_to_str(self, data_df, compact=True, print_rows=PL_PRINT_ROWS):
        if compact:
            schema = []
            for column in data_df.schema:
                schema.append(f"{column}({self.dataframe_type_to_str(data_df.schema[column])})")
            return "[" + ", ".join(schema) + "]"
        else:
            with pl.Config(
                    tbl_rows=print_rows,
                    tbl_cols=-1,
                    fmt_str_lengths=50,
                    set_tbl_width_chars=30000,
                    set_fmt_float="full",
                    set_ascii_tables=True,
                    tbl_formatting="ASCII_FULL_CONDENSED",
                    set_tbl_hide_dataframe_shape=True,
            ):
                data_lines = str(data_df).split('\n')
                return data_lines

    def dataframe_print(self, data_df, messages=None, compact=False, print_prefix="DataFrame", print_label=None,
                        print_verb="created", print_suffix=None, print_rows=PL_PRINT_ROWS, started=None):
        if not log_enabled("info"):
            return data_df
        if print_rows >= 0:
            if messages is None:
                messages = (f"{print_prefix}{'' if print_label is None else f' [{print_label}]'}"
                            f" {print_verb} with [{len(data_df.columns):,}] columns and [{len(data_df):,}] rows"
                            f"{'' if print_suffix is None else f' {print_suffix}'}")
            self.print_log(messages,
                           None if print_rows == 0 else self.dataframe_to_str(data_df, compact, print_rows),
                           started=started)
        return data_df

    def file_list(self, file_dir, file_prefix):
        files = {}
        for file_name in os.listdir(file_dir):
            if file_name.startswith(file_prefix):
                file_path = join(file_dir, file_name)
                files[file_path] = True, True
                self.print_log(f"File [{file_name}] found at [{file_path}]")
        return files

    def counter_write(self):
        if config.disable_uploads or database is None:
            return
        values = []
        timestamp_ms = int(time.time() * 1000)
        for source in self.counters:
            for action in self.counters[source]:
                values.append(f"{f'{source}_{action}'.lower().replace(' ', '_')}={self.counters[source][action]}i")
        line = f"{self.name.lower()},type=metadata,period=30m,unit=scalar,source=wrangle {','.join(values)} {timestamp_ms}"
        try:
            database.write(record=line, write_precision="ms")
        except Exception as exception:
            self.print_log("Counter write failed", exception=exception)

    def __init__(self, name, input_drive):
        self.name = name
        self.reset_counters()
        self.input_drive = input_drive
        self.input = abspath(get_dir(f"data/{name.lower()}"))
