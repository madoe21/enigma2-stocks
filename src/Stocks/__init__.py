# -*- coding: utf-8 -*-
from __future__ import absolute_import

import gettext

from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

PLUGIN_DOMAIN = "Stocks"
PLUGIN_PATH = "Extensions/Stocks/locale"

_DE_FALLBACK = {
    "Stock market watchlist and price alerts": "Aktien-Watchlist und Kursalarme",
    "Stocks Watchlist": "Aktien-Watchlist",
    "Search Stocks": "Aktien suchen",
    "Settings": "Einstellungen",
    "Search": "Suchen",
    "Add": "Hinzufügen",
    "Remove": "Entfernen",
    "Refresh": "Aktualisieren",
    "Back": "Zurück",
    "Cancel": "Abbrechen",
    "Save": "Speichern",
    "No entries": "Keine Einträge",
    "No stock selected": "Keine Aktie ausgewählt",
    "Added to watchlist": "Zur Watchlist hinzugefügt",
    "Already in watchlist": "Bereits in der Watchlist",
    "Remove from watchlist?": "Von Watchlist entfernen?",
    "Settings saved": "Einstellungen gespeichert",
    "Currency": "Währung",
    "Alert threshold": "Alarm-Schwellenwert",
    "Output target": "Ausgabeziel",
    "UI only": "Nur UI",
    "LCD only": "Nur LCD",
    "UI + LCD": "UI + LCD",
    "Polling interval (s)": "Abfrage-Intervall (s)",
    "Message timeout (s)": "Meldungsdauer (s)",
    "Enter stock name, ISIN or WKN": "Aktienname, ISIN oder WKN eingeben",
    "Left/Right changes value": "Links/Rechts ändert den Wert",
    "Refresh now": "Jetzt aktualisieren",
    "OK/GREEN=Refresh  RED=Remove  BLUE=Search  YELLOW=Settings":
        "OK/GRÜN=Aktualisieren  ROT=Entfernen  BLAU=Suchen  GELB=Einstellungen",
    "BLUE=Search  OK/GREEN=Add to watchlist":
        "BLAU=Suchen  OK/GRÜN=Zur Watchlist hinzufügen",
    "Price alert": "Kursalarm",
    "Poll executed": "Abfrage ausgeführt",
    "No search results": "Keine Suchergebnisse",
    "Search error": "Suchfehler",
    "Searching...": "Suche läuft...",
}


def localeInit():
    gettext.bindtextdomain(PLUGIN_DOMAIN, resolveFilename(SCOPE_PLUGINS, PLUGIN_PATH))


def _(txt):
    translated = gettext.dgettext(PLUGIN_DOMAIN, txt)
    if translated != txt:
        return translated

    try:
        lang = language.getLanguage()[:2]
    except Exception:
        lang = "en"

    if lang == "de":
        return _DE_FALLBACK.get(txt, txt)
    return txt


localeInit()
try:
    language.addCallback(localeInit)
except Exception:
    pass
