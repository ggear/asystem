import email.utils
import json
import threading
import time
import urllib.error

import googleapiclient.errors
import gspread.exceptions
import httplib2
import yfinance.exceptions

from .config import Backoff

GOOGLE_RATE_REASONS = frozenset({"rateLimitExceeded", "userRateLimitExceeded"})


class Throttle:
    def __init__(self, name: str, backoff: Backoff, print_log):
        self.name = name
        self.backoff = backoff
        self.print_log = print_log
        self.waited = 0.0
        self.resume = 0.0
        self.lock = threading.Lock()

    def reset(self):
        with self.lock:
            self.waited, self.resume = 0.0, 0.0

    def call(self, send, failed, headers=lambda response: getattr(response, "headers", None)):
        if self.resume > time.time():
            self._waited(self.resume - time.time(), "rate limit reset")
            self.resume = 0.0
        for attempt in range(self.backoff.retries + 1):
            try:
                response = send()
            except Exception as exception:
                failure = failed(exception)
                if failure is None:
                    raise
                status, failure_headers = failure
                retry = _seconds_until(failure_headers.get("Retry-After") if failure_headers is not None else None)
                if status not in self.backoff.statuses or attempt == self.backoff.retries or not self._waited(self.backoff.first_seconds * 2**attempt if retry is None else retry, f"HTTP {status}"):
                    raise
                continue
            response_headers = headers(response)
            if response_headers is not None and self.backoff.remaining_header is not None:
                remaining = response_headers.get(self.backoff.remaining_header)
                self.print_log(f"Throttle [{self.name}] rate limit remaining [{remaining}]", level="debug")
                if remaining is not None and remaining.strip() == "0":
                    reset = _seconds_until(response_headers.get(self.backoff.reset_header)) if self.backoff.reset_header is not None else None
                    self.resume = time.time() + (reset or self.backoff.first_seconds)
            return response
        raise TimeoutError(f"Throttle [{self.name}] retries exhausted")

    def _waited(self, seconds, reason) -> bool:
        with self.lock:
            seconds = min(max(seconds, 0.0), self.backoff.max_seconds, self.backoff.budget_seconds - self.waited)
            if seconds <= 0:
                return False
            self.waited += seconds
            left = self.backoff.budget_seconds - self.waited
        self.print_log(f"Throttle [{self.name}] waiting [{seconds:.1f}s] for [{reason}] with [{left:.1f}s] of the run's budget left", level="warn")
        time.sleep(seconds)
        return True


def urllib_failed(exception):
    return (exception.code, exception.headers) if isinstance(exception, urllib.error.HTTPError) else None


def google_failed(exception):
    if isinstance(exception, googleapiclient.errors.HttpError):
        try:
            error = json.loads(exception.content.decode("utf-8")).get("error", {})
        except (ValueError, AttributeError):
            error = {}
        details = [*(error.get("errors") or []), *(error.get("details") or [])] if isinstance(error, dict) else []
        reasons = {detail.get("reason") for detail in details if isinstance(detail, dict)}
        status = 429 if exception.resp.status == 403 and reasons & GOOGLE_RATE_REASONS else exception.resp.status
        return status, {"Retry-After": exception.resp.get("retry-after")}
    if isinstance(exception, gspread.exceptions.APIError):
        return exception.response.status_code, exception.response.headers
    if isinstance(exception, (OSError, httplib2.HttpLib2Error)):
        return 503, None
    return None


def yahoo_failed(exception):
    return (429, None) if isinstance(exception, yfinance.exceptions.YFRateLimitError) else None


def _seconds_until(value):
    if value is None:
        return None
    now = time.time()
    try:
        number = float(value)
        return number - now if number > 1e9 else number
    except ValueError:
        try:
            return email.utils.parsedate_to_datetime(value).timestamp() - now
        except (TypeError, ValueError):
            return None
