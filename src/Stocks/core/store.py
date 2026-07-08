# -*- coding: utf-8 -*-
"""JSON-backed watchlist and settings storage – pure Python."""
from __future__ import absolute_import

import json
import os

SETTINGS_FILE  = "/etc/enigma2/stocks_settings.json"
WATCHLIST_FILE = "/etc/enigma2/stocks_watchlist.json"
# Optional mirror into the Enigma2 global settings file. Pass None (or another
# path) at construction on non-Enigma2 platforms (e.g. Kodi) to disable it.
ENIGMA2_SETTINGS_FILE = "/etc/enigma2/settings"

DEFAULT_SETTINGS = {
    "currency":             "EUR",
    "alert_threshold_pct":  5.0,
    "output_target":        "both",   # "ui" | "lcd" | "both"
    "polling_interval_sec": 300,
    "message_timeout_sec":  8,
}


class StocksStore(object):
    """Platform-agnostic persistence layer.

    Stores two JSON files:
    - ``settings_file``  – user preferences
    - ``watchlist_file`` – list of watched stocks with cached quote data

    Both paths can be overridden at construction time, which is useful for
    unit testing and for Kodi where the config directory differs.
    """

    def __init__(
        self,
        settings_file=SETTINGS_FILE,
        watchlist_file=WATCHLIST_FILE,
        enigma2_settings_file=ENIGMA2_SETTINGS_FILE,
    ):
        self.settings_file = settings_file
        self.watchlist_file = watchlist_file
        # None disables the Enigma2 settings mirror (non-Enigma2 platforms).
        self.enigma2_settings_file = enigma2_settings_file

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _read_json(self, path, fallback):
        try:
            with open(path, "r") as fh:
                return json.load(fh)
        except Exception:
            return fallback

    def _write_json(self, path, data):
        try:
            folder = os.path.dirname(path)
            if folder and not os.path.isdir(folder):
                os.makedirs(folder)
            with open(path, "w") as fh:
                json.dump(data, fh, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def get_settings(self):
        """Return merged settings dict (defaults + persisted values)."""
        merged = DEFAULT_SETTINGS.copy()
        merged.update(self._read_json(self.settings_file, {}))
        return merged

    def save_settings(self, settings):
        merged = DEFAULT_SETTINGS.copy()
        merged.update(settings or {})
        self._write_json(self.settings_file, merged)

    # ------------------------------------------------------------------
    # Watchlist
    # ------------------------------------------------------------------

    def get_watchlist(self):
        """Return the list of watched stock dicts."""
        data = self._read_json(self.watchlist_file, [])
        return data if isinstance(data, list) else []

    def save_watchlist(self, watchlist):
        self._write_json(self.watchlist_file, watchlist or [])

    def add_to_watchlist(self, stock):
        """Add *stock* to the watchlist.

        *stock* must be a dict with at least a ``symbol`` key.

        Returns ``True`` if the stock was added, ``False`` if it was
        already present.
        """
        if not isinstance(stock, dict):
            return False
        symbol = stock.get("symbol", "").strip().upper()
        if not symbol:
            return False
        watchlist = self.get_watchlist()
        for item in watchlist:
            if isinstance(item, dict) and item.get("symbol", "").upper() == symbol:
                return False
        watchlist.append({
            "symbol":           symbol,
            "name":             stock.get("name") or symbol,
            "exchange":         stock.get("exchange") or "",
            "type":             stock.get("type") or "",
            "isin":             stock.get("isin") or "",
            "wkn":              stock.get("wkn") or "",
            # Cached quote (populated by the polling engine)
            "last_price":       None,
            "last_currency":    "",
            "last_change_pct":  None,
            # Baseline price for alert calculation
            "last_alert_price": None,
        })
        self.save_watchlist(watchlist)
        self._sync_watchlist_to_enigma2()
        return True

    def remove_from_watchlist(self, index):
        """Remove the item at *index*.  Returns True on success."""
        watchlist = self.get_watchlist()
        if index < 0 or index >= len(watchlist):
            return False
        watchlist.pop(index)
        self.save_watchlist(watchlist)
        self._sync_watchlist_to_enigma2()
        return True

    def update_stock_data(self, symbol, price, currency, change_pct,
                          set_alert_price=False):
        """Persist a fresh quote for *symbol*."""
        watchlist = self.get_watchlist()
        sym_upper = symbol.upper()
        changed   = False
        for item in watchlist:
            if not isinstance(item, dict):
                continue
            if item.get("symbol", "").upper() != sym_upper:
                continue
            item["last_price"]      = price
            item["last_currency"]   = currency
            item["last_change_pct"] = change_pct
            if item.get("last_alert_price") is None or set_alert_price:
                item["last_alert_price"] = price
            changed = True
        if changed:
            self.save_watchlist(watchlist)

    # ------------------------------------------------------------------
    # Enigma2 /etc/enigma2/settings sync
    # ------------------------------------------------------------------

    def _sync_watchlist_to_enigma2(self):
        """Mirror watchlist symbols into /etc/enigma2/settings so that
        deploying via .env is possible and the data survives a factory
        reset of the JSON files."""
        settings_path = self.enigma2_settings_file
        if not settings_path:
            return
        watchlist = self.get_watchlist()
        symbols = ",".join(
            item.get("symbol", "") for item in watchlist
            if isinstance(item, dict) and item.get("symbol")
        )
        try:
            lines = []
            if os.path.exists(settings_path):
                with open(settings_path, "r") as fh:
                    for raw in fh:
                        if not raw.strip().startswith("config.plugins.stocks.watchlist"):
                            lines.append(raw)
            # Remove trailing empty lines
            while lines and not lines[-1].strip():
                lines.pop()
            lines.append("config.plugins.stocks.watchlist=%s\n" % symbols)
            with open(settings_path, "w") as fh:
                fh.writelines(lines)
        except Exception:
            pass

    def load_watchlist_from_enigma2(self):
        """Read config.plugins.stocks.watchlist from /etc/enigma2/settings
        and add any symbols not yet in the JSON watchlist."""
        settings_path = self.enigma2_settings_file
        if not settings_path or not os.path.exists(settings_path):
            return
        try:
            with open(settings_path, "r") as fh:
                for raw in fh:
                    line = raw.strip()
                    if line.startswith("config.plugins.stocks.watchlist="):
                        value = line.split("=", 1)[1].strip()
                        if value:
                            self._merge_symbols(value.split(","))
                        return
        except Exception:
            pass

    def _merge_symbols(self, symbols):
        """Add symbols from the settings file that are not yet in the
        JSON watchlist."""
        watchlist = self.get_watchlist()
        existing = set(
            item.get("symbol", "").upper()
            for item in watchlist if isinstance(item, dict)
        )
        added = False
        for sym in symbols:
            sym = sym.strip().upper()
            if not sym or sym in existing:
                continue
            watchlist.append({
                "symbol":           sym,
                "name":             sym,
                "exchange":         "",
                "type":             "",
                "isin":             "",
                "wkn":              "",
                "last_price":       None,
                "last_currency":    "",
                "last_change_pct":  None,
                "last_alert_price": None,
            })
            existing.add(sym)
            added = True
        if added:
            self.save_watchlist(watchlist)
