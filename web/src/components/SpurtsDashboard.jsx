import { useEffect, useMemo, useState } from 'react'
import { fetchSpurtsDashboard } from '../api'
import { useDesk } from '../store'
import { sortRowsBy, tradingViewUrlForRow } from '../utils'

const DAY_COLS = [
  { key: 'date', label: 'Date', type: 'text' },
  { key: 'count', label: 'Names', type: 'num' },
  { key: 'nse', label: 'NSE', type: 'num' },
  { key: 'bse', label: 'BSE', type: 'num' },
  { key: 'spike', label: '≥3×', type: 'num' },
  { key: 'up', label: 'Up', type: 'num' },
  { key: 'down', label: 'Down', type: 'num' },
]

const REAPPEAR_COLS = [
  { key: 'nse', label: 'Stock', type: 'text' },
  { key: 'exchange', label: 'Exch', type: 'text' },
  { key: 'days', label: 'Days', type: 'num' },
  { key: 'vol_x_max', label: 'Max Vol×', type: 'num' },
  { key: 'vol_x_avg', label: 'Avg Vol×', type: 'num' },
  { key: 'last_vol_x', label: 'Last Vol×', type: 'num' },
  { key: 'last_date', label: 'Last date', type: 'text' },
  { key: 'last_change_pct', label: 'Last chg%', type: 'num' },
]

/**
 * Spurts default UI is the live data table (Stage → SpurtsTable).
 * This component is only the on-demand historic summary — collapsed until opened.
 */
export default function SpurtsDashboard() {
  const board = useDesk((s) => s.board)
  const setSpurtsDate = useDesk((s) => s.setSpurtsDate)
  const spurtsDate = useDesk((s) => s.spurtsDate)

  const [open, setOpen] = useState(false)
  const [dash, setDash] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('days') // days | reappear
  const [daySort, setDaySort] = useState({ key: 'date', dir: 'desc', type: 'text' })
  const [reSort, setReSort] = useState({ key: 'days', dir: 'desc', type: 'num' })

  useEffect(() => {
    if (!open) return undefined
    let cancelled = false
    setLoading(true)
    ;(async () => {
      try {
        const data = await fetchSpurtsDashboard(30)
        if (!cancelled) {
          setDash(data)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load archive summary')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open, board?.archive?.saved])

  const liveSyms = useMemo(() => {
    const set = new Set()
    for (const row of board?.rows || []) {
      const sym = String(row.nse || row.id || '').toUpperCase()
      if (sym) set.add(sym)
    }
    return set
  }, [board])

  const leaders = useMemo(() => {
    const ranked = (board?.rows || [])
      .filter((row) => row.vol_x != null)
      .slice()
      .sort((a, b) => (b.vol_x || 0) - (a.vol_x || 0))
    // ₹5 crore. NSE turnover is in lakh, BSE in crore. Drops a 100× print on a few thousand shares.
    const liquid = ranked.filter((row) => {
      const n = Number(row.turnover)
      if (!Number.isFinite(n) || n <= 0) return false
      const rupees = String(row.turnover_unit || '').toLowerCase().includes('cr') ? n * 1e7 : n * 1e5
      return rupees >= 5e7
    })
    return (liquid.length >= 4 ? liquid : ranked).slice(0, 8)
  }, [board])

  const kpis = dash?.dashboard || {}
  const dailyRaw = dash?.daily || []
  const reappearRaw = dash?.reappeared || []

  const daily = useMemo(
    () =>
      sortRowsBy(dailyRaw, daySort.key, daySort.dir, (d) => {
        if (daySort.key === 'date') return d.date || ''
        const v = d[daySort.key]
        return v == null || Number.isNaN(Number(v)) ? null : Number(v)
      }),
    [dailyRaw, daySort],
  )

  const reappear = useMemo(
    () =>
      sortRowsBy(reappearRaw, reSort.key, reSort.dir, (r) => {
        if (reSort.key === 'nse') return String(r.nse || r.id || r.name || '').toUpperCase()
        if (reSort.key === 'exchange' || reSort.key === 'last_date') return String(r[reSort.key] || '')
        const v = r[reSort.key]
        return v == null || Number.isNaN(Number(v)) ? null : Number(v)
      }),
    [reappearRaw, reSort],
  )

  function toggleSort(setter) {
    return (key, type) => {
      setter((prev) =>
        prev.key === key
          ? { ...prev, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
          : { key, dir: type === 'text' ? 'asc' : 'desc', type },
      )
    }
  }

  const toggleDay = toggleSort(setDaySort)
  const toggleRe = toggleSort(setReSort)

  const counts = board?.counts || {}
  const liveLine = [
    board?.history ? `Archive ${board.history_date || ''}`.trim() : null,
    counts.nse != null ? `NSE ${counts.nse}` : null,
    counts.bse != null ? `BSE ${counts.bse}` : null,
    counts.spike != null ? `≥3× ${counts.spike}` : null,
    counts.up != null ? `${counts.up}↑` : null,
    counts.down != null ? `${counts.down}↓` : null,
    counts.live != null && board?.scanned != null ? `quotes ${counts.live}/${board.scanned}` : null,
  ]
    .filter(Boolean)
    .join(' · ')
  const feedError = Array.isArray(board?.errors) && board.errors.length ? board.errors.join(' · ') : null

  if (!board) return null

  return (
    <section className="desk-dash is-plain" aria-label="Spurts dashboard">
      <div className="desk-dash-head">
        <h2 className="desk-dash-title">Spurts</h2>
        <p className="desk-dash-meta">{liveLine}</p>
        <p className="desk-dash-meta lookback">
          NSE Vol× = 1-week · BSE Vol× = 2-week · 2W× = NSE 2-week
        </p>
      </div>
      {feedError ? <p className="desk-dash-meta lookback">{feedError}</p> : null}
      {leaders.length ? (
        <div className="spurts-lead" aria-label="Highest volume multiples">
          {leaders.map((row) => {
            const sym = row.nse || row.id
            const href = tradingViewUrlForRow(row)
            const chg = row.change_pct
            const body = (
              <>
                <strong>{sym}</strong>
                <span>{row.exchange}</span>
                <em>{Number(row.vol_x).toFixed(1)}×</em>
                {chg != null ? (
                  <em className={chg >= 0 ? 'up' : 'down'}>
                    {chg >= 0 ? '+' : ''}
                    {Number(chg).toFixed(1)}%
                  </em>
                ) : null}
              </>
            )
            return href ? (
              <a key={`${row.exchange}-${sym}`} href={href} target="_blank" rel="noreferrer" title="Open on TradingView">
                {body}
              </a>
            ) : (
              <span key={`${row.exchange}-${sym}`}>{body}</span>
            )
          })}
        </div>
      ) : null}
    <details
      className="spurts-hist-panel"
      onToggle={(e) => setOpen(e.target.open)}
    >
      <summary>
        <span>Archive</span>
        <em>
          {dash
            ? `${kpis.days_covered || 0} days · ${kpis.reappeared || 0} reappeared`
            : 'By date · names that returned'}
        </em>
      </summary>

      <div className="spurts-hist-panel-body">
        {loading && !dash ? <p className="empty">Loading archive tables…</p> : null}
        {error ? <p className="empty">{error}</p> : null}

        {dash ? (
          <>
            <div className="spurts-hist-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                className={tab === 'days' ? 'is-on' : ''}
                onClick={() => setTab('days')}
              >
                By date
              </button>
              <button
                type="button"
                role="tab"
                className={tab === 'reappear' ? 'is-on' : ''}
                onClick={() => setTab('reappear')}
              >
                Reappeared
              </button>
              <span className="spurts-hist-kpis">
                Unique {kpis.unique_names ?? 0} · once {kpis.once_only ?? 0} · avg/day{' '}
                {kpis.avg_names_per_day ?? 0}
              </span>
            </div>

            {tab === 'days' ? (
              daily.length ? (
                <div className="tape spurts-hist-tape">
                  <table>
                    <thead>
                      <tr>
                        {DAY_COLS.map((c) => (
                          <th key={c.key}>
                            <button
                              type="button"
                              className={'sort-btn' + (daySort.key === c.key ? ' is-on' : '')}
                              onClick={() => toggleDay(c.key, c.type)}
                            >
                              {c.label}
                              {daySort.key === c.key ? (daySort.dir === 'asc' ? ' ↑' : ' ↓') : ''}
                            </button>
                          </th>
                        ))}
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {daily.map((d) => (
                        <tr
                          key={d.date}
                          className={spurtsDate === d.date ? 'is-active-day' : ''}
                        >
                          <td className="spurts-hist-date">{d.date}</td>
                          <td>{d.count}</td>
                          <td>{d.nse}</td>
                          <td>{d.bse}</td>
                          <td>{d.spike ?? '—'}</td>
                          <td className="up">{d.up ?? '—'}</td>
                          <td className="down">{d.down ?? '—'}</td>
                          <td>
                            <button
                              type="button"
                              className="chip-btn"
                              onClick={() => setSpurtsDate(d.date)}
                            >
                              Open table
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty">No saved days yet. Use Save day after close.</p>
              )
            ) : null}

            {tab === 'reappear' ? (
              reappear.length ? (
                <div className="tape spurts-hist-tape">
                  <table>
                    <thead>
                      <tr>
                        {REAPPEAR_COLS.map((c) => (
                          <th key={c.key}>
                            <button
                              type="button"
                              className={'sort-btn' + (reSort.key === c.key ? ' is-on' : '')}
                              onClick={() => toggleRe(c.key, c.type)}
                            >
                              {c.label}
                              {reSort.key === c.key ? (reSort.dir === 'asc' ? ' ↑' : ' ↓') : ''}
                            </button>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {reappear.map((r) => {
                        const tv = tradingViewUrlForRow(r)
                        const sym = r.nse || r.id
                        return (
                          <tr key={r.id}>
                            <td>
                              {tv ? (
                                <a
                                  className="stock-link"
                                  href={tv}
                                  target="_blank"
                                  rel="noreferrer"
                                  title="Open on TradingView"
                                >
                                  <strong className="stock-sym">{sym}</strong>
                                  {r.name ? <span className="spurts-hist-name">{r.name}</span> : null}
                                </a>
                              ) : (
                                <>
                                  <strong>{sym}</strong>
                                  {r.name ? <span className="spurts-hist-name">{r.name}</span> : null}
                                </>
                              )}
                            </td>
                            <td>{r.exchange || '—'}</td>
                            <td>{r.days}</td>
                            <td>{r.vol_x_max != null ? Number(r.vol_x_max).toFixed(2) : '—'}</td>
                            <td>{r.vol_x_avg != null ? Number(r.vol_x_avg).toFixed(2) : '—'}</td>
                            <td>
                              {r.last_vol_x != null ? Number(r.last_vol_x).toFixed(2) : '—'}
                              {liveSyms.has(String(r.nse || r.id || '').toUpperCase()) ? ' · today' : ''}
                            </td>
                            <td>
                              {r.last_date ? (
                                <button
                                  type="button"
                                  className="spurts-hist-link"
                                  onClick={() => setSpurtsDate(r.last_date)}
                                >
                                  {r.last_date}
                                </button>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td
                              className={
                                r.last_change_pct == null
                                  ? ''
                                  : r.last_change_pct >= 0
                                    ? 'up'
                                    : 'down'
                              }
                            >
                              {r.last_change_pct == null
                                ? '—'
                                : `${r.last_change_pct >= 0 ? '+' : ''}${Number(r.last_change_pct).toFixed(1)}%`}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty">No reappearances yet (need ≥2 archived days).</p>
              )
            ) : null}
          </>
        ) : null}
      </div>
    </details>
    </section>
  )
}
