import { useMemo } from 'react'
import { useDesk } from '../store'
import { displayStock, fmtNum, fmtVol } from '../utils'
import StockLink from './StockLink'

const COLS = [
  { key: 'rank', label: 'Rank', type: 'num', title: '1 = highest Vol× in this tab. Hover shows the rank on the full NSE+BSE list' },
  { key: 'exchange', label: 'Exch', type: 'text', title: 'NSE Volume Gainers or BSE Spurt-in-Volume' },
  { key: 'nse', label: 'Stock', type: 'text', title: 'Symbol' },
  { key: 'change_pct', label: 'Chg %', type: 'num', title: 'Live price change when a quote is available' },
  {
    key: 'vol_x',
    label: 'Vol×',
    type: 'num',
    title: 'NSE: today ÷ 1-week average · BSE: today ÷ 2-week average · official list, not the live quote',
  },
  {
    key: 'vol_x_2w',
    label: '2W×',
    type: 'num',
    title: 'NSE today ÷ 2-week average. BSE publishes one 2-week multiple, so this matches Vol×',
  },
  { key: 'volume', label: 'Volume', type: 'num', title: 'Exchange session volume (shares)' },
  { key: 'avg_volume', label: 'Avg', type: 'num', title: 'NSE 1-week average · BSE 2-week average' },
  { key: 'ltp', label: 'LTP', type: 'num', title: 'Last price · live quote when the feed answers' },
  { key: 'turnover', label: 'Turnover', type: 'num', title: 'NSE in ₹ lakh · BSE in ₹ crore' },
  { key: 'score', label: 'Score', type: 'num', title: '−100…+100. Log Vol×, capped near 200×, plus a small price adjustment. Rank still follows Vol×' },
]

function sortValue(row, col) {
  if (col.key === 'nse') {
    const { sym, name } = displayStock(row, { short: false })
    return String(sym || name || '').toUpperCase()
  }
  const value = row[col.key]
  if (col.type === 'text') return String(value || '').toUpperCase()
  if (value == null || Number.isNaN(Number(value))) return null
  return Number(value)
}

function Metric({ value, tone, digits }) {
  if (value == null || Number.isNaN(Number(value))) return <td className="metric-cell">—</td>
  const text = typeof digits === 'number' ? Number(value).toFixed(digits) : String(value)
  return (
    <td className="metric-cell">
      <span className={'metric-chip ' + (tone || '')}>
        <strong>{text}</strong>
      </span>
    </td>
  )
}

export default function SpurtsTable({ rows }) {
  const sortKey = useDesk((s) => s.sortKey)
  const sortDir = useDesk((s) => s.sortDir)
  const setSort = useDesk((s) => s.setSort)

  const volRank = useMemo(() => {
    const order = rows.slice().sort((a, b) => (b.vol_x || 0) - (a.vol_x || 0) || String(a.nse || '').localeCompare(String(b.nse || '')))
    const map = new Map()
    order.forEach((row, index) => map.set(row, index + 1))
    return map
  }, [rows])

  const sorted = useMemo(() => {
    const col = COLS.find((c) => c.key === sortKey) || COLS.find((c) => c.key === 'vol_x')
    const dir = sortDir === 'asc' ? 1 : -1
    return rows.slice().sort((a, b) => {
      const av = sortValue(a, col)
      const bv = sortValue(b, col)
      if (av == null && bv == null) return String(a.nse || '').localeCompare(String(b.nse || ''))
      if (av == null) return 1
      if (bv == null) return -1
      if (typeof av === 'string' || typeof bv === 'string') return String(av).localeCompare(String(bv)) * dir
      if (av === bv) return String(a.nse || '').localeCompare(String(b.nse || ''))
      return (av < bv ? -1 : 1) * dir
    })
  }, [rows, sortKey, sortDir])

  return (
    <div className="tape spurts-tape">
      <table>
        <thead>
          <tr>
            {COLS.map((col) => (
              <th key={col.key}>
                <button
                  type="button"
                  className={'sort-btn' + (sortKey === col.key ? ' is-on' : '')}
                  title={col.title || `Sort by ${col.label}`}
                  onClick={() => setSort(col.key, col.type)}
                >
                  {col.label}
                  {sortKey === col.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const cls =
              row.change_pct == null || row.change_pct === 0
                ? ''
                : row.change_pct > 0
                  ? 'is-bullish'
                  : 'is-bearish'
            const key = `${row.exchange}-${row.nse || row.id || row.scrip || row.rank}`
            return (
              <tr key={key} className={cls}>
                <td title={row.rank != null ? `Book rank ${row.rank}` : undefined}>{volRank.get(row) ?? row.rank ?? '—'}</td>
                <td>{row.exchange || '—'}</td>
                <StockLink row={row} as="cell" showName short />
                <td className={row.change_pct == null ? '' : row.change_pct >= 0 ? 'up' : 'down'}>
                  {row.change_pct != null
                    ? (row.change_pct >= 0 ? '+' : '') + fmtNum(row.change_pct) + '%'
                    : '—'}
                </td>
                <Metric value={row.vol_x} tone={(row.vol_x || 0) >= 3 ? 'up' : ''} digits={2} />
                <Metric
                  value={row.exchange === 'BSE' ? null : row.vol_x_2w}
                  tone={(row.vol_x_2w || 0) >= 3 ? 'up' : ''}
                  digits={2}
                />
                <td>{row.volume != null ? fmtVol(row.volume) : '—'}</td>
                <td>{row.avg_volume != null ? fmtVol(row.avg_volume) : '—'}</td>
                <td>{row.ltp != null ? fmtNum(row.ltp) : '—'}</td>
                <td>
                  {row.turnover != null
                    ? fmtNum(row.turnover) +
                      (row.turnover_unit ? ' ' + String(row.turnover_unit).replace('₹ ', '') : '')
                    : '—'}
                </td>
                <Metric value={row.score} tone={row.bias || (row.score >= 0 ? 'up' : 'down')} />
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
