# -*- coding: utf-8 -*-
"""Pure-Python price / alert text formatter.

Reusable across Enigma2, Kodi, CLI, etc.
"""
from __future__ import absolute_import


def format_watchlist_row(item):
    """Return a single display line for a watchlist entry.

    ``item`` is a watchlist dict as stored by :class:`StocksStore`.
    """
    symbol   = item.get("symbol", "")
    name     = item.get("name") or symbol
    price    = item.get("last_price")
    currency = item.get("last_currency") or ""
    chg      = item.get("last_change_pct")

    if price is not None:
        try:
            change_str = _format_pct(chg)
            return "%-30s  %s %.4f%s" % (
                name[:30], currency, float(price), change_str
            )
        except Exception:
            pass
    return "%-30s  [%s]" % (name[:30], symbol)


def format_alert_message(name, symbol, price, baseline, change_pct, currency):
    """Return the alert notification text shown in UI / LCD.

    ``name``       – instrument name
    ``symbol``     – ticker
    ``price``      – current price
    ``baseline``   – price at the time of the last alert / first fetch
    ``change_pct`` – absolute percentage change (always positive)
    ``currency``   – ISO currency code
    """
    try:
        p_delta = float(price) - float(baseline)
        sign    = "+" if p_delta >= 0 else "-"
        return "%s: %s%.2f%%  |  %.4f %s" % (
            name, sign, abs(float(change_pct)), float(price), currency
        )
    except Exception:
        return "%s: %.4f %s" % (name, float(price), currency)


def format_price(price, currency):
    """Return e.g. ``'182.3400 EUR'`` or ``'N/A'``."""
    if price is None:
        return "N/A"
    try:
        cur = (" " + currency) if currency else ""
        return "%.4f%s" % (float(price), cur)
    except Exception:
        return str(price)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _format_pct(chg):
    """Return ``'  (+1.23%)'`` or empty string."""
    if chg is None:
        return ""
    try:
        sign = "+" if float(chg) >= 0 else ""
        return "  (%s%.2f%%)" % (sign, float(chg))
    except Exception:
        return ""
