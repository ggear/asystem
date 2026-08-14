"""Real-time read-through proxy feeds, served at ``/api/v1/feed/{feed}/{resource}[/{argument}]``.

A feed answers "what is the value right now" and nothing else: no history, no counters, no database,
no plugin run lock.

Each resource is declared by ``WRANGLE_HTTP_API_<RESOURCE>_CONTEXT`` in ``.env_all`` and published by
nginx under its own hostname, so the origin path is hidden and ``/BHP.AX`` reaches
``/api/v1/feed/equity/prices/BHP.AX``:

- ``https://<resource>.data.janeandgraham.com`` on the LAN
- ``https://<resource>.janeandgraham.com`` from the Internet, through the Cloudflare tunnel

The edge name cannot carry the ``.data`` infix because Cloudflare's Universal SSL covers first-level
subdomains only. See ``equity_prices`` for the Google Sheets integration.
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
    """Map ``{feed}/{resource}[/{argument}]`` onto a registered resource, bound to its path argument.

    Returns a callable taking the query params. Raises ``FeedError`` 404 for an unknown feed or resource.
    """
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
    """Live price for one ticker.

    ``GET /api/v1/feed/equity/prices/{symbol}`` or ``?symbol=`` — ``https://prices.data.janeandgraham.com/{symbol}`` on the LAN, or
    ``https://prices.janeandgraham.com/{symbol}`` through the tunnel.
    Symbols are Yahoo tickers (``BHP.AX``, ``^AXJO``, ``BRK-B``), upper-cased, matched against ``FEED_SYMBOL_PATTERN``.

    Payload::

        {
            "symbol": "BHP.AX",
            "price": 61.14,
            "currency": "AUD",
            "previousClose": 63.45,
            "change": -2.31,
            "exchange": "ASX"
        }

    ``previousClose`` and ``change`` may be null. Cached ``FEED_CACHE_SECONDS`` per symbol behind a
    per-symbol lock, so concurrent sheet cells collapse to one upstream fetch. Errors: 400
    ``invalid_symbol``, 404 ``unknown_symbol``, 502 ``upstream_error``.

    **Google Sheets.** The public hostname is protected by a Cloudflare Access **Service Auth** policy,
    so the caller must present a service token. ``IMPORTDATA`` cannot send headers and therefore cannot
    be used; the integration is an Apps Script custom function.

    Set up the credentials once, in the sheet:

    1. Zero Trust > Access controls > Service credentials > Service Tokens > **Create**. The Client
       Secret is shown **once** — there is no way to display it again, only to delete and recreate.
    2. Extensions > Apps Script > **Project Settings** > Script Properties > Add script property:

       ===============================  =========================================
       Property                         Value
       ===============================  =========================================
       ``CF_ACCESS_CLIENT_ID``          the Client ID, ending in ``.access``
       ``CF_ACCESS_CLIENT_SECRET``      the Client Secret
       ===============================  =========================================

       Names are case-sensitive. The token never enters this repo — it lives only in Script Properties.

    3. Extensions > Apps Script > ``Code.gs``, then paste::

        var WRANGLE_SUFFIX = {
          '': '',
          'ASX': '.AX',
          'LON': '.L',
          'TSE': '.TO',
          'FRA': '.F',
          'NYSE': '',
          'NASDAQ': '',
          'NYSEARCA': '',
          'BATS': ''
        };

        function WRANGLE_PRICE(symbol, exchange) {
          var props = PropertiesService.getScriptProperties();
          var id = props.getProperty('CF_ACCESS_CLIENT_ID');
          var secret = props.getProperty('CF_ACCESS_CLIENT_SECRET');
          if (!id || !secret) throw new Error('Script Properties CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET are not set');
          if (!symbol) throw new Error('symbol is required, e.g. =WRANGLE_PRICE("BHP", "ASX")');
          var key = String(exchange || '').trim().toUpperCase();
          var suffix = WRANGLE_SUFFIX[key];
          if (suffix === undefined) throw new Error('unknown exchange [' + key + ']');
          var response = UrlFetchApp.fetch(
            'https://prices.janeandgraham.com/' + encodeURIComponent(String(symbol).trim() + suffix), {
              headers: {
                'CF-Access-Client-Id': id,
                'CF-Access-Client-Secret': secret
              },
              muteHttpExceptions: true
            });
          if (response.getResponseCode() != 200) throw new Error(response.getContentText());
          return JSON.parse(response.getContentText()).price;
        }

    4. Run these from the editor to check each layer before using the function in a cell, since a custom
       function reports errors poorly in a sheet::

        function testCredentials() {
          var props = PropertiesService.getScriptProperties();
          Logger.log('id set: %s, secret set: %s',
            !!props.getProperty('CF_ACCESS_CLIENT_ID'), !!props.getProperty('CF_ACCESS_CLIENT_SECRET'));
        }

        function testPrice() {
          Logger.log('ASX listing: %s', WRANGLE_PRICE('BHP', 'ASX'));
          Logger.log('US listing: %s', WRANGLE_PRICE('BRK-B', ''));
          Logger.log('index: %s', WRANGLE_PRICE('^AXJO', 'ASX'));
        }

        function testDenied() {
          var response = UrlFetchApp.fetch('https://prices.janeandgraham.com/BHP.AX', {muteHttpExceptions: true});
          Logger.log('unauthenticated status: %s (expect 403)', response.getResponseCode());
        }

    Used as ``=WRANGLE_PRICE(B8, K8)`` with the ticker in one column and the exchange code in another,
    so one column serves both conventions — ``GOOGLEFINANCE`` wants the exchange as a **prefix**
    (``ASX:BHP``) while Yahoo wants it as a **suffix** (``BHP.AX``), and ``WRANGLE_SUFFIX`` maps between
    them. A blank exchange means a US listing, where both conventions are the bare ticker.

    As a fallback behind ``GOOGLEFINANCE`` rather than a replacement::

        =IFERROR(GOOGLEFINANCE(IF(K8="", B8, CONCATENATE(K8, ":", B8))), WRANGLE_PRICE(B8, K8))

    Note ``IFERROR`` catches an error, not a wrong answer — a stale or zero price from ``GOOGLEFINANCE``
    passes through and the feed is never consulted.

    Sheets caches custom function results and cannot be forced to refresh, so where cadence matters write
    values into cells from a time-driven trigger. Each cell is one ``UrlFetchApp`` call — roughly 2-6s
    cold and 25ms once the per-symbol cache is warm — so a large sheet recalculating cold can reach the
    30 second custom function limit.
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
