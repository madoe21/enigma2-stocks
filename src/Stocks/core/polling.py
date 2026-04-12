# -*- coding: utf-8 -*-
"""Platform-neutral polling engine.

Fetches live quotes for every watched stock, updates the store, and
returns alert-message strings for stocks whose price has moved beyond
the configured threshold since the last alert baseline.

No Enigma2 / Kodi / timer dependencies – can be called from any
scheduler (Enigma2 eTimer, Kodi xbmc.Monitor, cron, etc.).
"""
from __future__ import absolute_import

from .formatter import format_alert_message


class StocksPollingEngine(object):

    def __init__(self, api):
        self.api = api

    def run(self, store):
        """Fetch quotes, detect alerts, update the store.

        Parameters
        ----------
        store : StocksStore
            Provides ``get_settings()``, ``get_watchlist()``,
            ``update_stock_data()``.

        Returns
        -------
        list[str]
            Human-readable alert messages (one per triggered stock).
            Empty list when no alerts fired.
        """
        settings  = store.get_settings()
        threshold = _to_float(settings.get("alert_threshold_pct", 5.0))
        watchlist = store.get_watchlist()
        alerts    = []

        for item in (watchlist or []):
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol", "")
            if not symbol:
                continue

            try:
                quote = self.api.get_quote(symbol)
            except Exception:
                continue

            price = quote.get("price")
            if price is None:
                continue

            currency   = quote.get("currency") or ""
            change_pct = quote.get("change_pct")
            name       = item.get("name") or symbol
            baseline   = item.get("last_alert_price")

            fire_alert = False
            if baseline is not None and threshold > 0:
                try:
                    moved_pct = (
                        abs(float(price) - float(baseline)) / abs(float(baseline))
                    ) * 100.0
                    if moved_pct >= threshold:
                        fire_alert = True
                        alerts.append(
                            format_alert_message(
                                name, symbol, price, baseline,
                                moved_pct, currency
                            )
                        )
                except Exception:
                    pass

            store.update_stock_data(
                symbol, price, currency, change_pct,
                set_alert_price=fire_alert,
            )

        return alerts


def _to_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0
