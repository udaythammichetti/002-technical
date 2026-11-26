# Signal Desk

Local scan desk for NSE and BSE cash equities. A Python API pulls prices and history, scores them, and serves a React UI on one local port.

This is a research tool. It is not a forecast and not investment advice.

## Desks

| Desk | What it shows |
| --- | --- |
| **Volume** | Price move confirmed by relative volume, CMF, MFI, OBV, A/D, and VPT |
| **Technical** | RSI, MACD, SMA 20/50, EMA 20, plus optional oscillators |
| **Lab** | Donchian breakouts, coils, and accumulation bases |
| **Chart** | Support/resistance, trend, gaps, patterns, Fibonacci, and candles |
| **Candles** | Last 3, 5, and 7 daily, weekly, and monthly candles as bull, bear, or neutral |

### Tabs (naming)

| Desk | Tabs |
| --- | --- |
| Volume | Map · Bullish · Bearish · Spike |
| Technical | Map · Bullish · Bearish |
| Lab | Map · Bullish · Coil · Breakout |
| Chart | Map · Bullish · Bearish · Breakout · S/R · Fib |
| Candles | Map · Bullish · Bearish · Aligned |

Convention: Title Case labels; overview is **Map**; bias tabs are full **Bullish** / **Bearish**; Lab uses **Coil** (not Consolidating).

**Book** (toolbar) picks the scan universe. Groups:

| Group | Books |
| --- | --- |
| Nifty | Nifty 50 · Next 50 · 100 · 200 · 500 |
| Cap | Midcap 50/150 · Smallcap 50/250 · Microcap 250 · LargeMidcap 250 |
| BSE | Group A · Group B |
| Exchange | NSE All · BSE All |

Volume, Technical, and Lab timeframes: **15m · 1H · 4H · 1D · 1W · 1M · 3M · 6M · 1Y · 5Y · Max**. Chart uses daily depth **6M–10Y**, swing **2Y·W / 5Y·W**, and long **5Y·M / 10Y·W**.

**Common Search** opens a combined dossier (Volume · Technical · Lab · Chart) with **Day** (1-day window) and **Long** (5-year daily). The **NSE · BSE volume** table shows the last 15 sessions (Total, Avg50, Δ Tot/NSE/BSE, RVOL, Mix, Spike, Delivery).

Each desk keeps its own board cache until you hit **Refresh** or **Clear all**.

## Data sources

- Price / OHLCV: Moneycontrol (Yahoo fallback)
- Books: official NSE constituent CSVs + BSE scrip list (`universe_dim.py`), refresh every Monday 07:00 IST while the server runs

## Run

Requires Python 3.11+ and Node.js (only needed the first time, to build the UI).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

./launch.sh
```

`launch.sh` builds `web/dist` if it is missing, then starts the server. Open the URL it prints (default [http://127.0.0.1:8797](http://127.0.0.1:8797)). If 8797 is taken it tries the next port up to 8806. Stop with Ctrl+C.

`curl_cffi` is the only Python dependency (Yahoo TLS fingerprint).

Manual single-port start:

```bash
source .venv/bin/activate
cd web && npm install && npm run build && cd ..
python -u server.py
```

## Develop the UI

Two terminals:

```bash
source .venv/bin/activate
python3 -u server.py
```

```bash
cd web
npm install
npm run dev
```

UI: [http://127.0.0.1:5173](http://127.0.0.1:5173) (proxies `/api` → `:8797`). After UI changes for the single-port server, run `npm run build` inside `web/`.

Refresh the symbol universe on demand:

```bash
source .venv/bin/activate
python3 universe_dim.py --refresh
```

## Layout

```
server.py                 # HTTP API + desk scan logic
universe_dim.py           # NSE/BSE book builder (Monday refresh)
launch.sh                 # venv + build web/dist + start server
requirements.txt
data/
  universe_dim.json       # cached books
web/                      # React + Vite UI (source)
  src/components/         # desks, Book toolbar, CombinedDossier, …
static/                   # legacy fallback UI
```

## API (local)

| Endpoint | Purpose |
| --- | --- |
| `GET /api/sources` | Feed status + Book list |
| `GET /api/board` | Volume board |
| `GET /api/tech-board` | Technical board |
| `GET /api/sci-board` | Lab board |
| `GET /api/chart-board` | Chart board |
| `GET /api/candle-board` | Candles board |
| `GET /api/volume` | Single-symbol volume study |
| `GET /api/symbol-dossier` | Combined search dossier (incl. NSE/BSE volume KPIs) |
| `GET /api/search?q=` | Symbol search |
| `GET /api/cache/clear` | Clear runtime caches |
| `GET /api/universe` · `/api/universe/refresh` | Book status / force rebuild |

Add `&fresh=1` on board/dossier calls to bypass cache.

## Notes

- Needs network access for Moneycontrol, Yahoo, NSE, and BSE.
- For personal research only.
