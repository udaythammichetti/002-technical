#!/usr/bin/env python3
"""Signal Desk — Streamlit UI for Volume / Technical / Lab / Spurts.

Run (from project root, with venv active):
  streamlit run app.py

Backend logic lives in server.py (Moneycontrol OHLC + NSE/BSE spurts).
Research only — not investment advice.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd
import streamlit as st

import server as desk

DESKS = {
    "volume": "Volume",
    "tech": "Technical",
    "sci": "Lab",
    "spurts": "Spurts",
}

UNIVERSE_LABELS = {item["id"]: item["label"] for item in desk.UNIVERSES}
TF_ORDER = list(desk.TIMEFRAMES.keys())
TF_LABELS = {k: v["label"] for k, v in desk.TIMEFRAMES.items()}

TECH_OPTS = [
    ("rsi", "RSI"),
    ("macd", "MACD"),
    ("sma", "SMA 20/50"),
    ("ema", "EMA 20"),
    ("bb", "BB %B"),
    ("stoch", "Stochastic"),
    ("cci", "CCI"),
    ("willr", "Williams %R"),
    ("adx", "ADX + DI"),
    ("roc", "ROC"),
]

VOLUME_TABS = [("trend", "Map"), ("bullish", "Bullish"), ("bearish", "Bearish"), ("spike", "Spike")]
TECH_TABS = [("trend", "Map"), ("bullish", "Bullish"), ("bearish", "Bearish")]
SCI_TABS = [("trend", "Map"), ("bullish", "Bullish"), ("bearish", "Bearish"), ("spike", "Spike")]
SPURT_TABS = [("trend", "All"), ("nse", "NSE"), ("bse", "BSE"), ("spike", "≥3×")]

LEGENDS = {
    "volume": [
        ("Bull ≥+30", "Bias score ≥ +30 — price up with volume confirmation"),
        ("Bear ≤−30", "Bias score ≤ −30 — price down with volume confirmation"),
        ("RVOL", "Relative volume: bar volume ÷ average of prior N bars"),
        ("OBV", "On-Balance Volume — rising = accumulation"),
        ("CMF", "Chaikin Money Flow — buying pressure"),
        ("MFI", "Money Flow Index (0–100)"),
    ],
    "tech": [
        ("Bull ≥+30", "Technical score ≥ +30 from indicator votes"),
        ("Bear ≤−30", "Technical score ≤ −30 from indicator votes"),
        ("RSI / MACD / SMA / EMA / BB / Stoch / CCI / %R / ADX / ROC", "Selected OHLC indicators"),
    ],
    "sci": [
        ("Rank", "Rank 1 = highest lab score"),
        ("RVOL · OBV · CMF · MFI · Force · VOsc · EOM · VWAP · PVT", "Cited volume/flow studies"),
    ],
    "spurts": [
        ("NSE", "Live Volume Gainers (~25 names)"),
        ("BSE", "Live Spurt in Volume — Equity T+1 + T+0 when published"),
        ("Vol×", "Today volume ÷ reference average"),
        ("Refresh", "Auto-polls every ~25s while Spurts is open"),
    ],
}

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Sora:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
  font-family: "Sora", ui-sans-serif, system-ui, sans-serif;
}
.stApp {
  background:
    radial-gradient(900px 380px at 10% -6%, rgba(10, 122, 88, 0.07), transparent 55%),
    linear-gradient(180deg, #f6f7f9 0%, #eef1f4 100%);
}
h1, h2, h3, .desk-title {
  font-family: "Fraunces", Georgia, serif !important;
  letter-spacing: -0.02em;
}
[data-testid="stSidebar"] {
  background: rgba(255,255,255,0.78);
  border-right: 1px solid rgba(16,20,24,0.08);
}
[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
.block-container { padding-top: 1.4rem; max-width: 1280px; }
.desk-kicker {
  color: #5a6470; font-size: 0.78rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.15rem;
}
.desk-title { font-size: 1.65rem; margin: 0 0 0.35rem 0; color: #101418; }
.desk-sub { color: #5a6470; font-size: 0.92rem; margin-bottom: 0.8rem; }
.status-chip {
  display: inline-block; padding: 0.28rem 0.65rem; border-radius: 999px;
  background: rgba(16,20,24,0.05); color: #101418; font-size: 0.8rem;
  font-family: "IBM Plex Mono", ui-monospace, Menlo, monospace;
}
.session-open { color: #0a7a58; font-weight: 600; }
.session-closed { color: #8a5810; font-weight: 600; }
.metric-up { color: #0a7a58; }
.metric-down { color: #b23a32; }
.trend-col {
  background: rgba(255,255,255,0.72); border: 1px solid rgba(16,20,24,0.08);
  border-radius: 12px; padding: 0.75rem 0.85rem; min-height: 220px;
}
.trend-col.bullish { border-top: 3px solid #0a7a58; }
.trend-col.neutral { border-top: 3px solid #8a5810; }
.trend-col.bearish { border-top: 3px solid #b23a32; }
.trend-head { font-size: 0.85rem; font-weight: 600; margin-bottom: 0.55rem; }
.trend-item {
  font-size: 0.8rem; padding: 0.35rem 0; border-bottom: 1px solid rgba(16,20,24,0.06);
  font-family: "IBM Plex Mono", ui-monospace, Menlo, monospace;
}
.foot-note { color: #5a6470; font-size: 0.78rem; margin-top: 1.2rem; }
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
</style>
"""


def _init_state() -> None:
    defaults = {
        "desk": "volume",
        "universe": "nifty50",
        "tf": "1d",
        "tab": "trend",
        "tech_indicators": [k for k, _ in TECH_OPTS],
        "symbol_query": "",
        "symbol": "",
        "sc_id": "",
        "mode": "scan",
        "fresh_nonce": 0,
        "spurt_auto": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _tv_url(symbol: str | None, exchange: str | None = "NSE") -> str:
    raw = (symbol or "").strip().upper()
    if not raw:
        return ""
    ex = "BSE" if str(exchange or "NSE").upper() == "BSE" else "NSE"
    return f"https://www.tradingview.com/chart/?symbol={ex}%3A{raw}"


def _fmt_vol(value: Any) -> str:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return "—"
    if n >= 1e7:
        return f"{n / 1e7:.2f} Cr"
    if n >= 1e5:
        return f"{n / 1e5:.2f} L"
    if n >= 1e3:
        return f"{n / 1e3:.1f}k"
    return str(int(round(n)))


@st.cache_data(ttl=120, show_spinner=False)
def _load_sources(fresh: bool = False) -> dict:
    return desk.verify_sources(fresh=fresh)


@st.cache_data(ttl=90, show_spinner=False)
def _load_volume_board(tf: str, universe: str, nonce: int) -> dict:
    return desk.build_board(tf_id=tf, universe_id=universe, fresh=nonce > 0)


@st.cache_data(ttl=90, show_spinner=False)
def _load_tech_board(tf: str, universe: str, indicators: tuple[str, ...], nonce: int) -> dict:
    return desk.build_tech_board(
        tf_id=tf,
        universe_id=universe,
        indicators=list(indicators),
        fresh=nonce > 0,
    )


@st.cache_data(ttl=90, show_spinner=False)
def _load_sci_board(tf: str, universe: str, nonce: int) -> dict:
    return desk.build_sci_board(tf_id=tf, universe_id=universe, fresh=nonce > 0)


@st.cache_data(ttl=20, show_spinner=False)
def _load_spurts(nonce: int) -> dict:
    return desk.build_spurts_board(fresh=True, exchange="all")


@st.cache_data(ttl=90, show_spinner=False)
def _load_symbol(symbol: str, sc_id: str, tf: str, nonce: int) -> dict:
    return desk.build_volume(
        symbol=symbol,
        sc_id=sc_id or "",
        kind="stock",
        tf_id=tf,
        fresh=nonce > 0,
    )


@st.cache_data(ttl=60, show_spinner=False)
def _search(query: str) -> list[dict]:
    return desk.search_symbols(query)


def _active_tabs(desk_id: str) -> list[tuple[str, str]]:
    if desk_id == "tech":
        return TECH_TABS
    if desk_id == "sci":
        return SCI_TABS
    if desk_id == "spurts":
        return SPURT_TABS
    return VOLUME_TABS


def _filter_rows(rows: list[dict], desk_id: str, tab: str) -> list[dict]:
    if desk_id == "spurts":
        if tab == "nse":
            return [r for r in rows if r.get("exchange") == "NSE"]
        if tab == "bse":
            return [r for r in rows if r.get("exchange") == "BSE"]
        if tab == "spike":
            return [r for r in rows if (r.get("vol_x") or 0) >= 3]
        return rows
    if tab == "bullish":
        return [r for r in rows if r.get("bias") == "bullish"]
    if tab == "bearish":
        return [r for r in rows if r.get("bias") == "bearish"]
    if tab == "spike":
        return [r for r in rows if r.get("spike")]
    return rows


def _tech_derived(row: dict) -> dict:
    out = dict(row)
    sma20, sma50 = row.get("sma20"), row.get("sma50")
    if sma20 is not None and sma50 is not None:
        out["sma_stack"] = 1 if sma20 > sma50 else -1 if sma20 < sma50 else 0
    else:
        out["sma_stack"] = None
    close, ema20 = row.get("close"), row.get("ema20")
    if close is not None and ema20 is not None:
        out["ema_bias"] = 1 if close > ema20 else -1 if close < ema20 else 0
    else:
        out["ema_bias"] = None
    return out


def _board_dataframe(rows: list[dict], desk_id: str, indicators: list[str]) -> pd.DataFrame:
    if desk_id == "spurts":
        records = []
        for r in rows:
            records.append(
                {
                    "Rank": r.get("rank"),
                    "Exch": r.get("exchange"),
                    "Symbol": r.get("nse") or r.get("id"),
                    "Chg %": r.get("change_pct"),
                    "Vol×": r.get("vol_x"),
                    "Volume": r.get("volume"),
                    "Avg": r.get("avg_volume"),
                    "LTP": r.get("ltp"),
                    "Turnover": r.get("turnover"),
                    "Score": r.get("score"),
                    "Settlement": r.get("settlement"),
                    "TV": _tv_url(r.get("nse") or r.get("id"), r.get("exchange")),
                }
            )
        return pd.DataFrame(records)

    if desk_id == "sci":
        records = []
        for r in rows:
            records.append(
                {
                    "Rank": r.get("rank"),
                    "Symbol": r.get("nse"),
                    "Chg %": r.get("change_pct"),
                    "RVOL": r.get("rvol"),
                    "CMF": r.get("cmf"),
                    "MFI": r.get("mfi"),
                    "Force": r.get("force"),
                    "VOsc": r.get("voscil"),
                    "EOM": r.get("eom"),
                    "VWAP%": r.get("vwap_bias"),
                    "Score": r.get("score"),
                    "%ile": r.get("percentile"),
                    "Bias": r.get("bias"),
                    "TV": _tv_url(r.get("nse")),
                }
            )
        return pd.DataFrame(records)

    if desk_id == "tech":
        allow = set(indicators)
        records = []
        for raw in rows:
            r = _tech_derived(raw)
            row = {
                "Symbol": r.get("nse"),
                "Chg %": r.get("change_pct"),
                "Score": r.get("score"),
                "Bias": r.get("bias"),
                "TV": _tv_url(r.get("nse")),
            }
            if "rsi" in allow:
                row["RSI"] = r.get("rsi")
            if "macd" in allow:
                row["MACD"] = r.get("macd_hist")
            if "sma" in allow:
                row["SMA"] = r.get("sma_stack")
            if "ema" in allow:
                row["EMA"] = r.get("ema_bias")
            if "bb" in allow:
                row["BB %B"] = r.get("bb_pctb")
            if "stoch" in allow:
                row["Stoch"] = r.get("stoch_k")
            if "cci" in allow:
                row["CCI"] = r.get("cci")
            if "willr" in allow:
                row["%R"] = r.get("willr")
            if "adx" in allow:
                row["ADX"] = r.get("adx")
            if "roc" in allow:
                row["ROC"] = r.get("roc")
            records.append(row)
        return pd.DataFrame(records)

    records = []
    for r in rows:
        records.append(
            {
                "Symbol": r.get("nse"),
                "Chg %": r.get("change_pct"),
                "RVOL": r.get("rvol"),
                "CMF": r.get("cmf"),
                "MFI": r.get("mfi"),
                "UV/DV": r.get("vol_ratio"),
                "Volume": r.get("volume"),
                "Score": r.get("score"),
                "OBV↑": r.get("obv_rising"),
                "Bias": r.get("bias"),
                "TV": _tv_url(r.get("nse")),
            }
        )
    return pd.DataFrame(records)


def _render_map(rows: list[dict], desk_id: str) -> None:
    cols = st.columns(3)
    for col, bias, label, mark in zip(
        cols,
        ["bullish", "neutral", "bearish"],
        ["Bullish bias", "Neutral", "Bearish bias"],
        ["↑", "·", "↓"],
    ):
        items = [r for r in rows if r.get("bias") == bias]
        with col:
            st.markdown(
                f'<div class="trend-col {bias}"><div class="trend-head">{mark} {label} · {len(items)}</div></div>',
                unsafe_allow_html=True,
            )
            if not items:
                st.caption(f"No {label.lower()} names.")
            else:
                for r in items[:40]:
                    sym = r.get("nse") or r.get("id") or "—"
                    score = r.get("score")
                    chg = r.get("change_pct")
                    extra = ""
                    if desk_id == "sci" and r.get("rank") is not None:
                        extra = f" · #{r.get('rank')}"
                    elif desk_id == "volume" and r.get("rvol") is not None:
                        extra = f" · {r.get('rvol'):.2f}×"
                    elif desk_id == "tech" and r.get("rsi") is not None:
                        extra = f" · RSI {r.get('rsi'):.0f}"
                    chg_s = f"{chg:+.2f}%" if chg is not None else "—"
                    score_s = f"{score:+.0f}" if score is not None else "—"
                    tv = _tv_url(sym, r.get("exchange"))
                    st.markdown(f"[{sym}]({tv}) · `{score_s}` · {chg_s}{extra}")
                if len(items) > 40:
                    st.caption(f"+{len(items) - 40} more — use table tabs")


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Signal Desk")
        st.caption("Volume · Technical · Lab · Spurts")

        desk_id = st.radio(
            "Workspace",
            options=list(DESKS.keys()),
            format_func=lambda k: DESKS[k],
            key="desk",
            label_visibility="collapsed",
        )

        if desk_id != "spurts":
            st.selectbox(
                "Universe",
                options=[u["id"] for u in desk.UNIVERSES],
                format_func=lambda i: UNIVERSE_LABELS.get(i, i),
                key="universe",
            )
            st.selectbox(
                "Timeframe",
                options=TF_ORDER,
                format_func=lambda i: TF_LABELS.get(i, i),
                key="tf",
            )
        else:
            st.session_state.spurt_auto = st.toggle("Auto-refresh (~25s)", value=st.session_state.spurt_auto)

        if desk_id == "tech":
            labels = {k: v for k, v in TECH_OPTS}
            picked = st.multiselect(
                "Signal set",
                options=[k for k, _ in TECH_OPTS],
                default=st.session_state.tech_indicators,
                format_func=lambda k: labels.get(k, k),
            )
            st.session_state.tech_indicators = picked or [k for k, _ in TECH_OPTS]

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Refresh", use_container_width=True):
                st.session_state.fresh_nonce += 1
                st.cache_data.clear()
                st.rerun()
        with c2:
            if st.button("Scan mode", use_container_width=True):
                st.session_state.mode = "scan"
                st.session_state.symbol = ""
                st.rerun()

        sources = _load_sources(False)
        session = sources.get("session") or desk.session_status()
        state = session.get("state", "")
        cls = "session-open" if state == "open" else "session-closed"
        st.markdown(
            f'<p class="{cls}">{session.get("label", "Session")} · {session.get("clock", "")}</p>',
            unsafe_allow_html=True,
        )
        st.caption(session.get("detail", ""))

        with st.expander("Feeds", expanded=False):
            for src in sources.get("sources") or []:
                mark = "●" if src.get("ok") else "○"
                st.write(f"{mark} **{src.get('name', 'Feed')}** — {src.get('detail') or src.get('note') or ('ok' if src.get('ok') else 'down')}")

        with st.expander("Model rules", expanded=False):
            for label, tip in LEGENDS.get(desk_id, []):
                st.markdown(f"**{label}** — {tip}")


def _fetch_board() -> dict:
    desk_id = st.session_state.desk
    nonce = st.session_state.fresh_nonce
    if desk_id == "spurts":
        return _load_spurts(nonce)
    if desk_id == "tech":
        return _load_tech_board(
            st.session_state.tf,
            st.session_state.universe,
            tuple(st.session_state.tech_indicators),
            nonce,
        )
    if desk_id == "sci":
        return _load_sci_board(st.session_state.tf, st.session_state.universe, nonce)
    return _load_volume_board(st.session_state.tf, st.session_state.universe, nonce)


def _render_symbol_view() -> None:
    symbol = st.session_state.symbol
    if not symbol:
        st.info("Search a symbol above to open the single-name volume view.")
        return
    with st.spinner(f"Loading {symbol}…"):
        data = _load_symbol(symbol, st.session_state.sc_id, st.session_state.tf, st.session_state.fresh_nonce)
    stats = data.get("stats") or {}
    st.subheader(f"{symbol} · {data.get('timeframe_label') or st.session_state.tf}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Score", stats.get("score", "—"))
    m2.metric("Bias", stats.get("bias", "—"))
    chg = stats.get("change_pct")
    m3.metric("Chg %", f"{chg:+.2f}%" if chg is not None else "—")
    m4.metric("RVOL", f"{stats.get('rvol'):.2f}×" if stats.get("rvol") is not None else "—")
    bars = data.get("bars") or []
    if bars:
        df = pd.DataFrame(
            [
                {
                    "Bar": b.get("label") or b.get("date"),
                    "Close": b.get("close"),
                    "Chg %": b.get("change_pct"),
                    "Volume": b.get("volume"),
                    "RVOL": b.get("rvol"),
                    "CMF": b.get("cmf"),
                    "MFI": b.get("mfi"),
                    "Score": b.get("score"),
                    "Bias": b.get("bias"),
                }
                for b in reversed(bars[-80:])
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
    tv = _tv_url(symbol)
    if tv:
        st.markdown(f"[Open on TradingView]({tv})")


def _render_scan() -> None:
    desk_id = st.session_state.desk
    tabs = _active_tabs(desk_id)
    tab_ids = [t[0] for t in tabs]
    if st.session_state.tab not in tab_ids:
        st.session_state.tab = tab_ids[0]

    with st.spinner("Running model…" if desk_id != "spurts" else "Fetching live NSE/BSE spurts…"):
        board = _fetch_board()

    counts = board.get("counts") or {}
    if desk_id == "spurts":
        status = (
            f"Spurts live · NSE {counts.get('nse', 0)} · BSE {counts.get('bse', 0)} · "
            f"{board.get('scanned', 0)} names · {board.get('as_of', '')}"
            + (" · cached" if board.get("cached") else " · fresh")
        )
        feeds = board.get("feeds") or []
        feed_bits = " · ".join(
            f"{f.get('name')} {f.get('count', 0)}"
            + (f" @ {f.get('as_of')}" if f.get("as_of") else "")
            for f in feeds
            if f.get("ok")
        )
        if feed_bits:
            status += f" · {feed_bits}"
        if board.get("errors"):
            status += " · " + board["errors"][0]
        links = board.get("links") or {}
        st.markdown(
            f'[NSE gainers]({links.get("nse", "#")}) · '
            f'[BSE spurts]({links.get("bse", "#")}) · live exchange feeds only'
        )
    else:
        status = (
            f"{DESKS[desk_id]} ready · {board.get('universe_label') or UNIVERSE_LABELS.get(st.session_state.universe)} · "
            f"{board.get('scanned', 0)}"
            + (f"/{board.get('universe_size')}" if board.get("universe_size") else "")
            + f" · {board.get('timeframe_label') or TF_LABELS.get(st.session_state.tf)} · "
            f"{counts.get('bullish', 0)} bull / {counts.get('bearish', 0)} bear"
            + (" · cached" if board.get("cached") else "")
        )

    st.markdown(f'<span class="status-chip">{status}</span>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scanned", board.get("scanned", 0))
    c2.metric("Bullish", counts.get("bullish", 0))
    c3.metric("Bearish", counts.get("bearish", 0))
    if desk_id == "spurts":
        c4.metric("≥3×", counts.get("spike", 0))
    else:
        c4.metric("Neutral", counts.get("neutral", 0))

    labels = [t[1] for t in tabs]
    chosen = st.radio(
        "View",
        options=labels,
        horizontal=True,
        label_visibility="collapsed",
        key=f"tab_radio_{desk_id}",
    )
    st.session_state.tab = tabs[labels.index(chosen)][0]
    tab = st.session_state.tab
    rows = board.get("rows") or []

    if tab == "trend" and desk_id != "spurts":
        _render_map(rows, desk_id)
    else:
        filtered = _filter_rows(rows, desk_id, "trend" if desk_id == "spurts" and tab == "trend" else tab)
        if desk_id == "spurts" and tab == "trend":
            filtered = rows
        df = _board_dataframe(filtered, desk_id, st.session_state.tech_indicators)
        if df.empty:
            st.info("No rows for this filter.")
        else:
            # Prefer Vol× / Score / Rank sort defaults
            sort_col = None
            for candidate in ("Vol×", "Rank", "Score", "RVOL"):
                if candidate in df.columns:
                    sort_col = candidate
                    break
            if sort_col:
                ascending = sort_col == "Rank"
                df = df.sort_values(sort_col, ascending=ascending, na_position="last")
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "TV": st.column_config.LinkColumn("TV", display_text="↗"),
                    "Volume": st.column_config.NumberColumn(format="%d"),
                    "Avg": st.column_config.NumberColumn(format="%d"),
                    "Chg %": st.column_config.NumberColumn(format="%.2f"),
                    "Vol×": st.column_config.NumberColumn(format="%.2f"),
                    "RVOL": st.column_config.NumberColumn(format="%.2f"),
                    "CMF": st.column_config.NumberColumn(format="%.3f"),
                    "MFI": st.column_config.NumberColumn(format="%.1f"),
                    "Score": st.column_config.NumberColumn(format="%.0f"),
                },
                height=min(620, 48 + 28 * min(len(df), 22)),
            )

    foot = {
        "tech": "Technical stack · RSI · MACD · SMA · EMA · BB · Stoch · CCI · %R · ADX · ROC · research only.",
        "sci": "Lab · RVOL · OBV · CMF · MFI · Force · VOsc · EOM · VWAP · PVT · research only.",
        "spurts": "Live spurts · NSE volume gainers + BSE spurt-in-volume · Vol× vs avg · research only.",
        "volume": "Volume stack · RVOL · OBV · UV/DV · CMF · MFI · A/D · VPT · research only.",
    }[desk_id]
    st.markdown(f'<p class="foot-note">{foot}</p>', unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(
        page_title="Signal Desk",
        page_icon="▣",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _init_state()
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    _render_sidebar()

    desk_id = st.session_state.desk
    titles = {
        "volume": ("Volume signals", "Universe scan with volume bias"),
        "tech": ("Technical models", "OHLC indicator vote stack"),
        "sci": ("Lab studies", "Cited volume / flow studies"),
        "spurts": ("Volume spurts", "Live NSE + BSE exchange lists"),
    }
    title, sub = titles[desk_id]
    st.markdown(f'<div class="desk-kicker">Signal Desk</div><h1 class="desk-title">{title}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="desk-sub">{sub}</p>', unsafe_allow_html=True)

    q_col, go_col = st.columns([4, 1])
    with q_col:
        query = st.text_input(
            "Search symbol",
            value=st.session_state.symbol_query,
            placeholder="RELIANCE, TCS…",
            label_visibility="collapsed",
            key="search_box",
        )
    with go_col:
        run = st.button("Run", use_container_width=True, type="primary")

    if run and query.strip():
        st.session_state.symbol_query = query.strip().upper()
        hits = _search(st.session_state.symbol_query)
        hit = hits[0] if hits else None
        st.session_state.mode = "symbol"
        st.session_state.symbol = (hit or {}).get("nse") or st.session_state.symbol_query
        st.session_state.sc_id = (hit or {}).get("sc_id") or ""
        st.rerun()

    if query.strip() and len(query.strip()) >= 2 and not run:
        hits = _search(query.strip().upper())
        if hits:
            st.caption("Suggestions — pick one, then Run:")
            labels = [h.get("label") or h.get("nse") or "?" for h in hits[:8]]
            pick = st.selectbox("Matches", options=list(range(len(labels))), format_func=lambda i: labels[i], label_visibility="collapsed")
            if st.button("Open match"):
                hit = hits[pick]
                st.session_state.mode = "symbol"
                st.session_state.symbol = hit.get("nse") or query.strip().upper()
                st.session_state.sc_id = hit.get("sc_id") or ""
                st.session_state.symbol_query = st.session_state.symbol
                st.rerun()

    if st.session_state.mode == "symbol" and desk_id == "volume":
        _render_symbol_view()
        return

    # Spurts: fragment re-runs every 25s (cache TTL 20s → fresh exchange pull)
    if desk_id == "spurts" and st.session_state.spurt_auto and hasattr(st, "fragment"):

        @st.fragment(run_every=timedelta(seconds=25))
        def _spurts_live() -> None:
            _render_scan()

        _spurts_live()
        return

    _render_scan()


if __name__ == "__main__":
    main()
