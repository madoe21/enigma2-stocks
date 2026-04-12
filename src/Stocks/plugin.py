# -*- coding: utf-8 -*-
from __future__ import absolute_import

from Plugins.Plugin import PluginDescriptor

from . import _
from .core.api import YahooFinanceClient
from .core.store import StocksStore
from .screens import StocksMainScreen
from .services import AlertDispatcher, LcdAlertService, StocksPollingService, UiAlertService

_APP = None


class AppContext(object):
    def __init__(self, session):
        self.session = session
        self.store = StocksStore()
        self.store.load_watchlist_from_enigma2()
        self.api = YahooFinanceClient()
        self.ui_service = UiAlertService(session)
        self.lcd_service = LcdAlertService()
        self.dispatcher = AlertDispatcher(self.ui_service, self.lcd_service, self.store)
        self.poller = StocksPollingService(self.api, self.store, self.dispatcher)

    def start(self):
        self.poller.start()

    def stop(self):
        self.poller.stop()


def _get_app(session):
    global _APP
    if _APP is None:
        _APP = AppContext(session)
        _APP.start()
    else:
        _APP.session = session
        _APP.ui_service.session = session
    return _APP


def autostart(reason, **kwargs):
    global _APP
    if reason == 0:
        session = kwargs.get("session")
        if session:
            _get_app(session)
    elif reason == 1 and _APP is not None:
        _APP.stop()
        _APP = None


def main(session, **kwargs):
    app = _get_app(session)
    session.open(StocksMainScreen, app)


def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name="Stocks",
            description=_("Stock market watchlist and price alerts"),
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="plugin.png",
            fnc=main,
        ),
        PluginDescriptor(
            where=PluginDescriptor.WHERE_AUTOSTART,
            fnc=autostart,
        ),
    ]
