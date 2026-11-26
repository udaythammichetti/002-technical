#!/usr/bin/env python3
"""Signal Desk — API + static file server for the React UI.

Dev (hot reload):
  python3 -u server.py          # API on :8797
  cd web && npm run dev         # UI on :5173 (proxies /api)

Production-style (single port):
  cd web && npm run build
  python3 -u server.py          # serves web/dist + /api on :8797

Primary source: Moneycontrol price/history APIs (NSE cash).
Not a forecast or investment advice.
"""

from __future__ import annotations

import gzip
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
#
# Periods are ChartSchool bar-counts on the active resolution
# (RSI 14 on 1D = 14 days; on 1W = 14 weeks; on 15m = 14×15m).
# Refs: StockCharts ChartSchool — RVOL default 50 · CMF 20 · MFI 14 ·
# Force Index EMA 13 · EMV SMA 14 · RSI 14 · MACD 12/26/9 · SMA 20/50.
#
# avg_window  → CMF / Lab·Chart base / UV-DV / OBVΔ (CMF default 20)
# rvol_window → RVOL / VolZ (ChartSchool RVOL default 50)
TIMEFRAMES = {
    "15m": {
        "label": "15 Min",
        "resolution": "15",
        "lookback_days": 7,
        "countback": 220,
        "avg_window": 20,
        "rvol_window": 50,
    },
    "1h": {
        "label": "1 Hour",
        "resolution": "60",
        "lookback_days": 20,
        "countback": 220,
        "avg_window": 20,
        "rvol_window": 50,
    },
    "4h": {
        "label": "4 Hours",
        "resolution": "60",
        "lookback_days": 35,
        "countback": 320,
        "avg_window": 20,
        "rvol_window": 50,
        "aggregate": 4,
    },
    "1d": {
        "label": "1 Day",
        "resolution": "1D",
        "lookback_days": 160,
        "countback": 160,
        # Chart 6-month read: 126 sessions. Other desks keep countback 160.
        "chart_countback": 126,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 126,
        "chart_fib_swing": 126,
    },
    # Chart daily mid-depths — Yahoo 2y / 5y fetch, then trim to ≈2/3/4/5 trading years.
    "1d2": {
        "label": "1 Day · 2Y",
        "resolution": "1D",
        "lookback_days": 800,
        "countback": 504,
        "chart_countback": 504,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 504,
        "chart_fib_swing": 504,
    },
    "1d3": {
        "label": "1 Day · 3Y",
        "resolution": "1D",
        "lookback_days": 1200,
        "countback": 756,
        "chart_countback": 756,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 756,
        "chart_fib_swing": 756,
    },
    "1d4": {
        "label": "1 Day · 4Y",
        "resolution": "1D",
        "lookback_days": 1600,
        "countback": 1008,
        "chart_countback": 1008,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 1008,
        "chart_fib_swing": 1008,
    },
    "1d5": {
        "label": "1 Day · 5Y",
        "resolution": "1D",
        "lookback_days": 2000,
        "countback": 1260,
        "chart_countback": 1260,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 1260,
        "chart_fib_swing": 1260,
    },
    # Chart daily full history — Yahoo 10y daily (~2.4k bars; Yahoo range=max is sparse on .NS).
    "1df": {
        "label": "1 Day · Full",
        "resolution": "1D",
        "lookback_days": 4000,
        "countback": 2520,
        "chart_countback": 2520,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 2520,
        "chart_fib_swing": 2520,
    },
    # Weekly bars (~5y fetch · ≤160 weeks) — ChartSchool counts are in weeks.
    "1w": {
        "label": "1 Week · 104",
        "resolution": "1W",
        "lookback_days": 900,
        "countback": 104,
        "chart_countback": 104,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 104,
        "chart_fib_swing": 104,
    },
    # Monthly bars (Yahoo max · ≤80 months) — ChartSchool counts are in months.
    "1m": {
        "label": "1 Month · 60",
        "resolution": "1M",
        "lookback_days": 2200,
        "countback": 60,
        "chart_countback": 60,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 60,
        "chart_fib_swing": 60,
    },
    # Long chips: same daily ChartSchool periods as 1D; more history for patterns.
    "3m": {
        "label": "3 Months",
        "resolution": "1D",
        "lookback_days": 160,
        "countback": 120,
        "avg_window": 20,
        "rvol_window": 50,
        # Yahoo 3mo daily is ~64 sessions. Lookbacks match that, not a 90-bar default.
        "chart_sr_look": 60,
        "chart_fib_swing": 60,
        "chart_countback": 60,
    },
    "6m": {
        "label": "6 Months",
        "resolution": "1D",
        "lookback_days": 240,
        "countback": 180,
        "avg_window": 20,
        "rvol_window": 50,
    },
    "1y": {
        "label": "1 Year",
        "resolution": "1D",
        "lookback_days": 420,
        "countback": 280,
        # Chart read: ≈1 trading year of daily bars.
        "chart_countback": 252,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 252,
        "chart_fib_swing": 252,
    },
    "5y": {
        "label": "5 Years · Week",
        "resolution": "1W",
        "lookback_days": 2000,
        "countback": 260,
        "chart_countback": 260,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 260,
        "chart_fib_swing": 260,
    },
    "max": {
        "label": "Max · Week",
        "resolution": "1W",
        "lookback_days": 12000,
        "countback": 520,
        "chart_countback": 520,
        "avg_window": 20,
        "rvol_window": 50,
        "chart_sr_look": 520,
        "chart_fib_swing": 520,
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

# Live scan progress (client polls /api/scan-progress?job=… while board request runs).
_scan_jobs_lock = threading.Lock()
_scan_jobs: dict[str, dict] = {}


def _scan_job_id(raw: str | None) -> str | None:
    job = re.sub(r"[^A-Za-z0-9_-]", "", str(raw or "").strip())[:64]
    return job or None


def _scan_job_start(job_id: str | None, *, total: int, phase: str, label: str = "") -> None:
    jid = _scan_job_id(job_id)
    if not jid:
        return
    total_n = max(0, int(total or 0))
    with _scan_jobs_lock:
        _scan_jobs[jid] = {
            "job": jid,
            "state": "running",
            "phase": phase or "scan",
            "label": label or "",
            "done": 0,
            "total": total_n,
            "pct": 0.0,
            "updated": time.time(),
        }


def _scan_job_tick(
    job_id: str | None,
    *,
    done: int | None = None,
    inc: int = 0,
    total: int | None = None,
    phase: str | None = None,
    label: str | None = None,
) -> None:
    jid = _scan_job_id(job_id)
    if not jid:
        return
    with _scan_jobs_lock:
        job = _scan_jobs.get(jid)
        if not job:
            return
        if total is not None:
            job["total"] = max(0, int(total))
        if done is not None:
            job["done"] = max(0, int(done))
        elif inc:
            job["done"] = max(0, int(job.get("done") or 0) + int(inc))
        if phase:
            job["phase"] = phase
        if label is not None:
            job["label"] = label
        tot = int(job.get("total") or 0)
        d = int(job.get("done") or 0)
        job["pct"] = round(min(100.0, (100.0 * d / tot) if tot else 0.0), 1)
        job["state"] = "running"
        job["updated"] = time.time()


def _scan_job_finish(job_id: str | None, *, ok: bool = True, error: str | None = None) -> None:
    jid = _scan_job_id(job_id)
    if not jid:
        return
    with _scan_jobs_lock:
        job = _scan_jobs.get(jid) or {
            "job": jid,
            "done": 0,
            "total": 0,
            "phase": "done",
            "label": "",
        }
        if ok:
            tot = int(job.get("total") or 0)
            if tot and int(job.get("done") or 0) < tot:
                job["done"] = tot
            job["pct"] = 100.0
            job["state"] = "done"
            job["phase"] = "done"
        else:
            job["state"] = "error"
            job["phase"] = "error"
            job["error"] = error or "Scan failed"
        job["updated"] = time.time()
        _scan_jobs[jid] = job


def get_scan_progress(job_id: str | None) -> dict:
    jid = _scan_job_id(job_id)
    if not jid:
        return {"state": "idle", "done": 0, "total": 0, "pct": 0, "phase": "", "label": ""}
    with _scan_jobs_lock:
        job = _scan_jobs.get(jid)
        if not job:
            return {
                "job": jid,
                "state": "pending",
                "done": 0,
                "total": 0,
                "pct": 0,
                "phase": "starting",
                "label": "",
            }
        return dict(job)


def _as_completed_progress(futures, job_id: str | None = None, *, phase: str = "scan"):
    """Yield completed futures while ticking scan progress."""
    items = list(futures)
    total = len(items)
    _scan_job_tick(job_id, done=0, total=total, phase=phase)
    done = 0
    for fut in as_completed(items):
        done += 1
        _scan_job_tick(job_id, done=done, total=total, phase=phase)
        yield fut


def _load_universe(universe_id: str, *, require_sc_id: bool = False) -> list[dict]:
    """Load the book for a board scan.

    Board history goes through Yahoo by symbol, so Moneycontrol sc_id is not
    required. BSE All / NSE All otherwise drop thousands of names that only
    have an exchange ticker.
    """
    universe_id = (universe_id or "nifty50").lower()
    cache_key = (universe_id, bool(require_sc_id))
    if cache_key in _universe_cache:
        return _universe_cache[cache_key]

    rows: list[dict] = []
    if get_universe_rows is not None:
        try:
            rows = get_universe_rows(universe_id, require_sc_id=require_sc_id)
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

    _universe_cache[cache_key] = rows
    return rows


def _universe_meta(universe_id: str) -> dict:
    uid = (universe_id or "nifty50").lower()
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
    meta = _universe_meta(uid)
    if meta.get("count"):
        return int(meta["count"])
    if get_universe_rows is not None:
        try:
            return len(get_universe_rows(uid, require_sc_id=False))
        except (OSError, ValueError, RuntimeError, TypeError):
            pass
    return len(_load_universe(uid))


def _merge_quote_remainder(
    enriched: list[dict],
    quote_rows: list[dict],
    tf_id: str | None = None,
) -> list[dict]:
    """Keep full-history shortlist + remaining quote-level names for large books.

    Quote RVOL uses live DVolAvg20 (daily) — only merge onto daily boards so
    intraday / weekly / monthly scans are not polluted with TF-blind scores.
    """
    if tf_id:
        res = TIMEFRAMES.get(_normalize_tf(tf_id), {}).get("resolution")
        if res != "1D":
            return list(enriched)
    seen = {row.get("id") for row in enriched if row.get("id")}
    out = list(enriched)
    for row in quote_rows:
        rid = row.get("id")
        if rid and rid not in seen:
            tagged = dict(row)
            tagged["quote_only"] = True
            out.append(tagged)
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


_yahoo_slots = threading.Semaphore(12)
_yahoo_hist_lock = threading.Lock()
_yahoo_hist: dict[tuple, dict] = {}
_yahoo_local = threading.local()
_yahoo_session = None
_mc_blocked: bool | None = None
# priceapi.moneycontrol.com hangs; techCharts history answers, but slowly.
_mc_quote_down = False
_mc_history_slow = False

# Moneycontrol resolution → Yahoo chart interval/range.
YAHOO_TF = {
    "15m": ("15m", "60d"),  # ~200+ fifteen-minute bars so SMA50/200 can compute
    "1h": ("60m", "3mo"),
    "4h": ("60m", "1y"),  # 4h is aggregated from 60m; 200×4h needs about a year
    "1d": ("1d", "1y"),
    "1d2": ("1d", "2y"),
    "1d3": ("1d", "5y"),  # Yahoo has no 3y — fetch 5y, trim to ~780
    "1d4": ("1d", "5y"),  # Yahoo has no 4y — fetch 5y, trim to ~1040
    "1d5": ("1d", "5y"),
    "1df": ("1d", "10y"),  # full daily depth (Yahoo max is thin on .NS)
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
        "1d_full": "1df",
        "1dfull": "1df",
        "dfull": "1df",
        "daily_full": "1df",
        "1d_2y": "1d2",
        "1d2y": "1d2",
        "daily_2y": "1d2",
        "1d_3y": "1d3",
        "1d3y": "1d3",
        "daily_3y": "1d3",
        "1d_4y": "1d4",
        "1d4y": "1d4",
        "daily_4y": "1d4",
        "1d_5y": "1d5",
        "1d5y": "1d5",
        "daily_5y": "1d5",
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


def _curl_session():
    """Browser-like HTTPS session so Yahoo accepts the quote requests."""
    try:
        from curl_cffi import requests as creq  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Install curl_cffi for Yahoo quotes: pip3 install curl_cffi"
        ) from exc
    return creq.Session()


def _yahoo_http() -> object:
    """One curl_cffi session per thread so a board scan can run several Yahoo calls at once."""
    session = getattr(_yahoo_local, "session", None)
    if session is None:
        session = _curl_session()
        _yahoo_local.session = session
    return session


def _yahoo_get_json(url: str, timeout: float = 12) -> dict | list:
    session = _yahoo_http()
    headers = {
        "User-Agent": UA,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Referer": "https://finance.yahoo.com/",
    }
    last_status = 0
    for attempt in range(3):
        with _yahoo_slots:
            response = session.get(url, headers=headers, impersonate="chrome131", timeout=timeout)
        last_status = response.status_code
        if response.status_code in {429, 500, 502, 503, 504}:
            time.sleep(0.45 * (attempt + 1))
            continue
        if response.status_code >= 400:
            raise RuntimeError(f"Yahoo HTTP {response.status_code}")
        return response.json()
    raise RuntimeError(f"Yahoo HTTP {last_status or 'retry'}")


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
                # Boards scan every ticker via Yahoo — do not use Moneycontrol sc_id
                # counts here (those made BSE Group B / BSE All look half-empty).
                "size": _universe_full_size(item["id"]),
                "scanable": len(_load_universe(item["id"])),
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
    cache_key = (ticker, interval, span)
    with _yahoo_hist_lock:
        cached = _yahoo_hist.get(cache_key)
    if cached is not None:
        return cached
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
    payload_out = {
        "s": "ok",
        "t": times,
        "o": quote_block.get("open") or [],
        "h": quote_block.get("high") or [],
        "l": quote_block.get("low") or [],
        "c": quote_block.get("close") or [],
        "v": quote_block.get("volume") or [],
        "_source": "yahoo",
        "_ticker": ticker,
    }
    with _yahoo_hist_lock:
        _yahoo_hist[cache_key] = payload_out
    return payload_out


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
        "previousclose": prev,
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


def _tf_change_mode(tf_id: str) -> str:
    """How Chg % is filled for this chip.

    session — live 1D vs previous close (daily bars: 1D / 3M / 1Y / …)
    period  — live WTD / MTD vs last completed week / month close
    bar     — last bar vs prior bar (intraday)
    """
    tf = TIMEFRAMES.get(_normalize_tf(tf_id) if tf_id else "1d") or {}
    res = str(tf.get("resolution") or "")
    if res == "1D":
        return "session"
    if res in {"1W", "1M"}:
        return "period"
    return "bar"


def _tf_is_daily(tf_id: str) -> bool:
    """True when the chip’s bar size is a daily session (1D / 1Y / 3M…)."""
    return _tf_change_mode(tf_id) == "session"


def _period_anchor_close(bars: list[dict], resolution: str) -> float | None:
    """Prior completed week/month close for live WTD / MTD.

    After stub-trim, last bar is the completed period → use its close.
    If the feed still keeps an in-progress week/month candle, use the one before.
    """
    if not bars:
        return None
    last = bars[-1]
    last_ts = last.get("ts")
    if last_ts is None:
        return _num(last.get("close"))
    last_dt = datetime.fromtimestamp(int(last_ts), tz=timezone.utc).astimezone(IST)
    now = datetime.now(tz=IST)
    in_progress = False
    if resolution == "1W":
        in_progress = last_dt.isocalendar()[:2] == now.isocalendar()[:2]
    elif resolution == "1M":
        in_progress = (last_dt.year, last_dt.month) == (now.year, now.month)
    if in_progress and len(bars) >= 2:
        return _num(bars[-2].get("close"))
    return _num(last.get("close"))


def _session_chg_from_quote(quote: dict | None) -> tuple[float | None, float | None]:
    """Live session % and LTP from a quote dict."""
    if not quote:
        return None, None
    px = _num(quote.get("pricecurrent"))
    chg = _num(quote.get("pricepercentchange"))
    prev = _num(quote.get("previousclose"))
    if chg is None and px is not None and prev:
        chg = ((px - prev) / prev) * 100.0
    if chg is not None:
        chg = round(float(chg), 2)
    return chg, px


def _stamp_today_change(row: dict, quote: dict | None) -> None:
    """Always set today_chg = live session % (independent of TF chip)."""
    if not row:
        return
    today, _px = _session_chg_from_quote(quote)
    if today is not None:
        row["today_chg"] = today
        row["today_up"] = bool(today >= 0)


def _overlay_live_change(
    row: dict,
    quote: dict | None,
    *,
    mode: str,
    period_prev_close: float | None = None,
) -> None:
    """Fill Chg % from live quote — session (1D) or period (WTD/MTD).

    Daily: Yahoo session % (bar gaps skip holidays → multi-day bar %).
    Swing/Long week·month: live price vs last completed period close so the
    column stays current instead of last finished week/month only.
    """
    if not row or not quote or mode == "bar":
        return
    px = _num(quote.get("pricecurrent"))
    chg = None
    if mode == "session":
        chg, px = _session_chg_from_quote(quote)
        row["change_basis"] = "session"
    elif mode == "period":
        prev = _num(period_prev_close)
        if px is not None and prev:
            chg = ((px - prev) / prev) * 100.0
        row["change_basis"] = "period"
    if chg is not None:
        row["change_pct"] = round(float(chg), 2)
        row["up"] = bool(row["change_pct"] >= 0)
    if px is not None:
        row["close"] = px


def _overlay_session_change(row: dict, quote: dict | None) -> None:
    """Back-compat: daily session overlay."""
    _overlay_live_change(row, quote, mode="session")


def _apply_tf_change(
    row: dict,
    quote: dict | None,
    tf_id: str,
    *,
    bars: list[dict] | None = None,
    period_prev_close: float | None = None,
) -> None:
    """Stamp Today % always; then TF Chg % (session / WTD / MTD / bar)."""
    _stamp_today_change(row, quote)
    mode = _tf_change_mode(tf_id)
    if mode == "bar":
        row["change_basis"] = "bar"
        return
    prev = period_prev_close
    if mode == "period" and prev is None and bars:
        res = str((TIMEFRAMES.get(_normalize_tf(tf_id)) or {}).get("resolution") or "")
        prev = _period_anchor_close(bars, res)
    _overlay_live_change(row, quote, mode=mode, period_prev_close=prev)


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


def _trim_swing_period_stub(bars: list[dict], resolution: str) -> list[dict]:
    """Drop Yahoo/MC live stubs wrongly appended to weekly/monthly series.

    Completed 1W/1M bars share a period-boundary clock (typically 18:30 UTC).
    Feeds often append a mid-period quote bar (wall-clock 'now' + that day's volume),
    which crushes Swing RVOL (e.g. today-only vol ÷ average full week/month).
    """
    if resolution not in {"1W", "1M"} or len(bars) < 3:
        return bars
    prev = datetime.fromtimestamp(int(bars[-2]["ts"]), tz=timezone.utc)
    last = datetime.fromtimestamp(int(bars[-1]["ts"]), tz=timezone.utc)
    if (last.hour, last.minute) == (prev.hour, prev.minute):
        return bars
    gap_last = int(bars[-1]["ts"]) - int(bars[-2]["ts"])
    gap_prev = int(bars[-2]["ts"]) - int(bars[-3]["ts"])
    # Stub usually has mismatched TOD; also shorter spacing than a full period.
    if gap_prev > 0 and gap_last < gap_prev * 0.85:
        return bars[:-1]
    # Monthly stub can sit ~28d after month-start yet still be a daily quote — TOD wins.
    if (last.hour, last.minute) != (prev.hour, prev.minute):
        return bars[:-1]
    return bars


# ChartSchool: Volume periods = bar counts on the selected interval's resolution.
# Example: RVOL(50) on 1D = 50 daily bars; on 15m = 50×15m bars; on 1W = 50 weeks.
TF_CONTRACT = (
    "Volume lookbacks are ChartSchool bar-counts on the selected interval: "
    "RVOL(50) · CMF(20) · MFI(14) · Force EMA(13) · EMV SMA(14) · "
    "VolOsc(5/20) · Chaikin Osc(3/10) · PVO(12/26/9). "
    "Same numbers on every TF — a 'bar' is that interval (15m / 1H / 1D / 1W / 1M). "
    "Long chips (3M/6M/1Y) keep daily bars + the same lookbacks with more history."
)

# Classic ChartSchool defaults (bar counts — not calendar days).
CS_RVOL = 50
CS_CMF = 20
CS_MFI = 14
CS_FORCE = 13
CS_EMV = 14
CS_VO_SHORT = 5
CS_VO_LONG = 20
CS_CHAIKIN_FAST = 3
CS_CHAIKIN_SLOW = 10
CS_PVO_FAST = 12
CS_PVO_SLOW = 26
CS_PVO_SIG = 9
CS_RSI = 14
CS_EMA = 20
CS_MACD_FAST = 12
CS_MACD_SLOW = 26
CS_MACD_SIG = 9
CS_SMA_FAST = 20
CS_SMA_SLOW = 50
CS_SMA_LONG = 200  # ChartSchool Golden / Death Cross with SMA50
CS_STOCH = 14
CS_STOCH_SLOW = 3  # ChartSchool Full Stochastic slowing / %D
CS_CCI = 20
CS_ROC = 12
CS_ADX = 14
CS_ATR = 14
CS_BB = 20
CS_BB_DEV = 2.0
CS_AROON = 25  # ChartSchool Aroon default
# PPO uses same Appel lengths as MACD (ChartSchool PPO 12/26/9)


def _tf_study_windows(tf_id: str) -> dict[str, int]:
    """CMF/base + RVOL windows for this TF (ChartSchool defaults, adapted later)."""
    tf = TIMEFRAMES[_normalize_tf(tf_id)]
    return {
        "avg_window": int(tf.get("avg_window") or CS_CMF),
        "rvol_window": int(tf.get("rvol_window") or CS_RVOL),
    }


def _tf_meta(tf_id: str) -> dict:
    tid = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tid]
    wins = _tf_study_windows(tid)
    res = tf["resolution"]
    res_label = {
        "15": "15-minute bars",
        "60": "60-minute bars" + (" (×4 → 4h)" if tid == "4h" else ""),
        "1D": "daily bars",
        "1W": "weekly bars",
        "1M": "monthly bars",
    }.get(res, res)
    change_mode = _tf_change_mode(tid)
    if change_mode == "session":
        change_label, change_title = "1D %", "Live session change vs previous close"
    elif change_mode == "period" and res == "1W":
        change_label, change_title = "WTD %", "Week-to-date vs last completed week close"
    elif change_mode == "period":
        change_label, change_title = "MTD %", "Month-to-date vs last completed month close"
    else:
        change_label, change_title = "Bar %", "Last bar vs prior bar"
    # Volume desk lookbacks for this interval (bar counts on resolution).
    volume = {
        "rvol": wins["rvol_window"],
        "vol_z": wins["rvol_window"],
        "cmf": wins["avg_window"],
        "uv_dv": wins["avg_window"],
        "obv_delta": wins["avg_window"],
        "ad_delta": wins["avg_window"],
        "mfi": CS_MFI,
        "force": CS_FORCE,
        "emv": CS_EMV,
        "vol_osc": f"{CS_VO_SHORT}/{CS_VO_LONG}",
        "chaikin": f"{CS_CHAIKIN_FAST}/{CS_CHAIKIN_SLOW}",
        "pvo": f"{CS_PVO_FAST}/{CS_PVO_SLOW}/{CS_PVO_SIG}",
        "donchian": wins["avg_window"],
        "spread": wins["avg_window"],
        "spike_rvol": 1.5,
        "spike_vol_z": 2.0,
    }
    return {
        "id": tid,
        "label": tf["label"],
        "resolution": res,
        "resolution_label": res_label,
        "change_mode": change_mode,
        "change_label": change_label,
        "change_title": change_title,
        "avg_window": wins["avg_window"],
        "rvol_window": wins["rvol_window"],
        "countback": int(tf["countback"]),
        "contract": TF_CONTRACT,
        "volume": volume,
        "tech": {
            "rsi": CS_RSI,
            "macd": f"{CS_MACD_FAST}/{CS_MACD_SLOW}/{CS_MACD_SIG}",
            "ppo": f"{CS_MACD_FAST}/{CS_MACD_SLOW}/{CS_MACD_SIG}",
            "sma": f"{CS_SMA_FAST}/{CS_SMA_SLOW}",
            "sma200": f"{CS_SMA_SLOW}/{CS_SMA_LONG}",
            "ema": CS_EMA,
            "bb": f"{CS_BB},{CS_BB_DEV:g}",
            "stoch": f"{CS_STOCH}/{CS_STOCH_SLOW}/{CS_STOCH_SLOW}",
            "cci": CS_CCI,
            "willr": CS_STOCH,
            "adx": CS_ADX,
            "aroon": CS_AROON,
            "roc": CS_ROC,
            "atr": CS_ATR,
        },
        # Lab (sci) — ChartSchool bar-counts on selected resolution.
        "lab": {
            "donchian": wins["avg_window"],
            "cmf": wins["avg_window"],
            "obv": wins["avg_window"],
            "rvol": wins["rvol_window"],
            "bb": f"{wins['avg_window']},{CS_BB_DEV:g}",
            "atr": CS_ATR,
            "break_rvol": 1.5,
            "coil_range_pct": 12,
        },
        # Chart Analysis — ChartSchool S/R · trend · gap · Fib on selected bars.
        "chart": {
            "sr": wins["avg_window"],
            "sr_look": int(tf.get("chart_sr_look") or 90),
            "rvol": wins["rvol_window"],
            "gap_rvol": 1.4,
            "near_pct": 1.25,
            "trend_touches": 3,
            "fib_swing": int(
                tf.get("chart_fib_swing") or max(50, wins["avg_window"] * 3)
            ),
            "zone_pct": 0.4,
            "history_bars": int(tf.get("chart_countback") or tf.get("countback") or 0) or None,
            "resolution": res,
            "read": tf.get("label") or tid,
        },
        "chartschool": {
            "rvol": CS_RVOL,
            "cmf": CS_CMF,
            "mfi": CS_MFI,
            "force": CS_FORCE,
            "emv": CS_EMV,
            "vol_osc": f"{CS_VO_SHORT}/{CS_VO_LONG}",
            "chaikin": f"{CS_CHAIKIN_FAST}/{CS_CHAIKIN_SLOW}",
            "pvo": f"{CS_PVO_FAST}/{CS_PVO_SLOW}/{CS_PVO_SIG}",
            "rsi": CS_RSI,
            "macd": f"{CS_MACD_FAST}/{CS_MACD_SLOW}/{CS_MACD_SIG}",
            "ppo": f"{CS_MACD_FAST}/{CS_MACD_SLOW}/{CS_MACD_SIG}",
            "sma": f"{CS_SMA_FAST}/{CS_SMA_SLOW}",
            "sma200": f"{CS_SMA_SLOW}/{CS_SMA_LONG}",
            "ema": CS_EMA,
            "bb": f"{CS_BB},{CS_BB_DEV:g}",
            "stoch": f"{CS_STOCH}/{CS_STOCH_SLOW}/{CS_STOCH_SLOW}",
            "adx": CS_ADX,
            "aroon": CS_AROON,
            "roc": CS_ROC,
            "atr": CS_ATR,
        },
    }


def _tech_period_prefs(_tf_id: str | None = None) -> dict[str, int]:
    """ChartSchool classic tech periods (bar counts on active resolution).

    Same numbers on every chip — a bar is 15m / 1H / 1D / 1W / 1M of the selection.
    Long 3M–1Y use daily bars; 5Y/Max use weekly bars.
    """
    return {
        "rsi": CS_RSI,
        "ema": CS_EMA,
        "fast": CS_MACD_FAST,
        "slow": CS_MACD_SLOW,
        "sig": CS_MACD_SIG,
        "sma_f": CS_SMA_FAST,
        "sma_s": CS_SMA_SLOW,
        "sma_l": CS_SMA_LONG,
        "bb": CS_BB,
        "stoch": CS_STOCH,
        "stoch_slow": CS_STOCH_SLOW,
        "cci": CS_CCI,
        "roc": CS_ROC,
        "adx": CS_ADX,
        "atr": CS_ATR,
        "aroon": CS_AROON,
    }


# Volume formulas (documented for API + UI).
# Refs: StockCharts OBV / CMF / MFI / A/D · relative volume practice.
FORMULAS = {
    "timeframe": TF_CONTRACT,
    "history": (
        "Recent listings / short series: every desk shrinks ChartSchool periods to available bars. "
        "history=thin (<8 bars) · partial (windows truncated) · full (preferred lookbacks fit). "
        "Score/KPIs use only what the series can support — never invent 50/200-day math on 10 bars."
    ),
    "rvol": (
        "RVOL = V_t ÷ SMA(V, prior 50 bars of the selected chip) — "
        "ChartSchool classic RVOL (current bar excluded from the average). "
        "Intraday: 15m→50×15m bars · 1H→50×60m · 4H→50×4h (from 60m aggregates). "
        "Swing: 1D→50 days · 1W→50 weeks · 1M→50 months. "
        "Long: 3M/6M/1Y use daily bars so RVOL = same as 1D (50 days); "
        "5Y/Max use weekly bars so RVOL = 50 weeks. "
        "Not time-of-day RVOL (RVOL-TOD)."
    ),
    "vol_z": (
        "VolZ = (V_t − μ) / σ over the same prior 50 bars as RVOL — "
        "≥2σ = spike (with RVOL ≥ 1.5×)"
    ),
    "obv": "OBV_t = OBV_{t−1} + V_t if C↑; −V_t if C↓ (Granville / ChartSchool OBV)",
    "obv_delta": (
        "OBVΔ = OBV_t − OBV_{t−20} on selected-interval bars "
        "(CMF window; rising = accumulation)"
    ),
    "volume_ratio": (
        "UV/DV = Σ up-bar volume ÷ Σ down-bar volume over last 20 bars "
        "(incl. current; ChartSchool CMF window)"
    ),
    "ad": "A/D += ((C−L)−(H−C))/(H−L) × V  (Chaikin Accumulation/Distribution)",
    "cmf": (
        "CMF(20) = Σ MFV_20 ÷ Σ V_20 on selected-interval bars; "
        "MFV = ((C−L)−(H−C))/(H−L)×V (Chaikin / ChartSchool)"
    ),
    "mfi": (
        "MFI(14) = 100 − 100/(1 + pos_MF ÷ neg_MF) over 14 bars "
        "(ChartSchool Money Flow Index / volume-weighted RSI)"
    ),
    "vpt": "VPT += V × (C − C_prev) / C_prev (Volume Price Trend)",
    "force": (
        "Force(1)=(C−C_prev)×V ; Force(13)=EMA of FI(1) seeded with SMA of first 13 "
        "(Elder / ChartSchool)"
    ),
    "emv": (
        "EMV(1)=DistanceMoved÷BoxRatio ; EMV(14)=SMA of EMV(1) "
        "(Arms / ChartSchool Ease of Movement)"
    ),
    "vol_osc": (
        "VolOsc% = 100 × (SMA(V,5) − SMA(V,20)) ÷ SMA(V,20) on consecutive bars "
        "(ChartSchool Volume Oscillator)"
    ),
    "chaikin": (
        "Chaikin Osc = EMA(ADL,3) − EMA(ADL,10) — Marc Chaikin / ChartSchool; "
        ">0 buying pressure momentum, <0 selling"
    ),
    "pvo": (
        "PVO = 100 × (EMA(V,12) − EMA(V,26)) ÷ EMA(V,26); Signal = EMA(PVO,9); "
        "Hist = PVO − Signal (ChartSchool Percentage Volume Oscillator)"
    ),
    "effort_result": (
        "Wyckoff Effort vs Result on selected-interval bars: "
        "Effort = RVOL (high≥1.5 · mid · low<0.7); "
        "Result = bar spread vs SMA(spread, 20) (wide≥1.2× · narrow≤0.7×) + close location. "
        "Confirm↑/↓ = high effort + wide spread + strong close; "
        "Absorb = high effort + narrow spread; NoDemand/NoSupply = low effort + narrow."
    ),
    "breakout": (
        "Correct/False breakout vs Donchian(20) of selected interval: "
        "Correct = close beyond prior box + RVOL≥1.5 + (wide spread or strong close); "
        "False = wick beyond but close back inside, weak volume break, or failed hold next bar. "
        "Intraday uses 20×15m/1H/4H bars; Swing 20 days/weeks/months; Long 3M–1Y = 20 daily."
    ),
    "bullish": "Bias = bullish when Score ≥ +30 (else neutral until ≤ −30)",
    "bearish": "Bias = bearish when Score ≤ −30",
    "score": (
        "Score (−100…+100) → Bias ≥+30 bullish / ≤−30 bearish: "
        "±25 bar direction · "
        "±25 RVOL≥1 (same sign) · ±15 RVOL≥1.5 · ×0.55 if RVOL<0.7 · "
        "±15/±6 OBVΔ · ±10 UV/DV · ±10 CMF · ±10 MFI · "
        "±8/±4 Force · ±6 EMV · ±8 VolZ≥2 / ×0.85 VolZ≤−1 · "
        "±6/±3 A/DΔ · ±8/±4 Chaikin · ±8/±3 PVO hist · "
        "±8/±6 Break Correct/False · ±5/±4 E/R Confirm·NoDemand/NoSupply · Absorb ×0.9"
    ),
}


def _vol_tone(rvol: float | None, vol_z: float | None = None) -> str:
    if (rvol is not None and rvol >= 1.5) or (vol_z is not None and vol_z >= 2.0):
        return "spike"
    if rvol is not None and rvol < 0.7:
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


def _ema_next(prev: float | None, value: float, period: int) -> float:
    """One EMA step (ChartSchool / Wilder-style α = 2/(N+1))."""
    if period <= 1:
        return value
    alpha = 2.0 / (period + 1.0)
    if prev is None:
        return value
    return prev + alpha * (value - prev)


def _volume_score(
    up: bool,
    rvol: float | None,
    obv_rising: bool | None,
    vol_ratio: float | None,
    cmf: float | None = None,
    mfi: float | None = None,
    force: float | None = None,
    emv: float | None = None,
    vol_z: float | None = None,
    ad_rising: bool | None = None,
    chaikin: float | None = None,
    pvo_hist: float | None = None,
    er_label: str | None = None,
    bo_quality: str | None = None,
    bo_side: str | None = None,
) -> float:
    """Combine classic volume confirms into a signed score (−100…+100).

    Core: direction × RVOL, then ChartSchool money-flow / volume oscillators,
    then light Wyckoff E/R + Correct/False break overlays. Clamp at the end.
    """
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
        score += 6.0  # bullish divergence lean
    elif obv_rising is False and up:
        score -= 6.0  # bearish divergence lean
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
    # Elder Force Index (smoothed) — ChartSchool
    if force is not None:
        if force > 0 and up:
            score += 8.0
        elif force < 0 and not up:
            score -= 8.0
        elif force > 0 and not up:
            score += 4.0
        elif force < 0 and up:
            score -= 4.0
    # Arms Ease of Movement — ChartSchool
    if emv is not None:
        if emv > 0 and up:
            score += 6.0
        elif emv < 0 and not up:
            score -= 6.0
    # Volume z-score anomaly (≥2σ unusual activity confirming the move)
    if vol_z is not None and vol_z >= 2.0:
        score += 8.0 if up else -8.0
    elif vol_z is not None and vol_z <= -1.0:
        score *= 0.85
    # Chaikin A/D slope
    if ad_rising is True and up:
        score += 6.0
    elif ad_rising is False and not up:
        score -= 6.0
    elif ad_rising is True and not up:
        score += 3.0
    elif ad_rising is False and up:
        score -= 3.0
    # Chaikin Oscillator — ADL momentum (ChartSchool 3/10)
    if chaikin is not None:
        if chaikin > 0 and up:
            score += 8.0
        elif chaikin < 0 and not up:
            score -= 8.0
        elif chaikin > 0 and not up:
            score += 4.0
        elif chaikin < 0 and up:
            score -= 4.0
    # PVO histogram — volume MACD (ChartSchool 12/26/9)
    if pvo_hist is not None:
        if pvo_hist > 0 and up:
            score += 8.0
        elif pvo_hist < 0 and not up:
            score -= 8.0
        elif pvo_hist > 0 and not up:
            score += 3.0
        elif pvo_hist < 0 and up:
            score -= 3.0
    # Wyckoff Break overlay (Correct / False)
    if bo_quality == "correct" and bo_side == "up":
        score += 8.0
    elif bo_quality == "correct" and bo_side == "down":
        score -= 8.0
    elif bo_quality == "false" and bo_side == "up":
        score -= 6.0
    elif bo_quality == "false" and bo_side == "down":
        score += 6.0  # failed breakdown / spring lean
    # Wyckoff Effort vs Result overlay
    if er_label == "Confirm↑":
        score += 5.0
    elif er_label == "Confirm↓":
        score -= 5.0
    elif er_label == "Absorb":
        score *= 0.9
    elif er_label == "NoDemand":
        score -= 4.0
    elif er_label == "NoSupply":
        score += 4.0
    return max(-100.0, min(100.0, score))


def _sma_seeded_ema_step(
    value: float,
    period: int,
    seed: list[float],
    ema: float | None,
) -> tuple[float | None, float | None]:
    """SMA-seed then EMA (ChartSchool). Returns (ema_state, output_or_None)."""
    if period <= 1:
        return value, value
    if ema is None:
        seed.append(value)
        if len(seed) >= period:
            seeded = sum(seed) / len(seed)
            return seeded, seeded
        return None, None
    nxt = _ema_next(ema, value, period)
    return nxt, nxt


def _bar_hlc(bar: dict) -> tuple[float, float, float]:
    close = float(bar["close"])
    high = float(bar["high"]) if bar.get("high") is not None else close
    low = float(bar["low"]) if bar.get("low") is not None else close
    if high < low:
        high, low = low, high
    return high, low, close


def _bar_spread(bar: dict) -> float:
    high, low, _ = _bar_hlc(bar)
    return max(0.0, high - low)


def _close_location(bar: dict) -> float:
    """0 = close on low · 1 = close on high (Wyckoff bar control)."""
    high, low, close = _bar_hlc(bar)
    span = high - low
    if span <= 0:
        return 0.5
    return max(0.0, min(1.0, (close - low) / span))


def _effort_result(
    rvol: float | None,
    spread: float,
    avg_spread: float | None,
    close_pos: float,
) -> dict:
    """Wyckoff Effort vs Result — volume = effort, bar spread/close = result.

    ChartSchool / Wyckoff: harmony when effort and result agree; absorption /
    no-demand when they diverge. Uses selected-interval bars only.
    """
    effort = "mid"
    if rvol is not None:
        if rvol >= 1.5:
            effort = "high"
        elif rvol < 0.7:
            effort = "low"

    result = "mid"
    if avg_spread is not None and avg_spread > 0:
        ratio = spread / avg_spread
        if ratio >= 1.2:
            result = "wide"
        elif ratio <= 0.7:
            result = "narrow"
    elif spread <= 0:
        result = "narrow"

    strong_up = close_pos >= 0.70
    strong_dn = close_pos <= 0.30
    label = "—"
    tone = "neutral"
    # Four highest-signal Wyckoff rows + harmony / clash
    if effort == "high" and result == "wide" and strong_up:
        label, tone = "Confirm↑", "bull"
    elif effort == "high" and result == "wide" and strong_dn:
        label, tone = "Confirm↓", "bear"
    elif effort == "high" and result == "narrow":
        label, tone = "Absorb", "warn"  # effort without result
    elif effort == "high" and result == "wide" and not strong_up and not strong_dn:
        label, tone = "Fight", "warn"  # high effort, mid close
    elif effort == "low" and result == "narrow" and strong_up:
        label, tone = "NoDemand", "bear"
    elif effort == "low" and result == "narrow" and strong_dn:
        label, tone = "NoSupply", "bull"
    elif effort == "high" and result == "mid" and strong_up:
        label, tone = "Effort↑", "bull"
    elif effort == "high" and result == "mid" and strong_dn:
        label, tone = "Effort↓", "bear"
    elif effort != "low" and result == "wide" and strong_up:
        label, tone = "Result↑", "bull"
    elif effort != "low" and result == "wide" and strong_dn:
        label, tone = "Result↓", "bear"
    elif effort == "high" and not strong_up and not strong_dn:
        label, tone = "Clash", "warn"

    return {
        "effort": effort,
        "result": result,
        "er": label,
        "er_tone": tone,
        "spread": round(spread, 4),
        "spread_x": round(spread / avg_spread, 2) if avg_spread and avg_spread > 0 else None,
        "close_pos": round(close_pos, 2),
    }


def _breakout_quality(
    bars: list[dict],
    i: int,
    box_n: int,
    rvol: float | None,
    close_pos: float,
    spread: float,
    avg_spread: float | None,
) -> dict:
    """Correct vs false breakout — Donchian(box) + volume + close (Wyckoff/VSA).

    box_n = CMF window on the selected interval (20 bars of 15m / 1D / 1W / …).
    Correct: close beyond prior box + RVOL≥1.5 + wide-ish spread + strong close.
    False: wick beyond but close back inside, or break on weak volume/weak close,
    or prior bar broke and this bar closes back inside (failed breakout).
    """
    empty = {
        "breakout": "—",
        "bo_side": None,
        "bo_level": None,
        "bo_quality": None,
    }
    if i < box_n or box_n < 2:
        return empty
    window = bars[i - box_n : i]
    highs = [_bar_hlc(b)[0] for b in window]
    lows = [_bar_hlc(b)[1] for b in window]
    prior_high = max(highs) if highs else None
    prior_low = min(lows) if lows else None
    if prior_high is None or prior_low is None or prior_high <= prior_low:
        return empty

    high, low, close = _bar_hlc(bars[i])
    spread_wide = bool(avg_spread and avg_spread > 0 and spread >= 1.0 * avg_spread)
    vol_ok = rvol is not None and rvol >= 1.5
    vol_weak = rvol is not None and rvol < 1.0

    # Failed continuation: prior bar closed outside box, this bar back inside
    if i >= box_n + 1:
        prev = bars[i - 1]
        prev_win = bars[i - 1 - box_n : i - 1]
        if len(prev_win) >= box_n:
            ph = max(_bar_hlc(b)[0] for b in prev_win)
            pl = min(_bar_hlc(b)[1] for b in prev_win)
            _, _, prev_c = _bar_hlc(prev)
            if prev_c > ph and close <= ph:
                return {
                    "breakout": "False↑",
                    "bo_side": "up",
                    "bo_level": round(ph, 2),
                    "bo_quality": "false",
                }
            if prev_c < pl and close >= pl:
                return {
                    "breakout": "False↓",
                    "bo_side": "down",
                    "bo_level": round(pl, 2),
                    "bo_quality": "false",
                }

    wick_up = high > prior_high
    wick_dn = low < prior_low
    close_up = close > prior_high
    close_dn = close < prior_low

    if close_up:
        if vol_ok and (spread_wide or close_pos >= 0.60):
            return {
                "breakout": "Correct↑",
                "bo_side": "up",
                "bo_level": round(prior_high, 2),
                "bo_quality": "correct",
            }
        if vol_weak or close_pos < 0.50:
            return {
                "breakout": "False↑",
                "bo_side": "up",
                "bo_level": round(prior_high, 2),
                "bo_quality": "false",
            }
        return {
            "breakout": "Weak↑",
            "bo_side": "up",
            "bo_level": round(prior_high, 2),
            "bo_quality": "weak",
        }

    if close_dn:
        if vol_ok and (spread_wide or close_pos <= 0.40):
            return {
                "breakout": "Correct↓",
                "bo_side": "down",
                "bo_level": round(prior_low, 2),
                "bo_quality": "correct",
            }
        if vol_weak or close_pos > 0.50:
            return {
                "breakout": "False↓",
                "bo_side": "down",
                "bo_level": round(prior_low, 2),
                "bo_quality": "false",
            }
        return {
            "breakout": "Weak↓",
            "bo_side": "down",
            "bo_level": round(prior_low, 2),
            "bo_quality": "weak",
        }

    # Wick-only beyond level → classic false / upthrust / spring probe
    if wick_up and close <= prior_high:
        return {
            "breakout": "False↑",
            "bo_side": "up",
            "bo_level": round(prior_high, 2),
            "bo_quality": "false",
        }
    if wick_dn and close >= prior_low:
        return {
            "breakout": "False↓",
            "bo_side": "down",
            "bo_level": round(prior_low, 2),
            "bo_quality": "false",
        }
    return empty


def _enrich(
    bars: list[dict],
    window: int = CS_CMF,
    rvol_window: int | None = None,
    quote: dict | None = None,
) -> list[dict]:
    """Volume stack — ChartSchool lookbacks as bar counts of the selected interval.

    window      → CMF / UV-DV / OBVΔ / A/DΔ (default 20)
    rvol_window → RVOL / VolZ prior-bar SMA (default 50; excludes current)
    MFI 14 · Force EMA 13 · EMV SMA 14 · VolOsc 5/20 · Chaikin 3/10 · PVO 12/26/9
    — classic, adapted only if history is short.
    """
    out: list[dict] = []
    obv = 0.0
    ad = 0.0
    vpt = 0.0
    force_ema: float | None = None
    force_seed: list[float] = []
    emv_raw: list[float] = []
    # Chaikin Oscillator — EMA(ADL,3) − EMA(ADL,10)
    ad_ema_fast: float | None = None
    ad_ema_slow: float | None = None
    ad_fast_seed: list[float] = []
    ad_slow_seed: list[float] = []
    # PVO — EMA volume 12/26 + signal EMA 9 of PVO
    vol_ema_fast: float | None = None
    vol_ema_slow: float | None = None
    vol_fast_seed: list[float] = []
    vol_slow_seed: list[float] = []
    pvo_sig_ema: float | None = None
    pvo_sig_seed: list[float] = []
    n_bars = len(bars)
    # ChartSchool periods — shrink to available bars (recent listings / IPOs).
    cmf_n = (
        _adapt_period(window or CS_CMF, n_bars, minimum=min(1, n_bars) or 1)
        if n_bars
        else int(window or CS_CMF)
    )
    rvol_n = (
        _adapt_period(
            rvol_window if rvol_window is not None else CS_RVOL,
            max(1, n_bars - 1) if n_bars > 1 else 1,
            minimum=1,
        )
        if n_bars
        else int(rvol_window if rvol_window is not None else CS_RVOL)
    )
    mfi_period = _adapt_period(CS_MFI, n_bars, minimum=min(3, n_bars) if n_bars else 3)
    force_period = _adapt_period(CS_FORCE, n_bars, minimum=min(3, n_bars) if n_bars else 3)
    emv_period = _adapt_period(CS_EMV, n_bars, minimum=min(3, n_bars) if n_bars else 3)
    vo_short, vo_long = _adapt_pair(CS_VO_SHORT, CS_VO_LONG, n_bars, fast_min=2)
    chaikin_fast_n, chaikin_slow_n = _adapt_pair(
        CS_CHAIKIN_FAST, CS_CHAIKIN_SLOW, n_bars, fast_min=2
    )
    pvo_fast_n, pvo_slow_n = _adapt_pair(CS_PVO_FAST, CS_PVO_SLOW, n_bars, fast_min=2)
    pvo_sig_n = _adapt_period(CS_PVO_SIG, n_bars, minimum=min(3, n_bars) if n_bars else 3)
    periods = {
        "rvol": rvol_n,
        "vol_z": rvol_n,
        "cmf": cmf_n,
        "uv_dv": cmf_n,
        "obv_delta": cmf_n,
        "ad_delta": cmf_n,
        "mfi": mfi_period,
        "force": force_period,
        "emv": emv_period,
        "vol_osc_short": vo_short,
        "vol_osc_long": vo_long,
        "chaikin_fast": chaikin_fast_n,
        "chaikin_slow": chaikin_slow_n,
        "pvo_fast": pvo_fast_n,
        "pvo_slow": pvo_slow_n,
        "pvo_signal": pvo_sig_n,
        "donchian": cmf_n,  # Effort/Result + breakout box on selected interval
        "spread": cmf_n,
    }
    for i, bar in enumerate(bars):
        rvol_start = max(0, i - rvol_n)
        cmf_start = max(0, i - cmf_n)
        # RVOL / VolZ: prior bars only (ChartSchool relative volume).
        prior = bars[rvol_start:i]
        sample = [float(item["volume"]) for item in prior if item["volume"] > 0]
        avg = (sum(sample) / len(sample)) if sample else None
        rvol = (float(bar["volume"]) / avg) if avg else None

        vol_z = None
        if len(sample) >= 3:
            mean = sum(sample) / len(sample)
            var = sum((v - mean) ** 2 for v in sample) / len(sample)
            std = var**0.5
            if std > 0:
                vol_z = (float(bar["volume"]) - mean) / std

        # OBV (Granville / ChartSchool)
        if i == 0:
            obv = float(bar["volume"])
        else:
            prev_close = bars[i - 1]["close"]
            if bar["close"] > prev_close:
                obv += bar["volume"]
            elif bar["close"] < prev_close:
                obv -= bar["volume"]

        # Accumulation / Distribution (Chaikin)
        mfm = _money_flow_multiplier(bar.get("high"), bar.get("low"), bar["close"])
        mfv = mfm * bar["volume"]
        ad += mfv

        # Chaikin Oscillator = EMA(ADL,3) − EMA(ADL,10) — ChartSchool
        ad_ema_fast, ad_fast_out = _sma_seeded_ema_step(
            ad, chaikin_fast_n, ad_fast_seed, ad_ema_fast
        )
        ad_ema_slow, ad_slow_out = _sma_seeded_ema_step(
            ad, chaikin_slow_n, ad_slow_seed, ad_ema_slow
        )
        chaikin = (
            (ad_fast_out - ad_slow_out)
            if ad_fast_out is not None and ad_slow_out is not None
            else None
        )

        # PVO(12/26/9) — ChartSchool Percentage Volume Oscillator
        vol_f = float(bar["volume"] or 0)
        vol_ema_fast, vol_fast_out = _sma_seeded_ema_step(
            vol_f, pvo_fast_n, vol_fast_seed, vol_ema_fast
        )
        vol_ema_slow, vol_slow_out = _sma_seeded_ema_step(
            vol_f, pvo_slow_n, vol_slow_seed, vol_ema_slow
        )
        pvo = None
        pvo_signal = None
        pvo_hist = None
        if vol_fast_out is not None and vol_slow_out is not None and vol_slow_out > 0:
            pvo = 100.0 * (vol_fast_out - vol_slow_out) / vol_slow_out
            pvo_sig_ema, pvo_sig_out = _sma_seeded_ema_step(
                pvo, pvo_sig_n, pvo_sig_seed, pvo_sig_ema
            )
            if pvo_sig_out is not None:
                pvo_signal = pvo_sig_out
                pvo_hist = pvo - pvo_signal

        # VPT
        if i > 0 and bars[i - 1]["close"]:
            vpt += bar["volume"] * (bar["close"] - bars[i - 1]["close"]) / bars[i - 1]["close"]

        # Elder Force Index — ChartSchool: FI(1)=(C−Cprev)×V ; FI(13)=EMA seeded with SMA
        force_out: float | None = None
        if i > 0:
            force_raw = (bar["close"] - bars[i - 1]["close"]) * float(bar["volume"])
            if force_ema is None:
                force_seed.append(force_raw)
                if len(force_seed) >= force_period:
                    force_ema = sum(force_seed) / len(force_seed)
                    force_out = force_ema
                elif force_seed:
                    force_out = sum(force_seed) / len(force_seed)
            else:
                force_ema = _ema_next(force_ema, force_raw, force_period)
                force_out = force_ema

        # Arms Ease of Movement — ChartSchool EMV(14) = SMA of 1-period EMV
        emv = None
        if i > 0:
            high = bar.get("high") if bar.get("high") is not None else bar["close"]
            low = bar.get("low") if bar.get("low") is not None else bar["close"]
            prev_high = bars[i - 1].get("high")
            prev_low = bars[i - 1].get("low")
            prev_high = prev_high if prev_high is not None else bars[i - 1]["close"]
            prev_low = prev_low if prev_low is not None else bars[i - 1]["close"]
            distance = ((high + low) / 2.0) - ((prev_high + prev_low) / 2.0)
            span = high - low
            box = (float(bar["volume"]) / 100_000_000.0) / span if span > 0 else None
            raw_emv = (distance / box) if box else 0.0
            emv_raw.append(raw_emv)
            if len(emv_raw) >= emv_period:
                emv = sum(emv_raw[-emv_period:]) / emv_period

        # Volume Oscillator % — ChartSchool SMA(V,5) vs SMA(V,20) on consecutive bars
        vol_osc = None
        if i + 1 >= vo_long:
            chunk = [float(b["volume"] or 0) for b in bars[i + 1 - vo_long : i + 1]]
            long_avg = sum(chunk) / vo_long
            short_avg = sum(chunk[-vo_short:]) / vo_short
            if long_avg > 0:
                vol_osc = 100.0 * (short_avg - long_avg) / long_avg

        # CMF(20) — ChartSchool (including current bar)
        cmf_slice = out[cmf_start:i]
        cmf_mfv = sum(
            _money_flow_multiplier(item.get("high"), item.get("low"), item["close"]) * item["volume"]
            for item in cmf_slice
        ) + mfv
        cmf_vol = sum(item["volume"] for item in cmf_slice) + bar["volume"]
        cmf = (cmf_mfv / cmf_vol) if cmf_vol else None

        # MFI (typical price money flow) — ChartSchool
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
        ad_rising = None
        if i >= cmf_n and out:
            obv_rising = obv > out[i - cmf_n]["obv"]
            ad_rising = ad > out[i - cmf_n]["ad"]

        # OBV vs price divergence label (ChartSchool interpretation)
        obv_div = None
        if obv_rising is not None:
            if obv_rising and not bar["up"]:
                obv_div = "bull"
            elif (not obv_rising) and bar["up"]:
                obv_div = "bear"

        window_bars = out[cmf_start:i]
        up_vol = sum(item["volume"] for item in window_bars if item.get("up"))
        down_vol = sum(item["volume"] for item in window_bars if not item.get("up"))
        if bar["up"]:
            up_vol += bar["volume"]
        else:
            down_vol += bar["volume"]
        vol_ratio = (up_vol / down_vol) if down_vol > 0 else (None if up_vol == 0 else 99.0)

        # Effort vs Result + Correct/False breakout (Wyckoff — bar counts of this TF)
        spread = _bar_spread(bar)
        close_pos = _close_location(bar)
        prior_spreads = [_bar_spread(b) for b in bars[cmf_start:i]]
        avg_spread = (sum(prior_spreads) / len(prior_spreads)) if prior_spreads else None
        er = _effort_result(rvol, spread, avg_spread, close_pos)
        bo = _breakout_quality(bars, i, cmf_n, rvol, close_pos, spread, avg_spread)

        score = _volume_score(
            bool(bar["up"]),
            rvol,
            obv_rising,
            vol_ratio,
            cmf,
            mfi,
            force=force_out,
            emv=emv,
            vol_z=vol_z,
            ad_rising=ad_rising,
            chaikin=chaikin,
            pvo_hist=pvo_hist,
            er_label=er.get("er"),
            bo_quality=bo.get("bo_quality"),
            bo_side=bo.get("bo_side"),
        )
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
        enriched["vol_z"] = round(vol_z, 2) if vol_z is not None else None
        enriched["spike"] = bool(
            (rvol is not None and rvol >= 1.5) or (vol_z is not None and vol_z >= 2.0)
        )
        enriched["tone"] = _vol_tone(enriched["rvol"], enriched["vol_z"])
        enriched["obv"] = int(round(obv))
        enriched["obv_rising"] = obv_rising
        enriched["obv_div"] = obv_div
        enriched["ad"] = int(round(ad))
        enriched["ad_rising"] = ad_rising
        enriched["cmf"] = round(cmf, 3) if cmf is not None else None
        enriched["mfi"] = round(mfi, 1) if mfi is not None else None
        enriched["vpt"] = int(round(vpt))
        enriched["force"] = round(force_out, 1) if force_out is not None else None
        enriched["emv"] = round(emv, 4) if emv is not None else None
        enriched["vol_osc"] = round(vol_osc, 1) if vol_osc is not None else None
        enriched["chaikin"] = round(chaikin, 1) if chaikin is not None else None
        enriched["pvo"] = round(pvo, 2) if pvo is not None else None
        enriched["pvo_signal"] = round(pvo_signal, 2) if pvo_signal is not None else None
        enriched["pvo_hist"] = round(pvo_hist, 2) if pvo_hist is not None else None
        enriched["vol_ratio"] = round(vol_ratio, 2) if vol_ratio is not None else None
        enriched["effort"] = er.get("effort")
        enriched["result"] = er.get("result")
        enriched["er"] = er.get("er")
        enriched["er_tone"] = er.get("er_tone")
        enriched["spread_x"] = er.get("spread_x")
        enriched["close_pos"] = er.get("close_pos")
        enriched["breakout"] = bo.get("breakout")
        enriched["bo_side"] = bo.get("bo_side")
        enriched["bo_level"] = bo.get("bo_level")
        enriched["bo_quality"] = bo.get("bo_quality")
        enriched["score"] = round(score, 1)
        enriched["bias"] = bias
        enriched["strength"] = strength
        enriched["periods"] = periods

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
            "vol_z": enriched["vol_z"],
            "avg_vol": enriched["avg_vol"],
            "move": move,
            "tone": enriched["tone"],
            "bias": enriched["bias"],
            "score": enriched["score"],
            "strength": enriched["strength"],
            "obv_rising": enriched["obv_rising"],
            "obv_div": enriched["obv_div"],
            "ad_rising": enriched["ad_rising"],
            "vol_ratio": enriched["vol_ratio"],
            "cmf": enriched["cmf"],
            "mfi": enriched["mfi"],
            "ad": enriched["ad"],
            "vpt": enriched["vpt"],
            "force": enriched["force"],
            "emv": enriched["emv"],
            "vol_osc": enriched["vol_osc"],
            "chaikin": enriched["chaikin"],
            "pvo": enriched["pvo"],
            "pvo_signal": enriched["pvo_signal"],
            "pvo_hist": enriched["pvo_hist"],
            "effort": enriched["effort"],
            "result": enriched["result"],
            "er": enriched["er"],
            "er_tone": enriched["er_tone"],
            "spread_x": enriched["spread_x"],
            "close_pos": enriched["close_pos"],
            "breakout": enriched["breakout"],
            "bo_side": enriched["bo_side"],
            "bo_level": enriched["bo_level"],
            "bo_quality": enriched["bo_quality"],
            "delivery_pct": delivery,
            "high": enriched.get("high"),
            "low": enriched.get("low"),
            "periods": periods,
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
        "correct_break": sum(1 for bar in bars if bar.get("bo_quality") == "correct"),
        "false_break": sum(1 for bar in bars if bar.get("bo_quality") == "false"),
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
        "avg_vol": (last or {}).get("avg_vol")
        or int(_num(quote.get("DVolAvg20")) or 0)
        or None,
        # Legacy alias (was always named _20 even when RVOL window ≠ 20).
        "avg_vol_20": (last or {}).get("avg_vol")
        or int(_num(quote.get("DVolAvg20")) or 0)
        or None,
        "periods": (last or {}).get("periods"),
        "rvol": (last or {}).get("rvol"),
        "tone": (last or {}).get("tone") or "normal",
        "bias": (last or {}).get("bias") or "neutral",
        "score": (last or {}).get("score"),
        "strength": (last or {}).get("strength") or "weak",
        "obv": (last or {}).get("obv"),
        "obv_rising": (last or {}).get("obv_rising"),
        "obv_div": (last or {}).get("obv_div"),
        "ad_rising": (last or {}).get("ad_rising"),
        "vol_ratio": (last or {}).get("vol_ratio"),
        "cmf": (last or {}).get("cmf"),
        "mfi": (last or {}).get("mfi"),
        "ad": (last or {}).get("ad"),
        "vpt": (last or {}).get("vpt"),
        "force": (last or {}).get("force"),
        "emv": (last or {}).get("emv"),
        "vol_osc": (last or {}).get("vol_osc"),
        "chaikin": (last or {}).get("chaikin"),
        "pvo": (last or {}).get("pvo"),
        "pvo_signal": (last or {}).get("pvo_signal"),
        "pvo_hist": (last or {}).get("pvo_hist"),
        "effort": (last or {}).get("effort"),
        "result": (last or {}).get("result"),
        "er": (last or {}).get("er"),
        "er_tone": (last or {}).get("er_tone"),
        "spread_x": (last or {}).get("spread_x"),
        "close_pos": (last or {}).get("close_pos"),
        "breakout": (last or {}).get("breakout"),
        "bo_side": (last or {}).get("bo_side"),
        "bo_level": (last or {}).get("bo_level"),
        "bo_quality": (last or {}).get("bo_quality"),
        "vol_z": (last or {}).get("vol_z"),
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
    return _history_to_tf_bars(raw, tf_id)


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

    wins = _tf_study_windows(tf_id)
    bars = _enrich(
        bars_raw,
        window=wins["avg_window"],
        rvol_window=wins["rvol_window"],
        quote=quote,
    )
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
    preferred_win = max(wins["avg_window"], wins["rvol_window"])
    hist = _history_meta(len(bars), preferred_win + 1)
    stats.update(hist)
    payload = {
        "as_of": _ist_stamp(),
        "cached": False,
        "session": session_status(),
        "timeframe": tf_id,
        "timeframe_label": tf["label"],
        "tf_meta": _tf_meta(tf_id),
        "formulas": FORMULAS,
        "volume_available": volume_available,
        **hist,
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
    wins = _tf_study_windows(tf_id)
    bars = _enrich(
        _load_bars(
            preset["nse"],
            tf_id,
            exchange=preset.get("exchange") or "NSE",
            fast=True,
        ),
        window=wins["avg_window"],
        rvol_window=wins["rvol_window"],
    )
    if not bars:
        return None
    last = bars[-1]
    preferred = max(wins["avg_window"], wins["rvol_window"])
    hist = _history_meta(len(bars), preferred + 1)
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
    study.update(hist)
    row = {
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
        "obv_div": last.get("obv_div"),
        "ad_rising": last.get("ad_rising"),
        "vol_ratio": last.get("vol_ratio"),
        "cmf": last.get("cmf"),
        "mfi": last.get("mfi"),
        "ad": last.get("ad"),
        "vpt": last.get("vpt"),
        "force": last.get("force"),
        "emv": last.get("emv"),
        "vol_osc": last.get("vol_osc"),
        "chaikin": last.get("chaikin"),
        "pvo": last.get("pvo"),
        "pvo_signal": last.get("pvo_signal"),
        "pvo_hist": last.get("pvo_hist"),
        "effort": last.get("effort"),
        "result": last.get("result"),
        "er": last.get("er"),
        "er_tone": last.get("er_tone"),
        "spread_x": last.get("spread_x"),
        "close_pos": last.get("close_pos"),
        "breakout": last.get("breakout"),
        "bo_side": last.get("bo_side"),
        "bo_level": last.get("bo_level"),
        "bo_quality": last.get("bo_quality"),
        "vol_z": last.get("vol_z"),
        "spike": last.get("spike"),
        "periods": last.get("periods") or study.get("periods"),
        "close": last["close"],
        "change_pct": last["change_pct"],
        "up": last["up"],
        "label": last["label"],
        "delivery_pct": _num(quote.get("AvgDelVolPer_5day")),
        **hist,
        "study": study,
    }
    _apply_tf_change(row, quote, tf_id, bars=bars)
    if row.get("study") is not None and row.get("change_pct") is not None:
        chg = float(row["change_pct"])
        row["study"]["move"] = f"{'+' if chg >= 0 else ''}{chg:.2f}%"
    return row


# --- Technical Desk: classic OHLC indicators ---------------------------------

TECH_INDICATORS = [
    "rsi",
    "macd",
    "ppo",
    "sma",
    "sma200",
    "ema",
    "bb",
    "stoch",
    "cci",
    "willr",
    "adx",
    "aroon",
    "roc",
]

# Default Technical score set — core + high-value ChartSchool scan KPIs (PPO · Aroon · 50/200).
TECH_CORE_INDICATORS = [
    "rsi",
    "macd",
    "ppo",
    "sma",
    "sma200",
    "ema",
    "stoch",
    "adx",
    "aroon",
    "bb",
    "roc",
]

# Wilder / Appel / Bollinger / Chande defaults — periods are bars of the active TF.
TECH_FORMULAS = {
    "timeframe": (
        "All Technical periods are ChartSchool bar-counts on the selected chip’s resolution "
        "(not calendar days). "
        "Intraday 15m/1H/4H → that many 15m/60m/4h bars; "
        "Swing 1D/1W/1M → days/weeks/months; "
        "Long 3M/6M/1Y → daily bars (same math as 1D); 5Y/Max → weekly. "
        "Defaults: RSI(14) · MACD(12/26/9) · PPO(12/26/9) · SMA(20/50) · SMA(50/200) · "
        "EMA(20) · BB(20,2) · Full Stoch(14/3/3) · CCI(20) · %R(14) · ADX(14) · "
        "Aroon(25) · ROC(12) · ATR(14)."
    ),
    "rsi": (
        "Wilder RSI(14): first AvgGain/AvgLoss = SMA of first 14 changes; then "
        "Avg = (Prev×13 + Current)/14; RSI = 100 − 100/(1+AvgGain/AvgLoss). "
        "Score: ≥60 +2 · ≥55 +1 · ≤45 −1 · ≤40 −2 (ChartSchool RSI)."
    ),
    "macd": (
        "Appel MACD: EMA(12)−EMA(26) of close (EMA seeded with SMA); "
        "Signal = EMA(9) of MACD; Hist = MACD−Signal. "
        "Score: Hist>0 & MACD>Signal +1/+2 · opposite −1/−2. "
        "If PPO is also selected, MACD is shown but not double-counted in Score."
    ),
    "ppo": (
        "ChartSchool PPO(12/26/9): ((EMA12−EMA26)/EMA26)×100; Signal=EMA9(PPO); "
        "Hist=PPO−Signal. Preferred over MACD for comparing stocks (percentage scale). "
        "Score: Hist>0 & PPO>Signal +1/+2 · opposite −1/−2 "
        "(when both MACD+PPO selected, Score uses PPO only)."
    ),
    "sma": (
        "SMA(n)=mean(close,n) on selected bars. Score: SMA20>SMA50 +1 · SMA20<SMA50 −1 "
        "(ChartSchool moving averages)."
    ),
    "sma200": (
        "ChartSchool Golden/Death Cross bias: SMA50 vs SMA200 (exact periods — needs ≥200 bars). "
        "Score: SMA50>SMA200 +2 · SMA50<SMA200 −2. Blank on short history (e.g. many intraday series)."
    ),
    "ema": (
        "EMA(n): seed=SMA(n); then EMA=Prev+α×(Close−Prev), α=2/(n+1). "
        "Score: Close>EMA20 +1 · Close<EMA20 −1."
    ),
    "bb": (
        "Bollinger(20,2): Mid=SMA20; Upper/Lower=Mid±2σ (σ of last 20 closes); "
        "%B=(C−Lower)/(Upper−Lower). Score: %B≥0.8 +2 · ≥0.5 +1 · ≤0.2 −2 · <0.5 −1 "
        "(ChartSchool Bollinger %B — position in band, not a standalone reverse signal)."
    ),
    "stoch": (
        "ChartSchool Full Stochastic(14,3,3): Fast%K=100×(C−LL14)/(HH14−LL14); "
        "Full%K=SMA(Fast%K,3); %D=SMA(Full%K,3). Table Stoch = Full%K. "
        "Score: ≥80 +2 · ≥50 +1 · ≤20 −2 · <50 −1."
    ),
    "cci": (
        "CCI(20)=(TP−SMA20(TP))/(0.015×MeanDeviation); TP=(H+L+C)/3. "
        "Score: ≥100 +2 · >0 +1 · ≤−100 −2 · <0 −1 (Lambert / ChartSchool CCI)."
    ),
    "willr": (
        "Williams %R(14)=−100×(HH14−C)/(HH14−LL14). "
        "Score: ≥−20 +2 · ≥−50 +1 · ≤−80 −2 · <−50 −1 (ChartSchool Williams %R)."
    ),
    "adx": (
        "Wilder +DI/−DI/ADX(14): TR, +DM, −DM smoothed like ATR; "
        "+DI=100×+DM/ATR; DX=100×|+DI−−DI|/(+DI+−DI); ADX=Wilder smooth of DX. "
        "Score: +DI>−DI +1 (−1 if opposite); ADX≥25 doubles to ±2."
    ),
    "aroon": (
        "Chande Aroon(25): Up=((25−bars since HH25)/25)×100; Down=((25−bars since LL25)/25)×100; "
        "Osc=Up−Down. Score: Osc≥50 +2 · Up>Down +1 · Osc≤−50 −2 · Up<Down −1 (ChartSchool Aroon)."
    ),
    "roc": (
        "ROC(12)=100×(C−C₁₂)/C₁₂ on selected bars. "
        "Score: ≥+3% +2 · >0 +1 · ≤−3% −2 · <0 −1 (ChartSchool ROC)."
    ),
    "atr": (
        "ATR(14) Wilder: TR=max(H−L,|H−Cprev|,|L−Cprev|); first ATR=SMA(TR,14); "
        "then (Prev×13+TR)/14. ATR%=100×ATR/Close (ChartSchool ATR / ATRP)."
    ),
    "setup": (
        "Setup (display, not in score): Thin if <8 bars (recent listing); "
        "Overbought if RSI≥70 or Stoch≥80 or %B≥1; "
        "Oversold if RSI≤30 or Stoch≤20 or %B≤0; "
        "Trend↑/↓ if SMA stack + Close vs EMA20 (+ ADX≥20 & DI / Aroon when strong); "
        "Momentum↑/↓ from RSI+MACD+Stoch; else Range."
    ),
    "score": (
        "Score = (Σ selected votes) / (2×N) × 100, clamped ±100. "
        "Each selected Signal votes −2…+2 (N = voting Signals with data). "
        "MACD+PPO together → PPO only (same Appel signal). "
        "Recent listings: periods shrink to available bars; Signals that still lack "
        "lookback are skipped (e.g. SMA50/200 needs ≥200 bars). "
        "Bias: ≥+30 bullish · ≤−30 bearish · else neutral."
    ),
    "history": (
        "history=full when bars cover ChartSchool windows (≥~55–200); "
        "partial when periods are shrunk; thin when <8 bars (IPO / new listing). "
        "Stochastic falls back to Fast %K if Full(14/3/3) does not fit."
    ),
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
        "id": "ppo",
        "name": "PPO",
        "ref": "ChartSchool Percentage Price Oscillator (scan-comparable MACD)",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/percentage-price-oscillator-ppo",
    },
    {
        "id": "ma",
        "name": "SMA / EMA / Golden Cross",
        "ref": "ChartSchool moving averages · Golden / Death Cross",
        "url": "https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-average-trading-strategies/trading-using-the-golden-cross",
    },
    {
        "id": "aroon",
        "name": "Aroon",
        "ref": "Tushar Chande — ChartSchool Aroon",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/aroon",
    },
    {
        "id": "adx",
        "name": "ADX",
        "ref": "J. Welles Wilder — ChartSchool ADX",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-directional-index-adx",
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
    """Shrink a lookback to fit available bars (IPO / short history).

    Always returns a value in ``[1, n]`` when ``n > 0`` — never exceeds bar count
    (avoids SMA(21) on 20 bars and similar silent None results).
    """
    if n <= 0:
        return max(1, int(minimum))
    pref = max(1, int(preferred))
    lo = max(1, min(int(minimum), n))
    return max(lo, min(pref, n))


def _history_meta(n: int, full_need: int, *, thin_bars: int = 8) -> dict:
    """Shared recent-listing flag for every desk (Volume · Technical · Lab · Chart).

    thin     — fewer than ``thin_bars`` (IPO / brand-new series)
    partial  — some ChartSchool windows still truncated
    full     — enough bars for preferred lookbacks
    """
    bars = max(0, int(n))
    need = max(1, int(full_need))
    # Yahoo 2y/5y/10y daily counts land a few sessions under a 252-day year.
    slack = max(12, int(round(need * 0.025))) if need >= 240 else 0
    if bars < thin_bars:
        hist = "thin"
    elif bars + slack < need:
        hist = "partial"
    else:
        hist = "full"
    return {
        "history": hist,
        "partial_history": hist != "full",
        "bars_used": bars,
        "history_need": need,
    }


def _adapt_pair(fast_pref: int, slow_pref: int, n: int, *, fast_min: int = 2) -> tuple[int, int]:
    """Fast/slow periods both ≤ n with fast < slow when possible (IPO-safe)."""
    if n <= 0:
        return 1, 1
    fast = _adapt_period(fast_pref, n, minimum=min(fast_min, n))
    slow = _adapt_period(slow_pref, n, minimum=min(n, fast + 1 if fast < n else n))
    if slow <= fast:
        if n > fast:
            slow = n
        elif slow > 1:
            fast = slow - 1
        else:
            fast = 1
    return fast, slow


def _tech_lookbacks(n: int, prefs: dict[str, int]) -> dict[str, int]:
    """ChartSchool preferred periods, coherently shrunk for short / IPO history.

    Every returned period is ≤ ``n`` (or ≤ n−1 for RSI/ROC which need a prior bar).
    """
    n = max(1, int(n))
    # RSI / ROC need a prior close.
    p_rsi = _adapt_period(prefs["rsi"], max(1, n - 1), minimum=min(2, max(1, n - 1))) if n >= 2 else 1
    p_ema = _adapt_period(prefs["ema"], n, minimum=min(2, n))
    # MACD/PPO: keep fast < slow ≤ n; leave room for signal when possible.
    p_sig = _adapt_period(prefs["sig"], n, minimum=min(2, n))
    ideal_slow = min(prefs["slow"], max(2, n - p_sig + 1))
    p_slow = _adapt_period(ideal_slow, n, minimum=min(2, n))
    ideal_fast = min(prefs["fast"], max(1, p_slow - 1), max(1, n // 2))
    p_fast = _adapt_period(ideal_fast, n, minimum=1)
    if p_fast >= p_slow and p_slow > 1:
        p_fast = p_slow - 1
    # SMA stack: fast < slow, both ≤ n.
    p_sma_f = _adapt_period(prefs["sma_f"], n, minimum=min(2, n))
    p_sma_s = _adapt_period(prefs["sma_s"], n, minimum=min(n, p_sma_f + 1 if p_sma_f < n else n))
    if p_sma_s <= p_sma_f:
        if n > p_sma_f:
            p_sma_s = n
        elif p_sma_s > 1:
            p_sma_f = p_sma_s - 1
        else:
            p_sma_f = 1
    p_bb = _adapt_period(prefs.get("bb", CS_BB), n, minimum=min(2, n))
    p_stoch = _adapt_period(prefs["stoch"], n, minimum=min(2, n))
    p_stoch_slow = _adapt_period(prefs.get("stoch_slow", CS_STOCH_SLOW), n, minimum=1)
    while p_stoch + p_stoch_slow - 1 > n and p_stoch_slow > 1:
        p_stoch_slow -= 1
    while p_stoch + p_stoch_slow - 1 > n and p_stoch > 1:
        p_stoch -= 1
    p_cci = _adapt_period(prefs["cci"], n, minimum=min(2, n))
    p_roc = _adapt_period(prefs["roc"], max(1, n - 1), minimum=1) if n >= 2 else 1
    p_adx = _adapt_period(prefs["adx"], n, minimum=min(3, n))
    p_atr = _adapt_period(prefs.get("atr", CS_ATR), n, minimum=min(2, n))
    p_aroon = _adapt_period(prefs.get("aroon", CS_AROON), n, minimum=min(2, n))
    return {
        "rsi": max(1, p_rsi),
        "ema": p_ema,
        "fast": max(1, p_fast),
        "slow": max(1, p_slow),
        "sig": max(1, p_sig),
        "sma_f": p_sma_f,
        "sma_s": p_sma_s,
        "bb": p_bb,
        "stoch": p_stoch,
        "stoch_slow": p_stoch_slow,
        "cci": p_cci,
        "roc": p_roc,
        "adx": p_adx,
        "atr": p_atr,
        "aroon": p_aroon,
        "sma_l": prefs.get("sma_l", CS_SMA_LONG),
    }


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


def _stoch_fast_k_at(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    end: int,
    period: int,
) -> float | None:
    """Fast %K at index `end` over `period` bars (ChartSchool Stochastic)."""
    start = end - period + 1
    if start < 0 or end >= len(closes):
        return None
    hh = max(highs[start : end + 1])
    ll = min(lows[start : end + 1])
    if hh <= ll:
        return 50.0
    return ((closes[end] - ll) / (hh - ll)) * 100.0


def _stoch_k(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
    smooth: int = 3,
) -> float | None:
    """ChartSchool Full Stochastic %K: SMA(smooth) of Fast %K(period). Default 14/3."""
    smooth = max(1, int(smooth))
    need = period + smooth - 1
    if len(closes) < need:
        return None
    vals: list[float] = []
    for end in range(len(closes) - smooth, len(closes)):
        fk = _stoch_fast_k_at(highs, lows, closes, end, period)
        if fk is None:
            return None
        vals.append(fk)
    return sum(vals) / smooth


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


def _aroon_at(
    highs: list[float], lows: list[float], period: int = 25
) -> tuple[float | None, float | None, float | None]:
    """ChartSchool Aroon(period): Up, Down, Oscillator = Up − Down."""
    if period <= 0 or len(highs) < period or len(lows) < period:
        return None, None, None
    window_h = highs[-period:]
    window_l = lows[-period:]
    # Days since high/low within the window (0 = today is the extreme).
    hh = max(window_h)
    ll = min(window_l)
    since_high = period - 1 - max(i for i, v in enumerate(window_h) if v == hh)
    since_low = period - 1 - max(i for i, v in enumerate(window_l) if v == ll)
    up = ((period - since_high) / period) * 100.0
    down = ((period - since_low) / period) * 100.0
    return up, down, up - down


def _atr_last(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float | None:
    """Wilder ATR(period) — ChartSchool Average True Range."""
    n = len(closes)
    if period <= 0 or n < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if len(trs) < period:
        return None
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


def _tech_setup(ind: dict) -> str:
    """Confluence label for scanning — ChartSchool trend / momentum / extremes."""
    rsi = ind.get("rsi")
    hist = ind.get("macd_hist")
    macd = ind.get("macd")
    signal = ind.get("macd_signal")
    sma20 = ind.get("sma20")
    sma50 = ind.get("sma50")
    ema20 = ind.get("ema20")
    close = ind.get("close")
    stoch = ind.get("stoch_k")
    bb = ind.get("bb_pctb")
    plus_di = ind.get("plus_di")
    minus_di = ind.get("minus_di")
    adx = ind.get("adx")

    overbought = (
        (rsi is not None and rsi >= 70)
        or (stoch is not None and stoch >= 80)
        or (bb is not None and bb >= 1.0)
    )
    oversold = (
        (rsi is not None and rsi <= 30)
        or (stoch is not None and stoch <= 20)
        or (bb is not None and bb <= 0.0)
    )
    if overbought and not oversold:
        return "Overbought"
    if oversold and not overbought:
        return "Oversold"

    stack_up = sma20 is not None and sma50 is not None and sma20 > sma50
    stack_dn = sma20 is not None and sma50 is not None and sma20 < sma50
    above_ema = close is not None and ema20 is not None and close > ema20
    below_ema = close is not None and ema20 is not None and close < ema20
    di_up = plus_di is not None and minus_di is not None and plus_di > minus_di
    di_dn = plus_di is not None and minus_di is not None and plus_di < minus_di
    trend_ok = adx is not None and adx >= 20
    aroon_osc = ind.get("aroon_osc")
    aroon_up = aroon_osc is not None and aroon_osc >= 50
    aroon_dn = aroon_osc is not None and aroon_osc <= -50
    gold = ind.get("sma50") is not None and ind.get("sma200") is not None and ind["sma50"] > ind["sma200"]
    death = ind.get("sma50") is not None and ind.get("sma200") is not None and ind["sma50"] < ind["sma200"]
    if stack_up and above_ema and (di_up or aroon_up or gold) and trend_ok:
        return "Trend↑"
    if stack_dn and below_ema and (di_dn or aroon_dn or death) and trend_ok:
        return "Trend↓"

    macd_up = hist is not None and signal is not None and macd is not None and hist > 0 and macd > signal
    macd_dn = hist is not None and signal is not None and macd is not None and hist < 0 and macd < signal
    rsi_up = rsi is not None and rsi >= 55
    rsi_dn = rsi is not None and rsi <= 45
    st_up = stoch is not None and stoch >= 50
    st_dn = stoch is not None and stoch < 50
    if macd_up and rsi_up and st_up:
        return "Momentum↑"
    if macd_dn and rsi_dn and st_dn:
        return "Momentum↓"
    if stack_up and above_ema:
        return "Trend↑"
    if stack_dn and below_ema:
        return "Trend↓"
    if macd_up or rsi_up:
        return "Momentum↑"
    if macd_dn or rsi_dn:
        return "Momentum↓"
    return "Range"


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
    ppo = ind.get("ppo")
    ppo_sig = ind.get("ppo_signal")
    ppo_hist = ind.get("ppo_hist")
    if ppo is not None and ppo_sig is not None and ppo_hist is not None:
        if ppo_hist > 0 and ppo > ppo_sig:
            votes.append(("ppo", 2 if ppo_hist > abs(ppo) * 0.05 else 1))
        elif ppo_hist < 0 and ppo < ppo_sig:
            votes.append(("ppo", -2 if ppo_hist < -abs(ppo) * 0.05 else -1))
        else:
            votes.append(("ppo", 0))
    sma20 = ind.get("sma20")
    sma50 = ind.get("sma50")
    if sma20 is not None and sma50 is not None:
        votes.append(("sma", 1 if sma20 > sma50 else -1 if sma20 < sma50 else 0))
    sma200 = ind.get("sma200")
    if sma50 is not None and sma200 is not None:
        # ChartSchool Golden / Death Cross bias (strong long-term filter).
        votes.append(("sma200", 2 if sma50 > sma200 else -2 if sma50 < sma200 else 0))
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
    aroon_up = ind.get("aroon_up")
    aroon_dn = ind.get("aroon_down")
    aroon_osc = ind.get("aroon_osc")
    if aroon_osc is not None and aroon_up is not None and aroon_dn is not None:
        if aroon_osc >= 50:
            votes.append(("aroon", 2))
        elif aroon_up > aroon_dn:
            votes.append(("aroon", 1))
        elif aroon_osc <= -50:
            votes.append(("aroon", -2))
        elif aroon_up < aroon_dn:
            votes.append(("aroon", -1))
        else:
            votes.append(("aroon", 0))
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
    """Scale selected votes to −100…+100.

    Each vote is −2…+2. Denominator = 2×N so a full-strength panel → ±100.
    ChartSchool: PPO is the %-form of MACD — when both are selected for scoring,
    only PPO is counted so the Appel signal is not double-weighted.
    """
    if selected:
        allow = set(selected)
        votes = [(name, val) for name, val in votes if name in allow]
    names = {name for name, _ in votes}
    if "macd" in names and "ppo" in names:
        votes = [(name, val) for name, val in votes if name != "macd"]
    if not votes:
        return 0.0
    raw = sum(v for _, v in votes)
    denom = max(2.0 * len(votes), 1.0)
    return max(-100.0, min(100.0, (raw / denom) * 100.0))


def _tech_enrich(
    bars: list[dict],
    indicators: list[str] | None = None,
    tf_id: str = "1d",
) -> dict | None:
    """Technical study on available bars — works for recent listings / IPOs.

    Periods shrink to fit history. Signals that still cannot compute are omitted
    from Score (denom shrinks). ``history`` = full | partial | thin.
    """
    # Need at least 2 bars for a directional change; 1 bar → price-only thin row.
    if not bars:
        return None
    closes = [float(b["close"]) for b in bars]
    highs = [
        float(b["high"] if b.get("high") is not None else b["close"]) for b in bars
    ]
    lows = [float(b["low"] if b.get("low") is not None else b["close"]) for b in bars]
    last = bars[-1]
    n = len(closes)
    prefs = _tech_period_prefs(tf_id)
    full_need = max(prefs["sma_s"] + 1, prefs["slow"] + prefs["sig"] + 2, prefs.get("sma_l", CS_SMA_LONG), 55)
    lb = _tech_lookbacks(n, prefs)
    p_rsi = lb["rsi"]
    p_ema = lb["ema"]
    p_fast, p_slow, p_sig = lb["fast"], lb["slow"], lb["sig"]
    p_sma_f, p_sma_s = lb["sma_f"], lb["sma_s"]
    p_sma_l = lb["sma_l"]
    p_bb = lb["bb"]
    p_stoch, p_stoch_slow = lb["stoch"], lb["stoch_slow"]
    p_cci, p_roc = lb["cci"], lb["roc"]
    p_adx, p_atr, p_aroon = lb["adx"], lb["atr"], lb["aroon"]

    ema20_s = _ema_series(closes, p_ema) if n >= p_ema else [None] * n
    ema12_s = _ema_series(closes, p_fast) if n >= p_fast else [None] * n
    ema26_s = _ema_series(closes, p_slow) if n >= p_slow else [None] * n
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
    # ChartSchool PPO — percent form of MACD (comparable across prices).
    ppo_line: list[float | None] = [
        ((ema12_s[i] - ema26_s[i]) / ema26_s[i] * 100.0)
        if ema12_s[i] is not None and ema26_s[i] not in (None, 0)
        else None
        for i in range(n)
    ]
    ppo_vals = [x for x in ppo_line if x is not None]
    ppo_signal_series: list[float | None] = [None] * n
    if len(ppo_vals) >= p_sig:
        first_p = next(i for i, x in enumerate(ppo_line) if x is not None)
        compact_p = _ema_series(ppo_vals, p_sig)
        for j, val in enumerate(compact_p):
            if val is not None:
                ppo_signal_series[first_p + j] = val
    rsi_s = _rsi_series(closes, p_rsi) if n > p_rsi else [None] * n
    sma20 = _sma_at(closes, p_sma_f)
    sma50 = _sma_at(closes, p_sma_s)
    # Exact SMA50/200 for Golden Cross when history allows; else null (never fake).
    sma50_x = _sma_at(closes, CS_SMA_SLOW) if n >= CS_SMA_SLOW else None
    sma200 = _sma_at(closes, p_sma_l) if n >= p_sma_l else None
    ema20 = ema20_s[-1] if ema20_s else None
    macd = macd_line[-1]
    macd_signal = signal_series[-1]
    macd_hist = (
        (macd - macd_signal) if macd is not None and macd_signal is not None else None
    )
    # Short history: if signal EMA not ready yet, lean on MACD vs zero (centerline).
    if macd_hist is None and macd is not None and n < full_need:
        macd_signal = 0.0
        macd_hist = macd
    ppo = ppo_line[-1]
    ppo_signal = ppo_signal_series[-1]
    ppo_hist = (ppo - ppo_signal) if ppo is not None and ppo_signal is not None else None
    if ppo_hist is None and ppo is not None and n < full_need:
        ppo_signal = 0.0
        ppo_hist = ppo
    bb_mid = _sma_at(closes, p_bb)
    bb_pctb = None
    if bb_mid is not None and n >= p_bb:
        chunk = closes[-p_bb:]
        var = sum((x - bb_mid) ** 2 for x in chunk) / p_bb  # population σ (Bollinger)
        std = var**0.5
        upper = bb_mid + CS_BB_DEV * std
        lower = bb_mid - CS_BB_DEV * std
        span = upper - lower
        bb_pctb = ((closes[-1] - lower) / span) if span > 0 else 0.5
    stoch_k = _stoch_k(highs, lows, closes, p_stoch, smooth=p_stoch_slow)
    stoch_mode = "full"
    if stoch_k is None and n >= p_stoch:
        # Fall back to Fast %K when Full Stoch window does not fit (IPO / thin).
        stoch_k = _stoch_fast_k_at(highs, lows, closes, n - 1, p_stoch)
        stoch_mode = "fast"
    cci = _cci_at(highs, lows, closes, p_cci)
    willr = _willr_at(highs, lows, closes, p_stoch)
    plus_di, minus_di, adx = _adx_last(highs, lows, closes, p_adx)
    aroon_up, aroon_down, aroon_osc = _aroon_at(highs, lows, p_aroon)
    atr = _atr_last(highs, lows, closes, p_atr)
    atr_pct = (100.0 * atr / closes[-1]) if atr is not None and closes[-1] else None
    roc = None
    if n > p_roc and closes[-(p_roc + 1)]:
        roc = ((closes[-1] - closes[-(p_roc + 1)]) / closes[-(p_roc + 1)]) * 100.0
    # For votes: use exact SMA50 when pairing with SMA200; else adapted SMA50 for short stack.
    sma50_for_cross = sma50_x if sma200 is not None else sma50
    ind = {
        "close": closes[-1],
        "rsi": round(rsi_s[-1], 1) if rsi_s[-1] is not None else None,
        "macd": round(macd, 3) if macd is not None else None,
        "macd_signal": round(macd_signal, 3) if macd_signal is not None else None,
        "macd_hist": round(macd_hist, 3) if macd_hist is not None else None,
        "ppo": round(ppo, 3) if ppo is not None else None,
        "ppo_signal": round(ppo_signal, 3) if ppo_signal is not None else None,
        "ppo_hist": round(ppo_hist, 3) if ppo_hist is not None else None,
        "sma20": round(sma20, 2) if sma20 is not None else None,
        "sma50": round(sma50_for_cross, 2) if sma50_for_cross is not None else None,
        "sma200": round(sma200, 2) if sma200 is not None else None,
        "ema20": round(ema20, 2) if ema20 is not None else None,
        "bb_pctb": round(bb_pctb, 3) if bb_pctb is not None else None,
        "stoch_k": round(stoch_k, 1) if stoch_k is not None else None,
        "cci": round(cci, 1) if cci is not None else None,
        "willr": round(willr, 1) if willr is not None else None,
        "plus_di": round(plus_di, 1) if plus_di is not None else None,
        "minus_di": round(minus_di, 1) if minus_di is not None else None,
        "adx": round(adx, 1) if adx is not None else None,
        "aroon_up": round(aroon_up, 1) if aroon_up is not None else None,
        "aroon_down": round(aroon_down, 1) if aroon_down is not None else None,
        "aroon_osc": round(aroon_osc, 1) if aroon_osc is not None else None,
        "roc": round(roc, 2) if roc is not None else None,
        "atr": round(atr, 2) if atr is not None else None,
        "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
    }
    selected = _parse_tech_indicators(indicators)
    votes = _tech_votes(ind)
    score = round(_tech_score_from_votes(votes, selected), 1)
    bias = _bias_from_score(score)
    strength = (
        "strong" if abs(score) >= 60 else "moderate" if abs(score) >= 30 else "weak"
    )
    hist = _history_meta(n, full_need)
    history = hist["history"]
    partial = hist["partial_history"]
    setup = _tech_setup(ind)
    if history == "thin" and setup in ("Range", "Momentum↑", "Momentum↓"):
        setup = "Thin"
    # Which selected Signals could not vote (missing lookback).
    voted_names = {name for name, _ in votes}
    skipped = [name for name in selected if name not in voted_names]
    # After PPO preference, macd may still show in votes dict but not score — not "skipped".
    shown = {name: val for name, val in votes if name in selected}
    stoch_period_label = (
        f"{p_stoch}/{p_stoch_slow}/{p_stoch_slow}"
        if stoch_mode == "full"
        else f"{p_stoch} fast"
    )
    return {
        **ind,
        "setup": setup,
        "votes": shown,
        "indicators": selected,
        "skipped": skipped,
        "periods": {
            "rsi": p_rsi,
            "ema": p_ema,
            "macd": f"{p_fast}/{p_slow}/{p_sig}",
            "ppo": f"{p_fast}/{p_slow}/{p_sig}",
            "sma": f"{p_sma_f}/{p_sma_s}",
            "sma200": f"{CS_SMA_SLOW}/{p_sma_l}" if sma200 is not None else None,
            "bb": f"{p_bb},{CS_BB_DEV:g}",
            "stoch": stoch_period_label,
            "cci": p_cci,
            "willr": p_stoch,
            "roc": p_roc,
            "adx": p_adx,
            "aroon": p_aroon,
            "atr": p_atr,
        },
        "score": score,
        "bias": bias,
        "strength": strength,
        "change_pct": last.get("change_pct"),
        "up": last.get("up"),
        "volume": last.get("volume"),
        "label": last.get("label"),
        **hist,
    }


def _scan_tech_row(
    preset: dict,
    tf_id: str,
    indicators: list[str] | None = None,
) -> dict | None:
    # 3M/6M are short daily windows. SMA50/200 still needs ~200 sessions,
    # so those chips read the 1-year daily series (RSI/MACD use the same last bars).
    hist_tf = "1y" if tf_id in {"3m", "6m"} else tf_id
    bars = _load_bars(
        preset["nse"],
        hist_tf,
        exchange=preset.get("exchange") or "NSE",
        fast=True,
    )
    study = _tech_enrich(bars, indicators=indicators, tf_id=tf_id)
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
    row = {
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
        "ppo": study.get("ppo"),
        "ppo_signal": study.get("ppo_signal"),
        "ppo_hist": study.get("ppo_hist"),
        "sma20": study.get("sma20"),
        "sma50": study.get("sma50"),
        "sma200": study.get("sma200"),
        "ema20": study.get("ema20"),
        "bb_pctb": study.get("bb_pctb"),
        "stoch_k": study.get("stoch_k"),
        "cci": study.get("cci"),
        "willr": study.get("willr"),
        "plus_di": study.get("plus_di"),
        "minus_di": study.get("minus_di"),
        "adx": study.get("adx"),
        "aroon_up": study.get("aroon_up"),
        "aroon_down": study.get("aroon_down"),
        "aroon_osc": study.get("aroon_osc"),
        "roc": study.get("roc"),
        "atr": study.get("atr"),
        "atr_pct": study.get("atr_pct"),
        "setup": study.get("setup"),
        "score": study.get("score"),
        "bias": study.get("bias"),
        "strength": study.get("strength"),
        "votes": study.get("votes") or {},
        "skipped": study.get("skipped") or [],
        "periods": study.get("periods"),
        "study": study,
        "spike": False,
        "bars_used": study.get("bars_used"),
        "partial_history": study.get("partial_history"),
        "history": study.get("history") or ("partial" if study.get("partial_history") else "full"),
    }
    _apply_tf_change(row, quote, tf_id, bars=bars)
    return row


def build_tech_board(
    tf_id: str = "1d",
    universe_id: str = "nifty50",
    fresh: bool = False,
    indicators: str | list[str] | None = None,
    progress_job: str | None = None,
) -> dict:
    _ensure_universe_ready()
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    meta = _universe_meta(universe_id)
    universe_id = meta["id"]
    selected = _parse_tech_indicators(indicators)
    presets = _load_universe(universe_id)
    cache_key = ("tech-board-v6", universe_id, tf_id, ",".join(selected))
    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                _scan_job_finish(progress_job, ok=True)
                return payload

    _scan_job_start(
        progress_job,
        total=len(presets),
        phase="scan",
        label=f"{meta['label']} · Technical",
    )
    errors = 0
    try:
        if _universe_is_large(universe_id):
            rows = []
            with ThreadPoolExecutor(max_workers=16) as pool:
                futures = {
                    pool.submit(_scan_tech_row, preset, tf_id, selected): preset for preset in presets
                }
                for future in _as_completed_progress(futures, progress_job, phase="enrich"):
                    try:
                        row = future.result()
                    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                        errors += 1
                        continue
                    if row:
                        rows.append(row)
            universe_note = (
                f"{meta['label']}: tech-enriched {len(rows)}/{len(presets)}"
                f" of {_universe_full_size(universe_id)} · {len(selected)} indicators"
            )
        else:
            rows = []
            with ThreadPoolExecutor(max_workers=12) as pool:
                futures = {
                    pool.submit(_scan_tech_row, preset, tf_id, selected): preset
                    for preset in presets
                }
                for future in _as_completed_progress(futures, progress_job, phase="scan"):
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
    except Exception as exc:
        _scan_job_finish(progress_job, ok=False, error=str(exc))
        raise

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
    _scan_job_finish(progress_job, ok=True)
    return payload


def build_board(
    tf_id: str = "1d",
    universe_id: str = "nifty50",
    fresh: bool = False,
    progress_job: str | None = None,
) -> dict:
    _ensure_universe_ready()
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    meta = _universe_meta(universe_id)
    universe_id = meta["id"]
    presets = _load_universe(universe_id)
    cache_key = ("board-v5", universe_id, tf_id)
    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                _scan_job_finish(progress_job, ok=True)
                return payload

    _scan_job_start(
        progress_job,
        total=len(presets),
        phase="scan",
        label=f"{meta['label']} · Volume",
    )
    errors = 0
    # Large books used to history-enrich only the 1,200 most active quotes.
    try:
        if _universe_is_large(universe_id):
            rows = []
            with ThreadPoolExecutor(max_workers=16) as pool:
                futures = {pool.submit(_scan_row, preset, tf_id): preset for preset in presets}
                for future in _as_completed_progress(futures, progress_job, phase="enrich"):
                    try:
                        row = future.result()
                    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                        errors += 1
                        continue
                    if row:
                        rows.append(row)
            universe_note = (
                f"{meta['label']}: volume-enriched {len(rows)}/{len(presets)}"
                f" of {_universe_full_size(universe_id)}"
            )
        else:
            rows = []
            with ThreadPoolExecutor(max_workers=12) as pool:
                futures = {pool.submit(_scan_row, preset, tf_id): preset for preset in presets}
                for future in _as_completed_progress(futures, progress_job, phase="scan"):
                    try:
                        row = future.result()
                    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                        errors += 1
                        continue
                    if row:
                        rows.append(row)
            universe_note = f"{meta['label']} full volume scan · {tf['label']}"
    except Exception as exc:
        _scan_job_finish(progress_job, ok=False, error=str(exc))
        raise

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
    _scan_job_finish(progress_job, ok=True)
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
    "timeframe": (
        "Lab periods are ChartSchool bar-counts on the selected chip’s resolution "
        "(not calendar days). "
        "Intraday 15m/1H/4H → that many bars; Swing 1D/1W/1M → day/week/month; "
        "Long 3M–1Y → daily (same as 1D); 5Y/Max → weekly. "
        "Defaults: Donchian/CMF/OBV(20) · RVOL(50 prior) · BB BandWidth(20,2) · ATR(14) · "
        "break needs RVOL≥1.5×."
    ),
    "history": (
        "Recent listings: Donchian/RVOL/CMF/ATR/BB windows shrink to available bars. "
        "history=thin (<8) · partial · full. Scores use only what the series can support."
    ),
    "range": (
        "Range% = 100 × (prior HH_N − prior LL_N) / mid — Donchian box excluding the "
        "current bar when possible (ChartSchool Price Channels). N = CMF/avg_window "
        "on the selected chip (default 20)."
    ),
    "squeeze": (
        "BandWidth = 4σ/SMA_N on last N closes (Bollinger 20,2); ATR% = ATR(14)/Close. "
        "Squeeze if BandWidth or ATR% < 85% of the prior N-bar reading."
    ),
    "rvol": (
        "RVOL = V_t ÷ SMA(V, prior 50 bars) — current bar excluded (ChartSchool RVOL). "
        "Breakout filter: RVOL ≥ 1.5×."
    ),
    "cmf": (
        "CMF(N) = Σ MFV_N ÷ Σ V_N over the Donchian base; "
        "MFV=((C−L)−(H−C))/(H−L)×V (Chaikin / ChartSchool). N defaults to 20."
    ),
    "obv": (
        "OBVΔ = OBV_t − OBV_{t−N} on selected bars; rising while coiled = quiet buying "
        "(Granville / ChartSchool OBV)."
    ),
    "structure": (
        "Higher pivot lows (last 3 swings, or 2 on thin history) = bullish structure "
        "(ChartSchool Trend Lines)."
    ),
    "bull_breakout": (
        "Close > prior HH_N AND RVOL≥1.5 AND close in top of range (pos≥0.85)."
    ),
    "bull_base": (
        "Coil (consol_score≥55) + accumulation (CMF>0.05 or OBV↑ or higher lows)."
    ),
    "consolidating": (
        "Coil from tight Range% + BandWidth/ATR squeeze + volume dry-up in the base."
    ),
    "score": (
        "Pattern score 0…100: breakout uses bull_score; bull_base mixes bull+coil; "
        "plain coil uses consol×0.7. Bias bullish on breakout/bull_base."
    ),
    "rank": "Rank 1 = breakout first, then bull base, then coil — by score inside each group",
    "spark": "Sparkline = last 30 closes of the selected TF for visual context",
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


def _sci_enrich(
    bars: list[dict],
    window: int = CS_CMF,
    rvol_window: int | None = None,
) -> dict | None:
    """Lab reader — Donchian coil / breakout with ChartSchool lookbacks on TF bars."""
    n = len(bars)
    pref_box = int(window or CS_CMF)
    pref_rvol = int(rvol_window if rvol_window is not None else CS_RVOL)
    # Fit Donchian/base window to available history (recent listings OK).
    base = _adapt_study_window(pref_box, n, floor=4, headroom=1)
    if base is None:
        base = _adapt_study_window(pref_box, n, floor=2, headroom=1)
    if base is None:
        return None
    # RVOL uses prior bars only → cap at n−1.
    rvol_n = _adapt_period(pref_rvol, max(1, n - 1), minimum=1)
    atr_p = _adapt_period(CS_ATR, max(1, n - 1), minimum=min(3, max(1, n - 1)))
    bb_n = _adapt_period(pref_box, n, minimum=min(3, n))
    cmf_n = min(base, n)
    preferred = max(pref_box, pref_rvol, CS_ATR)
    hist = _history_meta(n, preferred + 1)
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

    # Bollinger BandWidth on N bars of the active TF (ChartSchool BandWidth)
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

    # ChartSchool RVOL — prior bars only (exclude current).
    prior_vols = [v for v in vols[max(0, n - 1 - rvol_n) : n - 1] if v > 0]
    avg_vol = (sum(prior_vols) / len(prior_vols)) if prior_vols else None
    rvol = (vols[-1] / avg_vol) if avg_vol and avg_vol > 0 else None
    half = max(2, base // 2)
    base_vol = _sma_last(vols[-(base + 1) : -1] or vols[-base:], half)
    prior_vol = _sma_last(vols[-(2 * base) : -(base + 1)] or vols[-base:], half)
    vol_dry = bool(
        base_vol is not None and prior_vol is not None and prior_vol > 0 and base_vol < prior_vol * 0.85
    )

    # CMF over Donchian/base window
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
        **hist,
        "window": base,
        "rvol_window": rvol_n,
        "periods": {
            "donchian": base,
            "cmf": cmf_n,
            "obv": obv_back,
            "rvol": rvol_n,
            "bb": f"{bb_n},{CS_BB_DEV:g}",
            "atr": atr_p,
            "break_rvol": 1.5,
            "hl": hl_need,
        },
    }


def _scan_sci_row(preset: dict, tf_id: str) -> dict | None:
    tf = TIMEFRAMES[tf_id]
    bars = _load_bars(
        preset["nse"],
        tf_id,
        exchange=preset.get("exchange") or "NSE",
        fast=True,
    )
    wins = _tf_study_windows(tf_id)
    study = _sci_enrich(
        bars,
        window=wins["avg_window"],
        rvol_window=wins["rvol_window"],
    )
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
    row = {
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
        "periods": study.get("periods"),
        "window": study.get("window"),
        "rvol_window": study.get("rvol_window"),
        "bars_used": study.get("bars_used"),
        "partial_history": study.get("partial_history"),
        "history": study.get("history") or ("partial" if study.get("partial_history") else "full"),
        "history_need": study.get("history_need"),
        "rank": None,
        "percentile": None,
    }
    _apply_tf_change(row, quote, tf_id, bars=bars)
    return row


def build_sci_board(
    tf_id: str = "1d",
    universe_id: str = "nifty50",
    fresh: bool = False,
    progress_job: str | None = None,
) -> dict:
    _ensure_universe_ready()
    tf_id = _normalize_tf(tf_id)
    tf = TIMEFRAMES[tf_id]
    meta = _universe_meta(universe_id)
    universe_id = meta["id"]
    presets = _load_universe(universe_id)
    cache_key = ("sci-board-v5", universe_id, tf_id)
    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                _scan_job_finish(progress_job, ok=True)
                return payload

    _scan_job_start(
        progress_job,
        total=len(presets),
        phase="scan",
        label=f"{meta['label']} · Lab",
    )
    errors = 0
    try:
        if _universe_is_large(universe_id):
            rows = []
            with ThreadPoolExecutor(max_workers=16) as pool:
                futures = {pool.submit(_scan_sci_row, preset, tf_id): preset for preset in presets}
                for future in _as_completed_progress(futures, progress_job, phase="enrich"):
                    try:
                        row = future.result()
                    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                        errors += 1
                        continue
                    if row:
                        rows.append(row)
            universe_note = (
                f"{meta['label']}: lab-enriched {len(rows)}/{len(presets)}"
                f" of {_universe_full_size(universe_id)}"
            )
        else:
            rows = []
            with ThreadPoolExecutor(max_workers=12) as pool:
                futures = {
                    pool.submit(_scan_sci_row, preset, tf_id): preset for preset in presets
                }
                for future in _as_completed_progress(futures, progress_job, phase="scan"):
                    try:
                        row = future.result()
                    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                        errors += 1
                        continue
                    if row:
                        rows.append(row)
            universe_note = (
                f"{meta['label']} Lab · {tf['label']} · volume + chart patterns"
            )
    except Exception as exc:
        _scan_job_finish(progress_job, ok=False, error=str(exc))
        raise

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
    _scan_job_finish(progress_job, ok=True)
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

# API field → table header (Chart dashboard “→ columns” must match ScanTable labels).
CHART_COLUMN_LABELS = {
    "support": "Sup",
    "resistance": "Res",
    "demand_lo": "Demand",
    "supply_lo": "Supply",
    "dist_support_pct": "Dist S%",
    "dist_resistance_pct": "Dist R%",
    "range_width_pct": "Range%",
    "setup": "Setup",
    "trend": "Trend",
    "trend_touches": "Touches",
    "higher_lows": "HL",
    "lower_highs": "LH",
    "gap": "Gap",
    "gap_pct": "Gap%",
    "rvol": "RVOL",
    "pattern": "Pattern",
    "fib_nearest": "Fib",
    "fib_zone": "Fib zone",
    "fib_context": "Fib ctx",
    "candle": "Candle",
    "candle_quality": "Candle Q",
    "score": "Score",
    "bias": "Bias",
    "high_edge": "Edge",
    "confluence": "Conf",
}

CHART_SOURCES = [
    {
        "id": "support_resistance",
        "name": "Support & Resistance",
        "ref": "StockCharts ChartSchool — reaction highs/lows, trading ranges, S⇄R flips",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/support-and-resistance",
        "columns": ["support", "resistance", "demand_lo", "supply_lo", "dist_support_pct", "dist_resistance_pct", "range_width_pct", "setup"],
        "lookback": "sr_look · sr · near_pct · zone_pct",
    },
    {
        "id": "trend",
        "name": "Trend Lines",
        "ref": "StockCharts — uptrend (rising lows) / downtrend (falling highs), ≥3 touches",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/trend-lines",
        "columns": ["trend", "trend_touches", "higher_lows", "lower_highs"],
        "lookback": "trend_touches",
    },
    {
        "id": "gap",
        "name": "Gaps",
        "ref": "StockCharts — common · breakaway · runaway · exhaustion (volume context)",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/gaps-and-gap-analysis",
        "columns": ["gap", "gap_pct", "rvol"],
        "lookback": "rvol · gap_rvol",
    },
    {
        "id": "rvol",
        "name": "Relative Volume (RVOL)",
        "ref": "StockCharts — V ÷ SMA(prior 50); confirms gaps/breaks (default 50)",
        "url": "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-volume-rvol",
        "columns": ["rvol"],
        "lookback": "rvol",
    },
    {
        "id": "pattern",
        "name": "Chart Patterns",
        "ref": "StockCharts — rectangle · triangles · flags · double top/bottom",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns",
        "columns": ["pattern"],
        "lookback": "sr",
    },
    {
        "id": "fibonacci",
        "name": "Fibonacci Retracements",
        "ref": "StockCharts — 23.6% · 38.2% · 50% · 61.8% alert zones",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-annotation-tools/fibonacci-retracements",
        "columns": ["fib_nearest", "fib_zone", "fib_context"],
        "lookback": "fib_swing",
    },
    {
        "id": "candle",
        "name": "Candlestick Reversals",
        "ref": "StockCharts — hammer · engulfing · shooting star · doji (context at S/R)",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/candlestick-charts/introduction-to-candlesticks",
        "columns": ["candle", "candle_quality"],
        "lookback": "last bar",
    },
    {
        "id": "candle_bull",
        "name": "Bullish Candlestick Patterns",
        "ref": "StockCharts — hammer · bullish engulfing at support",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/candlestick-charts/candlestick-bullish-reversal-patterns",
        "columns": ["candle"],
        "lookback": "last bar",
    },
    {
        "id": "candle_bear",
        "name": "Bearish Candlestick Patterns",
        "ref": "StockCharts — shooting star · bearish engulfing at resistance",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis/candlestick-charts/candlestick-bearish-reversal-patterns",
        "columns": ["candle"],
        "lookback": "last bar",
    },
    {
        "id": "score_edges",
        "name": "Score · Edge · Conf",
        "ref": "Murphy / ChartSchool — weighted high-success edges · confirmation count",
        "url": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis",
        "columns": ["score", "bias", "high_edge", "confluence"],
        "lookback": "edges on selected read window",
    },
]

CHART_FORMULAS = {
    "timeframe": (
        "Chart read windows (no Intraday): "
        "Daily sessions: 126 (6M) · 252 (1Y) · 504 (2Y) · 756 (3Y) · 1008 (4Y) · 1260 (5Y) · 2520 (Full). "
        "Swing weeks: 104 (2Y) · 260 (5Y). Long: 60 months · 520 weeks (10Y). "
        "Inside every chip: RVOL(50) · S/R base(20) · trend ≥3 touches · Fib on that chart. "
        "A bar is that resolution (RVOL(50) = 50 weeks on Swing, 50 months on 5Y·M). "
        "S/R and Fib use the selected chart. Near≤1.25% · gap RVOL≥1.4."
    ),
    "history": (
        "Recent listings / IPOs: use every available bar of the selected chip. "
        "S/R base, pivot look, RVOL, and Fib swing shrink to fit; trend needs 2 touches "
        "when <12 bars; Fib alerts off until ≥24 bars. "
        "history=thin (<8) · partial · full. Score dampened thin×0.45 / partial×0.70 "
        "and tagged T/P on Score/Setup — never blank solely for short history."
    ),
    "score": (
        "Score column = projected confluence 0…100 (mid 50) from ChartSchool edges: "
        "vol-confirmed S/R break · validated trend · cont pattern+trend · "
        "reversal candle at S/R/Fib · breakaway gap · Fib 38.2–61.8 with trend. "
        "Murphy: ≥3 aligned edges adds a bonus. Bullish ≥60 · bearish ≤40 · "
        "thin/partial dampened · T/P tag."
    ),
    "bias": (
        "Bias column: bullish when Score≥60 · bearish when Score≤40 · else neutral."
    ),
    "high_edge": (
        "Edge column = High when |Conf|≥3 or a top-tier edge fires "
        "(vol_breakout / vol_breakdown / cont pattern+trend / hammer_sr / star_sr / "
        "gap_breakaway). Off on thin IPOs. Hover Edge/Conf for edge list."
    ),
    "confluence": (
        "Conf column = bull edges − bear edges (signed count). "
        "|Conf|≥3 triggers Murphy bonus on Score."
    ),
    "setup": (
        "Setup column: breakout / breakdown / near_support / near_resistance / "
        "fib_zone / mid_range — from S/R proximity and breaks. T/P = thin/partial history."
    ),
    "support": (
        "Sup = nearest shelf at or under the close on the look window: swing-low zone, "
        "or a broken swing high that flipped to support when it is tighter (ChartSchool S⇄R). "
        "Never plotted above the close. Touches = reactions inside ~0.6%."
    ),
    "resistance": (
        "Res = nearest swing-high zone at or above the close on the selected chart "
        "(5-bar swings, not a one-day spike). Break = close through that zone."
    ),
    "demand": (
        "Demand = bottom 20% of the selected chart high–low (visible-range discount). "
        "PAGEIND-style base: the orange zone price is sitting on, not the last tiny pivot."
    ),
    "supply": (
        "Supply = top 20% of the selected chart high–low (visible-range premium). "
        "The ceiling of this read window — 1D·160 is the recent swing, 2Y+ reaches the prior high."
    ),
    "dist": (
        "Dist S% / Dist R% = % from close to support / resistance. "
        "Near when ≤ near_pct (1.25% full · 1.5% partial · 2% thin)."
    ),
    "range_width": (
        "S/R% = 100×(nearest Res − nearest Sup) / mid. "
        "Loc = where Close sits from Demand (0) to Supply (100)."
    ),
    "trend": (
        "Trend column: up / down / sideways — rising swing lows or falling swing highs "
        "(ChartSchool Trend Lines). Touches(≥N) counts touches; ✓ when validated "
        "(≥3, or ≥2 on thin). HL / LH = higher lows / lower highs structure."
    ),
    "rvol": (
        "RVOL(N) = V_t ÷ SMA(V, prior N bars) — current excluded (ChartSchool). "
        "Confirms gaps/breaks at ≥1.4×. On 1W, N weeks; on 1M, N months."
    ),
    "gap": (
        "Gap column: up/down × common|breakaway|runaway|exhaustion (or —). "
        "Up when low>prior high; down when high<prior low. "
        "Breakaway needs congestion (range ~4–16%) + RVOL≥1.4. Gap% on hover."
    ),
    "pattern": (
        "Pattern column: rectangle · asc/desc/sym triangle · double top/bottom · flag "
        "(or —). ChartSchool confirmation = close through the boundary or neckline "
        "(doubles score only after that break). Role = continuation / reversal / range. "
        "Shapes shrink on short history."
    ),
    "rectangle": "Sideways range between flat support & resistance",
    "asc_triangle": "Flat highs + rising lows — bullish continuation bias",
    "desc_triangle": "Flat lows + falling highs — bearish continuation bias",
    "sym_triangle": "Converging highs and lows — coiled continuation/reversal",
    "double_bottom": "Two similar swing lows with intervening peak — reversal",
    "double_top": "Two similar swing highs with intervening trough — reversal",
    "flag": "Tight counter-move after an impulse leg — continuation",
    "fib": (
        "Fib(≥swing) = nearest retracement label (23.6/38.2/50/61.8). "
        "After advance: High−span×r; after decline: Low+span×r. "
        "Zone highlight when ≤1% of 38.2/50/61.8. Off until ≥24 bars. "
        "Hover: context · dist% · swing."
    ),
    "candle": (
        "Candle column: hammer / bullish engulfing / shooting star / bearish engulfing / "
        "doji (or —). Stronger at S/R or Fib — quality on hover."
    ),
    "hammer": (
        "Small body near top of range + long lower shadow — bullish reversal; "
        "stronger at support / Fib / downtrend (ChartSchool)."
    ),
    "engulfing": "Current body engulfs prior body — reversal candlestick",
}

# ChartSchool / Murphy — higher-reliability edges for score projection (points from 50).
# Prefer volume-confirmed breaks, validated trends, continuation-with-trend, context candles.
CHART_EDGE_WEIGHTS: dict[str, float] = {
    # S/R breaks — volume confirmation preferred (ChartSchool TA 101 / Murphy)
    "vol_breakout": 22.0,
    "breakout": 12.0,
    "vol_breakdown": -22.0,
    "breakdown": -12.0,
    # Validated trend lines (≥3 touches)
    "trend_valid_up": 12.0,
    "trend_up": 5.0,
    "trend_valid_down": -12.0,
    "trend_down": -5.0,
    # Continuation patterns aligned with trend (ascending triangle, flags)
    "cont_asc_triangle": 14.0,
    "asc_triangle": 7.0,
    "cont_desc_triangle": -14.0,
    "desc_triangle": -7.0,
    "cont_flag_bull": 12.0,
    "flag_bull": 6.0,
    "cont_flag_bear": -12.0,
    "flag_bear": -6.0,
    "rect_support": 7.0,
    "rect_resist": -7.0,
    "sym_coil": 2.0,
    # Reversal patterns (double bottom/top — ChartSchool: confirm on break)
    "double_bottom": 11.0,
    "double_top": -11.0,
    # Gaps — breakaway/runaway > common; exhaustion fades
    "gap_breakaway_up": 12.0,
    "gap_runaway_up": 8.0,
    "gap_common_up": 2.0,
    "gap_exhaust_up": -5.0,
    "gap_breakaway_down": -12.0,
    "gap_runaway_down": -8.0,
    "gap_common_down": -2.0,
    "gap_exhaust_down": 5.0,
    # Candles with S/R or Fib context (ChartSchool)
    "hammer_sr": 12.0,
    "engulf_bull_sr": 11.0,
    "hammer_weak": 3.0,
    "star_sr": -12.0,
    "engulf_bear_sr": -11.0,
    "star_weak": -3.0,
    # Fib alert zone with trend (38.2 / 50 / 61.8)
    "fib_pullback_up": 10.0,
    "fib_bounce_down": -8.0,
    "fib_pullback": 4.0,
    "fib_bounce": -3.0,
    # Near S/R with trend (bounce / reject setups)
    "near_support_up": 9.0,
    "near_support": 5.0,
    "near_resist_down": -9.0,
    "near_resist": -5.0,
    # Murphy confirmation bonus applied separately when |edges| ≥ 3
}


def _cluster_prices(prices: list[float], zone_pct: float) -> list[tuple[float, int]]:
    """Merge reaction prices that sit in one ChartSchool zone. Returns (level, touches)."""
    if not prices:
        return []
    pts = sorted(float(p) for p in prices)
    groups: list[list[float]] = [[pts[0]]]
    for price in pts[1:]:
        mid = sum(groups[-1]) / len(groups[-1])
        if mid > 0 and abs(price - mid) / mid * 100.0 <= zone_pct:
            groups[-1].append(price)
        else:
            groups.append([price])
    return [(sum(group) / len(group), len(group)) for group in groups]


def _chart_sr_levels(
    swing_highs: list[float],
    swing_lows: list[float],
    highs: list[float],
    lows: list[float],
    close: float,
    *,
    look: int,
    base: int,
    zone_pct: float,
) -> dict:
    """Nearest chart support under price and resistance over price.

    Resistance is the closest swing-high zone the close has not broken.
    Support is the closest shelf under the close: a swing low, or a broken
    swing high that flipped (ChartSchool S⇄R) when that shelf is tighter.
    """
    cluster_pct = max(zone_pct, 0.6)
    hi_lv = _cluster_prices(swing_highs, cluster_pct)
    lo_lv = _cluster_prices(swing_lows, cluster_pct)

    res_opts = [(px, touches) for px, touches in hi_lv if px + 1e-9 >= close]
    res_from = "pivot"
    if not res_opts:
        overhead = [h for h in highs[-look:] if h >= close]
        if not overhead:
            overhead = [h for h in highs[-base:] if h >= close] or highs[-base:]
        res_opts = [(max(overhead) if max(overhead) >= close else close, 1)]
        res_from = "range"
    res_opts.sort(key=lambda item: item[0])
    nearest_res = res_opts[0][0]
    res_band = [item for item in res_opts if item[0] <= nearest_res * 1.003]
    resistance, res_touches = max(res_band, key=lambda item: (item[1], -item[0]))

    # Swing lows on or under the close. A high the close has cleared becomes support
    # only when it is a tighter shelf than those lows (ChartSchool role reversal).
    sup_opts = [(px, touches, "pivot") for px, touches in lo_lv if px <= close]
    nearest_low = max((px for px, _, _ in sup_opts), default=None)
    for px, touches in hi_lv:
        if px >= close:
            continue
        if nearest_low is not None and px < nearest_low:
            continue
        sup_opts.append((px, touches, "flip"))
    sup_from = "pivot"
    if not sup_opts:
        under = [lv for lv in lows[-look:] if lv <= close]
        if not under:
            under = [lv for lv in lows[-base:] if lv <= close] or lows[-base:]
        floor = min(under) if min(under) <= close else close
        sup_opts = [(floor, 1, "range")]
    sup_opts.sort(key=lambda item: -item[0])
    nearest_sup = sup_opts[0][0]
    sup_band = [item for item in sup_opts if item[0] >= nearest_sup * 0.997]
    support, sup_touches, sup_from = max(sup_band, key=lambda item: (item[1], item[0]))

    if resistance <= support:
        under = [lv for lv in lows[-look:] if lv < close] or lows[-base:]
        over = [h for h in highs[-look:] if h > close] or highs[-base:]
        support, resistance = min(under), max(over)
        if resistance <= support:
            support, resistance = min(lows[-base:]), max(highs[-base:])
        sup_touches, res_touches = 1, 1
        sup_from, res_from = "range", "range"

    return {
        "support": support,
        "resistance": resistance,
        "support_touches": int(sup_touches),
        "resistance_touches": int(res_touches),
        "support_from": sup_from,
        "resistance_from": res_from,
    }


def _visible_range_zones(highs: list[float], lows: list[float], fraction: float = 0.20) -> dict:
    """Premium and discount zones of the selected chart (visible-range supply/demand).

    Top 20% of the chart high–low is supply. Bottom 20% is demand.
    Matches a multi-year daily read such as PAGEIND: demand near the base,
    supply near the ceiling, not the last one-day pivot.
    """
    if not highs or not lows:
        return {}
    hi = max(highs)
    lo = min(lows)
    span = hi - lo
    if span <= 0:
        return {"demand_lo": lo, "demand_hi": hi, "supply_lo": lo, "supply_hi": hi}
    band = span * fraction
    return {
        "demand_lo": lo,
        "demand_hi": lo + band,
        "supply_lo": hi - band,
        "supply_hi": hi,
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


def _chart_enrich(
    bars: list[dict],
    window: int = CS_CMF,
    rvol_window: int | None = None,
    sr_look: int | None = None,
    fib_swing: int | None = None,
) -> dict | None:
    """StockCharts Chart Analysis — tightened ChartSchool rules.

    Recent listings: shrink every lookback to available bars and still emit a row
    (S/R from HH/LL of what exists). Score conviction is dampened when thin/partial.
    """
    n = len(bars)
    if n < 1:
        return None
    # Fit S/R window to available bars so short listings still get a reading.
    base = _adapt_study_window(window or CS_CMF, n, floor=4, headroom=1)
    if base is None:
        base = _adapt_study_window(window or CS_CMF, n, floor=2, headroom=1)
    if base is None:
        # Brand-new listing (1–2 bars): use the whole series as the box.
        base = max(1, n - (1 if n > 1 else 0))
    rvol_n = _adapt_period(
        rvol_window if rvol_window is not None else CS_RVOL,
        max(1, n - 1) if n > 1 else 1,
        minimum=1,
    )
    look_pref_meta = int(sr_look) if sr_look is not None else 90
    fib_pref_meta = int(fib_swing) if fib_swing is not None else max(50, int(window or CS_CMF) * 3)
    preferred = max(
        int(window or CS_CMF),
        int(rvol_window or CS_RVOL),
        look_pref_meta,
        fib_pref_meta,
    )
    # RVOL excludes the current bar, so it needs one extra session. Do not add
    # that extra bar on top of a longer S/R window — that marked every full
    # chart (126, 260, 504, …) as partial and dampened the score.
    full_need = max(preferred, int(rvol_window or CS_RVOL) + 1)
    hist = _history_meta(n, full_need)
    partial = hist["partial_history"]
    listing = hist.get("history") or "full"  # thin | partial | full
    opens = [float(b.get("open") if b.get("open") is not None else b["close"]) for b in bars]
    highs = [float(b["high"] if b.get("high") is not None else b["close"]) for b in bars]
    lows = [float(b["low"] if b.get("low") is not None else b["close"]) for b in bars]
    closes = [float(b["close"]) for b in bars]
    vols = [float(b.get("volume") or 0) for b in bars]
    last = bars[-1]
    close = closes[-1]
    zone_pct = 0.4
    # Slightly wider "near" zone when history is short (levels noisier).
    near_pct = 2.0 if listing == "thin" else 1.5 if listing == "partial" else 1.25
    gap_rvol = 1.4
    tol = max(close * (zone_pct / 100.0), 1e-6)  # ChartSchool: zones, not exact ticks

    # --- Support & Resistance (reaction highs / lows) ---
    # Chip sets preferred pivot look; always clamp to available bars (IPO-safe).
    if sr_look is not None:
        look_pref = int(sr_look)
    else:
        look_pref = 90
        if n >= 800:
            look_pref = 252
        elif n >= 400:
            look_pref = 200
        elif n >= 220:
            look_pref = 160
        elif n >= 180:
            look_pref = 120
    look = _adapt_period(look_pref, n, minimum=min(max(base, 2), n))
    off = n - look
    pivot_lr = 2 if look >= 10 else 1
    ph_abs = [(off + i, v) for i, v in _pivot_highs(highs[-look:], left=pivot_lr, right=pivot_lr)]
    pl_abs = [(off + i, v) for i, v in _pivot_lows(lows[-look:], left=pivot_lr, right=pivot_lr)]
    # Support / resistance use the whole selected chart, with a wider swing
    # so a one-day spike is not "the" level. Trend keeps the shorter look above.
    chart_lr = 5 if n >= 40 else 3 if n >= 16 else max(1, pivot_lr)
    ph_chart = [v for _, v in _pivot_highs(highs, left=chart_lr, right=chart_lr)]
    pl_chart = [v for _, v in _pivot_lows(lows, left=chart_lr, right=chart_lr)]
    sr = _chart_sr_levels(
        ph_chart,
        pl_chart,
        highs,
        lows,
        close,
        look=n,
        base=base,
        zone_pct=zone_pct,
    )
    zones = _visible_range_zones(highs, lows)
    support = sr["support"]
    resistance = sr["resistance"]
    support_touches = sr["support_touches"]
    resistance_touches = sr["resistance_touches"]
    support_from = sr["support_from"]
    resistance_from = sr["resistance_from"]

    mid_sr = (support + resistance) / 2.0
    range_width = ((resistance - support) / mid_sr * 100.0) if mid_sr else None
    dist_sup = ((close - support) / close * 100.0) if close else None
    dist_res = ((resistance - close) / close * 100.0) if close else None
    # Near = inside ChartSchool-style zone under the level
    near_support = bool(dist_sup is not None and -0.15 <= dist_sup <= near_pct)
    near_resistance = bool(dist_res is not None and -0.15 <= dist_res <= near_pct)
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

    # --- Gaps (ChartSchool definitions + RVOL prior-only volume significance) ---
    gap = "none"
    gap_pct = None
    prior_vols = [v for v in vols[max(0, n - 1 - rvol_n) : n - 1] if v > 0]
    avg_vol = (sum(prior_vols) / len(prior_vols)) if prior_vols else None
    rvol = (vols[-1] / avg_vol) if avg_vol and avg_vol > 0 else None
    congested = bool(range_width is not None and 4.0 <= range_width <= 16.0)
    if n >= 2:
        prev_h, prev_l = highs[-2], lows[-2]
        # Gap must persist: today's extreme still clear of prior bar (intraday fill ignored on daily)
        if lows[-1] > prev_h:
            gap_pct = (lows[-1] - prev_h) / prev_h * 100.0 if prev_h else None
            strong_vol = rvol is not None and rvol >= gap_rvol
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
            strong_vol = rvol is not None and rvol >= gap_rvol
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
    pattern_neck = None  # double top/bottom confirmation level (ChartSchool reaction extreme)
    if range_width is not None and range_width <= 11 and flat_high and flat_low:
        pattern = "rectangle"
    elif flat_high and rising_lows and range_width is not None and range_width <= 18:
        pattern = "asc_triangle"
    elif flat_low and falling_highs and range_width is not None and range_width <= 18:
        pattern = "desc_triangle"
    elif falling_highs and rising_lows and range_width is not None and range_width <= 14:
        pattern = "sym_triangle"
    else:
        # Double bottom: two similar lows, peak between (gap shrinks on short history)
        dbl_gap = 3 if n < 30 else 6
        if len(pl_abs) >= 2 and mid_sr:
            i1, a = pl_abs[-2]
            i2, b = pl_abs[-1]
            if dbl_gap <= i2 - i1 <= max(base * 2, dbl_gap + 1) and abs(a - b) / mid_sr <= 0.03 and i2 >= n - base:
                peak = max(highs[i1 : i2 + 1])
                if peak >= max(a, b) * 1.02 and close >= min(a, b):
                    pattern = "double_bottom"
                    pattern_neck = peak
        if pattern == "none" and len(ph_abs) >= 2 and mid_sr:
            i1, a = ph_abs[-2]
            i2, b = ph_abs[-1]
            if dbl_gap <= i2 - i1 <= max(base * 2, dbl_gap + 1) and abs(a - b) / mid_sr <= 0.03 and i2 >= n - base:
                trough = min(lows[i1 : i2 + 1])
                if trough <= min(a, b) * 0.98 and close <= max(a, b):
                    pattern = "double_top"
                    pattern_neck = trough
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

    # ChartSchool: a pattern is complete on the break (neckline / boundary), not on the shape alone.
    pattern_role = "none"
    pattern_confirmed = False
    if pattern == "rectangle":
        pattern_role = "range"
        pattern_confirmed = bool(break_res or break_sup)
    elif pattern in ("asc_triangle", "flag_bull"):
        pattern_role = "continuation"
        if pattern == "asc_triangle":
            pattern_confirmed = bool(break_res)
        elif n > 6:
            pattern_confirmed = close > max(highs[-6:-1])
    elif pattern in ("desc_triangle", "flag_bear"):
        pattern_role = "continuation"
        if pattern == "desc_triangle":
            pattern_confirmed = bool(break_sup)
        elif n > 6:
            pattern_confirmed = close < min(lows[-6:-1])
    elif pattern == "sym_triangle":
        pattern_role = "continuation"
        pattern_confirmed = bool(break_res or break_sup)
    elif pattern == "double_bottom":
        pattern_role = "reversal"
        pattern_confirmed = bool(pattern_neck is not None and close > pattern_neck)
    elif pattern == "double_top":
        pattern_role = "reversal"
        pattern_confirmed = bool(pattern_neck is not None and close < pattern_neck)

    # --- Fibonacci: ChartSchool after advance/decline ---
    # Needs a meaningful swing — skip alert zones on brand-new listings (<24 bars).
    if fib_swing is not None:
        fib_pref = int(fib_swing)
    else:
        fib_pref = max(50, base * 3)
        if n >= 800:
            fib_pref = max(fib_pref, 180)
        elif n >= 400:
            fib_pref = max(fib_pref, 120)
        elif n >= 220:
            fib_pref = max(fib_pref, 90)
    swing_look = _adapt_period(
        fib_pref, max(1, n - 1) if n > 1 else 1, minimum=min(8, max(1, n - 1 if n > 1 else 1))
    )
    swing_h = highs[-swing_look:] if swing_look else highs
    swing_l = lows[-swing_look:] if swing_look else lows
    swing_high, swing_low = max(swing_h), min(swing_l)
    hi_i = len(swing_h) - 1 - swing_h[::-1].index(swing_high)
    lo_i = len(swing_l) - 1 - swing_l[::-1].index(swing_low)
    fib_levels: dict[str, float] = {}
    fib_nearest = None
    fib_dist = None
    fib_zone = False
    fib_context = None  # pullback | bounce
    fib_ready = n >= 24 and swing_high > swing_low * 1.02
    if fib_ready:
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

    # --- Projected score from ChartSchool higher-reliability edges ---
    # Prefer volume-confirmed breaks, validated trends, continuation-with-trend,
    # S/R candles, breakaway gaps, Fib+trend (Murphy confirmation principle).
    edges: list[str] = []
    vol_ok = rvol is not None and rvol >= gap_rvol
    if break_res:
        edges.append("vol_breakout" if vol_ok else "breakout")
    if break_sup:
        edges.append("vol_breakdown" if vol_ok else "breakdown")
    if trend == "up":
        edges.append("trend_valid_up" if trend_valid else "trend_up")
    elif trend == "down":
        edges.append("trend_valid_down" if trend_valid else "trend_down")
    if pattern == "asc_triangle":
        edges.append("cont_asc_triangle" if trend == "up" else "asc_triangle")
    elif pattern == "desc_triangle":
        edges.append("cont_desc_triangle" if trend == "down" else "desc_triangle")
    elif pattern == "flag_bull":
        edges.append("cont_flag_bull" if trend == "up" else "flag_bull")
    elif pattern == "flag_bear":
        edges.append("cont_flag_bear" if trend == "down" else "flag_bear")
    elif pattern == "rectangle" and near_support:
        edges.append("rect_support")
    elif pattern == "rectangle" and near_resistance:
        edges.append("rect_resist")
    elif pattern == "sym_triangle":
        edges.append("sym_coil")
    elif pattern == "double_bottom" and pattern_confirmed:
        # ChartSchool: reversal completes on the neckline break, not the second low.
        edges.append("double_bottom")
    elif pattern == "double_top" and pattern_confirmed:
        edges.append("double_top")
    if gap == "up_breakaway":
        edges.append("gap_breakaway_up")
    elif gap == "up_runaway":
        edges.append("gap_runaway_up")
    elif gap == "up_common":
        edges.append("gap_common_up")
    elif gap == "up_exhaustion":
        edges.append("gap_exhaust_up")
    elif gap == "down_breakaway":
        edges.append("gap_breakaway_down")
    elif gap == "down_runaway":
        edges.append("gap_runaway_down")
    elif gap == "down_common":
        edges.append("gap_common_down")
    elif gap == "down_exhaustion":
        edges.append("gap_exhaust_down")
    if candle == "hammer":
        edges.append("hammer_sr" if (near_support or fib_zone) else "hammer_weak")
    elif candle == "engulfing_bull":
        edges.append("engulf_bull_sr" if (near_support or fib_zone) else "hammer_weak")
    elif candle == "shooting_star":
        edges.append("star_sr" if (near_resistance or fib_zone) else "star_weak")
    elif candle == "engulfing_bear":
        edges.append("engulf_bear_sr" if (near_resistance or fib_zone) else "star_weak")
    if fib_zone and fib_context == "pullback":
        edges.append("fib_pullback_up" if trend == "up" else "fib_pullback")
    elif fib_zone and fib_context == "bounce":
        edges.append("fib_bounce_down" if trend == "down" else "fib_bounce")
    if near_support and not break_res and not break_sup:
        edges.append("near_support_up" if trend == "up" else "near_support")
    if near_resistance and not break_res and not break_sup:
        edges.append("near_resist_down" if trend == "down" else "near_resist")

    # Deduplicate while preserving order
    _seen_edges: set[str] = set()
    uniq_edges: list[str] = []
    for e in edges:
        if e not in _seen_edges:
            _seen_edges.add(e)
            uniq_edges.append(e)
    edges = uniq_edges

    score = 50.0
    for e in edges:
        score += CHART_EDGE_WEIGHTS.get(e, 0.0)
    bull_n = sum(1 for e in edges if CHART_EDGE_WEIGHTS.get(e, 0) > 0)
    bear_n = sum(1 for e in edges if CHART_EDGE_WEIGHTS.get(e, 0) < 0)
    # Murphy confirmation: several aligned factors strengthen the projection
    if bull_n >= 3 and bull_n > bear_n and listing == "full":
        score += 6.0
    elif bear_n >= 3 and bear_n > bull_n and listing == "full":
        score -= 6.0
    # Recent listing: pull score toward 50 — less conviction on short series.
    if listing == "thin":
        score = 50.0 + (score - 50.0) * 0.45
    elif listing == "partial":
        score = 50.0 + (score - 50.0) * 0.70
    score = max(0.0, min(100.0, score))
    confluence = bull_n - bear_n
    top_tier = {
        "vol_breakout",
        "vol_breakdown",
        "cont_asc_triangle",
        "cont_desc_triangle",
        "cont_flag_bull",
        "cont_flag_bear",
        "hammer_sr",
        "star_sr",
        "engulf_bull_sr",
        "engulf_bear_sr",
        "gap_breakaway_up",
        "gap_breakaway_down",
        "double_bottom",
        "double_top",
        "fib_pullback_up",
        "fib_bounce_down",
    }
    # High-edge only when history can support the claim (not on thin IPOs).
    high_edge = bool(
        listing != "thin"
        and (abs(confluence) >= 3 or any(e in top_tier for e in edges))
    )
    bias = "bullish" if score >= 60 else "bearish" if score <= 40 else "neutral"
    strength = (
        "strong" if score >= 72 or score <= 28 else "moderate" if score >= 60 or score <= 40 else "weak"
    )
    if listing == "thin":
        strength = "weak"

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
        "support_touches": support_touches,
        "resistance_touches": resistance_touches,
        "support_from": support_from,
        "resistance_from": resistance_from,
        "demand_lo": round(zones["demand_lo"], 2) if zones else None,
        "demand_hi": round(zones["demand_hi"], 2) if zones else None,
        "supply_lo": round(zones["supply_lo"], 2) if zones else None,
        "supply_hi": round(zones["supply_hi"], 2) if zones else None,
        "at_demand": bool(
            zones and zones["demand_lo"] <= close <= zones["demand_hi"] * (1 + near_pct / 100.0)
        ),
        "at_supply": bool(
            zones and zones["supply_lo"] * (1 - near_pct / 100.0) <= close <= zones["supply_hi"]
        ),
        "range_pos_pct": (
            round((close - zones["demand_lo"]) / (zones["supply_hi"] - zones["demand_lo"]) * 100.0, 1)
            if zones and zones["supply_hi"] > zones["demand_lo"]
            else None
        ),
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
        "pattern_role": pattern_role,
        "pattern_confirmed": pattern_confirmed,
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
        "edges": edges,
        "confluence": confluence,
        "high_edge": high_edge,
        "listing": listing,
        "adapted": bool(listing != "full"),
        "spike": bool(break_res and rvol is not None and rvol >= gap_rvol),
        "spark": spark,
        "spark_up": spark_up,
        "label": last.get("label"),
        **hist,
        "study_window": base,
        "rvol_window": rvol_n,
        "window": base,
        "periods": {
            "sr": base,
            "sr_look": look,
            "pivot": pivot_lr,
            "trend_touches": piv_need,
            "rvol": rvol_n,
            "gap_rvol": gap_rvol,
            "near_pct": near_pct,
            "fib_swing": swing_look,
            "zone_pct": zone_pct,
            "adapted": bool(listing != "full"),
            "available": n,
            "preferred_look": look_pref,
            "preferred_fib": fib_pref,
        },
    }


def _chart_trim_bars(bars: list[dict], tf_id: str) -> list[dict]:
    """Cap Chart history: 1D·160 stays tight; 1D·Full keeps deep daily bars."""
    tf = TIMEFRAMES.get(_normalize_tf(tf_id)) or {}
    cap = int(tf.get("chart_countback") or 0)
    if cap > 0 and len(bars) > cap:
        return bars[-cap:]
    return bars


def _scan_chart_row(preset: dict, tf_id: str, *, with_quote: bool = False) -> dict | None:
    tf = TIMEFRAMES[tf_id]
    bars = _load_bars(
        preset["nse"],
        tf_id,
        exchange=preset.get("exchange") or "NSE",
        fast=True,
    )
    bars = _chart_trim_bars(bars, tf_id)
    wins = _tf_study_windows(tf_id)
    study = _chart_enrich(
        bars,
        window=wins["avg_window"],
        rvol_window=wins["rvol_window"],
        sr_look=tf.get("chart_sr_look"),
        fib_swing=tf.get("chart_fib_swing"),
    )
    if not study:
        return None
    quote = {}
    # Always quote — Today % needs live session on every chip (incl. intraday).
    try:
        quote = _quote_stock(
            preset.get("sc_id") or "",
            nse=preset.get("nse") or preset.get("id") or "",
            exchange=preset.get("exchange") or "NSE",
            fast=True,
        )
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
        quote = {}
    row = {
        "id": preset["id"],
        "nse": quote.get("NSEID") or quote.get("BSEID") or preset["nse"],
        "name": quote.get("company") or preset["label"],
        "sc_id": preset["sc_id"],
        "exchange": quote.get("_market") or preset.get("exchange") or "NSE",
        "sector": quote.get("SC_SUBSEC") or quote.get("newSubsector") or preset.get("industry") or "",
        **{k: study.get(k) for k in study if k != "label"},
        "rank": None,
        "percentile": None,
    }
    _apply_tf_change(row, quote, tf_id, bars=bars)
    return row


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
    return _trim_swing_period_stub(bars, str(tf.get("resolution") or ""))


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
    wins = _tf_study_windows(tf_id)
    return _enrich_exchange_volume_kpis(
        [by_date[k] for k in sorted(by_date.keys())],
        rvol_window=wins["rvol_window"],
    )


def _enrich_exchange_volume_kpis(rows: list[dict], rvol_window: int = CS_RVOL) -> list[dict]:
    """Volume-only KPIs: total, AvgN, Δ total/NSE/BSE, RVOL, spike, delivery %."""
    win = max(3, int(rvol_window or CS_RVOL))
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
    """Combined Volume + Technical + Lab + Chart readout for one symbol."""
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
    cache_key = ("dossier-v8", symbol, sc_id, tf_id, exchange, str(indicators or ""))
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
        fut_chart = pool.submit(_scan_chart_row, preset, tf_id, with_quote=True)
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


def _chart_dashboard(rows: list[dict]) -> dict:
    """ChartSchool families — gaps and patterns are not one bucket.

    Breakaway / runaway / exhaustion are different gap types (ChartSchool).
    Continuation vs reversal, and confirmed only after the boundary/neckline break.
    """

    def n(pred) -> int:
        return sum(1 for r in rows if pred(r))

    def gap_is(*kinds: str):
        return lambda r: (r.get("gap") or "none") in kinds

    bull_candle = {"hammer", "engulfing_bull"}
    bear_candle = {"shooting_star", "engulfing_bear"}
    scores = [r.get("score") for r in rows if r.get("score") is not None]
    confs = [r.get("confluence") for r in rows if r.get("confluence") is not None]
    return {
        "bullish": n(lambda r: r.get("bias") == "bullish"),
        "bearish": n(lambda r: r.get("bias") == "bearish"),
        "high_edge": n(lambda r: r.get("high_edge")),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "avg_confluence": round(sum(confs) / len(confs), 1) if confs else None,
        "near_support": n(lambda r: r.get("near_support")),
        "near_resistance": n(lambda r: r.get("near_resistance")),
        "breakout": n(lambda r: r.get("break_resistance")),
        "breakdown": n(lambda r: r.get("break_support")),
        "vol_break": n(
            lambda r: "vol_breakout" in (r.get("edges") or [])
            or "vol_breakdown" in (r.get("edges") or [])
        ),
        "trend_up": n(lambda r: r.get("trend") == "up"),
        "trend_down": n(lambda r: r.get("trend") == "down"),
        "trend_valid": n(lambda r: r.get("trend_valid")),
        "gaps": n(lambda r: r.get("gap") and r.get("gap") != "none"),
        "gap_breakaway": n(gap_is("up_breakaway", "down_breakaway")),
        "gap_runaway": n(gap_is("up_runaway", "down_runaway")),
        "gap_exhaustion": n(gap_is("up_exhaustion", "down_exhaustion")),
        "gap_common": n(gap_is("up_common", "down_common")),
        "patterns": n(lambda r: r.get("pattern") and r.get("pattern") != "none"),
        "pattern_cont": n(lambda r: r.get("pattern_role") == "continuation"),
        "pattern_rev": n(lambda r: r.get("pattern_role") == "reversal"),
        "pattern_confirmed": n(lambda r: r.get("pattern_confirmed")),
        "fib_zone": n(lambda r: r.get("fib_zone")),
        "candles": n(lambda r: r.get("candle") and r.get("candle") != "none"),
        "candle_bull": n(lambda r: r.get("candle") in bull_candle),
        "candle_bear": n(lambda r: r.get("candle") in bear_candle),
        "candle_context": n(
            lambda r: r.get("candle")
            and r.get("candle") not in ("none", "doji")
            and r.get("candle_quality")
            and not str(r.get("candle_quality")).endswith("_weak")
        ),
        "thin": n(lambda r: r.get("history") == "thin"),
        "partial": n(lambda r: r.get("history") == "partial"),
    }


_CANDLE_BODY_FLAT = 0.15  # candle body % treated as a doji
_CANDLE_NET_FLAT = 0.35  # window open→close % that stays neutral
_CANDLE_WINDOWS = (3, 5, 7)


def _resample_calendar(bars: list[dict], period: str) -> list[dict]:
    """Fold daily bars into calendar weeks (Monday) or calendar months.

    The current, unfinished week or month stays as the last candle.
    """
    if not bars:
        return []
    buckets: dict[str, dict] = {}
    order: list[str] = []
    for bar in bars:
        when = datetime.fromtimestamp(int(bar["ts"]), tz=IST)
        if period == "W":
            year, week, _weekday = when.isocalendar()
            key = f"{year}-W{week:02d}"
        else:
            key = when.strftime("%Y-%m")
        high = bar.get("high") if bar.get("high") is not None else bar["close"]
        low = bar.get("low") if bar.get("low") is not None else bar["close"]
        if key not in buckets:
            order.append(key)
            buckets[key] = {
                "ts": bar["ts"],
                "date": bar["date"],
                "open": bar.get("open") if bar.get("open") is not None else bar["close"],
                "high": high,
                "low": low,
                "close": bar["close"],
                "volume": int(bar.get("volume") or 0),
            }
            continue
        slot = buckets[key]
        slot["high"] = max(slot["high"], high)
        slot["low"] = min(slot["low"], low)
        slot["close"] = bar["close"]
        slot["ts"] = bar["ts"]
        slot["date"] = bar["date"]
        slot["volume"] += int(bar.get("volume") or 0)
    return [buckets[key] for key in order]


def _candle_stretch(bars: list[dict], n: int) -> dict:
    """Last n candles: bull, bear, or neutral.

    Bull when the window closed up and more candles are green than red.
    Bear is the mirror. A doji body under 0.15% does not vote. A net move
    inside ±0.35% stays neutral even if the colors lean one way.
    """
    empty = {"bias": None, "net": None, "up": None, "down": None}
    if len(bars) < n:
        return empty
    window = bars[-n:]
    first_open = window[0].get("open")
    if first_open is None:
        first_open = window[0]["close"]
    last_close = window[-1]["close"]
    if not first_open:
        return empty
    net = (last_close - first_open) / first_open * 100.0
    up = down = 0
    for bar in window:
        opened = bar.get("open") if bar.get("open") is not None else bar["close"]
        if not opened:
            continue
        body = (bar["close"] - opened) / opened * 100.0
        if body > _CANDLE_BODY_FLAT:
            up += 1
        elif body < -_CANDLE_BODY_FLAT:
            down += 1
    # A color tie follows the net move. Opposite colors keep the window neutral.
    if net >= _CANDLE_NET_FLAT and up >= down:
        bias = "bull"
    elif net <= -_CANDLE_NET_FLAT and down >= up:
        bias = "bear"
    else:
        bias = "neutral"
    return {"bias": bias, "net": round(net, 2), "up": up, "down": down}


def _scan_candle_row(preset: dict) -> dict | None:
    """One year of daily candles, then the last 3/5/7 days, weeks, and months."""
    bars = _load_bars(
        preset["nse"],
        "1y",
        exchange=preset.get("exchange") or "NSE",
        fast=True,
    )
    if not bars:
        return None
    weekly = _resample_calendar(bars, "W")
    monthly = _resample_calendar(bars, "M")
    last = bars[-1]
    closes = [float(b["close"]) for b in bars if b.get("close") is not None]
    spark = _spark_closes(closes, 30)
    spark_up = bool(len(closes) >= 2 and closes[-1] >= closes[-min(30, len(closes))])
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
    row: dict = {
        "id": preset["id"],
        "nse": quote.get("NSEID") or quote.get("BSEID") or preset["nse"],
        "name": quote.get("company") or preset.get("label") or preset["nse"],
        "sc_id": preset.get("sc_id"),
        "exchange": quote.get("_market") or preset.get("exchange") or "NSE",
        "sector": quote.get("SC_SUBSEC") or quote.get("newSubsector") or preset.get("industry") or "",
        "close": last["close"],
        "change_pct": last.get("change_pct"),
        "up": last.get("up"),
        "volume": last.get("volume"),
        "spark": spark,
        "spark_up": spark_up,
    }
    # Candles is always a daily desk — live session % (not bar-gap).
    _apply_tf_change(row, quote, "1d", bars=bars)
    score = 0
    filled = 0
    for n in _CANDLE_WINDOWS:
        for prefix, series in (("d", bars), ("w", weekly), ("m", monthly)):
            stretch = _candle_stretch(series, n)
            key = f"{prefix}{n}"
            row[key] = stretch["bias"]
            row[f"{key}_net"] = stretch["net"]
            row[f"{key}_up"] = stretch["up"]
            row[f"{key}_down"] = stretch["down"]
            if stretch["bias"] == "bull":
                score += 1
                filled += 1
            elif stretch["bias"] == "bear":
                score -= 1
                filled += 1
            elif stretch["bias"] == "neutral":
                filled += 1
    row["score"] = score
    row["windows"] = filled
    row["bias"] = "bullish" if score >= 3 else "bearish" if score <= -3 else "neutral"
    # Horizon lean: ≥2 of 3 windows bull / bear on that horizon.
    for prefix in ("d", "w", "m"):
        bulls = sum(1 for n in _CANDLE_WINDOWS if row.get(f"{prefix}{n}") == "bull")
        bears = sum(1 for n in _CANDLE_WINDOWS if row.get(f"{prefix}{n}") == "bear")
        row[f"{prefix}_lean"] = "bull" if bulls >= 2 else "bear" if bears >= 2 else "flat"
    # Extra short window for the 2D↑ filter / column (not part of Score ±N/9).
    stretch2 = _candle_stretch(bars, 2)
    row["d2"] = stretch2["bias"]
    row["d2_net"] = stretch2["net"]
    row["d2_up"] = stretch2["up"]
    row["d2_down"] = stretch2["down"]
    turn_kind, turn_strength = _candle_turnaround(row)
    row["turn"] = turn_kind  # bull | bear | None
    row["turn_strength"] = turn_strength  # 0..3
    # Signed turn score for sorting: bull +1..+3 · bear −1..−3 · else 0
    if turn_kind == "bull":
        row["turn_score"] = turn_strength
    elif turn_kind == "bear":
        row["turn_score"] = -turn_strength
    else:
        row["turn_score"] = 0
    return row


def _candle_horizon_points(row: dict, prefix: str) -> int:
    """Sum of bull(+1)/bear(−1) across 3/5/7 windows on one horizon (−3…+3)."""
    total = 0
    for n in _CANDLE_WINDOWS:
        bias = row.get(f"{prefix}{n}")
        if bias == "bull":
            total += 1
        elif bias == "bear":
            total -= 1
    return total


def _candle_turnaround(row: dict) -> tuple[str | None, int]:
    """Detect short-term turn vs longer horizon.

    Bull turn: month still weak (≤ −2), days recovering (day ≥ +1 or flat+2D bull).
    Bear turn: month still strong (≥ +2), days rolling over.
    Strength 1…3 from day lean / 2D confirmation.
    Not part of Score ±N/9.
    """
    day = _candle_horizon_points(row, "d")
    week = _candle_horizon_points(row, "w")
    month = _candle_horizon_points(row, "m")
    d2 = row.get("d2")
    d2_pt = 1 if d2 == "bull" else -1 if d2 == "bear" else 0

    if month <= -2 and (day >= 1 or (day >= 0 and d2_pt == 1)):
        strength = 1
        if day >= 2 or row.get("d_lean") == "bull":
            strength += 1
        if d2_pt == 1:
            strength += 1
        return "bull", min(3, strength)

    if month >= 2 and (day <= -1 or (day <= 0 and d2_pt == -1)):
        strength = 1
        if day <= -2 or row.get("d_lean") == "bear":
            strength += 1
        if d2_pt == -1:
            strength += 1
        return "bear", min(3, strength)

    # Milder week+month setup with a clear 2D+day flip
    if month <= -1 and week <= 0 and day >= 2 and d2_pt == 1:
        return "bull", 2
    if month >= 1 and week >= 0 and day <= -2 and d2_pt == -1:
        return "bear", 2

    return None, 0


def _candle_dashboard(rows: list[dict]) -> dict:
    """Book-level candle KPIs for the Candles desk strip."""
    n = len(rows) or 1

    def lean(prefix: str, side: str) -> int:
        return sum(1 for row in rows if row.get(f"{prefix}_lean") == side)

    scores = [row.get("score") for row in rows if row.get("score") is not None]
    avg = round(sum(scores) / len(scores), 1) if scores else None
    return {
        "bullish": sum(1 for row in rows if row.get("bias") == "bullish"),
        "bearish": sum(1 for row in rows if row.get("bias") == "bearish"),
        "neutral": sum(1 for row in rows if row.get("bias") == "neutral"),
        "aligned": sum(1 for row in rows if abs(row.get("score") or 0) >= 6),
        "day_bull": lean("d", "bull"),
        "day_bear": lean("d", "bear"),
        "week_bull": lean("w", "bull"),
        "week_bear": lean("w", "bear"),
        "month_bull": lean("m", "bull"),
        "month_bear": lean("m", "bear"),
        "avg_score": avg,
        "book": len(rows),
        "pct_bullish": round(100.0 * sum(1 for row in rows if row.get("bias") == "bullish") / n, 0),
    }


CANDLE_FORMULAS = {
    "window": (
        "Each cell is Bull/Bear/Flat (green/window). Daily has 2D plus 3/5/7; weekly and monthly "
        "use 3/5/7 from the same year folded by calendar week and month. "
        "The unfinished week and month stay as the latest candle. 2D feeds the 2D↑ filter only."
    ),
    "bias": (
        "Bull (e.g. 2/3): window close is at least 0.35% above the first open, and green candles "
        "are at least as many as red. Bear is the mirror. A color tie follows the net move. "
        "Opposite colors, or a net move inside ±0.35%, stay Flat. "
        "A candle body under 0.15% is a doji and does not vote."
    ),
    "score": (
        "Score = bull windows − bear windows, shown as ±N/9 across 3/5/7 × Day/Week/Month only "
        "(2D and Turn are excluded). Row bias is bullish at Score ≥ +3 and bearish at Score ≤ −3. "
        "Close is green when the day is up."
    ),
    "turn": (
        "Turnaround vs the month. Bull turn: month windows still weak (≤ −2) while days recover "
        "(day ≥ +1 or flat day + 2D bull). Bear turn is the mirror. Strength 1…3 from day lean / 2D. "
        "Shown as ↑N / ↓N. Filter tabs Turn↑ / Turn↓."
    ),
}


def build_candle_board(
    universe_id: str = "nifty50",
    fresh: bool = False,
    progress_job: str | None = None,
) -> dict:
    _ensure_universe_ready()
    meta = _universe_meta(universe_id)
    universe_id = meta["id"]
    presets = _load_universe(universe_id)
    cache_key = ("candle-board-v8", universe_id)
    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                _scan_job_finish(progress_job, ok=True)
                return payload

    _scan_job_start(
        progress_job,
        total=len(presets),
        phase="scan",
        label=f"{meta['label']} · Candles",
    )
    errors = 0
    workers = 16 if _universe_is_large(universe_id) else 12
    try:
        rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_scan_candle_row, preset): preset for preset in presets}
            for future in _as_completed_progress(futures, progress_job, phase="scan"):
                try:
                    row = future.result()
                except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                    errors += 1
                    continue
                if row:
                    rows.append(row)
        universe_note = (
            f"{meta['label']}: candle-read {len(rows)}/{len(presets)}"
            f" of {_universe_full_size(universe_id)}"
        )
    except Exception as exc:
        _scan_job_finish(progress_job, ok=False, error=str(exc))
        raise

    rows.sort(key=lambda item: (-(item.get("score") or 0), item.get("nse") or ""))
    total = len(rows) or 1
    for idx, row in enumerate(rows):
        row["rank"] = idx + 1
        row["percentile"] = round(100.0 * (total - idx) / total, 1)

    sources = verify_sources()
    payload = {
        "as_of": _ist_stamp(),
        "cached": False,
        "desk": "candle",
        "session": session_status(),
        "timeframe": "1y",
        "timeframe_label": "Daily · 2D + 3/5/7 D W M",
        "universe": universe_id,
        "universe_label": meta["label"],
        "universe_size": _universe_full_size(universe_id),
        "universe_scanable": len(presets),
        "scanned": len(rows),
        "errors": errors,
        "formulas": CANDLE_FORMULAS,
        "source": {
            "name": sources.get("plot_source") or "Yahoo",
            "verified": bool(sources.get("ready")),
            "note": universe_note + " · last 3/5/7 daily, weekly, and monthly candles",
        },
        "sources": sources.get("sources", []),
        "counts": {
            "all": len(rows),
            "bullish": sum(1 for row in rows if row.get("bias") == "bullish"),
            "bearish": sum(1 for row in rows if row.get("bias") == "bearish"),
            "neutral": sum(1 for row in rows if row.get("bias") == "neutral"),
            "aligned": sum(1 for row in rows if abs(row.get("score") or 0) >= 6),
            "turn_bull": sum(1 for row in rows if row.get("turn") == "bull"),
            "turn_bear": sum(1 for row in rows if row.get("turn") == "bear"),
        },
        "dashboard": _candle_dashboard(rows),
        "rows": rows,
    }
    with _cache_lock:
        _cache[cache_key] = (time.time(), payload)
    _scan_job_finish(progress_job, ok=True)
    return payload


def build_chart_board(
    tf_id: str = "1d",
    universe_id: str = "nifty50",
    fresh: bool = False,
    progress_job: str | None = None,
) -> dict:
    _ensure_universe_ready()
    tf_id = _normalize_tf(tf_id)
    # ChartSchool patterns need day/week/month structure — skip Intraday noise.
    if tf_id in {"15m", "1h", "4h"}:
        tf_id = "1d"
    tf = TIMEFRAMES[tf_id]
    meta = _universe_meta(universe_id)
    universe_id = meta["id"]
    presets = _load_universe(universe_id)
    cache_key = ("chart-board-v20", universe_id, tf_id)
    now = time.time()
    if not fresh:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and now - cached[0] < CACHE_TTL:
                payload = dict(cached[1])
                payload["cached"] = True
                payload["session"] = session_status()
                _scan_job_finish(progress_job, ok=True)
                return payload

    _scan_job_start(
        progress_job,
        total=len(presets),
        phase="scan",
        label=f"{meta['label']} · Chart",
    )
    errors = 0
    try:
        if _universe_is_large(universe_id):
            # Whole book. The old cap kept only the 1,200 highest-volume quotes,
            # so quieter names such as 3MINDIA stayed on the board with no chart fields.
            rows = []
            with ThreadPoolExecutor(max_workers=16) as pool:
                futures = {
                    pool.submit(_scan_chart_row, preset, tf_id): preset for preset in presets
                }
                for future in _as_completed_progress(futures, progress_job, phase="enrich"):
                    try:
                        row = future.result()
                    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                        errors += 1
                        continue
                    if row:
                        rows.append(row)
            universe_note = (
                f"{meta['label']}: chart-enriched {len(rows)}/{len(presets)}"
                f" of {_universe_full_size(universe_id)}"
            )
        else:
            rows = []
            with ThreadPoolExecutor(max_workers=12) as pool:
                futures = {
                    pool.submit(_scan_chart_row, preset, tf_id): preset for preset in presets
                }
                for future in _as_completed_progress(futures, progress_job, phase="scan"):
                    try:
                        row = future.result()
                    except (URLError, HTTPError, TimeoutError, OSError, ValueError, RuntimeError):
                        errors += 1
                        continue
                    if row:
                        rows.append(row)
            universe_note = f"{meta['label']} Chart Analysis · {tf['label']} · ChartSchool"
    except Exception as exc:
        _scan_job_finish(progress_job, ok=False, error=str(exc))
        raise

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
        "column_labels": dict(CHART_COLUMN_LABELS),
        "toc": "https://chartschool.stockcharts.com/table-of-contents/chart-analysis",
        "dashboard": _chart_dashboard(rows),
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
    _scan_job_finish(progress_job, ok=True)
    return payload


def clear_runtime_caches() -> dict:
    """Drop all in-process board / probe caches (global Clear cache)."""
    global _probe_cache
    board_n = 0
    with _cache_lock:
        board_n = len(_cache)
        _cache.clear()
    _probe_cache = None
    with _yahoo_hist_lock:
        _yahoo_hist.clear()
    return {
        "ok": True,
        "as_of": _ist_stamp(),
        "cleared": {"boards": board_n, "probe": True},
    }


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
        raw = json.dumps(payload, separators=(",", ":")).encode()
        accept = self.headers.get("Accept-Encoding") or ""
        if "gzip" in accept and len(raw) > 2048:
            body = gzip.compress(raw, compresslevel=5)
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
            return
        self._send(code, raw, "application/json; charset=utf-8")

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
        if parsed.path == "/api/scan-progress":
            self._json(get_scan_progress((params.get("job") or [""])[0]))
            return
        if parsed.path == "/api/board":
            try:
                self._json(
                    build_board(
                        tf_id=(params.get("tf") or params.get("timeframe") or ["1d"])[0],
                        universe_id=(params.get("universe") or ["nifty50"])[0],
                        fresh=(params.get("fresh") or ["0"])[0] == "1",
                        progress_job=(params.get("job") or [None])[0],
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
                        progress_job=(params.get("job") or [None])[0],
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
                        progress_job=(params.get("job") or [None])[0],
                    )
                )
            except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
                self._json({"error": f"Upstream failed: {exc}"}, code=502)
            return
        if parsed.path == "/api/candle-board":
            try:
                self._json(
                    build_candle_board(
                        universe_id=(params.get("universe") or ["nifty50"])[0],
                        fresh=(params.get("fresh") or ["0"])[0] == "1",
                        progress_job=(params.get("job") or [None])[0],
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
                        progress_job=(params.get("job") or [None])[0],
                    )
                )
            except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
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
                            "size": _universe_full_size(item["id"]),
                            "scanable": len(_load_universe(item["id"])),
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
    print(f"UI: {ui} · Volume · Technical · Lab · Chart · Candles. Press Ctrl+C to stop.")
    print("Universe: NSE/BSE dimension · refresh every Monday 07:00 IST")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
