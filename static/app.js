const VOLUME_TABS = [
  ["trend", "Map", "all"],
  ["bullish", "Bullish", "bullish"],
  ["bearish", "Bearish", "bearish"],
  ["spike", "Spike", "spike"],
];

const TECH_TABS = [
  ["trend", "Map", "all"],
  ["bullish", "Bullish", "bullish"],
  ["bearish", "Bearish", "bearish"],
];

const SCI_TABS = [
  ["trend", "Map", "all"],
  ["bullish", "Bullish", "bullish"],
  ["bearish", "Bearish", "bearish"],
  ["spike", "Spike", "spike"],
];

const VOLUME_LEGEND = [
  ["Bull ≥+30", "Bias score ≥ +30 — price up with volume confirmation"],
  ["Bear ≤−30", "Bias score ≤ −30 — price down with volume confirmation"],
  ["RVOL", "Relative volume: bar volume ÷ average of prior N bars (≥1.5× = spike)"],
  ["OBV", "On-Balance Volume — rising = accumulation, falling = distribution"],
  ["UV/DV", "Up-bar volume ÷ down-bar volume over the lookback window"],
  ["CMF", "Chaikin Money Flow — close location in the range × volume (buying pressure)"],
  ["MFI", "Money Flow Index (0–100) — volume-weighted momentum; ≥55 buy / ≤45 sell lean"],
  ["A/D", "Accumulation/Distribution — running money-flow volume from high/low/close"],
  ["VPT", "Volume Price Trend — cumulative volume × % price change"],
];

const TECH_LEGEND = [
  ["Bull ≥+30", "Technical score ≥ +30 from the 10 indicator votes"],
  ["Bear ≤−30", "Technical score ≤ −30 from the 10 indicator votes"],
  ["RSI(14)", "Relative Strength — ≥55 bullish · ≤45 bearish · ≥60 / ≤40 strong"],
  ["MACD", "MACD(12,26,9) — hist > 0 and line > signal = bullish"],
  ["SMA 20/50", "SMA20 above SMA50 = uptrend stack"],
  ["EMA(20)", "Close above EMA20 = short-term bullish"],
  ["BB %B", "Bollinger %B(20,2) — >0.5 upper half · ≥0.8 strong"],
  ["Stoch %K", "Stochastic(14) — ≥50 bullish · ≤20 / ≥80 extremes"],
  ["CCI(20)", "Commodity Channel — >0 lean up · ≥100 / ≤−100 strong"],
  ["Will%R", "Williams %R(14) — >−50 bullish · ≤−80 oversold lean"],
  ["ADX+DI", "ADX(14) trend strength · +DI vs −DI for direction"],
  ["ROC(12)", "Rate of change — >0 momentum up · ≥3% / ≤−3% strong"],
];

const SCI_LEGEND = [
  ["Rank", "Rank 1 = highest lab score in the scanned universe"],
  ["Bull ≥+30", "Lab score ≥ +30 from cited volume/flow study votes"],
  ["Bear ≤−30", "Lab score ≤ −30 from cited volume/flow study votes"],
  ["RVOL", "RVOL(20) = volume ÷ SMA(volume,20) — StockCharts / market practice"],
  ["OBV", "On-Balance Volume — Joseph Granville (1963); vote from Δ over lookback"],
  ["CMF", "Chaikin Money Flow(20) — Marc Chaikin / StockCharts"],
  ["MFI", "Money Flow Index(14) — Quong & Soudack / StockCharts"],
  ["Force", "Force Index EMA(13) — Alexander Elder"],
  ["VOsc", "Volume Oscillator(5,20) — StockCharts"],
  ["EOM", "Ease of Movement EMA(14) — Richard W. Arms Jr. / StockCharts"],
  ["VWAP", "Lookback VWAP bias = (close − VWAP)/VWAP — standard VWAP"],
  ["PVT", "Volume Price Trend — StockCharts; vote from Δ over lookback"],
];

const SCI_COLUMNS = [
  { key: "rank", label: "Rank", type: "num" },
  { key: "nse", label: "Symbol", type: "text" },
  { key: "change_pct", label: "Chg %", type: "num" },
  { key: "rvol", label: "RVOL", type: "num" },
  { key: "cmf", label: "CMF", type: "num" },
  { key: "mfi", label: "MFI", type: "num" },
  { key: "force", label: "Force", type: "num" },
  { key: "voscil", label: "VOsc", type: "num" },
  { key: "eom", label: "EOM", type: "num" },
  { key: "vwap_bias", label: "VWAP%", type: "num" },
  { key: "score", label: "Score", type: "num" },
  { key: "percentile", label: "%ile", type: "num" },
];

const TIMEFRAMES = ["15m", "1h", "4h", "1d", "1w", "1m", "3m", "6m", "1y", "5y", "max"];
const UNIVERSES = ["nifty50", "nifty500", "midcap", "smallcap", "nse_all", "bse_all"];
const DESKS = ["volume", "tech", "sci", "spurts"];

const SPURT_TABS = [
  ["trend", "All", "all"],
  ["nse", "NSE", "nse"],
  ["bse", "BSE", "bse"],
  ["spike", "≥3×", "spike"],
];

const SPURT_LEGEND = [
  ["Rank", "Rank 1 = highest Vol× in the current tab"],
  ["NSE", "Live Volume Gainers — nseindia.com/market-data/volume-gainers-spurts (~25 names)"],
  ["BSE", "Live Spurt in Volume — Equity T+1 + T+0 when BSE publishes"],
  ["Vol×", "Today volume ÷ reference average (NSE 1-week avg / BSE 2-week avg)"],
  ["Score", "Log-scaled Vol× with soft price confirmation (−100…+100)"],
  ["Refresh", "Auto-polls exchange APIs every ~25s while Spurts is open"],
];

const SPURT_COLUMNS = [
  { key: "rank", label: "Rank", type: "num" },
  { key: "exchange", label: "Exch", type: "text" },
  { key: "nse", label: "Symbol", type: "text" },
  { key: "change_pct", label: "Chg %", type: "num" },
  { key: "vol_x", label: "Vol×", type: "num" },
  { key: "volume", label: "Volume", type: "num" },
  { key: "avg_volume", label: "Avg", type: "num" },
  { key: "ltp", label: "LTP", type: "num" },
  { key: "turnover", label: "Turnover", type: "num" },
  { key: "score", label: "Score", type: "num" },
];

const UNIVERSE_LABELS = {
  nifty50: "Nifty 50",
  nifty500: "Nifty 500",
  midcap: "Nifty Midcap 150",
  smallcap: "Nifty Smallcap 250",
  nse_all: "NSE All",
  bse_all: "BSE All",
  all: "NSE All",
};

const UNIVERSE_SHORT = {
  nifty50: "N50",
  nifty500: "N500",
  midcap: "MID",
  smallcap: "SML",
  nse_all: "NSE",
  bse_all: "BSE",
  all: "NSE",
};

const VOLUME_COLUMNS = [
  { key: "nse", label: "Symbol", type: "text" },
  { key: "change_pct", label: "Chg %", type: "num" },
  { key: "rvol", label: "RVOL", type: "num" },
  { key: "cmf", label: "CMF", type: "num" },
  { key: "mfi", label: "MFI", type: "num" },
  { key: "vol_ratio", label: "UV/DV", type: "num" },
  { key: "volume", label: "Volume", type: "num" },
  { key: "score", label: "Score", type: "num" },
  { key: "obv_rising", label: "OBV", type: "obv" },
];

const TECH_INDICATOR_OPTIONS = [
  { id: "rsi", label: "RSI", col: "rsi" },
  { id: "macd", label: "MACD", col: "macd_hist" },
  { id: "sma", label: "SMA 20/50", col: "sma_stack" },
  { id: "ema", label: "EMA 20", col: "ema_bias" },
  { id: "bb", label: "BB %B", col: "bb_pctb" },
  { id: "stoch", label: "Stochastic", col: "stoch_k" },
  { id: "cci", label: "CCI", col: "cci" },
  { id: "willr", label: "Williams %R", col: "willr" },
  { id: "adx", label: "ADX + DI", col: "adx" },
  { id: "roc", label: "ROC", col: "roc" },
];

const TECH_COLUMNS = [
  { key: "nse", label: "Symbol", type: "text" },
  { key: "change_pct", label: "Chg %", type: "num" },
  { key: "rsi", label: "RSI", type: "num", indicator: "rsi" },
  { key: "macd_hist", label: "MACD", type: "num", indicator: "macd" },
  { key: "sma_stack", label: "SMA", type: "num", indicator: "sma" },
  { key: "ema_bias", label: "EMA", type: "num", indicator: "ema" },
  { key: "bb_pctb", label: "BB %B", type: "num", indicator: "bb" },
  { key: "stoch_k", label: "Stoch", type: "num", indicator: "stoch" },
  { key: "cci", label: "CCI", type: "num", indicator: "cci" },
  { key: "willr", label: "%R", type: "num", indicator: "willr" },
  { key: "adx", label: "ADX", type: "num", indicator: "adx" },
  { key: "roc", label: "ROC", type: "num", indicator: "roc" },
  { key: "score", label: "Score", type: "num" },
];

const state = {
  desk: "volume", // volume | tech
  mode: "scan", // scan | symbol
  kind: "stock",
  symbol: "RELIANCE",
  scId: "RI",
  tf: "1d",
  universe: "nifty50",
  tab: "trend",
  sortKey: "score",
  sortDir: "desc",
  techIndicators: TECH_INDICATOR_OPTIONS.map((item) => item.id),
  sources: null,
  data: null,
  board: null,
};

function activeTabs() {
  if (state.desk === "tech") return TECH_TABS;
  if (state.desk === "sci") return SCI_TABS;
  if (state.desk === "spurts") return SPURT_TABS;
  return VOLUME_TABS;
}

function activeLegend() {
  if (state.desk === "spurts") return SPURT_LEGEND;
  if (state.desk === "sci") return SCI_LEGEND;
  if (state.desk !== "tech") return VOLUME_LEGEND;
  const allow = selectedIndicatorSet();
  const map = {
    "RSI(14)": "rsi",
    MACD: "macd",
    "SMA 20/50": "sma",
    "EMA(20)": "ema",
    "BB %B": "bb",
    "Stoch %K": "stoch",
    "CCI(20)": "cci",
    "Will%R": "willr",
    "ADX+DI": "adx",
    "ROC(12)": "roc",
  };
  return TECH_LEGEND.filter(([label]) => {
    if (label.startsWith("Bull") || label.startsWith("Bear")) return true;
    const id = map[label];
    return !id || allow.has(id);
  });
}

function activeColumns() {
  if (state.desk === "spurts") return SPURT_COLUMNS;
  if (state.desk === "sci") return SCI_COLUMNS;
  if (state.desk !== "tech") return VOLUME_COLUMNS;
  const allow = new Set(state.techIndicators);
  return TECH_COLUMNS.filter((col) => !col.indicator || allow.has(col.indicator));
}

function deskLabel() {
  if (state.desk === "tech") return "Technical";
  if (state.desk === "sci") return "Lab";
  if (state.desk === "spurts") return "Spurts";
  return "Volume";
}

function selectedIndicatorSet() {
  return new Set(state.techIndicators);
}

let inflight = null;
let searchTimer = null;
let spurtTimer = null;
const SPURT_POLL_MS = 25000;

function syncSpurtRefresh() {
  if (spurtTimer) {
    clearInterval(spurtTimer);
    spurtTimer = null;
  }
  if (state.desk !== "spurts" || state.mode !== "scan") return;
  spurtTimer = setInterval(() => {
    if (document.hidden) return;
    if (state.desk !== "spurts" || state.mode !== "scan") return;
    loadBoard(true);
  }, SPURT_POLL_MS);
}

const els = {
  q: document.getElementById("q"),
  form: document.getElementById("search-form"),
  suggestions: document.getElementById("suggestions"),
  status: document.getElementById("status"),
  sourcePanel: document.getElementById("source-panel"),
  formulaPanel: document.getElementById("formula-panel"),
  universe: document.getElementById("universe"),
  techFilter: document.getElementById("tech-ind-filter"),
  techIndList: document.getElementById("tech-ind-list"),
  techIndSummary: document.getElementById("tech-ind-summary"),
  techIndAll: document.getElementById("tech-ind-all"),
  techIndNone: document.getElementById("tech-ind-none"),
  techIndApply: document.getElementById("tech-ind-apply"),
  meter: null,
  tabs: document.getElementById("tabs"),
  panel: document.getElementById("panel"),
  foot: document.getElementById("foot-text") || document.querySelector(".foot p"),
  deskTitle: document.getElementById("desk-title"),
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function universeLabel(id) {
  return UNIVERSE_LABELS[id] || id;
}

function syncTechFilterSummary() {
  const count = document.getElementById("tech-ind-count");
  if (!count) return;
  const n = state.techIndicators.length;
  const total = TECH_INDICATOR_OPTIONS.length;
  count.textContent = n >= total ? "Σ" : n + "/" + total;
  if (els.techIndSummary) {
    els.techIndSummary.title =
      n >= total ? "Signal set · all" : "Signal set · " + n + "/" + total;
  }
}

function renderTechIndicatorFilter() {
  if (!els.techIndList) return;
  const selected = selectedIndicatorSet();
  els.techIndList.replaceChildren();
  TECH_INDICATOR_OPTIONS.forEach((item) => {
    const label = el("label", "");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = item.id;
    input.checked = selected.has(item.id);
    label.append(input);
    label.append(document.createTextNode(item.label));
    els.techIndList.append(label);
  });
  syncTechFilterSummary();
}

function readTechFilterSelection() {
  if (!els.techIndList) return state.techIndicators.slice();
  const picked = [];
  els.techIndList.querySelectorAll('input[type="checkbox"]').forEach((input) => {
    if (input.checked) picked.push(input.value);
  });
  return picked.length ? picked : TECH_INDICATOR_OPTIONS.map((item) => item.id);
}

function applyDeskChrome() {
  document.querySelectorAll("[data-desk]").forEach((node) => {
    node.classList.toggle("is-on", node.dataset.desk === state.desk);
  });
  const titleText = document.getElementById("desk-title-text");
  const label =
    state.desk === "tech"
      ? "Technical models"
      : state.desk === "sci"
        ? "Lab studies"
        : state.desk === "spurts"
          ? "Volume spurts"
          : "Volume signals";
  if (titleText) titleText.textContent = label;
  if (els.deskTitle) els.deskTitle.title = label;
  document.querySelectorAll("[data-desk-ico]").forEach((node) => {
    node.hidden = node.dataset.deskIco !== state.desk;
  });
  document.title =
    state.desk === "tech"
      ? "Signal Desk — technical models"
      : state.desk === "sci"
        ? "Signal Desk — lab studies"
        : state.desk === "spurts"
          ? "Signal Desk — volume spurts"
          : "Signal Desk — volume signals";
  if (els.techFilter) {
    els.techFilter.hidden = state.desk !== "tech";
    if (state.desk !== "tech") els.techFilter.open = false;
  }
  const tfRow = document.getElementById("tf-row");
  if (tfRow) tfRow.hidden = state.desk === "spurts";
  if (els.universe) {
    const wrap = els.universe.closest(".universe-label");
    if (wrap) wrap.hidden = state.desk === "spurts";
  }
  document.body.dataset.desk = state.desk;
  updateFoot();
  renderLegendChrome();
  renderTechIndicatorFilter();
}

function restore() {
  try {
    const saved = JSON.parse(sessionStorage.getItem("volume-desk") || "{}");
    if (DESKS.includes(saved.desk)) state.desk = saved.desk;
    if (saved.mode === "scan" || saved.mode === "symbol") state.mode = saved.mode;
    if (saved.kind === "stock" || saved.kind === "index") state.kind = saved.kind;
    if (typeof saved.symbol === "string") state.symbol = saved.symbol;
    if (typeof saved.scId === "string") state.scId = saved.scId;
    if (TIMEFRAMES.includes(saved.tf)) state.tf = saved.tf;
    if (UNIVERSES.includes(saved.universe)) state.universe = saved.universe;
    if (activeTabs().some(([id]) => id === saved.tab)) state.tab = saved.tab;
    else if (saved.tab === "all" || saved.tab === "chart" || saved.tab === "spike") {
      state.tab = saved.mode === "symbol" ? "chart" : "trend";
    }
    if (activeColumns().some((col) => col.key === saved.sortKey)) state.sortKey = saved.sortKey;
    else state.sortKey = "score";
    if (saved.sortDir === "asc" || saved.sortDir === "desc") state.sortDir = saved.sortDir;
    if (Array.isArray(saved.techIndicators)) {
      const allow = new Set(TECH_INDICATOR_OPTIONS.map((item) => item.id));
      const picked = saved.techIndicators.filter((id) => allow.has(id));
      if (picked.length) state.techIndicators = picked;
    }
  } catch (_err) {
    /* defaults */
  }
  if (
    state.tab === "all" ||
    (state.desk === "tech" && state.tab === "spike") ||
    (state.desk === "spurts" && !["trend", "nse", "bse", "spike"].includes(state.tab))
  ) {
    state.tab = state.mode === "symbol" ? "chart" : "trend";
  }
  document.querySelectorAll("[data-tf]").forEach((button) => {
    button.classList.toggle("is-on", button.dataset.tf === state.tf);
  });
  if (els.universe) els.universe.value = state.universe;
  applyDeskChrome();
}

function persist() {
  sessionStorage.setItem(
    "volume-desk",
    JSON.stringify({
      desk: state.desk,
      mode: state.mode,
      kind: state.kind,
      symbol: state.symbol,
      scId: state.scId,
      tf: state.tf,
      universe: state.universe,
      tab: state.tab,
      sortKey: state.sortKey,
      sortDir: state.sortDir,
      techIndicators: state.techIndicators,
    })
  );
}

function fmtVol(value) {
  const n = Number(value) || 0;
  if (n >= 1e7) return (n / 1e7).toFixed(2) + " Cr";
  if (n >= 1e5) return (n / 1e5).toFixed(2) + " L";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(Math.round(n));
}

function fmtNum(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("en-IN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function fmtCompact(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  if (abs >= 1e7) return sign + (abs / 1e7).toFixed(2) + " Cr";
  if (abs >= 1e5) return sign + (abs / 1e5).toFixed(2) + " L";
  if (abs >= 1e3) return sign + (abs / 1e3).toFixed(1) + "k";
  return String(Math.round(n));
}

function counts() {
  if (state.mode === "scan") return state.board ? state.board.counts : null;
  return state.data ? state.data.counts : null;
}

function formulas() {
  if (state.mode === "scan") return (state.board && state.board.formulas) || null;
  return (state.data && state.data.formulas) || null;
}

function filteredBars() {
  const bars = state.data ? state.data.bars : [];
  if (state.tab === "bullish") return bars.filter((bar) => bar.bias === "bullish");
  if (state.tab === "bearish") return bars.filter((bar) => bar.bias === "bearish");
  if (state.tab === "spike") return bars.filter((bar) => bar.spike);
  return bars;
}

function filteredRows() {
  const rows = state.board ? state.board.rows : [];
  if (state.desk === "spurts") {
    if (state.tab === "nse") return rows.filter((row) => row.exchange === "NSE");
    if (state.tab === "bse") return rows.filter((row) => row.exchange === "BSE");
    if (state.tab === "spike") return rows.filter((row) => (row.vol_x || 0) >= 3);
    return rows;
  }
  if (state.tab === "bullish") return rows.filter((row) => row.bias === "bullish");
  if (state.tab === "bearish") return rows.filter((row) => row.bias === "bearish");
  if (state.tab === "spike") return rows.filter((row) => row.spike);
  return rows;
}

function tradingViewUrl(symbol, exchange) {
  const raw = String(symbol || "")
    .trim()
    .toUpperCase();
  if (!raw) return "";
  const ex = String(exchange || "NSE").toUpperCase() === "BSE" ? "BSE" : "NSE";
  return "https://www.tradingview.com/chart/?symbol=" + encodeURIComponent(ex + ":" + raw);
}

function stockTvLink(symbol, exchange, label) {
  const text = label || symbol || "";
  const url = tradingViewUrl(symbol, exchange);
  if (!url) return el("span", "", text);
  const a = el("a", "stock-link", text);
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  a.title = "Open " + symbol + " on TradingView";
  a.addEventListener("click", (event) => event.stopPropagation());
  return a;
}

function setFoldTitle(foldId, title) {
  const fold = document.getElementById(foldId);
  const summary = fold ? fold.querySelector("summary") : null;
  if (summary) summary.title = title;
}

function renderLegendChrome() {
  if (!els.formulaPanel) return;
  els.formulaPanel.replaceChildren();
  const legend = activeLegend();
  setFoldTitle("legend-fold", "Model rules · " + legend.length);
  legend.forEach(([label, tip]) => {
    const chip = el("span", "", label);
    chip.title = tip;
    els.formulaPanel.append(chip);
  });
}

function renderSources() {
  if (!els.sourcePanel) return;
  const sources = state.sources ? state.sources.sources : [];
  els.sourcePanel.replaceChildren();
  if (!sources.length) {
    setFoldTitle("source-fold", "Feeds");
    return;
  }
  const okCount = sources.filter((source) => source.ok).length;
  setFoldTitle("source-fold", "Feeds · " + okCount + "/" + sources.length + " live");
  sources.forEach((source) => {
    const card = el("div", "source-card " + (source.ok ? "ok" : ""));
    card.title = source.detail || "";
    card.append(el("strong", "", source.name));
    card.append(el("span", "src-detail", source.ok ? "ok" : "down"));
    els.sourcePanel.append(card);
  });
}

function renderSession(_session) {
  /* clock / session pill removed from chrome */
}

function renderMeter() {
  if (!els.meter) return;
  els.meter.hidden = true;
  els.meter.replaceChildren();
}

function renderTabs() {
  const c = counts();
  els.tabs.replaceChildren();
  const row = el("div", "tab-row");
  activeTabs().forEach(([id, label, countKey]) => {
    const button = el("button", "tab");
    button.type = "button";
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", id === state.tab ? "true" : "false");
    button.append(document.createTextNode(label));
    if (c && countKey) button.append(el("span", "count", String(c[countKey] ?? 0)));
    button.addEventListener("click", () => {
      state.tab = id;
      persist();
      renderTabs();
      renderPanel();
    });
    row.append(button);
  });
  els.tabs.append(row);
}

function studyTags(study) {
  const wrap = el("div", "study");
  if (!study) return wrap;
  const items = [];
  if (study.bias) items.push([study.bias, study.bias]);
  if (study.score != null) items.push(["", "score " + study.score]);
  if (study.rvol != null) items.push([study.tone === "spike" ? "spike" : "", study.rvol.toFixed(2) + "× RVOL"]);
  if (study.vol_ratio != null) items.push(["", "UV/DV " + study.vol_ratio.toFixed(2)]);
  if (study.obv_rising === true) items.push(["bullish", "OBV↑"]);
  if (study.obv_rising === false) items.push(["bearish", "OBV↓"]);
  if (study.cmf != null) items.push([study.cmf >= 0 ? "bullish" : "bearish", "CMF " + study.cmf.toFixed(3)]);
  if (study.mfi != null) {
    items.push([
      study.mfi >= 55 ? "bullish" : study.mfi <= 45 ? "bearish" : "",
      "MFI " + study.mfi.toFixed(1),
    ]);
  }
  if (study.ad != null) items.push(["", "A/D " + fmtCompact(study.ad)]);
  if (study.vpt != null) items.push(["", "VPT " + fmtCompact(study.vpt)]);
  if (study.move) items.push([study.move.startsWith("-") ? "down" : "up", study.move]);
  if (study.volume != null) items.push(["", fmtVol(study.volume)]);
  items.forEach(([tone, text]) => wrap.append(el("span", "tag " + tone, text)));
  return wrap;
}

function svgEl(name, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, String(value)));
  return node;
}

function drawPriceVolume(target, bars) {
  target.replaceChildren();
  if (!bars.length) return;
  const width = 920;
  const height = 280;
  const pad = { top: 18, right: 18, bottom: 36, left: 54 };
  const mid = pad.top + (height - pad.top - pad.bottom) * 0.58;
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}` });
  const closes = bars.map((bar) => bar.close);
  const volumes = bars.map((bar) => bar.volume);
  const minC = Math.min(...closes);
  const maxC = Math.max(...closes);
  const maxV = Math.max(...volumes, 1);
  const innerW = width - pad.left - pad.right;
  const priceH = mid - pad.top;
  const volH = height - pad.bottom - mid - 8;
  const step = innerW / Math.max(bars.length, 1);
  const yPrice = (value) => pad.top + ((maxC - value) / (maxC - minC || 1)) * priceH;
  const yVol = (value) => mid + 8 + (1 - value / maxV) * volH;

  bars.forEach((bar, i) => {
    const x = pad.left + i * step + step * 0.18;
    const w = Math.max(1.5, step * 0.64);
    const y = yVol(bar.volume);
    const fill =
      bar.bias === "bullish"
        ? "rgba(12,122,86,0.45)"
        : bar.bias === "bearish"
          ? "rgba(156,51,44,0.45)"
          : "rgba(26,29,35,0.18)";
    svg.append(svgEl("rect", { x, y, width: w, height: Math.max(1, height - pad.bottom - y), fill, rx: 1 }));
  });

  let d = "";
  bars.forEach((bar, i) => {
    d += (i ? " L " : "M ") + (pad.left + i * step + step / 2) + " " + yPrice(bar.close);
  });
  svg.append(svgEl("path", { d, fill: "none", stroke: "#1a1d23", "stroke-width": 1.8, "stroke-linejoin": "round" }));
  target.append(svg);
}

function drawRvol(target, bars) {
  target.replaceChildren();
  const usable = bars.filter((bar) => bar.rvol != null);
  if (!usable.length) return;
  const width = 920;
  const height = 190;
  const pad = { top: 18, right: 18, bottom: 28, left: 54 };
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}` });
  const maxR = Math.max(2, ...usable.map((bar) => bar.rvol));
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const step = innerW / Math.max(usable.length, 1);
  const y = (value) => pad.top + (1 - value / maxR) * innerH;

  [1, 1.5].forEach((level) => {
    if (level > maxR) return;
    svg.append(
      svgEl("line", {
        x1: pad.left,
        x2: width - pad.right,
        y1: y(level),
        y2: y(level),
        stroke: level === 1.5 ? "rgba(138,88,16,0.45)" : "rgba(26,29,35,0.25)",
        "stroke-dasharray": level === 1.5 ? "4 4" : "0",
      })
    );
  });

  usable.forEach((bar, i) => {
    const x = pad.left + i * step + step * 0.2;
    const w = Math.max(1.5, step * 0.6);
    const yy = y(bar.rvol);
    svg.append(
      svgEl("rect", {
        x,
        y: yy,
        width: w,
        height: Math.max(1, y(0) - yy),
        fill:
          bar.bias === "bullish"
            ? "rgba(12,122,86,0.65)"
            : bar.bias === "bearish"
              ? "rgba(156,51,44,0.65)"
              : "rgba(26,29,35,0.28)",
        rx: 1,
      })
    );
  });
  target.append(svg);
}

function openSymbol(row) {
  state.mode = "symbol";
  state.kind = "stock";
  state.symbol = row.id || row.nse;
  state.scId = row.sc_id || "";
  state.tab = "chart";
  els.q.value = row.nse || state.symbol;
  persist();
  loadVolume();
}

function renderTrend(root, rows) {
  const squares = el("div", "trend-squares");
  [
    ["bullish", "Bullish bias", "↑"],
    ["neutral", "Neutral", "·"],
    ["bearish", "Bearish bias", "↓"],
  ].forEach(([bias, labelText, mark]) => {
    const box = el("section", "trend-square " + bias);
    const head = el("h2", "trend-square-head");
    head.append(el("span", "trend-mark", mark));
    head.append(document.createTextNode(labelText));
    const items = rows.filter((row) => row.bias === bias);
    head.append(el("span", "count", String(items.length)));
    box.append(head);
    const list = el("div", "trend-list");
    if (!items.length) {
      list.append(el("p", "empty", "No " + labelText.toLowerCase() + " names."));
    } else {
      items.forEach((row) => {
        const button = el("button", "trend-row");
        button.type = "button";
        const titleWrap = el("div", "trend-title");
        if (row.nse) {
          titleWrap.append(stockTvLink(row.nse, row.exchange));
          if (row.name) titleWrap.append(document.createTextNode(" · " + row.name));
        } else {
          titleWrap.append(
            document.createTextNode((row.label || row.date) + " · " + fmtVol(row.volume))
          );
        }
        button.append(titleWrap);
        const meta = el("div", "meta");
        const chips = el("div", "metric-chips");
        const chipDefs =
          state.desk === "tech"
            ? [
                ["score", row.score != null ? String(row.score) : null, row.bias || ""],
                selectedIndicatorSet().has("rsi")
                  ? ["rsi", row.rsi != null ? row.rsi.toFixed(0) : null, row.rsi == null ? "" : row.rsi >= 55 ? "up" : row.rsi <= 45 ? "down" : ""]
                  : null,
                selectedIndicatorSet().has("macd")
                  ? ["macd", row.macd_hist != null ? row.macd_hist.toFixed(2) : null, row.macd_hist == null ? "" : row.macd_hist >= 0 ? "up" : "down"]
                  : null,
                selectedIndicatorSet().has("stoch")
                  ? ["stoch", row.stoch_k != null ? row.stoch_k.toFixed(0) : null, row.stoch_k == null ? "" : row.stoch_k >= 50 ? "up" : "down"]
                  : null,
                selectedIndicatorSet().has("adx")
                  ? ["adx", row.adx != null ? row.adx.toFixed(0) : null, row.plus_di != null && row.minus_di != null ? (row.plus_di > row.minus_di ? "up" : row.plus_di < row.minus_di ? "down" : "") : ""]
                  : null,
              ].filter(Boolean)
            : state.desk === "sci"
              ? [
                  ["rank", row.rank != null ? "#" + row.rank : null, ""],
                  ["score", row.score != null ? String(row.score) : null, row.bias || ""],
                  ["cmf", row.cmf != null ? row.cmf.toFixed(2) : null, row.cmf == null ? "" : row.cmf >= 0 ? "up" : "down"],
                  ["force", row.force != null ? fmtCompact(row.force) : null, row.force == null ? "" : row.force >= 0 ? "up" : "down"],
                ]
              : [
                  ["score", row.score != null ? String(row.score) : null, row.bias || ""],
                  ["cmf", row.cmf != null ? row.cmf.toFixed(2) : null, row.cmf == null ? "" : row.cmf >= 0 ? "up" : "down"],
                  ["mfi", row.mfi != null ? row.mfi.toFixed(0) : null, row.mfi == null ? "" : row.mfi >= 55 ? "up" : row.mfi <= 45 ? "down" : ""],
                ];
        chipDefs.forEach(([key, value, tone]) => {
          if (value == null) return;
          const chip = el("span", "metric-chip " + tone);
          chip.append(el("em", "", key.toUpperCase()));
          chip.append(el("strong", "", value));
          chips.append(chip);
        });
        meta.append(chips);
        const rest =
          state.desk === "tech"
            ? [
                row.sma20 != null && row.sma50 != null ? (row.sma20 > row.sma50 ? "SMA↑" : "SMA↓") : null,
                row.bb_pctb != null ? "BB " + row.bb_pctb.toFixed(2) : null,
                row.roc != null ? "ROC " + row.roc.toFixed(1) : null,
                row.change_pct != null ? (row.change_pct >= 0 ? "+" : "") + fmtNum(row.change_pct) + "%" : null,
              ]
            : state.desk === "sci"
              ? [
                  row.rvol != null ? row.rvol.toFixed(2) + "×" : null,
                  row.vwap_bias != null ? "VWAP " + (row.vwap_bias >= 0 ? "+" : "") + row.vwap_bias.toFixed(1) + "%" : null,
                  row.percentile != null ? "p" + row.percentile : null,
                  row.change_pct != null ? (row.change_pct >= 0 ? "+" : "") + fmtNum(row.change_pct) + "%" : null,
                ]
              : [
                  row.rvol != null ? row.rvol.toFixed(2) + "×" : null,
                  row.change_pct != null ? (row.change_pct >= 0 ? "+" : "") + fmtNum(row.change_pct) + "%" : null,
                  row.strength || null,
                ];
        const restText = rest.filter(Boolean).join(" · ");
        if (restText) meta.append(el("span", "meta-rest", restText));
        button.append(meta);
        button.addEventListener("click", () => {
          if (row.sc_id || row.nse) openSymbol(row);
        });
        list.append(button);
      });
    }
    box.append(list);
    squares.append(box);
  });
  root.append(squares);
}

function techDerived(row) {
  const smaStack =
    row.sma20 != null && row.sma50 != null ? (row.sma20 > row.sma50 ? 1 : row.sma20 < row.sma50 ? -1 : 0) : null;
  const emaBias =
    row.close != null && row.ema20 != null ? (row.close > row.ema20 ? 1 : row.close < row.ema20 ? -1 : 0) : null;
  return {
    ...row,
    sma_stack: smaStack,
    ema_bias: emaBias,
  };
}

function sortValue(row, col) {
  const enriched = state.desk === "tech" ? techDerived(row) : row;
  const value = enriched[col.key];
  if (col.type === "text") return String(value || "").toUpperCase();
  if (col.type === "obv") {
    if (value === true) return 1;
    if (value === false) return -1;
    return null;
  }
  if (value == null || Number.isNaN(Number(value))) return null;
  return Number(value);
}

function sortedScanRows(rows) {
  const cols = activeColumns();
  const col = cols.find((item) => item.key === state.sortKey) || cols[1];
  const dir = state.sortDir === "asc" ? 1 : -1;
  return rows.slice().sort((a, b) => {
    const av = sortValue(a, col);
    const bv = sortValue(b, col);
    if (av == null && bv == null) return String(a.nse || "").localeCompare(String(b.nse || ""));
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "string" || typeof bv === "string") {
      return String(av).localeCompare(String(bv)) * dir;
    }
    if (av === bv) return String(a.nse || "").localeCompare(String(b.nse || ""));
    return (av < bv ? -1 : 1) * dir;
  });
}

function appendMetricCell(tr, value, tone, digits) {
  const td = el("td", "metric-cell");
  if (value == null || Number.isNaN(Number(value))) {
    td.textContent = "—";
  } else {
    const chip = el("span", "metric-chip " + (tone || ""));
    const text = typeof digits === "number" ? Number(value).toFixed(digits) : String(value);
    chip.append(el("strong", "", text));
    td.append(chip);
  }
  tr.append(td);
}

function renderScanTable(root, rows) {
  const cols = activeColumns();
  const wrap = el("div", "tape");
  const table = el("table");
  const thead = el("thead");
  const head = el("tr");
  cols.forEach((col) => {
    const th = el("th", "sortable");
    const button = el("button", "sort-btn", col.label);
    button.type = "button";
    if (state.sortKey === col.key) {
      button.classList.add("is-on");
      button.dataset.dir = state.sortDir;
      button.append(el("span", "sort-ind", state.sortDir === "asc" ? " ↑" : " ↓"));
    }
    button.addEventListener("click", () => {
      if (state.sortKey === col.key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = col.key;
        state.sortDir = col.type === "text" || col.key === "rank" ? "asc" : "desc";
      }
      persist();
      renderPanel();
    });
    th.append(button);
    head.append(th);
  });
  thead.append(head);
  table.append(thead);
  const tbody = el("tbody");
  sortedScanRows(rows).forEach((row) => {
    const tr = el(
      "tr",
      (row.vol_x || 0) >= 3 || row.bias === "bullish"
        ? "is-bullish"
        : row.bias === "bearish"
          ? "is-bearish"
          : ""
    );
    if (state.desk === "spurts") {
      tr.append(el("td", "", row.rank != null ? String(row.rank) : "—"));
      tr.append(el("td", "", row.exchange || "—"));
      const name = el("td");
      const sym = row.nse || row.id || "";
      if (sym && row.exchange === "NSE") name.append(stockTvLink(sym, "NSE"));
      else if (row.source_url) {
        const a = el("a", "stock-link", sym || row.scrip || "—");
        a.href = row.source_url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        name.append(a);
      } else name.append(document.createTextNode(sym || row.scrip || "—"));
      if (row.name) name.append(document.createTextNode(" · " + row.name));
      tr.append(name);
      tr.append(
        el(
          "td",
          row.up ? "up" : "down",
          row.change_pct != null ? (row.change_pct >= 0 ? "+" : "") + fmtNum(row.change_pct) + "%" : "—"
        )
      );
      appendMetricCell(tr, row.vol_x, (row.vol_x || 0) >= 3 ? "up" : "", 2);
      tr.append(el("td", "", row.volume != null ? fmtVol(row.volume) : "—"));
      tr.append(el("td", "", row.avg_volume != null ? fmtVol(row.avg_volume) : "—"));
      tr.append(el("td", "", row.ltp != null ? fmtNum(row.ltp) : "—"));
      tr.append(
        el(
          "td",
          "",
          row.turnover != null
            ? fmtNum(row.turnover) + (row.turnover_unit ? " " + row.turnover_unit.replace("₹ ", "") : "")
            : "—"
        )
      );
      appendMetricCell(tr, row.score, row.bias || "", null);
    } else if (state.desk === "sci") {
      tr.append(el("td", "", row.rank != null ? String(row.rank) : "—"));
      const name = el("td");
      name.append(stockTvLink(row.nse, row.exchange));
      tr.append(name);
      tr.append(
        el(
          "td",
          row.up ? "up" : "down",
          row.change_pct != null ? (row.change_pct >= 0 ? "+" : "") + fmtNum(row.change_pct) + "%" : "—"
        )
      );
      tr.append(el("td", "", row.rvol != null ? row.rvol.toFixed(2) + "×" : "—"));
      appendMetricCell(tr, row.cmf, row.cmf == null ? "" : row.cmf >= 0 ? "up" : "down", 3);
      appendMetricCell(
        tr,
        row.mfi,
        row.mfi == null ? "" : row.mfi >= 55 ? "up" : row.mfi <= 45 ? "down" : "",
        0
      );
      const forceTd = el("td", "metric-cell");
      if (row.force == null) forceTd.textContent = "—";
      else {
        const chip = el("span", "metric-chip " + (row.force >= 0 ? "up" : "down"));
        chip.append(el("strong", "", fmtCompact(row.force)));
        forceTd.append(chip);
      }
      tr.append(forceTd);
      appendMetricCell(tr, row.voscil, row.voscil == null ? "" : row.voscil >= 0 ? "up" : "down", 1);
      appendMetricCell(tr, row.eom, row.eom == null ? "" : row.eom >= 0 ? "up" : "down", 3);
      appendMetricCell(
        tr,
        row.vwap_bias,
        row.vwap_bias == null ? "" : row.vwap_bias >= 0 ? "up" : "down",
        2
      );
      appendMetricCell(tr, row.score, row.bias || "", null);
      tr.append(el("td", "", row.percentile != null ? String(row.percentile) : "—"));
    } else if (state.desk === "tech") {
      const name = el("td");
      name.append(stockTvLink(row.nse, row.exchange));
      tr.append(name);
      tr.append(
        el(
          "td",
          row.up ? "up" : "down",
          row.change_pct != null ? (row.change_pct >= 0 ? "+" : "") + fmtNum(row.change_pct) + "%" : "—"
        )
      );
      const derived = techDerived(row);
      const allow = selectedIndicatorSet();
      const cols = activeColumns().filter((col) => col.key !== "nse" && col.key !== "change_pct");
      cols.forEach((col) => {
        if (col.key === "rsi" && allow.has("rsi")) {
          appendMetricCell(tr, row.rsi, row.rsi == null ? "" : row.rsi >= 55 ? "up" : row.rsi <= 45 ? "down" : "", 1);
        } else if (col.key === "macd_hist" && allow.has("macd")) {
          appendMetricCell(
            tr,
            row.macd_hist,
            row.macd_hist == null ? "" : row.macd_hist >= 0 ? "up" : "down",
            3
          );
        } else if (col.key === "sma_stack" && allow.has("sma")) {
          const smaTd = el("td", "metric-cell");
          if (derived.sma_stack == null) smaTd.textContent = "—";
          else {
            const chip = el(
              "span",
              "metric-chip " + (derived.sma_stack > 0 ? "up" : derived.sma_stack < 0 ? "down" : "")
            );
            chip.append(
              el("strong", "", derived.sma_stack > 0 ? "20>50" : derived.sma_stack < 0 ? "20<50" : "flat")
            );
            smaTd.append(chip);
          }
          tr.append(smaTd);
        } else if (col.key === "ema_bias" && allow.has("ema")) {
          const emaTd = el("td", "metric-cell");
          if (derived.ema_bias == null) emaTd.textContent = "—";
          else {
            const chip = el(
              "span",
              "metric-chip " + (derived.ema_bias > 0 ? "up" : derived.ema_bias < 0 ? "down" : "")
            );
            chip.append(
              el("strong", "", derived.ema_bias > 0 ? "above" : derived.ema_bias < 0 ? "below" : "at")
            );
            emaTd.append(chip);
          }
          tr.append(emaTd);
        } else if (col.key === "bb_pctb" && allow.has("bb")) {
          appendMetricCell(
            tr,
            row.bb_pctb,
            row.bb_pctb == null ? "" : row.bb_pctb >= 0.5 ? "up" : "down",
            2
          );
        } else if (col.key === "stoch_k" && allow.has("stoch")) {
          appendMetricCell(
            tr,
            row.stoch_k,
            row.stoch_k == null ? "" : row.stoch_k >= 50 ? "up" : "down",
            1
          );
        } else if (col.key === "cci" && allow.has("cci")) {
          appendMetricCell(tr, row.cci, row.cci == null ? "" : row.cci >= 0 ? "up" : "down", 0);
        } else if (col.key === "willr" && allow.has("willr")) {
          appendMetricCell(
            tr,
            row.willr,
            row.willr == null ? "" : row.willr >= -50 ? "up" : "down",
            0
          );
        } else if (col.key === "adx" && allow.has("adx")) {
          const adxTd = el("td");
          if (row.adx == null) adxTd.textContent = "—";
          else {
            const dir =
              row.plus_di != null && row.minus_di != null
                ? row.plus_di > row.minus_di
                  ? " +"
                  : row.plus_di < row.minus_di
                    ? " −"
                    : ""
                : "";
            adxTd.textContent = row.adx.toFixed(1) + dir;
            if (dir === " +") adxTd.className = "up";
            if (dir === " −") adxTd.className = "down";
          }
          tr.append(adxTd);
        } else if (col.key === "roc" && allow.has("roc")) {
          appendMetricCell(tr, row.roc, row.roc == null ? "" : row.roc >= 0 ? "up" : "down", 1);
        } else if (col.key === "score") {
          appendMetricCell(tr, row.score, row.bias || "", null);
        }
      });
    } else {
      const name = el("td");
      name.append(stockTvLink(row.nse, row.exchange));
      tr.append(name);
      tr.append(
        el(
          "td",
          row.up ? "up" : "down",
          row.change_pct != null ? (row.change_pct >= 0 ? "+" : "") + fmtNum(row.change_pct) + "%" : "—"
        )
      );
      tr.append(el("td", "", row.rvol != null ? row.rvol.toFixed(2) + "×" : "—"));
      appendMetricCell(tr, row.cmf, row.cmf == null ? "" : row.cmf >= 0 ? "up" : "down", 2);
      appendMetricCell(
        tr,
        row.mfi,
        row.mfi == null ? "" : row.mfi >= 55 ? "up" : row.mfi <= 45 ? "down" : "",
        0
      );
      tr.append(el("td", "", row.vol_ratio != null ? row.vol_ratio.toFixed(2) : "—"));
      tr.append(el("td", "", fmtVol(row.volume)));
      appendMetricCell(tr, row.score, row.bias || "", null);
      tr.append(el("td", "", row.obv_rising === true ? "↑" : row.obv_rising === false ? "↓" : "—"));
    }
    tbody.append(tr);
  });
  table.append(tbody);
  wrap.append(table);
  root.append(wrap);
}

function renderSymbolDetail(root) {
  const data = state.data;
  const head = el("header", "headline");
  const title = el("h2", "headline-row");
  title.append(stockTvLink(data.symbol.nse, data.symbol.exchange || "NSE"));
  title.append(document.createTextNode(" · " + data.symbol.name));
  head.append(title);
  head.append(
    el(
      "p",
      "sub",
      [
        data.timeframe_label,
        data.stats.bias,
        data.stats.strength,
        data.source.name + (data.source.verified ? " verified" : ""),
      ].join(" · ")
    )
  );
  head.append(studyTags(data.study));
  root.append(head);

  const stats = el("div", "stats");
  const s = data.stats;
  [
    {
      label: "Bias score",
      value: s.score != null ? String(s.score) : "—",
      hint: (s.bias || "neutral") + " · " + (s.strength || ""),
      className: s.bias || "",
    },
    {
      label: "RVOL",
      value: s.rvol != null ? s.rvol.toFixed(2) + "×" : "—",
      hint: s.avg_vol_20 ? "avg " + fmtVol(s.avg_vol_20) : "vs prior N bars",
      className: s.tone === "spike" ? "up" : "",
    },
    {
      label: "CMF",
      value: s.cmf != null ? s.cmf.toFixed(3) : "—",
      hint: "Chaikin Money Flow",
      className: s.cmf == null ? "" : s.cmf >= 0 ? "up" : "down",
    },
    {
      label: "MFI",
      value: s.mfi != null ? s.mfi.toFixed(1) : "—",
      hint: "Money Flow Index (0–100)",
      className: s.mfi == null ? "" : s.mfi >= 55 ? "up" : s.mfi <= 45 ? "down" : "",
    },
    {
      label: "A/D · VPT",
      value: (s.ad != null ? fmtCompact(s.ad) : "—") + " · " + (s.vpt != null ? fmtCompact(s.vpt) : "—"),
      hint: "Accumulation/Distribution · Volume Price Trend",
    },
    {
      label: "Last volume",
      value: fmtVol(s.last_volume),
      hint: s.vol_ratio != null ? "UV/DV " + s.vol_ratio.toFixed(2) : "session volume",
    },
    {
      label: "Price",
      value: s.last_close != null ? fmtNum(s.last_close) : "—",
      hint:
        s.change_pct == null
          ? s.obv_rising === true
            ? "OBV rising"
            : s.obv_rising === false
              ? "OBV falling"
              : "last close"
          : (s.change_pct >= 0 ? "+" : "") + fmtNum(s.change_pct) + "%",
      className: s.change_pct == null ? "" : s.change_pct >= 0 ? "up" : "down",
    },
  ].forEach((item) => {
    const card = el("div", "stat");
    card.append(el("p", "label", item.label));
    card.append(el("p", "value " + (item.className || ""), item.value));
    card.append(el("p", "hint", item.hint));
    stats.append(card);
  });
  root.append(stats);

  const bars = filteredBars();
  const block = el("section", "chart-block");
  const ch = el("div", "chart-head");
  ch.append(el("h2", "", "Price and volume"));
  ch.append(el("p", "caption", "Green = bullish · Red = bearish · " + data.timeframe_label));
  block.append(ch);
  const frame = el("div", "chart-frame");
  drawPriceVolume(frame, bars);
  block.append(frame);
  root.append(block);

  const rBlock = el("section", "chart-block");
  const rh = el("div", "chart-head");
  rh.append(el("h2", "", "Relative volume"));
  rh.append(el("p", "caption", "RVOL = V ÷ avg(prior N) · lines at 1.0× and 1.5×"));
  rBlock.append(rh);
  const rFrame = el("div", "chart-frame short");
  drawRvol(rFrame, bars);
  rBlock.append(rFrame);
  root.append(rBlock);

  const wrap = el("div", "tape");
  const table = el("table");
  const thead = el("thead");
  const hr = el("tr");
  ["When", "Close", "Chg %", "Volume", "RVOL", "CMF", "MFI", "Score", "Bias"].forEach((label) =>
    hr.append(el("th", "", label))
  );
  thead.append(hr);
  table.append(thead);
  const tbody = el("tbody");
  bars
    .slice()
    .reverse()
    .slice(0, 50)
    .forEach((bar) => {
      const tr = el("tr", bar.bias === "bullish" ? "is-bullish" : bar.bias === "bearish" ? "is-bearish" : "");
      tr.append(el("td", "", bar.label));
      tr.append(el("td", "", fmtNum(bar.close)));
      tr.append(el("td", bar.up ? "up" : "down", (bar.change_pct >= 0 ? "+" : "") + fmtNum(bar.change_pct)));
      tr.append(el("td", "", fmtVol(bar.volume)));
      tr.append(el("td", "", bar.rvol != null ? bar.rvol.toFixed(2) + "×" : "—"));
      tr.append(el("td", "", bar.cmf != null ? bar.cmf.toFixed(3) : "—"));
      tr.append(el("td", "", bar.mfi != null ? bar.mfi.toFixed(1) : "—"));
      tr.append(el("td", "", bar.score != null ? String(bar.score) : "—"));
      tr.append(el("td", bar.bias || "", bar.bias || "neutral"));
      tbody.append(tr);
    });
  table.append(tbody);
  wrap.append(table);
  root.append(wrap);
}

function renderPanel() {
  els.panel.replaceChildren();
  if (state.mode === "scan") {
    if (!state.board) {
      els.panel.append(
        el(
          "p",
          "board-note",
          state.desk === "spurts"
            ? "Loading live NSE / BSE volume spurts…"
            : "Running model on " + universeLabel(state.universe) + "…"
        )
      );
      return;
    }
    if (state.desk === "spurts") {
      const note = el("p", "board-note");
      const nseA = el("a", "stock-link", "NSE gainers");
      nseA.href = (state.board.links && state.board.links.nse) || "https://www.nseindia.com/market-data/volume-gainers-spurts";
      nseA.target = "_blank";
      nseA.rel = "noopener noreferrer";
      const bseA = el("a", "stock-link", "BSE spurts");
      bseA.href = (state.board.links && state.board.links.bse) || "https://www.bseindia.com/markets/equity/eqreports/missprtvol";
      bseA.target = "_blank";
      bseA.rel = "noopener noreferrer";
      const feedBits = (state.board.feeds || [])
        .map((feed) => {
          if (!feed.ok) return (feed.name || "?") + " down";
          const stamp = feed.as_of ? " @ " + String(feed.as_of).replace(" IST", "") : "";
          return (feed.name || "?") + " " + (feed.count || 0) + stamp;
        })
        .join(" · ");
      note.append(
        nseA,
        document.createTextNode(" · "),
        bseA,
        document.createTextNode(
          " · live only" +
            (state.board.as_of ? " · desk " + state.board.as_of : "") +
            (feedBits ? " · " + feedBits : "") +
            (state.board.cached ? " · cached ≤20s" : " · fresh")
        )
      );
      els.panel.append(note);
      renderScanTable(els.panel, filteredRows());
      return;
    }
    if (state.tab === "trend") {
      renderTrend(els.panel, state.board.rows);
      return;
    }
    renderScanTable(els.panel, filteredRows());
    return;
  }
  if (!state.data) return;
  if (state.tab === "trend") {
    renderTrend(
      els.panel,
      state.data.bars.map((bar) => ({
        ...bar,
        nse: null,
        name: null,
      }))
    );
    return;
  }
  renderSymbolDetail(els.panel);
}

function updateFoot() {
  if (!els.foot) return;
  els.foot.textContent =
    state.desk === "tech"
      ? "Technical stack · RSI · MACD · SMA · EMA · BB · Stoch · CCI · %R · ADX · ROC · bias ≥+30 / ≤−30 · research only."
      : state.desk === "sci"
        ? "Lab · RVOL · OBV · CMF · MFI · Force · VOsc · EOM · VWAP · PVT · refs StockCharts/Chaikin/Elder/Granville/Arms · research only."
        : state.desk === "spurts"
          ? "Live spurts · NSE volume gainers + BSE spurt-in-volume · Vol× vs avg · research only."
          : "Volume stack · RVOL · OBV · UV/DV · CMF · MFI · A/D · VPT · bias ≥+30 / ≤−30 · research only.";
}

async function loadSources(fresh) {
  const res = await fetch("/api/sources" + (fresh ? "?fresh=1" : ""));
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Source check failed");
  state.sources = data;
  if (Array.isArray(data.universes) && els.universe) {
    const current = state.universe;
    els.universe.replaceChildren();
    data.universes.forEach((item) => {
      const opt = el("option", "", UNIVERSE_SHORT[item.id] || item.label);
      opt.value = item.id;
      opt.title = item.label || UNIVERSE_LABELS[item.id] || item.id;
      if (item.id === current) opt.selected = true;
      els.universe.append(opt);
    });
    if (!UNIVERSES.includes(current) && data.universes[0]) {
      state.universe = data.universes[0].id;
      els.universe.value = state.universe;
    }
  }
  renderSources();
  renderSession(data.session);
  return data;
}

async function loadBoard(fresh) {
  if (inflight) inflight.abort();
  inflight = new AbortController();
  const label = universeLabel(state.universe);
  const labelDesk = deskLabel();
  if (state.desk === "spurts") {
    els.status.textContent = "Fetching live NSE/BSE volume spurts…";
  } else {
    els.status.textContent = "Running " + labelDesk.toLowerCase() + " model · " + label + " · " + state.tf + "…";
  }
  const params = new URLSearchParams();
  if (state.desk !== "spurts") {
    params.set("tf", state.tf);
    params.set("universe", state.universe);
  } else {
    params.set("exchange", "all");
  }
  if (fresh) params.set("fresh", "1");
  if (state.desk === "tech") {
    params.set("indicators", state.techIndicators.join(","));
  }
  const endpoint =
    state.desk === "tech"
      ? "/api/tech-board?"
      : state.desk === "sci"
        ? "/api/sci-board?"
        : state.desk === "spurts"
          ? "/api/spurts?"
          : "/api/board?";
  try {
    const res = await fetch(endpoint + params.toString(), { signal: inflight.signal });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Scan failed");
    state.board = data;
    if (data.sources) {
      state.sources = { ...(state.sources || {}), sources: data.sources, ready: data.source.verified };
      renderSources();
    }
    if (state.desk === "spurts" && Array.isArray(data.feeds)) {
      const panel = document.getElementById("source-panel");
      if (panel) {
        panel.replaceChildren();
        data.feeds.forEach((feed) => {
          const card = el("div", "source-card " + (feed.ok ? "ok" : ""));
          card.title = feed.error || feed.api || feed.url || "";
          card.append(el("strong", "", feed.name || "Feed"));
          card.append(
            el("span", "src-detail", feed.ok ? feed.count + " names" : feed.error || "down")
          );
          if (feed.url) {
            const a = el("a", "stock-link", "↗");
            a.href = feed.url;
            a.target = "_blank";
            a.rel = "noopener noreferrer";
            a.style.marginLeft = "4px";
            card.append(a);
          }
          panel.append(card);
        });
        setFoldTitle(
          "source-fold",
          "Feeds · " + data.feeds.filter((f) => f.ok).length + "/" + data.feeds.length + " live"
        );
      }
    }
    renderSession(data.session);
    renderMeter();
    renderTabs();
    renderPanel();
    if (state.desk === "spurts") {
      const errNote = Array.isArray(data.errors) && data.errors.length ? " · " + data.errors[0] : "";
      const nseFeed = (data.feeds || []).find((f) => f.name === "NSE");
      const nseStamp = nseFeed && nseFeed.as_of ? " · NSE " + nseFeed.as_of : "";
      els.status.textContent =
        "Spurts live · NSE " +
        (data.counts.nse || 0) +
        " · BSE " +
        (data.counts.bse || 0) +
        " · " +
        data.scanned +
        " names" +
        (data.as_of ? " · " + data.as_of : "") +
        nseStamp +
        (data.cached ? " · cached ≤20s" : " · fresh") +
        " · auto 25s" +
        errNote;
      syncSpurtRefresh();
    } else {
      els.status.textContent =
        labelDesk +
        " ready · " +
        (data.universe_label || label) +
        " · " +
        data.scanned +
        (data.universe_size ? "/" + data.universe_size : "") +
        " · " +
        data.timeframe_label +
        " · " +
        data.counts.bullish +
        " bull / " +
        data.counts.bearish +
        " bear" +
        (data.cached ? " · cached" : "");
    }
  } catch (err) {
    if (err.name === "AbortError") return;
    els.status.textContent = err.message || "Model run failed";
  }
}

function switchDesk(desk) {
  if (!DESKS.includes(desk) || desk === state.desk) return;
  state.desk = desk;
  state.mode = "scan";
  state.tab = "trend";
  if (desk === "sci" || desk === "spurts") {
    state.sortKey = desk === "spurts" ? "vol_x" : "rank";
    state.sortDir = desk === "spurts" ? "desc" : "asc";
  } else {
    state.sortKey = "score";
    state.sortDir = "desc";
  }
  state.board = null;
  state.data = null;
  els.q.value = "";
  applyDeskChrome();
  persist();
  renderTabs();
  renderPanel();
  syncSpurtRefresh();
  loadBoard(desk === "spurts");
}

async function loadVolume(fresh) {
  if (inflight) inflight.abort();
  inflight = new AbortController();
  els.status.textContent = "Loading signal · " + state.symbol + " · " + state.tf + "…";
  const params = new URLSearchParams({
    symbol: state.symbol,
    sc_id: state.scId || "",
    kind: state.kind,
    tf: state.tf,
  });
  if (fresh) params.set("fresh", "1");
  try {
    const res = await fetch("/api/volume?" + params.toString(), { signal: inflight.signal });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Volume request failed");
    state.data = data;
    if (data.sources) {
      state.sources = { ...(state.sources || {}), sources: data.sources, ready: data.source.verified };
      renderSources();
    }
    renderSession(data.session);
    renderMeter();
    renderTabs();
    renderPanel();
    els.status.textContent =
      data.symbol.nse +
      " · " +
      data.timeframe_label +
      " · " +
      (data.stats.bias || "neutral") +
      " (" +
      (data.stats.score ?? "—") +
      ")" +
      (data.cached ? " (cached)" : "");
  } catch (err) {
    if (err.name === "AbortError") return;
    els.status.textContent = err.message || "Could not load volume";
  }
}

async function runSearch(query) {
  if (!query) {
    els.suggestions.hidden = true;
    els.suggestions.replaceChildren();
    return;
  }
  const res = await fetch("/api/search?q=" + encodeURIComponent(query));
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Search failed");
  els.suggestions.replaceChildren();
  if (!data.results.length) {
    els.suggestions.hidden = true;
    return;
  }
  data.results.forEach((item) => {
    const button = el("button", "");
    button.type = "button";
    button.append(document.createTextNode(item.label));
    if (item.sector) button.append(el("span", "meta", item.sector));
    button.addEventListener("click", () => {
      state.mode = "symbol";
      state.kind = "stock";
      state.symbol = item.nse;
      state.scId = item.sc_id;
      state.tab = "chart";
      els.q.value = item.nse;
      els.suggestions.hidden = true;
      persist();
      loadVolume();
    });
    els.suggestions.append(button);
  });
  els.suggestions.hidden = false;
}

function bind() {
  document.querySelectorAll("[data-desk]").forEach((button) => {
    button.addEventListener("click", () => switchDesk(button.dataset.desk));
  });

  if (els.techIndAll) {
    els.techIndAll.addEventListener("click", () => {
      els.techIndList.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        input.checked = true;
      });
    });
  }
  if (els.techIndNone) {
    els.techIndNone.addEventListener("click", () => {
      els.techIndList.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        input.checked = false;
      });
    });
  }
  if (els.techIndApply) {
    els.techIndApply.addEventListener("click", () => {
      state.techIndicators = readTechFilterSelection();
      if (!activeColumns().some((col) => col.key === state.sortKey)) {
        state.sortKey = "score";
      }
      syncTechFilterSummary();
      if (els.techFilter) els.techFilter.open = false;
      persist();
      state.mode = "scan";
      state.tab = "trend";
      loadBoard(true);
    });
  }

  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = els.q.value.trim().toUpperCase();
    if (!query) return;
    state.mode = "symbol";
    state.kind = "stock";
    state.symbol = query;
    state.scId = "";
    state.tab = "chart";
    els.suggestions.hidden = true;
    persist();
    loadVolume(true);
  });

  els.q.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      runSearch(els.q.value.trim()).catch((err) => {
        els.status.textContent = err.message;
      });
    }, 220);
  });

  if (els.universe) {
    els.universe.addEventListener("change", () => {
      state.universe = els.universe.value;
      state.mode = "scan";
      state.tab = "trend";
      els.q.value = "";
      persist();
      loadBoard();
    });
  }

  document.querySelectorAll("[data-tf]").forEach((button) => {
    button.addEventListener("click", () => {
      state.tf = button.dataset.tf;
      document.querySelectorAll("[data-tf]").forEach((node) => {
        node.classList.toggle("is-on", node.dataset.tf === state.tf);
      });
      persist();
      if (state.mode === "scan") loadBoard();
      else loadVolume();
    });
  });
}

async function boot() {
  restore();
  bind();
  applyDeskChrome();
  try {
    const sources = await loadSources(false);
    if (!sources.ready) {
      els.status.textContent = "Primary feed unavailable.";
      return;
    }
    renderTabs();
    if (state.mode === "symbol" && state.desk === "volume") {
      els.q.value = state.symbol;
      await loadVolume(false);
    } else {
      state.mode = "scan";
      await loadBoard(state.desk === "spurts");
      syncSpurtRefresh();
    }
  } catch (err) {
    els.status.textContent = err.message || "Could not start Signal Desk";
  }
}

boot();
