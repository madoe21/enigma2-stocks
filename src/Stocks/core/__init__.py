# -*- coding: utf-8 -*-
"""
Stocks core package – pure Python, no Enigma2 or Kodi dependencies.

Provides:
    api       – YahooFinanceClient
    store     – StocksStore  (JSON-backed watchlist + settings)
    polling   – StocksPollingEngine (alert detection)
    formatter – human-readable price / alert strings
"""
from __future__ import absolute_import
