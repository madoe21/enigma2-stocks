# enigma2-stocks

Stock market watchlist and price alert plugin for Enigma2.  
Data is fetched from the Yahoo Finance API (no API key required).

---

## Features

| Button | Action |
|--------|--------|
| **Blue** | Open search – type a stock name, ISIN or WKN |
| **Red** | Remove the selected stock from the watchlist |
| **Green** | Refresh all prices in the background |
| **Yellow** | Open settings |
| **OK** | Refresh the price for the currently selected stock |

### Price alerts
When a watched stock's price moves by the configured **Alert threshold** percentage
the alert is shown as a pop-up in the UI and/or written to the front-panel LCD
(configurable in Settings).

---

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Currency | EUR | Display preference (does not convert prices) |
| Alert threshold | 5.0 % | Percentage change that triggers an alert |
| Output target | UI + LCD | Where to show alerts |
| Polling interval | 300 s | How often prices are fetched in the background |
| Message timeout | 8 s | How long UI pop-ups stay visible |

---

## Build & deploy

```bash
# 1. Copy .env.example to .env and enter your box credentials
cp .env.example .env

# 2. Build the .ipk package
make ipk

# 3. Build, upload and install on the box (no restart, no settings)
make install

# 4. Copy watchlist from .env to box settings
make copy-settings

# 5. Restart Enigma2
make apply

# 6. Or do all three steps at once
make deploy
```

The package is placed in `build/enigma2-plugin-extensions-stocks_1.0.0_all.ipk`.

---

## .env variables

| Variable | Description |
|----------|-------------|
| `BOX_HOST` | Enigma2 box IP or hostname |
| `BOX_USER` | SSH user (usually `root`) |
| `BOX_PORT` | SSH port (default `22`) |
| `STOCKS_WATCHLIST` | Comma-separated list of stocks to watch. Accepts Yahoo symbols (`SAP.DE`), ISINs (`DE0007164600`) or WKNs (`A3GNFN`). Resolved to Yahoo symbols at deploy time. |

Example:

```env
STOCKS_WATCHLIST=A3GNFN,A0RPWH,A2N6LC,A1JULM
```

---

## Data

Prices are sourced from Yahoo Finance (unofficial API, no key required).  
Data may be subject to a 15-minute delay depending on the exchange.

`ca-certificates` must be installed on the box for HTTPS to work
(listed as a dependency in the `.ipk` control file).

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Found a bug or have a suggestion for improvement? Please create an issue or pull request.

I appreciate everyone who supports me and the project! For any requests and suggestions, feel free to provide feedback.

<p>
  <a href="https://www.buymeacoffee.com/madoe21">
    <img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" height="50" alt="Buy Me a Coffee">
  </a>

  <a href="https://ko-fi.com/madoe21">
    <img src="https://storage.ko-fi.com/cdn/kofi3.png?v=3" height="50" alt="Ko-fi">
  </a>

  <a href="https://paypal.me/MartinD809">
    <img src="https://www.paypalobjects.com/webstatic/mktg/logo/pp_cc_mark_111x69.jpg" height="50" alt="PayPal">
  </a>
</p>

---

## Built with aiflow

This project was built with support from **[aiflow](https://cyber93de.github.io/aiflow/)** — *built with aiflow*.
