"""Real-time read-through proxy feeds, served at ``/api/v1/feed/{feed}/{resource}[/{argument}]``.

A feed answers "what is the value right now" and nothing else: no history, no counters, no database,
no plugin run lock. Each resource is declared by ``WRANGLE_HTTP_API_<RESOURCE>_CONTEXT`` in
``.env_all`` and published by nginx under its own hostname.
"""

import re
import threading
import time
from collections.abc import Callable

import yfinance as yf
from requests.exceptions import RequestException

from wrangle.plugin.config import FEED_CACHE_SECONDS, FEED_SYMBOL_PATTERN

FEED_ROOT = "feed"


class FeedError(Exception):
    """Caller or upstream fault, rendered as ``{"error": {"code", "message"}}`` with ``status``."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def resolve(path: str) -> tuple[Callable[[dict], dict], str | None]:
    """Map ``{feed}/{resource}[/{argument}]`` onto a callable taking the query params, 404 if unknown."""
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) < 2 or len(segments) > 3:
        raise FeedError("not_found", f"unknown feed resource [{path}]", 404)
    feed_name, resource_name = segments[0], segments[1]
    argument = segments[2] if len(segments) == 3 else None
    resources = FEEDS.get(feed_name)
    if resources is None:
        raise FeedError("unknown_feed", f"unknown feed [{feed_name}]", 404)
    resource = resources.get(resource_name)
    if resource is None:
        raise FeedError("unknown_resource", f"unknown resource [{resource_name}] for feed [{feed_name}]", 404)
    return lambda params: resource(argument, params), argument


def paths() -> dict[str, str]:
    """Every registered resource as ``{"<feed>.<resource>": "feed/<feed>/<resource>"}`` for the API index."""
    return {f"{feed_name}.{resource_name}": f"{FEED_ROOT}/{feed_name}/{resource_name}" for feed_name, resources in FEEDS.items() for resource_name in resources}


def equity_prices(argument: str | None, params: dict) -> dict:
    """Live price for one Yahoo ticker, cached ``FEED_CACHE_SECONDS`` per symbol behind a per-symbol lock.

    Argument or ``?symbol=``, upper-cased and matched against ``FEED_SYMBOL_PATTERN``. Returns
    ``symbol``, ``price``, ``currency``, ``previousClose``, ``change``, ``exchange``, the last two null
    when Yahoo has no previous close. Errors 400 ``invalid_symbol``, 404 ``unknown_symbol``, 502
    ``upstream_error``. Google Sheets integration is in ``src/build/resources/sheets/equity_price.js``.
    """
    symbol = _validated(argument if argument is not None else params.get("symbol"))
    with _lock_for(symbol):
        cached = _CACHE.get(symbol)
        if cached is not None and time.time() - cached[0] < FEED_CACHE_SECONDS:
            return cached[1]
        result = _priced(symbol)
        _CACHE[symbol] = (time.time(), result)
        return result



FEEDS: dict[str, dict[str, Callable[[str | None, dict], dict]]] = {
    "equity": {
        "prices": equity_prices,
    },
}

_CACHE: dict[str, tuple[float, dict]] = {}
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_LOCK = threading.Lock()
_SYMBOL = re.compile(FEED_SYMBOL_PATTERN)


def _validated(symbol) -> str:
    symbol = str(symbol or "").strip().upper()
    if not _SYMBOL.match(symbol):
        raise FeedError("invalid_symbol", f"invalid symbol [{symbol}]")
    return symbol



def _lock_for(symbol: str) -> threading.Lock:
    with _LOCKS_LOCK:
        return _LOCKS.setdefault(symbol, threading.Lock())


def _priced(symbol: str) -> dict:
    try:
        info = dict(yf.Ticker(symbol).fast_info)
    except RequestException as error:
        raise FeedError("upstream_error", f"quote failed for [{symbol}] [{error}]", 502) from error
    except Exception as error:
        raise FeedError("unknown_symbol", f"no price for [{symbol}]", 404) from error
    price = info.get("lastPrice")
    if price is None:
        raise FeedError("unknown_symbol", f"no price for [{symbol}]", 404)
    previous_close = info.get("previousClose")
    return {
        "symbol": symbol,
        "price": round(float(price), 4),
        "currency": _text(info.get("currency")),
        "previousClose": None if previous_close is None else round(float(previous_close), 4),
        "change": None if previous_close is None else round(float(price) - float(previous_close), 4),
        "exchange": _text(info.get("exchange")),
    }


def _text(value) -> str | None:
    return None if value is None else str(value)
