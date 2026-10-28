#!/usr/bin/env python3
"""Common universe dimension from NSE + BSE official sources.

Writes data/universe_dim.json. Refresh every Monday 07:00 IST (server scheduler
or: python universe_dim.py --refresh).

Sources (exchange-only):
  NSE archives — index constituent CSVs + EQUITY_L.csv
  BSE India API — ListofScripData (Active Equity)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import ssl
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DIM_PATH = DATA_DIR / "universe_dim.json"
SC_ID_CACHE_PATH = DATA_DIR / "sc_id_cache.json"
IST = ZoneInfo("Asia/Kolkata")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

NSE_INDEX_CSVS = {
    "nifty50": (
        "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv",
        "Nifty 50",
        50,
    ),
    "next50": (
        "https://nsearchives.nseindia.com/content/indices/ind_niftynext50list.csv",
        "Nifty Next 50",
        50,
    ),
    "largecap": (
        "https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv",
        "Nifty 100",
        100,
    ),
    "nifty200": (
        "https://nsearchives.nseindia.com/content/indices/ind_nifty200list.csv",
        "Nifty 200",
        200,
    ),
    "nifty500": (
        "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
        "Nifty 500",
        500,
    ),
    "midcap50": (
        "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap50list.csv",
        "Nifty Midcap 50",
        50,
    ),
    "midcap": (
        "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
        "Nifty Midcap 150",
        150,
    ),
    "smallcap50": (
        "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap50list.csv",
        "Nifty Smallcap 50",
        50,
    ),
    "smallcap": (
        "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "Nifty Smallcap 250",
        250,
    ),
    "microcap": (
        "https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv",
        "Nifty Microcap 250",
        250,
    ),
    "largemidcap": (
        "https://nsearchives.nseindia.com/content/indices/ind_niftylargemidcap250list.csv",
        "Nifty LargeMidcap 250",
        250,
    ),
}

NSE_EQUITY_CSV = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
BSE_SCRIP_API = (
    "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
    "?Group=&Scripcode=&industry=&segment=Equity&status=Active"
)

# Scan-ready metadata (enrich_limit = full history enrich cap for large books;
# remaining names still appear via quote-pass on dashboards).
# Order = Book dropdown: Nifty ladder → cap slices → BSE groups → full exchange.
UNIVERSE_META = [
    {"id": "nifty50", "label": "Nifty 50", "group": "Nifty", "enrich_limit": 50, "exchange": "NSE"},
    {"id": "next50", "label": "Nifty Next 50", "group": "Nifty", "enrich_limit": 50, "exchange": "NSE"},
    {"id": "largecap", "label": "Nifty 100", "group": "Nifty", "enrich_limit": 100, "exchange": "NSE"},
    {"id": "nifty200", "label": "Nifty 200", "group": "Nifty", "enrich_limit": 200, "exchange": "NSE"},
    {"id": "nifty500", "label": "Nifty 500", "group": "Nifty", "enrich_limit": 500, "exchange": "NSE"},
    {
        "id": "midcap50",
        "label": "Nifty Midcap 50",
        "group": "Cap",
        "enrich_limit": 50,
        "exchange": "NSE",
    },
    {
        "id": "midcap",
        "label": "Nifty Midcap 150",
        "group": "Cap",
        "enrich_limit": 150,
        "exchange": "NSE",
    },
    {
        "id": "smallcap50",
        "label": "Nifty Smallcap 50",
        "group": "Cap",
        "enrich_limit": 50,
        "exchange": "NSE",
    },
    {
        "id": "smallcap",
        "label": "Nifty Smallcap 250",
        "group": "Cap",
        "enrich_limit": 250,
        "exchange": "NSE",
    },
    {
        "id": "microcap",
        "label": "Nifty Microcap 250",
        "group": "Cap",
        "enrich_limit": 250,
        "exchange": "NSE",
    },
    {
        "id": "largemidcap",
        "label": "Nifty LargeMidcap 250",
        "group": "Cap",
        "enrich_limit": 250,
        "exchange": "NSE",
    },
    {
        "id": "bse_large",
        "label": "BSE Group A",
        "group": "BSE",
        "enrich_limit": 700,
        "exchange": "BSE",
        "large": True,
    },
    {
        "id": "bse_mid",
        "label": "BSE Group B",
        "group": "BSE",
        "enrich_limit": 1200,
        "exchange": "BSE",
        "large": True,
    },
    {
        "id": "nse_all",
        "label": "NSE All",
        "group": "Exchange",
        "enrich_limit": 1200,
        "exchange": "NSE",
        "large": True,
    },
    {
        "id": "bse_all",
        "label": "BSE All",
        "group": "Exchange",
        "enrich_limit": 1200,
        "exchange": "BSE",
        "large": True,
    },
    {
        "id": "all",
        "label": "NSE All",
        "group": "Exchange",
        "enrich_limit": 1200,
        "exchange": "NSE",
        "large": True,
        "alias_of": "nse_all",
    },
]

# Cash market series included in NSE All (official EQUITY_L).
NSE_ALL_SERIES = {"EQ", "BE"}

_CA_FILES = (
    "/etc/ssl/cert.pem",
    "/private/etc/ssl/cert.pem",
    "/etc/ssl/certs/ca-certificates.crt",
)

_dim_lock = threading.Lock()
_dim_mem: dict[str, Any] | None = None
_scheduler_started = False


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


def _ist_now() -> datetime:
    return datetime.now(IST)


def _next_monday_7am(now: datetime | None = None) -> datetime:
    local = (now or _ist_now()).astimezone(IST)
    # Days until Monday (0); if Monday before 07:00, today; if Monday after, next week.
    days_ahead = (0 - local.weekday()) % 7
    candidate = (local + timedelta(days=days_ahead)).replace(
        hour=7, minute=0, second=0, microsecond=0
    )
    if candidate <= local:
        candidate += timedelta(days=7)
    return candidate


def _last_monday_7am(now: datetime | None = None) -> datetime:
    local = (now or _ist_now()).astimezone(IST)
    days_back = local.weekday() % 7  # Mon=0
    candidate = (local - timedelta(days=days_back)).replace(
        hour=7, minute=0, second=0, microsecond=0
    )
    if local < candidate:
        candidate -= timedelta(days=7)
    return candidate


def _fetch_text_nse(url: str, timeout: float = 45) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Referer": "https://www.nseindia.com/",
        },
    )
    with urlopen(req, timeout=timeout, context=SSL_CONTEXT) as response:
        return response.read().decode("utf-8", "replace")


def _fetch_bse_scrips(timeout: float = 60) -> list[dict]:
    try:
        from curl_cffi import requests as creq  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Install curl_cffi for BSE dimension refresh: pip install curl_cffi"
        ) from exc
    session = creq.Session()
    base = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    session.get("https://www.bseindia.com/", headers=base, impersonate="chrome131", timeout=timeout)
    response = session.get(
        BSE_SCRIP_API,
        headers={
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.bseindia.com/",
            "Origin": "https://www.bseindia.com",
        },
        impersonate="chrome131",
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"BSE ListofScripData HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("BSE ListofScripData: unexpected payload")
    return payload


def _parse_nse_index_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for item in reader:
        symbol = (item.get("Symbol") or item.get("SYMBOL") or "").strip().upper()
        if not symbol:
            continue
        name = (item.get("Company Name") or item.get("Company") or symbol).strip()
        industry = (item.get("Industry") or "").strip()
        series = (item.get("Series") or "EQ").strip()
        isin = (item.get("ISIN Code") or item.get("ISIN") or "").strip().upper()
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "industry": industry,
                "series": series,
                "isin": isin,
            }
        )
    return rows


def _parse_nse_equity_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for item in reader:
        # Header keys may have leading spaces (e.g. " SERIES")
        cleaned = {str(k).strip(): (v or "").strip() for k, v in item.items() if k}
        symbol = (cleaned.get("SYMBOL") or "").upper()
        if not symbol:
            continue
        series = (cleaned.get("SERIES") or "").upper()
        if series not in NSE_ALL_SERIES:
            continue
        name = cleaned.get("NAME OF COMPANY") or symbol
        isin = (cleaned.get("ISIN NUMBER") or "").upper()
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "series": series or "EQ",
                "isin": isin,
                "listing_date": cleaned.get("DATE OF LISTING") or "",
                "face_value": cleaned.get("FACE VALUE") or "",
            }
        )
    return rows


def _load_sc_id_cache() -> dict[str, str]:
    if not SC_ID_CACHE_PATH.is_file():
        return {}
    try:
        raw = json.loads(SC_ID_CACHE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k).upper(): str(v) for k, v in raw.items() if k and v}


def _save_sc_id_cache(cache: dict[str, str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ordered = {k: cache[k] for k in sorted(cache)}
    SC_ID_CACHE_PATH.write_text(json.dumps(ordered, indent=0, sort_keys=True) + "\n")


def _mc_lookup_sc_id(query: str) -> str | None:
    """Resolve Moneycontrol sc_id via official autosuggest (for price join only)."""
    q = (query or "").strip()
    if len(q) < 1:
        return None
    url = (
        "https://www.moneycontrol.com/mccode/common/autosuggestion_solr.php"
        f"?classic=true&query={quote(q)}&type=1&format=json"
    )
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.moneycontrol.com/",
        },
    )
    try:
        with urlopen(req, timeout=12, context=SSL_CONTEXT) as response:
            items = json.loads(response.read())
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(items, list):
        return None
    q_up = q.upper()
    for item in items:
        if not isinstance(item, dict):
            continue
        sc_id = str(item.get("sc_id") or "").strip()
        display = str(item.get("pdt_dis_nm") or "")
        match = re.search(r",\s*([A-Z0-9.&-]{1,20}),\s*\d{4,}", display)
        nse = (match.group(1) if match else "").upper()
        if sc_id and (nse == q_up or q_up in display.upper()):
            return sc_id
    for item in items:
        if isinstance(item, dict) and item.get("sc_id"):
            return str(item["sc_id"]).strip()
    return None


def _backfill_sc_ids(
    symbols: list[str],
    cache: dict[str, str],
    *,
    limit: int = 400,
) -> int:
    """Fill missing NSE symbol → sc_id mappings; returns newly resolved count."""
    missing = [s for s in symbols if s and s.upper() not in cache]
    if not missing:
        return 0
    resolved = 0
    for i, sym in enumerate(missing[:limit]):
        sc_id = _mc_lookup_sc_id(sym)
        if sc_id:
            cache[sym.upper()] = sc_id
            resolved += 1
        if i and i % 40 == 0:
            time.sleep(0.12)
    if resolved:
        _save_sc_id_cache(cache)
    return resolved


def _preset_row(
    *,
    symbol: str,
    name: str,
    exchange: str,
    isin: str = "",
    series: str = "EQ",
    bse_code: str = "",
    industry: str = "",
    sc_id: str | None = None,
    group: str = "",
) -> dict:
    row = {
        "id": symbol,
        "label": (name or symbol)[:64],
        "nse": symbol if exchange == "NSE" else "",
        "bse": bse_code,
        "isin": isin,
        "exchange": exchange,
        "series": series or "EQ",
        "industry": industry,
        "group": group,
        "sc_id": sc_id or "",
    }
    if exchange == "BSE" and not row["nse"] and symbol:
        # BSE ticker often matches NSE; keep for MC join attempts.
        row["nse"] = symbol
    return row


def build_dimension() -> dict[str, Any]:
    """Fetch NSE + BSE lists and assemble universe_dim payload."""
    sc_cache = _load_sc_id_cache()
    sources: dict[str, Any] = {
        "nse_indices": {},
        "nse_equity": NSE_EQUITY_CSV,
        "bse_equity": BSE_SCRIP_API,
        "nse_series": sorted(NSE_ALL_SERIES),
    }

    index_members: dict[str, list[dict]] = {}
    for uid, (url, label, _limit) in NSE_INDEX_CSVS.items():
        text = _fetch_text_nse(url)
        parsed = _parse_nse_index_csv(text)
        sources["nse_indices"][uid] = {"url": url, "label": label, "count": len(parsed)}
        index_members[uid] = parsed

    nse_equity = _parse_nse_equity_csv(_fetch_text_nse(NSE_EQUITY_CSV))
    sources["nse_equity_count"] = len(nse_equity)

    bse_raw = _fetch_bse_scrips()
    sources["bse_equity_count"] = len(bse_raw)

    # ISIN → NSE symbol for BSE → sc_id join
    isin_to_nse: dict[str, str] = {}
    for item in nse_equity:
        if item.get("isin"):
            isin_to_nse[item["isin"]] = item["symbol"]
    for members in index_members.values():
        for item in members:
            if item.get("isin"):
                isin_to_nse.setdefault(item["isin"], item["symbol"])

    # Backfill Moneycontrol sc_id for exchange symbols still missing in cache.
    nse_symbols = sorted({item["symbol"] for item in nse_equity})
    for members in index_members.values():
        nse_symbols.extend(item["symbol"] for item in members)
    nse_symbols = sorted(set(nse_symbols))
    filled_nse = _backfill_sc_ids(nse_symbols, sc_cache, limit=500)
    sources["sc_id_backfill_nse"] = filled_nse

    # Prefer Group A/B BSE tickers for backfill (most liquid / dual-listed gaps).
    bse_tickers: list[str] = []
    for item in bse_raw:
        if not isinstance(item, dict):
            continue
        group = str(item.get("GROUP") or "").strip().upper()
        ticker = str(item.get("scrip_id") or "").strip().upper()
        isin = str(item.get("ISIN_NUMBER") or "").strip().upper()
        if not ticker:
            continue
        if ticker in sc_cache or isin_to_nse.get(isin) in sc_cache:
            continue
        if group in {"A", "B", "T"}:
            bse_tickers.append(ticker)
    filled_bse = _backfill_sc_ids(sorted(set(bse_tickers)), sc_cache, limit=600)
    sources["sc_id_backfill_bse"] = filled_bse
    sources["sc_id_cache_size"] = len(sc_cache)

    def with_sc_id(symbol: str) -> str:
        return sc_cache.get((symbol or "").upper(), "")

    universes: dict[str, list[dict]] = {}
    for uid, members in index_members.items():
        rows = []
        for item in members:
            sym = item["symbol"]
            rows.append(
                _preset_row(
                    symbol=sym,
                    name=item["name"],
                    exchange="NSE",
                    isin=item.get("isin") or "",
                    series=item.get("series") or "EQ",
                    industry=item.get("industry") or "",
                    sc_id=with_sc_id(sym),
                )
            )
        universes[uid] = rows

    nse_all = []
    for item in nse_equity:
        sym = item["symbol"]
        nse_all.append(
            _preset_row(
                symbol=sym,
                name=item["name"],
                exchange="NSE",
                isin=item.get("isin") or "",
                series=item.get("series") or "EQ",
                sc_id=with_sc_id(sym),
            )
        )
    universes["nse_all"] = nse_all
    universes["all"] = list(nse_all)  # backward-compatible alias

    bse_all = []
    for item in bse_raw:
        if not isinstance(item, dict):
            continue
        status = str(item.get("Status") or "").strip().lower()
        if status and status != "active":
            continue
        bse_code = str(item.get("SCRIP_CD") or "").strip()
        ticker = str(item.get("scrip_id") or item.get("Scrip_Name") or "").strip().upper()
        name = str(item.get("Scrip_Name") or ticker or bse_code).strip()
        isin = str(item.get("ISIN_NUMBER") or "").strip().upper()
        group = str(item.get("GROUP") or "").strip()
        if not ticker and not bse_code:
            continue
        symbol = ticker or bse_code
        # Prefer NSE symbol via ISIN for sc_id + dual-listed names.
        nse_sym = isin_to_nse.get(isin) or ""
        if not nse_sym and ticker and ticker in sc_cache:
            nse_sym = ticker
        sc_id = with_sc_id(nse_sym) if nse_sym else with_sc_id(symbol)
        # Also try BSE code as cache key (written during prior backfills).
        if not sc_id and bse_code:
            sc_id = with_sc_id(bse_code) or with_sc_id(f"BSE:{bse_code}")
        row = _preset_row(
            symbol=nse_sym or symbol,
            name=name,
            exchange="BSE",
            isin=isin,
            series="EQ",
            bse_code=bse_code,
            industry="",
            sc_id=sc_id,
            group=group,
        )
        if nse_sym:
            row["nse"] = nse_sym
        elif ticker:
            row["nse"] = ticker
        bse_all.append(row)
    universes["bse_all"] = bse_all
    # BSE liquidity books from official Group field (Sensex/BSE100 APIs are not CSV-stable).
    universes["bse_large"] = [
        r for r in bse_all if str(r.get("group") or "").strip().upper() == "A"
    ]
    universes["bse_mid"] = [
        r for r in bse_all if str(r.get("group") or "").strip().upper() == "B"
    ]

    meta_out = []
    for item in UNIVERSE_META:
        uid = item["id"]
        source_id = item.get("alias_of") or uid
        rows = universes.get(source_id) or universes.get(uid) or []
        scanable = sum(1 for r in rows if r.get("sc_id"))
        meta_out.append(
            {
                **item,
                "count": len(rows),
                "scanable": scanable,
            }
        )

    as_of = _ist_now().isoformat(timespec="seconds")
    payload = {
        "as_of": as_of,
        "as_of_ist": _ist_now().strftime("%a %-d %b %Y · %-I:%M %p IST")
        .replace("AM", "am")
        .replace("PM", "pm"),
        "refreshed_for": _last_monday_7am().isoformat(timespec="seconds"),
        "next_refresh": _next_monday_7am().isoformat(timespec="seconds"),
        "schedule": "Every Monday 07:00 Asia/Kolkata",
        "sources": sources,
        "meta": meta_out,
        "universes": universes,
    }
    return payload


def save_dimension(payload: dict[str, Any], path: Path = DIM_PATH) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=0) + "\n")
    tmp.replace(path)
    # Keep legacy slice files in sync for older tooling.
    uni = payload.get("universes") or {}
    for key, fname in (
        ("nifty500", "nifty500.json"),
        ("nse_all", "all_nse.json"),
    ):
        rows = uni.get(key)
        if rows:
            (DATA_DIR / fname).write_text(json.dumps(rows, indent=0) + "\n")
    global _dim_mem
    with _dim_lock:
        _dim_mem = payload
    return path


def refresh_dimension(force: bool = True) -> dict[str, Any]:
    payload = build_dimension()
    save_dimension(payload)
    return payload


def load_dimension(refresh_if_stale: bool = False) -> dict[str, Any] | None:
    global _dim_mem
    with _dim_lock:
        if _dim_mem is not None:
            payload = _dim_mem
        elif DIM_PATH.is_file():
            try:
                payload = json.loads(DIM_PATH.read_text())
                _dim_mem = payload
            except (OSError, json.JSONDecodeError):
                payload = None
        else:
            payload = None

    if refresh_if_stale and _is_stale(payload):
        try:
            return refresh_dimension()
        except (URLError, HTTPError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
            if payload is not None:
                return payload
            raise RuntimeError(f"Universe dimension refresh failed: {exc}") from exc
    return payload


def _is_stale(payload: dict[str, Any] | None) -> bool:
    """Stale if missing, or file/payload older than this week's Monday 07:00 IST."""
    cutoff = _last_monday_7am()
    if DIM_PATH.is_file():
        mtime = datetime.fromtimestamp(DIM_PATH.stat().st_mtime, tz=IST)
        if mtime < cutoff:
            return True
    if not payload:
        return True
    raw = payload.get("as_of") or payload.get("refreshed_for") or ""
    try:
        as_of = datetime.fromisoformat(str(raw))
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=IST)
        else:
            as_of = as_of.astimezone(IST)
    except ValueError:
        return True
    return as_of < cutoff


def clear_dimension_cache() -> None:
    global _dim_mem
    with _dim_lock:
        _dim_mem = None


def list_universe_meta() -> list[dict]:
    """Book list for UI/API: live UNIVERSE_META order/labels, sizes from dim file."""
    payload = load_dimension(refresh_if_stale=False)
    saved = {m["id"]: m for m in (payload or {}).get("meta") or [] if m.get("id")}
    out = []
    for item in UNIVERSE_META:
        uid = item["id"]
        hit = saved.get(uid) or {}
        row = dict(item)
        if hit.get("count") is not None:
            row["count"] = hit["count"]
        if hit.get("scanable") is not None:
            row["scanable"] = hit["scanable"]
        out.append(row)
    return out


def get_universe_rows(universe_id: str, *, require_sc_id: bool = True) -> list[dict]:
    uid = (universe_id or "nifty50").lower()
    payload = load_dimension(refresh_if_stale=False)
    if not payload:
        return []
    meta_by_id = {m["id"]: m for m in payload.get("meta") or []}
    meta = meta_by_id.get(uid)
    if meta and meta.get("alias_of"):
        uid = meta["alias_of"]
    rows = list((payload.get("universes") or {}).get(uid) or [])
    if require_sc_id:
        rows = [r for r in rows if r.get("sc_id")]
    return rows


def get_universe_meta(universe_id: str) -> dict:
    uid = (universe_id or "nifty50").lower()
    for item in list_universe_meta():
        if item["id"] == uid:
            return item
    return dict(UNIVERSE_META[0])


def is_large_universe(universe_id: str) -> bool:
    meta = get_universe_meta(universe_id)
    if meta.get("large"):
        return True
    return meta.get("id") in {"all", "nse_all", "bse_all", "bse_large", "bse_mid"}


def dimension_status() -> dict[str, Any]:
    payload = load_dimension(refresh_if_stale=False)
    stale = _is_stale(payload)
    file_mtime = None
    if DIM_PATH.is_file():
        file_mtime = datetime.fromtimestamp(DIM_PATH.stat().st_mtime, tz=IST).isoformat(
            timespec="seconds"
        )
    return {
        "path": str(DIM_PATH),
        "exists": DIM_PATH.is_file(),
        "stale": stale,
        "file_mtime": file_mtime,
        "as_of": (payload or {}).get("as_of"),
        "as_of_ist": (payload or {}).get("as_of_ist"),
        "schedule": "Every Monday 07:00 Asia/Kolkata",
        "next_refresh": _next_monday_7am().isoformat(timespec="seconds"),
        "last_monday_7am": _last_monday_7am().isoformat(timespec="seconds"),
        "counts": {
            m["id"]: {"count": m.get("count"), "scanable": m.get("scanable")}
            for m in (payload or {}).get("meta") or []
        },
        "sources": (payload or {}).get("sources"),
    }


def ensure_fresh_dimension() -> dict[str, Any]:
    """Load dim; refresh if missing or older than this week's Monday 07:00 IST."""
    payload = load_dimension(refresh_if_stale=True)
    if payload is None:
        payload = refresh_dimension()
    return payload


def start_monday_refresh_scheduler() -> None:
    """Background: refresh at Monday 07:00 IST; also catch up if stale on boot."""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def _loop() -> None:
        # Boot catch-up
        try:
            if _is_stale(load_dimension(refresh_if_stale=False)):
                print("Universe dim: stale — refreshing from NSE/BSE…")
                refresh_dimension()
                print("Universe dim: refresh complete →", DIM_PATH)
        except Exception as exc:  # noqa: BLE001 — keep server alive
            print(f"Universe dim: boot refresh skipped ({exc})")

        while True:
            target = _next_monday_7am()
            delay = max(5.0, (target - _ist_now()).total_seconds())
            time.sleep(min(delay, 3600.0))  # wake hourly near the window
            if _ist_now() >= target - timedelta(seconds=30):
                try:
                    print("Universe dim: Monday 07:00 IST refresh starting…")
                    refresh_dimension()
                    print("Universe dim: Monday refresh complete →", DIM_PATH)
                    time.sleep(120)  # avoid double-fire
                except Exception as exc:  # noqa: BLE001
                    print(f"Universe dim: Monday refresh failed ({exc})")
                    time.sleep(300)

    thread = threading.Thread(target=_loop, name="universe-dim-refresh", daemon=True)
    thread.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="NSE/BSE universe dimension")
    parser.add_argument("--refresh", action="store_true", help="Fetch and write universe_dim.json")
    parser.add_argument("--status", action="store_true", help="Show dimension status")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(dimension_status(), indent=2))
        return
    if args.refresh or not args.status:
        print("Refreshing universe dimension from NSE + BSE…")
        payload = refresh_dimension()
        print(
            "Wrote",
            DIM_PATH,
            "·",
            payload.get("as_of_ist"),
            "· universes:",
            {m["id"]: m.get("count") for m in payload.get("meta") or []},
        )


if __name__ == "__main__":
    main()
