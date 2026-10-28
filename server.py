#!/usr/bin/env python3
"""Signal Desk — API + static file server for the React UI.

Dev (hot reload):
  python3 -u server.py          # API on :8797
  cd web && npm run dev         # UI on :5173 (proxies /api)

Production-style (single port):
  cd web && npm run build
  python3 -u server.py          # serves web/dist + /api on :8797

Primary source: Moneycontrol price/history APIs (NSE cash).
Spurts: live NSE / BSE exchange APIs.
Not a forecast or investment advice.
"""

from __future__ import annotations

import json
import math
import re
import ssl
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
# Prefer built React UI (web/dist); fall back to legacy static/.
WEB_DIST = ROOT / "web" / "dist"
IST = ZoneInfo("Asia/Kolkata")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Moneycontrol resolutions. 4h is aggregated from 60-minute bars.
TIMEFRAMES = {
    "15m": {
        "label": "15 Min",
        "resolution": "15",
        "lookback_days": 7,
        "countback": 220,
        "avg_window": 20,
    },
    "1h": {
        "label": "1 Hour",
        "resolution": "60",
        "lookback_days": 20,
        "countback": 220,
        "avg_window": 20,
    },
    "4h": {
        "label": "4 Hours",
        "resolution": "60",
        "lookback_days": 35,
        "countback": 320,
        "avg_window": 16,
        "aggregate": 4,
    },
    "1d": {
        "label": "1 Day",
        "resolution": "1D",
        "lookback_days": 140,
        "countback": 140,
        "avg_window": 20,
    },
    "1w": {
        "label": "1 Week",
        "resolution": "1W",
        "lookback_days": 900,
        "countback": 120,
        "avg_window": 12,
    },
    "1m": {
        "label": "1 Month",
        "resolution": "1M",
        "lookback_days": 2200,
        "countback": 48,
        "avg_window": 6,
    },
    # Swing/long frames use daily (or denser) bars so Lab/Chart/Tech have enough history.
    "3m": {
        "label": "3 Months",
        "resolution": "1D",
        "lookback_days": 130,
        "countback": 100,
        "avg_window": 20,
    },
    "6m": {
        "label": "6 Months",
        "resolution": "1D",
        "lookback_days": 220,
        "countback": 160,
        "avg_window": 20,
    },
    "1y": {
        "label": "1 Year",
        "resolution": "1D",
        "lookback_days": 420,
        "countback": 280,
        "avg_window": 20,
    },
    "5y": {
        "label": "5 Years",
        "resolution": "1W",
        "lookback_days": 2000,
        "countback": 280,
        "avg_window": 20,
    },
    "max": {
        "label": "Entire",
        "resolution": "1W",
        "lookback_days": 12000,
        "countback": 520,
        "avg_window": 20,
    },
}

# Nifty 50 constituents with Moneycontrol sc_id (NSE cash).
NIFTY50 = [
    {"id": "ADANIENT", "label": "Adani Ent", "sc_id": "AE01", "nse": "ADANIENT"},
    {"id": "ADANIPORTS", "label": "Adani Ports", "sc_id": "MPS", "nse": "ADANIPORTS"},
    {"id": "APOLLOHOSP", "label": "Apollo Hosp", "sc_id": "AHE", "nse": "APOLLOHOSP"},
    {"id": "ASIANPAINT", "label": "Asian Paints", "sc_id": "API", "nse": "ASIANPAINT"},
    {"id": "AXISBANK", "label": "Axis Bank", "sc_id": "UTI10", "nse": "AXISBANK"},
    {"id": "BAJAJ-AUTO", "label": "Bajaj Auto", "sc_id": "BA06", "nse": "BAJAJ-AUTO"},
    {"id": "BAJFINANCE", "label": "Bajaj Fin", "sc_id": "BAF", "nse": "BAJFINANCE"},
    {"id": "BAJAJFINSV", "label": "Bajaj Finserv", "sc_id": "BF04", "nse": "BAJAJFINSV"},
    {"id": "BEL", "label": "BEL", "sc_id": "BE03", "nse": "BEL"},
    {"id": "BHARTIARTL", "label": "Airtel", "sc_id": "BTV", "nse": "BHARTIARTL"},
    {"id": "CIPLA", "label": "Cipla", "sc_id": "C", "nse": "CIPLA"},
    {"id": "COALINDIA", "label": "Coal India", "sc_id": "CI29", "nse": "COALINDIA"},
    {"id": "DRREDDY", "label": "Dr Reddy", "sc_id": "DRL", "nse": "DRREDDY"},
    {"id": "EICHERMOT", "label": "Eicher", "sc_id": "EM", "nse": "EICHERMOT"},
    {"id": "ETERNAL", "label": "Eternal", "sc_id": "Z01", "nse": "ETERNAL"},
    {"id": "GRASIM", "label": "Grasim", "sc_id": "GI01", "nse": "GRASIM"},
    {"id": "HCLTECH", "label": "HCL Tech", "sc_id": "HCL02", "nse": "HCLTECH"},
    {"id": "HDFCBANK", "label": "HDFC Bank", "sc_id": "HDF01", "nse": "HDFCBANK"},
    {"id": "HDFCLIFE", "label": "HDFC Life", "sc_id": "HSL01", "nse": "HDFCLIFE"},
    {"id": "HEROMOTOCO", "label": "Hero Moto", "sc_id": "HHM", "nse": "HEROMOTOCO"},
    {"id": "HINDALCO", "label": "Hindalco", "sc_id": "H", "nse": "HINDALCO"},
    {"id": "HINDUNILVR", "label": "HUL", "sc_id": "HL", "nse": "HINDUNILVR"},
    {"id": "ICICIBANK", "label": "ICICI Bank", "sc_id": "ICI02", "nse": "ICICIBANK"},
    {"id": "INDUSINDBK", "label": "IndusInd", "sc_id": "IIB", "nse": "INDUSINDBK"},
    {"id": "INFY", "label": "Infosys", "sc_id": "IT", "nse": "INFY"},
    {"id": "ITC", "label": "ITC", "sc_id": "ITC", "nse": "ITC"},
    {"id": "JIOFIN", "label": "Jio Fin", "sc_id": "JFS", "nse": "JIOFIN"},
    {"id": "JSWSTEEL", "label": "JSW Steel", "sc_id": "JVS", "nse": "JSWSTEEL"},
    {"id": "KOTAKBANK", "label": "Kotak Bank", "sc_id": "KMF", "nse": "KOTAKBANK"},
    {"id": "LT", "label": "L&T", "sc_id": "LT", "nse": "LT"},
    {"id": "M&M", "label": "M&M", "sc_id": "MM", "nse": "M&M"},
    {"id": "MARUTI", "label": "Maruti", "sc_id": "MU01", "nse": "MARUTI"},
    {"id": "MAXHEALTH", "label": "Max Health", "sc_id": "MHI", "nse": "MAXHEALTH"},
    {"id": "NESTLEIND", "label": "Nestle", "sc_id": "NI", "nse": "NESTLEIND"},
    {"id": "NTPC", "label": "NTPC", "sc_id": "NTP", "nse": "NTPC"},
    {"id": "ONGC", "label": "ONGC", "sc_id": "ONG", "nse": "ONGC"},
    {"id": "POWERGRID", "label": "Powergrid", "sc_id": "PGC", "nse": "POWERGRID"},
    {"id": "RELIANCE", "label": "Reliance", "sc_id": "RI", "nse": "RELIANCE"},
    {"id": "SBILIFE", "label": "SBI Life", "sc_id": "SLI03", "nse": "SBILIFE"},
    {"id": "SBIN", "label": "SBI", "sc_id": "SBI", "nse": "SBIN"},
    {"id": "SUNPHARMA", "label": "Sun Pharma", "sc_id": "SPI", "nse": "SUNPHARMA"},
    {"id": "TATACONSUM", "label": "Tata Cons", "sc_id": "TT", "nse": "TATACONSUM"},
    {"id": "TATAMOTORS", "label": "Tata Motors", "sc_id": "TML02", "nse": "TATAMOTORS"},
    {"id": "TATASTEEL", "label": "Tata Steel", "sc_id": "TIS", "nse": "TATASTEEL"},
    {"id": "TCS", "label": "TCS", "sc_id": "TCS", "nse": "TCS"},
    {"id": "TECHM", "label": "TechM", "sc_id": "TM4", "nse": "TECHM"},
    {"id": "TITAN", "label": "Titan", "sc_id": "TI01", "nse": "TITAN"},
    {"id": "TRENT", "label": "Trent", "sc_id": "L", "nse": "TRENT"},
    {"id": "ULTRACEMCO", "label": "UltraTech", "sc_id": "UTC", "nse": "ULTRACEMCO"},
    {"id": "WIPRO", "label": "Wipro", "sc_id": "W", "nse": "WIPRO"},
]

PRESETS = NIFTY50  # alias used by /api/sources
DATA_DIR = ROOT / "data"

try:
    from universe_dim import (  # noqa: E402
        UNIVERSE_META as _DIM_UNIVERSE_META,
        clear_dimension_cache,
        dimension_status,
        ensure_fresh_dimension,
        get_universe_meta as _dim_universe_meta,
        get_universe_rows,
        is_large_universe,
        list_universe_meta,
        refresh_dimension,
        start_monday_refresh_scheduler,
    )
except ImportError:  # pragma: no cover
    _DIM_UNIVERSE_META = []
    clear_dimension_cache = None  # type: ignore
    dimension_status = None  # type: ignore
    ensure_fresh_dimension = None  # type: ignore
    _dim_universe_meta = None  # type: ignore
    get_universe_rows = None  # type: ignore
    is_large_universe = None  # type: ignore
    list_universe_meta = None  # type: ignore
    refresh_dimension = None  # type: ignore
    start_monday_refresh_scheduler = None  # type: ignore

UNIVERSES = [
    {"id": "nifty50", "label": "Nifty 50", "group": "Nifty", "enrich_limit": 50},
    {"id": "next50", "label": "Nifty Next 50", "group": "Nifty", "enrich_limit": 50},
    {"id": "largecap", "label": "Nifty 100", "group": "Nifty", "enrich_limit": 100},
    {"id": "nifty200", "label": "Nifty 200", "group": "Nifty", "enrich_limit": 200},
    {"id": "nifty500", "label": "Nifty 500", "group": "Nifty", "enrich_limit": 500},
    {"id": "midcap50", "label": "Nifty Midcap 50", "group": "Cap", "enrich_limit": 50},
    {"id": "midcap", "label": "Nifty Midcap 150", "group": "Cap", "enrich_limit": 150},
    {"id": "smallcap50", "label": "Nifty Smallcap 50", "group": "Cap", "enrich_limit": 50},
    {"id": "smallcap", "label": "Nifty Smallcap 250", "group": "Cap", "enrich_limit": 250},
    {"id": "microcap", "label": "Nifty Microcap 250", "group": "Cap", "enrich_limit": 250},
    {"id": "largemidcap", "label": "Nifty LargeMidcap 250", "group": "Cap", "enrich_limit": 250},
    {"id": "bse_large", "label": "BSE Group A", "group": "BSE", "enrich_limit": 700, "large": True},
    {"id": "bse_mid", "label": "BSE Group B", "group": "BSE", "enrich_limit": 1200, "large": True},
    {"id": "nse_all", "label": "NSE All", "group": "Exchange", "enrich_limit": 1200, "large": True},
    {"id": "bse_all", "label": "BSE All", "group": "Exchange", "enrich_limit": 1200, "large": True},
    {"id": "all", "label": "NSE All", "group": "Exchange", "enrich_limit": 1200, "large": True, "alias_of": "nse_all"},
]
if _DIM_UNIVERSE_META:
    UNIVERSES = [
        {
            "id": item["id"],
            "label": item["label"],
            "group": item.get("group") or "Nifty",
            "enrich_limit": item.get("enrich_limit", 200),
            "large": bool(item.get("large")),
            "alias_of": item.get("alias_of"),
        }
        for item in _DIM_UNIVERSE_META
    ]

INDEX_PRESETS = [
    {"id": "NIFTY50", "label": "Nifty 50", "symbol": "in;NSX", "kind": "index"},
    {"id": "SENSEX", "label": "Sensex", "symbol": "in;SEN", "kind": "index"},
]

MC_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.moneycontrol.com/",
}

# Board payloads stay until Refresh (fresh=1) or /api/cache/clear.
CACHE_TTL = 10**9
PROBE_TTL = 300
_cache_lock = threading.Lock()
_cache: dict[tuple, tuple[float, dict]] = {}
_probe_cache: tuple[float, dict] | None = None
_universe_cache: dict[str, list[dict]] = {}


def _load_universe(universe_id: str) -> list[dict]:
    universe_id = (universe_id or "nifty50").lower()
    # Spurts "live" book → scan NSE All on other desks if selected.
    if universe_id == "live":
        universe_id = "nse_all"
    if universe_id in _universe_cache:
        return _universe_cache[universe_id]

    rows: list[dict] = []
    if get_universe_rows is not None:
        try:
            rows = get_universe_rows(universe_id, require_sc_id=True)
        except (OSError, ValueError, RuntimeError, TypeError):
            rows = []

    if not rows:
        # Legacy fallbacks when dimension file is missing.
        if universe_id == "nifty50":
            rows = list(NIFTY50)
        elif universe_id in {
            "nifty500",
            "midcap",
            "smallcap",
            "largecap",
            "next50",
            "nifty200",
            "midcap50",
            "smallcap50",
            "microcap",
            "largemidcap",
        }:
            path = DATA_DIR / "nifty500.json"
            rows = json.loads(path.read_text()) if path.is_file() else list(NIFTY50)
        elif universe_id in {"all", "nse_all", "bse_all", "bse_large", "bse_mid"}:
            path = DATA_DIR / "all_nse.json"
            rows = json.loads(path.read_text()) if path.is_file() else list(NIFTY50)
        else:
            rows = list(NIFTY50)

    _universe_cache[universe_id] = rows
    return rows


def _universe_meta(universe_id: str) -> dict:
    uid = (universe_id or "nifty50").lower()
    if uid == "live":
        return {
            "id": "live",
            "label": "Live Spurts (NSE+BSE)",
            "enrich_limit": 0,
            "large": False,
            "count": None,
        }
    if _dim_universe_meta is not None:
        try:
            meta = _dim_universe_meta(uid)
            if meta:
                return meta
        except (OSError, ValueError, TypeError):
            pass
    for item in UNIVERSES:
        if item["id"] == uid:
            return item
    return UNIVERSES[0]


def _universe_is_large(universe_id: str) -> bool:
    if is_large_universe is not None:
        try:
            return bool(is_large_universe(universe_id))
        except (OSError, ValueError, TypeError):
            pass
    return (universe_id or "").lower() in {"all", "nse_all", "bse_all"}


def _reload_universe_cache() -> None:
    _universe_cache.clear()
    if clear_dimension_cache is not None:
        clear_dimension_cache()


def _ensure_universe_ready() -> None:
    """Refresh shared dimension when file/as_of is older than Monday 07:00 IST."""
    if ensure_fresh_dimension is None:
        return
    before = None
    try:
        before = dimension_status() if dimension_status else None
        ensure_fresh_dimension()
        after = dimension_status() if dimension_status else None
        if not before or not after or before.get("as_of") != after.get("as_of") or before.get("stale"):
            _reload_universe_cache()
    except Exception as exc:  # noqa: BLE001 — boards continue on legacy lists
        print(f"Universe dim: ensure_fresh skipped ({exc})")


def _universe_full_size(universe_id: str) -> int:
    uid = (universe_id or "nifty50").lower()
    if uid == "live":
        return 0  # Spurts membership list — size is feed-driven
    meta = _universe_meta(uid)
    if meta.get("count"):
        return int(meta["count"])
    if get_universe_rows is not None:
        try:
            return len(get_universe_rows(uid, require_sc_id=False))
        except (OSError, ValueError, RuntimeError, TypeError):
            pass
    return len(_load_universe(uid))


def _merge_quote_remainder(enriched: list[dict], quote_rows: list[dict]) -> list[dict]:
    """Keep full-history shortlist + remaining quote-level names for large books."""
    seen = {row.get("id") for row in enriched if row.get("id")}
    out = list(enriched)
    for row in quote_rows:
        rid = row.get("id")
        if rid and rid not in seen:
            out.append(row)
            seen.add(rid)
    return out

_CA_FILES = (
    "/etc/ssl/cert.pem",
    "/private/etc/ssl/cert.pem",
    "/etc/ssl/certs/ca-certificates.crt",
)


def _ssl_context() -> ssl.SSLContext:
    paths = []
    configured = ssl.get_default_verify_paths().openssl_cafile
    if configured:
        paths.append(configured)
    paths.extend(_CA_FILES)
    for path in paths:
        if path and Path(path).is_file():
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


SSL_CONTEXT = _ssl_context()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ist_stamp() -> str:
    return (
        _now()
        .astimezone(IST)
        .strftime("%-d %b, %-I:%M %p")
        .replace("AM", "am")
        .replace("PM", "pm")
        + " IST"
    )


_yahoo_slots = threading.Semaphore(6)
_yahoo_local = threading.local()
_yahoo_session = None
_mc_blocked: bool | None = None
# priceapi.moneycontrol.com hangs; techCharts history answers, but slowly.
_mc_quote_down = False
_mc_history_slow = False

# Moneycontrol resolution → Yahoo chart interval/range.
YAHOO_TF = {
    "15m": ("15m", "5d"),
    "1h": ("60m", "1mo"),
    "4h": ("60m", "3mo"),
    "1d": ("1d", "1y"),
    "1w": ("1wk", "5y"),
    "1m": ("1mo", "max"),
    "3m": ("1d", "3mo"),
    "6m": ("1d", "6mo"),
    "1y": ("1d", "1y"),
    "5y": ("1wk", "5y"),
    "max": ("1wk", "max"),
}


def _normalize_tf(tf_id: str | None) -> str:
    """Canonical timeframe id for all desks (accepts 1D / daily / etc.)."""
    raw = str(tf_id or "1d").strip().lower().replace(" ", "")
    aliases = {
        "d": "1d",
        "day": "1d",
        "daily": "1d",
        "1day": "1d",
        "w": "1w",
        "wk": "1w",
        "week": "1w",
        "weekly": "1w",
        "1week": "1w",
        "mo": "1m",
        "mon": "1m",
        "month": "1m",
        "monthly": "1m",
        "1month": "1m",
        "60m": "1h",
        "60min": "1h",
        "240m": "4h",
        "4hr": "4h",
        "3mo": "3m",
        "6mo": "6m",
        "12m": "1y",
        "year": "1y",
    }
    raw = aliases.get(raw, raw)
    return raw if raw in TIMEFRAMES else "1d"

YAHOO_INDEX = {
    "in;NSX": "^NSEI",
    "in;SEN": "^BSESN",
    "NIFTY50": "^NSEI",
    "SENSEX": "^BSESN",
}


def _get_json(url: str, headers: dict | None = None, timeout: float = 20) -> dict | list:
    req = Request(url, headers=headers or MC_HEADERS)
    with urlopen(req, timeout=timeout, context=SSL_CONTEXT) as response:
        return json.loads(response.read())


def _get_text(url: str, headers: dict | None = None, timeout: float = 20) -> tuple[int, str]:
    req = Request(url, headers=headers or MC_HEADERS)
    with urlopen(req, timeout=timeout, context=SSL_CONTEXT) as response:
        return response.status, response.read(240).decode("utf-8", "replace")


def _yahoo_http() -> object:
    """One curl_cffi session per thread so a board scan can run several Yahoo calls at once."""
    session = getattr(_yahoo_local, "session", None)
    if session is None:
        session = _curl_session()
        _yahoo_local.session = session
    return session


def _yahoo_get_json(url: str, timeout: float = 12) -> dict | list:
    session = _yahoo_http()
    with _yahoo_slots:
        response = session.get(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-IN,en;q=0.9",
                "Referer": "https://finance.yahoo.com/",
            },
            impersonate="chrome131",
            timeout=timeout,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Yahoo HTTP {response.status_code}")
    return response.json()


def _yahoo_ticker(nse: str, exchange: str = "NSE") -> str:
    sym = (nse or "").strip().upper()
    if not sym:
        return ""
    if sym.startswith("^"):
        return sym
    ex = (exchange or "NSE").upper()
    if ex == "BSE":
        return f"{sym}.BO"
    return f"{sym}.NS"


def session_status(moment: datetime | None = None) -> dict:
    local = (moment or _now()).astimezone(IST)
    label_time = (
        local.strftime("%a %-d %b · %-I:%M %p").replace("AM", "am").replace("PM", "pm")
    )
    weekend = local.weekday() >= 5
    minutes = local.hour * 60 + local.minute
    if weekend:
        state, label, detail = (
            "closed",
            "Market closed",
            "Cash market is shut today. Volume is from the last NSE session.",
        )
    elif minutes < 9 * 60 + 15:
        state, label, detail = (
            "preopen",
            "Before the open",
            "Cash market not open yet. Figures are from the previous close.",
        )
    elif minutes <= 15 * 60 + 30:
        state, label, detail = (
            "open",
            "Market open",
            "Cash session is live. Volume updates as Moneycontrol refreshes.",
        )
    else:
        state, label, detail = (
            "closed",
            "Market closed",
            "Today's cash session is over. Showing the latest available volume.",
        )
    return {
        "state": state,
        "label": label,
        "detail": detail,
        "clock": label_time + " IST",
    }


def _num(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _clean(text: str) -> str:
    text = (text or "").replace("&nbsp;", " ")
    return re.sub(r"<[^>]+>", "", text).strip()


def _probe_moneycontrol() -> dict:
    started = time.time()
    try:
        payload = _get_json(
            "https://priceapi.moneycontrol.com/pricefeed/nse/equitycash/RI",
            timeout=12,
        )
        data = payload.get("data") or {}
        vol = _num(data.get("VOL"))
        ok = payload.get("code") == "200" and vol is not None and vol > 0
        return {
            "id": "moneycontrol",
            "name": "Moneycontrol",
            "role": "primary",
            "trusted": True,
            "ok": ok,
            "latency_ms": int((time.time() - started) * 1000),
            "detail": f"Reliance last volume {int(vol):,}" if ok else "Volume missing",
            "endpoint": "priceapi.moneycontrol.com",
        }
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "id": "moneycontrol",
            "name": "Moneycontrol",
            "role": "primary",
            "trusted": True,
            "ok": False,
            "latency_ms": int((time.time() - started) * 1000),
            "detail": f"{exc.__class__.__name__}: {exc}",
            "endpoint": "priceapi.moneycontrol.com",
        }


def _probe_yahoo() -> dict:
    """Yahoo chart API — used as board fallback when Moneycontrol is blocked."""
    started = time.time()
    try:
        payload = _yahoo_get_json(
            "https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?interval=1d&range=5d",
            timeout=12,
        )
        result = ((payload.get("chart") or {}).get("result") or [None])[0]
        meta = (result or {}).get("meta") or {}
        price = _num(meta.get("regularMarketPrice"))
        ok = price is not None and price > 0
        return {
            "id": "yahoo",
            "name": "Yahoo Finance",
            "role": "fallback",
            "trusted": True,
            "ok": ok,
            "latency_ms": int((time.time() - started) * 1000),
            "detail": f"Reliance {price}" if ok else "Chart empty",
            "endpoint": "query1.finance.yahoo.com",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "yahoo",
            "name": "Yahoo Finance",
            "role": "fallback",
            "trusted": True,
            "ok": False,
            "latency_ms": int((time.time() - started) * 1000),
            "detail": f"{exc.__class__.__name__}: {exc}",
            "endpoint": "query1.finance.yahoo.com",
        }


def verify_sources(fresh: bool = False) -> dict:
    global _probe_cache
    now = time.time()
    if not fresh and _probe_cache and now - _probe_cache[0] < PROBE_TTL:
        payload = dict(_probe_cache[1])
        payload["cached"] = True
        payload["session"] = session_status()
        return payload

    sources = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_probe_moneycontrol), pool.submit(_probe_yahoo)]
        for future in as_completed(futures):
            sources.append(future.result())
    sources.sort(key=lambda item: 0 if item["id"] == "moneycontrol" else 1)
    primary_ok = any(item["id"] == "moneycontrol" and item["ok"] for item in sources)
    yahoo_ok = any(item["id"] == "yahoo" and item["ok"] for item in sources)
    plot_source = "Moneycontrol" if primary_ok else ("Yahoo Finance" if yahoo_ok else None)
    payload = {
        "as_of": _ist_stamp(),
        "cached": False,
        "session": session_status(),
        "plot_source": plot_source,
        "ready": primary_ok or yahoo_ok,
        "sources": sources,
        "presets": NIFTY50,
        "index_presets": INDEX_PRESETS,
        "universes": [
            {
                "id": item["id"],
                "label": item["label"],
                "group": item.get("group") or "Nifty",
                "size": _universe_full_size(item["id"]),
                "scanable": item.get("scanable")
                if item.get("scanable") is not None
                else len(_load_universe(item["id"])),
                "enrich_limit": item.get("enrich_limit"),
            }
            for item in (list_universe_meta() if list_universe_meta else UNIVERSES)
            if item.get("id") != "all"  # UI uses nse_all; keep `all` as API alias only
        ],
        "universe_dim": dimension_status() if dimension_status else None,
        "timeframes": [
            {"id": key, "label": meta["label"]} for key, meta in TIMEFRAMES.items()
        ],
    }
    with _cache_lock:
        _probe_cache = (now, payload)
    return payload


def search_symbols(query: str) -> list[dict]:
    query = re.sub(r"[\x00-\x1f<>]", "", query)[:40].strip()
    if len(query) < 1:
        return []
    url = (
        "https://www.moneycontrol.com/mccode/common/autosuggestion_solr.php"
        f"?classic=true&query={quote(query)}&type=1&format=json"
    )
    items = _get_json(url, timeout=15)
    if not isinstance(items, list):
        return []
    out = []
    for item in items[:12]:
        sc_id = (item.get("sc_id") or "").strip()
        name = _clean(item.get("stock_name") or item.get("name") or "")
        display = _clean(item.get("pdt_dis_nm") or "")
        nse = ""
        match = re.search(r",\s*([A-Z0-9.&-]{1,20}),\s*\d{4,}", display)
        if match:
            nse = match.group(1)
        if not sc_id or not name:
            continue
        out.append(
            {
                "sc_id": sc_id,
                "name": name,
                "nse": nse or sc_id,
                "label": f"{nse or sc_id} · {name}",
                "sector": _clean(item.get("sc_sector") or ""),
            }
        )
    return out


def _history_moneycontrol(nse: str, tf: dict, kind: str = "stock", index_symbol: str = "") -> dict:
    global _mc_blocked
    if _mc_blocked:
        raise RuntimeError("Moneycontrol blocked")
    to_ts = int(time.time())
    from_ts = to_ts - int(tf["lookback_days"]) * 86400
    countback = int(tf["countback"])
    resolution = tf["resolution"]
    if kind == "index":
        url = (
            "https://priceapi.moneycontrol.com/techCharts/indianMarket/index/history"
            f"?symbol={quote(index_symbol)}&resolution={quote(resolution)}"
            f"&from={from_ts}&to={to_ts}&countback={countback}&currencyCode=INR"
        )
    else:
        url = (
            "https://priceapi.moneycontrol.com/techCharts/indianMarket/stock/history"
            f"?symbol={quote(nse)}&resolution={quote(resolution)}"
            f"&from={from_ts}&to={to_ts}&countback={countback}&currencyCode=INR"
        )
    try:
        return _get_json(url, timeout=8)
    except HTTPError as exc:
        if exc.code in {403, 401, 429}:
            _mc_blocked = True
        raise


def _history_yahoo(
    nse: str,
    tf_id: str,
    *,
    kind: str = "stock",
    index_symbol: str = "",
    exchange: str = "NSE",
) -> dict:
    """Return Moneycontrol-shaped history dict {s,t,o,h,l,c,v} from Yahoo chart."""
    if kind == "index":
        ticker = YAHOO_INDEX.get(index_symbol) or YAHOO_INDEX.get((nse or "").upper()) or ""
    else:
        ticker = _yahoo_ticker(nse, exchange)
    if not ticker:
        return {"s": "error"}
    interval, span = YAHOO_TF.get(tf_id, ("1d", "1y"))
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(ticker, safe='^.')}?interval={quote(interval)}&range={quote(span)}"
    )
    payload = _yahoo_get_json(url, timeout=25)
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return {"s": "error"}
    quote_block = ((result.get("indicators") or {}).get("quote") or [None])[0] or {}
    times = result.get("timestamp") or []
    return {
        "s": "ok",
        "t": times,
        "o": quote_block.get("open") or [],
        "h": quote_block.get("high") or [],
        "l": quote_block.get("low") or [],
        "c": quote_block.get("close") or [],
        "v": quote_block.get("volume") or [],
        "_source": "yahoo",
        "_ticker": ticker,
        "_meta": result.get("meta") or {},
    }


def _history(
    nse: str,
    tf: dict,
    kind: str = "stock",
    index_symbol: str = "",
    *,
    tf_id: str = "1d",
    exchange: str = "NSE",
    fast: bool = False,
) -> dict:
    global _mc_history_slow
    # Board scans skip Moneycontrol history: one name takes ~6s, Yahoo answers in under a second.
    if not fast and not _mc_blocked and not _mc_history_slow:
        started = time.time()
        try:
            raw = _history_moneycontrol(nse, tf, kind=kind, index_symbol=index_symbol)
            if time.time() - started >= 3:
                _mc_history_slow = True
            if isinstance(raw, dict) and raw.get("s") == "ok":
                raw["_source"] = "moneycontrol"
                return raw
        except (URLError, HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError, RuntimeError):
            if time.time() - started >= 3:
                _mc_history_slow = True
    return _history_yahoo(
        nse,
        tf_id,
        kind=kind,
        index_symbol=index_symbol,
        exchange=exchange,
    )


def _quote_yahoo(nse: str, exchange: str = "NSE") -> dict:
    ticker = _yahoo_ticker(nse, exchange)
    if not ticker:
        return {}
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(ticker, safe='^.')}?interval=1d&range=1mo"
    )
    try:
        payload = _yahoo_get_json(url, timeout=20)
    except (RuntimeError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return {}
    meta = result.get("meta") or {}
    quote_block = ((result.get("indicators") or {}).get("quote") or [None])[0] or {}
    volumes = [v for v in (quote_block.get("volume") or []) if v is not None]
    avg20 = None
    if len(volumes) >= 2:
        window = volumes[-21:-1] if len(volumes) > 21 else volumes[:-1]
        if window:
            avg20 = sum(window) / len(window)
    price = _num(meta.get("regularMarketPrice"))
    prev = _num(meta.get("chartPreviousClose"))
    change_pct = _num(meta.get("regularMarketChangePercent"))
    if change_pct is None and price is not None and prev:
        change_pct = ((price - prev) / prev) * 100.0
    market = "BSE" if str(meta.get("exchangeName") or "").upper() in {"BSE", "BOM"} else "NSE"
    sym = (nse or "").strip().upper()
    return {
        "pricecurrent": price,
        "pricepercentchange": change_pct,
        "VOL": _num(meta.get("regularMarketVolume")),
        "DVolAvg20": avg20,
        "company": meta.get("longName") or meta.get("shortName") or sym,
        "NSEID": sym if market == "NSE" else "",
        "BSEID": sym if market == "BSE" else "",
        "SC_SUBSEC": "",
        "newSubsector": "",
        "AvgDelVolPer_5day": None,
        "_market": market,
        "_source": "yahoo",
        "_ticker": ticker,
    }


def _quote_stock(sc_id: str, nse: str = "", exchange: str = "NSE", *, fast: bool = False) -> dict:
    """Prefer Moneycontrol cash quote; fall back to Yahoo when that host is down."""
    global _mc_blocked, _mc_quote_down
    # The pricefeed host currently hangs until the socket times out. One miss is enough.
    if sc_id and not fast and not _mc_blocked and not _mc_quote_down:
        markets = ("bse", "nse") if (exchange or "").upper() == "BSE" else ("nse", "bse")
        for market in markets:
            url = f"https://priceapi.moneycontrol.com/pricefeed/{market}/equitycash/{quote(sc_id)}"
            try:
                payload = _get_json(url, timeout=4)
            except HTTPError as exc:
                if exc.code in {403, 401}:
                    _mc_blocked = True
                    break
                continue
            except (URLError, TimeoutError, OSError):
                _mc_quote_down = True
                break
            except (ValueError, json.JSONDecodeError):
                continue
            data = payload.get("data") or {}
            if data and (
                _num(data.get("pricecurrent")) is not None or _num(data.get("VOL")) is not None
            ):
                data["_market"] = market.upper()
                data["_source"] = "moneycontrol"
                return data
    if nse:
        return _quote_yahoo(nse, exchange=exchange)
    return {}


def _quote_index(symbol: str) -> dict:
    if not _mc_blocked:
        url = (
            "https://priceapi.moneycontrol.com/pricefeed/notapplicable/inidicesindia/"
            + quote(symbol, safe="")
        )
        try:
            payload = _get_json(url, timeout=20)
            data = payload.get("data") or {}
            if data:
                data["_source"] = "moneycontrol"
                return data
        except (URLError, HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            pass
    ticker = YAHOO_INDEX.get(symbol) or ""
    if not ticker:
        return {}
    yq = _quote_yahoo(ticker, exchange="NSE")
    if yq:
        yq["company"] = yq.get("company") or symbol
    return yq


def _bars_from_history(raw: dict, intraday: bool) -> list[dict]:
    if not isinstance(raw, dict) or raw.get("s") != "ok":
        return []
    times = raw.get("t") or []
    opens = raw.get("o") or []
    highs = raw.get("h") or []
    lows = raw.get("l") or []
    closes = raw.get("c") or []
    volumes = raw.get("v") or []
    bars = []
    for i, ts in enumerate(times):
        close = _num(closes[i] if i < len(closes) else None)
        volume = abs(_num(volumes[i] if i < len(volumes) else None) or 0.0)
        if close is None:
            continue
        when = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(IST)
        open_px = _num(opens[i] if i < len(opens) else None)
        high = _num(highs[i] if i < len(highs) else None)
        low = _num(lows[i] if i < len(lows) else None)
        prev = bars[-1]["close"] if bars else open_px or close
        change = close - prev if prev is not None else 0.0
        label = (
            when.strftime("%-d %b %-I:%M %p").replace("AM", "am").replace("PM", "pm")
            if intraday
            else when.strftime("%-d %b")
        )
        bars.append(
            {
                "ts": int(ts),
                "date": when.strftime("%Y-%m-%d"),
                "label": label,
                "open": round(open_px, 2) if open_px is not None else None,
                "high": round(high, 2) if high is not None else None,
                "low": round(low, 2) if low is not None else None,
                "close": round(close, 2),
                "volume": int(volume),
                "up": change >= 0,
                "change": round(change, 2),
                "change_pct": round((change / prev) * 100, 2) if prev else 0.0,
            }
        )
    return bars


def _aggregate_bars(bars: list[dict], group: int) -> list[dict]:
    if group <= 1 or not bars:
        return bars
    out = []
    for i in range(0, len(bars), group):
        chunk = bars[i : i + group]
        if not chunk:
            continue
        first, last = chunk[0], chunk[-1]
        highs = [bar["high"] for bar in chunk if bar.get("high") is not None]
        lows = [bar["low"] for bar in chunk if bar.get("low") is not None]
        volume = sum(bar["volume"] for bar in chunk)
        prev = out[-1]["close"] if out else first.get("open") or first["close"]
        change = last["close"] - prev if prev else 0.0
        out.append(
            {
                "ts": last["ts"],
                "date": last["date"],
                "label": last["label"],
                "open": first.get("open"),
                "high": max(highs) if highs else last["close"],
                "low": min(lows) if lows else last["close"],
                "close": last["close"],
                "volume": int(volume),
                "up": change >= 0,
                "change": round(change, 2),
                "change_pct": round((change / prev) * 100, 2) if prev else 0.0,
            }
        )
    return out


# Timeframe contract (all desks except Spurts): periods are bar-counts on the
# active TF's resolution. RSI(14) on 1d = 14 days; on 1w = 14 weeks; on 15m = 14×15m.
# ChartSchool: indicators apply on any chart timeframe the same way.
TF_CONTRACT = (
    "Periods count bars of the selected timeframe "
    "(N = avg_window). Example: RSI(14) on 1 Day = 14 daily bars; "
    "on 1 Week = 14 weekly bars. 3m/6m/1y load daily bars so trend studies "
    "have enough history."
)


def _tf_meta(tf_id: str) -> dict:
    tid = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tid]
    res = tf["resolution"]
    res_label = {
        "15": "15-minute bars",
        "60": "60-minute bars" + (" (×4 → 4h)" if tid == "4h" else ""),
        "1D": "daily bars",
        "1W": "weekly bars",
        "1M": "monthly bars",
    }.get(res, res)
    return {
        "id": tid,
        "label": tf["label"],
        "resolution": res,
        "resolution_label": res_label,
        "avg_window": int(tf["avg_window"]),
        "countback": int(tf["countback"]),
        "contract": TF_CONTRACT,
    }


# Volume formulas (documented for API + UI).
# Refs: StockCharts OBV / CMF / MFI / A/D · relative volume practice.
FORMULAS = {
    "timeframe": TF_CONTRACT,
    "rvol": "RVOL = V_t ÷ SMA(V, N) over prior N bars of the active TF",
    "obv": "OBV_t = OBV_{t−1} + V_t if C↑; −V_t if C↓ (Granville / ChartSchool OBV)",
    "obv_delta": "OBVΔ = OBV_t − OBV_{t−N} (rising = accumulation)",
    "volume_ratio": "UV/DV = Σ volume on up bars ÷ Σ volume on down bars over N bars",
    "ad": "A/D += ((C−L)−(H−C))/(H−L) × V  (Chaikin Accumulation/Distribution)",
    "cmf": "CMF(N) = Σ MFV_N ÷ Σ V_N ; MFV = A/D multiplier × V (Chaikin / ChartSchool)",
    "mfi": "MFI = 100 − 100/(1 + pos_MF ÷ neg_MF) over ~14 bars (ChartSchool MFI)",
    "vpt": "VPT += V × (C − C_prev) / C_prev (Volume Price Trend)",
    "bullish": "Bullish when bias score ≥ +30 (price up + volume confirmation)",
    "bearish": "Bearish when bias score ≤ −30 (price down + volume confirmation)",
    "score": (
        "Score: ±25 price · ±25 RVOL≥1 · ±15 RVOL≥1.5 · ±15 OBVΔ · "
        "±10 UV/DV · ±10 CMF · ±10 MFI"
    ),
}


def _vol_tone(rvol: float | None) -> str:
    if rvol is None:
        return "normal"
    if rvol >= 1.5:
        return "spike"
    if rvol < 0.7:
        return "quiet"
    return "normal"


def _bias_from_score(score: float) -> str:
    if score >= 30:
        return "bullish"
    if score <= -30:
        return "bearish"
    return "neutral"


def _money_flow_multiplier(high: float | None, low: float | None, close: float) -> float:
    if high is None or low is None:
        return 0.0
    span = high - low
    if span <= 0:
        return 0.0
    return ((close - low) - (high - close)) / span


def _volume_score(
    up: bool,
    rvol: float | None,
    obv_rising: bool | None,
    vol_ratio: float | None,
    cmf: float | None = None,
    mfi: float | None = None,
) -> float:
    """Combine classic volume confirms into a signed score (−100…+100)."""
    score = 25.0 if up else -25.0
    if rvol is not None:
        if rvol >= 1.0:
            score += 25.0 if up else -25.0
        if rvol >= 1.5:
            score += 15.0 if up else -15.0
        if rvol < 0.7:
            score *= 0.55
    if obv_rising is True and up:
        score += 15.0
    elif obv_rising is False and not up:
        score -= 15.0
    elif obv_rising is True and not up:
        score += 6.0
    elif obv_rising is False and up:
        score -= 6.0
    if vol_ratio is not None:
        if vol_ratio >= 1.2:
            score += 10.0
        elif vol_ratio <= 0.83:
            score -= 10.0
    if cmf is not None:
        if cmf >= 0.05:
            score += 10.0
        elif cmf <= -0.05:
            score -= 10.0
    if mfi is not None:
        if mfi >= 55:
            score += 10.0
        elif mfi <= 45:
            score -= 10.0
    return max(-100.0, min(100.0, score))


def _enrich(bars: list[dict], window: int = 20, quote: dict | None = None) -> list[dict]:
    out: list[dict] = []
    obv = 0.0
    ad = 0.0
    vpt = 0.0
    n_bars = len(bars)
    # Short listings: use whatever history exists instead of requiring a full window.
    window = _adapt_period(window or 20, max(1, n_bars - 1), minimum=1) if n_bars else int(window or 20)
    mfi_period = min(14, max(3, window), max(3, n_bars))
    for i, bar in enumerate(bars):
        start = max(0, i - window)
        prior = bars[start:i]
        sample = [item["volume"] for item in prior if item["volume"] > 0]
        avg = (sum(sample) / len(sample)) if sample else None
        rvol = (bar["volume"] / avg) if avg else None

        # OBV
        if i == 0:
            obv = float(bar["volume"])
        else:
            prev_close = bars[i - 1]["close"]
            if bar["close"] > prev_close:
                obv += bar["volume"]
            elif bar["close"] < prev_close:
                obv -= bar["volume"]

        # Accumulation / Distribution
        mfm = _money_flow_multiplier(bar.get("high"), bar.get("low"), bar["close"])
        mfv = mfm * bar["volume"]
        ad += mfv

        # VPT
        if i > 0 and bars[i - 1]["close"]:
            vpt += bar["volume"] * (bar["close"] - bars[i - 1]["close"]) / bars[i - 1]["close"]

        # CMF over window (including current)
        cmf_slice = out[start:i]
        cmf_mfv = sum(
            _money_flow_multiplier(item.get("high"), item.get("low"), item["close"]) * item["volume"]
            for item in cmf_slice
        ) + mfv
        cmf_vol = sum(item["volume"] for item in cmf_slice) + bar["volume"]
        cmf = (cmf_mfv / cmf_vol) if cmf_vol else None

        # MFI (typical price money flow)
        mfi = None
        if i >= mfi_period:
            pos_flow = 0.0
            neg_flow = 0.0
            for j in range(i - mfi_period + 1, i + 1):
                high = bars[j].get("high") if bars[j].get("high") is not None else bars[j]["close"]
                low = bars[j].get("low") if bars[j].get("low") is not None else bars[j]["close"]
                tp = (high + low + bars[j]["close"]) / 3.0
                raw_flow = tp * bars[j]["volume"]
                if j == 0:
                    continue
                prev_high = bars[j - 1].get("high")
                prev_low = bars[j - 1].get("low")
                prev_tp = (
                    (
                        (prev_high if prev_high is not None else bars[j - 1]["close"])
                        + (prev_low if prev_low is not None else bars[j - 1]["close"])
                        + bars[j - 1]["close"]
                    )
                    / 3.0
                )
                if tp > prev_tp:
                    pos_flow += raw_flow
                elif tp < prev_tp:
                    neg_flow += raw_flow
            if neg_flow > 0:
                mfi = 100.0 - (100.0 / (1.0 + pos_flow / neg_flow))
            elif pos_flow > 0:
                mfi = 100.0

        obv_rising = None
        if i >= window and out:
            obv_rising = obv > out[i - window]["obv"]

        window_bars = out[start:i]
        up_vol = sum(item["volume"] for item in window_bars if item.get("up"))
        down_vol = sum(item["volume"] for item in window_bars if not item.get("up"))
        if bar["up"]:
            up_vol += bar["volume"]
        else:
            down_vol += bar["volume"]
        vol_ratio = (up_vol / down_vol) if down_vol > 0 else (None if up_vol == 0 else 99.0)

        score = _volume_score(bool(bar["up"]), rvol, obv_rising, vol_ratio, cmf, mfi)
        bias = _bias_from_score(score)
        strength = (
            "strong"
            if abs(score) >= 60
            else "moderate"
            if abs(score) >= 30
            else "weak"
        )

        enriched = dict(bar)
        enriched["avg_vol"] = int(round(avg)) if avg else None
        enriched["rvol"] = round(rvol, 2) if rvol is not None else None
        enriched["spike"] = bool(rvol is not None and rvol >= 1.5)
        enriched["tone"] = _vol_tone(enriched["rvol"])
        enriched["obv"] = int(round(obv))
        enriched["obv_rising"] = obv_rising
        enriched["ad"] = int(round(ad))
        enriched["cmf"] = round(cmf, 3) if cmf is not None else None
        enriched["mfi"] = round(mfi, 1) if mfi is not None else None
        enriched["vpt"] = int(round(vpt))
        enriched["vol_ratio"] = round(vol_ratio, 2) if vol_ratio is not None else None
        enriched["score"] = round(score, 1)
        enriched["bias"] = bias
        enriched["strength"] = strength

        delivery = None
        if quote is not None and i == len(bars) - 1:
            delivery = _num(quote.get("AvgDelVolPer_5day"))
        move = ""
        if enriched.get("change_pct") is not None:
            sign = "+" if enriched["change_pct"] >= 0 else ""
            move = f"{sign}{enriched['change_pct']:.2f}%"
        enriched["study"] = {
            "volume": enriched["volume"],
            "rvol": enriched["rvol"],
            "avg_vol": enriched["avg_vol"],
            "move": move,
            "tone": enriched["tone"],
            "bias": enriched["bias"],
            "score": enriched["score"],
            "strength": enriched["strength"],
            "obv_rising": enriched["obv_rising"],
            "vol_ratio": enriched["vol_ratio"],
            "cmf": enriched["cmf"],
            "mfi": enriched["mfi"],
            "ad": enriched["ad"],
            "vpt": enriched["vpt"],
            "delivery_pct": delivery,
            "high": enriched.get("high"),
            "low": enriched.get("low"),
        }
        out.append(enriched)
    return out


def _counts(bars: list[dict]) -> dict:
    return {
        "all": len(bars),
        "bullish": sum(1 for bar in bars if bar.get("bias") == "bullish"),
        "bearish": sum(1 for bar in bars if bar.get("bias") == "bearish"),
        "neutral": sum(1 for bar in bars if bar.get("bias") == "neutral"),
        "spike": sum(1 for bar in bars if bar.get("tone") == "spike"),
        "up": sum(1 for bar in bars if bar.get("up")),
        "down": sum(1 for bar in bars if not bar.get("up")),
    }


def _stats(bars: list[dict], quote: dict, kind: str) -> dict:
    last = bars[-1] if bars else None
    live_vol = _num(quote.get("VOL"))
    return {
        "last_volume": (last["volume"] if last else 0) or int(live_vol or 0),
        "last_close": _num(quote.get("pricecurrent")) or (last["close"] if last else None),
        "change": _num(quote.get("pricechange")) if kind == "stock" else (last or {}).get("change"),
        "change_pct": _num(quote.get("pricepercentchange"))
        if kind == "stock"
        else (last or {}).get("change_pct"),
        "avg_vol_20": (last or {}).get("avg_vol")
        or int(_num(quote.get("DVolAvg20")) or 0)
        or None,
        "rvol": (last or {}).get("rvol"),
        "tone": (last or {}).get("tone") or "normal",
        "bias": (last or {}).get("bias") or "neutral",
        "score": (last or {}).get("score"),
        "strength": (last or {}).get("strength") or "weak",
        "obv": (last or {}).get("obv"),
        "obv_rising": (last or {}).get("obv_rising"),
        "vol_ratio": (last or {}).get("vol_ratio"),
        "cmf": (last or {}).get("cmf"),
        "mfi": (last or {}).get("mfi"),
        "ad": (last or {}).get("ad"),
        "vpt": (last or {}).get("vpt"),
        "delivery_qty": int(_num(quote.get("QtyDeliverable")) or 0) or None,
        "delivery_pct_5d": _num(quote.get("AvgDelVolPer_5day")),
        "spikes": sum(1 for bar in bars if bar.get("spike")),
        "bars": len(bars),
        "kind": kind,
        "updated": quote.get("lastupd") or quote.get("DTTIME") or "",
        "open": _num(quote.get("OPN")) or (last or {}).get("open"),
        "high": _num(quote.get("HP")) or (last or {}).get("high"),
        "low": _num(quote.get("LP")) or (last or {}).get("low"),
    }


def _resolve_stock(symbol: str, sc_id: str) -> dict:
    symbol = re.sub(r"[\x00-\x1f<>]", "", symbol or "").strip().upper()
    sc_id = re.sub(r"[\x00-\x1f<>]", "", sc_id or "").strip()
    for preset in NIFTY50:
        if symbol in {preset["id"], preset["nse"]} or sc_id == preset["sc_id"]:
            return {
                "kind": "stock",
                "id": preset["id"],
                "name": preset["label"],
                "sc_id": preset["sc_id"],
                "nse": preset["nse"],
            }
    if sc_id and symbol:
        return {
            "kind": "stock",
            "id": symbol,
            "name": symbol,
            "sc_id": sc_id,
            "nse": symbol,
        }
    if not symbol:
        return {
            "kind": "stock",
            "id": "RELIANCE",
            "name": "Reliance",
            "sc_id": "RI",
            "nse": "RELIANCE",
        }
    hits = search_symbols(symbol)
    if not hits:
        raise RuntimeError(f"No Moneycontrol match for {symbol}.")
    hit = next((item for item in hits if item["nse"] == symbol), hits[0])
    return {
        "kind": "stock",
        "id": hit["nse"],
        "name": hit["name"],
        "sc_id": hit["sc_id"],
        "nse": hit["nse"],
    }


def _resolve_index(symbol: str) -> dict:
    symbol = (symbol or "NIFTY50").strip().upper()
    for preset in INDEX_PRESETS:
        if symbol in {preset["id"], preset["symbol"].upper()}:
            return {
                "kind": "index",
                "id": preset["id"],
                "name": preset["label"],
                "symbol": preset["symbol"],
            }
    raise RuntimeError(f"Unknown index {symbol}.")


def _load_bars(
    nse: str,
    tf_id: str,
    kind: str = "stock",
    index_symbol: str = "",
    exchange: str = "NSE",
    *,
    fast: bool = False,
) -> list[dict]:
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    raw = _history(
        nse,
        tf,
        kind=kind,
        index_symbol=index_symbol,
        tf_id=tf_id,
        exchange=exchange,
        fast=fast,
    )
    intraday = tf_id in {"15m", "1h", "4h"}
    bars = _bars_from_history(raw, intraday=intraday)
    if tf.get("aggregate"):
        bars = _aggregate_bars(bars, int(tf["aggregate"]))
    return bars


def build_volume(
    symbol: str,
    sc_id: str,
    kind: str,
    tf_id: str,
    fresh: bool = False,
) -> dict:
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    kind = "index" if kind == "index" else "stock"
    if kind == "index":
        meta = _resolve_index(symbol)
        cache_key = ("index", meta["id"], tf_id)
    else:
        meta = _resolve_stock(symbol, sc_id)
        cache_key = ("stock", meta["nse"], tf_id)

    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                return payload

    if kind == "index":
        bars_raw = _load_bars("", tf_id, kind="index", index_symbol=meta["symbol"])
        quote = _quote_index(meta["symbol"])
        display_name = quote.get("company") or meta["name"]
        exchange = "INDEX"
        nse = meta["id"]
        sc = meta["symbol"]
    else:
        bars_raw = _load_bars(meta["nse"], tf_id, exchange=meta.get("exchange") or "NSE")
        quote = _quote_stock(
            meta["sc_id"],
            nse=meta.get("nse") or meta.get("id") or "",
            exchange=meta.get("exchange") or "NSE",
        )
        display_name = quote.get("company") or meta["name"]
        exchange = quote.get("_market") or meta.get("exchange") or "NSE"
        nse = quote.get("NSEID") or meta["nse"]
        sc = meta["sc_id"]

    bars = _enrich(bars_raw, window=int(tf["avg_window"]), quote=quote)
    if not bars:
        raise RuntimeError("No volume bars returned for this symbol and timeframe.")

    volume_available = any(bar["volume"] > 0 for bar in bars)
    sources = verify_sources()
    feed = quote.get("_source") or sources.get("plot_source") or "Yahoo Finance"
    note = f"NSE/BSE OHLCV · {tf['label']} via {feed}"
    if kind == "index" and not volume_available:
        note = "Index price from Moneycontrol; traded volume not on this feed"
    if tf_id == "4h":
        note += " (4h built from 60-minute bars)"
    stats = _stats(bars, quote, kind)
    preferred_win = max(12, min(int(tf.get("avg_window") or 20), 40))
    bars_used = len(bars)
    partial_history = bars_used < preferred_win + 1
    stats["bars_used"] = bars_used
    stats["partial_history"] = partial_history
    payload = {
        "as_of": _ist_stamp(),
        "cached": False,
        "session": session_status(),
        "timeframe": tf_id,
        "timeframe_label": tf["label"],
        "tf_meta": _tf_meta(tf_id),
        "formulas": FORMULAS,
        "volume_available": volume_available,
        "partial_history": partial_history,
        "bars_used": bars_used,
        "symbol": {
            "kind": kind,
            "id": meta["id"],
            "name": display_name,
            "nse": nse,
            "sc_id": sc,
            "exchange": exchange,
            "sector": quote.get("SC_SUBSEC") or quote.get("newSubsector") or "",
        },
        "stats": stats,
        "counts": _counts(bars),
        "study": {
            "nse": nse,
            "name": display_name,
            "rvol": stats.get("rvol"),
            "tone": stats.get("tone"),
            "bias": stats.get("bias"),
            "score": stats.get("score"),
            "strength": stats.get("strength"),
            "obv_rising": stats.get("obv_rising"),
            "vol_ratio": stats.get("vol_ratio"),
            "cmf": stats.get("cmf"),
            "mfi": stats.get("mfi"),
            "ad": stats.get("ad"),
            "vpt": stats.get("vpt"),
            "volume": stats.get("last_volume"),
            "avg_vol_20": stats.get("avg_vol_20"),
            "delivery_pct": stats.get("delivery_pct_5d"),
            "move": (
                f"{'+' if (stats.get('change_pct') or 0) >= 0 else ''}"
                f"{stats.get('change_pct'):.2f}%"
                if stats.get("change_pct") is not None
                else ""
            ),
        },
        "formulas": FORMULAS,
        "bars": bars,
        "source": {
            "name": "Moneycontrol",
            "endpoint": "priceapi.moneycontrol.com",
            "verified": bool(sources.get("ready")),
            "note": note,
        },
        "sources": sources.get("sources", []),
    }
    with _cache_lock:
        _cache[cache_key] = (now, payload)
    return payload


def _scan_quote_row(preset: dict) -> dict | None:
    """Fast first pass using live quote volume averages."""
    try:
        quote = _quote_stock(
            preset.get("sc_id") or "",
            nse=preset.get("nse") or preset.get("id") or "",
            exchange=preset.get("exchange") or "NSE",
            fast=True,
        )
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
        return None
    if not quote:
        return None
    vol = _num(quote.get("VOL")) or 0
    avg20 = _num(quote.get("DVolAvg20")) or 0
    rvol = (vol / avg20) if avg20 else None
    change_pct = _num(quote.get("pricepercentchange"))
    up = (change_pct or 0) >= 0
    score = _volume_score(up, rvol, None, None, None, None)
    return {
        "id": preset["id"],
        "nse": quote.get("NSEID") or quote.get("BSEID") or preset["nse"],
        "name": quote.get("company") or preset["label"],
        "sc_id": preset["sc_id"],
        "exchange": quote.get("_market") or preset.get("exchange") or "NSE",
        "sector": quote.get("SC_SUBSEC") or quote.get("newSubsector") or "",
        "volume": int(vol),
        "avg_vol": int(avg20) if avg20 else None,
        "rvol": round(rvol, 2) if rvol is not None else None,
        "tone": _vol_tone(round(rvol, 2) if rvol is not None else None),
        "bias": _bias_from_score(score),
        "score": round(score, 1),
        "strength": "strong" if abs(score) >= 60 else "moderate" if abs(score) >= 30 else "weak",
        "obv_rising": None,
        "vol_ratio": None,
        "cmf": None,
        "mfi": None,
        "ad": None,
        "vpt": None,
        "spike": bool(rvol is not None and rvol >= 1.5),
        "close": _num(quote.get("pricecurrent")),
        "change_pct": change_pct,
        "up": up,
        "label": "live",
        "delivery_pct": _num(quote.get("AvgDelVolPer_5day")),
        "study": {
            "volume": int(vol),
            "rvol": round(rvol, 2) if rvol is not None else None,
            "bias": _bias_from_score(score),
            "score": round(score, 1),
            "move": (
                f"{'+' if (change_pct or 0) >= 0 else ''}{change_pct:.2f}%"
                if change_pct is not None
                else ""
            ),
        },
    }


def _scan_row(preset: dict, tf_id: str) -> dict | None:
    tf = TIMEFRAMES[tf_id]
    bars = _enrich(
        _load_bars(
            preset["nse"],
            tf_id,
            exchange=preset.get("exchange") or "NSE",
            fast=True,
        ),
        window=int(tf["avg_window"]),
    )
    if not bars:
        return None
    last = bars[-1]
    preferred = max(12, min(int(tf.get("avg_window") or 20), 40))
    bars_used = len(bars)
    partial = bars_used < preferred + 1
    quote = {}
    try:
        quote = _quote_stock(
            preset.get("sc_id") or "",
            nse=preset.get("nse") or preset.get("id") or "",
            exchange=preset.get("exchange") or "NSE",
            fast=True,
        )
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
        quote = {}
    study = dict(last.get("study") or {})
    study["bars_used"] = bars_used
    study["partial_history"] = partial
    return {
        "id": preset["id"],
        "nse": quote.get("NSEID") or quote.get("BSEID") or preset["nse"],
        "name": quote.get("company") or preset["label"],
        "sc_id": preset["sc_id"],
        "exchange": quote.get("_market") or preset.get("exchange") or "NSE",
        "sector": quote.get("SC_SUBSEC") or quote.get("newSubsector") or "",
        "volume": last["volume"],
        "avg_vol": last.get("avg_vol"),
        "rvol": last.get("rvol"),
        "tone": last.get("tone"),
        "bias": last.get("bias"),
        "score": last.get("score"),
        "strength": last.get("strength"),
        "obv_rising": last.get("obv_rising"),
        "vol_ratio": last.get("vol_ratio"),
        "cmf": last.get("cmf"),
        "mfi": last.get("mfi"),
        "ad": last.get("ad"),
        "vpt": last.get("vpt"),
        "spike": last.get("spike"),
        "close": last["close"],
        "change_pct": last["change_pct"],
        "up": last["up"],
        "label": last["label"],
        "delivery_pct": _num(quote.get("AvgDelVolPer_5day")),
        "bars_used": bars_used,
        "partial_history": partial,
        "study": study,
    }


# --- Technical Desk: classic OHLC indicators ---------------------------------

TECH_INDICATORS = [
    "rsi",
    "macd",
    "sma",
    "ema",
    "bb",
    "stoch",
    "cci",
    "willr",
    "adx",
    "roc",
]

# Default Technical score set (matches UI filter default).
TECH_CORE_INDICATORS = ["rsi", "macd", "sma", "ema"]

# Wilder / Appel / Bollinger defaults — periods are bars of the active TF.
# RSI: ChartSchool RSI = 100 − 100/(1+RS); RS = AvgGain/AvgLoss (Wilder smooth).
TECH_FORMULAS = {
    "timeframe": TF_CONTRACT,
    "rsi": (
        "RSI(14) = 100 − 100/(1+RS); RS = AvgGain/AvgLoss (Wilder smooth) — "
        "≥55 bull · ≤45 bear · ≥60/≤40 strong · ChartSchool RSI"
    ),
    "macd": (
        "MACD = EMA12−EMA26; signal = EMA9(MACD); hist = MACD−signal "
        "(Appel) — hist>0 and MACD>signal = bullish"
    ),
    "sma": "SMA(n) = mean(close, n); stack bullish when SMA20 > SMA50",
    "ema": "EMA(n) with α=2/(n+1); close > EMA20 = short-term bullish",
    "bb": "%B = (C−Lower)/(Upper−Lower); bands = SMA20 ± 2σ (Bollinger)",
    "stoch": "%K = 100×(C−LL14)/(HH14−LL14) — ≥50 bull · ≤20/≥80 extremes",
    "cci": "CCI = (TP−SMA20)/(0.015×MD) — >0 up lean · ≥100/≤−100 strong",
    "willr": "%R = −100×(HH14−C)/(HH14−LL14) — >−50 bull · ≤−80/≥−20 extremes",
    "adx": "+DI/−DI/ADX(14) Wilder — direction from DI; ADX≥25 strengthens vote",
    "roc": "ROC(12) = 100×(C−C₁₂)/C₁₂ — >0 up · ≥3%/≤−3% strong",
    "score": "Score = sum of selected indicator votes scaled to −100…+100",
    "bullish": "Bullish when technical score ≥ +30",
    "bearish": "Bearish when technical score ≤ −30",
}

TECH_SOURCES = [
    {
        "id": "rsi",
        "name": "RSI",
        "ref": "J. Welles Wilder — ChartSchool Relative Strength Index",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-strength-index-rsi",
    },
    {
        "id": "macd",
        "name": "MACD",
        "ref": "Gerald Appel — ChartSchool MACD",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/macd-moving-average-convergence-divergence-oscillator",
    },
    {
        "id": "ma",
        "name": "SMA / EMA",
        "ref": "ChartSchool moving averages",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/moving-averages-simple-and-exponential",
    },
]


def _parse_tech_indicators(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return list(TECH_CORE_INDICATORS)
    if isinstance(raw, list):
        parts = []
        for item in raw:
            parts.extend(str(item).split(","))
    else:
        parts = str(raw).split(",")
    selected = []
    seen = set()
    for part in parts:
        key = part.strip().lower()
        if key in TECH_INDICATORS and key not in seen:
            selected.append(key)
            seen.add(key)
    return selected or list(TECH_CORE_INDICATORS)


def _adapt_period(preferred: int, n: int, minimum: int = 2) -> int:
    """Shrink a lookback period to fit available bars (IPO / short history)."""
    if n <= 0:
        return minimum
    return max(minimum, min(int(preferred), int(n)))


def _adapt_study_window(
    preferred: int,
    n: int,
    *,
    floor: int = 5,
    headroom: int = 2,
) -> int | None:
    """Window for Donchian/Chart studies that need a little history past the box.

    Returns None only when bars are below an absolute minimum.
    """
    abs_min = floor + max(1, headroom)
    if n < abs_min:
        return None
    return max(floor, min(int(preferred or floor), n - headroom))


def _sma_at(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    chunk = values[-period:]
    return sum(chunk) / period


def _ema_series(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    k = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def _rsi_series(closes: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if period <= 0 or len(closes) <= period:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        out[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - (100.0 / (1.0 + rs))
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def _stoch_k(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period:
        return None
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh <= ll:
        return 50.0
    return ((closes[-1] - ll) / (hh - ll)) * 100.0


def _cci_at(highs: list[float], lows: list[float], closes: list[float], period: int = 20) -> float | None:
    if len(closes) < period:
        return None
    tps = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(-period, 0)]
    tp = tps[-1]
    sma = sum(tps) / period
    md = sum(abs(x - sma) for x in tps) / period
    if md == 0:
        return 0.0
    return (tp - sma) / (0.015 * md)


def _willr_at(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period:
        return None
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh <= ll:
        return -50.0
    return ((hh - closes[-1]) / (hh - ll)) * -100.0


def _adx_last(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> tuple[float | None, float | None, float | None]:
    n = len(closes)
    if n < period + 2:
        return None, None, None
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    trs: list[float] = []
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if len(trs) < period:
        return None, None, None
    atr = sum(trs[:period]) / period
    plus_di_s = sum(plus_dm[:period]) / period
    minus_di_s = sum(minus_dm[:period]) / period
    dx_vals: list[float] = []
    def _di(p: float, m: float, a: float) -> tuple[float, float]:
        if a == 0:
            return 0.0, 0.0
        return 100.0 * p / a, 100.0 * m / a

    pdi, mdi = _di(plus_di_s, minus_di_s, atr)
    denom = pdi + mdi
    dx_vals.append(0.0 if denom == 0 else 100.0 * abs(pdi - mdi) / denom)
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
        plus_di_s = (plus_di_s * (period - 1) + plus_dm[i]) / period
        minus_di_s = (minus_di_s * (period - 1) + minus_dm[i]) / period
        pdi, mdi = _di(plus_di_s, minus_di_s, atr)
        denom = pdi + mdi
        dx_vals.append(0.0 if denom == 0 else 100.0 * abs(pdi - mdi) / denom)
    if len(dx_vals) < period:
        return pdi, mdi, None
    adx = sum(dx_vals[:period]) / period
    for i in range(period, len(dx_vals)):
        adx = (adx * (period - 1) + dx_vals[i]) / period
    return pdi, mdi, adx


def _tech_votes(ind: dict) -> list[tuple[str, int]]:
    votes: list[tuple[str, int]] = []
    rsi = ind.get("rsi")
    if rsi is not None:
        if rsi >= 60:
            votes.append(("rsi", 2))
        elif rsi >= 55:
            votes.append(("rsi", 1))
        elif rsi <= 40:
            votes.append(("rsi", -2))
        elif rsi <= 45:
            votes.append(("rsi", -1))
        else:
            votes.append(("rsi", 0))
    macd = ind.get("macd")
    signal = ind.get("macd_signal")
    hist = ind.get("macd_hist")
    if macd is not None and signal is not None and hist is not None:
        if hist > 0 and macd > signal:
            votes.append(("macd", 2 if hist > abs(macd) * 0.05 else 1))
        elif hist < 0 and macd < signal:
            votes.append(("macd", -2 if hist < -abs(macd) * 0.05 else -1))
        else:
            votes.append(("macd", 0))
    sma20 = ind.get("sma20")
    sma50 = ind.get("sma50")
    if sma20 is not None and sma50 is not None:
        votes.append(("sma", 1 if sma20 > sma50 else -1 if sma20 < sma50 else 0))
    ema20 = ind.get("ema20")
    close = ind.get("close")
    if ema20 is not None and close is not None:
        votes.append(("ema", 1 if close > ema20 else -1 if close < ema20 else 0))
    bb = ind.get("bb_pctb")
    if bb is not None:
        if bb >= 0.8:
            votes.append(("bb", 2))
        elif bb >= 0.5:
            votes.append(("bb", 1))
        elif bb <= 0.2:
            votes.append(("bb", -2))
        elif bb < 0.5:
            votes.append(("bb", -1))
        else:
            votes.append(("bb", 0))
    stoch = ind.get("stoch_k")
    if stoch is not None:
        if stoch >= 80:
            votes.append(("stoch", 2))
        elif stoch >= 50:
            votes.append(("stoch", 1))
        elif stoch <= 20:
            votes.append(("stoch", -2))
        elif stoch < 50:
            votes.append(("stoch", -1))
        else:
            votes.append(("stoch", 0))
    cci = ind.get("cci")
    if cci is not None:
        if cci >= 100:
            votes.append(("cci", 2))
        elif cci > 0:
            votes.append(("cci", 1))
        elif cci <= -100:
            votes.append(("cci", -2))
        elif cci < 0:
            votes.append(("cci", -1))
        else:
            votes.append(("cci", 0))
    willr = ind.get("willr")
    if willr is not None:
        if willr >= -20:
            votes.append(("willr", 2))
        elif willr >= -50:
            votes.append(("willr", 1))
        elif willr <= -80:
            votes.append(("willr", -2))
        elif willr < -50:
            votes.append(("willr", -1))
        else:
            votes.append(("willr", 0))
    plus_di = ind.get("plus_di")
    minus_di = ind.get("minus_di")
    adx = ind.get("adx")
    if plus_di is not None and minus_di is not None:
        lean = 1 if plus_di > minus_di else -1 if plus_di < minus_di else 0
        if adx is not None and adx >= 25 and lean:
            lean = 2 if lean > 0 else -2
        votes.append(("adx", lean))
    roc = ind.get("roc")
    if roc is not None:
        if roc >= 3:
            votes.append(("roc", 2))
        elif roc > 0:
            votes.append(("roc", 1))
        elif roc <= -3:
            votes.append(("roc", -2))
        elif roc < 0:
            votes.append(("roc", -1))
        else:
            votes.append(("roc", 0))
    return votes


def _tech_score_from_votes(
    votes: list[tuple[str, int]],
    selected: list[str] | None = None,
) -> float:
    if selected:
        allow = set(selected)
        votes = [(name, val) for name, val in votes if name in allow]
    if not votes:
        return 0.0
    raw = sum(v for _, v in votes)
    # each indicator can contribute up to ±2
    denom = max(2.0 * len(votes), 1.0)
    return max(-100.0, min(100.0, (raw / denom) * 100.0))


def _tech_enrich(bars: list[dict], indicators: list[str] | None = None) -> dict | None:
    # Process with whatever history exists (recent listings may have << 55 bars).
    if not bars or len(bars) < 3:
        return None
    closes = [float(b["close"]) for b in bars]
    highs = [
        float(b["high"] if b.get("high") is not None else b["close"]) for b in bars
    ]
    lows = [float(b["low"] if b.get("low") is not None else b["close"]) for b in bars]
    last = bars[-1]
    n = len(closes)
    partial = n < 55
    # Classic defaults, shrunk to available length.
    p_rsi = _adapt_period(14, max(2, n - 1), minimum=2)
    p_ema = _adapt_period(20, n, minimum=3)
    p_fast = _adapt_period(12, max(3, n // 2), minimum=3)
    p_slow = _adapt_period(26, n, minimum=max(4, p_fast + 1))
    p_sig = _adapt_period(9, max(3, n // 3), minimum=3)
    p_sma_f = _adapt_period(20, n, minimum=3)
    p_sma_s = _adapt_period(50, n, minimum=max(4, p_sma_f + 1))
    p_stoch = _adapt_period(14, n, minimum=3)
    p_cci = _adapt_period(20, n, minimum=3)
    p_roc = _adapt_period(12, max(2, n - 1), minimum=2)
    p_adx = _adapt_period(14, max(5, n // 2), minimum=5)

    ema20_s = _ema_series(closes, p_ema)
    ema12_s = _ema_series(closes, p_fast)
    ema26_s = _ema_series(closes, p_slow)
    macd_line: list[float | None] = [
        (ema12_s[i] - ema26_s[i]) if ema12_s[i] is not None and ema26_s[i] is not None else None
        for i in range(n)
    ]
    macd_vals = [x for x in macd_line if x is not None]
    signal_series: list[float | None] = [None] * n
    if len(macd_vals) >= p_sig:
        first_i = next(i for i, x in enumerate(macd_line) if x is not None)
        compact = _ema_series(macd_vals, p_sig)
        for j, val in enumerate(compact):
            if val is not None:
                signal_series[first_i + j] = val
    rsi_s = _rsi_series(closes, p_rsi)
    sma20 = _sma_at(closes, p_sma_f)
    sma50 = _sma_at(closes, p_sma_s)
    ema20 = ema20_s[-1]
    macd = macd_line[-1]
    macd_signal = signal_series[-1]
    macd_hist = (
        (macd - macd_signal) if macd is not None and macd_signal is not None else None
    )
    bb_mid = sma20
    bb_pctb = None
    if bb_mid is not None and n >= p_sma_f:
        chunk = closes[-p_sma_f:]
        var = sum((x - bb_mid) ** 2 for x in chunk) / p_sma_f
        std = var**0.5
        upper = bb_mid + 2 * std
        lower = bb_mid - 2 * std
        span = upper - lower
        bb_pctb = ((closes[-1] - lower) / span) if span > 0 else 0.5
    stoch_k = _stoch_k(highs, lows, closes, p_stoch)
    cci = _cci_at(highs, lows, closes, p_cci)
    willr = _willr_at(highs, lows, closes, p_stoch)
    plus_di, minus_di, adx = _adx_last(highs, lows, closes, p_adx)
    roc = None
    if n > p_roc and closes[-(p_roc + 1)]:
        roc = ((closes[-1] - closes[-(p_roc + 1)]) / closes[-(p_roc + 1)]) * 100.0
    ind = {
        "close": closes[-1],
        "rsi": round(rsi_s[-1], 1) if rsi_s[-1] is not None else None,
        "macd": round(macd, 3) if macd is not None else None,
        "macd_signal": round(macd_signal, 3) if macd_signal is not None else None,
        "macd_hist": round(macd_hist, 3) if macd_hist is not None else None,
        "sma20": round(sma20, 2) if sma20 is not None else None,
        "sma50": round(sma50, 2) if sma50 is not None else None,
        "ema20": round(ema20, 2) if ema20 is not None else None,
        "bb_pctb": round(bb_pctb, 3) if bb_pctb is not None else None,
        "stoch_k": round(stoch_k, 1) if stoch_k is not None else None,
        "cci": round(cci, 1) if cci is not None else None,
        "willr": round(willr, 1) if willr is not None else None,
        "plus_di": round(plus_di, 1) if plus_di is not None else None,
        "minus_di": round(minus_di, 1) if minus_di is not None else None,
        "adx": round(adx, 1) if adx is not None else None,
        "roc": round(roc, 2) if roc is not None else None,
    }
    selected = _parse_tech_indicators(indicators)
    votes = _tech_votes(ind)
    score = round(_tech_score_from_votes(votes, selected), 1)
    bias = _bias_from_score(score)
    strength = (
        "strong" if abs(score) >= 60 else "moderate" if abs(score) >= 30 else "weak"
    )
    return {
        **ind,
        "votes": {name: val for name, val in votes if name in selected},
        "indicators": selected,
        "score": score,
        "bias": bias,
        "strength": strength,
        "change_pct": last.get("change_pct"),
        "up": last.get("up"),
        "volume": last.get("volume"),
        "label": last.get("label"),
        "bars_used": n,
        "partial_history": partial,
    }


def _scan_tech_row(
    preset: dict,
    tf_id: str,
    indicators: list[str] | None = None,
) -> dict | None:
    bars = _load_bars(
        preset["nse"],
        tf_id,
        exchange=preset.get("exchange") or "NSE",
        fast=True,
    )
    study = _tech_enrich(bars, indicators=indicators)
    if not study:
        return None
    quote = {}
    try:
        quote = _quote_stock(
            preset.get("sc_id") or "",
            nse=preset.get("nse") or preset.get("id") or "",
            exchange=preset.get("exchange") or "NSE",
            fast=True,
        )
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
        quote = {}
    return {
        "id": preset["id"],
        "nse": quote.get("NSEID") or quote.get("BSEID") or preset["nse"],
        "name": quote.get("company") or preset["label"],
        "sc_id": preset["sc_id"],
        "exchange": quote.get("_market") or preset.get("exchange") or "NSE",
        "sector": quote.get("SC_SUBSEC") or quote.get("newSubsector") or "",
        "close": study.get("close"),
        "change_pct": study.get("change_pct"),
        "up": study.get("up"),
        "volume": study.get("volume"),
        "rsi": study.get("rsi"),
        "macd": study.get("macd"),
        "macd_signal": study.get("macd_signal"),
        "macd_hist": study.get("macd_hist"),
        "sma20": study.get("sma20"),
        "sma50": study.get("sma50"),
        "ema20": study.get("ema20"),
        "bb_pctb": study.get("bb_pctb"),
        "stoch_k": study.get("stoch_k"),
        "cci": study.get("cci"),
        "willr": study.get("willr"),
        "plus_di": study.get("plus_di"),
        "minus_di": study.get("minus_di"),
        "adx": study.get("adx"),
        "roc": study.get("roc"),
        "score": study.get("score"),
        "bias": study.get("bias"),
        "strength": study.get("strength"),
        "votes": study.get("votes") or {},
        "study": study,
        "spike": False,
        "bars_used": study.get("bars_used"),
        "partial_history": study.get("partial_history"),
    }


def build_tech_board(
    tf_id: str = "1d",
    universe_id: str = "nifty50",
    fresh: bool = False,
    indicators: str | list[str] | None = None,
) -> dict:
    _ensure_universe_ready()
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    meta = _universe_meta(universe_id)
    universe_id = meta["id"]
    selected = _parse_tech_indicators(indicators)
    presets = _load_universe(universe_id)
    cache_key = ("tech-board", universe_id, tf_id, ",".join(selected))
    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                return payload

    errors = 0
    if _universe_is_large(universe_id):
        quote_rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=18) as pool:
            futures = {pool.submit(_scan_quote_row, preset): preset for preset in presets}
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row and row.get("volume", 0) > 0:
                    quote_rows.append(row)
        quote_rows.sort(key=lambda item: item.get("volume") or 0, reverse=True)
        enrich_limit = int(meta.get("enrich_limit") or 200)
        shortlist = quote_rows[:enrich_limit]
        rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {
                pool.submit(
                    _scan_tech_row,
                    {
                        "id": row["id"],
                        "label": row["name"],
                        "sc_id": row["sc_id"],
                        "nse": row["nse"],
                        "exchange": row.get("exchange"),
                    },
                    tf_id,
                    selected,
                ): row
                for row in shortlist
            }
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row:
                    rows.append(row)
        enriched_n = len(rows)
        rows = _merge_quote_remainder(rows, quote_rows)
        universe_note = (
            f"{meta['label']}: quoted {len(quote_rows)}, tech-enriched {enriched_n}"
            f", board {len(rows)}/{_universe_full_size(universe_id)}"
            f" · {len(selected)} indicators"
        )
    else:
        rows = []
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {
                pool.submit(_scan_tech_row, preset, tf_id, selected): preset
                for preset in presets
            }
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row:
                    rows.append(row)
        universe_note = (
            f"{meta['label']} technical scan · {tf['label']} · {len(selected)} indicators"
        )

    rows.sort(
        key=lambda item: (
            0 if item.get("bias") == "bullish" else 1 if item.get("bias") == "bearish" else 2,
            -(item.get("score") or 0),
            -(item.get("rsi") or 0),
        )
    )
    sources = verify_sources()
    payload = {
        "as_of": _ist_stamp(),
        "cached": False,
        "desk": "tech",
        "session": session_status(),
        "timeframe": tf_id,
        "timeframe_label": tf["label"],
        "tf_meta": _tf_meta(tf_id),
        "universe": universe_id,
        "universe_label": meta["label"],
        "universe_size": _universe_full_size(universe_id),
        "universe_scanable": len(presets),
        "scanned": len(rows),
        "errors": errors,
        "formulas": TECH_FORMULAS,
        "chart_sources": TECH_SOURCES,
        "indicators": selected,
        "indicator_options": [
            {
                "id": key,
                "label": {
                    "rsi": "RSI",
                    "macd": "MACD",
                    "sma": "SMA 20/50",
                    "ema": "EMA 20",
                    "bb": "BB %B",
                    "stoch": "Stochastic",
                    "cci": "CCI",
                    "willr": "Williams %R",
                    "adx": "ADX + DI",
                    "roc": "ROC",
                }.get(key, key.upper()),
            }
            for key in TECH_INDICATORS
        ],
        "source": {
            "name": "Moneycontrol",
            "verified": bool(sources.get("ready")),
            "note": universe_note,
        },
        "sources": sources.get("sources", []),
        "counts": {
            "all": len(rows),
            "bullish": sum(1 for row in rows if row["bias"] == "bullish"),
            "bearish": sum(1 for row in rows if row["bias"] == "bearish"),
            "neutral": sum(1 for row in rows if row["bias"] == "neutral"),
            "spike": 0,
            "up": sum(1 for row in rows if row.get("up")),
            "down": sum(1 for row in rows if not row.get("up")),
        },
        "rows": rows,
    }
    with _cache_lock:
        _cache[cache_key] = (now, payload)
    return payload


def build_board(
    tf_id: str = "1d",
    universe_id: str = "nifty50",
    fresh: bool = False,
) -> dict:
    _ensure_universe_ready()
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    meta = _universe_meta(universe_id)
    universe_id = meta["id"]
    presets = _load_universe(universe_id)
    cache_key = ("board", universe_id, tf_id)
    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                return payload

    errors = 0
    # Very large universes: quote pass first, then history-enrich the most active names.
    # Index books (Nifty 50/500, Midcap, Smallcap) are scanned in full when sized.
    if _universe_is_large(universe_id):
        quote_rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=18) as pool:
            futures = {pool.submit(_scan_quote_row, preset): preset for preset in presets}
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row and row.get("volume", 0) > 0:
                    quote_rows.append(row)
        quote_rows.sort(key=lambda item: item.get("volume") or 0, reverse=True)
        enrich_limit = int(meta.get("enrich_limit") or 200)
        shortlist = quote_rows[:enrich_limit]
        rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {
                pool.submit(_scan_row, {
                    "id": row["id"],
                    "label": row["name"],
                    "sc_id": row["sc_id"],
                    "nse": row["nse"],
                    "exchange": row.get("exchange"),
                }, tf_id): row
                for row in shortlist
            }
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row:
                    rows.append(row)
        enriched_n = len(rows)
        rows = _merge_quote_remainder(rows, quote_rows)
        universe_note = (
            f"{meta['label']}: quoted {len(quote_rows)}, enriched {enriched_n}"
            f", board {len(rows)}/{_universe_full_size(universe_id)}"
        )
    else:
        rows = []
        pool = ThreadPoolExecutor(max_workers=12)
        futures = {pool.submit(_scan_row, preset, tf_id): preset for preset in presets}
        try:
            for future in as_completed(futures, timeout=18):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row:
                    rows.append(row)
        except TimeoutError:
            errors += 1
            print("Board scan: deadline — returning rows already in hand")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        universe_note = f"{meta['label']} full volume scan · {tf['label']}"

    rows.sort(
        key=lambda item: (
            0 if item.get("bias") == "bullish" else 1 if item.get("bias") == "bearish" else 2,
            -(item.get("score") or 0),
            -(item.get("rvol") or 0),
        )
    )
    sources = verify_sources()
    payload = {
        "as_of": _ist_stamp(),
        "cached": False,
        "session": session_status(),
        "timeframe": tf_id,
        "timeframe_label": tf["label"],
        "tf_meta": _tf_meta(tf_id),
        "universe": universe_id,
        "universe_label": meta["label"],
        "universe_size": _universe_full_size(universe_id),
        "universe_scanable": len(presets),
        "scanned": len(rows),
        "errors": errors,
        "formulas": FORMULAS,
        "source": {
            "name": "Moneycontrol",
            "verified": bool(sources.get("ready")),
            "note": universe_note,
        },
        "sources": sources.get("sources", []),
        "counts": {
            "all": len(rows),
            "bullish": sum(1 for row in rows if row["bias"] == "bullish"),
            "bearish": sum(1 for row in rows if row["bias"] == "bearish"),
            "neutral": sum(1 for row in rows if row["bias"] == "neutral"),
            "spike": sum(1 for row in rows if row.get("spike")),
            "up": sum(1 for row in rows if row["up"]),
            "down": sum(1 for row in rows if not row["up"]),
        },
        "rows": rows,
    }
    with _cache_lock:
        _cache[cache_key] = (now, payload)
    return payload


# --- Lab Desk: volume + chart-pattern reader ------------------------------
# Scientific / cited formulas to classify charts as:
#   • bull_breakout — upside break of range with volume
#   • bull_base     — consolidating range with accumulation
#   • consolidating — tight range / vol contraction (no break yet)
# Research only — not investment advice.
#
# Formula lineage:
#   • Donchian channel breakout — Richard Donchian / StockCharts
#   • Bollinger BandWidth squeeze — John Bollinger / StockCharts
#   • ATR volatility contraction — J. Welles Wilder
#   • RVOL on breakout — market practice / StockCharts relative volume
#   • CMF accumulation in base — Marc Chaikin / StockCharts
#   • OBV slope in base — Joseph Granville
#   • Higher-lows structure — classic swing charting

SCI_STUDIES = [
    "range",  # Donchian / box width
    "squeeze",  # BB Width + ATR% contraction
    "rvol",  # relative volume
    "cmf",  # accumulation in base
    "obv",  # OBV slope
    "structure",  # higher lows / lower highs
]

SCI_SOURCES = [
    {
        "id": "range",
        "name": "Donchian range %",
        "ref": "Richard Donchian / StockCharts — Price Channels (HH/LL box)",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/price-channels",
    },
    {
        "id": "squeeze",
        "name": "BandWidth + ATR%",
        "ref": "Bollinger BandWidth squeeze · Wilder ATR contraction",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/bollinger-bandwidth",
    },
    {
        "id": "rvol",
        "name": "RVOL on break",
        "ref": "Relative volume vs SMA(volume) — breakout confirmation",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-volume-rvol",
    },
    {
        "id": "cmf",
        "name": "CMF in base",
        "ref": "Marc Chaikin Money Flow — accumulation during consolidation",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/chaikin-money-flow-cmf",
    },
    {
        "id": "obv",
        "name": "OBV slope",
        "ref": "Joseph Granville — On Balance Volume rising in a base",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/on-balance-volume-obv",
    },
    {
        "id": "structure",
        "name": "Higher lows",
        "ref": "Swing charting — rising pivot lows = bullish structure",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/trend-lines",
    },
]

SCI_FORMULAS = {
    "timeframe": TF_CONTRACT,
    "range": (
        "Range% = 100 × (HH_N − LL_N) / mid over N=avg_window bars — "
        "tight box ≈ consolidation (Donchian / ChartSchool Price Channels)"
    ),
    "squeeze": (
        "BandWidth = (Upper−Lower)/SMA_N = 4σ/SMA; ATR% = ATR14/close; "
        "contraction vs prior N bars = squeeze (Bollinger · Wilder ATR)"
    ),
    "rvol": (
        "RVOL = V ÷ SMA(V, N) — breakout needs RVOL ≥ 1.5 "
        "(ChartSchool relative volume practice)"
    ),
    "cmf": (
        "CMF(N) in the base — positive = accumulation while price coils "
        "(Chaikin / ChartSchool CMF)"
    ),
    "obv": (
        "OBV Δ over N bars > 0 while range is tight = quiet buying "
        "(Granville / ChartSchool OBV)"
    ),
    "structure": (
        "Higher pivot lows (last 3 swing lows rising) = bullish structure "
        "(ChartSchool Trend Lines)"
    ),
    "bull_breakout": (
        "Close > prior HH_N (exclude current bar) AND RVOL≥1.5 AND close near highs"
    ),
    "bull_base": (
        "Consolidating box + (CMF>0 or OBV rising or higher lows) — coiled bull"
    ),
    "consolidating": (
        "Tight Range% + squeeze (BB/ATR contraction) + volume drying in base"
    ),
    "score": "Bull score prioritizes breakout > bull base > plain consolidation",
    "rank": "Rank 1 = highest bull/pattern score in the universe",
    "spark": "Sparkline = last 30 closes for visual pattern context",
}


def _sma_last(values: list[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    chunk = values[-period:]
    return sum(chunk) / period


def _ema_last(values: list[float], period: int) -> float | None:
    series = _ema_series(values, period)
    return series[-1] if series else None


def _spark_closes(closes: list[float], points: int = 30) -> list[float]:
    """Normalize last N closes to 0…1 for SVG sparklines."""
    chunk = closes[-points:] if len(closes) >= 2 else closes
    if len(chunk) < 2:
        return []
    lo = min(chunk)
    hi = max(chunk)
    span = hi - lo
    if span <= 0:
        return [0.5] * len(chunk)
    return [round((x - lo) / span, 4) for x in chunk]


def _atr_series(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    """Wilder ATR series (None until seeded)."""
    n = len(closes)
    out: list[float | None] = [None] * n
    if n < period + 1:
        return out
    trs: list[float] = [highs[0] - lows[0]]
    for i in range(1, n):
        trs.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    atr = sum(trs[1 : period + 1]) / period
    out[period] = atr
    for i in range(period + 1, n):
        atr = (atr * (period - 1) + trs[i]) / period
        out[i] = atr
    return out


def _pivot_lows(lows: list[float], left: int = 2, right: int = 2) -> list[tuple[int, float]]:
    """Swing lows: low[i] <= neighbors in [i-left, i+right]."""
    out: list[tuple[int, float]] = []
    n = len(lows)
    for i in range(left, n - right):
        window = lows[i - left : i + right + 1]
        if lows[i] <= min(window):
            out.append((i, lows[i]))
    return out


def _higher_lows(lows: list[float], count: int = 3) -> bool | None:
    lr = 2 if len(lows) >= 10 else 1
    pivots = _pivot_lows(lows, left=lr, right=lr)
    if len(pivots) < count:
        return None
    recent = [p[1] for p in pivots[-count:]]
    return all(recent[i] < recent[i + 1] for i in range(len(recent) - 1))


def _sci_enrich(bars: list[dict], window: int = 20) -> dict | None:
    """Volume + chart-pattern reader for bull / consolidating setups."""
    n = len(bars)
    # Fit Donchian/base window to available history (recent listings OK).
    base = _adapt_study_window(window or 20, n, floor=4, headroom=1)
    if base is None:
        return None
    preferred = max(12, min(int(window or 20), 30))
    partial = n < preferred + 20
    closes = [float(b["close"]) for b in bars]
    highs = [
        float(b["high"] if b.get("high") is not None else b["close"]) for b in bars
    ]
    lows = [float(b["low"] if b.get("low") is not None else b["close"]) for b in bars]
    vols = [float(b.get("volume") or 0) for b in bars]
    last = bars[-1]
    close = closes[-1]

    # Donchian box — exclude today for breakout test when possible
    if n >= base + 1:
        prior_h = max(highs[-(base + 1) : -1])
        prior_l = min(lows[-(base + 1) : -1])
    else:
        prior_h = max(highs[:-1] or highs)
        prior_l = min(lows[:-1] or lows)
    mid = (prior_h + prior_l) / 2.0 if prior_h > prior_l else close
    range_pct = (100.0 * (prior_h - prior_l) / mid) if mid else None
    pos_in_range = None
    if prior_h > prior_l:
        pos_in_range = (close - prior_l) / (prior_h - prior_l)

    # Bollinger BandWidth on N=base bars of the active TF (ChartSchool BandWidth)
    bb_n = base
    sma_bb = _sma_at(closes, bb_n)
    bb_width = None
    bb_width_prev = None
    if sma_bb is not None and n >= bb_n:
        chunk = closes[-bb_n:]
        var = sum((x - sma_bb) ** 2 for x in chunk) / bb_n
        std = var**0.5
        # BandWidth = (upper − lower) / middle ; bands = SMA ± 2σ → 4σ/SMA
        bb_width = (4.0 * std) / sma_bb if sma_bb else None
        if n >= bb_n * 2:
            prev_closes = closes[-(bb_n * 2) : -bb_n]
            prev_sma = sum(prev_closes) / bb_n
            prev_var = sum((x - prev_sma) ** 2 for x in prev_closes) / bb_n
            prev_std = prev_var**0.5
            bb_width_prev = (4.0 * prev_std) / prev_sma if prev_sma else None

    atr_p = _adapt_period(14, max(3, n - 1), minimum=3)
    atr_s = _atr_series(highs, lows, closes, atr_p)
    atr = atr_s[-1]
    atr_prev = atr_s[-1 - base] if n > base + atr_p else None
    atr_pct = (100.0 * atr / close) if atr and close else None
    atr_pct_prev = (100.0 * atr_prev / closes[-1 - base]) if atr_prev and closes[-1 - base] else None
    squeeze = False
    if bb_width is not None and bb_width_prev is not None and bb_width_prev > 0:
        squeeze = bb_width < bb_width_prev * 0.85
    if atr_pct is not None and atr_pct_prev is not None and atr_pct_prev > 0:
        squeeze = squeeze or atr_pct < atr_pct_prev * 0.85

    # Volume: RVOL + dry-up in base
    avg_vol = _sma_last(vols, base)
    rvol = (vols[-1] / avg_vol) if avg_vol and avg_vol > 0 else None
    half = max(2, base // 2)
    base_vol = _sma_last(vols[-(base + 1) : -1] or vols[-base:], half)
    prior_vol = _sma_last(vols[-(2 * base) : -(base + 1)] or vols[-base:], half)
    vol_dry = bool(
        base_vol is not None and prior_vol is not None and prior_vol > 0 and base_vol < prior_vol * 0.85
    )

    # CMF over base window
    cmf_n = min(base, n)
    mfv_sum = 0.0
    vol_sum = 0.0
    for i in range(n - cmf_n, n):
        mfv_sum += _money_flow_multiplier(highs[i], lows[i], closes[i]) * vols[i]
        vol_sum += vols[i]
    cmf = (mfv_sum / vol_sum) if vol_sum > 0 else None

    # OBV slope over base
    obv = 0.0
    obv_series: list[float] = []
    for i in range(n):
        if i == 0:
            obv = vols[i]
        elif closes[i] > closes[i - 1]:
            obv += vols[i]
        elif closes[i] < closes[i - 1]:
            obv -= vols[i]
        obv_series.append(obv)
    obv_back = min(base, max(1, n - 1))
    obv_delta = obv_series[-1] - obv_series[-1 - obv_back]
    obv_rising = obv_delta > 0

    hl_need = 3 if n >= 12 else 2
    higher_lows = _higher_lows(lows[-min(n, 60) :], hl_need)

    # Pattern scores (0…100)
    consol_score = 0.0
    if range_pct is not None:
        if range_pct <= 8:
            consol_score += 40
        elif range_pct <= 12:
            consol_score += 28
        elif range_pct <= 18:
            consol_score += 14
    if squeeze:
        consol_score += 25
    if vol_dry:
        consol_score += 20
    if pos_in_range is not None and 0.25 <= pos_in_range <= 0.75:
        consol_score += 15
    consol_score = min(100.0, consol_score)
    consolidating = consol_score >= 55

    breakout = bool(
        prior_h
        and close > prior_h
        and rvol is not None
        and rvol >= 1.5
        and (pos_in_range is None or pos_in_range >= 0.85)
    )
    accum = bool(
        (cmf is not None and cmf > 0.05)
        or obv_rising
        or higher_lows is True
    )

    bull_score = 0.0
    if breakout:
        bull_score += 55
        if rvol is not None:
            bull_score += min(20.0, (rvol - 1.5) * 10.0)
        if cmf is not None and cmf > 0:
            bull_score += 10
        if higher_lows:
            bull_score += 10
    elif consolidating and accum:
        bull_score += 35 + consol_score * 0.35
        if cmf is not None and cmf >= 0.10:
            bull_score += 12
        if obv_rising:
            bull_score += 8
        if higher_lows:
            bull_score += 10
    elif consolidating:
        bull_score += consol_score * 0.25
    elif accum and pos_in_range is not None and pos_in_range >= 0.6:
        bull_score += 28
    bull_score = min(100.0, bull_score)

    if breakout:
        pattern = "bull_breakout"
        bias = "bullish"
    elif consolidating and accum:
        pattern = "bull_base"
        bias = "bullish"
    elif consolidating:
        pattern = "consolidating"
        bias = "neutral"
    elif bull_score >= 40:
        pattern = "bull_base"
        bias = "bullish"
    else:
        pattern = "none"
        bias = "neutral"

    # Primary score: emphasize bulls; consolidating ranks by coil quality
    if pattern == "bull_breakout":
        score = bull_score
    elif pattern == "bull_base":
        score = 0.65 * bull_score + 0.35 * consol_score
    elif pattern == "consolidating":
        score = consol_score * 0.7
    else:
        score = max(bull_score, consol_score) * 0.35
    score = round(max(-100.0, min(100.0, score)), 1)

    strength = (
        "strong" if score >= 70 else "moderate" if score >= 45 else "weak"
    )
    spark = _spark_closes(closes, 30)
    spark_up = bool(len(closes) >= 2 and closes[-1] >= closes[-min(30, n)])

    return {
        "close": close,
        "change_pct": last.get("change_pct"),
        "up": last.get("up"),
        "volume": int(round(vols[-1])),
        "rvol": round(rvol, 2) if rvol is not None else None,
        "range_pct": round(range_pct, 2) if range_pct is not None else None,
        "pos_in_range": round(pos_in_range, 3) if pos_in_range is not None else None,
        "bb_width": round(bb_width, 4) if bb_width is not None else None,
        "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
        "squeeze": squeeze,
        "vol_dry": vol_dry,
        "cmf": round(cmf, 3) if cmf is not None else None,
        "obv_rising": obv_rising,
        "higher_lows": higher_lows,
        "pattern": pattern,
        "consol_score": round(consol_score, 1),
        "bull_score": round(bull_score, 1),
        "score": score,
        "bias": bias,
        "strength": strength,
        "spike": breakout,
        "spark": spark,
        "spark_up": spark_up,
        "label": last.get("label"),
        "breakout_level": round(prior_h, 2) if prior_h else None,
        "support_level": round(prior_l, 2) if prior_l else None,
        "bars_used": n,
        "partial_history": partial,
    }


def _scan_sci_row(preset: dict, tf_id: str) -> dict | None:
    tf = TIMEFRAMES[tf_id]
    bars = _load_bars(
        preset["nse"],
        tf_id,
        exchange=preset.get("exchange") or "NSE",
        fast=True,
    )
    study = _sci_enrich(bars, window=int(tf["avg_window"]))
    if not study:
        return None
    quote = {}
    try:
        quote = _quote_stock(
            preset.get("sc_id") or "",
            nse=preset.get("nse") or preset.get("id") or "",
            exchange=preset.get("exchange") or "NSE",
            fast=True,
        )
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
        quote = {}
    return {
        "id": preset["id"],
        "nse": quote.get("NSEID") or quote.get("BSEID") or preset["nse"],
        "name": quote.get("company") or preset["label"],
        "sc_id": preset["sc_id"],
        "exchange": quote.get("_market") or preset.get("exchange") or "NSE",
        "sector": quote.get("SC_SUBSEC") or quote.get("newSubsector") or "",
        "close": study.get("close"),
        "change_pct": study.get("change_pct"),
        "up": study.get("up"),
        "volume": study.get("volume"),
        "rvol": study.get("rvol"),
        "range_pct": study.get("range_pct"),
        "pos_in_range": study.get("pos_in_range"),
        "bb_width": study.get("bb_width"),
        "atr_pct": study.get("atr_pct"),
        "squeeze": study.get("squeeze"),
        "vol_dry": study.get("vol_dry"),
        "cmf": study.get("cmf"),
        "obv_rising": study.get("obv_rising"),
        "higher_lows": study.get("higher_lows"),
        "pattern": study.get("pattern"),
        "consol_score": study.get("consol_score"),
        "bull_score": study.get("bull_score"),
        "score": study.get("score"),
        "bias": study.get("bias"),
        "strength": study.get("strength"),
        "spike": study.get("spike"),
        "spark": study.get("spark") or [],
        "spark_up": study.get("spark_up"),
        "breakout_level": study.get("breakout_level"),
        "support_level": study.get("support_level"),
        "study": study,
        "bars_used": study.get("bars_used"),
        "partial_history": study.get("partial_history"),
        "rank": None,
        "percentile": None,
    }


def build_sci_board(
    tf_id: str = "1d",
    universe_id: str = "nifty50",
    fresh: bool = False,
) -> dict:
    _ensure_universe_ready()
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    meta = _universe_meta(universe_id)
    universe_id = meta["id"]
    presets = _load_universe(universe_id)
    cache_key = ("sci-board-pattern", universe_id, tf_id)
    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                return payload

    errors = 0
    if _universe_is_large(universe_id):
        quote_rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=18) as pool:
            futures = {pool.submit(_scan_quote_row, preset): preset for preset in presets}
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row and row.get("volume", 0) > 0:
                    quote_rows.append(row)
        quote_rows.sort(key=lambda item: item.get("volume") or 0, reverse=True)
        enrich_limit = int(meta.get("enrich_limit") or 200)
        shortlist = quote_rows[:enrich_limit]
        rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {
                pool.submit(
                    _scan_sci_row,
                    {
                        "id": row["id"],
                        "label": row["name"],
                        "sc_id": row["sc_id"],
                        "nse": row["nse"],
                        "exchange": row.get("exchange"),
                    },
                    tf_id,
                ): row
                for row in shortlist
            }
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row:
                    rows.append(row)
        enriched_n = len(rows)
        rows = _merge_quote_remainder(rows, quote_rows)
        universe_note = (
            f"{meta['label']}: quoted {len(quote_rows)}, pattern-enriched {enriched_n}"
            f", board {len(rows)}/{_universe_full_size(universe_id)}"
        )
    else:
        rows = []
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {
                pool.submit(_scan_sci_row, preset, tf_id): preset for preset in presets
            }
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row:
                    rows.append(row)
        universe_note = (
            f"{meta['label']} pattern lab · {tf['label']} · volume + chart patterns"
        )

    pattern_rank = {
        "bull_breakout": 0,
        "bull_base": 1,
        "consolidating": 2,
        "none": 3,
    }
    rows.sort(
        key=lambda item: (
            pattern_rank.get(item.get("pattern") or "none", 9),
            -(item.get("score") or 0),
            -(item.get("bull_score") or 0),
            -(item.get("rvol") or 0),
            item.get("nse") or "",
        )
    )
    total = len(rows) or 1
    for idx, row in enumerate(rows):
        row["rank"] = idx + 1
        row["percentile"] = round(100.0 * (total - idx) / total, 1)

    sources = verify_sources()
    payload = {
        "as_of": _ist_stamp(),
        "cached": False,
        "desk": "sci",
        "session": session_status(),
        "timeframe": tf_id,
        "timeframe_label": tf["label"],
        "tf_meta": _tf_meta(tf_id),
        "universe": universe_id,
        "universe_label": meta["label"],
        "universe_size": _universe_full_size(universe_id),
        "universe_scanable": len(presets),
        "scanned": len(rows),
        "errors": errors,
        "formulas": SCI_FORMULAS,
        "studies": list(SCI_STUDIES),
        "chart_sources": SCI_SOURCES,
        "dashboard": {
            "bull_breakout": sum(1 for row in rows if row.get("pattern") == "bull_breakout"),
            "bull_base": sum(1 for row in rows if row.get("pattern") == "bull_base"),
            "consolidating": sum(1 for row in rows if row.get("pattern") == "consolidating"),
            "squeeze": sum(1 for row in rows if row.get("squeeze")),
            "vol_dry": sum(1 for row in rows if row.get("vol_dry")),
            "higher_lows": sum(1 for row in rows if row.get("higher_lows")),
            "avg_range_pct": (
                round(
                    sum(row["range_pct"] for row in rows if row.get("range_pct") is not None)
                    / max(1, sum(1 for row in rows if row.get("range_pct") is not None)),
                    2,
                )
                if any(row.get("range_pct") is not None for row in rows)
                else None
            ),
        },
        "source": {
            "name": sources.get("plot_source") or "Moneycontrol / Yahoo",
            "verified": bool(sources.get("ready")),
            "note": universe_note
            + " · refs: Donchian · Bollinger BandWidth · Wilder ATR · Chaikin CMF · Granville OBV",
        },
        "sources": sources.get("sources", []),
        "counts": {
            "all": len(rows),
            "bullish": sum(1 for row in rows if row["bias"] == "bullish"),
            "bearish": sum(1 for row in rows if row["bias"] == "bearish"),
            "neutral": sum(1 for row in rows if row["bias"] == "neutral"),
            "spike": sum(1 for row in rows if row.get("spike")),
            "up": sum(1 for row in rows if row.get("up")),
            "down": sum(1 for row in rows if not row.get("up")),
            "bull_breakout": sum(1 for row in rows if row.get("pattern") == "bull_breakout"),
            "bull_base": sum(1 for row in rows if row.get("pattern") == "bull_base"),
            "consolidating": sum(1 for row in rows if row.get("pattern") == "consolidating"),
        },
        "rows": rows,
    }
    with _cache_lock:
        _cache[cache_key] = (now, payload)
    return payload


# --- Chart Desk: StockCharts ChartSchool · Chart Analysis -------------------
# Source TOC: https://chartschool.stockcharts.com/table-of-contents/chart-analysis
# Implements computable rules from:
#   Support & Resistance · Trend Lines · Gaps · Chart Patterns ·
#   Fibonacci Retracements · Candlestick reversals
# Research only — not investment advice.

CHART_STUDIES = [
    "support_resistance",
    "trend",
    "gap",
    "pattern",
    "fibonacci",
    "candle",
]

CHART_SOURCES = [
    {
        "id": "support_resistance",
        "name": "Support & Resistance",
        "ref": "StockCharts ChartSchool — reaction highs/lows, trading ranges, S⇄R flips",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/support-and-resistance",
    },
    {
        "id": "trend",
        "name": "Trend Lines",
        "ref": "StockCharts — uptrend (rising lows) / downtrend (falling highs), ≥3 touches",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/trend-lines",
    },
    {
        "id": "gap",
        "name": "Gaps",
        "ref": "StockCharts — common · breakaway · runaway · exhaustion (volume context)",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/gaps-and-gap-analysis",
    },
    {
        "id": "pattern",
        "name": "Chart Patterns",
        "ref": "StockCharts — rectangle · triangles · flags · double top/bottom",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns",
    },
    {
        "id": "fibonacci",
        "name": "Fibonacci Retracements",
        "ref": "StockCharts — 23.6% · 38.2% · 50% · 61.8% alert zones",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-annotation-tools/fibonacci-retracements",
    },
    {
        "id": "candle",
        "name": "Candlestick Reversals",
        "ref": "StockCharts — hammer · engulfing · shooting star · doji",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/candlestick-charts/introduction-to-candlesticks",
    },
]

CHART_FORMULAS = {
    "timeframe": TF_CONTRACT,
    "support": (
        "Support = nearest swing-low pivot ≤ close (reaction low zone ~0.4%) — "
        "ChartSchool Support & Resistance"
    ),
    "resistance": (
        "Resistance = nearest swing-high pivot ≥ close — ChartSchool S&R"
    ),
    "trend": (
        "Uptrend: ≥3 rising swing lows + positive slope; downtrend: ≥3 falling "
        "swing highs + negative slope — ChartSchool Trend Lines (3rd touch validates)"
    ),
    "gap_up": "Up gap when bar.low > prior.high — ChartSchool Gaps",
    "gap_down": "Down gap when bar.high < prior.low — ChartSchool Gaps",
    "breakaway_gap": "Gap out of congestion with RVOL≥1.4 — ChartSchool gap types",
    "rectangle": "Sideways range between flat support & resistance",
    "asc_triangle": "Flat highs + rising lows — bullish continuation bias",
    "desc_triangle": "Flat lows + falling highs — bearish continuation bias",
    "sym_triangle": "Converging highs and lows — coiled continuation/reversal",
    "double_bottom": "Two similar swing lows with intervening peak — reversal",
    "double_top": "Two similar swing highs with intervening trough — reversal",
    "flag": "Tight counter-move after an impulse leg — continuation",
    "fib": (
        "After advance: level = High − (High−Low)×r; after decline: Low+(High−Low)×r; "
        "r ∈ {0.236, 0.382, 0.5, 0.618} — ChartSchool Fibonacci (50% Dow Theory)"
    ),
    "hammer": "Small body near top of range + long lower shadow — bullish reversal",
    "engulfing": "Current body engulfs prior body — reversal candlestick",
    "score": "Confluence of S/R · trend · gap · pattern · Fib · candle (0…100 bull lean)",
}


def _pivot_highs(highs: list[float], left: int = 2, right: int = 2) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    n = len(highs)
    for i in range(left, n - right):
        window = highs[i - left : i + right + 1]
        if highs[i] >= max(window):
            out.append((i, highs[i]))
    return out


def _linreg_slope(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    n = float(len(xs))
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return None
    return num / den


def _detect_candle(o: float, h: float, l: float, c: float, prev_o: float, prev_c: float) -> str:
    """ChartSchool candlestick tags — last bar (hammer / engulfing / star / doji)."""
    body = abs(c - o)
    full = max(h - l, 1e-9)
    upper = h - max(c, o)
    lower = min(c, o) - l
    # Doji: open ≈ close (very small body)
    if body / full <= 0.08:
        return "doji"
    # Hammer: long lower shadow (≥2× body), little/no upper shadow, body in upper range
    if lower >= 2.0 * max(body, full * 0.05) and upper <= body * 0.5 and (c + o) / 2 >= l + 0.55 * full:
        return "hammer"
    # Shooting star: mirror of hammer at tops
    if upper >= 2.0 * max(body, full * 0.05) and lower <= body * 0.5 and (c + o) / 2 <= h - 0.55 * full:
        return "shooting_star"
    # Engulfing: current body fully wraps prior body with opposite color
    prev_body = abs(prev_c - prev_o)
    if body > prev_body * 1.05 and prev_body > 0:
        if c > o and prev_c < prev_o and c >= max(prev_o, prev_c) and o <= min(prev_o, prev_c):
            return "engulfing_bull"
        if c < o and prev_c > prev_o and o >= max(prev_o, prev_c) and c <= min(prev_o, prev_c):
            return "engulfing_bear"
    return "none"


def _chart_enrich(bars: list[dict], window: int = 20) -> dict | None:
    """StockCharts Chart Analysis — tightened ChartSchool rules."""
    n = len(bars)
    # Fit S/R window to available bars so short listings still get a reading.
    base = _adapt_study_window(window or 20, n, floor=4, headroom=1)
    if base is None:
        return None
    preferred = max(18, min(int(window or 20), 40))
    partial = n < preferred + 12
    opens = [float(b.get("open") if b.get("open") is not None else b["close"]) for b in bars]
    highs = [float(b["high"] if b.get("high") is not None else b["close"]) for b in bars]
    lows = [float(b["low"] if b.get("low") is not None else b["close"]) for b in bars]
    closes = [float(b["close"]) for b in bars]
    vols = [float(b.get("volume") or 0) for b in bars]
    last = bars[-1]
    close = closes[-1]
    tol = max(close * 0.004, 1e-6)  # ~0.4% zone (ChartSchool: zones, not exact ticks)

    # --- Support & Resistance (reaction highs / lows) ---
    look = min(n, 90)
    off = n - look
    pivot_lr = 2 if look >= 10 else 1
    ph_abs = [(off + i, v) for i, v in _pivot_highs(highs[-look:], left=pivot_lr, right=pivot_lr)]
    pl_abs = [(off + i, v) for i, v in _pivot_lows(lows[-look:], left=pivot_lr, right=pivot_lr)]
    # Nearest resistance above / support below from recent pivots
    resist_cands = sorted({v for _, v in ph_abs[-8:] if v >= close - tol})
    support_cands = sorted({v for _, v in pl_abs[-8:] if v <= close + tol}, reverse=True)
    resistance = resist_cands[0] if resist_cands else max(highs[-base:])
    support = support_cands[0] if support_cands else min(lows[-base:])
    if resistance <= support:
        support, resistance = min(lows[-base:]), max(highs[-base:])

    mid_sr = (support + resistance) / 2.0
    range_width = ((resistance - support) / mid_sr * 100.0) if mid_sr else None
    dist_sup = ((close - support) / close * 100.0) if close else None
    dist_res = ((resistance - close) / close * 100.0) if close else None
    # Near = inside ChartSchool-style zone under the level
    near_support = bool(dist_sup is not None and -0.15 <= dist_sup <= 1.25)
    near_resistance = bool(dist_res is not None and -0.15 <= dist_res <= 1.25)
    # Breaks: close through the level (ChartSchool: supply/demand wins on close)
    if n >= 2:
        prior_inside = closes[-2] <= resistance + tol and closes[-2] >= support - tol
        break_res = bool(close > resistance + tol and prior_inside)
        break_sup = bool(close < support - tol and prior_inside)
    else:
        break_res = break_sup = False

    # --- Trend lines: ChartSchool valid line prefers ≥3 touches ---
    low_piv = pl_abs[-6:]
    high_piv = ph_abs[-6:]
    up_slope = (
        _linreg_slope([float(i) for i, _ in low_piv], [v for _, v in low_piv])
        if len(low_piv) >= 2
        else None
    )
    dn_slope = (
        _linreg_slope([float(i) for i, _ in high_piv], [v for _, v in high_piv])
        if len(high_piv) >= 2
        else None
    )
    hl_need = 3 if n >= 12 else 2
    hl = _higher_lows(lows[-min(n, 70) :], hl_need)
    lh = None
    if len(high_piv) >= 3:
        vals = [v for _, v in high_piv[-3:]]
        lh = all(vals[i] > vals[i + 1] * 0.998 for i in range(2))
    elif len(high_piv) >= 2:
        vals = [v for _, v in high_piv[-2:]]
        lh = vals[0] > vals[1] * 0.998

    trend = "sideways"
    trend_valid = False
    piv_need = 3 if n >= 12 else 2
    if len(low_piv) >= piv_need and up_slope is not None and up_slope > 0 and hl is True:
        trend, trend_valid, trend_touches = "up", True, len(low_piv)
    elif len(high_piv) >= piv_need and dn_slope is not None and dn_slope < 0 and lh is True:
        trend, trend_valid, trend_touches = "down", True, len(high_piv)
    elif hl is True:
        trend, trend_touches = "up", len(low_piv)
    elif lh is True:
        trend, trend_touches = "down", len(high_piv)
    else:
        trend_touches = max(len(low_piv), len(high_piv))

    # --- Gaps (ChartSchool definitions + volume significance) ---
    gap = "none"
    gap_pct = None
    avg_vol = _sma_last(vols, base)
    rvol = (vols[-1] / avg_vol) if avg_vol and avg_vol > 0 else None
    congested = bool(range_width is not None and 4.0 <= range_width <= 16.0)
    if n >= 2:
        prev_h, prev_l = highs[-2], lows[-2]
        # Gap must persist: today's extreme still clear of prior bar (intraday fill ignored on daily)
        if lows[-1] > prev_h:
            gap_pct = (lows[-1] - prev_h) / prev_h * 100.0 if prev_h else None
            strong_vol = rvol is not None and rvol >= 1.4
            large_gap = gap_pct is not None and gap_pct >= 1.0
            if congested and strong_vol and close > resistance - tol:
                gap = "up_breakaway"
            elif strong_vol and trend == "up" and not near_resistance:
                gap = "up_runaway"
            elif strong_vol and large_gap and (near_resistance or trend == "up"):
                gap = "up_exhaustion"
            else:
                gap = "up_common"
        elif highs[-1] < prev_l:
            gap_pct = (prev_l - highs[-1]) / prev_l * 100.0 if prev_l else None
            strong_vol = rvol is not None and rvol >= 1.4
            large_gap = gap_pct is not None and gap_pct >= 1.0
            if congested and strong_vol and close < support + tol:
                gap = "down_breakaway"
            elif strong_vol and trend == "down" and not near_support:
                gap = "down_runaway"
            elif strong_vol and large_gap and (near_support or trend == "down"):
                gap = "down_exhaustion"
            else:
                gap = "down_common"

    # --- Chart patterns (ChartSchool geometries, pivot-aware) ---
    recent_low_piv = [v for i, v in pl_abs if i >= n - base]
    recent_high_piv = [v for i, v in ph_abs if i >= n - base]
    # Rising lows / falling highs from last 3 pivots when available
    rising_lows = (
        len(recent_low_piv) >= 3
        and recent_low_piv[-1] > recent_low_piv[-2] > recent_low_piv[-3]
    ) or (
        len(recent_low_piv) >= 2 and recent_low_piv[-1] > recent_low_piv[-2] * 1.008
    )
    falling_highs = (
        len(recent_high_piv) >= 3
        and recent_high_piv[-1] < recent_high_piv[-2] < recent_high_piv[-3]
    ) or (
        len(recent_high_piv) >= 2 and recent_high_piv[-1] < recent_high_piv[-2] * 0.992
    )
    # Flat side: pivot cluster within 1.2%
    flat_high = False
    flat_low = False
    if len(recent_high_piv) >= 2:
        hh, hlv = max(recent_high_piv[-4:]), min(recent_high_piv[-4:])
        flat_high = (hh - hlv) / mid_sr <= 0.012
    if len(recent_low_piv) >= 2:
        lh_v, ll = max(recent_low_piv[-4:]), min(recent_low_piv[-4:])
        flat_low = (lh_v - ll) / mid_sr <= 0.012

    pattern = "none"
    if range_width is not None and range_width <= 11 and flat_high and flat_low:
        pattern = "rectangle"
    elif flat_high and rising_lows and range_width is not None and range_width <= 18:
        pattern = "asc_triangle"
    elif flat_low and falling_highs and range_width is not None and range_width <= 18:
        pattern = "desc_triangle"
    elif falling_highs and rising_lows and range_width is not None and range_width <= 14:
        pattern = "sym_triangle"
    else:
        # Double bottom: two similar lows, peak between, second low not much lower
        if len(pl_abs) >= 2:
            i1, a = pl_abs[-2]
            i2, b = pl_abs[-1]
            if 6 <= i2 - i1 <= base * 2 and abs(a - b) / mid_sr <= 0.025 and i2 >= n - base:
                peak = max(highs[i1 : i2 + 1])
                if peak >= max(a, b) * 1.025 and close >= min(a, b):
                    pattern = "double_bottom"
        if pattern == "none" and len(ph_abs) >= 2:
            i1, a = ph_abs[-2]
            i2, b = ph_abs[-1]
            if 6 <= i2 - i1 <= base * 2 and abs(a - b) / mid_sr <= 0.025 and i2 >= n - base:
                trough = min(lows[i1 : i2 + 1])
                if trough <= min(a, b) * 0.975 and close <= max(a, b):
                    pattern = "double_top"
        # Flag / pennant: impulse ≥6% then 5–12 bar coil ≤4%
        if pattern == "none" and n > 20:
            for impulse_len in (10, 14, 18):
                if n <= impulse_len + 6:
                    continue
                start = closes[-(impulse_len + 6)]
                mid = closes[-6]
                move = (mid - start) / start if start else 0
                coil = (max(highs[-6:]) - min(lows[-6:])) / close if close else 1
                if abs(move) >= 0.06 and coil <= 0.045:
                    pattern = "flag_bull" if move > 0 else "flag_bear"
                    break

    # --- Fibonacci: ChartSchool after advance/decline ---
    swing_look = min(n - 1, max(50, base * 3))
    swing_h = highs[-swing_look:]
    swing_l = lows[-swing_look:]
    swing_high, swing_low = max(swing_h), min(swing_l)
    hi_i = len(swing_h) - 1 - swing_h[::-1].index(swing_high)
    lo_i = len(swing_l) - 1 - swing_l[::-1].index(swing_low)
    fib_levels: dict[str, float] = {}
    fib_nearest = None
    fib_dist = None
    fib_zone = False
    fib_context = None  # pullback | bounce
    if swing_high > swing_low * 1.02:
        span = swing_high - swing_low
        if hi_i > lo_i:
            # Advance then correction — retrace from high toward low
            fib_context = "pullback"
            for name, ratio in (("23.6", 0.236), ("38.2", 0.382), ("50.0", 0.5), ("61.8", 0.618)):
                fib_levels[name] = swing_high - span * ratio
        else:
            # Decline then bounce — retrace from low toward high
            fib_context = "bounce"
            for name, ratio in (("23.6", 0.236), ("38.2", 0.382), ("50.0", 0.5), ("61.8", 0.618)):
                fib_levels[name] = swing_low + span * ratio
        best_name, best_d = None, 1e9
        for name, lvl in fib_levels.items():
            d = abs(close - lvl) / close * 100.0
            if d < best_d:
                best_d, best_name = d, name
        fib_nearest, fib_dist = best_name, round(best_d, 2)
        # ChartSchool alert zone: moderate 38.2–50 + golden 61.8 (prefer ≤1%)
        fib_zone = bool(
            best_d <= 1.0 and best_name in {"38.2", "50.0", "61.8"} and fib_context
        )

    if n >= 2:
        candle = _detect_candle(
            opens[-1], highs[-1], lows[-1], closes[-1], opens[-2], closes[-2]
        )
    else:
        candle = "none"
    # ChartSchool: reversal candles matter more at S/R
    candle_quality = candle
    if candle == "hammer" and not (near_support or fib_zone or trend == "down"):
        candle_quality = "hammer_weak"
    if candle == "shooting_star" and not (near_resistance or fib_zone or trend == "up"):
        candle_quality = "shooting_star_weak"

    if break_res:
        setup = "breakout"
    elif break_sup:
        setup = "breakdown"
    elif near_support:
        setup = "near_support"
    elif near_resistance:
        setup = "near_resistance"
    elif fib_zone:
        setup = "fib_zone"
    else:
        setup = "mid_range"

    score = 50.0
    if trend == "up":
        score += 14 if trend_valid else 8
    elif trend == "down":
        score -= 14 if trend_valid else 8
    if near_support:
        score += 10
    if near_resistance:
        score -= 8
    if break_res:
        score += 16 + (4 if rvol and rvol >= 1.4 else 0)
    if break_sup:
        score -= 16 + (4 if rvol and rvol >= 1.4 else 0)
    if pattern == "asc_triangle":
        score += 10
    elif pattern == "desc_triangle":
        score -= 10
    elif pattern == "double_bottom":
        score += 12
    elif pattern == "double_top":
        score -= 12
    elif pattern == "flag_bull":
        score += 9
    elif pattern == "flag_bear":
        score -= 9
    elif pattern == "rectangle" and near_support:
        score += 6
    elif pattern == "sym_triangle":
        score += 2
    if gap in {"up_breakaway", "up_runaway"}:
        score += 10
    elif gap == "up_common":
        score += 2
    elif gap in {"down_breakaway", "down_runaway"}:
        score -= 10
    elif gap == "down_common":
        score -= 2
    elif gap == "up_exhaustion":
        score -= 4
    elif gap == "down_exhaustion":
        score += 4
    if candle in {"hammer", "engulfing_bull"}:
        score += 10 if candle_quality == candle else 4
    if candle in {"shooting_star", "engulfing_bear"}:
        score -= 10 if candle_quality == candle else 4
    if fib_zone and fib_context == "pullback":
        score += 7
    if fib_zone and fib_context == "bounce":
        score -= 5
    score = max(0.0, min(100.0, score))
    bias = "bullish" if score >= 60 else "bearish" if score <= 40 else "neutral"
    strength = (
        "strong" if score >= 72 or score <= 28 else "moderate" if score >= 60 or score <= 40 else "weak"
    )

    spark = _spark_closes(closes, 30)
    spark_up = bool(len(closes) >= 2 and closes[-1] >= closes[-min(30, n)])

    return {
        "close": close,
        "change_pct": last.get("change_pct"),
        "up": last.get("up"),
        "volume": int(round(vols[-1])),
        "rvol": round(rvol, 2) if rvol is not None else None,
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "dist_support_pct": round(dist_sup, 2) if dist_sup is not None else None,
        "dist_resistance_pct": round(dist_res, 2) if dist_res is not None else None,
        "near_support": near_support,
        "near_resistance": near_resistance,
        "break_resistance": break_res,
        "break_support": break_sup,
        "range_width_pct": round(range_width, 2) if range_width is not None else None,
        "trend": trend,
        "trend_valid": trend_valid,
        "trend_touches": trend_touches,
        "higher_lows": hl,
        "lower_highs": lh,
        "gap": gap,
        "gap_pct": round(gap_pct, 2) if gap_pct is not None else None,
        "pattern": pattern,
        "fib_levels": {k: round(v, 2) for k, v in fib_levels.items()},
        "fib_nearest": fib_nearest,
        "fib_dist_pct": fib_dist,
        "fib_zone": fib_zone,
        "fib_context": fib_context,
        "candle": candle,
        "candle_quality": candle_quality,
        "setup": setup,
        "score": round(score, 1),
        "bias": bias,
        "strength": strength,
        "spike": bool(break_res and rvol is not None and rvol >= 1.4),
        "spark": spark,
        "spark_up": spark_up,
        "label": last.get("label"),
        "bars_used": n,
        "partial_history": partial,
        "study_window": base,
    }


def _scan_chart_row(preset: dict, tf_id: str) -> dict | None:
    tf = TIMEFRAMES[tf_id]
    bars = _load_bars(
        preset["nse"],
        tf_id,
        exchange=preset.get("exchange") or "NSE",
        fast=True,
    )
    study = _chart_enrich(bars, window=int(tf["avg_window"]))
    if not study:
        return None
    quote = {}
    try:
        quote = _quote_stock(
            preset.get("sc_id") or "",
            nse=preset.get("nse") or preset.get("id") or "",
            exchange=preset.get("exchange") or "NSE",
            fast=True,
        )
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
        quote = {}
    return {
        "id": preset["id"],
        "nse": quote.get("NSEID") or quote.get("BSEID") or preset["nse"],
        "name": quote.get("company") or preset["label"],
        "sc_id": preset["sc_id"],
        "exchange": quote.get("_market") or preset.get("exchange") or "NSE",
        "sector": quote.get("SC_SUBSEC") or quote.get("newSubsector") or "",
        **{k: study.get(k) for k in study if k != "label"},
        "study": study,
        "rank": None,
        "percentile": None,
    }


def _history_to_tf_bars(raw: dict, tf_id: str) -> list[dict]:
    """Normalize a Moneycontrol/Yahoo history payload into TF bars."""
    if not isinstance(raw, dict) or raw.get("s") != "ok":
        return []
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    intraday = tf_id in {"15m", "1h", "4h"}
    bars = _bars_from_history(raw, intraday=intraday)
    if tf.get("aggregate"):
        bars = _aggregate_bars(bars, int(tf["aggregate"]))
    return bars


def _load_exchange_volume_bars(symbol: str, tf_id: str, *, exchange: str, bse_id: str = "") -> list[dict]:
    """OHLCV for one exchange. NSE uses ticker; BSE prefers Moneycontrol BSEID."""
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    ex = (exchange or "NSE").upper()
    # Moneycontrol stock history: NSE symbol vs numeric BSE code yield distinct volumes.
    mc_symbol = (bse_id or "").strip() if ex == "BSE" else (symbol or "").strip()
    if mc_symbol:
        try:
            raw = _history_moneycontrol(mc_symbol, tf, kind="stock")
            bars = _history_to_tf_bars(raw, tf_id)
            if bars:
                return bars
        except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError, json.JSONDecodeError):
            pass
    # Yahoo fallback (.NS / .BO) — some .BO series are sparse.
    try:
        raw = _history_yahoo(symbol, tf_id, kind="stock", exchange=ex)
        return _history_to_tf_bars(raw, tf_id)
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError, KeyError, TypeError):
        return []


def _merge_nse_bse_volume_rows(symbol: str, tf_id: str, sc_id: str = "") -> list[dict]:
    """Daily (or TF) rows with both NSE and BSE traded volume side by side."""
    bse_id = ""
    try:
        meta = _resolve_stock(symbol, sc_id)
        quote = _quote_stock(
            meta.get("sc_id") or sc_id,
            nse=meta.get("nse") or symbol,
            exchange=meta.get("exchange") or "NSE",
        )
        bse_id = str(quote.get("BSEID") or "").strip()
        symbol = (quote.get("NSEID") or meta.get("nse") or symbol or "").strip().upper() or symbol
    except (RuntimeError, URLError, HTTPError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        pass

    nse_bars = _load_exchange_volume_bars(symbol, tf_id, exchange="NSE")
    bse_bars = _load_exchange_volume_bars(symbol, tf_id, exchange="BSE", bse_id=bse_id)

    by_date: dict[str, dict] = {}
    for bar in nse_bars:
        d = bar.get("date") or ""
        if not d:
            continue
        by_date[d] = {
            "date": d,
            "label": bar.get("label") or d,
            "nse_volume": int(bar.get("volume") or 0) or None,
            "bse_volume": None,
            "close": bar.get("close"),
            "change_pct": bar.get("change_pct"),
            "up": bar.get("up"),
            "delivery": None,
        }
    for bar in bse_bars:
        d = bar.get("date") or ""
        if not d:
            continue
        row = by_date.get(d)
        if not row:
            row = {
                "date": d,
                "label": bar.get("label") or d,
                "nse_volume": None,
                "bse_volume": None,
                "close": bar.get("close"),
                "change_pct": bar.get("change_pct"),
                "up": bar.get("up"),
                "delivery": None,
            }
            by_date[d] = row
        row["bse_volume"] = int(bar.get("volume") or 0) or None
        if row.get("close") is None:
            row["close"] = bar.get("close")
            row["change_pct"] = bar.get("change_pct")
            row["up"] = bar.get("up")
    return _enrich_exchange_volume_kpis([by_date[k] for k in sorted(by_date.keys())])


def _enrich_exchange_volume_kpis(rows: list[dict], rvol_window: int = 10) -> list[dict]:
    """Volume-only KPIs: total, AvgN, Δ total/NSE/BSE, RVOL, spike, delivery %."""
    win = max(3, int(rvol_window or 10))
    totals: list[float] = []
    nse_hist: list[float] = []
    bse_hist: list[float] = []
    out: list[dict] = []
    for raw in rows:
        row = dict(raw)
        nse = float(row.get("nse_volume") or 0)
        bse = float(row.get("bse_volume") or 0)
        total = nse + bse
        row["total_volume"] = int(total) if total > 0 else None

        prev_tot = totals[-1] if totals else None
        prev_nse = nse_hist[-1] if nse_hist else None
        prev_bse = bse_hist[-1] if bse_hist else None
        row["vol_chg_pct"] = (
            round(((total - prev_tot) / prev_tot) * 100, 2)
            if total > 0 and prev_tot and prev_tot > 0
            else None
        )
        row["nse_chg_pct"] = (
            round(((nse - prev_nse) / prev_nse) * 100, 2)
            if nse > 0 and prev_nse and prev_nse > 0
            else None
        )
        row["bse_chg_pct"] = (
            round(((bse - prev_bse) / prev_bse) * 100, 2)
            if bse > 0 and prev_bse and prev_bse > 0
            else None
        )

        lookback = [t for t in totals[-win:] if t > 0]
        if lookback:
            avg = sum(lookback) / len(lookback)
            row["avg_volume"] = int(round(avg)) if avg > 0 else None
            row["rvol"] = round(total / avg, 2) if total > 0 and avg > 0 else None
        else:
            row["avg_volume"] = None
            row["rvol"] = None
        row["spike"] = bool(row.get("rvol") is not None and float(row["rvol"]) >= 1.5)

        # NSE ÷ BSE mix (how many times NSE volume vs BSE).
        if nse > 0 and bse > 0:
            row["nse_bse_ratio"] = round(nse / bse, 2)
        else:
            row["nse_bse_ratio"] = None

        delivery = row.get("delivery")
        base = nse if nse > 0 else total
        if delivery is not None and base > 0:
            try:
                row["delivery_pct"] = round((float(delivery) / base) * 100, 1)
            except (TypeError, ValueError):
                row["delivery_pct"] = None
        else:
            row["delivery_pct"] = None

        if total > 0:
            totals.append(total)
        if nse > 0:
            nse_hist.append(nse)
        if bse > 0:
            bse_hist.append(bse)
        out.append(row)
    return out


def build_symbol_dossier(
    symbol: str,
    sc_id: str = "",
    tf_id: str = "1d",
    exchange: str = "NSE",
    indicators: str | list[str] | None = None,
    fresh: bool = False,
) -> dict:
    """Combined Volume + Technical + Lab + Chart readout for one symbol (no Spurts)."""
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    symbol = re.sub(r"[\x00-\x1f<>]", "", symbol or "").strip().upper()
    sc_id = re.sub(r"[\x00-\x1f<>]", "", sc_id or "").strip()
    exchange = (exchange or "NSE").strip().upper() or "NSE"
    if not symbol:
        raise RuntimeError("Symbol required.")
    preset = {
        "id": symbol,
        "nse": symbol,
        "sc_id": sc_id,
        "label": symbol,
        "exchange": exchange,
    }
    cache_key = ("dossier-v7", symbol, sc_id, tf_id, exchange, str(indicators or ""))
    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                return payload

    volume_payload = None
    volume_err = None
    try:
        volume_payload = build_volume(
            symbol=symbol,
            sc_id=sc_id,
            kind="stock",
            tf_id=tf_id,
            fresh=fresh,
        )
    except (RuntimeError, URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
        volume_err = str(exc)

    selected = _parse_tech_indicators(indicators)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_tech = pool.submit(_scan_tech_row, preset, tf_id, selected)
        fut_sci = pool.submit(_scan_sci_row, preset, tf_id)
        fut_chart = pool.submit(_scan_chart_row, preset, tf_id)
        fut_xbars = pool.submit(_merge_nse_bse_volume_rows, symbol, tf_id, sc_id)
        tech = fut_tech.result()
        sci = fut_sci.result()
        chart = fut_chart.result()
        exchange_volume = fut_xbars.result()

    # Attach latest deliverable qty to the most recent row when quote provides it.
    stats = (volume_payload or {}).get("stats") or {}
    delivery_qty = stats.get("delivery_qty")
    if exchange_volume and delivery_qty:
        last = exchange_volume[-1]
        last["delivery"] = int(delivery_qty)
        nse = float(last.get("nse_volume") or 0)
        total = float(last.get("total_volume") or (nse + float(last.get("bse_volume") or 0)))
        base = nse if nse > 0 else total
        if base > 0:
            last["delivery_pct"] = round((float(delivery_qty) / base) * 100, 1)

    sym_meta = (volume_payload or {}).get("symbol") or {}
    name = (
        sym_meta.get("name")
        or (tech or {}).get("name")
        or (sci or {}).get("name")
        or (chart or {}).get("name")
        or symbol
    )
    payload = {
        "as_of": _ist_stamp(),
        "cached": False,
        "session": session_status(),
        "timeframe": tf_id,
        "timeframe_label": tf["label"],
        "tf_meta": _tf_meta(tf_id),
        "desks": ["volume", "tech", "sci", "chart"],
        "symbol": {
            "id": symbol,
            "nse": sym_meta.get("nse") or symbol,
            "name": name,
            "sc_id": sym_meta.get("sc_id") or sc_id,
            "exchange": sym_meta.get("exchange") or exchange,
            "sector": sym_meta.get("sector")
            or (tech or {}).get("sector")
            or (sci or {}).get("sector")
            or "",
        },
        "volume": volume_payload,
        "volume_error": volume_err,
        "exchange_volume": exchange_volume,
        "tech": tech,
        "sci": sci,
        "chart": chart,
    }
    with _cache_lock:
        _cache[cache_key] = (now, payload)
    return payload


def build_chart_board(
    tf_id: str = "1d",
    universe_id: str = "nifty50",
    fresh: bool = False,
) -> dict:
    _ensure_universe_ready()
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    meta = _universe_meta(universe_id)
    universe_id = meta["id"]
    presets = _load_universe(universe_id)
    cache_key = ("chart-board-v2", universe_id, tf_id)
    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                return payload

    errors = 0
    if _universe_is_large(universe_id):
        quote_rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=18) as pool:
            futures = {pool.submit(_scan_quote_row, preset): preset for preset in presets}
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row and row.get("volume", 0) > 0:
                    quote_rows.append(row)
        quote_rows.sort(key=lambda item: item.get("volume") or 0, reverse=True)
        enrich_limit = int(meta.get("enrich_limit") or 200)
        shortlist = quote_rows[:enrich_limit]
        rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {
                pool.submit(
                    _scan_chart_row,
                    {
                        "id": row["id"],
                        "label": row["name"],
                        "sc_id": row["sc_id"],
                        "nse": row["nse"],
                        "exchange": row.get("exchange"),
                    },
                    tf_id,
                ): row
                for row in shortlist
            }
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row:
                    rows.append(row)
        enriched_n = len(rows)
        rows = _merge_quote_remainder(rows, quote_rows)
        universe_note = (
            f"{meta['label']}: quoted {len(quote_rows)}, chart-enriched {enriched_n}"
            f", board {len(rows)}/{_universe_full_size(universe_id)}"
        )
    else:
        rows = []
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {
                pool.submit(_scan_chart_row, preset, tf_id): preset for preset in presets
            }
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row:
                    rows.append(row)
        universe_note = f"{meta['label']} Chart Analysis · {tf['label']} · ChartSchool"

    rows.sort(
        key=lambda item: (
            -(item.get("score") or 0),
            0 if item.get("setup") == "breakout" else 1,
            item.get("nse") or "",
        )
    )
    total = len(rows) or 1
    for idx, row in enumerate(rows):
        row["rank"] = idx + 1
        row["percentile"] = round(100.0 * (total - idx) / total, 1)

    sources = verify_sources()
    payload = {
        "as_of": _ist_stamp(),
        "cached": False,
        "desk": "chart",
        "session": session_status(),
        "timeframe": tf_id,
        "timeframe_label": tf["label"],
        "tf_meta": _tf_meta(tf_id),
        "universe": universe_id,
        "universe_label": meta["label"],
        "universe_size": _universe_full_size(universe_id),
        "universe_scanable": len(presets),
        "scanned": len(rows),
        "errors": errors,
        "formulas": CHART_FORMULAS,
        "studies": list(CHART_STUDIES),
        "chart_sources": CHART_SOURCES,
        "toc": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis",
        "dashboard": {
            "near_support": sum(1 for r in rows if r.get("near_support")),
            "near_resistance": sum(1 for r in rows if r.get("near_resistance")),
            "breakout": sum(1 for r in rows if r.get("break_resistance")),
            "breakdown": sum(1 for r in rows if r.get("break_support")),
            "trend_up": sum(1 for r in rows if r.get("trend") == "up"),
            "trend_down": sum(1 for r in rows if r.get("trend") == "down"),
            "gaps": sum(1 for r in rows if r.get("gap") and r.get("gap") != "none"),
            "patterns": sum(1 for r in rows if r.get("pattern") and r.get("pattern") != "none"),
            "fib_zone": sum(1 for r in rows if r.get("fib_zone")),
            "candles": sum(1 for r in rows if r.get("candle") and r.get("candle") != "none"),
        },
        "source": {
            "name": sources.get("plot_source") or "Moneycontrol / Yahoo",
            "verified": bool(sources.get("ready")),
            "note": universe_note
            + " · StockCharts ChartSchool Chart Analysis",
        },
        "sources": sources.get("sources", []),
        "counts": {
            "all": len(rows),
            "bullish": sum(1 for row in rows if row.get("bias") == "bullish"),
            "bearish": sum(1 for row in rows if row.get("bias") == "bearish"),
            "neutral": sum(1 for row in rows if row.get("bias") == "neutral"),
            "spike": sum(1 for row in rows if row.get("spike")),
            "up": sum(1 for row in rows if row.get("up")),
            "down": sum(1 for row in rows if not row.get("up")),
        },
        "rows": rows,
    }
    with _cache_lock:
        _cache[cache_key] = (now, payload)
    return payload


# --- Spurts Desk: live NSE / BSE volume gainers --------------------------------
# NSE: https://www.nseindia.com/market-data/volume-gainers-spurts
#      API live-analysis-volume-gainers
# BSE: https://www.bseindia.com/markets/equity/eqreports/missprtvol
#      API SpurtvolumeNew (needs browser-like TLS; curl_cffi recommended)

SPURT_FORMULAS = {
    "nse": (
        "NSE Volume Gainers — today's volume vs 1-week & 2-week average volume "
        "(nseindia.com/market-data/volume-gainers-spurts)"
    ),
    "bse": (
        "BSE Spurt in Volume — today's volume (Lacs) vs 2-week average, "
        "volume change in times (bseindia.com …/missprtvol)"
    ),
    "vol_x": "Vol× = today volume ÷ reference average volume (NSE week-1 avg / BSE 2-wk avg)",
    "rank": "Rank 1 = highest Vol× within the selected exchange tab",
    "score": "Score = clamp(log-scaled Vol× + price confirmation, −100…+100)",
    "history": (
        "After cash close (15:30 IST), the live NSE+BSE list is written to "
        "data/spurts_history/YYYY-MM-DD.json and kept for 30 calendar days"
    ),
    "reappear": (
        "Reappeared = same symbol on ≥2 distinct archive days in the rolling 30-day window "
        "(unusual volume that keeps returning)"
    ),
}

# Why keep historical spurts (research citations for the dashboard):
SPURT_HISTORY_PURPOSE = [
    {
        "id": "nse_list",
        "title": "Exchange unusual-volume screen",
        "ref": "NSE Volume Gainers / BSE Spurt-in-Volume — official unusual activity lists",
        "url": "https://www.nseindia.com/market-data/volume-gainers-spurts",
        "note": "Live pages are session snapshots; a local archive turns them into a research series.",
    },
    {
        "id": "volume_continuation",
        "title": "High-volume moves tend to continue",
        "ref": (
            "Parthasarathy (2019), Review of Behavioral Finance — large one-day price "
            "changes with high volume show short-horizon continuation in Indian equities"
        ),
        "url": "https://doi.org/10.1108/RBF-06-2018-0058",
        "note": "Reappearances + high Vol× flag names where volume shock may persist.",
    },
    {
        "id": "return_volume",
        "title": "Volume often leads returns",
        "ref": (
            "Mishra & Tripathy — return–volume study (Indian market): evidence of volume "
            "causing returns more than the reverse"
        ),
        "url": "https://econwpa.ub.uni-muenchen.de/econ-wp/fin/papers/0504/0504013.pdf",
        "note": "Tracking which names keep spiking helps separate one-off noise from persistent flow.",
    },
]

SPURTS_HISTORY_DIR = DATA_DIR / "spurts_history"
SPURTS_HISTORY_DAYS = 30

_spurt_cache: dict[str, tuple[float, dict]] = {}
_spurt_lock = threading.Lock()
# Spurts live list also held until Refresh / Clear cache (not a short TTL).
SPURT_TTL = 10**9


def clear_runtime_caches() -> dict:
    """Drop all in-process board / spurts / probe caches (global Clear cache)."""
    global _probe_cache
    board_n = 0
    spurt_n = 0
    with _cache_lock:
        board_n = len(_cache)
        _cache.clear()
    with _spurt_lock:
        spurt_n = len(_spurt_cache)
        _spurt_cache.clear()
    _probe_cache = None
    return {
        "ok": True,
        "as_of": _ist_stamp(),
        "cleared": {"boards": board_n, "spurts": spurt_n, "probe": True},
    }


def _spurts_today() -> str:
    return _now().astimezone(IST).strftime("%Y-%m-%d")


def _spurts_history_ensure() -> Path:
    SPURTS_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return SPURTS_HISTORY_DIR


def _spurts_archive_path(date_str: str) -> Path:
    return _spurts_history_ensure() / f"{date_str}.json"


def _spurts_row_slim(row: dict) -> dict:
    keys = (
        "exchange",
        "id",
        "nse",
        "scrip",
        "name",
        "volume",
        "avg_volume",
        "avg_volume_2w",
        "vol_x",
        "vol_x_2w",
        "ltp",
        "change_pct",
        "turnover",
        "turnover_unit",
        "score",
        "bias",
        "strength",
        "up",
        "rank",
        "percentile",
    )
    return {k: row[k] for k in keys if k in row and row[k] is not None}


def _spurts_prune_archives(keep_days: int = SPURTS_HISTORY_DAYS) -> int:
    """Delete flat files older than keep_days. Returns removed count."""
    root = _spurts_history_ensure()
    cutoff = (_now().astimezone(IST).date() - timedelta(days=max(1, keep_days))).isoformat()
    removed = 0
    for path in root.glob("????-??-??.json"):
        if path.stem < cutoff:
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def list_spurts_archives(limit: int = SPURTS_HISTORY_DAYS) -> list[dict]:
    root = _spurts_history_ensure()
    out: list[dict] = []
    for path in sorted(root.glob("????-??-??.json"), reverse=True):
        try:
            with path.open(encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        rows = payload.get("rows") or []
        out.append(
            {
                "date": path.stem,
                "as_of": payload.get("as_of"),
                "count": len(rows),
                "nse": sum(1 for r in rows if r.get("exchange") == "NSE"),
                "bse": sum(1 for r in rows if r.get("exchange") == "BSE"),
                "path": str(path.relative_to(ROOT)),
            }
        )
        if len(out) >= limit:
            break
    return out


def load_spurts_archive(date_str: str) -> dict | None:
    """Load one day's flat-file snapshot as a board-shaped payload."""
    raw = str(date_str or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return None
    path = _spurts_archive_path(raw)
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    rows = list(payload.get("rows") or [])
    rows = _rank_spurt_rows(rows)
    session = session_status()
    return {
        "as_of": payload.get("as_of") or raw,
        "cached": False,
        "desk": "spurts",
        "history": True,
        "history_date": raw,
        "history_path": str(path.relative_to(ROOT)),
        "session": session,
        "exchange": "all",
        "universe": "live",
        "universe_label": f"Archive · {raw}",
        "universe_size": len(rows),
        "universe_scanable": len(rows),
        "formulas": SPURT_FORMULAS,
        "feeds": payload.get("feeds") or [],
        "errors": [],
        "scanned": len(rows),
        "raw_scanned": len(rows),
        "live_quotes": 0,
        "feed_as_of": payload.get("feed_as_of") or {},
        "counts": {
            "all": len(rows),
            "nse": sum(1 for row in rows if row.get("exchange") == "NSE"),
            "bse": sum(1 for row in rows if row.get("exchange") == "BSE"),
            "bullish": sum(1 for row in rows if row.get("bias") == "bullish"),
            "bearish": sum(1 for row in rows if row.get("bias") == "bearish"),
            "neutral": sum(1 for row in rows if row.get("bias") == "neutral"),
            "spike": sum(1 for row in rows if (row.get("vol_x") or 0) >= 3),
            "up": sum(1 for row in rows if row.get("up")),
            "down": sum(1 for row in rows if not row.get("up")),
            "live": 0,
        },
        "source": {
            "name": f"Spurts archive · {raw}",
            "verified": True,
            "note": f"Flat file {path.relative_to(ROOT)} · EOD snapshot (no live LTP overlay)",
        },
        "links": {
            "nse": "https://www.nseindia.com/market-data/volume-gainers-spurts",
            "bse": "https://www.bseindia.com/markets/equity/eqreports/missprtvol",
        },
        "archives": list_spurts_archives(),
        "rows": rows,
    }


def save_spurts_archive(
    rows: list[dict],
    *,
    feeds: list[dict] | None = None,
    feed_as_of: dict | None = None,
    force: bool = False,
) -> dict:
    """Persist today's spurts list after session close. Keeps ≤30 days of flat files."""
    session = session_status()
    today = _spurts_today()
    path = _spurts_archive_path(today)
    if session.get("state") == "open" and not force:
        return {
            "ok": False,
            "saved": False,
            "reason": "market_open",
            "date": today,
            "detail": "Archive waits until after 15:30 IST cash close",
        }
    if not rows:
        return {"ok": False, "saved": False, "reason": "empty", "date": today}
    if path.is_file() and not force:
        try:
            with path.open(encoding="utf-8") as fh:
                existing = json.load(fh)
            if len(existing.get("rows") or []) >= len(rows):
                _spurts_prune_archives()
                return {
                    "ok": True,
                    "saved": False,
                    "reason": "already_archived",
                    "date": today,
                    "path": str(path.relative_to(ROOT)),
                    "count": len(existing.get("rows") or []),
                }
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    slim = [_spurts_row_slim(r) for r in rows]
    payload = {
        "date": today,
        "as_of": _ist_stamp(),
        "session_state": session.get("state"),
        "feeds": feeds or [],
        "feed_as_of": feed_as_of or {},
        "count": len(slim),
        "rows": slim,
    }
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=0)
    tmp.replace(path)
    removed = _spurts_prune_archives()
    return {
        "ok": True,
        "saved": True,
        "date": today,
        "path": str(path.relative_to(ROOT)),
        "count": len(slim),
        "pruned": removed,
    }


def build_spurts_dashboard(days: int = SPURTS_HISTORY_DAYS) -> dict:
    """30-day analytics: reappearances, day counts, cited research purpose."""
    days = max(1, min(int(days or SPURTS_HISTORY_DAYS), SPURTS_HISTORY_DAYS))
    archives = list_spurts_archives(limit=days)
    # Load oldest→newest for series
    by_date: list[tuple[str, list[dict]]] = []
    for item in reversed(archives):
        path = _spurts_archive_path(item["date"])
        try:
            with path.open(encoding="utf-8") as fh:
                payload = json.load(fh)
            by_date.append((item["date"], list(payload.get("rows") or [])))
        except (OSError, ValueError, json.JSONDecodeError):
            continue

    # symbol key → appearances
    appearances: dict[str, dict] = {}
    daily_series: list[dict] = []
    for date_str, rows in by_date:
        daily_series.append(
            {
                "date": date_str,
                "count": len(rows),
                "nse": sum(1 for r in rows if r.get("exchange") == "NSE"),
                "bse": sum(1 for r in rows if r.get("exchange") == "BSE"),
                "spike": sum(1 for r in rows if (r.get("vol_x") or 0) >= 3),
            }
        )
        seen_today: set[str] = set()
        for row in rows:
            sym = str(row.get("nse") or row.get("id") or "").strip().upper()
            if not sym or sym in seen_today:
                continue
            seen_today.add(sym)
            slot = appearances.setdefault(
                sym,
                {
                    "id": sym,
                    "nse": sym,
                    "name": row.get("name") or sym,
                    "exchange": row.get("exchange") or "",
                    "days": 0,
                    "dates": [],
                    "vol_x_max": None,
                    "vol_x_sum": 0.0,
                    "vol_x_n": 0,
                    "last_change_pct": None,
                    "last_vol_x": None,
                    "last_date": None,
                },
            )
            slot["days"] += 1
            slot["dates"].append(date_str)
            slot["name"] = row.get("name") or slot["name"]
            slot["exchange"] = row.get("exchange") or slot["exchange"]
            vx = _num(row.get("vol_x"))
            if vx is not None:
                slot["vol_x_max"] = vx if slot["vol_x_max"] is None else max(slot["vol_x_max"], vx)
                slot["vol_x_sum"] += vx
                slot["vol_x_n"] += 1
                slot["last_vol_x"] = vx
            slot["last_change_pct"] = row.get("change_pct")
            slot["last_date"] = date_str

    reappear = []
    for slot in appearances.values():
        if slot["days"] < 2:
            continue
        avg = (slot["vol_x_sum"] / slot["vol_x_n"]) if slot["vol_x_n"] else None
        reappear.append(
            {
                "id": slot["id"],
                "nse": slot["nse"],
                "name": slot["name"],
                "exchange": slot["exchange"],
                "days": slot["days"],
                "dates": slot["dates"],
                "vol_x_max": round(slot["vol_x_max"], 2) if slot["vol_x_max"] is not None else None,
                "vol_x_avg": round(avg, 2) if avg is not None else None,
                "last_vol_x": slot["last_vol_x"],
                "last_change_pct": slot["last_change_pct"],
                "last_date": slot["last_date"],
            }
        )
    reappear.sort(key=lambda r: (-r["days"], -(r.get("vol_x_max") or 0), r["id"]))

    unique_n = len(appearances)
    once_n = sum(1 for s in appearances.values() if s["days"] == 1)
    return {
        "as_of": _ist_stamp(),
        "desk": "spurts",
        "window_days": days,
        "history_dir": str(SPURTS_HISTORY_DIR.relative_to(ROOT)),
        "archives": archives,
        "days_covered": len(by_date),
        "daily": daily_series,
        "dashboard": {
            "days_covered": len(by_date),
            "unique_names": unique_n,
            "once_only": once_n,
            "reappeared": len(reappear),
            "reappear_pct": round(100.0 * len(reappear) / unique_n, 1) if unique_n else 0.0,
            "avg_names_per_day": (
                round(sum(d["count"] for d in daily_series) / len(daily_series), 1)
                if daily_series
                else 0.0
            ),
            "total_listings": sum(d["count"] for d in daily_series),
        },
        "reappeared": reappear[:40],
        "purpose": SPURT_HISTORY_PURPOSE,
        "formulas": {
            k: SPURT_FORMULAS[k] for k in ("history", "reappear", "vol_x", "nse", "bse") if k in SPURT_FORMULAS
        },
        "note": (
            "Archives write automatically after 15:30 IST when the Spurts desk refreshes. "
            f"Flat files live under {SPURTS_HISTORY_DIR.relative_to(ROOT)}/ (≤{SPURTS_HISTORY_DAYS} days)."
        ),
    }


def _curl_session():
    """Browser-like HTTPS session (required for BSE Akamai)."""
    try:
        from curl_cffi import requests as creq  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Install curl_cffi for live NSE/BSE spurts: pip3 install curl_cffi"
        ) from exc
    return creq.Session()


def _spurt_get_json(session, url: str, headers: dict, timeout: float = 30) -> dict | list:
    response = session.get(url, headers=headers, impersonate="chrome131", timeout=timeout)
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code} for {url}")
    return response.json()


def _fetch_nse_spurts() -> tuple[list[dict], dict]:
    session = _curl_session()
    home = "https://www.nseindia.com/"
    page = "https://www.nseindia.com/market-data/volume-gainers-spurts"
    api = "https://www.nseindia.com/api/live-analysis-volume-gainers"
    base_headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    session.get(home, headers=base_headers, impersonate="chrome131", timeout=30)
    session.get(
        page,
        headers={**base_headers, "Referer": home},
        impersonate="chrome131",
        timeout=30,
    )
    payload = _spurt_get_json(
        session,
        api,
        {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": page,
        },
    )
    rows_in = payload.get("data") if isinstance(payload, dict) else payload
    rows: list[dict] = []
    for item in rows_in or []:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        volume = _num(item.get("volume"))
        avg1 = _num(item.get("week1AvgVolume"))
        avg2 = _num(item.get("week2AvgVolume"))
        vol_x = _num(item.get("week1volChange"))
        if vol_x is None and volume and avg1:
            vol_x = volume / avg1
        ltp = _num(item.get("ltp"))
        change_pct = _num(item.get("pChange"))
        turnover = _num(item.get("turnover"))
        score = _spurt_score(vol_x, change_pct)
        rows.append(
            {
                "exchange": "NSE",
                "id": symbol,
                "nse": symbol,
                "scrip": None,
                "name": item.get("companyName") or symbol,
                "volume": int(volume) if volume is not None else None,
                "avg_volume": int(avg1) if avg1 is not None else None,
                "avg_volume_2w": int(avg2) if avg2 is not None else None,
                "vol_x": round(vol_x, 2) if vol_x is not None else None,
                "vol_x_2w": round(_num(item.get("week2volChange")) or 0, 2)
                if item.get("week2volChange") is not None
                else None,
                "ltp": ltp,
                "change_pct": change_pct,
                "turnover": turnover,
                "turnover_unit": "₹ Lakh",
                "score": score,
                "bias": _bias_from_score(score),
                "strength": (
                    "strong"
                    if abs(score) >= 60
                    else "moderate"
                    if abs(score) >= 30
                    else "weak"
                ),
                "source_url": page,
                "up": bool(change_pct is not None and change_pct >= 0),
            }
        )
    meta = {
        "ok": True,
        "name": "NSE",
        "count": len(rows),
        "url": page,
        "api": api,
        "as_of": (payload.get("timestamp") if isinstance(payload, dict) else None),
    }
    return rows, meta


def _parse_bse_spurt_item(item: dict, page: str, settlement: str) -> dict | None:
    scrip = str(item.get("scrip_cd") or item.get("SCRIP_CD") or "").strip()
    symbol = str(item.get("scripname") or item.get("ScripName") or "").strip().upper()
    if not scrip and not symbol:
        return None
    # BSE publishes volume in Lacs on this report.
    vol_lacs = _num(item.get("Trd_vol") or item.get("trd_vol"))
    avg_lacs = _num(item.get("wkavgqty") or item.get("WkAvgQty"))
    volume = int(round(vol_lacs * 100000)) if vol_lacs is not None else None
    avg_volume = int(round(avg_lacs * 100000)) if avg_lacs is not None else None
    vol_x = _num(item.get("volumechangetimes") or item.get("VolumeChangeTimes"))
    if vol_x is None and vol_lacs and avg_lacs:
        vol_x = vol_lacs / avg_lacs
    ltp = _num(item.get("Ltradert") or item.get("ltradert"))
    change_pct = _num(item.get("change_percent") or item.get("CHANGE_PERCENT"))
    turnover_cr = _num(item.get("TurnOver") or item.get("turnover"))
    score = _spurt_score(vol_x, change_pct)
    return {
        "exchange": "BSE",
        "id": symbol or scrip,
        "nse": symbol or None,
        "scrip": scrip or None,
        "name": item.get("long_name") or symbol or scrip,
        "volume": volume,
        "avg_volume": avg_volume,
        "avg_volume_2w": avg_volume,
        "vol_x": round(vol_x, 2) if vol_x is not None else None,
        "vol_x_2w": None,
        "ltp": ltp,
        "change_pct": change_pct,
        "turnover": turnover_cr,
        "turnover_unit": "₹ Cr",
        "score": score,
        "bias": _bias_from_score(score),
        "strength": (
            "strong"
            if abs(score) >= 60
            else "moderate"
            if abs(score) >= 30
            else "weak"
        ),
        "source_url": item.get("NSURL") or page,
        "up": bool(change_pct is not None and change_pct >= 0),
        "settlement": settlement,
    }


def _fetch_bse_spurts() -> tuple[list[dict], dict]:
    session = _curl_session()
    page = "https://www.bseindia.com/markets/equity/eqreports/missprtvol"
    # flag 1 = Equity T+1 (default on site), flag 0 = Equity T+0 when published
    api_base = "https://api.bseindia.com/BseIndiaAPI/api/SpurtvolumeNew/w?flag="
    base_headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    session.get(
        "https://www.bseindia.com/",
        headers=base_headers,
        impersonate="chrome131",
        timeout=30,
    )
    session.get(
        page,
        headers={**base_headers, "Referer": "https://www.bseindia.com/"},
        impersonate="chrome131",
        timeout=30,
    )
    api_headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.bseindia.com",
        "Referer": page,
    }
    by_key: dict[str, dict] = {}
    fetched_flags: list[str] = []
    for flag, settlement in (("1", "T+1"), ("0", "T+0")):
        try:
            payload = _spurt_get_json(session, api_base + flag, api_headers)
        except Exception:
            continue
        rows_in = (
            payload
            if isinstance(payload, list)
            else payload.get("Table") or payload.get("data") or []
        )
        if not rows_in:
            continue
        fetched_flags.append(f"{flag}:{settlement}:{len(rows_in)}")
        for item in rows_in:
            if not isinstance(item, dict):
                continue
            row = _parse_bse_spurt_item(item, page, settlement)
            if not row:
                continue
            key = row.get("scrip") or row.get("nse") or row["id"]
            prev = by_key.get(key)
            # Keep the stronger volume multiple if the same scrip appears in both.
            if prev is None or (row.get("vol_x") or 0) > (prev.get("vol_x") or 0):
                by_key[key] = row
    rows = list(by_key.values())
    if not rows and not fetched_flags:
        raise RuntimeError("BSE SpurtvolumeNew returned no rows")
    meta = {
        "ok": True,
        "name": "BSE",
        "count": len(rows),
        "url": page,
        "api": api_base + "0|1",
        "as_of": None,
        "detail": "flags " + (", ".join(fetched_flags) if fetched_flags else "empty"),
    }
    return rows, meta


def _spurt_score(vol_x: float | None, change_pct: float | None) -> float:
    """Map volume multiple + price move into −100…+100 for ranking context."""
    if vol_x is None or vol_x <= 0:
        base = 0.0
    else:
        # 1× → ~0, 3× → ~35, 10× → ~70, 50×+ → ~100
        base = max(0.0, min(100.0, (math.log10(vol_x) / math.log10(50.0)) * 100.0))
    if change_pct is None:
        signed = base * 0.85
    elif change_pct >= 0:
        signed = base + min(15.0, change_pct)
    else:
        # Volume spurt on a down day still ranks high on vol, but softens score.
        signed = base * 0.55 + max(-25.0, change_pct)
    return round(max(-100.0, min(100.0, signed)), 1)


def _rank_spurt_rows(rows: list[dict]) -> list[dict]:
    rows.sort(
        key=lambda item: (
            -(item.get("vol_x") or 0),
            -(item.get("score") or 0),
            item.get("nse") or item.get("id") or "",
        )
    )
    total = len(rows) or 1
    for idx, row in enumerate(rows):
        row["rank"] = idx + 1
        row["percentile"] = round(100.0 * (total - idx) / total, 1)
    return rows


def _enrich_one_spurt_live(row: dict) -> dict:
    """Overlay live LTP / %chg / session volume from Yahoo on exchange spurt row."""
    sym = str(row.get("nse") or row.get("id") or "").strip().upper()
    if not sym:
        return row
    exchange = row.get("exchange") or "NSE"
    quote = _quote_yahoo(sym, exchange=exchange)
    if not quote:
        row["live"] = False
        return row
    live_ltp = _num(quote.get("pricecurrent"))
    live_chg = _num(quote.get("pricepercentchange"))
    live_vol = _num(quote.get("VOL"))
    row["exchange_ltp"] = row.get("ltp")
    row["exchange_change_pct"] = row.get("change_pct")
    row["exchange_volume"] = row.get("volume")
    if live_ltp is not None:
        row["ltp"] = live_ltp
    if live_chg is not None:
        row["change_pct"] = live_chg
        row["up"] = live_chg >= 0
    if live_vol is not None and live_vol > 0:
        row["live_volume"] = int(live_vol)
        # Prefer live session volume for display; keep exchange vol for vol_x basis.
        row["volume"] = int(live_vol)
        avg = _num(row.get("avg_volume"))
        if avg and avg > 0:
            row["vol_x"] = round(live_vol / avg, 2)
            row["score"] = _spurt_score(row["vol_x"], live_chg)
            row["bias"] = _bias_from_score(row["score"])
            row["strength"] = (
                "strong"
                if abs(row["score"]) >= 60
                else "moderate"
                if abs(row["score"]) >= 30
                else "weak"
            )
    row["live"] = True
    row["quote_source"] = "yahoo"
    return row


def _enrich_spurts_live(rows: list[dict]) -> tuple[list[dict], dict]:
    """Refresh LTP/volume for spurts list so the desk stays live after exchange EOD stamp."""
    if not rows:
        return rows, {"ok": False, "enriched": 0}
    out: list[dict] = []
    ok_n = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_enrich_one_spurt_live, dict(row)): row for row in rows}
        for future in as_completed(futures):
            try:
                row = future.result()
            except Exception:  # noqa: BLE001
                row = dict(futures[future])
                row["live"] = False
            if row.get("live"):
                ok_n += 1
            out.append(row)
    meta = {
        "ok": ok_n > 0,
        "name": "Live quotes",
        "count": ok_n,
        "detail": f"Yahoo LTP/volume on {ok_n}/{len(rows)} spurts",
        "as_of": _ist_stamp(),
    }
    return out, meta


def _filter_spurts_by_universe(rows: list[dict], universe_id: str) -> tuple[list[dict], dict]:
    """Keep spurts that belong to the shared NSE/BSE universe dimension.

    `live` = full official NSE Volume Gainers + BSE Spurt-in-Volume (no index cut).
    """
    meta = _universe_meta(universe_id)
    uid = meta["id"]
    if uid == "live":
        meta = {
            **meta,
            "count": len(rows),
            "label": "Live Spurts (NSE+BSE)",
        }
        return list(rows), meta
    if uid in {"nse_all", "all"}:
        return [row for row in rows if row.get("exchange") == "NSE"], meta
    if uid == "bse_all":
        return [row for row in rows if row.get("exchange") == "BSE"], meta

    # Membership uses full exchange list (not only sc_id-mapped names).
    if get_universe_rows is not None:
        try:
            presets = get_universe_rows(uid, require_sc_id=False)
        except (OSError, ValueError, RuntimeError, TypeError):
            presets = _load_universe(uid)
    else:
        presets = _load_universe(uid)
    nse_syms = {
        str(item.get("nse") or item.get("id") or "").strip().upper()
        for item in presets
        if item.get("nse") or item.get("id")
    }
    bse_codes = {
        str(item.get("bse") or "").strip()
        for item in presets
        if item.get("bse")
    }
    filtered: list[dict] = []
    for row in rows:
        sym = str(row.get("nse") or row.get("id") or "").strip().upper()
        scrip = str(row.get("scrip") or "").strip()
        if sym and sym in nse_syms:
            filtered.append(row)
        elif scrip and scrip in bse_codes:
            filtered.append(row)
    return filtered, meta


def build_spurts_board(
    fresh: bool = False,
    exchange: str = "all",
    universe_id: str = "live",
    date: str | None = None,
) -> dict:
    _ensure_universe_ready()
    # Historical flat-file view (any past day, or today once archived).
    hist_date = str(date or "").strip().lower()
    if hist_date and hist_date not in {"live", "today", ""}:
        if hist_date == "today":
            hist_date = _spurts_today()
        archived = load_spurts_archive(hist_date)
        if archived:
            return archived
        # Fall through to live only when requesting today's missing archive.
        if hist_date != _spurts_today():
            raise ValueError(f"No spurts archive for {hist_date}")

    exchange = (exchange or "all").strip().lower()
    if exchange not in {"all", "nse", "bse"}:
        exchange = "all"
    meta = _universe_meta(universe_id)
    universe_id = meta["id"]
    # Align exchange shortcut with large books when caller didn't specify.
    if universe_id == "live":
        exchange = "all"
    elif universe_id in {"nse_all", "all"} and exchange == "all":
        exchange = "nse"
    elif universe_id == "bse_all" and exchange == "all":
        exchange = "bse"

    cache_key = f"spurts:{exchange}:{universe_id}"
    now = time.time()
    if not fresh:
        with _spurt_lock:
            cached = _spurt_cache.get(cache_key)
            if cached and now - cached[0] < SPURT_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                payload["archives"] = list_spurts_archives()
                # Still try EOD archive on cache hits after close.
                if payload.get("rows") and session_status().get("state") != "open":
                    payload["archive"] = save_spurts_archive(
                        payload["rows"],
                        feeds=payload.get("feeds"),
                        feed_as_of=payload.get("feed_as_of"),
                    )
                return payload

    feeds: list[dict] = []
    rows: list[dict] = []
    errors: list[str] = []

    want_nse = exchange in {"all", "nse"}
    want_bse = exchange in {"all", "bse"}

    if want_nse:
        try:
            nse_rows, nse_meta = _fetch_nse_spurts()
            rows.extend(nse_rows)
            feeds.append(nse_meta)
        except Exception as exc:  # noqa: BLE001 — surface feed errors in UI
            errors.append(f"NSE: {exc}")
            feeds.append(
                {
                    "ok": False,
                    "name": "NSE",
                    "count": 0,
                    "url": "https://www.nseindia.com/market-data/volume-gainers-spurts",
                    "error": str(exc),
                }
            )

    if want_bse:
        try:
            bse_rows, bse_meta = _fetch_bse_spurts()
            rows.extend(bse_rows)
            feeds.append(bse_meta)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"BSE: {exc}")
            feeds.append(
                {
                    "ok": False,
                    "name": "BSE",
                    "count": 0,
                    "url": "https://www.bseindia.com/markets/equity/eqreports/missprtvol",
                    "error": str(exc),
                }
            )

    raw_count = len(rows)
    rows, meta = _filter_spurts_by_universe(rows, universe_id)
    # Exchange spurts lists often stamp at session close; overlay live quotes.
    rows, live_meta = _enrich_spurts_live(rows)
    feeds.append(live_meta)
    rows = _rank_spurt_rows(rows)
    nse_asof = next((f.get("as_of") for f in feeds if f.get("name") == "NSE" and f.get("as_of")), None)
    bse_asof = next((f.get("as_of") for f in feeds if f.get("name") == "BSE" and f.get("as_of")), None)
    live_asof = live_meta.get("as_of")
    session = session_status()
    list_note = "exchange spurts list"
    if session.get("state") != "open" and nse_asof:
        list_note = f"exchange spurts list frozen at {nse_asof} (session closed)"
    payload = {
        "as_of": _ist_stamp(),
        "cached": False,
        "desk": "spurts",
        "session": session,
        "exchange": exchange,
        "universe": universe_id,
        "universe_label": meta.get("label") or universe_id,
        "universe_size": _universe_full_size(universe_id),
        # Never call _load_universe("live") — that remaps to nse_all.
        "universe_scanable": (
            len(rows)
            if universe_id == "live"
            else (meta.get("scanable") or meta.get("count") or len(_load_universe(universe_id)))
        ),
        "formulas": SPURT_FORMULAS,
        "feeds": feeds,
        "errors": errors,
        "scanned": len(rows),
        "raw_scanned": raw_count,
        "live_quotes": live_meta.get("count") or 0,
        "feed_as_of": {
            "nse": nse_asof,
            "bse": bse_asof,
            "quotes": live_asof,
        },
        "counts": {
            "all": len(rows),
            "nse": sum(1 for row in rows if row.get("exchange") == "NSE"),
            "bse": sum(1 for row in rows if row.get("exchange") == "BSE"),
            "bullish": sum(1 for row in rows if row.get("bias") == "bullish"),
            "bearish": sum(1 for row in rows if row.get("bias") == "bearish"),
            "neutral": sum(1 for row in rows if row.get("bias") == "neutral"),
            "spike": sum(1 for row in rows if (row.get("vol_x") or 0) >= 3),
            "up": sum(1 for row in rows if row.get("up")),
            "down": sum(1 for row in rows if not row.get("up")),
            "live": sum(1 for row in rows if row.get("live")),
        },
        "source": {
            "name": "NSE + BSE spurts · live Yahoo LTP",
            "verified": any(feed.get("ok") for feed in feeds),
            "note": (
                f"{list_note} · live LTP/volume on {live_meta.get('count') or 0}/{len(rows)}"
                f" · {meta.get('label') or universe_id}"
            ),
        },
        "links": {
            "nse": "https://www.nseindia.com/market-data/volume-gainers-spurts",
            "bse": "https://www.bseindia.com/markets/equity/eqreports/missprtvol",
        },
        "history": False,
        "history_date": None,
        "archives": list_spurts_archives(),
        "rows": rows,
    }
    # After cash close, persist today's list to data/spurts_history/ (≤30 days).
    if rows and session.get("state") != "open" and universe_id == "live":
        payload["archive"] = save_spurts_archive(
            rows,
            feeds=feeds,
            feed_as_of=payload.get("feed_as_of"),
        )
        payload["archives"] = list_spurts_archives()
    with _spurt_lock:
        _spurt_cache[cache_key] = (now, payload)
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "SignalDesk/1.3"

    def log_message(self, fmt: str, *args) -> None:
        if args and str(args[1]).startswith("4"):
            super().log_message(fmt, *args)

    def handle_one_request(self) -> None:
        """Ignore client disconnects mid-response (BrokenPipe / reset)."""
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        try:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Browser navigated away / cancelled while we were writing.
            return

    def _json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload).encode()
        self._send(code, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if parsed.path == "/api/sources":
            self._json(verify_sources(fresh=(params.get("fresh") or ["0"])[0] == "1"))
            return
        if parsed.path == "/api/cache/clear":
            self._json(clear_runtime_caches())
            return
        if parsed.path == "/api/search":
            query = (params.get("q") or [""])[0]
            try:
                self._json({"query": query, "results": search_symbols(query)})
            except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
                self._json({"error": str(exc)}, code=502)
            return
        if parsed.path == "/api/board":
            try:
                self._json(
                    build_board(
                        tf_id=(params.get("tf") or params.get("timeframe") or ["1d"])[0],
                        universe_id=(params.get("universe") or ["nifty50"])[0],
                        fresh=(params.get("fresh") or ["0"])[0] == "1",
                    )
                )
            except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
                self._json({"error": f"Upstream failed: {exc}"}, code=502)
            return
        if parsed.path == "/api/tech-board":
            try:
                self._json(
                    build_tech_board(
                        tf_id=(params.get("tf") or params.get("timeframe") or ["1d"])[0],
                        universe_id=(params.get("universe") or ["nifty50"])[0],
                        fresh=(params.get("fresh") or ["0"])[0] == "1",
                        indicators=(params.get("indicators") or [None])[0],
                    )
                )
            except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
                self._json({"error": f"Upstream failed: {exc}"}, code=502)
            return
        if parsed.path == "/api/sci-board":
            try:
                self._json(
                    build_sci_board(
                        tf_id=(params.get("tf") or params.get("timeframe") or ["1d"])[0],
                        universe_id=(params.get("universe") or ["nifty50"])[0],
                        fresh=(params.get("fresh") or ["0"])[0] == "1",
                    )
                )
            except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
                self._json({"error": f"Upstream failed: {exc}"}, code=502)
            return
        if parsed.path == "/api/chart-board":
            try:
                self._json(
                    build_chart_board(
                        tf_id=(params.get("tf") or params.get("timeframe") or ["1d"])[0],
                        universe_id=(params.get("universe") or ["nifty50"])[0],
                        fresh=(params.get("fresh") or ["0"])[0] == "1",
                    )
                )
            except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
                self._json({"error": f"Upstream failed: {exc}"}, code=502)
            return
        if parsed.path == "/api/spurts/history":
            self._json(
                {
                    "as_of": _ist_stamp(),
                    "history_dir": str(SPURTS_HISTORY_DIR.relative_to(ROOT)),
                    "keep_days": SPURTS_HISTORY_DAYS,
                    "archives": list_spurts_archives(),
                    "today": _spurts_today(),
                    "session": session_status(),
                }
            )
            return
        if parsed.path == "/api/spurts/dashboard":
            try:
                days_raw = (params.get("days") or [str(SPURTS_HISTORY_DAYS)])[0]
                self._json(build_spurts_dashboard(days=int(days_raw)))
            except (TypeError, ValueError) as exc:
                self._json({"error": str(exc)}, code=400)
            return
        if parsed.path == "/api/spurts/archive":
            # Force-write today's snapshot (also used for testing before close).
            try:
                board = build_spurts_board(
                    fresh=True,
                    exchange="all",
                    universe_id="live",
                )
                result = save_spurts_archive(
                    board.get("rows") or [],
                    feeds=board.get("feeds"),
                    feed_as_of=board.get("feed_as_of"),
                    force=(params.get("force") or ["0"])[0] == "1",
                )
                self._json({**result, "archives": list_spurts_archives()})
            except RuntimeError as exc:
                self._json({"error": str(exc)}, code=503)
            except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
                self._json({"error": f"Upstream failed: {exc}"}, code=502)
            return
        if parsed.path == "/api/spurts":
            try:
                self._json(
                    build_spurts_board(
                        fresh=(params.get("fresh") or ["0"])[0] == "1",
                        exchange=(params.get("exchange") or ["all"])[0],
                        universe_id=(params.get("universe") or ["live"])[0],
                        date=(params.get("date") or [None])[0],
                    )
                )
            except RuntimeError as exc:
                self._json({"error": str(exc)}, code=503)
            except ValueError as exc:
                self._json({"error": str(exc)}, code=404)
            except (URLError, HTTPError, TimeoutError, OSError) as exc:
                self._json({"error": f"Upstream failed: {exc}"}, code=502)
            return
        if parsed.path == "/api/universe":
            status = dimension_status() if dimension_status else {"exists": False}
            metas = list_universe_meta() if list_universe_meta else UNIVERSES
            self._json(
                {
                    "schedule": "Every Monday 07:00 Asia/Kolkata",
                    "sources": ["NSE archives (indices + EQUITY_L)", "BSE ListofScripData"],
                    "status": status,
                    "universes": [
                        {
                            "id": item["id"],
                            "label": item["label"],
                            "enrich_limit": item.get("enrich_limit"),
                            "count": item.get("count"),
                            "scanable": item.get("scanable"),
                            "size": len(_load_universe(item["id"])),
                        }
                        for item in metas
                        if item.get("id") != "all"
                    ],
                }
            )
            return
        if parsed.path == "/api/universe/refresh":
            if refresh_dimension is None:
                self._json({"error": "universe_dim module unavailable"}, code=503)
                return
            try:
                payload = refresh_dimension()
                _reload_universe_cache()
                self._json(
                    {
                        "ok": True,
                        "as_of": payload.get("as_of"),
                        "as_of_ist": payload.get("as_of_ist"),
                        "status": dimension_status() if dimension_status else None,
                        "counts": {
                            m["id"]: m.get("count") for m in payload.get("meta") or []
                        },
                    }
                )
            except (URLError, HTTPError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
                self._json({"error": f"Universe refresh failed: {exc}"}, code=502)
            return
        if parsed.path == "/api/volume":
            try:
                payload = build_volume(
                    symbol=(params.get("symbol") or ["RELIANCE"])[0],
                    sc_id=(params.get("sc_id") or [""])[0],
                    kind=(params.get("kind") or ["stock"])[0],
                    tf_id=(params.get("tf") or params.get("timeframe") or ["1d"])[0],
                    fresh=(params.get("fresh") or ["0"])[0] == "1",
                )
                self._json(payload)
            except RuntimeError as exc:
                self._json({"error": str(exc)}, code=404)
            except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
                self._json({"error": f"Upstream failed: {exc}"}, code=502)
            return
        if parsed.path == "/api/symbol-dossier":
            try:
                self._json(
                    build_symbol_dossier(
                        symbol=(params.get("symbol") or [""])[0],
                        sc_id=(params.get("sc_id") or [""])[0],
                        tf_id=(params.get("tf") or params.get("timeframe") or ["1d"])[0],
                        exchange=(params.get("exchange") or ["NSE"])[0],
                        indicators=(params.get("indicators") or [None])[0],
                        fresh=(params.get("fresh") or ["0"])[0] == "1",
                    )
                )
            except RuntimeError as exc:
                self._json({"error": str(exc)}, code=404)
            except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
                self._json({"error": f"Upstream failed: {exc}"}, code=502)
            return

        path = parsed.path
        if path == "/":
            path = "/index.html"
        # SPA fallback: unknown non-API paths serve index.html from React build.
        ui_root = WEB_DIST if (WEB_DIST / "index.html").is_file() else STATIC
        file_path = (ui_root / path.lstrip("/")).resolve()
        try:
            file_path.relative_to(ui_root)
        except ValueError:
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        if not file_path.is_file():
            # Client-side router fallback for React build only.
            index = ui_root / "index.html"
            if ui_root == WEB_DIST and index.is_file() and "." not in Path(path).name:
                file_path = index
            else:
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
        kind = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".mjs": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
            ".woff2": "font/woff2",
            ".map": "application/json; charset=utf-8",
        }.get(file_path.suffix, "application/octet-stream")
        self._send(200, file_path.read_bytes(), kind)


def main() -> None:
    STATIC.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    SPURTS_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    if start_monday_refresh_scheduler is not None:
        start_monday_refresh_scheduler()
    if ensure_fresh_dimension is not None:
        try:
            ensure_fresh_dimension()
            _reload_universe_cache()
        except Exception as exc:  # noqa: BLE001 — boot with legacy JSON if needed
            print(f"Universe dim: using cached/legacy lists ({exc})")
    class QuietHTTPServer(ThreadingHTTPServer):
        def handle_error(self, request, client_address) -> None:  # noqa: ANN001
            exc = sys.exc_info()[1]
            if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
                return
            super().handle_error(request, client_address)

    server = None
    port = 8797
    for port in range(8797, 8807):
        try:
            server = QuietHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit("Could not bind a local port between 8797 and 8806.")
    ui = "React (web/dist)" if (WEB_DIST / "index.html").is_file() else "legacy static/"
    print(f"Signal Desk is running at http://127.0.0.1:{port}")
    print(f"UI: {ui} · Volume · Technical · Lab · Chart · Spurts. Press Ctrl+C to stop.")
    print("Universe: NSE/BSE dimension · refresh every Monday 07:00 IST")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
