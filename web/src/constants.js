export const DESKS = [
  { id: 'volume', label: 'Volume', title: 'Volume', blurb: '' },
  { id: 'tech', label: 'Technical', title: 'Technical', blurb: '' },
  { id: 'sci', label: 'Lab', title: 'Lab', blurb: '' },
  { id: 'chart', label: 'Chart', title: 'Chart', blurb: '' },
  { id: 'spurts', label: 'Spurts', title: 'Spurts', blurb: '' },
]

export const TIMEFRAMES = ['15m', '1h', '4h', '1d', '1w', '1m', '3m', '6m', '1y', '5y', 'max']

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
      { id: 'max', label: 'Max' },
    ],
  },
]

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

/** Default Technical signal set (pre-selected in filter). */
export const TECH_CORE = [
  { id: 'rsi', label: 'RSI' },
  { id: 'macd', label: 'MACD' },
  { id: 'sma', label: 'SMA 20/50' },
  { id: 'ema', label: 'EMA 20' },
]

export const TECH_CORE_IDS = TECH_CORE.map((i) => i.id)

/** Full Technical filter list — score uses whatever is selected. */
export const TECH_INDICATORS = [
  { id: 'rsi', label: 'RSI' },
  { id: 'macd', label: 'MACD' },
  { id: 'sma', label: 'SMA 20/50' },
  { id: 'ema', label: 'EMA 20' },
  { id: 'bb', label: 'BB %B' },
  { id: 'stoch', label: 'Stochastic' },
  { id: 'cci', label: 'CCI' },
  { id: 'willr', label: 'Williams %R' },
  { id: 'adx', label: 'ADX + DI' },
  { id: 'roc', label: 'ROC' },
]

export const TECH_INDICATOR_IDS = TECH_INDICATORS.map((i) => i.id)

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
    ['bullish', 'Bull'],
    ['consolidating', 'Consolidating'],
    ['breakout', 'Breakout'],
  ],
  chart: [
    ['trend', 'Map'],
    ['bullish', 'Bullish'],
    ['bearish', 'Bearish'],
    ['breakout', 'Breakout'],
    ['support', 'S/R · Fib'],
  ],
  spurts: [
    ['trend', 'All'],
    ['nse', 'NSE'],
    ['bse', 'BSE'],
    ['spike', '≥3×'],
  ],
}

export const LEGENDS = {
  volume: [
    ['Bull ≥+30', 'Bias score ≥ +30 — price up with volume confirmation'],
    ['Bear ≤−30', 'Bias score ≤ −30 — price down with volume confirmation'],
    ['RVOL', 'Relative volume vs prior N bars'],
    ['CMF', 'Chaikin Money Flow — buying pressure'],
    ['MFI', 'Money Flow Index (0–100)'],
    ['UV/DV', 'Up-bar volume ÷ down-bar volume'],
    ['OBV', 'On-Balance Volume rising / falling'],
    ['A/D · VPT', 'Accumulation/Distribution · Volume Price Trend'],
  ],
  tech: [
    ['Bull ≥+30', 'Technical score ≥ +30 from RSI · MACD · SMA · EMA'],
    ['Bear ≤−30', 'Technical score ≤ −30 from RSI · MACD · SMA · EMA'],
    ['Stack', 'RSI(14) · MACD(12,26,9) · SMA20/50 · EMA20'],
  ],
  sci: [
    ['Bull break', 'Close > Donchian HH + RVOL≥1.5 — volume-confirmed breakout'],
    ['Bull base', 'Tight coil + CMF/OBV/higher-lows accumulation'],
    ['Coil', 'Range% + BandWidth/ATR squeeze + volume dry-up'],
  ],
  chart: [
    ['S/R', 'Support & resistance from reaction highs/lows — ChartSchool'],
    ['Trend', 'Uptrend / downtrend lines from swing pivots'],
    ['Gaps · Patterns · Fib · Candles', 'ChartSchool Chart Analysis stack'],
  ],
  spurts: [
    ['Live', 'NSE Volume Gainers + BSE Spurt-in-Volume · live LTP'],
    ['Archive', 'EOD flat files in data/spurts_history/ · kept 30 days'],
    ['History', 'Toolbar filter to open any archived day'],
    ['Reappear', 'Dashboard: names on ≥2 days in the last 30'],
  ],
}

export const FOOT = {
  volume: 'Volume · RVOL · OBV · CMF · MFI · research only',
  tech: 'Technical · RSI · MACD · SMA · EMA · research only',
  sci: 'Lab · Donchian · Bollinger · ATR · RVOL · CMF · OBV · research only',
  chart: 'Chart · ChartSchool S/R · trends · gaps · Fib · candles · research only',
  spurts: 'Spurts · live NSE + BSE · 30-day archive · research only',
}

export const SPURT_POLL_MS = 12000
/**
 * Soft poll interval. When a report is already cached on this machine,
 * polling is skipped until Refresh or Clear cache.
 */
export const BOARD_POLL_MS = 120000
