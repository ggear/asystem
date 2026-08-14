import re
import threading
import time
from collections.abc import Callable

import yfinance as yf
from requests.exceptions import RequestException

from wrangle.plugin.config import FEED_CACHE_SECONDS, FEED_SEARCH_LIMIT, FEED_SYMBOL_PATTERN

FEED_ROOT = "feed"


class FeedError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def resolve(path: str) -> tuple[Callable[[dict], dict], str | None]:
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
    return {f"{feed_name}.{resource_name}": f"{FEED_ROOT}/{feed_name}/{resource_name}" for feed_name, resources in FEEDS.items() for resource_name in resources}


def equity_quote(argument: str | None, params: dict) -> dict:
    symbol = _validated(argument if argument is not None else params.get("symbol"))
    with _lock_for(symbol):
        cached = _CACHE.get(symbol)
        if cached is not None and time.time() - cached[0] < FEED_CACHE_SECONDS:
            return cached[1]
        result = _quoted(symbol)
        _CACHE[symbol] = (time.time(), result)
        return result


def equity_symbols(argument: str | None, params: dict) -> dict:
    query = argument if argument is not None else params.get("q")
    if not query:
        raise FeedError("invalid_query", "query [q] must not be empty")
    limit = _limited(params.get("limit"))
    try:
        found = yf.Lookup(query).get_all(count=limit)
    except RequestException as error:
        raise FeedError("upstream_error", f"lookup failed for [{query}] [{error}]", 502) from error
    except Exception as error:
        raise FeedError("unknown_query", f"no matches for [{query}]", 404) from error
    matches = []
    if found is not None and len(found) > 0:
        for symbol, row in found.head(limit).iterrows():
            matches.append({
                "symbol": str(symbol),
                "name": _text(row.get("shortName")),
                "exchange": _text(row.get("exchange")),
                "type": _text(row.get("quoteType")),
            })
    return {"query": query, "matches": matches}


FEEDS: dict[str, dict[str, Callable[[str | None, dict], dict]]] = {
    "equity": {
        "quotes": equity_quote,
        "symbols": equity_symbols,
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


def _limited(limit) -> int:
    if limit is None:
        return FEED_SEARCH_LIMIT
    try:
        value = int(limit)
    except ValueError:
        raise FeedError("invalid_limit", f"invalid limit [{limit}]") from None
    if value < 1:
        raise FeedError("invalid_limit", f"invalid limit [{limit}]")
    return min(value, FEED_SEARCH_LIMIT)


def _lock_for(symbol: str) -> threading.Lock:
    with _LOCKS_LOCK:
        return _LOCKS.setdefault(symbol, threading.Lock())


def _quoted(symbol: str) -> dict:
    try:
        info = dict(yf.Ticker(symbol).fast_info)
    except RequestException as error:
        raise FeedError("upstream_error", f"quote failed for [{symbol}] [{error}]", 502) from error
    except Exception as error:
        raise FeedError("unknown_symbol", f"no quote for [{symbol}]", 404) from error
    price = info.get("lastPrice")
    if price is None:
        raise FeedError("unknown_symbol", f"no quote for [{symbol}]", 404)
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
