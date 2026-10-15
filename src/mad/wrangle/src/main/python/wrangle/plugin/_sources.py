import collections
import concurrent.futures
import contextlib
import functools
import glob
import hashlib
import io
import json
import logging
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from ftplib import FTP
from os.path import exists, getmtime

import dropbox
import google
import google.auth.transport.requests
import google.oauth2.credentials
import google_auth_httplib2
import gspread
import gspread.exceptions
import httplib2
import polars as pl
import requests
import yfinance as yf
from dateutil import parser
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from requests.adapters import HTTPAdapter

from . import database
from ._contract import ContractMixin
from .config import *
from .counters import *
from .logger import dataframe_print

logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)


def _timed(action):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            start = time.perf_counter()
            try:
                return func(self, *args, **kwargs)
            finally:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                self.add_counter(CTR_SRC_TIMING, action, elapsed_ms)

        return wrapper

    return decorator


class SheetStillLoadingError(Exception):
    pass


class DefaultTimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, timeout: float, *args, **kwargs):
        self._timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        if timeout is None:
            timeout = self._timeout
        return super().send(request, stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies)


class SourcesMixin(ContractMixin):
    @staticmethod
    def _google_authorized_http(credentials):
        return google_auth_httplib2.AuthorizedHttp(
            credentials,
            http=httplib2.Http(timeout=TIMEOUT_NETWORK_SECONDS),
        )

    @_timed(CTR_ACT_MARSHALL_MILLIS)
    def http_download(self, url_file: str, local_path: str, check: bool = True, ignore: bool = False) -> DownloadResult:
        """
        Fetches `url_file` to `local_path`, stamped with the server's `Last-Modified`. With `check` a HEAD
        request keeps a cache whose stamp still matches, without it any cache is kept; downloads disabled serve
        the cache, and `ignore` silences a failed fetch.
        """
        started_time = time.time()
        local_path = abspath(local_path).lower()
        label = basename(local_path).split(".")[0]
        effective_force = config.force_downloads
        if config.disable_source_downloads:
            if isfile(local_path):
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, [local_path])
            if config.force_reprocessing:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_SKIPPED)
                return DownloadResult(DownloadStatus.SKIPPED, [])
            return DownloadResult(DownloadStatus.FAILED, [])
        if not effective_force and not check and isfile(local_path):
            self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, [local_path])
        client = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11",
            "Accept": "text/html,application/xhtml+xml,application/xml,text/csv,application/zip;q=0.9,*/*;q=0.8",
            "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
            "Accept-Encoding": "none",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "keep-alive",
        }

        def get_modified(headers):
            modified_header = headers.get("Last-Modified")
            if modified_header:
                return int(datetime.strptime(modified_header, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=UTC).timestamp())
            return None

        if not effective_force and check and isfile(local_path):
            modified_timestamp_cached = int(getmtime(local_path))
            try:
                request = urllib.request.Request(url_file, headers=client)
                request.get_method = lambda: "HEAD"
                response = urllib.request.urlopen(
                    request,
                    timeout=TIMEOUT_NETWORK_SECONDS,
                    context=ssl._create_unverified_context(),
                )
                modified_timestamp = get_modified(response.headers)
                if modified_timestamp is not None and modified_timestamp_cached == modified_timestamp:
                    self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                    return DownloadResult(DownloadStatus.CACHED, [local_path])
            except (urllib.error.URLError, OSError):
                pass
        try:
            response = urllib.request.urlopen(
                urllib.request.Request(url_file, headers=client),
                timeout=TIMEOUT_NETWORK_SECONDS,
                context=ssl._create_unverified_context(),
            )
            if not exists(dirname(local_path)):
                os.makedirs(dirname(local_path))
            with open(local_path, "wb") as local_file:
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
            return DownloadResult(DownloadStatus.DOWNLOADED, [local_path])
        except Exception as exception:
            if not ignore:
                self.print_log(f"File [{label}] not available at [{url_file}]", exception=exception)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return DownloadResult(DownloadStatus.FAILED, [])

    @_timed(CTR_ACT_MARSHALL_MILLIS)
    def redbark_download(self, url_paths: list[str], local_path: str, columns: list[str], check: bool = True, ignore: bool = False, paged: bool = True) -> DownloadResult:
        """
        Fetches each Redbark API path in `url_paths`, following `limit` and `offset` pages when `paged`, caches the returned
        rows' `columns` in `local_path` stamped now, and returns them as `data_frame`. Without `check` any cache
        is kept and downloads disabled serve the cache; a failed path comes back in `errors` with its HTTP status, leaves the
        cache as it was and is logged unless `ignore`.
        """
        started_time = time.time()
        local_path = abspath(local_path)
        label = basename(local_path).split(".")[0]
        schema = dict.fromkeys(columns, pl.Utf8)
        if config.disable_source_downloads or (not config.force_downloads and not check and isfile(local_path)):
            if isfile(local_path):
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                cached_df = pl.read_csv(local_path, infer_schema=False)
                return DownloadResult(
                    DownloadStatus.CACHED, [local_path], data_frame=cached_df.select([pl.col(column) if column in cached_df.columns else pl.lit(None, pl.Utf8).alias(column) for column in columns])
                )
            if config.force_reprocessing:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_SKIPPED)
                return DownloadResult(DownloadStatus.SKIPPED, [])
            return DownloadResult(DownloadStatus.FAILED, [])

        def _request(_path):
            _response = urllib.request.urlopen(
                urllib.request.Request(
                    f"{REDBARK_URL}{_path}", headers={"Authorization": f"Bearer {os.environ.get('REDBARK_TOKEN', '')}", "Content-Type": "application/json", "User-Agent": "curl/8.0"}
                ),
                timeout=TIMEOUT_NETWORK_SECONDS,
                context=ssl._create_unverified_context(),
            )
            self.print_log(f"Redbark request [{_path.split('?')[0]}] rate limit remaining [{_response.headers.get('X-RateLimit-Remaining')}]", level="debug")
            return json.loads(_response.read().decode())

        rows, errors = [], []
        for url_path in url_paths:
            try:
                offset = 0
                for _ in range(REDBARK_PAGES_MAX):
                    response = _request(f"{url_path}{'&' if '?' in url_path else '?'}limit={REDBARK_PAGE_LIMIT}&offset={offset}" if paged else url_path)
                    page_rows = response.get("data", [])
                    has_more = paged and bool(response.get("pagination", {}).get("hasMore", False))
                    if has_more and len(page_rows) == 0:
                        raise TimeoutError("Redbark pagination reported more with an empty page")
                    rows.extend(page_rows)
                    if not has_more:
                        break
                    offset += len(page_rows)
                else:
                    raise TimeoutError(f"Redbark pagination exceeded max pages [{REDBARK_PAGES_MAX}]")
            except Exception as exception:
                errors.append({"Path": url_path, "Status": exception.code if isinstance(exception, urllib.error.HTTPError) else None, "Detail": str(exception)})
                if not ignore:
                    self.print_log(f"File [{label}] not available at [{REDBARK_URL}{url_path}]", exception=exception)
        rows_df = pl.DataFrame([{column: (None if row.get(column) is None else str(row.get(column))) for column in columns} for row in rows], schema=schema)
        if errors:
            if not ignore:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
            return DownloadResult(DownloadStatus.FAILED, [], data_frame=None if len(errors) == len(url_paths) else rows_df, errors=errors)
        if not exists(dirname(local_path)):
            os.makedirs(dirname(local_path))
        rows_df.write_csv(local_path)
        modified_timestamp = self.now().timestamp()
        os.utime(local_path, (modified_timestamp, modified_timestamp))
        self.print_log(f"File [{label}] downloaded to [{local_path}]", started=started_time)
        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
        return DownloadResult(DownloadStatus.DOWNLOADED, [local_path], data_frame=rows_df)

    @_timed(CTR_ACT_MARSHALL_MILLIS)
    def ftp_download(
        self,
        url_file: str,
        local_path: str,
        check: bool = True,
        ignore: bool = False,
    ) -> DownloadResult:
        """
        Fetches `url_file` over FTP to `local_path`, stamped with the server's `MDTM`. With `check` a cache
        whose stamp still matches is kept, without it any cache is kept; downloads disabled serve the cache, and
        `ignore` silences a failed fetch.
        """
        started_time = time.time()
        local_path = abspath(local_path).lower()
        label = basename(local_path).split(".")[0]
        effective_force = config.force_downloads
        if config.disable_source_downloads:
            if isfile(local_path):
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, [local_path])
            if config.force_reprocessing:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_SKIPPED)
                return DownloadResult(DownloadStatus.SKIPPED, [])
            return DownloadResult(DownloadStatus.FAILED, [])
        if not effective_force and not check and isfile(local_path):
            self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, [local_path])
        url_server = url_file.replace("ftp://", "").split("/")[0]
        url_path = url_file.split(url_server)[-1]
        client = None
        try:
            client = FTP(url_server, timeout=TIMEOUT_NETWORK_SECONDS)
            client.login()
            modified_timestamp = int(parser.parse(client.voidcmd(f"MDTM {url_path}")[4:].strip()).replace(tzinfo=UTC).timestamp())
            if not effective_force and check and isfile(local_path):
                modified_timestamp_cached = int(getmtime(local_path))
                if modified_timestamp_cached == modified_timestamp:
                    self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                    client.quit()
                    return DownloadResult(DownloadStatus.CACHED, [local_path])
            if not exists(dirname(local_path)):
                os.makedirs(dirname(local_path))
            with open(local_path, "wb") as local_file:
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
            return DownloadResult(DownloadStatus.DOWNLOADED, [local_path])
        except Exception as exception:
            if client is not None:
                client.quit()
            if not ignore:
                self.print_log(f"File [{label}] not available at [{url_file}]", exception=exception)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return DownloadResult(DownloadStatus.FAILED, [])

    @_timed(CTR_ACT_MARSHALL_MILLIS)
    def stock_download(
        self,
        local_path: str,
        ticker: str,
        start: str,
        end: str,
        end_of_day: str = "17:00",
        check: bool = True,
        ignore: bool = True,
    ) -> DownloadResult:
        """
        Fetches a ticker's daily prices from `start` to `end` into `local_path` with yfinance. With `check` a
        cache already covering the range is kept (today's close counted only after `end_of_day`), without it any
        cache is kept; downloads disabled serve the cache, and `ignore` lets a ticker with no rows pass.
        """
        started_time = time.time()
        local_path = abspath(local_path).lower()
        label = basename(local_path).split(".")[0]
        effective_force = config.force_downloads
        if config.disable_source_downloads:
            if isfile(local_path):
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, [local_path])
            if config.force_reprocessing:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_SKIPPED)
                return DownloadResult(DownloadStatus.SKIPPED, [])
            return DownloadResult(DownloadStatus.FAILED, [])
        now = self.now()
        end_exclusive = date.fromisoformat(end) + timedelta(days=1)
        start_date = date.fromisoformat(start)
        if start_date >= end_exclusive:
            self.print_log(f"File [{label}] stock query skipped, empty date range [{start}] to [{end}]", level="debug")
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_SKIPPED)
            return DownloadResult(DownloadStatus.SKIPPED, [])
        if start_date < end_exclusive:
            if not effective_force and not check and isfile(local_path):
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                return DownloadResult(DownloadStatus.CACHED, [local_path])
            try:
                if not effective_force and check and isfile(local_path):  # noqa: SIM102
                    if now.year == int(end.split("-")[0]) and now.month == int(end.split("-")[1]):
                        data_df = self.csv_read(local_path)
                        if len(data_df) > 0:
                            end_data = data_df.row(-1)[0]
                            end_data = date.fromisoformat(end_data) if isinstance(end_data, str) else end_data
                            end_expected = (now - timedelta(days=max(0, now.weekday() - 4))).date()
                            if now.date() == end_expected:
                                if -1 < now.weekday() < 5:
                                    if now.strftime("%H:%M") < end_of_day:
                                        end_expected = end_expected - timedelta(days=3 if now.weekday() == 0 else 1)
                                else:
                                    end_expected = end_expected - timedelta(days=2 if now.weekday() == 5 else 1)
                            if end_data == end_expected:
                                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
                                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                                return DownloadResult(DownloadStatus.CACHED, [local_path])
                        else:
                            self.print_log(f"File [{label}] cached (but empty) at [{local_path}]", started=started_time)
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                            return DownloadResult(DownloadStatus.CACHED, [local_path])
                data_df = yf.Ticker(ticker).history(start=start, end=end_exclusive, timeout=TIMEOUT_NETWORK_SECONDS)
                if hasattr(data_df.index, "tz_localize"):
                    data_df.index = data_df.index.tz_localize(None)  # type: ignore[union-attr]
                if "Capital Gains" in data_df.columns:
                    data_df = data_df.drop(columns=["Capital Gains"])
                in_range = (data_df.index.date >= start_date) & (data_df.index.date < end_exclusive)  # type: ignore[union-attr]
                if not in_range.all():
                    self.print_log(f"File [{label}] stock query returned [{(~in_range).sum()}] rows outside [{start}] to [{end_exclusive}] for ticker [{ticker}], dropped", level="warn")
                    data_df = data_df.loc[in_range]
                if now.year == int(end.split("-")[0]) and now.month == int(end.split("-")[1]) and len(data_df) > 0 and data_df.index[-1].date() == now.date() and now.strftime("%H:%M") < end_of_day:
                    data_df = data_df[:-1]
                if len(data_df) == 0:
                    if not ignore:
                        raise Exception(f"File [{label}] stock query returned no data for ticker [{ticker}] between [{start}] and [{end_exclusive}]")
                    self.print_log(f"File [{label}] stock query returned no data for ticker [{ticker}] between [{start}] and [{end_exclusive}]", level="warn")
                    if isfile(local_path):
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                        return DownloadResult(DownloadStatus.CACHED, [local_path])
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_SKIPPED)
                    return DownloadResult(DownloadStatus.SKIPPED, [])
                if len(data_df.columns) == 0:
                    self.print_log(f"File [{label}] stock query returned only dates (no price columns) for ticker [{ticker}] between [{start}] and [{end_exclusive}]", level="warn")
                if not exists(dirname(local_path)):
                    os.makedirs(dirname(local_path))
                data_df.insert(loc=0, column="Date", value=data_df.index.strftime("%Y-%m-%d"))  # type: ignore[union-attr]
                if len(data_df) > 0:
                    last_date = date.fromisoformat(data_df["Date"].iloc[-1])
                    end_date = date.fromisoformat(end)
                    reference_date = end_date
                    if now.year == end_date.year and now.month == end_date.month:
                        reference_date = (now - timedelta(days=1)).date() if now.strftime("%H:%M") < end_of_day else now.date()
                    expected_date = reference_date
                    while expected_date.weekday() >= 5:
                        expected_date -= timedelta(days=1)
                    missing_weekdays = []
                    check_day = last_date + timedelta(days=1)
                    while check_day <= expected_date:
                        if check_day.weekday() < 5:
                            missing_weekdays.append(check_day)
                        check_day += timedelta(days=1)
                    weekday_gap = len(missing_weekdays)
                    warn_threshold = 2 if ticker.startswith("^") else 1
                    error_threshold = 3 if ticker.startswith("^") else 2
                    dec_25_26 = weekday_gap == 2 and {(d.month, d.day) for d in missing_weekdays} == {(12, 25), (12, 26)} and missing_weekdays[0].year == missing_weekdays[1].year
                    day_word = "trading day" if weekday_gap == 1 else "trading days"
                    if weekday_gap >= error_threshold and not dec_25_26:
                        self.print_log(
                            f"File [{label}] stock query for ticker [{ticker}] missing data: last date [{last_date}] is [{weekday_gap}] {day_word} before expected [{expected_date}]", level="error"
                        )
                    elif weekday_gap >= warn_threshold and not dec_25_26:
                        self.print_log(
                            f"File [{label}] stock query for ticker [{ticker}] missing data: last date [{last_date}] is [{weekday_gap}] {day_word} before expected [{expected_date}]", level="warn"
                        )
                if len(data_df) > 0 and isfile(local_path):
                    prior_df = self.csv_read(local_path)
                    if len(prior_df) == len(data_df):
                        prior_last = prior_df.row(-1)[0]
                        prior_last = date.fromisoformat(prior_last) if isinstance(prior_last, str) else prior_last
                        new_last = date.fromisoformat(data_df["Date"].iloc[-1])
                        if prior_last == new_last:
                            self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time, level="debug")
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                            return DownloadResult(DownloadStatus.CACHED, [local_path])
                self.csv_write(pl.from_pandas(data_df), local_path, print_verb="downloaded", started=started_time)
                if len(data_df) > 0:
                    modified = date.fromisoformat(str(data_df.values[-1][0]))
                    modified_timestamp = int((modified + timedelta(hours=8) - date(1970, 1, 1)).total_seconds())
                    try:
                        os.utime(local_path, (modified_timestamp, modified_timestamp))
                    except Exception as exception:
                        self.print_log(f"File [{label}] stock query file [{local_path}] modified timestamp set failed [{modified_timestamp}]", exception=exception)
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                return DownloadResult(DownloadStatus.DOWNLOADED, [local_path])
            except Exception as exception:
                self.print_log(
                    f"File [{label}] stock query failed for ticker [{ticker}] between [{start}] and [{end_exclusive}]",
                    exception=exception,
                )
                if not ignore:
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
        return DownloadResult(DownloadStatus.FAILED, [])

    @_timed(CTR_ACT_MARSHALL_MILLIS)
    def database_download(self, query_name, query_string, start=None, end=None, check=True):
        """
        Runs `query_string` into the cache `_database_<query_name>.csv`. With `check` a cache whose dates span
        `start` to `end` is kept, without it any cache is kept; downloads disabled or no connection serve the
        cache.
        """
        started_time = time.time()
        local_path = abspath(f"{self.local_cache}/_database_{query_name.lower()}.csv")
        effective_force = config.force_downloads
        if config.disable_database_downloads:
            if isfile(local_path):
                self.print_log(f"File [{query_name}] cached at [{local_path}]", started=started_time, level="debug")
                return DownloadResult(DownloadStatus.CACHED, [local_path])
            self.print_log(f"File [{query_name}] query skipped, downloads disabled and no cache available")
            return DownloadResult(DownloadStatus.FAILED, [])
        if database.database_conn is None:
            if isfile(local_path):
                self.print_log(f"File [{query_name}] cached at [{local_path}]", started=started_time, level="debug")
                return DownloadResult(DownloadStatus.CACHED, [local_path])
            self.print_log(f"File [{query_name}] connection unavailable and no cache available")
            self.add_counter(CTR_SRC_DATA, CTR_ACT_ERRORED)
            return DownloadResult(DownloadStatus.FAILED, [])
        if not effective_force and not check and isfile(local_path):
            self.print_log(f"File [{query_name}] cached at [{local_path}]", started=started_time, level="debug")
            return DownloadResult(DownloadStatus.CACHED, [local_path])
        if not effective_force and check and isfile(local_path):
            data_df = self.csv_read(local_path, print_rows=-1)
            if len(data_df) > 0:
                data_start = data_df.head(1).rows()[0][0]
                data_end = data_df.tail(1).rows()[0][0]
                if (start is None or start >= data_start) and (end is None or end <= data_end):
                    self.print_log(f"File [{query_name}] cached at [{local_path}]", started=started_time, level="debug")
                    return DownloadResult(DownloadStatus.CACHED, [local_path])
        try:
            data_df = pl.read_database(query=query_string, connection=database.database_conn)
            if data_df is None or len(data_df) == 0:
                self.print_log(f"File [{query_name}] query returned no data")
                self.add_counter(CTR_SRC_DATA, CTR_ACT_ERRORED)
                return DownloadResult(DownloadStatus.FAILED, [])
            self.csv_write(data_df, local_path, print_verb="queried", started=started_time)
            return DownloadResult(DownloadStatus.DOWNLOADED, [local_path])
        except Exception as exception:
            self.print_log(f"File [{query_name}] query failed", exception=exception, started=started_time)
            self.add_counter(CTR_SRC_DATA, CTR_ACT_ERRORED)
            with contextlib.suppress(Exception):
                database.database_conn.rollback()
        return DownloadResult(DownloadStatus.FAILED, [])

    @_timed(CTR_ACT_EGRESS_MILLIS)
    def database_upload(self, data_df, table_name=None, metric_type="", period="", unit="", print_label=None):
        """
        Unpivots `data_df` (the first column the time, every other column one entity's value) to long rows and
        upserts them into `table_name`; with uploads disabled or no connection they accumulate in
        `_database_<name>.csv` instead.
        """
        started_time = time.time()
        if len(data_df.columns) <= 1 or len(data_df) == 0:
            return
        date_col = data_df.columns[0]
        table_name = table_name or self.name.lower()
        csv_path = abspath(f"{self.local_cache}/_database_{self.name.lower()}.csv")
        long_df = (
            data_df.rename({date_col: "time"})
            .unpivot(index="time", variable_name="_col", value_name="value")
            .filter(pl.col("value").is_not_null())
            .with_columns(pl.col("_col").str.split(" ").list.first().alias("entity"), pl.lit(metric_type).alias("type"), pl.lit(period).alias("period"), pl.lit(unit).alias("unit"))
            .select(["time", "entity", "type", "period", "unit", "value"])
        )
        if long_df.is_empty():
            return
        self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_COLUMNS, len(data_df.columns) - 1)
        self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_ROWS, len(data_df))
        if config.disable_database_uploads or database.database_conn is None:
            pk = ["time", "entity", "type", "period", "unit"]
            if csv_path in self._db_cache_dfs:
                kept = self._db_cache_dfs[csv_path].join(long_df.select(pk), on=pk, how="anti")
                long_df = pl.concat([kept, long_df]).sort("time")
            self._db_cache_dfs[csv_path] = long_df
            dataframe_print(self.name, long_df, print_label=print_label, print_verb="cached", print_suffix=f"to [{csv_path}]", started=started_time)
            return
        try:
            database.database_ensure_table(table_name, database.database_conn)
            database.database_upsert(long_df, table_name, database.database_conn, database.DSN)
            dataframe_print(self.name, long_df, print_label=print_label, print_verb="uploaded", print_suffix=f"to [{table_name}]", started=started_time)
        except Exception as exception:
            self.print_log(f"DataFrame{'' if print_label is None else f' [{print_label}]'} write failed", exception=exception)
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)
            with contextlib.suppress(Exception):
                database.database_conn.rollback()

    def _sheets_credentials(self):
        if self._sheet_credentials is None:
            cred_path = os.path.expanduser("~/.config/gspread_pandas/creds/default")
            with open(cred_path) as cred_file:
                cred_data = json.load(cred_file)
            creds = google.oauth2.credentials.Credentials(
                token=None,
                refresh_token=cred_data["refresh_token"],
                token_uri=cred_data["token_uri"],
                client_id=cred_data["client_id"],
                client_secret=cred_data["client_secret"],
                scopes=cred_data.get("scopes"),
            )
            timeout_session = requests.Session()
            timeout_adapter = DefaultTimeoutHTTPAdapter(TIMEOUT_NETWORK_SECONDS)
            timeout_session.mount("https://", timeout_adapter)
            timeout_session.mount("http://", timeout_adapter)
            creds.refresh(google.auth.transport.requests.Request(session=timeout_session))
            self._sheet_credentials = creds
        return self._sheet_credentials

    def _sheet_cache_cleanup(self, name, current_version):
        name = name.lower()
        pattern = abspath(f"{self.local_cache}/_sheet_{name}_v*.csv")
        for file_path in glob.glob(pattern):
            filename = basename(file_path)
            prefix = f"_sheet_{name}_v"
            version_str = filename[len(prefix) : -len(".csv")]
            if version_str.isdigit() and int(version_str) <= current_version - 2:
                os.remove(file_path)
                self.print_log(f"File [{name}] deleted old version [{file_path}]", level="debug")

    def _sheet_version(self, drive_key) -> str | None:
        try:
            drive_service = build("drive", "v3", http=self._google_authorized_http(self._sheets_credentials()), cache_discovery=False)
            raw_version = drive_service.files().get(fileId=drive_key, fields="version").execute().get("version")
            return None if raw_version is None else str(raw_version)
        except Exception as exception:
            self.print_log(f"Failed to get Drive version of sheet [https://docs.google.com/spreadsheets/d/{drive_key}]", exception=exception, level="error")
            return None

    def sheet_cached(self, workbook_name, sheet_name=None) -> pl.DataFrame | None:
        """
        Reads a tab as last downloaded or uploaded from its cache, as text, or None when there is no cache or it cannot
        be read.
        """
        label = workbook_name if sheet_name is None else f"{workbook_name}:{sheet_name}"
        cache_path = self._sheet_cache_path((workbook_name if sheet_name is None else f"{workbook_name}_{sheet_name}").lower())
        if cache_path is None:
            return None
        try:
            return pl.read_csv(cache_path, infer_schema=False, raise_if_empty=False)
        except Exception as exception:
            self.print_log(f"File [{label}] cache unreadable at [{cache_path}]", exception=exception, level="warn")
            return None

    @_timed(CTR_ACT_MARSHALL_MILLIS)
    def sheet_download(self, drive_key, workbook_name, sheet_name=None, sheet_start_row=1, sheet_load_secs=10, sheet_retry_max=5, check=True, schema=None, print_rows=PL_PRINT_ROWS):
        """
        Downloads one tab, or several in one read, into versioned caches: one Drive version lookup serves every
        tab from cache while the spreadsheet is unchanged, and a tab it lacks is written empty. With `schema` no
        blank column is dropped, declared numeric columns are stripped of `$`, `£` and `,`, and declared dates
        are rewritten ISO.
        """
        started_time = time.time()
        sheet_names = sheet_name if isinstance(sheet_name, list) else [sheet_name]
        names = [(workbook_name if name is None else f"{workbook_name}_{name}").lower() for name in sheet_names]
        label = workbook_name if sheet_name is None or isinstance(sheet_name, list) else f"{workbook_name}:{sheet_name}"
        effective_force = config.force_downloads

        def _tab_dataframe(_cells, _label):
            _numeric_pattern = r"^\s*[-+]?[$£]?[\d,]*\.?\d+\s*$"
            _data_df = self.dataframe_new(data=_cells[1:], orient="row", print_label=_label, print_rows=-1)
            if len(_cells) > 0:
                _data_df.columns = [_named if _named != "" else _default for _default, _named in zip(_data_df.columns, _cells[0], strict=False)]
            _data_df = _data_df.with_columns(pl.col(pl.Utf8).replace("#N/A", None))
            _numeric_columns = (
                [_column for _column in _data_df.columns if _column in schema and schema[_column].is_numeric()]
                if schema is not None
                else [_column for _column in _data_df.columns if _data_df.schema[_column] == pl.Utf8]
            )
            _data_df = _data_df.with_columns(
                [
                    pl.when(pl.col(_column).str.contains(_numeric_pattern)).then(pl.col(_column).str.replace_all(r"[$£,\s]", "")).otherwise(pl.col(_column)).alias(_column)
                    for _column in _numeric_columns
                ]
            ).with_columns(pl.when(pl.col(pl.Utf8).str.len_chars() == 0).then(None).otherwise(pl.col(pl.Utf8)).name.keep())
            if schema is None:
                _data_df = _data_df.select([_column.name for _column in _data_df if _column.null_count() != _data_df.height])
            else:
                _data_df = _data_df.with_columns(
                    [
                        pl.coalesce([pl.col(_column).str.strip_chars().str.to_date(_date_format, strict=False) for _date_format in SHEET_DATE_FORMATS])
                        .dt.strftime("%Y-%m-%d")
                        .fill_null(pl.col(_column))
                        .alias(_column)
                        for _column, _dtype in schema.items()
                        if _dtype == pl.Date and _column in _data_df.columns
                    ]
                )
            for _column in _data_df.columns:
                if _data_df.schema[_column] == pl.Utf8 and len(_data_df.filter(pl.col(_column) == "Loading...")) > 0:
                    raise SheetStillLoadingError(f"DataFrame [{_label}] loaded from sheet that is yet to finish rendering column [{_column}]")
            return _data_df

        def _cached(_partial=False):
            _file_paths = [self._sheet_cache_path(name) or "" for name in names]
            if all(_file_paths) or (_partial and any(_file_paths)):
                self.print_log(f"File [{label}] cached at [{', '.join(_file_paths)}]", started=started_time, level="debug")
                return DownloadResult(DownloadStatus.CACHED, _file_paths)
            return None

        if config.disable_sheet_downloads or drive_key is None:
            cached = _cached(_partial=True)
            if cached is not None:
                return cached
            if config.disable_sheet_downloads and drive_key is not None:
                self.print_log(f"File [{label}] sheet download skipped, downloads disabled and no cache available")
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_SKIPPED)
            return DownloadResult(DownloadStatus.FAILED, [])
        if not effective_force and not check:
            cached = _cached()
            if cached is not None:
                return cached
        drive_url = "https://docs.google.com/spreadsheets/d/" + drive_key
        credentials = self._sheets_credentials()
        drive_version = self._sheet_version(drive_key)
        if drive_version is not None:
            file_paths = [abspath(f"{self.local_cache}/_sheet_{name}_v{drive_version}.csv") for name in names]
            for name in names:
                self._sheet_cache_cleanup(name, int(drive_version))
            if not effective_force and all(isfile(file_path) for file_path in file_paths):
                self.print_log(f"File [{label}] cached at version [{drive_version}]", started=started_time, level="debug")
                return DownloadResult(DownloadStatus.CACHED, file_paths)
        else:
            if not effective_force:
                cached = _cached()
                if cached is not None:
                    return cached
            file_paths = [abspath(f"{self.local_cache}/_sheet_{name}.csv") for name in names]
        retries = 0
        caught_exception = None
        try:
            sheets_service = build("sheets", "v4", http=self._google_authorized_http(credentials), cache_discovery=False)
            sheet_titles = [
                sheet["properties"]["title"]
                for sheet in sorted(
                    sheets_service.spreadsheets().get(spreadsheetId=drive_key, fields="sheets.properties(title,index)").execute().get("sheets", []),
                    key=lambda sheet: sheet["properties"].get("index", 0),
                )
            ]
            titles = [sheet_titles[0] if name is None and sheet_titles else name for name in sheet_names]
            present = [title for title in titles if title in sheet_titles]
            while retries < sheet_retry_max:
                try:
                    retries += 1
                    value_ranges = (
                        sheets_service.spreadsheets()
                        .values()
                        .batchGet(spreadsheetId=drive_key, ranges=[f"'{title}'" for title in present], valueRenderOption="FORMATTED_VALUE")
                        .execute()
                        .get("valueRanges", [])
                        if present
                        else []
                    )
                    cells_by_title = {title: value_range.get("values", []) for title, value_range in zip(present, value_ranges, strict=True)}
                    data_dfs = []
                    for title in titles:
                        if title not in cells_by_title:
                            self.print_log(f"File [{workbook_name}:{title}] written empty, no such tab at [{drive_url}]", level="warn")
                        cells = cells_by_title.get(title, [])[sheet_start_row - 1 :]
                        width = max((len(row) for row in cells), default=0)
                        data_dfs.append(_tab_dataframe([[*row, *([""] * (width - len(row)))] for row in cells], f"{workbook_name}:{title}"))
                    for title, data_df, file_path in zip(titles, data_dfs, file_paths, strict=True):
                        tab_label = workbook_name if sheet_name is None else f"{workbook_name}_{title}"
                        self.csv_write(data_df, file_path, print_label=tab_label, print_rows=-1)
                        dataframe_print(
                            self.name, data_df, print_label=tab_label, print_verb="downloaded", print_suffix=f"from [{drive_url}][{workbook_name}:{title}]", print_rows=print_rows, started=started_time
                        )
                    caught_exception = None
                    break
                except SheetStillLoadingError as exception:
                    time.sleep(sheet_load_secs)
                    caught_exception = exception
            if caught_exception is not None:
                raise caught_exception
        except Exception as exception:
            self.print_log(
                f"DataFrame [{label}] unavailable at [{drive_url}]" + ("" if retries < sheet_retry_max else f" after retrying [{sheet_retry_max}] times over [{sheet_retry_max * sheet_load_secs}s]"),
                exception=exception,
            )
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
            return DownloadResult(DownloadStatus.FAILED, [])
        return DownloadResult(DownloadStatus.DOWNLOADED, file_paths)

    @_timed(CTR_ACT_EGRESS_MILLIS)
    def sheet_upload(
        self,
        data_df,
        drive_key,
        workbook_name,
        sheet_name=None,
        sheet_start_row=1,
        sheet_start_column="A",
        add_filter=False,
        raw_columns=None,
        formula_columns=None,
        dropdown_columns=None,
        highlight_cells=None,
        sheet_before=None,
        sheet_after=None,
        print_label=None,
        print_rows=PL_PRINT_ROWS,
        check=True,
        guard=False,
        schema=None,
    ) -> UploadStatus:
        """
        Replaces a tab's values with `data_df`, its grid sized to exactly the data, and caches what was written.
        Raw, formula, dropdown and highlight columns are applied and their format cached beside it for the
        caller to compare; a new tab is placed by `sheet_before` and `sheet_after`. With `check` and a `schema`
        the upload is skipped when the cached tab and its format already match; with `guard` the tab is read
        again first and left when it changed since cached. Returns the upload's status.
        """
        sheet_chunk_rows = 10000
        started_time = time.time()
        name = (workbook_name if sheet_name is None else f"{workbook_name}_{sheet_name}").lower()
        label = workbook_name if sheet_name is None else f"{workbook_name}:{sheet_name}"
        columns = list(data_df.columns)
        start_column_index = ord(sheet_start_column.upper()) - ord("A")

        def _unresolved(_what, _value):
            self.print_log(f"DataFrame upload to sheet [{name}] has unresolvable {_what} [{_value}]", level="error")
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)

        column_letters = {column: self._sheet_column_letter(start_column_index + index) for index, column in enumerate(columns)}
        raw_set = set()
        for column in raw_columns or []:
            if column in (formula_columns or {}):
                continue
            if column in column_letters:
                raw_set.add(column)
            else:
                _unresolved("raw column", column)
        formulas = {}
        for column, template in (formula_columns or {}).items():
            references = re.findall(r"\{([^{}]+)}", template)
            if column not in column_letters or not references or any(reference not in column_letters for reference in references):
                _unresolved("formula column", column)
            else:
                formulas[column] = template
        dropdowns = {}
        for column, options in (dropdown_columns or {}).items():
            if column in column_letters and isinstance(options, list) and options and all(isinstance(option, str) and option for option in options):
                dropdowns[column] = list(options)
            elif column in column_letters and isinstance(options, str) and re.fullmatch(r"[A-Za-z0-9_ ]+![A-Z]+[0-9]*:[A-Z]+[0-9]*", options):
                dropdowns[column] = options
            else:
                _unresolved("dropdown column", column)
        highlights = []
        for reference in highlight_cells or []:
            if re.fullmatch(r"[A-Z]+([0-9]+)?(:[A-Z]+[0-9]*)?", reference) and set(re.findall(r"[A-Z]+", reference)) <= set(column_letters.values()):
                highlights.append(reference)
            else:
                _unresolved("highlight reference", reference)
        formatted = raw_columns is not None or formula_columns is not None or dropdown_columns is not None or highlight_cells is not None

        def _typed(_data_df) -> pl.DataFrame | None:
            if schema is None or not set(schema) <= set(_data_df.columns):
                return None
            return _data_df.select(
                [
                    ((pl.col(_column) * 100).round().cast(pl.Int64) if _dtype == pl.Float64 else pl.col(_column).cast(pl.Utf8).replace("", None) if _dtype == pl.Utf8 else pl.col(_column)).alias(
                        _column
                    )
                    for _column, _dtype in schema.items()
                ]
            )

        def _tab_typed(_tab_df) -> pl.DataFrame | None:
            if schema is None or list(_tab_df.columns) != list(schema):
                return None

            def _tab_parsed(_column, _dtype):
                if _dtype == pl.Date:
                    return pl.coalesce([pl.col(_column).str.to_date(_date_format, strict=False) for _date_format in SHEET_DATE_FORMATS])
                if _dtype.is_numeric():
                    return pl.col(_column).str.replace_all(r"[$£,\s]", "").cast(_dtype, strict=False)
                return pl.col(_column)

            return _typed(_tab_df.with_columns([_tab_parsed(_column, _dtype).alias(_column) for _column, _dtype in schema.items()]))

        cached_df = self.sheet_cached(workbook_name, sheet_name) if guard or (check and schema is not None) else None
        format_path = abspath(f"{self.local_cache}/_sheet_{name}_format.json")
        if check and cached_df is not None and (cached_typed_df := _tab_typed(cached_df)) is not None and cached_typed_df.equals(_typed(data_df)):
            layout = {"raw": sorted(raw_set), "formulas": formulas, "dropdowns": dropdowns, "highlights": highlights}
            if formatted == isfile(format_path) and (not formatted or self._sheet_format_cached(format_path) == layout):
                self.print_log(f"Sheet [{label}] status [{UploadStatus.UNCHANGED.name}] since cached", started=started_time, level="debug")
                return UploadStatus.UNCHANGED
        if guard and cached_df is not None and self._sheet_moved(drive_key, workbook_name, sheet_name, schema, cached_df, _tab_typed):
            self.print_log(f"Sheet [{label}] status [{UploadStatus.MOVED.name}] edited since cached", started=started_time, level="warn")
            return UploadStatus.MOVED
        try:
            date_cols = [c for c in data_df.columns if data_df[c].dtype == pl.Date]
            values_df = data_df.with_columns([pl.col(c).dt.strftime("%Y-%m-%d") for c in date_cols])
            all_values = [values_df.columns] + [["" if v is None else str(v) for v in row] for row in values_df.iter_rows()]
            for column, template in formulas.items():
                column_index = columns.index(column)
                for row_index in range(1, len(all_values)):
                    sheet_row = sheet_start_row + row_index
                    all_values[row_index][column_index] = re.sub(r"\{([^{}]+)}", lambda match, _row=sheet_row: f"{column_letters[match.group(1)]}{_row}", template)
            drive_url = f"https://docs.google.com/spreadsheets/d/{drive_key}" if drive_key is not None else None
            drive_version: str | None = None
            if drive_key is not None and not config.disable_sheet_uploads:
                spreadsheet, credentials = self._sheet_opened(drive_key)
                grid_rows = max(sheet_start_row - 1 + len(all_values), sheet_start_row + 1)
                grid_columns = start_column_index + len(columns)
                worksheets = self._sheet_tabs(drive_key)
                worksheet = next((existing for existing in worksheets if existing.title == sheet_name), None) if sheet_name is not None else next(iter(worksheets), None)
                if worksheet is None:
                    position = self._sheet_insert_index([existing.title for existing in worksheets], sheet_before, sheet_after)
                    worksheet = spreadsheet.add_worksheet(title=str(sheet_name), rows=grid_rows, cols=grid_columns, index=position)
                    worksheets.insert(len(worksheets) if position is None else position, worksheet)
                sheets_service = build("sheets", "v4", http=self._google_authorized_http(credentials), cache_discovery=False)
                clear_fields = (
                    "userEnteredValue" + (",dataValidation" if dropdown_columns is not None else "") + (",userEnteredFormat.textFormat.foregroundColorStyle" if highlight_cells is not None else "")
                )
                layout_requests = [
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": worksheet.id,
                                "gridProperties": {
                                    "rowCount": grid_rows,
                                    "columnCount": grid_columns,
                                },
                            },
                            "fields": "gridProperties.rowCount,gridProperties.columnCount",
                        }
                    },
                    {
                        "repeatCell": {
                            "range": {"sheetId": worksheet.id},
                            "cell": {},
                            "fields": clear_fields,
                        }
                    },
                ]
                letter_index = {letter: start_column_index + index for index, letter in enumerate(column_letters.values())}
                for column, options in dropdowns.items():
                    column_index = start_column_index + columns.index(column)
                    layout_requests.append(
                        {
                            "setDataValidation": {
                                "range": {
                                    "sheetId": worksheet.id,
                                    "startRowIndex": sheet_start_row,
                                    "endRowIndex": sheet_start_row - 1 + len(all_values),
                                    "startColumnIndex": column_index,
                                    "endColumnIndex": column_index + 1,
                                },
                                "rule": {
                                    "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": option} for option in options]}
                                    if isinstance(options, list)
                                    else {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"={options}"}]},
                                    "strict": False,
                                    "showCustomUi": True,
                                },
                            }
                        }
                    )
                for reference in highlights:
                    start_reference, _, end_reference = reference.partition(":")
                    end_reference = end_reference or start_reference
                    start_letters, start_digits = re.match(r"([A-Z]+)([0-9]*)", start_reference).groups()  # type: ignore[union-attr]
                    end_letters, end_digits = re.match(r"([A-Z]+)([0-9]*)", end_reference).groups()  # type: ignore[union-attr]
                    layout_requests.append(
                        {
                            "repeatCell": {
                                "range": {
                                    "sheetId": worksheet.id,
                                    "startRowIndex": int(start_digits) - 1 if start_digits else sheet_start_row - 1,
                                    "endRowIndex": int(end_digits) if end_digits else sheet_start_row - 1 + len(all_values),
                                    "startColumnIndex": letter_index[start_letters],
                                    "endColumnIndex": letter_index[end_letters] + 1,
                                },
                                "cell": {"userEnteredFormat": {"textFormat": {"foregroundColorStyle": {"rgbColor": SHEET_MANUAL_COLOUR}}}},
                                "fields": "userEnteredFormat.textFormat.foregroundColorStyle",
                            }
                        }
                    )
                if add_filter:
                    layout_requests.extend(
                        [
                            {
                                "setBasicFilter": {
                                    "filter": {
                                        "range": {
                                            "sheetId": worksheet.id,
                                            "startRowIndex": sheet_start_row - 1,
                                            "endRowIndex": sheet_start_row - 1 + len(all_values),
                                            "startColumnIndex": start_column_index,
                                            "endColumnIndex": start_column_index + len(data_df.columns),
                                        }
                                    }
                                }
                            },
                            {
                                "updateSheetProperties": {
                                    "properties": {"sheetId": worksheet.id, "gridProperties": {"frozenRowCount": sheet_start_row}},
                                    "fields": "gridProperties.frozenRowCount",
                                }
                            },
                        ]
                    )
                sheets_service.spreadsheets().batchUpdate(spreadsheetId=drive_key, body={"requests": layout_requests}).execute()
                tab_prefix = f"'{sheet_name}'!" if sheet_name is not None else ""
                for chunk_start in range(0, len(all_values), sheet_chunk_rows):
                    chunk = all_values[chunk_start : chunk_start + sheet_chunk_rows]
                    chunk_row = sheet_start_row + chunk_start
                    if not raw_set:
                        sheets_service.spreadsheets().values().update(
                            spreadsheetId=drive_key, range=f"{tab_prefix}{sheet_start_column}{chunk_row}", valueInputOption="USER_ENTERED", body={"values": chunk}
                        ).execute()
                        continue
                    for input_option, input_columns in (("USER_ENTERED", [c for c in columns if c not in raw_set]), ("RAW", [c for c in columns if c in raw_set])):
                        if input_columns:
                            sheets_service.spreadsheets().values().batchUpdate(
                                spreadsheetId=drive_key,
                                body={
                                    "valueInputOption": input_option,
                                    "data": [
                                        {"range": f"{tab_prefix}{column_letters[column]}{chunk_row}", "majorDimension": "COLUMNS", "values": [[row[columns.index(column)] for row in chunk]]}
                                        for column in input_columns
                                    ],
                                },
                            ).execute()
                drive_version = self._sheet_version(drive_key)
            suffix = f"_v{drive_version}" if drive_version is not None else ""
            file_path = abspath(f"{self.local_cache}/_sheet_{name}{suffix}.csv")
            self.csv_write(data_df, file_path)
            if formatted:
                with open(abspath(f"{self.local_cache}/_sheet_{name}_format.json"), "w") as format_file:
                    json.dump({"raw": sorted(raw_set), "formulas": formulas, "dropdowns": dropdowns, "highlights": highlights}, format_file, indent=2, sort_keys=True)
            if drive_version is not None:
                self._sheet_cache_cleanup(name, int(drive_version))
            dataframe_print(
                self.name,
                data_df,
                print_label=print_label,
                print_verb="uploaded",
                print_suffix=f"to [{drive_url or 'local'}][{workbook_name}{'' if sheet_name is None else f':{sheet_name}'}]",
                started=started_time,
                print_rows=print_rows,
            )
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_COLUMNS, len(data_df.columns))
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_SHEET_ROWS, len(data_df))
            return UploadStatus.UPLOADED
        except Exception as exception:
            self.print_log(f"DataFrame failed to upload to sheet [{name}]", exception=exception)
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)
            return UploadStatus.FAILED

    @_timed(CTR_ACT_EGRESS_MILLIS)
    def sheet_update(self, cells, rows, drive_key, workbook_name, sheet_name=None, highlight_cells=None, guard=False, schema=None) -> UploadStatus:
        """
        Writes `cells` ({(row, column): value}) into a tab and appends `rows` (dicts by column) below its data, both raw,
        and colours `highlight_cells` as manual, a column reference colouring the whole column. Columns are the cached
        tab's header: a cell must name one, a row's other keys are left out. With `guard` the tab is read again first
        and left when it changed since cached. Without a key the edit applies to the cached tab, with uploads disabled
        nothing is written. Returns the update's status.
        """
        started_time = time.time()
        label = workbook_name if sheet_name is None else f"{workbook_name}:{sheet_name}"
        drive_url = f"https://docs.google.com/spreadsheets/d/{drive_key}" if drive_key is not None else None
        if not cells and not rows:
            return UploadStatus.UNCHANGED
        cached_df = self.sheet_cached(workbook_name, sheet_name)
        if guard and self._sheet_moved(drive_key, workbook_name, sheet_name, schema, cached_df):
            self.print_log(f"Sheet [{label}] status [{UploadStatus.MOVED.name}] edited since cached", started=started_time, level="warn")
            return UploadStatus.MOVED
        header = list(cached_df.columns) if cached_df is not None else []
        unresolved = sorted({column for _, column in cells if column not in header})
        if unresolved:
            self.print_log(f"Sheet [{label}] status [{UploadStatus.FAILED.name}] unresolvable columns [{', '.join(unresolved)}]", started=started_time, level="error")
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)
            return UploadStatus.FAILED
        try:
            if drive_key is None or config.disable_sheet_uploads:
                cache_path = self._sheet_cache_path((workbook_name if sheet_name is None else f"{workbook_name}_{sheet_name}").lower())
                if drive_key is None and cache_path is not None and cached_df is not None:
                    tab_df = cached_df.with_row_index("__row", offset=2)
                    for (row_number, column), value in cells.items():
                        tab_df = tab_df.with_columns(pl.when(pl.col("__row") == row_number).then(pl.lit(value, dtype=pl.Utf8)).otherwise(pl.col(column)).alias(column))
                    rows_df = pl.DataFrame([{column: None if row.get(column) is None else str(row[column]) for column in header} for row in rows], schema=dict.fromkeys(header, pl.Utf8))
                    pl.concat([tab_df.drop("__row"), rows_df], how="vertical_relaxed").write_csv(cache_path)
                self.print_log(f"Sheet [{label}] status [{UploadStatus.UPLOADED.name}] cells [{len(cells)}] rows [{len(rows)}] to [local]", started=started_time, level="debug")
                return UploadStatus.UPLOADED
            tab_prefix = f"'{sheet_name}'!" if sheet_name is not None else ""
            letters = {column: self._sheet_column_letter(index) for index, column in enumerate(header)}
            service = build("sheets", "v4", http=self._google_authorized_http(self._sheets_credentials()), cache_discovery=False)
            if cells:
                service.spreadsheets().values().batchUpdate(
                    spreadsheetId=drive_key,
                    body={
                        "valueInputOption": "RAW",
                        "data": [{"range": f"{tab_prefix}{letters[column]}{row_number}", "values": [["" if value is None else str(value)]]} for (row_number, column), value in cells.items()],
                    },
                ).execute()
            if rows:
                service.spreadsheets().values().append(
                    spreadsheetId=drive_key,
                    range=f"{tab_prefix}A1",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [["" if row.get(column) is None else str(row[column]) for column in header] for row in rows]},
                ).execute()
            if highlight_cells:
                worksheets = self._sheet_tabs(drive_key)
                sheet_id = next(worksheet.id for worksheet in worksheets if sheet_name is None or worksheet.title == sheet_name)
                letter_index = {letter: index for index, letter in enumerate(letters.values())}
                requests = []
                for reference in highlight_cells:
                    start_reference, _, end_reference = reference.partition(":")
                    start_letters, start_digits = re.match(r"([A-Z]+)([0-9]*)", start_reference).groups()  # type: ignore[union-attr]
                    end_letters, end_digits = re.match(r"([A-Z]+)([0-9]*)", end_reference or start_reference).groups()  # type: ignore[union-attr]
                    cell_range = {"sheetId": sheet_id, "startColumnIndex": letter_index[start_letters], "endColumnIndex": letter_index[end_letters] + 1}
                    if start_digits:
                        cell_range["startRowIndex"] = int(start_digits) - 1
                    if end_digits:
                        cell_range["endRowIndex"] = int(end_digits)
                    requests.append(
                        {
                            "repeatCell": {
                                "range": cell_range,
                                "cell": {"userEnteredFormat": {"textFormat": {"foregroundColorStyle": {"rgbColor": SHEET_MANUAL_COLOUR}}}},
                                "fields": "userEnteredFormat.textFormat.foregroundColorStyle",
                            }
                        }
                    )
                service.spreadsheets().batchUpdate(spreadsheetId=drive_key, body={"requests": requests}).execute()
            self.print_log(f"Sheet [{label}] status [{UploadStatus.UPLOADED.name}] cells [{len(cells)}] rows [{len(rows)}] to [{drive_url}]", started=started_time)
            return UploadStatus.UPLOADED
        except Exception as exception:
            self.print_log(f"Sheet [{label}] status [{UploadStatus.FAILED.name}] to [{drive_url}]", started=started_time, exception=exception)
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)
            return UploadStatus.FAILED

    @_timed(CTR_ACT_MARSHALL_MILLIS)
    def sheet_ensure(self, drive_key, workbook_name, tabs):
        """
        Creates any of `tabs` (name to header columns, in sheet order) the spreadsheet lacks, each placed after the last of
        the tabs before it, else before the first after it, holding just its header row. Existing tabs are never moved.
        """
        if drive_key is None or config.disable_sheet_uploads:
            return []
        started_time = time.time()
        created = []
        try:
            spreadsheet, _ = self._sheet_opened(drive_key)
            worksheets = self._sheet_tabs(drive_key)
            titles = [worksheet.title for worksheet in worksheets]
            order = list(tabs)
            for index, (name, columns) in enumerate(tabs.items()):
                if name in titles:
                    continue
                position = self._sheet_insert_index(titles, order[index + 1 :], order[:index])
                worksheet = spreadsheet.add_worksheet(title=name, rows=2, cols=max(len(columns), 1), index=position)
                if columns:
                    worksheet.update(values=[list(columns)], range_name="A1")
                titles.insert(len(titles) if position is None else position, name)
                worksheets.insert(len(worksheets) if position is None else position, worksheet)
                created.append(name)
            if created:
                self.print_log(f"Sheet [{workbook_name}] tabs created [{', '.join(created)}]", started=started_time)
        except Exception as exception:
            self.print_log(f"Sheet [{workbook_name}] tabs failed to create", exception=exception)
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)
        return created

    @_timed(CTR_ACT_MARSHALL_MILLIS)
    def dropbox_download(self, dropbox_dir: str | None, local_dir: str, check: bool = True):
        """
        Downloads a Dropbox folder into `local_dir`, fetching files missing locally or, with `check`, whose
        content hash differs. Returns each file's (present, downloaded).
        """
        if dropbox_dir is None:
            return collections.OrderedDict()
        started_time = time.time()

        def file_hash(file_name) -> str:
            block_digests: list[bytes] = []
            with open(file_name, "rb") as f:
                while True:
                    block = f.read(4 * 1024 * 1024)
                    if not block:
                        break
                    block_digests.append(hashlib.sha256(block).digest())
            return hashlib.sha256(b"".join(block_digests)).hexdigest()

        local_files = {}
        for local_file in glob.glob(f"{local_dir}/*"):
            local_files[basename(local_file).lower()] = {"hash": file_hash(local_file) if check else None, "modified": int(getmtime(local_file)) if check else None}
        dropbox_files = {}
        service = dropbox.Dropbox(os.getenv("DROPBOX_TOKEN", ""), timeout=int(TIMEOUT_NETWORK_SECONDS))
        cursor: str | None = None
        while True:
            response = service.files_list_folder(dropbox_dir) if cursor is None else service.files_list_folder_continue(cursor)
            for dropbox_file in response.entries:  # type: ignore[union-attr]
                dropbox_files[dropbox_file.name] = {
                    "id": dropbox_file.id,
                    "hash": dropbox_file.content_hash,
                    "modified": int(dropbox_file.client_modified.replace(tzinfo=UTC).timestamp()),
                }
            if response.has_more:  # type: ignore[union-attr]
                cursor = response.cursor  # type: ignore[union-attr]
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
            local_path = abspath(f"{local_dir}/{dropbox_file}").lower()
            label = basename(local_path).split(".")[0]
            dropbox_file_lower = dropbox_file.lower()
            if dropbox_file_lower not in local_files or (
                check and (dropbox_files[dropbox_file]["modified"] != local_files[dropbox_file_lower]["modified"] or dropbox_files[dropbox_file]["hash"] != local_files[dropbox_file_lower]["hash"])
            ):
                try:
                    if not exists(dirname(local_path)):
                        os.makedirs(dirname(local_path))
                    with open(local_path, "wb") as local_file:
                        _, response = service.files_download(path=f"{dropbox_dir}/{dropbox_file}")  # type: ignore[misc]
                        local_file.write(response.content)
                    try:
                        os.utime(local_path, (dropbox_files[dropbox_file]["modified"], dropbox_files[dropbox_file]["modified"]))
                    except Exception as exception:
                        self.print_log(
                            f"File [{label}] downloaded file [{local_path}] modified timestamp set failed [{dropbox_files[dropbox_file]['modified']}]",
                            exception=exception,
                        )
                    local_files[dropbox_file_lower] = {"hash": dropbox_files[dropbox_file]["hash"], "modified": dropbox_files[dropbox_file]["modified"]}
                    file_actioned = True
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                    self.print_log(f"File [{label}] downloaded to [{local_path}]", started=started_time_file)
                except Exception as exception:
                    self.print_log(f"File [{label}] failed to download from [https://www.dropbox.com/home/{dropbox_dir}/{dropbox_file}]", exception=exception)
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
            else:
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                self.print_log(f"File [{label}] cached at [{local_path}]", started=started_time_file, level="debug")
            actioned_files[local_path] = True, file_actioned
        self.print_log(
            f"Directory [{basename(local_dir).title()}] downloaded [{len(actioned_files)}] files from [https://www.dropbox.com/home/{dropbox_dir}]",
            started=started_time,
        )
        return collections.OrderedDict(sorted(actioned_files.items()))

    def drive_synchronise(self, drive_dir, local_dir, check=True, download=True, upload=False):
        """
        Syncs a Drive folder with `local_dir`, skipping names starting `_` or `~$`: downloads files missing
        locally or newer on Drive, and with `upload` uploads files missing on Drive or differing in size or
        hash. Never deletes on either side. Returns each file's (present, downloaded).
        """
        if drive_dir is None:
            return collections.OrderedDict()
        started_time = time.time()

        def file_hash(file_name) -> str:
            hasher = hashlib.new("md5")
            with open(file_name, "rb") as f:
                for block in iter(lambda: f.read(8 * 1024), b""):
                    hasher.update(block)
            return hasher.hexdigest()

        local_files = {}
        actioned_files = {}
        ignore_prefixes = ("_", "~$")
        drive_files = {}
        auth_start = time.perf_counter()
        credentials = google.oauth2.service_account.Credentials.from_service_account_file(  # type: ignore[attr-defined]
            get_file(".google_service_account.json"), scopes=["https://www.googleapis.com/auth/drive"]
        )
        service = build("drive", "v3", http=self._google_authorized_http(credentials), cache_discovery=False)
        force_download = config.force_downloads and not config.disable_drive_downloads
        force_upload = config.force_uploads and not config.disable_drive_uploads
        auth_elapsed_ms = int((time.perf_counter() - auth_start) * 1000)
        marshall_start = time.perf_counter()
        try:
            for local_file in glob.glob(f"{local_dir}/*"):
                if basename(local_file).startswith(ignore_prefixes):
                    continue
                local_files[basename(local_file).lower()] = {"path": local_file, "hash": None, "size": os.path.getsize(local_file), "modified": int(getmtime(local_file)) if check else None}
            token = None
            while True:
                response = (
                    service.files()
                    .list(q=f"'{drive_dir}' in parents", spaces="drive", fields="nextPageToken, files(id, name, modifiedTime, md5Checksum, size)", pageSize=1000, pageToken=token)
                    .execute()
                )
                for drive_file in response.get("files", []):
                    if drive_file["name"].startswith(ignore_prefixes):
                        continue
                    drive_files[drive_file["name"]] = {
                        "id": drive_file["id"],
                        "hash": drive_file.get("md5Checksum"),
                        "size": int(drive_file.get("size", -1)),
                        "modified": int(datetime.strptime(drive_file["modifiedTime"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC).timestamp()),
                    }
                token = response.get("nextPageToken")
                if not token:
                    break
            self.print_log(f"Directory [{basename(local_dir).title()}] listed [{len(drive_files)}] files from [https://drive.google.com/drive/folders/{drive_dir}]", started=started_time)
            started_time = time.time()
            thread_local = threading.local()
            to_download = []
            for drive_file in drive_files:
                local_path = abspath(f"{local_dir}/{drive_file}").lower()
                drive_file_lower = drive_file.lower()
                needs_download = drive_file_lower not in local_files or (check and not force_download and drive_files[drive_file]["modified"] > local_files[drive_file_lower]["modified"])
                if download and not config.disable_drive_downloads and (force_download or needs_download):
                    to_download.append((drive_file, local_path))
                else:
                    self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED)
                    self.print_log(f"File [{basename(local_path).split('.')[0]}] cached at [{local_path}]", level="debug")
                    actioned_files[local_path] = True, False

            def _thread_service():
                if not hasattr(thread_local, "service"):
                    thread_local.service = build("drive", "v3", http=self._google_authorized_http(credentials), cache_discovery=False)
                return thread_local.service

            def _download_one(_drive_file_name, _local_path):
                _file_started = time.time()
                _label = basename(_local_path).split(".")[0]
                _last_error = None
                for _attempt in range(3):
                    if _attempt > 0:
                        time.sleep(2)
                    try:
                        _request = _thread_service().files().get_media(fileId=drive_files[_drive_file_name]["id"])
                        buf = io.BytesIO()
                        downloader = MediaIoBaseDownload(buf, _request)
                        done = False
                        while not done:
                            _, done = downloader.next_chunk()
                        if not exists(dirname(_local_path)):
                            os.makedirs(dirname(_local_path))
                        with open(_local_path, "wb") as f:
                            f.write(buf.getvalue())
                        _utime_error = None
                        try:
                            os.utime(_local_path, (drive_files[_drive_file_name]["modified"], drive_files[_drive_file_name]["modified"]))
                        except Exception as e:
                            _utime_error = e
                        return _drive_file_name, _local_path, _label, _file_started, None, _utime_error
                    except Exception as e:
                        _last_error = e
                return _drive_file_name, _local_path, _label, _file_started, _last_error, None

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(_download_one, df, lp): (df, lp) for df, lp in to_download}
                for future in concurrent.futures.as_completed(futures):
                    drive_file, local_path, label, file_started, download_error, utime_error = future.result()
                    if download_error is None:
                        local_files[drive_file.lower()] = {"hash": drive_files[drive_file]["hash"], "modified": drive_files[drive_file]["modified"]}
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                        self.print_log(f"File [{label}] downloaded to [{local_path}]", started=file_started)
                        if utime_error is not None:
                            self.print_log(f"File [{label}] downloaded file [{local_path}] modified timestamp set failed [{drive_files[drive_file]['modified']}]", exception=utime_error)
                    else:
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
                        self.print_log(f"File [{label}] failed to download to [{local_path}]", exception=download_error)
                    actioned_files[local_path] = True, download_error is None
        finally:
            self.add_counter(CTR_SRC_TIMING, CTR_ACT_MARSHALL_MILLIS, int((time.perf_counter() - marshall_start) * 1000) + (auth_elapsed_ms if download else 0))

        egress_start = time.perf_counter()
        try:
            if upload:
                for local_file in local_files:
                    if not local_file.startswith(ignore_prefixes):
                        started_time_file = time.time()
                        file_actioned = False
                        local_path = abspath(f"{local_dir}/{local_file}").lower()
                        label = basename(local_path).split(".")[0]
                        drive_match = next((k for k in drive_files if k.lower() == local_file), None)
                        needs_upload = drive_match is None
                        if not needs_upload and check and not force_upload:
                            needs_upload = local_files[local_file]["size"] != drive_files[drive_match]["size"]
                            if not needs_upload and not local_file.endswith(".pdf") and drive_files[drive_match]["hash"] is not None:
                                if local_files[local_file]["hash"] is None:
                                    local_files[local_file]["hash"] = file_hash(local_files[local_file]["path"])
                                needs_upload = drive_files[drive_match]["hash"] != local_files[local_file]["hash"]
                        if (force_upload or needs_upload) and not config.disable_drive_uploads:
                            try:
                                data = MediaFileUpload(local_path)
                                drive_id = drive_files[drive_match]["id"] if drive_match is not None else None
                                metadata: dict[str, object] = {"modifiedTime": datetime.fromtimestamp(local_files[local_file]["modified"], UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}
                                if drive_id is None:
                                    metadata["name"] = basename(local_file)
                                    metadata["parents"] = [drive_dir]
                                    request = service.files().create(body=metadata, media_body=data).execute()
                                else:
                                    request = service.files().update(fileId=drive_id, body=metadata, media_body=data).execute()
                                file_actioned = True
                                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_UPLOADED)
                                self.print_log(f"File [{label}] uploaded to [https://drive.google.com/file/d/{request.get('id') if drive_id is None else drive_id}]", started=started_time_file)
                            except Exception as exception:
                                self.print_log(f"File [{label}] failed to upload to [https://drive.google.com/drive/folders/{drive_dir}]", exception=exception)
                                self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)
                        else:
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_PERSISTED)
                            self.print_log(f"File [{label}] verified at [https://drive.google.com/file/d/{drive_files[drive_match]['id']}]", started=started_time_file, level="debug")
                        actioned_files[local_path] = True, file_actioned
        finally:
            self.add_counter(CTR_SRC_TIMING, CTR_ACT_EGRESS_MILLIS, int((time.perf_counter() - egress_start) * 1000) + (auth_elapsed_ms if not download else 0))

        self.print_log(f"Directory [{basename(local_dir).title()}] synchronised [{len(actioned_files)}] files from [https://drive.google.com/drive/folders/{drive_dir}]", started=started_time)
        return collections.OrderedDict(sorted(actioned_files.items()))

    def _sheet_opened(self, drive_key):
        if drive_key not in self._sheet_spreadsheets:
            client = gspread.Client(auth=self._sheets_credentials())
            client.set_timeout(TIMEOUT_NETWORK_SECONDS)
            for attempt in range(3):
                try:
                    self._sheet_spreadsheets[drive_key] = client.open_by_key(drive_key)
                    break
                except gspread.exceptions.APIError as api_exception:
                    if attempt == 2 or api_exception.response.status_code < 500:
                        raise
                    time.sleep(10 * (attempt + 1))
        return self._sheet_spreadsheets[drive_key], self._sheets_credentials()

    @staticmethod
    def _sheet_column_letter(index):
        letters = ""
        index += 1
        while index > 0:
            index, remainder = divmod(index - 1, 26)
            letters = chr(ord("A") + remainder) + letters
        return letters

    @staticmethod
    def _sheet_format_cached(format_path):
        with open(format_path) as format_file:
            return json.load(format_file)

    def _sheet_moved(self, drive_key, workbook_name, sheet_name, schema, cached_df, typed=None) -> bool:
        result = self.sheet_download(drive_key, workbook_name, sheet_name, schema=schema)
        if result.file_status == DownloadStatus.FAILED:
            return True
        if result.file_status != DownloadStatus.DOWNLOADED:
            return False
        sheet_df = pl.read_csv(result.file_paths[0], infer_schema=False, raise_if_empty=False)
        if typed is not None and cached_df is not None:
            sheet_typed_df, cached_typed_df = typed(sheet_df), typed(cached_df)
            if sheet_typed_df is not None and cached_typed_df is not None:
                return not sheet_typed_df.equals(cached_typed_df)
        return not (cached_df is not None and sheet_df.equals(cached_df))

    def _sheet_tabs(self, drive_key):
        if drive_key not in self._sheet_worksheets:
            self._sheet_worksheets[drive_key] = self._sheet_opened(drive_key)[0].worksheets()
        return self._sheet_worksheets[drive_key]

    @staticmethod
    def _sheet_insert_index(titles, before=None, after=None):
        after_indexes = [index for index, title in enumerate(titles) if title in (after or [])]
        if after_indexes:
            return max(after_indexes) + 1
        before_indexes = [index for index, title in enumerate(titles) if title in (before or [])]
        return min(before_indexes) if before_indexes else None

    def _sheet_cache_path(self, name):
        prefix = f"_sheet_{name}_v"
        versioned_files = sorted(
            [(int(basename(path)[len(prefix) : -len(".csv")]), path) for path in glob.glob(abspath(f"{self.local_cache}/{prefix}*.csv")) if basename(path)[len(prefix) : -len(".csv")].isdigit()],
            reverse=True,
        )
        if versioned_files:
            return versioned_files[0][1]
        unversioned_path = abspath(f"{self.local_cache}/_sheet_{name}.csv")
        return unversioned_path if isfile(unversioned_path) else None
