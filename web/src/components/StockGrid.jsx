import { useMemo } from 'react'
import { useDesk } from '../store'
import StockCard from './StockCard'

function sortRows(rows, desk) {
  const key = desk === 'spurts' ? 'vol_x' : desk === 'sci' || desk === 'chart' ? 'rank' : 'score'
  const dir = desk === 'sci' || desk === 'chart' ? 1 : -1
  return rows.slice().sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    if (av == null && bv == null) return String(a.nse || '').localeCompare(String(b.nse || ''))
    if (av == null) return 1
    if (bv == null) return -1
    if (av === bv) return String(a.nse || '').localeCompare(String(b.nse || ''))
    return (av < bv ? -1 : 1) * dir
  })
}

export default function StockGrid({ rows }) {
  const desk = useDesk((s) => s.desk)
  const sorted = useMemo(() => sortRows(rows, desk), [rows, desk])

  if (!sorted.length) return <p className="empty">No names match these filters.</p>

  // Chart Analysis: group by setup
  if (desk === 'chart') {
    const groups = [
      ['breakout', 'Resistance breakout', '↑'],
      ['near_support', 'Near support', '▭'],
      ['fib_zone', 'Fibonacci alert zone', 'φ'],
      ['mid_range', 'Mid-range', '·'],
      ['near_resistance', 'Near resistance', '▬'],
      ['breakdown', 'Support breakdown', '↓'],
    ]
    return (
      <div className="stock-board">
        {groups.map(([setup, label, mark]) => {
          const items = sorted.filter((r) => (r.setup || 'mid_range') === setup)
          if (!items.length) return null
          const tone =
            setup === 'breakout' || setup === 'near_support' || setup === 'fib_zone'
              ? 'bullish'
              : setup === 'breakdown' || setup === 'near_resistance'
                ? 'bearish'
                : 'neutral'
          return (
            <section key={setup} className={'stock-group ' + tone}>
              <h2 className="stock-group-head">
                <span className="mark">{mark}</span>
                {label}
                <span className="count">{items.length}</span>
              </h2>
              <div className={'stock-grid desk-' + desk}>
                {items.map((row) => (
                  <StockCard key={`${row.nse || row.id}-${setup}`} row={row} />
                ))}
              </div>
            </section>
          )
        })}
      </div>
    )
  }

  // Lab: group by chart pattern; other desks by bias
  if (desk === 'sci') {
    const groups = [
      ['bull_breakout', 'Bull breakout', '↑'],
      ['bull_base', 'Bull base (coil + volume)', '◎'],
      ['consolidating', 'Consolidating', '▭'],
      ['none', 'No clear pattern', '·'],
    ]
    return (
      <div className="stock-board">
        {groups.map(([pattern, label, mark]) => {
          const items = sorted.filter((r) => (r.pattern || 'none') === pattern)
          if (!items.length) return null
          return (
            <section key={pattern} className={'stock-group ' + (pattern.startsWith('bull') ? 'bullish' : pattern === 'consolidating' ? 'neutral' : 'neutral')}>
              <h2 className="stock-group-head">
                <span className="mark">{mark}</span>
                {label}
                <span className="count">{items.length}</span>
              </h2>
              <div className={'stock-grid desk-' + desk}>
                {items.map((row) => (
                  <StockCard key={`${row.nse || row.id}-${pattern}`} row={row} />
                ))}
              </div>
            </section>
          )
        })}
      </div>
    )
  }

  if (desk !== 'spurts') {
    const groups = [
      ['bullish', 'Bullish', '↑'],
      ['neutral', 'Neutral', '·'],
      ['bearish', 'Bearish', '↓'],
    ]
    return (
      <div className="stock-board">
        {groups.map(([bias, label, mark]) => {
          const items = sorted.filter((r) => (r.bias || 'neutral') === bias)
          if (!items.length) return null
          return (
            <section key={bias} className={'stock-group ' + bias}>
              <h2 className="stock-group-head">
                <span className="mark">{mark}</span>
                {label}
                <span className="count">{items.length}</span>
              </h2>
              <div className={'stock-grid desk-' + desk}>
                {items.map((row) => (
                  <StockCard key={`${row.nse || row.id}-${bias}`} row={row} />
                ))}
              </div>
            </section>
          )
        })}
      </div>
    )
  }

  return (
    <div className="stock-board">
      <div className={'stock-grid desk-' + desk}>
        {sorted.map((row) => (
          <StockCard key={`${row.exchange}-${row.nse || row.id || row.scrip}`} row={row} />
        ))}
      </div>
    </div>
  )
}
