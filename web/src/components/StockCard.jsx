import { displayStock, fmtCompact, fmtNum, fmtVol, stockSymbol } from '../utils'
import { tradingViewUrl } from '../utils'
import { useDesk } from '../store'
import Sparkline from './Sparkline'

function toneClass(row, desk) {
  if (desk === 'spurts') {
    if ((row.change_pct || 0) < 0) return 'tone-bear'
    const x = row.vol_x || 0
    if (x >= 5) return 'tone-spike'
    if (x >= 3) return 'tone-bull'
    return 'tone-neutral'
  }
  if (desk === 'sci') {
    const p = row.pattern || 'none'
    if (p === 'bull_breakout') return 'tone-spike'
    if (p === 'bull_base') return 'tone-bull'
    if (p === 'consolidating') return 'tone-neutral'
    return 'tone-neutral'
  }
  if (desk === 'chart') {
    const s = row.setup || 'mid_range'
    if (s === 'breakout') return 'tone-spike'
    if (s === 'near_support' || s === 'fib_zone') return 'tone-bull'
    if (s === 'breakdown') return 'tone-bear-strong'
    if (s === 'near_resistance') return 'tone-bear'
    return 'tone-neutral'
  }
  const bias = row.bias || 'neutral'
  const score = Math.abs(Number(row.score) || 0)
  if (bias === 'bullish') return score >= 60 ? 'tone-bull-strong' : 'tone-bull'
  if (bias === 'bearish') return score >= 60 ? 'tone-bear-strong' : 'tone-bear'
  return 'tone-neutral'
}

function scoreLabel(score, desk) {
  if (score == null || Number.isNaN(Number(score))) return '—'
  const n = Number(score)
  const body = Number.isInteger(n) ? String(n) : n.toFixed(1)
  if (desk === 'chart' || desk === 'sci') return body
  return (n > 0 ? '+' : '') + body
}

function histTag(row) {
  const hist = row.history || (row.partial_history ? 'partial' : null)
  if (!hist || hist === 'full') return ''
  return hist === 'thin' ? ' T' : ' P'
}

function scoreWithHistory(row, valueKey = 'score', desk) {
  return scoreLabel(row[valueKey], desk) + histTag(row)
}

/** Color Chg by %: up / down / flat */
function chgTone(changePct) {
  if (changePct == null || Number.isNaN(Number(changePct))) return ''
  const n = Number(changePct)
  if (n > 0) return 'chg-up'
  if (n < 0) return 'chg-down'
  return 'chg-flat'
}

function metrics(row, desk) {
  if (desk === 'spurts') {
    return [
      { key: 'Score', value: scoreLabel(row.score), tone: row.score == null ? '' : row.score >= 0 ? 'pos' : 'neg' },
      {
        key: 'Vol×',
        value: row.vol_x != null ? row.vol_x.toFixed(1) + '×' : '—',
        tone: row.vol_x != null && row.vol_x >= 3 ? 'pos' : '',
      },
    ]
  }
  if (desk === 'sci') {
    const pattern = row.pattern || 'none'
    const patternLabel =
      pattern === 'bull_breakout'
        ? 'Breakout'
        : pattern === 'bull_base'
          ? 'Bull base'
          : pattern === 'consolidating'
            ? 'Coil'
            : '—'
    return [
      {
        key: 'Pattern',
        value: patternLabel,
        tone: pattern.startsWith('bull') ? 'pos' : pattern === 'consolidating' ? '' : '',
      },
      {
        key: 'Bullish',
        value: row.bull_score != null ? Number(row.bull_score).toFixed(0) + histTag(row) : '—',
        tone: row.bull_score != null && row.bull_score >= 45 ? 'pos' : '',
      },
      {
        key: 'Coil',
        value: row.consol_score != null ? Number(row.consol_score).toFixed(0) : '—',
      },
      {
        key: 'Range%',
        value: row.range_pct != null ? row.range_pct.toFixed(1) : '—',
        tone: row.range_pct != null && row.range_pct <= 12 ? 'pos' : '',
      },
      {
        key: 'RVOL',
        value: row.rvol != null ? row.rvol.toFixed(1) + '×' : '—',
        tone: row.rvol != null && row.rvol >= 1.5 ? 'pos' : '',
      },
      {
        key: 'CMF',
        value: row.cmf != null ? row.cmf.toFixed(2) : '—',
        tone: row.cmf == null ? '' : row.cmf > 0 ? 'pos' : row.cmf < 0 ? 'neg' : '',
      },
      {
        key: 'OBV',
        value: row.obv_rising === true ? '↑' : row.obv_rising === false ? '↓' : '—',
        tone: row.obv_rising === true ? 'pos' : row.obv_rising === false ? 'neg' : '',
      },
      {
        key: 'HL',
        value: row.higher_lows === true ? 'Yes' : row.higher_lows === false ? 'No' : '—',
        tone: row.higher_lows === true ? 'pos' : '',
      },
      {
        key: 'ATR%',
        value: row.atr_pct != null ? Number(row.atr_pct).toFixed(2) + '%' : '—',
      },
      {
        key: 'Squeeze',
        value: row.squeeze === true ? 'Yes' : row.squeeze === false ? 'No' : '—',
        tone: row.squeeze === true ? 'pos' : '',
      },
      {
        key: 'Lookback',
        value: row.periods
          ? `D${row.periods.donchian}·R${row.periods.rvol}`
          : row.history && row.history !== 'full'
            ? row.history
            : '—',
      },
    ]
  }
  if (desk === 'chart') {
    const pattern = (row.pattern || 'none').replace(/_/g, ' ')
    const gap = (row.gap || 'none').replace(/_/g, ' ')
    const candle = (row.candle || 'none').replace(/_/g, ' ')
    const setup = (row.setup || '—').replace(/_/g, ' ')
    return [
      {
        key: 'Score',
        value: scoreWithHistory(row, 'score', 'chart'),
        tone: row.score == null ? '' : row.score >= 60 ? 'pos' : row.score <= 40 ? 'neg' : '',
      },
      {
        key: 'Edge',
        value: row.high_edge ? 'High' : '—',
        tone: row.high_edge ? 'pos' : '',
      },
      {
        key: 'Conf',
        value: row.confluence != null ? (row.confluence > 0 ? '+' : '') + String(row.confluence) : '—',
        tone: row.confluence != null && row.confluence >= 2 ? 'pos' : row.confluence != null && row.confluence <= -2 ? 'neg' : '',
      },
      {
        key: 'Setup',
        value: setup,
        tone:
          setup === 'breakout' || setup === 'near support' || setup === 'fib zone'
            ? 'pos'
            : setup === 'breakdown' || setup === 'near resistance'
              ? 'neg'
              : '',
      },
      {
        key: 'Support',
        value: row.support != null ? fmtNum(row.support) : '—',
        tone: row.near_support ? 'pos' : '',
      },
      {
        key: 'Resist',
        value: row.resistance != null ? fmtNum(row.resistance) : '—',
        tone: row.near_resistance ? 'neg' : '',
      },
      {
        key: 'Loc',
        value: row.at_demand
          ? 'Demand'
          : row.at_supply
            ? 'Supply'
            : row.range_pos_pct != null
              ? `Mid ${Number(row.range_pos_pct).toFixed(0)}%`
              : '—',
        tone: row.at_demand ? 'pos' : row.at_supply ? 'neg' : '',
      },
      {
        key: 'Trend',
        value: row.trend || '—',
        tone: row.trend === 'up' ? 'pos' : row.trend === 'down' ? 'neg' : '',
      },
      {
        key: 'Pattern',
        value: pattern === 'none' ? '—' : pattern,
        tone: pattern.includes('bull') || pattern.includes('asc') || pattern.includes('bottom') ? 'pos' : '',
      },
      {
        key: 'Gap',
        value: gap === 'none' ? '—' : gap.replace('up ', '↑').replace('down ', '↓'),
        tone: gap.startsWith('up') ? 'pos' : gap.startsWith('down') ? 'neg' : '',
      },
      {
        key: 'Fib',
        value: row.fib_nearest ? row.fib_nearest + '%' : '—',
        tone: row.fib_zone ? 'pos' : '',
      },
      {
        key: 'Candle',
        value: candle === 'none' ? '—' : candle,
        tone:
          candle.includes('hammer') || candle.includes('bull')
            ? 'pos'
            : candle.includes('star') || candle.includes('bear')
              ? 'neg'
              : '',
      },
      {
        key: 'RVOL',
        value: row.rvol != null ? Number(row.rvol).toFixed(1) + '×' : '—',
        tone: row.rvol != null && row.rvol >= 1.4 ? 'pos' : '',
      },
      {
        key: 'Lookback',
        value: row.periods
          ? row.periods.adapted
            ? `${row.periods.available || row.bars_used || '?'}b·S${row.periods.sr}·L${row.periods.sr_look}`
            : `S${row.periods.sr}·L${row.periods.sr_look}·R${row.periods.rvol}`
          : row.history && row.history !== 'full'
            ? row.history
            : '—',
      },
    ]
  }
  if (desk === 'tech') {
    const sma20 = row.sma20
    const sma50 = row.sma50
    let smaLabel = '—'
    let smaTone = ''
    if (sma20 != null && sma50 != null) {
      if (sma20 > sma50) {
        smaLabel = '20>50'
        smaTone = 'pos'
      } else if (sma20 < sma50) {
        smaLabel = '20<50'
        smaTone = 'neg'
      } else {
        smaLabel = 'flat'
      }
    }
    const close = row.close
    const ema20 = row.ema20
    let emaLabel = '—'
    let emaTone = ''
    if (close != null && ema20 != null) {
      if (close > ema20) {
        emaLabel = 'above'
        emaTone = 'pos'
      } else if (close < ema20) {
        emaLabel = 'below'
        emaTone = 'neg'
      } else {
        emaLabel = 'at'
      }
    }
    const hist = row.macd_hist
    return [
      {
        key: 'Score',
        value: scoreWithHistory(row, 'score', 'tech'),
        tone: row.score == null ? '' : row.score >= 0 ? 'pos' : 'neg',
      },
      {
        key: 'RSI',
        value: row.rsi != null ? row.rsi.toFixed(0) : '—',
        tone: row.rsi == null ? '' : row.rsi >= 55 ? 'pos' : row.rsi <= 45 ? 'neg' : '',
      },
      {
        key: 'MACD',
        value: hist != null ? hist.toFixed(2) : '—',
        tone: hist == null ? '' : hist > 0 ? 'pos' : hist < 0 ? 'neg' : '',
      },
      { key: 'SMA', value: smaLabel, tone: smaTone },
      { key: 'EMA', value: emaLabel, tone: emaTone },
    ]
  }

  // Volume desk — ChartSchool stack + Force / EMV / VolZ (Chg % by symbol)
  return [
    {
      key: 'Score',
      value: scoreWithHistory(row, 'score', 'volume'),
      tone: row.score == null ? '' : row.score >= 0 ? 'pos' : 'neg',
    },
    {
      key: 'RVOL',
      value: row.rvol != null ? row.rvol.toFixed(1) + '×' : '—',
      tone: row.rvol != null && row.rvol >= 1.5 ? 'pos' : row.rvol != null && row.rvol < 0.8 ? 'neg' : '',
    },
    {
      key: 'VolZ',
      value: row.vol_z != null ? ((row.vol_z >= 0 ? '+' : '') + row.vol_z.toFixed(1) + 'σ') : '—',
      tone: row.vol_z != null && row.vol_z >= 2 ? 'pos' : row.vol_z != null && row.vol_z <= -1 ? 'neg' : '',
    },
    {
      key: 'CMF',
      value: row.cmf != null ? row.cmf.toFixed(2) : '—',
      tone: row.cmf == null ? '' : row.cmf >= 0 ? 'pos' : 'neg',
    },
    {
      key: 'MFI',
      value: row.mfi != null ? row.mfi.toFixed(0) : '—',
      tone: row.mfi == null ? '' : row.mfi >= 55 ? 'pos' : row.mfi <= 45 ? 'neg' : '',
    },
    {
      key: 'Force',
      value: row.force != null ? fmtCompact(row.force) : '—',
      tone: row.force == null ? '' : row.force > 0 ? 'pos' : row.force < 0 ? 'neg' : '',
    },
    {
      key: 'EMV',
      value: row.emv != null ? row.emv.toFixed(2) : '—',
      tone: row.emv == null ? '' : row.emv > 0 ? 'pos' : row.emv < 0 ? 'neg' : '',
    },
    {
      key: 'VOsc',
      value: row.vol_osc != null ? row.vol_osc.toFixed(1) + '%' : '—',
      tone: row.vol_osc == null ? '' : row.vol_osc > 0 ? 'pos' : row.vol_osc < 0 ? 'neg' : '',
    },
    {
      key: 'UV/DV',
      value: row.vol_ratio != null ? row.vol_ratio.toFixed(2) : '—',
      tone: row.vol_ratio == null ? '' : row.vol_ratio >= 1.2 ? 'pos' : row.vol_ratio < 0.8 ? 'neg' : '',
    },
    {
      key: 'OBV',
      value: row.obv_rising === true ? '↑' : row.obv_rising === false ? '↓' : '—',
      tone: row.obv_rising === true ? 'pos' : row.obv_rising === false ? 'neg' : '',
    },
    {
      key: 'A/D',
      value:
        row.ad_rising === true ? '↑' : row.ad_rising === false ? '↓' : row.ad != null ? fmtCompact(row.ad) : '—',
      tone: row.ad_rising === true ? 'pos' : row.ad_rising === false ? 'neg' : '',
    },
    { key: 'VPT', value: row.vpt != null ? fmtCompact(row.vpt) : '—' },
  ]
}

export default function StockCard({ row }) {
  const desk = useDesk((s) => s.desk)
  const openSymbol = useDesk((s) => s.openSymbol)
  const sym = stockSymbol(row)
  const { title } = displayStock(row, { short: true })
  const tone = toneClass(row, desk)
  const tv = tradingViewUrl(sym, row.exchange === 'BSE' ? 'BSE' : 'NSE')
  const clickable = Boolean(row.sc_id || (row.nse && desk !== 'spurts'))
  const items = metrics(row, desk)
  const dense = desk === 'volume' || desk === 'tech' || desk === 'sci' || desk === 'chart'

  return (
    <article
      className={
        'stock-box ' +
        tone +
        (clickable ? ' is-clickable' : '') +
        (dense ? ' is-dense' : '') +
        (desk === 'tech' ? ' is-tech' : '') +
        (desk === 'sci' || desk === 'chart' ? ' is-lab' : '')
      }
      title={title}
      onClick={() => {
        if (clickable) openSymbol(row)
      }}
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={(e) => {
        if (clickable && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          openSymbol(row)
        }
      }}
    >
      <header className="stock-box-head">
        <div className="stock-box-id">
          {tv ? (
            <a
              className="stock-box-sym"
              href={tv}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
            >
              {sym || '—'}
            </a>
          ) : (
            <span className="stock-box-sym">{sym || row.label || '—'}</span>
          )}
          {row.exchange && desk === 'spurts' ? (
            <span className="stock-box-exch">{row.exchange}</span>
          ) : null}
        </div>
        <span className={'chg-pill ' + chgTone(row.change_pct)}>
          {row.change_pct != null
            ? (row.change_pct >= 0 ? '+' : '') + fmtNum(row.change_pct, 1) + '%'
            : '—'}
        </span>
      </header>

      {(desk === 'sci' || desk === 'chart') && row.spark?.length > 1 ? (
        <div className="stock-box-spark">
          <Sparkline points={row.spark} up={row.spark_up !== false} />
          {row.rank != null ? <span className="spark-rank">#{row.rank}</span> : null}
        </div>
      ) : null}

      <dl className={'stock-box-metrics' + (dense ? ' cols-3' : '')}>
        {items.map((item) => (
          <div key={item.key} className={item.tone ? 'tone-' + item.tone : ''}>
            <dt>{item.key}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>

      {desk === 'spurts' && row.volume != null ? (
        <footer className="stock-box-foot">Vol {fmtVol(row.volume)}</footer>
      ) : null}
    </article>
  )
}
