import { useMemo } from 'react'
import { useDesk } from '../store'
import { displayStock, fmtCompact, fmtNum, fmtVol, sortRowsBy } from '../utils'
import StockLink from './StockLink'

function scoreLabel(score, desk) {
  if (score == null || Number.isNaN(Number(score))) return '—'
  const n = Number(score)
  const body = Number.isInteger(n) ? String(n) : n.toFixed(1)
  // Chart / Lab project 0…100 (mid ~50) — no signed '+' prefix.
  if (desk === 'chart' || desk === 'sci') return body
  return (n > 0 ? '+' : '') + body
}

function Chip({ value }) {
  if (value == null || value === '—') return '—'
  return value
}

function colsForDesk(desk, tfMeta) {
  if (desk === 'tech') {
    // Lead fixed · then ChartSchool KPIs by scan usefulness
    const t = tfMeta?.tech
    return [
      { key: 'nse', label: 'Stock', type: 'text' },
      { key: 'change_pct', label: 'Chg %', type: 'num' },
      { key: 'score', label: 'Score', type: 'num' },
      { key: 'bias', label: 'Bias', type: 'text' },
      { key: 'setup', label: 'Setup', type: 'text' },
      { key: 'rsi', label: t?.rsi != null ? `RSI(${t.rsi})` : 'RSI', type: 'num' },
      { key: 'macd_hist', label: t?.macd != null ? `MACD(${t.macd})` : 'MACD', type: 'num' },
      { key: 'ppo_hist', label: t?.ppo != null ? `PPO(${t.ppo})` : 'PPO', type: 'num' },
      { key: 'sma', label: t?.sma != null ? `SMA(${t.sma})` : 'SMA', type: 'num' },
      { key: 'sma200', label: t?.sma200 != null ? `50/200(${t.sma200})` : '50/200', type: 'num' },
      { key: 'ema', label: t?.ema != null ? `EMA(${t.ema})` : 'EMA', type: 'num' },
      { key: 'stoch_k', label: t?.stoch != null ? `Stoch(${t.stoch})` : 'Stoch', type: 'num' },
      { key: 'adx', label: t?.adx != null ? `ADX(${t.adx})` : 'ADX', type: 'num' },
      { key: 'aroon_osc', label: t?.aroon != null ? `Aroon(${t.aroon})` : 'Aroon', type: 'num' },
      { key: 'bb_pctb', label: t?.bb != null ? `%B(${t.bb})` : '%B', type: 'num' },
      { key: 'roc', label: t?.roc != null ? `ROC(${t.roc})` : 'ROC', type: 'num' },
      { key: 'cci', label: t?.cci != null ? `CCI(${t.cci})` : 'CCI', type: 'num' },
      { key: 'willr', label: t?.willr != null ? `%R(${t.willr})` : '%R', type: 'num' },
      { key: 'atr_pct', label: t?.atr != null ? `ATR%(${t.atr})` : 'ATR%', type: 'num' },
    ]
  }
  if (desk === 'sci') {
    const lab = tfMeta?.lab
    return [
      { key: 'nse', label: 'Stock', type: 'text' },
      { key: 'change_pct', label: 'Chg %', type: 'num' },
      { key: 'pattern', label: 'Pattern', type: 'text' },
      { key: 'bull_score', label: 'Bullish', type: 'num' },
      { key: 'consol_score', label: 'Coil', type: 'num' },
      { key: 'range_pct', label: lab?.donchian != null ? `Range%(${lab.donchian})` : 'Range%', type: 'num' },
      { key: 'rvol', label: lab?.rvol != null ? `RVOL(${lab.rvol})` : 'RVOL', type: 'num' },
      { key: 'cmf', label: lab?.cmf != null ? `CMF(${lab.cmf})` : 'CMF', type: 'num' },
      { key: 'obv_rising', label: lab?.obv != null ? `OBV(${lab.obv})` : 'OBV', type: 'text' },
      { key: 'higher_lows', label: 'HL', type: 'text' },
      { key: 'atr_pct', label: lab?.atr != null ? `ATR%(${lab.atr})` : 'ATR%', type: 'num' },
      { key: 'squeeze', label: lab?.bb != null ? `Squeeze(${lab.bb})` : 'Squeeze', type: 'text' },
    ]
  }
  if (desk === 'chart') {
    // ChartSchool Chart Analysis columns — labels carry scan lookbacks from tf_meta.chart
    const c = tfMeta?.chart
    const rvol = c?.rvol
    const fib = c?.fib_swing
    const touches = c?.trend_touches
    const near = c?.near_pct
    return [
      { key: 'nse', label: 'Stock', type: 'text', title: 'Symbol' },
      { key: 'change_pct', label: 'Chg %', type: 'num', title: 'Session / bar change %' },
      { key: 'close', label: 'Close', type: 'num', title: 'Last close — read Sup, Res, Demand, and Supply against this price' },
      {
        key: 'score',
        label: 'Score',
        type: 'num',
        title: 'Projected 0…100 from ChartSchool edges · ≥60 bull · ≤40 bear · T/P = short history',
      },
      { key: 'bias', label: 'Bias', type: 'text', title: 'bullish ≥60 · bearish ≤40 · else neutral' },
      {
        key: 'high_edge',
        label: 'Edge',
        type: 'text',
        title: 'High when top ChartSchool edge or |Conf|≥3 · hover for edges',
      },
      {
        key: 'confluence',
        label: 'Conf',
        type: 'num',
        title: 'Bull edges − bear edges · |Conf|≥3 Murphy bonus',
      },
      {
        key: 'setup',
        label: 'Setup',
        type: 'text',
        title: 'breakout / breakdown / near support|resistance / fib zone · T/P = thin/partial',
      },
      {
        key: 'support',
        label: 'Sup',
        type: 'num',
        title: 'Nearest swing shelf at or under the close · hover for touches and flip',
      },
      {
        key: 'resistance',
        label: 'Res',
        type: 'num',
        title: 'Nearest swing high at or above the close · 5-bar swings on this chart',
      },
      {
        key: 'dist_support_pct',
        label: 'Dist S%',
        type: 'num',
        title: `% above support · near ≤${near ?? 1.25}%`,
      },
      {
        key: 'dist_resistance_pct',
        label: 'Dist R%',
        type: 'num',
        title: `% below resistance · near ≤${near ?? 1.25}%`,
      },
      {
        key: 'demand',
        label: 'Demand',
        type: 'text',
        title: 'Bottom 20% of this chart — visible-range demand zone',
      },
      {
        key: 'supply',
        label: 'Supply',
        type: 'text',
        title: 'Top 20% of this chart — visible-range supply zone',
      },
      {
        key: 'range_pos_pct',
        label: 'Loc',
        type: 'num',
        title: 'Where the close sits from demand (0) to supply (100). Demand / Supply when price is inside that zone',
      },
      {
        key: 'range_width_pct',
        label: 'S/R%',
        type: 'num',
        title: 'Width between nearest support and resistance · 100×(Res−Sup)/mid',
      },
      {
        key: 'trend',
        label: 'Trend',
        type: 'text',
        title: 'up / down / sideways · hover for validation',
      },
      {
        key: 'trend_touches',
        label: touches != null ? `Touches(≥${touches})` : 'Touches',
        type: 'num',
        title: `Trend-line touches · validated at ≥${touches ?? 3} (2 if thin)`,
      },
      { key: 'higher_lows', label: 'HL', type: 'text', title: 'Higher pivot lows — bullish structure' },
      { key: 'lower_highs', label: 'LH', type: 'text', title: 'Lower pivot highs — bearish structure' },
      {
        key: 'pattern',
        label: 'Pattern',
        type: 'text',
        title: 'rectangle · triangles · double · flag',
      },
      {
        key: 'gap',
        label: 'Gap',
        type: 'text',
        title: `Gap type · breakaway needs RVOL≥${c?.gap_rvol ?? 1.4}× · Gap% on hover`,
      },
      {
        key: 'fib_nearest',
        label: 'Fib',
        type: 'text',
        title: `Nearest Fib on this chart${fib != null ? ` (${fib} bars)` : ''} · highlight ≤1% of 38.2/50/61.8`,
      },
      {
        key: 'candle',
        label: 'Candle',
        type: 'text',
        title: 'Hammer / engulfing / star / doji · quality on hover',
      },
      {
        key: 'rvol',
        label: rvol != null ? `RVOL(${rvol})` : 'RVOL',
        type: 'num',
        title: `V ÷ SMA(prior ${rvol ?? 50}) · confirms gaps/breaks ≥${c?.gap_rvol ?? 1.4}×`,
      },
    ]
  }
  // Priority: fixed lead · then score-weighted volume KPIs · raw volume last
  const vol = tfMeta?.volume
  return [
    { key: 'nse', label: 'Stock', type: 'text' },
    { key: 'change_pct', label: 'Chg %', type: 'num' },
    { key: 'score', label: 'Score', type: 'num' },
    { key: 'bias', label: 'Bias', type: 'text' },
    { key: 'er', label: 'E/R', type: 'text' },
    { key: 'breakout', label: 'Break', type: 'text' },
    { key: 'rvol', label: vol?.rvol != null ? `RVOL(${vol.rvol})` : 'RVOL', type: 'num' },
    { key: 'vol_z', label: vol?.vol_z != null ? `VolZ(${vol.vol_z})` : 'VolZ', type: 'num' },
    { key: 'cmf', label: vol?.cmf != null ? `CMF(${vol.cmf})` : 'CMF', type: 'num' },
    { key: 'mfi', label: vol?.mfi != null ? `MFI(${vol.mfi})` : 'MFI', type: 'num' },
    { key: 'obv_rising', label: vol?.obv_delta != null ? `OBV(${vol.obv_delta})` : 'OBV', type: 'text' },
    { key: 'chaikin', label: vol?.chaikin != null ? `ChOsc(${vol.chaikin})` : 'ChOsc', type: 'num' },
    { key: 'pvo_hist', label: vol?.pvo != null ? `PVO(${vol.pvo})` : 'PVO', type: 'num' },
    { key: 'force', label: vol?.force != null ? `Force(${vol.force})` : 'Force', type: 'num' },
    { key: 'vol_ratio', label: vol?.uv_dv != null ? `UV/DV(${vol.uv_dv})` : 'UV/DV', type: 'num' },
    { key: 'ad', label: vol?.ad_delta != null ? `A/D(${vol.ad_delta})` : 'A/D', type: 'num' },
    { key: 'emv', label: vol?.emv != null ? `EMV(${vol.emv})` : 'EMV', type: 'num' },
    { key: 'vol_osc', label: vol?.vol_osc != null ? `VOsc(${vol.vol_osc})` : 'VOsc', type: 'num' },
    { key: 'vpt', label: 'VPT', type: 'num' },
    { key: 'volume', label: 'Volume', type: 'num' },
  ]
}

function sortValue(row, key, desk) {
  if (key === 'nse') {
    const { sym } = displayStock(row, { short: true })
    return String(sym || row.nse || '').toUpperCase()
  }
  if (key === 'obv_rising') {
    if (row.obv_rising === true) return 1
    if (row.obv_rising === false) return 0
    return null
  }
  if (key === 'setup' && desk === 'tech') {
    const rank = {
      'Trend↑': 5,
      'Momentum↑': 4,
      Oversold: 3,
      Thin: 1,
      Range: 0,
      Overbought: -3,
      'Momentum↓': -4,
      'Trend↓': -5,
    }
    return Object.prototype.hasOwnProperty.call(rank, row.setup) ? rank[row.setup] : null
  }
  if (key === 'er') {
    const rank = {
      'Confirm↑': 6,
      'Confirm↓': -6,
      'Effort↑': 4,
      'Effort↓': -4,
      'Result↑': 3,
      'Result↓': -3,
      NoSupply: 2,
      NoDemand: -2,
      Absorb: 1,
      Fight: 0,
      Clash: 0,
    }
    return Object.prototype.hasOwnProperty.call(rank, row.er) ? rank[row.er] : null
  }
  if (key === 'breakout') {
    const rank = { 'Correct↑': 4, 'Correct↓': -4, 'Weak↑': 2, 'Weak↓': -2, 'False↑': -1, 'False↓': 1 }
    return Object.prototype.hasOwnProperty.call(rank, row.breakout) ? rank[row.breakout] : null
  }
  if (key === 'higher_lows' || key === 'squeeze' || key === 'vol_dry') {
    if (row[key] === true) return 1
    if (row[key] === false) return 0
    return null
  }
  if (key === 'sma') {
    if (row.sma20 == null || row.sma50 == null) return null
    return Number(row.sma20) - Number(row.sma50)
  }
  if (key === 'sma200') {
    if (row.sma50 == null || row.sma200 == null) return null
    return Number(row.sma50) - Number(row.sma200)
  }
  if (key === 'ema') {
    if (row.close == null || row.ema20 == null) return null
    return Number(row.close) - Number(row.ema20)
  }
  if (key === 'pattern' && desk === 'sci') {
    const p = row.pattern || ''
    if (p === 'bull_breakout') return 'Breakout'
    if (p === 'bull_base') return 'Bull base'
    if (p === 'consolidating') return 'Coil'
    return ''
  }
  const v = row[key]
  if (v == null || v === '' || v === 'none') return null
  if (typeof v === 'number') return v
  return String(v).toUpperCase()
}

function cellSpec(row, key, desk) {
  if (key === 'nse') {
    return { node: <StockLink row={row} short showName={false} />, tdClass: 'stock-cell' }
  }

  if (key === 'change_pct') {
    const n = row.change_pct
    if (n == null) return { node: '—', tdClass: '' }
    const tone = n > 0 ? 'up' : n < 0 ? 'down' : 'neutral'
    return {
      node: <Chip value={(n >= 0 ? '+' : '') + fmtNum(n, 1) + '%'} tone={tone} />,
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'score' || key === 'bull_score') {
    const n = row[key]
    let tone = ''
    if (key === 'bull_score') {
      tone = n != null && n >= 45 ? 'up' : ''
    } else if (desk === 'chart' || desk === 'sci') {
      // Projected 0…100 — green ≥60 / red ≤40 (not signed ±).
      tone = n == null ? '' : n >= 60 ? 'up' : n <= 40 ? 'down' : 'neutral'
    } else if (n == null) {
      tone = ''
    } else if (n > 0 || row.bias === 'bullish') {
      tone = 'up'
    } else if (n < 0 || row.bias === 'bearish') {
      tone = 'down'
    } else {
      tone = 'neutral'
    }
    const hist = row.history || (row.partial_history ? 'partial' : null)
    const skip = Array.isArray(row.skipped) && row.skipped.length ? ` · skip ${row.skipped.join(',')}` : ''
    const showHist = desk !== 'spurts' && hist && hist !== 'full'
    const tip = showHist
      ? `${hist} history · ${row.bars_used != null ? row.bars_used + ' bars' : '—'}${
          row.history_need != null ? ` · need ${row.history_need}` : ''
        }${skip}`
      : skip
        ? `skip ${row.skipped.join(',')}`
        : desk === 'chart' && Array.isArray(row.edges) && row.edges.length
          ? row.edges.join(' · ')
          : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={scoreLabel(n, desk)} tone={tone === 'neutral' ? '' : tone} />
          {showHist && hist === 'thin' ? <sup className="hist-tag">T</sup> : null}
          {showHist && hist === 'partial' ? <sup className="hist-tag">P</sup> : null}
        </span>
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'consol_score') {
    return { node: <Chip value={scoreLabel(row.consol_score)} />, tdClass: '' }
  }

  if (key === 'bias') {
    const b = row.bias || '—'
    const tone = b === 'bullish' ? 'bullish' : b === 'bearish' ? 'bearish' : 'neutral'
    return {
      node: <Chip value={b} tone={tone} />,
      tdClass: tone === 'neutral' ? '' : tone === 'bullish' ? 'up' : 'down',
    }
  }

  if (key === 'high_edge') {
    const on = row.high_edge === true
    const tip = Array.isArray(row.edges) && row.edges.length ? row.edges.join(' · ') : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={on ? 'High' : '—'} tone={on ? 'up' : ''} />
        </span>
      ),
      tdClass: on ? 'up' : '',
    }
  }

  if (key === 'confluence') {
    const n = row.confluence
    const tone = n == null ? '' : n >= 2 ? 'up' : n <= -2 ? 'down' : 'neutral'
    const tip = Array.isArray(row.edges) && row.edges.length ? row.edges.join(' · ') : undefined
    return {
      node: (
        <span title={tip}>
          <Chip
            value={n != null ? (n > 0 ? '+' : '') + String(n) : '—'}
            tone={tone === 'neutral' ? '' : tone}
          />
        </span>
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'setup' && desk === 'tech') {
    const v = row.setup || '—'
    const hist = row.history || (row.partial_history ? 'partial' : 'full')
    const tone =
      v === 'Trend↑' || v === 'Momentum↑'
        ? 'up'
        : v === 'Trend↓' || v === 'Momentum↓'
          ? 'down'
          : v === 'Overbought'
            ? 'down'
            : v === 'Oversold' || v === 'Thin'
              ? 'up'
              : 'neutral'
    const tip =
      hist === 'thin'
        ? `Recent listing · ${row.bars_used ?? '—'} bars · periods shrunk`
        : hist === 'partial'
          ? `Partial history · ${row.bars_used ?? '—'} bars · some Signals adapted/skipped`
          : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={v} tone={tone === 'neutral' ? '' : tone} />
        </span>
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'er') {
    const v = row.er || '—'
    const t = row.er_tone || ''
    const td = t === 'bull' ? 'up' : t === 'bear' ? 'down' : t === 'warn' ? 'neutral' : ''
    const tip = [row.effort && `Effort ${row.effort}`, row.result && `Result ${row.result}`, row.spread_x != null && `Spread ${row.spread_x}×`]
      .filter(Boolean)
      .join(' · ')
    return {
      node: <span title={tip || undefined}><Chip value={v} /></span>,
      tdClass: td,
    }
  }

  if (key === 'breakout') {
    const v = row.breakout || '—'
    const q = row.bo_quality
    const td = q === 'correct' ? (row.bo_side === 'down' ? 'down' : 'up') : q === 'false' ? 'down' : q === 'weak' ? 'neutral' : ''
    const tip = row.bo_level != null ? `Level ${row.bo_level}` : undefined
    return {
      node: <span title={tip}><Chip value={v} /></span>,
      tdClass: td,
    }
  }

  if (key === 'rvol') {
    const n = row.rvol
    const tone = n != null && n >= 1.5 ? 'up' : ''
    const tip =
      row.periods?.rvol != null
        ? `RVOL(${row.periods.rvol}) · V ÷ SMA(prior bars) · current excluded`
        : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={n != null ? n.toFixed(1) + '×' : '—'} tone={tone} />
        </span>
      ),
      tdClass: tone,
    }
  }

  if (key === 'vol_z') {
    const n = row.vol_z
    const tone = n == null ? '' : n >= 2 ? 'up' : n <= -1 ? 'down' : 'neutral'
    return {
      node: <Chip value={n != null ? (n >= 0 ? '+' : '') + n.toFixed(1) + 'σ' : '—'} tone={tone === 'neutral' ? '' : tone} />,
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'force' || key === 'emv' || key === 'vol_osc' || key === 'chaikin' || key === 'pvo_hist') {
    const n = row[key]
    const tone = n == null ? '' : n > 0 ? 'up' : n < 0 ? 'down' : 'neutral'
    let label = '—'
    if (n != null) {
      if (key === 'force' || key === 'chaikin') label = fmtCompact(n)
      else if (key === 'emv') label = Number(n).toFixed(2)
      else if (key === 'pvo_hist') label = (n >= 0 ? '+' : '') + Number(n).toFixed(1)
      else label = Number(n).toFixed(1) + '%'
    }
    return {
      node: <Chip value={label} tone={tone === 'neutral' ? '' : tone} />,
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'vol_ratio') {
    const n = row.vol_ratio
    const tone = n == null ? '' : n >= 1.2 ? 'up' : n <= 0.83 ? 'down' : 'neutral'
    return {
      node: <Chip value={n != null ? n.toFixed(2) : '—'} tone={tone === 'neutral' ? '' : tone} />,
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'obv_rising') {
    const v = row.obv_rising
    const label = v === true ? '↑' : v === false ? '↓' : '—'
    const tone = v === true ? 'up' : v === false ? 'down' : ''
    return { node: <Chip value={label} tone={tone} />, tdClass: tone }
  }

  if (key === 'higher_lows' || key === 'lower_highs' || key === 'squeeze' || key === 'vol_dry') {
    const v = row[key]
    const label = v === true ? 'Yes' : v === false ? 'No' : '—'
    const tip =
      key === 'squeeze' && row.periods
        ? `BB(${row.periods.bb}) · ATR(${row.periods.atr}) on adapted lookback`
        : key === 'higher_lows' && (row.periods?.hl != null || row.periods?.trend_touches != null)
          ? `Higher pivot lows · need ${row.periods.hl ?? row.periods.trend_touches}`
          : key === 'lower_highs' && row.periods?.trend_touches != null
            ? `Lower pivot highs · need ${row.periods.trend_touches}`
            : undefined
    const tone = v === true ? (key === 'lower_highs' ? 'down' : 'up') : ''
    return {
      node: (
        <span title={tip}>
          <Chip value={label} tone={tone} />
        </span>
      ),
      tdClass: tone,
    }
  }

  if (key === 'ad') {
    if (row.ad_rising === true) return { node: '↑', tdClass: 'up' }
    if (row.ad_rising === false) return { node: '↓', tdClass: 'down' }
    return { node: row.ad != null ? fmtCompact(row.ad) : '—', tdClass: '' }
  }

  if (key === 'vpt') {
    return { node: row.vpt != null ? fmtCompact(row.vpt) : '—', tdClass: '' }
  }

  if (key === 'cmf') {
    const n = row.cmf
    const tone = n == null ? '' : n > 0 ? 'up' : n < 0 ? 'down' : 'neutral'
    const tip = row.periods?.cmf != null ? `CMF(${row.periods.cmf})` : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={n != null ? n.toFixed(2) : '—'} tone={tone === 'neutral' ? '' : tone} />
        </span>
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'mfi' || key === 'rsi') {
    const n = row[key]
    const tone = n == null ? '' : n >= 55 ? 'up' : n <= 45 ? 'down' : 'neutral'
    return {
      node: <Chip value={n != null ? Number(n).toFixed(0) : '—'} tone={tone} />,
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'stoch_k') {
    const n = row.stoch_k
    const tone = n == null ? '' : n >= 50 ? 'up' : n < 50 ? 'down' : 'neutral'
    return {
      node: <Chip value={n != null ? Number(n).toFixed(0) : '—'} tone={tone === 'neutral' ? '' : tone} />,
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'adx') {
    const n = row.adx
    const diUp = row.plus_di != null && row.minus_di != null && row.plus_di > row.minus_di
    const diDn = row.plus_di != null && row.minus_di != null && row.plus_di < row.minus_di
    const tone = n == null ? '' : n >= 25 ? (diUp ? 'up' : diDn ? 'down' : 'neutral') : 'neutral'
    const tip =
      row.plus_di != null && row.minus_di != null
        ? `+DI ${row.plus_di} · −DI ${row.minus_di}`
        : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={n != null ? Number(n).toFixed(0) : '—'} tone={tone === 'neutral' ? '' : tone} />
        </span>
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'bb_pctb') {
    const n = row.bb_pctb
    const tone = n == null ? '' : n >= 0.8 ? 'up' : n <= 0.2 ? 'down' : 'neutral'
    return {
      node: <Chip value={n != null ? Number(n).toFixed(2) : '—'} tone={tone === 'neutral' ? '' : tone} />,
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'roc') {
    const n = row.roc
    const tone = n == null ? '' : n > 0 ? 'up' : n < 0 ? 'down' : 'neutral'
    return {
      node: (
        <Chip
          value={n != null ? (n >= 0 ? '+' : '') + Number(n).toFixed(1) + '%' : '—'}
          tone={tone === 'neutral' ? '' : tone}
        />
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'cci') {
    const n = row.cci
    const tone = n == null ? '' : n > 0 ? 'up' : n < 0 ? 'down' : 'neutral'
    return {
      node: <Chip value={n != null ? Number(n).toFixed(0) : '—'} tone={tone === 'neutral' ? '' : tone} />,
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'willr') {
    const n = row.willr
    const tone = n == null ? '' : n >= -50 ? 'up' : 'down'
    return {
      node: <Chip value={n != null ? Number(n).toFixed(0) : '—'} tone={tone} />,
      tdClass: tone,
    }
  }

  if (key === 'atr_pct') {
    const n = row.atr_pct
    const tip = row.periods?.atr != null ? `ATR(${row.periods.atr})/Close %` : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={n != null ? Number(n).toFixed(2) + '%' : '—'} />
        </span>
      ),
      tdClass: '',
    }
  }

  if (key === 'macd_hist' || key === 'ppo_hist') {
    const n = row[key]
    const tone = n == null ? '' : n > 0 ? 'up' : n < 0 ? 'down' : 'neutral'
    return {
      node: <Chip value={n != null ? Number(n).toFixed(key === 'ppo_hist' ? 3 : 2) : '—'} tone={tone} />,
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'aroon_osc') {
    const n = row.aroon_osc
    const tip =
      row.aroon_up != null && row.aroon_down != null
        ? `Up ${row.aroon_up} · Down ${row.aroon_down}`
        : undefined
    const tone = n == null ? '' : n >= 50 ? 'up' : n <= -50 ? 'down' : n > 0 ? 'up' : n < 0 ? 'down' : 'neutral'
    return {
      node: (
        <span title={tip}>
          <Chip value={n != null ? Number(n).toFixed(0) : '—'} tone={tone === 'neutral' ? '' : tone} />
        </span>
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'volume') {
    return { node: fmtVol(row.volume), tdClass: '' }
  }

  if (key === 'range_pct') {
    const n = row.range_pct
    const tone = n != null && n <= 12 ? 'up' : ''
    const tip =
      row.periods?.donchian != null
        ? `Donchian(${row.periods.donchian}) · 100×(prior HH−LL)/mid`
        : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={n != null ? n.toFixed(1) : '—'} tone={tone} />
        </span>
      ),
      tdClass: tone,
    }
  }

  if (key === 'close') {
    const n = row.close
    return {
      node: <Chip value={n != null ? fmtNum(n) : '—'} />,
      tdClass: '',
    }
  }

  if (key === 'range_pos_pct') {
    const n = row.range_pos_pct
    const where = row.at_demand ? 'Demand' : row.at_supply ? 'Supply' : n != null ? `Mid ${n.toFixed(0)}%` : '—'
    const tone = row.at_demand ? 'up' : row.at_supply ? 'down' : ''
    const tip = n != null ? `Close is ${n.toFixed(0)}% of the way from demand to supply` : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={where} tone={tone} />
        </span>
      ),
      tdClass: tone,
    }
  }

  if (key === 'support' || key === 'resistance') {
    const n = row[key]
    const isSup = key === 'support'
    const touches = isSup ? row.support_touches : row.resistance_touches
    const from = isSup ? row.support_from : row.resistance_from
    const tip =
      row.periods?.sr != null
        ? [
            isSup ? 'Support ≤ close' : 'Resistance ≥ close',
            from === 'flip' ? 'flipped S⇄R' : from === 'range' ? 'range extreme' : 'swing zone',
            touches != null ? `${touches} touch${touches === 1 ? '' : 'es'}` : null,
            `look ${row.periods.sr_look}`,
          ]
            .filter(Boolean)
            .join(' · ')
        : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={n != null ? fmtNum(n) : '—'} />
        </span>
      ),
      tdClass: '',
    }
  }

  if (key === 'demand' || key === 'supply') {
    const lo = key === 'demand' ? row.demand_lo : row.supply_lo
    const hi = key === 'demand' ? row.demand_hi : row.supply_hi
    const on = key === 'demand' ? row.at_demand : row.at_supply
    const label = lo != null && hi != null ? `${fmtNum(lo)}–${fmtNum(hi)}` : '—'
    const tip = on ? `Close is on this ${key} zone` : `Visible-range ${key} of the selected chart`
    return {
      node: (
        <span title={tip}>
          <Chip value={label} tone={on ? (key === 'demand' ? 'up' : 'down') : ''} />
        </span>
      ),
      tdClass: on ? (key === 'demand' ? 'up' : 'down') : '',
    }
  }

  if (key === 'dist_support_pct' || key === 'dist_resistance_pct') {
    const n = row[key]
    const nearLim = row.periods?.near_pct ?? 1.25
    const near = n != null && n <= nearLim
    const tone = near ? (key === 'dist_support_pct' ? 'up' : 'down') : ''
    const tip = near ? `Near · ≤${nearLim}%` : `Dist · near ≤${nearLim}%`
    return {
      node: (
        <span title={tip}>
          <Chip value={n != null ? n.toFixed(2) + '%' : '—'} tone={tone} />
        </span>
      ),
      tdClass: tone,
    }
  }

  if (key === 'range_width_pct') {
    const n = row.range_width_pct
    const tip =
      row.periods?.sr_look != null
        ? `S/R range width · look ${row.periods.sr_look} · base ${row.periods.sr}`
        : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={n != null ? n.toFixed(1) : '—'} />
        </span>
      ),
      tdClass: '',
    }
  }

  if (key === 'trend_touches') {
    const n = row.trend_touches
    const need = row.periods?.trend_touches
    const valid = row.trend_valid
    const tip = [valid ? 'validated' : 'unvalidated', need != null ? `need ≥${need}` : null]
      .filter(Boolean)
      .join(' · ')
    return {
      node: (
        <span title={tip || undefined}>
          <Chip value={n != null ? String(n) : '—'} tone={valid ? 'up' : ''} />
        </span>
      ),
      tdClass: valid ? 'up' : '',
    }
  }

  if (key === 'fib_nearest') {
    const tone = row.fib_zone ? 'up' : ''
    const tip = [
      row.fib_context,
      row.fib_dist_pct != null ? `${row.fib_dist_pct}% away` : null,
      row.periods?.fib_swing != null ? `swing ${row.periods.fib_swing}` : null,
    ]
      .filter(Boolean)
      .join(' · ')
    return {
      node: (
        <span title={tip || undefined}>
          <Chip value={row.fib_nearest != null ? row.fib_nearest + '%' : '—'} tone={tone} />
        </span>
      ),
      tdClass: tone,
    }
  }

  if (key === 'setup') {
    const v = row.setup || '—'
    const tone =
      v === 'breakout'
        ? 'up'
        : v === 'breakdown'
          ? 'down'
          : v === 'near_support' || v === 'fib_zone'
            ? 'up'
            : v === 'near_resistance'
              ? 'down'
              : 'neutral'
    const label = v && v !== 'none' ? String(v).replace(/_/g, ' ') : '—'
    const hist = row.history || (row.partial_history ? 'partial' : null)
    const tip =
      desk === 'chart' && row.periods
        ? [
            `S/R ${row.periods.sr} · look ${row.periods.sr_look}/${row.periods.preferred_look ?? '—'} · near≤${row.periods.near_pct}%`,
            row.periods.adapted || hist === 'thin' || hist === 'partial'
              ? `adapted to ${row.periods.available ?? row.bars_used ?? '—'} bars (${hist || 'short'})`
              : null,
          ]
            .filter(Boolean)
            .join(' · ')
        : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={label} tone={tone === 'neutral' ? '' : tone} />
          {desk === 'chart' && hist === 'thin' ? <sup className="hist-tag">T</sup> : null}
          {desk === 'chart' && hist === 'partial' ? <sup className="hist-tag">P</sup> : null}
        </span>
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'trend') {
    const v = row.trend || '—'
    const tone = v === 'up' ? 'up' : v === 'down' ? 'down' : 'neutral'
    const tip =
      desk === 'chart'
        ? [
            row.trend_valid ? 'validated' : 'unvalidated',
            row.trend_touches != null ? `${row.trend_touches} touches` : null,
            row.periods?.trend_touches != null ? `need ≥${row.periods.trend_touches}` : null,
          ]
            .filter(Boolean)
            .join(' · ') || undefined
        : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={v} tone={tone === 'neutral' ? '' : tone} />
        </span>
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'gap') {
    const raw = row.gap || 'none'
    const label =
      raw === 'none'
        ? '—'
        : String(raw).replace(/_/g, ' ').replace('up ', '↑').replace('down ', '↓')
    const tone = String(raw).startsWith('up') ? 'up' : String(raw).startsWith('down') ? 'down' : ''
    const tip =
      desk === 'chart' && row.periods?.gap_rvol != null
        ? `Gap · RVOL≥${row.periods.gap_rvol}× (prior ${row.periods.rvol})${
            row.gap_pct != null ? ` · ${row.gap_pct}%` : ''
          }`
        : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={label} tone={tone} />
        </span>
      ),
      tdClass: tone,
    }
  }

  if (key === 'candle') {
    const raw = row.candle || 'none'
    const label = raw === 'none' ? '—' : String(raw).replace(/_/g, ' ')
    const tone =
      raw.includes('hammer') || raw.includes('bull')
        ? 'up'
        : raw.includes('star') || raw.includes('bear')
          ? 'down'
          : raw === 'doji'
            ? 'neutral'
            : ''
    const tip =
      row.candle_quality && row.candle_quality !== raw
        ? `Quality ${String(row.candle_quality).replace(/_/g, ' ')}`
        : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={label} tone={tone === 'neutral' ? '' : tone} />
        </span>
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'pattern') {
    const p = row.pattern || 'none'
    let label = '—'
    let tone = ''
    if (desk === 'sci') {
      if (p === 'bull_breakout') {
        label = 'Breakout'
        tone = 'up'
      } else if (p === 'bull_base') {
        label = 'Bull base'
        tone = 'up'
      } else if (p === 'consolidating') {
        label = 'Coil'
        tone = 'neutral'
      }
    } else if (p !== 'none') {
      label = String(p).replace(/_/g, ' ')
      if (desk === 'chart' && row.pattern_confirmed) label += ' ✓'
      if (label.includes('bull') || label.includes('asc') || label.includes('bottom')) tone = 'up'
      else if (label.includes('bear') || label.includes('desc') || label.includes('top')) tone = 'down'
    }
    const tip =
      desk === 'sci' && row.periods
        ? `D${row.periods.donchian} · R${row.periods.rvol} · CMF${row.periods.cmf} · BB(${row.periods.bb}) · ATR${row.periods.atr}`
        : desk === 'chart' && p && p !== 'none'
          ? [row.pattern_role && row.pattern_role !== 'none' ? row.pattern_role : null, row.pattern_confirmed ? 'confirmed break' : 'forming']
              .filter(Boolean)
              .join(' · ')
          : undefined
    return {
      node: (
        <span title={tip}>
          <Chip value={label} tone={tone === 'neutral' ? '' : tone} />
        </span>
      ),
      tdClass: tone === 'neutral' ? '' : tone,
    }
  }

  if (key === 'sma') {
    const a = row.sma20
    const b = row.sma50
    if (a == null || b == null) return { node: <Chip value="—" />, tdClass: '' }
    if (a > b) return { node: <Chip value="20>50" tone="up" />, tdClass: 'up' }
    if (a < b) return { node: <Chip value="20<50" tone="down" />, tdClass: 'down' }
    return { node: <Chip value="flat" tone="neutral" />, tdClass: '' }
  }

  if (key === 'sma200') {
    const a = row.sma50
    const b = row.sma200
    if (a == null || b == null)
      return { node: <span title="Needs ≥200 bars"><Chip value="—" /></span>, tdClass: '' }
    if (a > b) return { node: <Chip value="Gold" tone="up" />, tdClass: 'up' }
    if (a < b) return { node: <Chip value="Death" tone="down" />, tdClass: 'down' }
    return { node: <Chip value="flat" tone="neutral" />, tdClass: '' }
  }

  if (key === 'ema') {
    if (row.close == null || row.ema20 == null) return { node: <Chip value="—" />, tdClass: '' }
    if (row.close > row.ema20) return { node: <Chip value="above" tone="up" />, tdClass: 'up' }
    if (row.close < row.ema20) return { node: <Chip value="below" tone="down" />, tdClass: 'down' }
    return { node: <Chip value="at" tone="neutral" />, tdClass: '' }
  }

  const v = row[key]
  if (v == null) return { node: '—', tdClass: '' }
  if (typeof v === 'number') return { node: fmtCompact(v), tdClass: '' }
  return { node: String(v), tdClass: '' }
}

function rowTone(row, desk) {
  if (desk === 'sci') {
    const p = row.pattern || ''
    if (p === 'bull_breakout' || p === 'bull_base') return 'is-bullish'
    return ''
  }
  if (desk === 'chart') {
    if (row.setup === 'breakout' || row.setup === 'near_support' || row.setup === 'fib_zone') return 'is-bullish'
    if (row.setup === 'breakdown' || row.setup === 'near_resistance') return 'is-bearish'
    return ''
  }
  if (row.bias === 'bullish') return 'is-bullish'
  if (row.bias === 'bearish') return 'is-bearish'
  return ''
}

export default function ScanTable({ rows }) {
  const desk = useDesk((s) => s.desk)
  const board = useDesk((s) => s.board)
  const openSymbol = useDesk((s) => s.openSymbol)
  const sortKey = useDesk((s) => s.sortKey)
  const sortDir = useDesk((s) => s.sortDir)
  const setSort = useDesk((s) => s.setSort)
  const tfMeta = board?.tf_meta
  const cols = useMemo(() => colsForDesk(desk, tfMeta), [desk, tfMeta])

  const sorted = useMemo(() => {
    const active = cols.find((c) => c.key === sortKey) || cols.find((c) => c.key === 'score') || cols[0]
    return sortRowsBy(rows, active.key, sortDir, (row) => sortValue(row, active.key, desk))
  }, [rows, cols, sortKey, sortDir, desk])

  return (
    <div className="tape scan-tape" tabIndex={0} role="region" aria-label="Scan table — scroll sideways for more columns">
      <table>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c.key} className={c.key === 'nse' ? 'stock' : c.type === 'num' ? 'num' : ''}>
                <button
                  type="button"
                  className={'sort-btn' + (sortKey === c.key ? ' is-on' : '')}
                  onClick={() => setSort(c.key, c.type)}
                  title={c.title || `Sort by ${c.label}`}
                >
                  {c.label}
                  {sortKey === c.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const clickable = Boolean(row.sc_id || row.nse)
            return (
              <tr
                key={(row.nse || '') + (row.sc_id || '') + (row.setup || row.pattern || '')}
                className={rowTone(row, desk) + (clickable ? ' is-clickable' : '')}
                onClick={() => {
                  if (clickable) openSymbol(row)
                }}
              >
                {cols.map((c) => {
                  const { node, tdClass } = cellSpec(row, c.key, desk)
                  const cls = [tdClass, c.type === 'num' ? 'num' : ''].filter(Boolean).join(' ')
                  return (
                    <td key={c.key} className={cls || undefined}>
                      {node}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
