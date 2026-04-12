# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import threading

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.Directories import SCOPE_PLUGINS, resolveFilename

try:
    from enigma import (
        RT_HALIGN_LEFT,
        RT_HALIGN_RIGHT,
        RT_HALIGN_CENTER,
        RT_VALIGN_CENTER,
        eListboxPythonMultiContent,
        gFont,
    )
except Exception:
    RT_HALIGN_LEFT = 0
    RT_HALIGN_RIGHT = 0
    RT_HALIGN_CENTER = 0
    RT_VALIGN_CENTER = 0
    eListboxPythonMultiContent = None
    gFont = None

try:
    from Screens.VirtualKeyBoard import VirtualKeyBoard
    _HAS_VKB = True
except ImportError:
    _HAS_VKB = False

from enigma import eTimer

from . import _
from .core.formatter import format_price  # noqa: F401

SUPPORT_LINE = "Buy me a coffee: https://buymeacoffee.com/madoe21"

def _timer_connect(timer, callback):
    try:
        timer.timeout.connect(callback)
    except Exception:
        timer.callback.append(callback)


# ---------------------------------------------------------------------------
# Column layout constants for main watchlist
# ---------------------------------------------------------------------------
_COL_NAME_X = 0
_COL_NAME_W = 340
_COL_SYM_X = 344
_COL_SYM_W = 140
_COL_PRICE_X = 488
_COL_PRICE_W = 220
_COL_CHG_X = 712
_COL_CHG_W = 140
_COL_EXCH_X = 856
_COL_EXCH_W = 284
_ROW_H = 38

# Colours
_COL_UP = 0x00CC44       # green – price up
_COL_DOWN = 0xFF4444     # red – price down
_COL_FLAT = 0xCCCCCC     # grey – no change / no data
_COL_TEXT = 0xFFFFFF     # default text
_COL_DIM = 0x888888      # dimmed text
_COL_WARM = 0xFF8800     # orange – accent


def _fmt_pct(chg):
    """Format percentage change with sign and colour."""
    if chg is None:
        return "-", _COL_FLAT
    try:
        v = float(chg)
        sign = "+" if v >= 0 else ""
        text = "%s%.2f%%" % (sign, v)
        color = _COL_UP if v > 0 else (_COL_DOWN if v < 0 else _COL_FLAT)
        return text, color
    except Exception:
        return "-", _COL_FLAT


def _fmt_price(price, currency):
    """Format price for display."""
    if price is None:
        return "-"
    try:
        cur = " %s" % currency if currency else ""
        return "%.2f%s" % (float(price), cur)
    except Exception:
        return str(price)


# ===========================================================================
# Main screen – watchlist with multi-content table
# ===========================================================================

class StocksMainScreen(Screen):

    skin = """
        <screen name="StocksMainScreen" position="center,90" size="1180,640" title="Stocks">
            <widget source="title"       render="Label" position="20,10"  size="1140,36" font="Regular;30" />
            <widget name="updated"       position="20,52"  size="1140,28" font="Regular;22" />
            <widget name="header_name"   position="20,84"  size="340,28" font="Regular;20" />
            <widget name="header_sym"    position="364,84" size="140,28" font="Regular;20" />
            <widget name="header_price"  position="508,84" size="220,28" font="Regular;20" />
            <widget name="header_chg"    position="732,84" size="140,28" font="Regular;20" />
            <widget name="header_exch"   position="876,84" size="284,28" font="Regular;20" />
            <widget name="list" position="20,116" size="1140,436" scrollbarMode="showOnDemand" />
            <widget source="support" render="Label" position="20,558" size="1140,24" font="Regular;18" foregroundColor="#666666" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png"    position="20,585"  size="200,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"  position="230,585" size="200,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="440,585" size="200,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/blue.png"   position="650,585" size="200,30" alphatest="on" />
            <widget source="key_red"    render="Label" position="20,585"  size="200,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_green"  render="Label" position="230,585" size="200,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_yellow" render="Label" position="440,585" size="200,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_blue"   render="Label" position="650,585" size="200,30" font="Regular;22" halign="center" valign="center" transparent="1" />
        </screen>
    """

    def __init__(self, session, app):
        Screen.__init__(self, session)
        self.app = app
        self._watchlist = []
        self._use_multicontent = eListboxPythonMultiContent is not None

        self["title"] = StaticText(_("Stocks - Watchlist"))
        self["updated"] = Label("")
        self["header_name"] = Label(_("Name"))
        self["header_sym"] = Label(_("Symbol"))
        self["header_price"] = Label(_("Price"))
        self["header_chg"] = Label(u"\u0394 %")
        self["header_exch"] = Label(u"B\u00f6rse")

        if self._use_multicontent:
            self["list"] = MenuList([], content=eListboxPythonMultiContent)
        else:
            self["list"] = MenuList([])

        if gFont is not None:
            try:
                self["list"].l.setFont(0, gFont("Regular", 22))
                self["list"].l.setItemHeight(_ROW_H)
            except Exception:
                pass

        self["support"] = StaticText(SUPPORT_LINE)
        self["key_red"] = StaticText(_("Close"))
        self["key_green"] = StaticText(_("Refresh"))
        self["key_yellow"] = StaticText(_("Settings"))
        self["key_blue"] = StaticText(_("Information"))

        self["actions"] = ActionMap(
            ["ColorActions", "OkCancelActions", "DirectionActions", "MenuActions"],
            {
                "ok": self._open_detail,
                "cancel": self.close,
                "red": self.close,
                "green": self._key_refresh,
                "yellow": self._key_settings,
                "blue": self._key_info,
                "menu": self._key_menu,
            },
            -1,
        )

        self.onShow.append(self._reload_from_store)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _reload_from_store(self):
        self._watchlist = self.app.store.get_watchlist()
        self._render()

    def _render(self):
        items = self._watchlist
        if not items:
            if self._use_multicontent:
                self["list"].setList([self._empty_item(_("No stocks in watchlist"))])
            else:
                self["list"].setList([_("No stocks in watchlist")])
            self["updated"].setText("")
            return

        if self._use_multicontent:
            self["list"].setList([self._build_item(item) for item in items])
        else:
            self["list"].setList([self._format_plain(item) for item in items])

        count = len(items)
        with_price = sum(1 for i in items if i.get("last_price") is not None)
        self["updated"].setText(
            "%d %s  |  %d %s" % (count, _("titles"), with_price, _("with price"))
        )

    def _empty_item(self, label):
        return [
            None,
            MultiContentEntryText(
                pos=(0, 0), size=(1140, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=label, color=_COL_DIM,
            ),
        ]

    def _build_item(self, item):
        name = (item.get("name") or item.get("symbol", "?"))[:32]
        symbol = (item.get("symbol") or "")[:14]
        price = _fmt_price(item.get("last_price"), item.get("last_currency"))[:22]
        chg_text, chg_color = _fmt_pct(item.get("last_change_pct"))
        exchange = (item.get("exchange") or "")[:24]
        has_price = item.get("last_price") is not None
        name_color = _COL_TEXT if has_price else _COL_DIM

        return [
            item,
            MultiContentEntryText(
                pos=(_COL_NAME_X, 0), size=(_COL_NAME_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=name, color=name_color,
            ),
            MultiContentEntryText(
                pos=(_COL_SYM_X, 0), size=(_COL_SYM_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=symbol, color=_COL_DIM,
            ),
            MultiContentEntryText(
                pos=(_COL_PRICE_X, 0), size=(_COL_PRICE_W, _ROW_H),
                font=0, flags=RT_HALIGN_RIGHT | RT_VALIGN_CENTER,
                text=price, color=_COL_TEXT,
            ),
            MultiContentEntryText(
                pos=(_COL_CHG_X, 0), size=(_COL_CHG_W, _ROW_H),
                font=0, flags=RT_HALIGN_RIGHT | RT_VALIGN_CENTER,
                text=chg_text, color=chg_color,
            ),
            MultiContentEntryText(
                pos=(_COL_EXCH_X, 0), size=(_COL_EXCH_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=exchange, color=_COL_DIM,
            ),
        ]

    def _format_plain(self, item):
        name = (item.get("name") or item.get("symbol", "?"))[:28]
        symbol = (item.get("symbol") or "")[:12]
        price = _fmt_price(item.get("last_price"), item.get("last_currency"))[:18]
        chg_text, _ = _fmt_pct(item.get("last_change_pct"))
        return u"%-28s  %-12s  %18s  %s" % (name, symbol, price, chg_text)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _get_selected_index(self):
        if not self._watchlist:
            return None
        try:
            index = int(self["list"].getSelectionIndex())
        except Exception:
            try:
                index = int(self["list"].getSelectedIndex())
            except Exception:
                index = 0
        if index < 0 or index >= len(self._watchlist):
            return None
        return index

    # ------------------------------------------------------------------
    # Key handlers
    # ------------------------------------------------------------------

    def _open_detail(self):
        index = self._get_selected_index()
        if index is None:
            return
        item = self._watchlist[index]
        self.session.openWithCallback(
            self._on_detail_close,
            StocksDetailScreen,
            item,
            self.app,
        )

    def _on_detail_close(self, *args):
        self._reload_from_store()

    def _key_refresh(self):
        self["updated"].setText(_("Refreshing..."))
        watchlist = list(self._watchlist)
        t = threading.Thread(target=self._bg_refresh, args=(watchlist,))
        t.daemon = True
        t.start()

    def _bg_refresh(self, watchlist):
        for item in watchlist:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol", "")
            if not symbol:
                continue
            try:
                quote = self.app.api.get_quote(symbol)
                price = quote.get("price")
                if price is not None:
                    self.app.store.update_stock_data(
                        symbol, price,
                        quote.get("currency") or "",
                        quote.get("change_pct"),
                    )
            except Exception:
                pass
        self._refresh_timer = eTimer()
        _timer_connect(self._refresh_timer, self._on_refresh_done)
        self._refresh_timer.start(50, True)

    def _on_refresh_done(self):
        self._reload_from_store()

    def _key_remove(self):
        index = self._get_selected_index()
        if index is None:
            self.session.open(
                MessageBox, _("No stock selected"),
                MessageBox.TYPE_INFO, timeout=3,
            )
            return
        item = self._watchlist[index]
        name = item.get("name") or item.get("symbol", "?")
        choices = [
            (_("Remove") + ": " + name, ("remove", index)),
            (_("Cancel"), ("cancel", None)),
        ]
        self.session.openWithCallback(
            self._on_remove_choice,
            ChoiceBox,
            title=_("Remove from watchlist?"),
            list=choices,
        )

    def _on_remove_choice(self, choice):
        if not choice:
            return
        if not isinstance(choice, (list, tuple)) or len(choice) < 2:
            return
        action_data = choice[1]
        if not isinstance(action_data, tuple):
            return
        action, index = action_data
        if action == "remove" and index is not None:
            if self.app.store.remove_from_watchlist(index):
                self._reload_from_store()

    def _key_settings(self):
        self.session.openWithCallback(
            lambda *_args: self._reload_from_store(),
            StocksSettingsScreen,
            self.app,
        )

    def _key_search(self):
        self.session.openWithCallback(
            lambda *_args: self._reload_from_store(),
            StocksSearchScreen,
            self.app,
        )

    def _key_info(self):
        self.session.open(StocksInfoScreen)

    def _key_menu(self):
        options = [
            (_("Search"), "search"),
            (_("Remove"), "remove"),
            (_("Refresh"), "refresh"),
            (_("Settings"), "settings"),
            (_("Information"), "info"),
            (_("Close"), "close"),
        ]
        self.session.openWithCallback(
            self._on_menu_choice,
            ChoiceBox,
            title=_("Main menu"),
            list=options,
        )

    def _on_menu_choice(self, choice=None):
        if not choice:
            return
        action = choice[1]
        if action == "refresh":
            self._key_refresh()
        elif action == "search":
            self._key_search()
        elif action == "remove":
            self._key_remove()
        elif action == "settings":
            self._key_settings()
        elif action == "info":
            self._key_info()
        elif action == "close":
            self.close()


# ===========================================================================
# Detail screen – shows full info for one stock
# ===========================================================================

class StocksDetailScreen(Screen):

    skin = """
        <screen name="StocksDetailScreen" position="center,80" size="1000,580" title="Stocks - Detail">
            <widget source="title"    render="Label" position="20,10"  size="960,44" font="Regular;34" />
            <widget source="subtitle" render="Label" position="20,60"  size="960,30" font="Regular;24" foregroundColor="#888888" />
            <widget name="body"       position="20,100" size="960,390" font="Regular;26" scrollbarMode="showOnDemand" />
            <widget source="support"  render="Label" position="20,500" size="960,24" font="Regular;18" foregroundColor="#666666" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png"    position="20,530"  size="220,34" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"  position="250,530" size="220,34" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/blue.png"   position="710,530" size="220,34" alphatest="on" />
            <widget source="key_red"    render="Label" position="20,530"  size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_green"  render="Label" position="250,530" size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_blue"   render="Label" position="710,530" size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
        </screen>
    """

    def __init__(self, session, item, app):
        Screen.__init__(self, session)
        self._item = dict(item) if item else {}
        self.app = app

        name = self._item.get("name") or self._item.get("symbol", "?")
        symbol = self._item.get("symbol", "")

        self["title"] = StaticText(name)
        self["subtitle"] = StaticText(symbol)
        self["body"] = ScrollLabel(self._build_text())
        self["support"] = StaticText(SUPPORT_LINE)
        self["key_red"] = StaticText(_("Close"))
        self["key_green"] = StaticText(_("Refresh"))
        self["key_blue"] = StaticText(_("Remove"))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "DirectionActions"],
            {
                "ok": self._scroll_down,
                "cancel": self.close,
                "red": self.close,
                "green": self._action_refresh,
                "blue": self._action_remove,
                "up": self._scroll_up,
                "down": self._scroll_down,
            },
            -1,
        )

    def _scroll_up(self):
        self["body"].pageUp()

    def _scroll_down(self):
        self["body"].pageDown()

    def _build_text(self):
        d = self._item
        na = _("n/a")

        price = d.get("last_price")
        currency = d.get("last_currency") or ""
        chg = d.get("last_change_pct")
        chg_text, _ = _fmt_pct(chg)

        lines = [
            u"\u250c\u2500 %s \u2500" % _("Security"),
            u"\u2502  %s:  %s" % (_("Name"), d.get("name") or na),
            u"\u2502  %s:  %s" % ("Symbol", d.get("symbol") or na),
            u"\u2502  %s:  %s" % (_("Type"), d.get("type") or na),
            u"\u2502  %s:  %s" % (u"B\u00f6rse", d.get("exchange") or na),
        ]
        if d.get("isin"):
            lines.append(u"\u2502  ISIN:  %s" % d["isin"])
        if d.get("wkn"):
            lines.append(u"\u2502  WKN:   %s" % d["wkn"])
        lines.append(u"\u2514\u2500\u2500\u2500")
        lines.append("")

        lines.append(u"\u250c\u2500 %s \u2500" % _("Quote data"))
        if price is not None:
            lines.append(u"\u2502  %s:  %s" % (_("Price"), _fmt_price(price, currency)))
            lines.append(u"\u2502  %s:  %s" % (u"\u0394 Tag", chg_text))
        else:
            lines.append(u"\u2502  %s" % _("No quote data loaded yet"))
        if d.get("last_alert_price") is not None:
            lines.append(u"\u2502  %s:  %s" % (
                _("Alert baseline"),
                _fmt_price(d["last_alert_price"], currency),
            ))
        lines.append(u"\u2514\u2500\u2500\u2500")

        # Extended data (fetched on refresh)
        summary = d.get("_summary") or {}
        if summary:
            lines.append("")
            lines.append(u"\u250c\u2500 %s \u2500" % _("Details"))
            asset_profile = summary.get("assetProfile") or {}
            price_data = summary.get("price") or {}
            if asset_profile.get("sector"):
                lines.append(u"\u2502  %s:  %s" % (_("Sector"), asset_profile["sector"]))
            if asset_profile.get("industry"):
                lines.append(u"\u2502  %s:  %s" % (_("Industry"), asset_profile["industry"]))
            if asset_profile.get("website"):
                lines.append(u"\u2502  %s:  %s" % ("Website", asset_profile["website"]))
            market_cap = price_data.get("marketCap") or {}
            mc_raw = market_cap.get("raw")
            if mc_raw:
                lines.append(u"\u2502  %s:  %s" % (
                    _("Market cap"),
                    _fmt_market_cap(mc_raw, currency),
                ))
            lines.append(u"\u2514\u2500\u2500\u2500")

        return "\n".join(lines)

    def _action_refresh(self):
        self["body"].setText(_("Loading data..."))
        t = threading.Thread(target=self._bg_refresh)
        t.daemon = True
        t.start()

    def _bg_refresh(self):
        symbol = self._item.get("symbol", "")
        if symbol:
            try:
                quote = self.app.api.get_quote(symbol)
                price = quote.get("price")
                if price is not None:
                    self._item["last_price"] = price
                    self._item["last_currency"] = quote.get("currency") or ""
                    self._item["last_change_pct"] = quote.get("change_pct")
                    self.app.store.update_stock_data(
                        symbol, price,
                        quote.get("currency") or "",
                        quote.get("change_pct"),
                    )
            except Exception:
                pass
            try:
                summary = self.app.api.get_quote_summary(symbol)
                if summary:
                    self._item["_summary"] = summary
            except Exception:
                pass
        self._detail_timer = eTimer()
        _timer_connect(self._detail_timer, self._on_detail_refreshed)
        self._detail_timer.start(50, True)

    def _on_detail_refreshed(self):
        self["body"].setText(self._build_text())

    def _action_remove(self):
        name = self._item.get("name") or self._item.get("symbol", "?")
        choices = [
            (_("Remove") + ": " + name, "remove"),
            (_("Cancel"), "cancel"),
        ]
        self.session.openWithCallback(
            self._on_remove_choice,
            ChoiceBox,
            title=_("Remove from watchlist?"),
            list=choices,
        )

    def _on_remove_choice(self, choice):
        if not choice:
            return
        action = choice[1]
        if action != "remove":
            return
        symbol = self._item.get("symbol", "").upper()
        watchlist = self.app.store.get_watchlist()
        for idx, item in enumerate(watchlist):
            if isinstance(item, dict) and item.get("symbol", "").upper() == symbol:
                self.app.store.remove_from_watchlist(idx)
                self.close()
                return


# ===========================================================================
# Search screen
# ===========================================================================

class StocksSearchScreen(Screen):

    skin = """
        <screen name="StocksSearchScreen" position="center,90" size="1180,640" title="Stocks - Suche">
            <widget source="title"       render="Label" position="20,10"  size="1140,36" font="Regular;30" />
            <widget name="hint"          position="20,52"  size="1140,28" font="Regular;22" />
            <widget name="header_name"   position="20,84"  size="400,28" font="Regular;20" />
            <widget name="header_sym"    position="424,84" size="160,28" font="Regular;20" />
            <widget name="header_exch"   position="588,84" size="280,28" font="Regular;20" />
            <widget name="header_type"   position="872,84" size="288,28" font="Regular;20" />
            <widget name="list" position="20,116" size="1140,436" scrollbarMode="showOnDemand" />
            <widget source="support" render="Label" position="20,558" size="1140,24" font="Regular;18" foregroundColor="#666666" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png"    position="20,585"  size="200,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"  position="230,585" size="200,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/blue.png"   position="650,585" size="200,30" alphatest="on" />
            <widget source="key_red"    render="Label" position="20,585"  size="200,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_green"  render="Label" position="230,585" size="200,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_blue"   render="Label" position="650,585" size="200,30" font="Regular;22" halign="center" valign="center" transparent="1" />
        </screen>
    """

    # Search result column layout
    _SR_NAME_X = 0
    _SR_NAME_W = 400
    _SR_SYM_X = 404
    _SR_SYM_W = 160
    _SR_EXCH_X = 568
    _SR_EXCH_W = 280
    _SR_TYPE_X = 852
    _SR_TYPE_W = 288

    def __init__(self, session, app):
        Screen.__init__(self, session)
        self.app = app
        self._results = []
        self._query = ""
        self._use_multicontent = eListboxPythonMultiContent is not None

        self["title"] = StaticText(_("Stock search"))
        self["hint"] = Label(_("BLUE = Start search"))
        self["header_name"] = Label(_("Name"))
        self["header_sym"] = Label(_("Symbol"))
        self["header_exch"] = Label(u"B\u00f6rse")
        self["header_type"] = Label(_("Type"))

        if self._use_multicontent:
            self["list"] = MenuList([], content=eListboxPythonMultiContent)
        else:
            self["list"] = MenuList([])

        if gFont is not None:
            try:
                self["list"].l.setFont(0, gFont("Regular", 22))
                self["list"].l.setItemHeight(_ROW_H)
            except Exception:
                pass

        self["support"] = StaticText(SUPPORT_LINE)
        self["key_red"] = StaticText(_("Close"))
        self["key_green"] = StaticText(_("Add"))
        self["key_blue"] = StaticText(_("Search"))

        self["actions"] = ActionMap(
            ["ColorActions", "OkCancelActions"],
            {
                "ok": self._add_selected,
                "cancel": self.close,
                "red": self.close,
                "green": self._add_selected,
                "blue": self._open_keyboard,
            },
            -1,
        )

        self._kb_timer = eTimer()
        _timer_connect(self._kb_timer, self._open_keyboard)
        self.onLayoutFinish.append(self._schedule_keyboard)

    def _schedule_keyboard(self):
        self._kb_timer.start(150, True)

    def _open_keyboard(self):
        if _HAS_VKB:
            self.session.openWithCallback(
                self._on_keyboard_done,
                VirtualKeyBoard,
                title=_("Enter name, ISIN or WKN"),
                text=self._query,
            )
        else:
            self.session.open(
                MessageBox,
                "VirtualKeyBoard not available",
                MessageBox.TYPE_INFO,
                timeout=4,
            )

    def _on_keyboard_done(self, query):
        if query is None:
            return
        self._query = query.strip()
        if not self._query:
            return
        self["hint"].setText(_("Searching..."))
        t = threading.Thread(target=self._bg_search, args=(self._query,))
        t.daemon = True
        t.start()

    def _bg_search(self, query):
        try:
            results = self.app.api.search(query)
        except Exception:
            results = []
        self._pending_results = results
        self._result_timer = eTimer()
        _timer_connect(self._result_timer, self._on_results_ready)
        self._result_timer.start(50, True)

    def _on_results_ready(self):
        results = getattr(self, "_pending_results", [])
        self._show_results(results)

    def _show_results(self, results):
        self["hint"].setText(
            "%d %s" % (len(results), _("results")) if results
            else _("BLUE = Start search")
        )
        self._results = results or []
        if not results:
            if self._use_multicontent:
                self["list"].setList([self._empty_item(_("No results"))])
            else:
                self["list"].setList([_("No results")])
            self.session.open(
                MessageBox, _("No results"), MessageBox.TYPE_INFO, timeout=3
            )
            return

        if self._use_multicontent:
            self["list"].setList([self._build_result_item(r) for r in results])
        else:
            self["list"].setList([self._format_result_plain(r) for r in results])

    def _empty_item(self, label):
        return [
            None,
            MultiContentEntryText(
                pos=(0, 0), size=(1140, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=label, color=_COL_DIM,
            ),
        ]

    def _build_result_item(self, r):
        name = (r.get("name") or "")[:38]
        symbol = (r.get("symbol") or "")[:16]
        exchange = (r.get("exchange") or "")[:26]
        type_ = (r.get("type") or "")[:24]

        return [
            r,
            MultiContentEntryText(
                pos=(self._SR_NAME_X, 0), size=(self._SR_NAME_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=name, color=_COL_TEXT,
            ),
            MultiContentEntryText(
                pos=(self._SR_SYM_X, 0), size=(self._SR_SYM_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=symbol, color=_COL_DIM,
            ),
            MultiContentEntryText(
                pos=(self._SR_EXCH_X, 0), size=(self._SR_EXCH_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=exchange, color=_COL_DIM,
            ),
            MultiContentEntryText(
                pos=(self._SR_TYPE_X, 0), size=(self._SR_TYPE_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=type_, color=_COL_WARM,
            ),
        ]

    def _format_result_plain(self, r):
        name = (r.get("name") or "")[:30]
        symbol = (r.get("symbol") or "")[:14]
        exchange = (r.get("exchange") or "")[:20]
        type_ = (r.get("type") or "")[:12]
        return u"%-30s  %-14s  %-20s  %s" % (name, symbol, exchange, type_)

    def _get_selected_result(self):
        if not self._results:
            return None
        try:
            index = int(self["list"].getSelectionIndex())
        except Exception:
            try:
                index = int(self["list"].getSelectedIndex())
            except Exception:
                index = 0
        if index < 0 or index >= len(self._results):
            return None
        return self._results[index]

    def _add_selected(self):
        stock = self._get_selected_result()
        if not isinstance(stock, dict):
            self.session.open(
                MessageBox, _("No stock selected"),
                MessageBox.TYPE_INFO, timeout=3,
            )
            return
        added = self.app.store.add_to_watchlist(stock)
        msg = _("Added to watchlist") if added else _("Already in watchlist")
        self.session.open(MessageBox, msg, MessageBox.TYPE_INFO, timeout=3)


# ===========================================================================
# Settings screen
# ===========================================================================

class StocksSettingsScreen(Screen):

    skin = """
        <screen name="StocksSettingsScreen" position="center,100" size="980,560" title="Stocks - Einstellungen">
            <widget source="title"  render="Label" position="20,10"  size="940,36" font="Regular;30" />
            <widget name="list"     position="20,56"  size="940,360" scrollbarMode="showOnDemand" />
            <widget name="hint"     position="20,426" size="940,30"  font="Regular;22" />
            <widget source="support" render="Label" position="20,464" size="940,24" font="Regular;18" foregroundColor="#666666" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png"    position="20,500"  size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"  position="250,500" size="220,30" alphatest="on" />
            <widget source="key_red"    render="Label" position="20,500"  size="220,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_green"  render="Label" position="250,500" size="220,30" font="Regular;22" halign="center" valign="center" transparent="1" />
        </screen>
    """

    CURRENCY_OPTIONS  = ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD",
                          "SEK", "NOK", "DKK", "CNY", "HKD"]
    THRESHOLD_OPTIONS = [0.5, 1.0, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0]
    TARGET_OPTIONS    = [
        ("ui",   "Nur UI"),
        ("lcd",  "Nur LCD"),
        ("both", "UI + LCD"),
    ]
    POLL_OPTIONS      = [60, 120, 300, 600, 1800, 3600]
    TIMEOUT_OPTIONS   = [4, 6, 8, 10, 15]

    def __init__(self, session, app):
        Screen.__init__(self, session)
        self.app = app
        self.settings = self.app.store.get_settings()
        self._rows = []

        self["title"] = StaticText(_("Settings"))
        self["list"] = MenuList([])
        self["hint"] = Label(_("Left/Right changes value"))
        self["support"] = StaticText(SUPPORT_LINE)
        self["key_red"] = StaticText(_("Cancel"))
        self["key_green"] = StaticText(_("Save"))

        self["actions"] = ActionMap(
            ["ColorActions", "OkCancelActions", "DirectionActions"],
            {
                "ok": self._key_ok,
                "cancel": self.close,
                "red": self.close,
                "green": self._key_save,
                "left": self._key_left,
                "right": self._key_right,
            },
            -1,
        )

        self._render()

    def _target_label(self):
        val = self.settings.get("output_target", "both")
        for key, label in self.TARGET_OPTIONS:
            if key == val:
                return label
        return val

    def _render(self):
        self._rows = [
            (_("Currency") + ":  " + str(self.settings.get("currency", "EUR")), "currency"),
            (_("Alert threshold") + ":  " + str(self.settings.get("alert_threshold_pct", 5.0)) + " %", "alert_threshold_pct"),
            (_("Output target") + ":  " + self._target_label(), "output_target"),
            (_("Polling interval") + ":  " + str(self.settings.get("polling_interval_sec", 300)) + " s", "polling_interval_sec"),
            (_("Display duration") + ":  " + str(self.settings.get("message_timeout_sec", 8)) + " s", "message_timeout_sec"),
            (_("Information"), "info"),
        ]
        self["list"].setList([r[0] for r in self._rows])

    def _current_key(self):
        try:
            index = int(self["list"].getSelectionIndex())
        except Exception:
            return None
        if index < 0 or index >= len(self._rows):
            return None
        return self._rows[index][1]

    def _options_for(self, key):
        if key == "currency":
            return self.CURRENCY_OPTIONS
        if key == "alert_threshold_pct":
            return self.THRESHOLD_OPTIONS
        if key == "output_target":
            return [k for k, _lbl in self.TARGET_OPTIONS]
        if key == "polling_interval_sec":
            return self.POLL_OPTIONS
        return self.TIMEOUT_OPTIONS

    def _rotate(self, key, direction):
        options = self._options_for(key)
        current = self.settings.get(key)
        try:
            idx = options.index(current)
        except (ValueError, TypeError):
            idx = 0
        idx = (idx + direction) % len(options)
        self.settings[key] = options[idx]

    def _key_left(self):
        key = self._current_key()
        if key and key != "info":
            self._rotate(key, -1)
            self._render()

    def _key_right(self):
        key = self._current_key()
        if key and key != "info":
            self._rotate(key, 1)
            self._render()

    def _key_ok(self):
        key = self._current_key()
        if key == "info":
            self.session.open(StocksInfoScreen)

    def _key_save(self):
        self.app.store.save_settings(self.settings)
        self.app.poller.start()
        self.session.open(
            MessageBox, _("Settings saved"),
            MessageBox.TYPE_INFO, timeout=3,
        )
        self.close()


# ===========================================================================
# Info / About screen
# ===========================================================================

class StocksInfoScreen(Screen):
    skin = """
        <screen name="StocksInfoScreen" position="center,90" size="1000,620" title="Stocks Info">
            <widget source="title" render="Label" position="20,10" size="960,35" font="Regular;30" />
            <widget name="body" position="20,55" size="690,500" font="Regular;24" scrollbarMode="showOnDemand" />
            <widget name="qr" position="740,100" size="240,240" alphatest="blend" />
            <widget source="support" render="Label" position="20,560" size="960,24" font="Regular;20" foregroundColor="#666666" />
            <ePixmap pixmap="skin_default/buttons/red.png" position="20,585" size="220,30" alphatest="on" />
            <widget source="key_red" render="Label" position="20,585" size="220,30" font="Regular;22" halign="center" valign="center" transparent="1" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self["title"] = StaticText(_("Information"))
        self["key_red"] = StaticText(_("Close"))
        self["support"] = StaticText(SUPPORT_LINE)
        self["body"] = ScrollLabel(self._build_info_text())
        self["qr"] = Pixmap()
        self.onLayoutFinish.append(self._load_qr_png)

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions", "ColorActions"],
            {
                "cancel": self.close,
                "ok": self.close,
                "red": self.close,
                "up": self._scroll_up,
                "down": self._scroll_down,
                "left": self._scroll_up,
                "right": self._scroll_down,
            },
            -1,
        )

    def _scroll_up(self):
        self["body"].pageUp()

    def _scroll_down(self):
        self["body"].pageDown()

    def _build_info_text(self):
        lines = [
            "Stocks Plugin v1.1",
            "",
            _("Data source") + ": Yahoo Finance",
            _("No API key required."),
            "",
            _("Controls") + ":",
            u"  OK          \u2192 Detail-Ansicht",
            u"  Gr\u00fcn        \u2192 Kurse aktualisieren",
            u"  Rot         \u2192 Aktie entfernen",
            u"  Gelb        \u2192 Einstellungen",
            u"  Blau        \u2192 Aktie suchen",
            u"  Men\u00fc       \u2192 Hauptmen\u00fc",
            "",
            _("Search") + ":",
            u"  \u2022 Nach Name (z.B. SAP, Adesso)",
            u"  \u2022 Nach ISIN (z.B. DE0007164600)",
            u"  \u2022 Nach WKN (z.B. 716460)",
            "",
            _("Deployment via .env") + ":",
            u"  STOCKS_WATCHLIST=SAP.DE,ADS.DE",
            u"  STOCKS_WATCHLIST=DE0007164600",
            "",
            "Buy me a coffee: https://buymeacoffee.com/madoe21",
            "GitHub: https://github.com/madoe21/enigma2-stocks",
        ]
        return "\n".join(lines)

    def _load_qr_png(self):
        candidate_paths = [
            resolveFilename(SCOPE_PLUGINS, "Extensions/Stocks/res/qr_buymeacoffee.png"),
            os.path.join(os.path.dirname(__file__), "res", "qr_buymeacoffee.png"),
        ]
        for path in candidate_paths:
            if os.path.exists(path):
                try:
                    self["qr"].instance.setPixmapFromFile(path)
                    return
                except Exception:
                    pass


# ===========================================================================
# Helpers
# ===========================================================================

def _fmt_market_cap(raw, currency):
    """Format market cap to human-readable (e.g. 1.23 Mrd EUR)."""
    try:
        v = float(raw)
        cur = " %s" % currency if currency else ""
        if v >= 1e12:
            return "%.2f Bio%s" % (v / 1e12, cur)
        if v >= 1e9:
            return "%.2f Mrd%s" % (v / 1e9, cur)
        if v >= 1e6:
            return "%.2f Mio%s" % (v / 1e6, cur)
        return "%.0f%s" % (v, cur)
    except Exception:
        return str(raw)
