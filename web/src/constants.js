export const DESKS = [
  { id: 'volume', label: 'Volume', title: 'Volume', blurb: '' },
  { id: 'tech', label: 'Technical', title: 'Technical', blurb: '' },
  { id: 'sci', label: 'Lab', title: 'Lab', blurb: '' },
  { id: 'chart', label: 'Chart', title: 'Chart', blurb: '' },
  { id: 'candle', label: 'Candles', title: 'Candles', blurb: '' },
]

export const TIMEFRAMES = [
  '15m',
  '1h',
  '4h',
  '1d',
  '1d2',
  '1d3',
  '1d4',
  '1d5',
  '1df',
  '1w',
  '1m',
  '3m',
  '6m',
  '1y',
  '5y',
  'max',
]

/** Intraday chips — useful for Volume/Technical/Lab; not for Chart patterns. */
export const INTRADAY_TF_IDS = new Set(['15m', '1h', '4h'])

/** Chart desk default — tight 160-bar daily swing window. */
export const CHART_DEFAULT_TF = '1d'

/** Chip labels: number + unit letter (15m stays lowercase m for minutes). */
export const TF_GROUPS = [
  {
    id: 'intraday',
    label: 'Intraday',
    items: [
      { id: '15m', label: '15m' },
      { id: '1h', label: '1H' },
      { id: '4h', label: '4H' },
    ],
  },
  {
    id: 'swing',
    label: 'Swing',
    items: [
      { id: '1d', label: '1D' },
      { id: '1w', label: '1W' },
      { id: '1m', label: '1M' },
    ],
  },
  {
    id: 'long',
    label: 'Long',
    items: [
      { id: '3m', label: '3M' },
      { id: '6m', label: '6M' },
      { id: '1y', label: '1Y' },
      { id: '5y', label: '5Y' },
    ],
  },
  {
    id: 'max',
    label: 'Max',
    items: [{ id: 'max', label: 'Max' }],
  },
]

/**
 * Chart read windows. The group is the bar size; the chip is how much history.
 * Daily = daily candles. Swing = weekly candles. Long = monthly, then max weekly.
 * S/R, demand, and supply use the whole chip. Trend keeps a shorter swing look.
 */
export const CHART_TF_GROUPS = [
  {
    id: 'daily',
    label: 'Daily',
    items: [
      {
        id: '1d',
        label: '6M',
        title: '126 daily sessions · half year · RVOL(50) · S/R base(20) · Fib on these 126 bars',
      },
      {
        id: '1y',
        label: '1Y',
        title: '252 daily sessions · one trading year · RVOL(50) · S/R base(20)',
      },
      {
        id: '1d2',
        label: '2Y',
        title: '504 daily sessions · 252×2 · RVOL(50) · S/R base(20)',
      },
      {
        id: '1d3',
        label: '3Y',
        title: '756 daily sessions · 252×3 · RVOL(50) · S/R base(20)',
      },
      {
        id: '1d4',
        label: '4Y',
        title: '1008 daily sessions · 252×4 · RVOL(50) · S/R base(20)',
      },
      {
        id: '1d5',
        label: '5Y',
        title: '1260 daily sessions · 252×5 · daily bars, not the weekly 5Y·W chip',
      },
      {
        id: '1df',
        label: '10Y',
        title: '2520 daily sessions · 252×10 · older spikes widen demand/supply',
      },
    ],
  },
  {
    id: 'swing',
    label: 'Swing',
    items: [
      {
        id: '1w',
        label: '2Y·W',
        title: '104 weekly bars · two years · RVOL(50) = 50 weeks · S/R base(20)',
      },
      {
        id: '5y',
        label: '5Y·W',
        title: '260 weekly bars · 52×5 · RVOL(50) = 50 weeks',
      },
    ],
  },
  {
    id: 'long',
    label: 'Long',
    items: [
      {
        id: '1m',
        label: '5Y·M',
        title: '60 monthly bars · five years · RVOL(50) = 50 months · S/R base(20)',
      },
      {
        id: 'max',
        label: '10Y·W',
        title: '520 weekly bars · 52×10 · longest weekly read · RVOL(50)',
      },
    ],
  },
]

/** TF chip groups visible on a desk (Chart hides Intraday; uses depth options). */
export function tfGroupsForDesk(desk) {
  if (desk === 'chart') return CHART_TF_GROUPS
  return TF_GROUPS
}

/** Book dropdown order: Nifty ladder → Cap → BSE → Exchange. */
export const BOOK_GROUPS = [
  { id: 'Nifty', label: 'Nifty' },
  { id: 'Cap', label: 'Cap' },
  { id: 'BSE', label: 'BSE' },
  { id: 'Exchange', label: 'Exchange' },
]

export const UNIVERSES = [
  { id: 'nifty50', short: 'N50', label: 'Nifty 50', group: 'Nifty' },
  { id: 'next50', short: 'NXT', label: 'Nifty Next 50', group: 'Nifty' },
  { id: 'largecap', short: 'N100', label: 'Nifty 100', group: 'Nifty' },
  { id: 'nifty200', short: 'N200', label: 'Nifty 200', group: 'Nifty' },
  { id: 'nifty500', short: 'N500', label: 'Nifty 500', group: 'Nifty' },
  { id: 'midcap50', short: 'M50', label: 'Nifty Midcap 50', group: 'Cap' },
  { id: 'midcap', short: 'M150', label: 'Nifty Midcap 150', group: 'Cap' },
  { id: 'smallcap50', short: 'S50', label: 'Nifty Smallcap 50', group: 'Cap' },
  { id: 'smallcap', short: 'S250', label: 'Nifty Smallcap 250', group: 'Cap' },
  { id: 'microcap', short: 'μ250', label: 'Nifty Microcap 250', group: 'Cap' },
  { id: 'largemidcap', short: 'LM250', label: 'Nifty LargeMidcap 250', group: 'Cap' },
  { id: 'bse_large', short: 'BSE-A', label: 'BSE Group A', group: 'BSE' },
  { id: 'bse_mid', short: 'BSE-B', label: 'BSE Group B', group: 'BSE' },
  { id: 'nse_all', short: 'NSE', label: 'NSE All', group: 'Exchange' },
  { id: 'bse_all', short: 'BSE', label: 'BSE All', group: 'Exchange' },
]

export const TECH_INDICATORS = [
  { id: 'rsi', label: 'RSI' },
  { id: 'macd', label: 'MACD' },
  { id: 'ppo', label: 'PPO' },
  { id: 'sma', label: 'SMA 20/50' },
  { id: 'sma200', label: 'SMA 50/200' },
  { id: 'ema', label: 'EMA 20' },
  { id: 'stoch', label: 'Stochastic' },
  { id: 'adx', label: 'ADX + DI' },
  { id: 'aroon', label: 'Aroon' },
  { id: 'bb', label: '%B' },
  { id: 'roc', label: 'ROC' },
  { id: 'cci', label: 'CCI' },
  { id: 'willr', label: 'Williams %R' },
]

export const TECH_CORE = [
  { id: 'rsi', label: 'RSI' },
  { id: 'macd', label: 'MACD' },
  { id: 'ppo', label: 'PPO' },
  { id: 'sma', label: 'SMA 20/50' },
  { id: 'sma200', label: 'SMA 50/200' },
  { id: 'ema', label: 'EMA 20' },
  { id: 'bb', label: 'BB %B' },
  { id: 'stoch', label: 'Stochastic' },
  { id: 'cci', label: 'CCI' },
  { id: 'willr', label: 'Williams %R' },
  { id: 'adx', label: 'ADX + DI' },
  { id: 'aroon', label: 'Aroon' },
  { id: 'roc', label: 'ROC' },
]

export const TECH_CORE_IDS = TECH_CORE.map((i) => i.id)
export const TECH_INDICATOR_IDS = TECH_INDICATORS.map((i) => i.id)

/**
 * Desk tabs — ids are stable filters; labels are Title Case.
 */
export const TABS = {
  volume: [
    ['trend', 'Map'],
    ['bullish', 'Bullish'],
    ['bearish', 'Bearish'],
    ['spike', 'Spike'],
  ],
  tech: [
    ['trend', 'Map'],
    ['bullish', 'Bullish'],
    ['bearish', 'Bearish'],
  ],
  sci: [
    ['trend', 'Map'],
    ['bullish', 'Bullish'],
    ['consolidating', 'Coil'],
    ['breakout', 'Breakout'],
  ],
  chart: [
    ['trend', 'Map'],
    ['bullish', 'Bullish'],
    ['bearish', 'Bearish'],
    ['breakout', 'Breakout'],
    ['support', 'S/R · Fib'],
  ],
  candle: [
    ['trend', 'Map'],
    ['bullish', 'Bullish'],
    ['bearish', 'Bearish'],
    ['aligned', 'Aligned'],
    ['turn_up', 'Turn↑'],
    ['turn_dn', 'Turn↓'],
    ['2d', '2D↑'],
    ['day', 'Day↑'],
    ['week', 'Week↑'],
    ['month', 'Month↑'],
  ],
}

export const LEGENDS = {
  volume: [
    ['Bullish ≥+30', 'Bias score ≥ +30 — price up with volume confirmation'],
    ['Bearish ≤−30', 'Bias score ≤ −30 — price down with volume confirmation'],
    ['Thin / Partial', 'Recent listings · lookbacks shrink · Score tagged T/P'],
    ['RVOL · VolZ', 'Relative volume + z-score anomaly (≥1.5× / ≥2σ spike)'],
    ['CMF · MFI', 'Chaikin Money Flow · Money Flow Index (ChartSchool)'],
    ['Force · EMV', 'Elder Force Index · Arms Ease of Movement'],
    ['VOsc · UV/DV', 'Volume Oscillator % · up/down volume ratio'],
    ['OBV · A/D', 'On-Balance Volume · Accumulation/Distribution slope'],
  ],
  tech: [
    ['Bullish ≥+30', 'Technical score ≥ +30 from selected Signals'],
    ['Bearish ≤−30', 'Technical score ≤ −30 from selected Signals'],
    ['Thin / Partial', 'Recent listings · periods shrink · Score uses only Signals that fit'],
    ['Core', 'RSI · MACD · PPO · SMA20/50 · SMA50/200 · EMA · Stoch · ADX · Aroon · %B · ROC'],
  ],
  sci: [
    ['Breakout', 'Close > Donchian HH + RVOL≥1.5 — volume-confirmed breakout'],
    ['Bull base', 'Tight coil + CMF/OBV/higher-lows accumulation'],
    ['Coil', 'Range% + BandWidth/ATR squeeze + volume dry-up'],
    ['Thin / Partial', 'New listings · Donchian/RVOL windows shrink · score tagged T/P'],
  ],
  chart: [
    ['Read window', 'Daily 126–2520 sessions · Swing 104/260 weeks · Long 60 months / 520 weeks'],
    ['Score · Bias · Edge · Conf', 'Score 0…100 (≥60 bull / ≤40 bear) · Edge=top setup · Conf=bull−bear'],
    ['Setup · Sup/Res · Dist% · Range%', 'near_support/breakout… · pivots · near ≤1.25% (wider on IPO)'],
    ['Trend · Touches · HL/LH', '≥3 touches (2 if thin) · rising lows / falling highs'],
    ['Pattern · Gap · Fib · Candle · RVOL', 'ChartSchool patterns · Fib off until ≥24 bars · RVOL confirms'],
    ['Thin / Partial', 'Recent listings · all available bars · lookbacks shrink · score dampened · T/P'],
  ],
  candle: [
    ['Turn ↑N/↓N', 'Month weak + days recovering = ↑ · month strong + days rolling over = ↓ · strength 1…3 · not in Score'],
    ['Turn↑ · Turn↓', 'Filter bull / bear turnaround rows'],
    ['2D', 'Last 2 daily candles · filter 2D↑ · not counted in Score ±N/9'],
    ['3/5/7', 'Last 3, 5, and 7 candles on each horizon'],
    ['D · W · M', 'Lean chips · ≥2 of 3 windows Bull/Bear on that horizon · then daily/weekly/monthly columns'],
    ['Map', 'Nine-window heat · Day · Week · Month · green Bull · red Bear · grey Flat'],
    ['2D↑ · Day↑ · Week↑ · Month↑', '2D↑ = last 2 days Bull · Day/Week/Month↑ = that horizon lean is Bull'],
    ['Bull (2/3)', 'Green cells · (green candles / window). Bull when closed up ≥0.35% with greens ≥ reds'],
    ['Bear (1/3)', 'Red cells · same count form. Bear when closed down ≥0.35% with reds ≥ greens'],
    ['Flat', 'Net move inside ±0.35%, or candle colors disagree with the close'],
    ['Score', 'Bull windows − bear windows as ±N/9. Bias at ±3 · Aligned when |Score| ≥ 6'],
    ['30D', 'Spark of the last 30 daily closes'],
  ],
}

export const FOOT = {
  volume: 'Volume · RVOL · VolZ · Force · EMV · CMF · MFI · research only',
  tech: 'Technical · RSI · MACD · SMA · EMA · research only',
  sci: 'Lab · Donchian(20) · RVOL(50 prior) · CMF/OBV(20) · BB+ATR squeeze · research only',
  chart: 'Chart · Daily 6M–10Y · Swing 2Y·W/5Y·W · Long 5Y·M/10Y·W · research only',
  candle: 'Candles · last 3/5/7 daily, weekly, and monthly · Bull (2/3) · Score ±N/9 · research only',
}
