import collections
import concurrent.futures
import contextlib
import fnmatch
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
from ._throttle import google_failed, urllib_failed, yahoo_failed
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
        Fetches each Redbark API path in `url_paths`, following `limit` and `offset` pages when `paged`, through the plugin's
        `redbark` throttle when it registers one, caches the returned rows' `columns` in `local_path` stamped now, and returns
        them as `data_frame`. Without `check` any cache is kept and downloads disabled serve the cache; a failed path comes back
        in `errors` with its HTTP status, leaves the cache as it was and is logged unless `ignore`.
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
            def _sent():
                return urllib.request.urlopen(
                    urllib.request.Request(
                        f"{REDBARK_URL}{_path}",
                        headers={"Authorization": f"Bearer {os.environ.get('REDBARK_TOKEN', '')}", "Content-Type": "application/json", "User-Agent": "curl/8.0"},
                    ),
                    timeout=TIMEOUT_NETWORK_SECONDS,
                    context=ssl._create_unverified_context(),
                )

            return json.loads(self._throttled("redbark", _sent, urllib_failed).read().decode())

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
                data_df = self._throttled("yahoo", lambda: yf.Ticker(ticker).history(start=start, end=end_exclusive, timeout=TIMEOUT_NETWORK_SECONDS), yahoo_failed)
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

    def sheet_typed(self, tab_df, schema) -> pl.DataFrame:
        """
        Types a tab read as text for comparison: the columns `schema` declares parsed as the sheet displays them, amounts in
        cents, dates ISO, text stripped with blanks as null, and any other column kept as stripped text.
        """

        def _typed(_column):
            _dtype = (schema or {}).get(_column, pl.Utf8)
            _text = pl.col(_column).cast(pl.Utf8).str.strip_chars()
            if _dtype == pl.Date:
                return pl.coalesce([_text.str.to_date(_date_format, strict=False) for _date_format in SHEET_DATE_FORMATS]).alias(_column)
            if _dtype == pl.Float64:
                return (_text.str.replace_all(r"[$£,\s]", "").cast(pl.Float64, strict=False) * 100).round().cast(pl.Int64).alias(_column)
            if _dtype.is_numeric():
                return _text.str.replace_all(r"[$£,\s]", "").cast(_dtype, strict=False).alias(_column)
            return _text.replace("", None).alias(_column)

        return tab_df.select([_typed(_column) for _column in tab_df.columns])

    @_timed(CTR_ACT_MARSHALL_MILLIS)
    def sheet_download(self, drive_key, workbook_name, sheet_name=None, sheet_start_row=1, sheet_load_secs=10, sheet_retry_max=5, check=True, schema=None, print_rows=PL_PRINT_ROWS):
        """
        Reads one tab, or several in one read, into versioned caches: a tab whose content, typed by `schema`, differs from its
        latest cached version is written as the next version and `DOWNLOADED`, else `CACHED`, and a tab the spreadsheet lacks
        is read empty. A list of tabs returns a result per tab. With `schema` no blank column is dropped, declared numeric
        columns are stripped of `$`, `£` and `,`, and declared dates are rewritten ISO.
        """
        started_time = time.time()
        sheet_names = sheet_name if isinstance(sheet_name, list) else [sheet_name]
        names = [(workbook_name if name is None else f"{workbook_name}_{name}").lower() for name in sheet_names]
        label = workbook_name if sheet_name is None or isinstance(sheet_name, list) else f"{workbook_name}:{sheet_name}"

        def _results(_statuses):
            _tab_results = {_name: DownloadResult(_status, [_path] if _status != DownloadStatus.FAILED else []) for _name, (_status, _path) in zip(sheet_names, _statuses, strict=True)}
            return _tab_results if isinstance(sheet_name, list) else _tab_results[sheet_name]

        def _cached():
            _paths = [self._sheet_cache_path(_name) for _name in names]
            return [(DownloadStatus.CACHED, _path) if _path is not None else (DownloadStatus.FAILED, "") for _path in _paths]

        def _tab_dataframe(_cells, _label):
            _numeric_pattern = r"^\s*[-+]?[$£]?[\d,]*\.?\d+\s*$"
            _data_df = (
                self.dataframe_new(data=_cells[1:], orient="row", print_label=_label, print_rows=-1)
                if len(_cells) > 1
                else pl.DataFrame(schema={f"column_{_index}": pl.Utf8 for _index in range(len(_cells[0]) if _cells else 0)})
            )
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
            return _data_df.with_columns(pl.all().cast(pl.Utf8))

        if config.disable_sheet_downloads or drive_key is None:
            cached = _cached()
            if config.disable_sheet_downloads and drive_key is not None and all(_status == DownloadStatus.FAILED for _status, _ in cached):
                self.print_log(f"File [{label}] sheet download skipped, downloads disabled and no cache available")
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_SKIPPED)
            else:
                self.print_log(f"File [{label}] cached", started=started_time, level="debug")
            return _results(cached)
        if not config.force_downloads and not check:
            cached = _cached()
            if all(_status == DownloadStatus.CACHED for _status, _ in cached):
                self.print_log(f"File [{label}] cached", started=started_time, level="debug")
                return _results(cached)
        drive_url = "https://docs.google.com/spreadsheets/d/" + drive_key
        retries = 0
        caught_exception = None
        statuses = []
        data_dfs = []
        try:
            while retries < sheet_retry_max:
                try:
                    retries += 1
                    cells_by_title = self._sheet_values(drive_key, sheet_names)
                    data_dfs.clear()
                    for title in sheet_names:
                        if title not in cells_by_title:
                            self.print_log(f"File [{workbook_name}:{title}] read empty, no such tab at [{drive_url}]", level="warn")
                        cells = cells_by_title.get(title, [])[sheet_start_row - 1 :]
                        width = max((len(row) for row in cells), default=0)
                        data_dfs.append(_tab_dataframe([[*row, *([""] * (width - len(row)))] for row in cells], f"{workbook_name}:{title}"))
                    caught_exception = None
                    break
                except SheetStillLoadingError as exception:
                    time.sleep(sheet_load_secs)
                    caught_exception = exception
            if caught_exception is not None:
                raise caught_exception
            for title, name, data_df in zip(sheet_names, names, data_dfs, strict=True):
                tab_label = workbook_name if title is None else f"{workbook_name}_{title}"
                version, latest_path = self._sheet_version_latest(name)
                latest_df = self.sheet_cached(workbook_name, title) if latest_path is not None else None
                if latest_df is not None and list(latest_df.columns) == list(data_df.columns) and self.sheet_typed(latest_df, schema).equals(self.sheet_typed(data_df, schema)):
                    self.print_log(f"Sheet [{workbook_name}:{title}] cached version [{version}]", level="debug")
                    statuses.append((DownloadStatus.CACHED, latest_path))
                    continue
                file_path = abspath(f"{self.local_cache}/_sheet_{name}_v{version + 1}.csv")
                self.csv_write(data_df, file_path, print_label=tab_label, print_rows=-1)
                self._sheet_cache_cleanup(name)
                dataframe_print(
                    self.name, data_df, print_label=tab_label, print_verb="downloaded", print_suffix=f"version [{version + 1}] from [{drive_url}]", print_rows=print_rows, started=started_time
                )
                statuses.append((DownloadStatus.DOWNLOADED, file_path))
        except Exception as exception:
            self.print_log(
                f"DataFrame [{label}] unavailable at [{drive_url}]" + ("" if retries < sheet_retry_max else f" after retrying [{sheet_retry_max}] times over [{sheet_retry_max * sheet_load_secs}s]"),
                exception=exception,
            )
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
            return _results([(DownloadStatus.FAILED, "")] * len(sheet_names))
        return _results(statuses)

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
        decimal_columns=None,
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
        Raw, formula, dropdown, highlight and two decimal columns are applied and their format cached beside it for the
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
        decimals = []
        for column in decimal_columns or []:
            if column in column_letters:
                decimals.append(column)
            else:
                _unresolved("decimal column", column)
        formatted = raw_columns is not None or formula_columns is not None or dropdown_columns is not None or highlight_cells is not None or decimal_columns is not None
        layout = {"raw": sorted(raw_set), "formulas": formulas, "dropdowns": dropdowns, "highlights": highlights, **({"decimals": sorted(decimals)} if decimal_columns is not None else {})}

        cached_df = self.sheet_cached(workbook_name, sheet_name) if guard or (check and schema is not None) else None
        format_path = abspath(f"{self.local_cache}/_sheet_{name}_format.json")
        if (
            check
            and schema is not None
            and cached_df is not None
            and list(cached_df.columns) == columns
            and self.sheet_typed(cached_df, schema).equals(
                self.sheet_typed(data_df.with_columns([pl.col(column).dt.strftime("%Y-%m-%d") for column in columns if data_df[column].dtype == pl.Date]).cast(pl.Utf8), schema)
            )
            and formatted == isfile(format_path)
            and (not formatted or self._sheet_format_cached(format_path) == layout)
        ):
            self.print_log(f"Sheet [{label}] status [{UploadStatus.UNCHANGED.name}] since cached", started=started_time, level="debug")
            return UploadStatus.UNCHANGED
        if guard and cached_df is not None and self._sheet_moved(drive_key, workbook_name, sheet_name, schema):
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
            if drive_key is not None and not config.disable_sheet_uploads:
                spreadsheet, credentials = self._sheet_opened(drive_key)
                grid_rows = max(sheet_start_row - 1 + len(all_values), sheet_start_row + 1)
                grid_columns = start_column_index + len(columns)
                worksheets = self._sheet_tabs(drive_key)
                worksheet = next((existing for existing in worksheets if existing.title == sheet_name), None) if sheet_name is not None else next(iter(worksheets), None)
                if worksheet is None:
                    position = self._sheet_insert_index([existing.title for existing in worksheets], sheet_before, sheet_after)
                    worksheet = self._throttled("google_sheets", lambda: spreadsheet.add_worksheet(title=str(sheet_name), rows=grid_rows, cols=grid_columns, index=position), google_failed)
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
                for column in decimals:
                    column_index = start_column_index + columns.index(column)
                    layout_requests.append(
                        {
                            "repeatCell": {
                                "range": {
                                    "sheetId": worksheet.id,
                                    "startRowIndex": sheet_start_row,
                                    "endRowIndex": sheet_start_row - 1 + len(all_values),
                                    "startColumnIndex": column_index,
                                    "endColumnIndex": column_index + 1,
                                },
                                "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0.00"}}},
                                "fields": "userEnteredFormat.numberFormat",
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
                self._throttled("google_sheets", sheets_service.spreadsheets().batchUpdate(spreadsheetId=drive_key, body={"requests": layout_requests}).execute, google_failed)
                tab_prefix = f"'{sheet_name}'!" if sheet_name is not None else ""
                for chunk_start in range(0, len(all_values), sheet_chunk_rows):
                    chunk = all_values[chunk_start : chunk_start + sheet_chunk_rows]
                    chunk_row = sheet_start_row + chunk_start
                    if not raw_set:
                        self._throttled(
                            "google_sheets",
                            sheets_service.spreadsheets()
                            .values()
                            .update(spreadsheetId=drive_key, range=f"{tab_prefix}{sheet_start_column}{chunk_row}", valueInputOption="USER_ENTERED", body={"values": chunk})
                            .execute,
                            google_failed,
                        )
                        continue
                    for input_option, input_columns in (("USER_ENTERED", [c for c in columns if c not in raw_set]), ("RAW", [c for c in columns if c in raw_set])):
                        if input_columns:
                            self._throttled(
                                "google_sheets",
                                sheets_service.spreadsheets()
                                .values()
                                .batchUpdate(
                                    spreadsheetId=drive_key,
                                    body={
                                        "valueInputOption": input_option,
                                        "data": [
                                            {"range": f"{tab_prefix}{column_letters[column]}{chunk_row}", "majorDimension": "COLUMNS", "values": [[row[columns.index(column)] for row in chunk]]}
                                            for column in input_columns
                                        ],
                                    },
                                )
                                .execute,
                                google_failed,
                            )
            file_path = abspath(f"{self.local_cache}/_sheet_{name}_v{self._sheet_version_latest(name)[0] + 1}.csv")
            self.csv_write(data_df, file_path)
            if formatted:
                with open(format_path, "w") as format_file:
                    json.dump(layout, format_file, indent=2, sort_keys=True)
            self._sheet_cache_cleanup(name)
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
        if guard and cached_df is not None and self._sheet_moved(drive_key, workbook_name, sheet_name, schema):
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
                self._throttled(
                    "google_sheets",
                    service.spreadsheets()
                    .values()
                    .batchUpdate(
                        spreadsheetId=drive_key,
                        body={
                            "valueInputOption": "RAW",
                            "data": [{"range": f"{tab_prefix}{letters[column]}{row_number}", "values": [["" if value is None else str(value)]]} for (row_number, column), value in cells.items()],
                        },
                    )
                    .execute,
                    google_failed,
                )
            if rows:
                self._throttled(
                    "google_sheets",
                    service.spreadsheets()
                    .values()
                    .append(
                        spreadsheetId=drive_key,
                        range=f"{tab_prefix}A1",
                        valueInputOption="RAW",
                        insertDataOption="INSERT_ROWS",
                        body={"values": [["" if row.get(column) is None else str(row[column]) for column in header] for row in rows]},
                    )
                    .execute,
                    google_failed,
                )
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
                self._throttled("google_sheets", service.spreadsheets().batchUpdate(spreadsheetId=drive_key, body={"requests": requests}).execute, google_failed)
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
                worksheet = self._throttled(
                    "google_sheets", lambda name=name, columns=columns, position=position: spreadsheet.add_worksheet(title=name, rows=2, cols=max(len(columns), 1), index=position), google_failed
                )
                if columns:
                    self._throttled("google_sheets", lambda worksheet=worksheet, columns=columns: worksheet.update(values=[list(columns)], range_name="A1"), google_failed)
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

    def drive_synchronise(self, drive_dir, local_dir, download=True, upload=False, errors=None):
        """
        Syncs a Drive folder with `local_dir` by the MD5 each file had at its last sync, kept in `_drive_synced.json`, skipping
        names starting `_` or `~$`. A download takes a file Drive changed, Drive winning a file changed on both sides as
        `conflicted`; an upload, after listing Drive again, sends a file changed only locally and skips one Drive changed too
        as `conflicted`, and lists nothing when no local file changed since its sync. Without a recorded MD5 the newer side wins
        once. A name listed twice is left alone, the plugin's download-only names are never uploaded, and nothing is deleted
        on either side. Returns each file's status.
        """
        if drive_dir is None:
            return collections.OrderedDict()
        started_time = time.time()
        statuses: dict[str, str] = {}
        duplicates: set[str] = set()
        manifest_path = abspath(f"{local_dir}/_drive_synced.json")
        manifest: dict[str, str] = {}
        if isfile(manifest_path):
            try:
                with open(manifest_path) as manifest_file:
                    manifest = json.load(manifest_file)
            except Exception as exception:
                self.print_log(f"Directory [{basename(local_dir).title()}] manifest unreadable at [{manifest_path}], newer side wins", exception=exception, level="warn")

        def _problem(_name, _code, _detail):
            if errors is not None and _code in self.error_codes:
                self.error(errors, "Drive", _name, _code, _detail)
            else:
                self.print_log(f"File [{_name}] {_detail}", level="error")
                self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)

        def _recorded(_name, _hash):
            manifest[_name] = _hash
            with open(f"{manifest_path}.tmp", "w") as _manifest_file:
                json.dump(dict(sorted(manifest.items())), _manifest_file, indent=2)
            os.replace(f"{manifest_path}.tmp", manifest_path)

        def _download_only(_name):
            return any(fnmatch.fnmatch(_name, _pattern) for _pattern in self.drive_download_only)

        if not download and not config.force_reprocessing and not config.force_uploads:
            local_hashes = {
                basename(path).lower(): (abspath(path).lower(), self._file_md5(path))
                for path in glob.glob(f"{local_dir}/*")
                if isfile(path) and not basename(path).startswith(DRIVE_IGNORE_PREFIXES) and not _download_only(basename(path).lower())
            }
            if all(manifest.get(name) == file_hash for name, (_, file_hash) in local_hashes.items()):
                self.print_log(f"Directory [{basename(local_dir).title()}] unchanged since its last sync, not listed", started=started_time, level="debug")
                return collections.OrderedDict(sorted((path, DriveStatus.VERIFIED) for path, _ in local_hashes.values()))

        auth_start = time.perf_counter()
        credentials = google.oauth2.service_account.Credentials.from_service_account_file(  # type: ignore[attr-defined]
            get_file(".google_service_account.json"), scopes=["https://www.googleapis.com/auth/drive"]
        )
        service = build("drive", "v3", http=self._google_authorized_http(credentials), cache_discovery=False)
        auth_elapsed_ms = int((time.perf_counter() - auth_start) * 1000)

        def _listed():
            _local_files = {
                basename(_path).lower(): {"path": abspath(_path).lower(), "hash": self._file_md5(_path), "modified": int(getmtime(_path))}
                for _path in glob.glob(f"{local_dir}/*")
                if isfile(_path) and not basename(_path).startswith(DRIVE_IGNORE_PREFIXES)
            }
            _drive_listed: dict[str, list[dict]] = {}
            _token = None
            while True:
                _response = self._throttled(
                    "google_drive",
                    service.files()
                    .list(q=f"'{drive_dir}' in parents and trashed = false", spaces="drive", fields="nextPageToken, files(id, name, modifiedTime, md5Checksum)", pageSize=1000, pageToken=_token)
                    .execute,
                    google_failed,
                )
                for _drive_file in _response.get("files", []):
                    if not _drive_file["name"].startswith(DRIVE_IGNORE_PREFIXES):
                        _drive_listed.setdefault(_drive_file["name"].lower(), []).append(
                            {
                                "id": _drive_file["id"],
                                "name": _drive_file["name"],
                                "hash": _drive_file.get("md5Checksum"),
                                "modified": int(datetime.strptime(_drive_file["modifiedTime"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC).timestamp()),
                            }
                        )
                _token = _response.get("nextPageToken")
                if not _token:
                    break
            _drive_files = {}
            for _name, _listings in sorted(_drive_listed.items()):
                if len(_listings) == 1:
                    _drive_files[_name] = _listings[0]
                elif _download_only(_name):
                    for _listing in _listings:
                        _stem, _extension = os.path.splitext(_name)
                        _drive_files[f"{_stem}_{_listing['id'].lower()}{_extension}"] = _listing
                else:
                    duplicates.add(_name)
                    if download:
                        _problem(_name, "DRIVE_DUPLICATE", f"listed [{len(_listings)}] times on Drive, left alone")
            self.drive_ids.update({_name: _drive_file["id"] for _name, _drive_file in _drive_files.items()})
            self.print_log(f"Directory [{basename(local_dir).title()}] listed [{len(_drive_files)}] files from [https://drive.google.com/drive/folders/{drive_dir}]", started=started_time)
            return _local_files, _drive_files

        marshall_start = time.perf_counter()
        try:
            local_files, drive_files = _listed()
            thread_local = threading.local()
            to_download = []
            for drive_name, drive_file in drive_files.items() if download else []:
                local_path = abspath(f"{local_dir}/{drive_name}").lower()
                local_file = local_files.get(drive_name)
                recorded = manifest.get(drive_name)
                if local_file is not None and local_file["hash"] == drive_file["hash"]:
                    if recorded != drive_file["hash"]:
                        _recorded(drive_name, drive_file["hash"])
                    statuses[local_path] = DriveStatus.CACHED
                    continue
                if config.disable_drive_downloads:
                    statuses[local_path] = DriveStatus.CACHED
                    continue
                if local_file is None:
                    to_download.append((drive_name, local_path, False))
                elif recorded is None:
                    if drive_file["modified"] > local_file["modified"] or config.force_downloads:
                        to_download.append((drive_name, local_path, False))
                    else:
                        statuses[local_path] = DriveStatus.CACHED
                elif drive_file["hash"] != recorded:
                    to_download.append((drive_name, local_path, local_file["hash"] != recorded))
                else:
                    statuses[local_path] = DriveStatus.CACHED
                    self.print_log(f"File [{basename(local_path).split('.')[0]}] cached at [{local_path}]", level="debug")

            def _thread_service():
                if not hasattr(thread_local, "service"):
                    thread_local.service = build("drive", "v3", http=self._google_authorized_http(credentials), cache_discovery=False)
                return thread_local.service

            def _download_one(_drive_name, _local_path):
                _file_started = time.time()

                def _fetched():
                    _buffer = io.BytesIO()
                    _downloader = MediaIoBaseDownload(_buffer, _thread_service().files().get_media(fileId=drive_files[_drive_name]["id"]))
                    _done = False
                    while not _done:
                        _, _done = _downloader.next_chunk()
                    return _buffer.getvalue()

                try:
                    _content = self._throttled("google_drive", _fetched, google_failed)
                    os.makedirs(dirname(_local_path), exist_ok=True)
                    with open(f"{_local_path}.tmp", "wb") as _local_file:
                        _local_file.write(_content)
                    os.replace(f"{_local_path}.tmp", _local_path)
                    with contextlib.suppress(OSError):
                        os.utime(_local_path, (drive_files[_drive_name]["modified"], drive_files[_drive_name]["modified"]))
                    return _file_started, None
                except Exception as exception:
                    return _file_started, exception

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(_download_one, drive_name, local_path): (drive_name, local_path, conflicted) for drive_name, local_path, conflicted in to_download}
                for future in concurrent.futures.as_completed(futures):
                    drive_name, local_path, conflicted = futures[future]
                    file_started, download_error = future.result()
                    label = basename(local_path).split(".")[0]
                    if download_error is None:
                        _recorded(drive_name, self._file_md5(local_path))
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_DOWNLOADED)
                        if conflicted:
                            statuses[local_path] = DriveStatus.CONFLICTED
                            _problem(drive_name, "DRIVE_CONFLICT", "changed both locally and on Drive since the last sync, Drive's taken")
                        else:
                            statuses[local_path] = DriveStatus.DOWNLOADED
                            self.print_log(f"File [{label}] downloaded to [{local_path}]", started=file_started)
                    else:
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_ERRORED)
                        self.print_log(f"File [{label}] failed to download to [{local_path}]", exception=download_error)
                        statuses[local_path] = DriveStatus.FAILED
            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_CACHED, sum(1 for status in statuses.values() if status == DriveStatus.CACHED))
        finally:
            self.add_counter(CTR_SRC_TIMING, CTR_ACT_MARSHALL_MILLIS, int((time.perf_counter() - marshall_start) * 1000) + (auth_elapsed_ms if download else 0))

        egress_start = time.perf_counter()
        try:
            if upload:
                if download:
                    local_files, drive_files = _listed()
                for local_name, local_file in local_files.items():
                    started_time_file = time.time()
                    local_path = local_file["path"]
                    label = basename(local_path).split(".")[0]
                    if statuses.get(local_path) in (DriveStatus.CONFLICTED, DriveStatus.FAILED) or local_name in duplicates or _download_only(local_name):
                        continue
                    drive_file = drive_files.get(local_name)
                    recorded = manifest.get(local_name)
                    if drive_file is not None and drive_file["hash"] == local_file["hash"]:
                        if recorded != local_file["hash"]:
                            _recorded(local_name, local_file["hash"])
                        if not config.force_uploads:
                            self.add_counter(CTR_SRC_SOURCES, CTR_ACT_PERSISTED)
                            self.print_log(f"File [{label}] verified at [https://drive.google.com/file/d/{drive_file['id']}]", started=started_time_file, level="debug")
                            statuses[local_path] = DriveStatus.VERIFIED
                            continue
                    elif drive_file is not None and (local_file["hash"] == recorded if recorded is not None else drive_file["modified"] > local_file["modified"]):
                        statuses[local_path] = DriveStatus.CACHED
                        continue
                    elif drive_file is not None and recorded is not None and drive_file["hash"] != recorded:
                        statuses[local_path] = DriveStatus.CONFLICTED
                        if local_name not in self.drive_conflicts:
                            self.drive_conflicts.add(local_name)
                            _problem(local_name, "DRIVE_CONFLICT", "changed on Drive during the run, upload skipped")
                        continue
                    if config.disable_drive_uploads:
                        statuses[local_path] = DriveStatus.CACHED
                        continue
                    try:
                        media = MediaFileUpload(local_path)
                        metadata: dict[str, object] = {"modifiedTime": datetime.fromtimestamp(local_file["modified"], UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}
                        if drive_file is None:
                            metadata["name"] = basename(local_path)
                            metadata["parents"] = [drive_dir]
                            drive_id = self._throttled("google_drive", service.files().create(body=metadata, media_body=media).execute, google_failed).get("id")
                            self.drive_ids[local_name] = drive_id
                        else:
                            drive_id = drive_file["id"]
                            self._throttled("google_drive", service.files().update(fileId=drive_id, body=metadata, media_body=media).execute, google_failed)
                        _recorded(local_name, local_file["hash"])
                        statuses[local_path] = DriveStatus.UPLOADED
                        self.add_counter(CTR_SRC_SOURCES, CTR_ACT_UPLOADED)
                        self.print_log(f"File [{label}] uploaded to [https://drive.google.com/file/d/{drive_id}]", started=started_time_file)
                    except Exception as exception:
                        statuses[local_path] = DriveStatus.FAILED
                        self.print_log(f"File [{label}] failed to upload to [https://drive.google.com/drive/folders/{drive_dir}]", exception=exception)
                        self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)
        finally:
            self.add_counter(CTR_SRC_TIMING, CTR_ACT_EGRESS_MILLIS, int((time.perf_counter() - egress_start) * 1000) + (auth_elapsed_ms if not download else 0))

        self.print_log(f"Directory [{basename(local_dir).title()}] synchronised [{len(statuses)}] files from [https://drive.google.com/drive/folders/{drive_dir}]", started=started_time)
        return collections.OrderedDict(sorted(statuses.items()))

    def drive_rename(self, drive_dir, local_dir, name, renamed):
        """
        Renames a synced file to `renamed`: on Drive by its id from the last listing, keeping its id and revisions, then the
        cached copy and its manifest entry. With Drive uploads disabled, or no id listed, only the cached copy is renamed.
        Returns whether the rename was done.
        """
        started_time = time.time()
        drive_id = self.drive_ids.get(name.lower())
        if drive_dir is not None and drive_id is not None and not config.disable_drive_uploads:
            try:
                credentials = google.oauth2.service_account.Credentials.from_service_account_file(  # type: ignore[attr-defined]
                    get_file(".google_service_account.json"), scopes=["https://www.googleapis.com/auth/drive"]
                )
                self._throttled(
                    "google_drive",
                    build("drive", "v3", http=self._google_authorized_http(credentials), cache_discovery=False).files().update(fileId=drive_id, body={"name": renamed}).execute,
                    google_failed,
                )
                self.drive_ids[renamed.lower()] = self.drive_ids.pop(name.lower())
            except Exception as exception:
                self.print_log(f"File [{name}] failed to rename to [{renamed}] on Drive", exception=exception)
                self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)
                return False
        try:
            os.rename(abspath(f"{local_dir}/{name}").lower(), abspath(f"{local_dir}/{renamed}").lower())
            manifest_path = abspath(f"{local_dir}/_drive_synced.json")
            if isfile(manifest_path):
                with open(manifest_path) as manifest_file:
                    manifest = json.load(manifest_file)
                if name.lower() in manifest:
                    manifest[renamed.lower()] = manifest.pop(name.lower())
                    with open(f"{manifest_path}.tmp", "w") as manifest_file:
                        json.dump(dict(sorted(manifest.items())), manifest_file, indent=2)
                    os.replace(f"{manifest_path}.tmp", manifest_path)
        except Exception as exception:
            self.print_log(f"File [{name}] failed to rename to [{renamed}] locally", exception=exception)
            self.add_counter(CTR_SRC_FILES, CTR_ACT_ERRORED)
            return False
        self.print_log(f"File [{name}] renamed to [{renamed}]", started=started_time)
        return True

    def _throttled(self, name, send, failed):
        throttle = self.throttles.get(name)
        return send() if throttle is None else throttle.call(send, failed)

    @staticmethod
    def _file_md5(file_path) -> str:
        hasher = hashlib.new("md5")
        with open(file_path, "rb") as file:
            for block in iter(lambda: file.read(64 * 1024), b""):
                hasher.update(block)
        return hasher.hexdigest()

    def _sheet_opened(self, drive_key):
        if drive_key not in self._sheet_spreadsheets:
            client = gspread.Client(auth=self._sheets_credentials())
            client.set_timeout(TIMEOUT_NETWORK_SECONDS)
            self._sheet_spreadsheets[drive_key] = self._throttled("google_sheets", lambda: client.open_by_key(drive_key), google_failed)
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

    def _sheet_moved(self, drive_key, workbook_name, sheet_name, schema) -> bool:
        return self.sheet_download(drive_key, workbook_name, sheet_name, schema=schema).file_status != DownloadStatus.CACHED

    def _sheet_values(self, drive_key, titles):
        sheets_service = build("sheets", "v4", http=self._google_authorized_http(self._sheets_credentials()), cache_discovery=False)
        sheet_titles = [
            sheet["properties"]["title"]
            for sheet in sorted(
                self._throttled("google_sheets", sheets_service.spreadsheets().get(spreadsheetId=drive_key, fields="sheets.properties(title,index)").execute, google_failed).get("sheets", []),
                key=lambda sheet: sheet["properties"].get("index", 0),
            )
        ]
        resolved = {title: sheet_titles[0] if title is None and sheet_titles else title for title in titles}
        present = [title for title in titles if resolved[title] in sheet_titles]
        value_ranges = (
            self._throttled(
                "google_sheets",
                sheets_service.spreadsheets().values().batchGet(spreadsheetId=drive_key, ranges=[f"'{resolved[title]}'" for title in present], valueRenderOption="FORMATTED_VALUE").execute,
                google_failed,
            ).get("valueRanges", [])
            if present
            else []
        )
        return {title: value_range.get("values", []) for title, value_range in zip(present, value_ranges, strict=True)}

    def _sheet_tabs(self, drive_key):
        if drive_key not in self._sheet_worksheets:
            spreadsheet = self._sheet_opened(drive_key)[0]
            self._sheet_worksheets[drive_key] = self._throttled("google_sheets", spreadsheet.worksheets, google_failed)
        return self._sheet_worksheets[drive_key]

    @staticmethod
    def _sheet_insert_index(titles, before=None, after=None):
        after_indexes = [index for index, title in enumerate(titles) if title in (after or [])]
        if after_indexes:
            return max(after_indexes) + 1
        before_indexes = [index for index, title in enumerate(titles) if title in (before or [])]
        return min(before_indexes) if before_indexes else None

    def _sheet_cache_path(self, name):
        path = self._sheet_version_latest(name)[1]
        if path is not None:
            return path
        unversioned_path = abspath(f"{self.local_cache}/_sheet_{name}.csv")
        return unversioned_path if isfile(unversioned_path) else None

    def _sheet_versions(self, name):
        prefix = f"_sheet_{name}_v"
        return sorted(
            [(int(basename(path)[len(prefix) : -len(".csv")]), path) for path in glob.glob(abspath(f"{self.local_cache}/{prefix}*.csv")) if basename(path)[len(prefix) : -len(".csv")].isdigit()],
            reverse=True,
        )

    def _sheet_version_latest(self, name):
        versions = self._sheet_versions(name)
        return versions[0] if versions else (0, None)

    def _sheet_cache_cleanup(self, name):
        for _, file_path in self._sheet_versions(name)[2:]:
            os.remove(file_path)
            self.print_log(f"File [{name}] deleted old version [{file_path}]", level="debug")
