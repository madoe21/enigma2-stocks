# Codebase map (onboarding 2026-07-08)

**enigma2-stocks** — Enigma2 (OpenATV 7.6) plugin: stock/index quotes and
watchlist on the TV. Python. ~2000 LOC.

## Layout
- `src/Stocks/plugin.py` — entry.
- `src/Stocks/core/api.py` (~230 LOC) — quote provider client.
- `src/Stocks/core/store.py` (~228) — watchlist/state persistence. **`core/`
  is the platform-agnostic data + storage layer.**
- `src/Stocks/screens.py` (~1059) — enigma2 GUI (largest file).
- `res/`, `control/`, `build/` (gitignored ipk).

## Conventions
- Enigma2 Py3; timeouts on quote fetches (main reactor thread).

## Kodi portability: **already split**
`core/` (api + store) separated from `screens.py`/`plugin.py`. Verify `core/`
has no enigma2 imports (store may reach into enigma2 config/paths — if so,
inject a path/config adapter). A Kodi port then only needs `platform/kodi/`.
One of the three reference-shaped plugins (with lotto, weather).
