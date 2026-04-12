# -*- coding: utf-8 -*-
"""Enigma2-specific services: timer-driven polling, LCD + UI alerts.

Imports the platform-neutral core and wires it to Enigma2's eTimer,
eDBoxLCD / evfd, and the Notifications API.
"""
from __future__ import absolute_import

import threading

from enigma import eTimer

try:
    from enigma import evfd
except Exception:
    evfd = None

try:
    from enigma import eDBoxLCD
except Exception:
    eDBoxLCD = None

from Screens.MessageBox import MessageBox
from Tools import Notifications

from .core.polling import StocksPollingEngine


def _timer_connect(timer, callback):
    try:
        timer.timeout.connect(callback)
    except Exception:
        timer.callback.append(callback)


# ---------------------------------------------------------------------------
# Alert output services
# ---------------------------------------------------------------------------

class UiAlertService(object):
    """Show alert pop-ups via Enigma2 Notifications."""

    def __init__(self, session):
        self.session = session

    def show(self, text, timeout_sec):
        Notifications.AddPopup(text, MessageBox.TYPE_INFO, timeout=int(timeout_sec))


class LcdAlertService(object):
    """Write alert text to the front-panel LCD / VFD."""

    def __init__(self):
        self._restore_timer = eTimer()
        _timer_connect(self._restore_timer, self._restore)

    def _write(self, text):
        if evfd is not None:
            try:
                evfd.getInstance().vfd_write_string(text)
                return
            except Exception:
                pass
        if eDBoxLCD is not None:
            try:
                eDBoxLCD.getInstance().setText(text)
            except Exception:
                pass

    def show(self, text, timeout_sec):
        short = text.replace("\n", " | ")
        self._write(short[:64])
        self._restore_timer.start(int(timeout_sec) * 1000, True)

    def _restore(self):
        self._write("")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class AlertDispatcher(object):
    """Route alert messages to one or both output services."""

    def __init__(self, ui_service, lcd_service, store):
        self.ui_service  = ui_service
        self.lcd_service = lcd_service
        self.store       = store

    def dispatch(self, text):
        settings = self.store.get_settings()
        target   = settings.get("output_target", "both")
        timeout  = int(settings.get("message_timeout_sec", 8))
        if target in ("ui", "both"):
            self.ui_service.show(text, timeout)
        if target in ("lcd", "both"):
            self.lcd_service.show(text, timeout)


# ---------------------------------------------------------------------------
# Polling service
# ---------------------------------------------------------------------------

class StocksPollingService(object):
    """Drives :class:`~core.polling.StocksPollingEngine` at a configurable
    interval using Enigma2's ``eTimer``.

    HTTP fetching is done in a daemon thread to avoid blocking the UI.
    Alert messages are written to a queue and drained on the main thread
    via a secondary short-interval timer.
    """

    def __init__(self, api, store, dispatcher):
        self.store      = store
        self.dispatcher = dispatcher
        self.engine     = StocksPollingEngine(api)

        self._lock           = threading.Lock()
        self._pending_alerts = []
        self._running        = False

        self._poll_timer = eTimer()
        _timer_connect(self._poll_timer, self._on_poll_due)

        self._drain_timer = eTimer()
        _timer_connect(self._drain_timer, self._drain_alerts)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def start(self):
        """(Re-)start the polling cycle."""
        self._running = True
        self._schedule_next(delay_ms=2000)

    def stop(self):
        self._running = False
        for t in (self._poll_timer, self._drain_timer):
            try:
                t.stop()
            except Exception:
                pass

    def trigger_now(self):
        """Kick off an immediate out-of-band fetch."""
        self._launch_fetch()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _schedule_next(self, delay_ms=None):
        if not self._running:
            return
        if delay_ms is None:
            settings = self.store.get_settings()
            interval = int(settings.get("polling_interval_sec", 300))
            delay_ms = interval * 1000
        self._poll_timer.start(delay_ms, True)

    def _on_poll_due(self):
        self._launch_fetch()
        self._schedule_next()

    def _launch_fetch(self):
        t = threading.Thread(target=self._fetch_worker)
        t.daemon = True
        t.start()

    def _fetch_worker(self):
        try:
            alerts = self.engine.run(self.store)
        except Exception:
            alerts = []
        if alerts:
            with self._lock:
                self._pending_alerts.extend(alerts)
            try:
                self._drain_timer.start(200, True)
            except Exception:
                pass

    def _drain_alerts(self):
        with self._lock:
            alerts               = list(self._pending_alerts)
            self._pending_alerts = []
        for text in alerts:
            try:
                self.dispatcher.dispatch(text)
            except Exception:
                pass
