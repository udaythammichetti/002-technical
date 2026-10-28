import { useDesk } from '../store'

const GUIDES = {
  volume: {
    title: 'Volume',
    blurb: 'Bias from price move confirmed by volume / money-flow. Bull ≥+30 · Bear ≤−30.',
    params: [
      { id: 'Score', tip: '±25 price · ±25 RVOL≥1 · ±15 RVOL≥1.5 · ±15 OBVΔ · ±10 UV/DV · ±10 CMF · ±10 MFI' },
      { id: 'RVOL', tip: 'Current volume ÷ average of prior N bars (≥1.5× = spike)' },
      { id: 'CMF', tip: 'Chaikin Money Flow — close location in range × volume (buying pressure)' },
      { id: 'MFI', tip: 'Money Flow Index 0–100 — volume-weighted momentum (≥55 buy / ≤45 sell lean)' },
      { id: 'UV/DV', tip: 'Up-bar volume ÷ down-bar volume over the lookback window' },
      { id: 'OBV', tip: 'On-Balance Volume — rising = accumulation, falling = distribution' },
      { id: 'A/D', tip: 'Accumulation / Distribution — running money-flow volume from H/L/C' },
      { id: 'VPT', tip: 'Volume Price Trend — cumulative volume × % price change' },
    ],
  },
  tech: {
    title: 'Technical',
    blurb: 'Default signals: RSI · MACD · SMA 20/50 · EMA 20. Score (−100…+100). Bull ≥+30 · Bear ≤−30.',
    params: [
      { id: 'Score', tip: 'Votes from RSI + MACD + SMA20/50 + EMA20, scaled to −100…+100' },
      { id: 'RSI', tip: 'RSI(14) Wilder — ≥55 bullish · ≤45 bearish · ≥60 / ≤40 strong' },
      { id: 'MACD', tip: 'MACD(12,26,9) hist — hist>0 and line>signal = bullish' },
      { id: 'SMA', tip: 'SMA20 vs SMA50 — 20>50 uptrend stack' },
      { id: 'EMA', tip: 'Close vs EMA20 — above = short-term bullish' },
    ],
  },
  sci: {
    title: 'Lab',
    blurb: 'Bull breakouts and coils — Donchian · Bollinger · ATR · RVOL · CMF · OBV.',
    params: [
      { id: 'Break↑', tip: 'Close breaks prior HH_N with RVOL ≥ 1.5 (Donchian + relative volume)' },
      { id: 'Bull base', tip: 'Tight range + accumulation (CMF>0 or OBV↑ or higher lows)' },
      { id: 'Coil', tip: 'Range% tight + BandWidth/ATR% contraction + volume dry-up in base' },
      { id: 'Range%', tip: '100 × (HH−LL)/mid over N bars of the active TF — smaller = tighter coil' },
      { id: 'RVOL', tip: 'Today volume ÷ SMA(volume,N) — confirms real breakouts' },
      { id: 'CMF', tip: 'Chaikin Money Flow in the base — buying while price consolidates' },
      { id: 'OBV', tip: 'On-Balance Volume rising through the coil = quiet accumulation' },
      { id: 'HL', tip: 'Higher pivot lows — bullish swing structure inside the range' },
    ],
  },
  chart: {
    title: 'Chart',
    blurb: 'ChartSchool S/R · trends · gaps · patterns · Fib · candles on the active TF.',
    params: [
      { id: 'S/R', tip: 'Nearest pivot support/resistance · near ≤1.25% · break = close through zone' },
      { id: 'Trend', tip: 'Valid up/down needs ≥3 swing touches + rising lows / falling highs' },
      { id: 'Gap', tip: 'low>prior high / high<prior low · breakaway needs congestion + RVOL≥1.4' },
      { id: 'Pattern', tip: 'Rectangle · asc/desc/sym triangle · double top/bottom · flag' },
      { id: 'Fib', tip: 'Pullback: High−span×r · bounce: Low+span×r · alert at 38.2/50/61.8%' },
      { id: 'Candle', tip: 'Hammer/star need context at S/R · engulfing wraps prior body' },
      { id: 'Score', tip: 'Confluence 0…100 · bullish ≥60 · bearish ≤40 · strong ≥72/≤28' },
    ],
  },
  spurts: {
    title: 'Spurts',
    blurb:
      'Default view is the live NSE + BSE data table. Open Historic for archive tables (by date / reappeared).',
    params: [
      { id: 'Live table', tip: 'Default · Rank · Exch · Stock · Chg · Vol× · Volume · LTP…' },
      { id: 'Date', tip: 'Toolbar · Live today, or load any saved day’s table' },
      { id: 'Historic', tip: 'Collapsed on demand · By date table + Reappeared table' },
      { id: 'Save day', tip: 'Write today’s list to data/spurts_history/ (also auto after 15:30 IST)' },
      { id: 'Vol×', tip: 'Session volume ÷ exchange reference average' },
    ],
  },
}

const FORMULA_ORDER = [
  'timeframe',
  'history',
  'reappear',
  'rsi',
  'macd',
  'sma',
  'ema',
  'rvol',
  'cmf',
  'mfi',
  'obv',
  'range',
  'squeeze',
  'structure',
  'support',
  'resistance',
  'trend',
  'fib',
  'gap_up',
  'bull_breakout',
  'vol_x',
  'nse',
  'bse',
  'score',
]

export default function DeskGuide() {
  const desk = useDesk((s) => s.desk)
  const board = useDesk((s) => s.board)
  const guide = GUIDES[desk] || GUIDES.volume
  const names = guide.params.map((p) => p.id).join(' · ')
  const formulas = board?.formulas || null
  const tfMeta = board?.tf_meta && desk !== 'spurts' ? board.tf_meta : null
  const formulaKeys = formulas
    ? FORMULA_ORDER.filter((k) => formulas[k]).concat(
        Object.keys(formulas).filter((k) => !FORMULA_ORDER.includes(k)),
      )
    : []

  return (
    <details className="desk-guide" aria-label={`${guide.title} parameters`}>
      <summary className="desk-guide-summary">
        <span className="desk-guide-title">{guide.title}</span>
        <span className="desk-guide-mini" title={guide.blurb}>
          {names}
        </span>
        <span className="desk-guide-toggle" aria-hidden="true">
          +
        </span>
      </summary>
      <div className="desk-guide-body">
        {guide.blurb ? <p className="desk-guide-blurb">{guide.blurb}</p> : null}
        {tfMeta ? (
          <p className="desk-guide-tf">
            {tfMeta.label} · {tfMeta.resolution_label} · N={tfMeta.avg_window}
          </p>
        ) : null}
        <div className="desk-guide-params">
          {guide.params.map((p) => (
            <div key={p.id} className="guide-chip" title={p.tip}>
              <em>{p.id}</em>
              <span>{p.tip}</span>
            </div>
          ))}
        </div>
        {formulas ? (
          <details className="desk-guide-formulas">
            <summary>Formulas</summary>
            <ul>
              {formulaKeys.slice(0, 12).map((key) => (
                <li key={key}>
                  <strong>{key}</strong>
                  <span> — {formulas[key]}</span>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </details>
  )
}
