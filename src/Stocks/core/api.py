# -*- coding: utf-8 -*-
"""Yahoo Finance API client – pure Python, no platform dependencies."""
from __future__ import absolute_import

import json
import socket
import threading

try:
    from urllib2 import urlopen, Request
    from urllib import urlencode
    from urllib import quote as _url_quote
except ImportError:
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode
    from urllib.parse import quote as _url_quote

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

# Yahoo Finance search endpoints (try multiple for resilience)
_SEARCH_URLS = [
    "https://query1.finance.yahoo.com/v1/finance/search",
    "https://query2.finance.yahoo.com/v1/finance/search",
]
# Yahoo Finance v8 chart endpoint  (no API key required)
_CHART_URL  = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# Yahoo Finance v7 quote summary (for additional meta like ISIN / market cap)
_QUOTE_SUMMARY_URL = (
    "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    "?modules=assetProfile,price"
)


class YahooFinanceClient(object):
    """Thin wrapper around the unofficial Yahoo Finance JSON API.

    All methods return plain Python dicts/lists – no platform-specific
    types – so this class works identically in Enigma2, Kodi, or any
    standard Python environment.
    """

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _fetch(self, url, timeout=12):
        """Fetch *url* and parse the JSON body.

        Returns an empty dict on any error so callers never have to
        guard against exceptions from network / JSON issues.
        """
        try:
            req = Request(url)
            for key, value in _REQUEST_HEADERS.items():
                req.add_header(key, value)
            # Set a global socket default timeout as safety net for
            # DNS/TLS hangs that urllib timeout does not cover.
            old_timeout = socket.getdefaulttimeout()
            try:
                socket.setdefaulttimeout(timeout)
                response = urlopen(req, timeout=timeout)
                raw = response.read()
            finally:
                socket.setdefaulttimeout(old_timeout)
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            return json.loads(raw)
        except Exception:
            return {}

    def _fetch_with_hard_timeout(self, url, timeout=8):
        """Like _fetch but enforces a hard wall-clock timeout via thread.

        Useful for search requests where DNS/TLS can hang on embedded
        devices, ignoring the socket-level timeout.
        """
        result = [{}]

        def _worker():
            result[0] = self._fetch(url, timeout=timeout)

        t = threading.Thread(target=_worker)
        t.daemon = True
        t.start()
        t.join(timeout + 2)  # hard wall-clock limit
        return result[0]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query):
        """Search for securities by name, ticker, ISIN or WKN.

        Case-insensitive.  Tries multiple Yahoo Finance endpoints for
        resilience (some are blocked/slow on certain networks).

        Returns a list of dicts, each with:
            symbol   – Yahoo ticker symbol (e.g. "SAP.DE")
            name     – long / short name
            exchange – human-readable exchange label
            type     – quote type label (e.g. "Equity", "ETF")
        """
        if not query or not str(query).strip():
            return []

        q = str(query).strip()
        params = urlencode({
            "q":           q,
            "lang":        "de-DE",
            "region":      "DE",
            "quotesCount": 20,
            "newsCount":   0,
            "listsCount":  0,
        })

        data = {}
        for base_url in _SEARCH_URLS:
            data = self._fetch_with_hard_timeout(
                "%s?%s" % (base_url, params), timeout=8
            )
            if data.get("quotes"):
                break

        results = []
        for item in (data.get("quotes") or []):
            if not isinstance(item, dict):
                continue
            symbol = (item.get("symbol") or "").strip()
            if not symbol:
                continue
            name = (
                item.get("longname")
                or item.get("shortname")
                or symbol
            )
            results.append({
                "symbol":   symbol,
                "name":     name,
                "exchange": item.get("exchDisp") or item.get("exchange") or "",
                "type":     item.get("typeDisp")  or item.get("quoteType") or "",
            })
        return results

    def get_quote(self, symbol):
        """Fetch the current price quote for *symbol*.

        Returns a dict with:
            symbol      – normalised ticker
            name        – instrument name
            price       – current / last price (float or None)
            prev_close  – previous close price (float or None)
            change_pct  – percentage change vs prev_close (float or None)
            currency    – ISO currency code (str)
            market_state – "REGULAR", "PRE", "POST", "CLOSED", …
        Returns an empty dict if the symbol is unknown or on error.
        """
        if not symbol:
            return {}

        url  = _CHART_URL.format(symbol=str(symbol).strip())
        data = self._fetch(url)

        try:
            chart = data.get("chart") or {}
            if chart.get("error"):
                return {}
            items = chart.get("result") or []
            if not items:
                return {}
            meta = items[0].get("meta") or {}
        except Exception:
            return {}

        price = meta.get("regularMarketPrice")
        prev_close = (
            meta.get("chartPreviousClose")
            or meta.get("previousClose")
            or meta.get("regularMarketPreviousClose")
        )
        currency     = meta.get("currency") or ""
        name         = meta.get("longName") or meta.get("shortName") or symbol
        market_state = meta.get("marketState") or ""

        change_pct = None
        if price is not None and prev_close:
            try:
                change_pct = (
                    (float(price) - float(prev_close)) / float(prev_close)
                ) * 100.0
            except Exception:
                pass

        return {
            "symbol":       meta.get("symbol") or symbol,
            "name":         name,
            "price":        price,
            "prev_close":   prev_close,
            "change_pct":   change_pct,
            "currency":     currency,
            "market_state": market_state,
        }

    def get_quote_summary(self, symbol):
        """Fetch extended metadata for *symbol* (assetProfile + price module).

        Useful for displaying ISIN (if provided by Yahoo), sector,
        industry, website, etc.

        Returns a dict; empty on error.
        """
        if not symbol:
            return {}
        url  = _QUOTE_SUMMARY_URL.format(symbol=str(symbol).strip())
        data = self._fetch(url)
        try:
            result = (data.get("quoteSummary") or {}).get("result") or []
            if result:
                return result[0]
        except Exception:
            pass
        return {}
