/** NSE/BSE ticker — never use bar date labels. */
export function stockSymbol(row) {
  if (!row || typeof row !== 'object') return ''
  const sym = row.nse || row.id || row.scrip || row.symbol || ''
  return String(sym).trim().toUpperCase()
}

/** Company name from API — ignore date-like `label` fields. */
export function stockName(row) {
  if (!row || typeof row !== 'object') return ''
  const raw = String(row.name || row.company || '').trim()
  if (!raw) return ''
  const sym = stockSymbol(row)
  if (sym && raw.toUpperCase() === sym) return ''
  // Reject values that look like bar dates ("19 Oct", "2024-01-01")
  if (/^\d{1,2}\s+[A-Za-z]{3}/.test(raw) || /^\d{4}-\d{2}-\d{2}/.test(raw)) return ''
  return raw
}

/** Shorter company name for dense tables. */
export function shortCompany(name) {
  if (!name) return ''
  return String(name)
    .replace(/\s+\((NSE|BSE)\)\s*$/i, '')
    .replace(
      /\s+(Limited|Ltd\.?|LLP|PLC|Inc\.?|Corporation|Corp\.?|Company|Co\.?)\s*$/i,
      '',
    )
    .replace(/\s+/g, ' ')
    .trim()
}

export function displayStock(row, { short = true } = {}) {
  const sym = stockSymbol(row)
  const full = stockName(row)
  const name = short ? shortCompany(full) : full
  return { sym, name, full: full || name, title: [sym, full || name].filter(Boolean).join(' · ') }
}

export function rowMatchesQuery(row, query) {
  const q = String(query || '')
    .trim()
    .toLowerCase()
  if (!q) return true
  const { sym, full, name } = displayStock(row, { short: false })
  const hay = [sym, full, name, row.sector, row.exchange, row.scrip]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return hay.includes(q)
}

export function fmtVol(value) {
  const n = Number(value) || 0
  if (n >= 1e7) return (n / 1e7).toFixed(2) + ' Cr'
  if (n >= 1e5) return (n / 1e5).toFixed(2) + ' L'
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'k'
  return String(Math.round(n))
}

export function fmtNum(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return Number(value).toLocaleString('en-IN', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}

export function fmtCompact(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const n = Number(value)
  const sign = n < 0 ? '-' : ''
  const abs = Math.abs(n)
  if (abs >= 1e7) return sign + (abs / 1e7).toFixed(2) + ' Cr'
  if (abs >= 1e5) return sign + (abs / 1e5).toFixed(2) + ' L'
  if (abs >= 1e3) return sign + (abs / 1e3).toFixed(1) + 'k'
  return String(Math.round(n))
}

export function tradingViewUrl(symbol, exchange) {
  let raw = String(symbol || '')
    .trim()
    .toUpperCase()
  // Prefer ticker text over pure BSE numeric scrip codes when possible.
  if (!raw || /^\d+$/.test(raw)) return ''
  const ex = String(exchange || 'NSE').toUpperCase() === 'BSE' ? 'BSE' : 'NSE'
  return 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(ex + ':' + raw)
}

/** Build TradingView chart URL from a board/spurt row. */
export function tradingViewUrlForRow(row) {
  if (!row || typeof row !== 'object') return ''
  const exchange = row.exchange === 'BSE' ? 'BSE' : 'NSE'
  const sym = String(row.nse || row.id || row.symbol || '')
    .trim()
    .toUpperCase()
  if (sym && !/^\d+$/.test(sym)) return tradingViewUrl(sym, exchange)
  return ''
}

export function techDerived(row) {
  const smaStack =
    row.sma20 != null && row.sma50 != null ? (row.sma20 > row.sma50 ? 1 : row.sma20 < row.sma50 ? -1 : 0) : null
  const emaBias =
    row.close != null && row.ema20 != null ? (row.close > row.ema20 ? 1 : row.close < row.ema20 ? -1 : 0) : null
  return { ...row, sma_stack: smaStack, ema_bias: emaBias }
}

export function filterRows(rows, desk, tab, filters = {}) {
  if (!rows) return []
  let out = rows

  if (desk === 'spurts') {
    if (tab === 'nse') out = out.filter((r) => r.exchange === 'NSE')
    else if (tab === 'bse') out = out.filter((r) => r.exchange === 'BSE')
    else if (tab === 'spike') out = out.filter((r) => (r.vol_x || 0) >= 3)
  } else if (desk === 'sci') {
    if (tab === 'bullish' || tab === 'bull')
      out = out.filter((r) => r.pattern === 'bull_breakout' || r.pattern === 'bull_base')
    else if (tab === 'consolidating' || tab === 'coil')
      out = out.filter((r) => r.pattern === 'consolidating' || r.pattern === 'bull_base')
    else if (tab === 'breakout' || tab === 'spike')
      out = out.filter((r) => r.pattern === 'bull_breakout' || r.spike)
  } else if (desk === 'chart') {
    if (tab === 'bullish') out = out.filter((r) => r.bias === 'bullish')
    else if (tab === 'bearish') out = out.filter((r) => r.bias === 'bearish')
    else if (tab === 'breakout')
      out = out.filter((r) => r.setup === 'breakout' || r.break_resistance || r.spike)
    else if (tab === 'support')
      out = out.filter((r) => r.near_support || r.near_resistance || r.fib_zone)
  } else {
    if (tab === 'bullish') out = out.filter((r) => r.bias === 'bullish')
    else if (tab === 'bearish') out = out.filter((r) => r.bias === 'bearish')
    else if (tab === 'spike') out = out.filter((r) => r.spike)
  }

  const {
    nameFilter,
    strengthFilter,
    minRvol,
    minVolX,
    chartPattern,
    chartSetup,
    chartTrend,
    chartGap,
    chartFib,
    chartCandle,
  } = filters
  if (nameFilter) out = out.filter((r) => rowMatchesQuery(r, nameFilter))
  if (desk === 'chart') {
    if (strengthFilter === 'strong') out = out.filter((r) => r.strength === 'strong')
    if (strengthFilter === 'moderate') out = out.filter((r) => r.strength === 'moderate')
  } else {
    if (strengthFilter === 'strong')
      out = out.filter((r) => r.strength === 'strong' || Math.abs(r.score || 0) >= 60)
    if (strengthFilter === 'moderate')
      out = out.filter(
        (r) => r.strength === 'moderate' || (Math.abs(r.score || 0) >= 30 && Math.abs(r.score || 0) < 60),
      )
  }

  if (desk === 'chart') {
    if (chartPattern && chartPattern !== 'all') out = out.filter((r) => (r.pattern || 'none') === chartPattern)
    if (chartSetup && chartSetup !== 'all') out = out.filter((r) => (r.setup || 'mid_range') === chartSetup)
    if (chartTrend === 'valid') out = out.filter((r) => r.trend_valid)
    else if (chartTrend && chartTrend !== 'all') out = out.filter((r) => (r.trend || 'sideways') === chartTrend)
    if (chartGap === 'any') out = out.filter((r) => r.gap && r.gap !== 'none')
    else if (chartGap === 'none') out = out.filter((r) => !r.gap || r.gap === 'none')
    else if (chartGap === 'breakaway') out = out.filter((r) => String(r.gap || '').includes('breakaway'))
    else if (chartGap === 'runaway') out = out.filter((r) => String(r.gap || '').includes('runaway'))
    else if (chartGap === 'exhaustion') out = out.filter((r) => String(r.gap || '').includes('exhaustion'))
    if (chartFib === 'zone') out = out.filter((r) => r.fib_zone)
    else if (chartFib === 'pullback') out = out.filter((r) => r.fib_zone && r.fib_context === 'pullback')
    else if (chartFib === 'bounce') out = out.filter((r) => r.fib_zone && r.fib_context === 'bounce')
    if (chartCandle === 'signal') out = out.filter((r) => r.candle && r.candle !== 'none')
    else if (chartCandle === 'bull')
      out = out.filter((r) => r.candle === 'hammer' || r.candle === 'engulfing_bull')
    else if (chartCandle === 'bear')
      out = out.filter((r) => r.candle === 'shooting_star' || r.candle === 'engulfing_bear')
  }

  const rvolMin = Number(minRvol)
  if (Number.isFinite(rvolMin) && minRvol !== '' && minRvol != null) {
    out = out.filter((r) => (r.rvol || 0) >= rvolMin)
  }
  const volxMin = Number(minVolX)
  if (Number.isFinite(volxMin) && minVolX !== '' && minVolX != null) {
    out = out.filter((r) => (r.vol_x || 0) >= volxMin)
  }

  return out
}
