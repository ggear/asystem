import collections
import glob
import hashlib
import io
import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from datetime import timezone
from ftplib import FTP
from os.path import exists, getmtime

import dropbox
import google
import polars as pl
import yfinance as yf
from dateutil import parser
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from gspread_pandas import Spread
from pandas.tseries.offsets import BDay

from . import database as _database
from ._contract import ContractMixin
from .config import *
from .logger import dataframe_print as _dataframe_print

logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)


class SourcesMixin(ContractMixin):

    def http_download(self, url_file: str, local_path: str,
                      check: bool = True, force: bool = False, ignore: bool = False) -> DownloadResult:
        started_time = time.time()
        local_path = abspath(local_path)
        label = basename(local_path).split(".")[0]
        effective_force = force or config.force_downloads
        if config.disable_downloads:
            if isfile(local_path):
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, local_path)
            return DownloadResult(DownloadStatus.FAILED, None)
        if not effective_force and not check and isfile(local_path):
            self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, local_path)
        client = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
            'Accept': 'text/html,application/xhtml+xml,application/xml,text/csv,application/zip;q=0.9,*/*;q=0.8',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
            'Accept-Encoding': 'none',
            'Accept-Language': 'en-US,en;q=0.8',
            'Connection': 'keep-alive'
        }

        def get_modified(headers):
            modified_header = headers.get("Last-Modified")
            if modified_header:
                return int((datetime.strptime(modified_header, '%a, %d %b %Y %H:%M:%S GMT') -
                            datetime(1970, 1, 1)).total_seconds())
            return None

        if not effective_force and check and isfile(local_path):
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
            response = urllib.request.urlopen(urllib.request.Request(url_file, headers=client), context=ssl._create_unverified_context())
            if not exists(dirname(local_path)):
                os.makedirs(dirname(local_path))
            with open(local_path, 'wb') as local_file:
                local_file.write(response.read())
            modified_timestamp = get_modified(response.headers)
            try:
                if modified_timestamp is not None:
                    os.utime(local_path, (modified_timestamp, modified_timestamp))
            except Exception as exception:
                self.print_log(
                    f"File [{label}] HTTP downloaded file [{local_path}] modified timestamp set failed [{modified_timestamp}]",
                    exception=exception,
                )
            self.print_log(f"File [{label}] downloaded to [{local_path}]", started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
            return DownloadResult(DownloadStatus.DOWNLOADED, local_path)
        except Exception as exception:
            if not ignore:
                self.print_log(f"File [{label}] not available at [{url_file}]", exception=exception)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return DownloadResult(DownloadStatus.FAILED, None)

    def ftp_download(
            self,
            url_file: str,
            local_path: str,
            check: bool = True,
            force: bool = False,
            ignore: bool = False,
    ) -> DownloadResult:
        started_time = time.time()
        local_path = abspath(local_path)
        label = basename(local_path).split(".")[0]
        effective_force = force or config.force_downloads
        if config.disable_downloads:
            if isfile(local_path):
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, local_path)
            return DownloadResult(DownloadStatus.FAILED, None)
        if not effective_force and not check and isfile(local_path):
            self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, local_path)
        url_server = url_file.replace("ftp://", "").split("/")[0]
        url_path = url_file.split(url_server)[-1]
        client = None
        try:
            client = FTP(url_server)
            client.login()
            modified_timestamp = int((parser.parse(client.voidcmd(f"MDTM {url_path}")[4:].strip()) - datetime(1970, 1, 1)).total_seconds())
            if not effective_force and check and isfile(local_path):
                modified_timestamp_cached = int(getmtime(local_path))
                if modified_timestamp_cached == modified_timestamp:
                    self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                    client.quit()
                    return DownloadResult(DownloadStatus.CACHED, local_path)
            if not exists(dirname(local_path)):
                os.makedirs(dirname(local_path))
            with open(local_path, 'wb') as local_file:
                client.retrbinary(f"RETR {url_path}", local_file.write)
            try:
                os.utime(local_path, (modified_timestamp, modified_timestamp))
            except Exception as exception:
                self.print_log(
                    f"File [{label}] FTP downloaded file [{local_path}] modified timestamp set failed [{modified_timestamp}]",
                    exception=exception,
                )
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

    def stock_download(
            self,
            local_path: str,
            ticker: str,
            start: str,
            end: str,
            end_of_day: str = '17:00',
            check: bool = True,
            force: bool = False,
            ignore: bool = True,
    ) -> DownloadResult:
        started_time = time.time()
        local_path = abspath(local_path)
        label = basename(local_path).split(".")[0]
        effective_force = force or config.force_downloads
        if config.disable_downloads:
            if isfile(local_path):
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, local_path)
            return DownloadResult(DownloadStatus.FAILED, None)
        now = datetime.now()
        end_exclusive = datetime.strptime(end, '%Y-%m-%d').date() + timedelta(days=1)
        if start != end_exclusive:
            if not effective_force and not check and isfile(local_path):
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, local_path)
            else:
                try:
                    if not effective_force and check and isfile(local_path):
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
                    data_df.index = data_df.index.tz_localize(None)
                    if "Capital Gains" in data_df.columns:
                        data_df = data_df.drop(columns=["Capital Gains"])
                    if now.year == int(end.split('-')[0]) and now.month == int(end.split('-')[1]) \
                            and len(data_df) > 0 and data_df.index[-1].date() == now.date() \
                            and now.strftime('%H:%M') < end_of_day:
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
                    self.print_log(
                        f"File [{label}] stock query failed for ticker [{ticker}] between [{start}] and [{end_exclusive}]",
                        exception=exception,
                    )
                    if not ignore:
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return DownloadResult(DownloadStatus.FAILED, None)

    def database_download(self, query_name, query_string, start=None, end=None,
                          check=True, force=False, ignore=True):
        started_time = time.time()
        local_path = abspath(f"{self.local_cache}/_Database_{query_name}.csv")
        effective_force = force or config.force_downloads
        if config.disable_downloads or _database.database_client is None:
            if isfile(local_path):
                self.print_log(f"File [{query_name}] cached at [{local_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, local_path)
            self.print_log(f"File [{query_name}] query skipped: downloads disabled and no cache available")
            if not ignore:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
            return DownloadResult(DownloadStatus.FAILED, None)
        if not effective_force and not check and isfile(local_path):
            self.print_log(f"File [{query_name}] cached at [{local_path}]", started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, local_path)
        if not effective_force and check and isfile(local_path):
            data_df = self.csv_read(local_path, print_rows=-1)
            if len(data_df) > 0:
                data_start = data_df.head(1).rows()[0][0]
                data_end = data_df.tail(1).rows()[0][0]
                if (start is None or start >= data_start) and (end is None or end <= data_end):
                    self.print_log(f"File [{query_name}] cached at [{local_path}]", started=started_time)
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                    return DownloadResult(DownloadStatus.CACHED, local_path)
        try:
            arrow_table = _database.database_client.query(query=query_string, language="sql")
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
        file_path = abspath(f"{self.local_cache}/_Redbark_{file_cache}.csv")
        effective_force = force or config.force_downloads
        if config.disable_downloads:
            if isfile(file_path):
                self.print_log(f"File [{file_cache}] cached at [{file_path}]", started=started_time)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, file_path)
            self.print_log(f"File [{file_cache}] query skipped: downloads disabled and no cache available")
            return DownloadResult(DownloadStatus.FAILED, None)
        if not effective_force and not check and isfile(file_path):
            self.print_log(f"File [{file_cache}] cached at [{file_path}]", started=started_time)
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, file_path)
        token = os.environ.get("REDBARK_TOKEN", "")
        base_url = "https://api.redbark.co"
        req_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        def _request(path):
            req = urllib.request.Request(f"{base_url}{path}", headers=req_headers)
            response = urllib.request.urlopen(req, context=ssl._create_unverified_context())
            return json.loads(response.read().decode())

        def _has_more(_result):
            pagination = _result.get("pagination", _result)
            return bool(pagination.get("hasMore", pagination.get("has_more", False)))

        def _all_accounts():
            _rows, offset = [], 0
            while True:
                _result = _request(f"/v1/accounts?limit=200&offset={offset}")
                _rows.extend(_result.get("data", []))
                if not _has_more(_result):
                    break
                offset += len(_result.get("data", []))
            return _rows

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
                if not effective_force and check and isfile(file_path):
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
        pattern = abspath(f"{self.local_cache}/_Sheet_{name}_v*.csv")
        for file_path in glob.glob(pattern):
            filename = basename(file_path)
            prefix = f"_Sheet_{name}_v"
            version_str = filename[len(prefix):-len(".csv")]
            if version_str.isdigit() and int(version_str) <= current_version - 2:
                os.remove(file_path)
                self.print_log(f"File [{name}] deleted old version [{file_path}]")

    def sheet_download(self, drive_key, workbook_name, sheet_name=None, sheet_start_row=1, sheet_load_secs=10, sheet_retry_max=5,
                       read_cache=True, write_cache=False, print_rows=PL_PRINT_ROWS):
        if drive_key is None:
            return DownloadResult(DownloadStatus.FAILED, None)
        started_time = time.time()
        drive_url = "https://docs.google.com/spreadsheets/d/" + drive_key
        drive_version: str | None = None
        try:
            raw_version = build('drive', 'v3', credentials=Spread(drive_url).client.auth, cache_discovery=False) \
                .files().get(fileId=drive_key, fields='version').execute().get('version')
            if raw_version is not None:
                drive_version = str(raw_version)
        except Exception as exception:
            self.print_log(f"Failed to get Drive version of sheet [{drive_url}]", exception=exception, level="error")
        name = workbook_name if sheet_name is None else f"{workbook_name}_{sheet_name}"
        if drive_version is not None:
            file_path = abspath(f"{self.local_cache}/_Sheet_{name}_v{drive_version}.csv")
            drive_version_int = int(drive_version)
            self._sheet_cache_cleanup(name, drive_version_int)
            if read_cache and not write_cache and isfile(file_path):
                self.print_log(f"File [{workbook_name}] cached at [{file_path}]", started=started_time)
                return DownloadResult(DownloadStatus.CACHED, file_path)
        else:
            prefix = f"_Sheet_{name}_v"
            versioned_files = sorted(
                [(int(basename(p)[len(prefix):-len(".csv")]), p)
                 for p in glob.glob(abspath(f"{self.local_cache}/{prefix}*.csv"))
                 if basename(p)[len(prefix):-len(".csv")].isdigit()],
                reverse=True
            )
            if read_cache and not write_cache and versioned_files:
                _, file_path = versioned_files[0]
                self.print_log(f"File [{workbook_name}] cached at [{file_path}]", started=started_time)
                return DownloadResult(DownloadStatus.CACHED, file_path)
            file_path = abspath(f"{self.local_cache}/_Sheet_{name}.csv")
            if read_cache and not write_cache and isfile(file_path):
                self.print_log(f"File [{workbook_name}] cached at [{file_path}]", started=started_time)
                return DownloadResult(DownloadStatus.CACHED, file_path)
        file_path = abspath(f"{self.local_cache}/_Sheet_{name}.csv") if drive_version is None else abspath(f"{self.local_cache}/_Sheet_{name}_v{drive_version}.csv")
        retries = 0
        caught_exception = None

        class SheetStillLoadingError(Exception):
            pass

        try:
            while retries < sheet_retry_max:
                try:
                    retries += 1
                    spread = Spread(drive_url, sheet=0 if sheet_name is None else sheet_name)
                    # noinspection PyProtectedMember
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
                            raise SheetStillLoadingError(
                                f"DataFrame [{workbook_name}] loaded from sheet that is yet to finish rendering column [{column}]")
                    self.csv_write(data_df, file_path, print_label=workbook_name, print_rows=-1)
                    _dataframe_print(self.name,
                        data_df,
                        print_label=workbook_name,
                        print_verb="downloaded",
                        print_suffix=f"from [{drive_url}][{workbook_name}{'' if sheet_name is None else f':{sheet_name}'}]",
                        print_rows=print_rows,
                        started=started_time
                    )
                    caught_exception = None
                    break
                except SheetStillLoadingError as exception:
                    time.sleep(sheet_load_secs)
                    caught_exception = exception
            if caught_exception is not None:
                raise caught_exception
        except Exception as exception:
            self.print_log(f"DataFrame [{workbook_name}] unavailable at [{drive_url}]" +
                           ("" if retries < sheet_retry_max else f" after retrying [{sheet_retry_max}] times over [{sheet_retry_max * sheet_load_secs}] seconds"), exception=exception)
            return DownloadResult(DownloadStatus.FAILED, None)
        return DownloadResult(DownloadStatus.DOWNLOADED, file_path)

    def sheet_upload(self, data_df, drive_key, workbook_name, sheet_name=None, sheet_start_row=1, sheet_start_column="A",
                     add_filter=False, print_label=None, print_rows=PL_PRINT_ROWS):
        if drive_key is None:
            return
        started_time = time.time()
        drive_url = "https://docs.google.com/spreadsheets/d/" + drive_key
        name = workbook_name if sheet_name is None else f"{workbook_name}_{sheet_name}"
        try:
            data_df_pd = data_df.to_pandas()
            drive_version: str | None = None
            if not config.disable_uploads:
                spread = Spread(drive_url)
                spread.df_to_sheet(data_df_pd, index=False, sheet=sheet_name, start=f"{sheet_start_column}{sheet_start_row}", add_filter=add_filter, replace=True)
                try:
                    raw_version = build('drive', 'v3', credentials=spread.client.auth, cache_discovery=False) \
                        .files().get(fileId=drive_key, fields='version').execute().get('version')
                    if raw_version is not None:
                        drive_version = str(raw_version)
                except Exception as exception:
                    self.print_log(f"Failed to get Drive version after upload of [{drive_url}]", exception=exception, level="error")
            suffix = f"_v{drive_version}" if drive_version is not None else ""
            file_path = abspath(f"{self.local_cache}/_Sheet_{name}{suffix}.csv")
            self.csv_write(data_df, file_path)
            if drive_version is not None:
                drive_version_str: str = drive_version
                drive_version_int = int(drive_version_str)
                self._sheet_cache_cleanup(name, drive_version_int)
            _dataframe_print(self.name,
                data_df,
                print_label=print_label,
                print_verb="uploaded",
                print_suffix=f"to [{drive_url}][{workbook_name}{'' if sheet_name is None else f':{sheet_name}'}]",
                started=started_time,
                print_rows=print_rows,
            )
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_COLUMNS, len(data_df.columns))
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_ROWS, len(data_df))
        except Exception as exception:
            self.print_log(f"DataFrame failed to upload to [{drive_url}]", exception=exception)
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)

    def dropbox_download(self, dropbox_dir: str | None, local_dir: str, check: bool = True):
        if dropbox_dir is None:
            return collections.OrderedDict()
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
        service = dropbox.Dropbox(os.getenv('DROPBOX_TOKEN', ''))
        cursor: str | None = None
        while True:
            if cursor is None:
                response = service.files_list_folder(dropbox_dir)
            else:
                response = service.files_list_folder_continue(cursor)
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
        self.print_log(
            f"Directory [{basename(local_dir)}] listed [{len(dropbox_files)}] files from [https://www.dropbox.com/home/{dropbox_dir}]",
            started=started_time,
        )
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
                    self.print_log(
                        f"File [{label}] downloaded file [{local_path}] modified timestamp set failed [{dropbox_files[dropbox_file]['modified']}]",
                        exception=exception,
                    )
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
        self.print_log(
            f"Directory [{basename(local_dir).title()}] downloaded [{len(actioned_files)}] files from [https://www.dropbox.com/home/{dropbox_dir}]",
            started=started_time,
        )
        return collections.OrderedDict(sorted(actioned_files.items()))

    def drive_synchronise(self, drive_dir, local_dir, check=True, download=True, upload=False):
        if drive_dir is None:
            return collections.OrderedDict()
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
            response = service.files().list(
                q=f"'{drive_dir}' in parents",
                spaces='drive',
                fields='nextPageToken, files(id, name, modifiedTime, md5Checksum)',
                pageToken=token
            ).execute()
            for drive_file in response.get('files', []):
                drive_files[drive_file["name"]] = {
                    "id": drive_file["id"],
                    "hash": drive_file["md5Checksum"],
                    "modified": int((datetime.strptime(drive_file["modifiedTime"], '%Y-%m-%dT%H:%M:%S.%fZ') - datetime(1970, 1, 1)).total_seconds()),
                }
            token = response.get('nextPageToken')
            if not token:
                break
        self.print_log(
            f"Directory [{basename(local_dir)}] listed [{len(drive_files)}] files from [https://drive.google.com/drive/folders/{drive_dir}]",
            started=started_time,
        )
        started_time = time.time()
        force_download = config.force_downloads and not config.disable_downloads
        force_upload = config.force_downloads and not config.disable_uploads
        for drive_file in drive_files:
            started_time_file = time.time()
            file_actioned = False
            local_path = abspath(f"{local_dir}/{drive_file}")
            label = basename(local_path).split(".")[0]
            needs_download = drive_file not in local_files or (check and not force_download and drive_files[drive_file]["modified"] > local_files[drive_file]["modified"])
            if download and not config.disable_downloads and (force_download or needs_download):
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
                    self.print_log(
                        f"File [{label}] downloaded file [{local_path}] modified timestamp set failed [{drive_files[drive_file]['modified']}]",
                        exception=exception,
                    )
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
                    needs_upload = local_file not in drive_files or (check and not force_upload and (
                            drive_files[local_file]["modified"] != local_files[local_file]["modified"] or
                            drive_files[local_file]["hash"] != local_files[local_file]["hash"]
                    ))
                    if (force_upload or needs_upload) and not config.disable_uploads:
                        try:
                            data = MediaFileUpload(local_path)
                            drive_id = drive_files[local_file]["id"] if local_file in drive_files else None
                            metadata: dict[str, object] = {'modifiedTime': datetime.fromtimestamp(
                                local_files[local_file]["modified"], timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
                            if drive_id is None:
                                metadata['name'] = basename(local_file)
                                metadata['parents'] = [drive_dir]
                                request = service.files().create(body=metadata, media_body=data).execute()
                            else:
                                request = service.files().update(fileId=drive_id, body=metadata, media_body=data).execute()
                            file_actioned = True
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_UPLOADED)
                            self.print_log(
                                f"File [{label}] uploaded to [https://drive.google.com/file/d/{request.get('id') if drive_id is None else drive_id}]",
                                started=started_time_file,
                            )
                        except Exception as exception:
                            self.print_log(
                                f"File [{label}] failed to upload to [https://drive.google.com/drive/folders/{drive_dir}]",
                                exception=exception,
                            )
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
                    else:
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_PERSISTED)
                        self.print_log(
                            f"File [{label}] verified at [https://drive.google.com/file/d/{drive_files[local_file]['id']}]",
                            started=started_time_file,
                        )
                    actioned_files[local_path] = True, file_actioned
        self.print_log(
            f"Directory [{basename(local_dir).title()}] synchronised [{len(actioned_files)}] files from [https://drive.google.com/drive/folders/{drive_dir}]",
            started=started_time,
        )
        return collections.OrderedDict(sorted(actioned_files.items()))
