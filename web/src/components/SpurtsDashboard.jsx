import { useEffect, useState } from 'react'
import { fetchSpurtsDashboard } from '../api'
import { useDesk } from '../store'
import { tradingViewUrlForRow } from '../utils'

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
        if (!cancelled) setError(err.message || 'Could not load historic summary')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open, board?.archive?.saved])

  const kpis = dash?.dashboard || {}
  const daily = [...(dash?.daily || [])].reverse()
  const reappear = dash?.reappeared || []

  return (
    <details
      className="spurts-hist-panel"
      onToggle={(e) => setOpen(e.target.open)}
    >
      <summary>
        <span>Historic</span>
        <em>
          {dash
            ? `${kpis.days_covered || 0} days · ${kpis.reappeared || 0} reappeared`
            : 'Open for archive tables'}
        </em>
      </summary>

      <div className="spurts-hist-panel-body">
        {loading && !dash ? <p className="empty">Loading historic tables…</p> : null}
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
              <span className="spurts-hist-meta">
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
                        <th>Date</th>
                        <th>Names</th>
                        <th>NSE</th>
                        <th>BSE</th>
                        <th>≥3×</th>
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
                        <th>Stock</th>
                        <th>Exch</th>
                        <th>Days</th>
                        <th>Max Vol×</th>
                        <th>Avg Vol×</th>
                        <th>Last date</th>
                        <th>Last chg%</th>
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
  )
}
