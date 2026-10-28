import { useDesk } from '../store'

export default function LabDashboard() {
  const board = useDesk((s) => s.board)
  if (!board || board.desk !== 'sci') return null

  const dash = board.dashboard || {}
  const sources = board.chart_sources || []
  const meta = [board.universe_label, board.timeframe_label, board.scanned != null ? `${board.scanned}` : null]
    .filter(Boolean)
    .join(' · ')

  const tiles = [
    { label: 'Break↑', value: dash.bull_breakout ?? 0, tone: 'pos' },
    { label: 'Bull base', value: dash.bull_base ?? 0, tone: 'pos' },
    { label: 'Coil', value: dash.consolidating ?? 0, tone: '' },
    { label: 'Squeeze', value: dash.squeeze ?? 0, tone: '' },
    { label: 'Vol dry', value: dash.vol_dry ?? 0, tone: '' },
    { label: 'HL', value: dash.higher_lows ?? 0, tone: 'pos' },
    { label: 'Range%', value: dash.avg_range_pct != null ? dash.avg_range_pct : '—', tone: '' },
  ]

  return (
    <section className="desk-dash" aria-label="Lab dashboard">
      <div className="desk-dash-head">
        <h2 className="desk-dash-title">Lab</h2>
        <p className="desk-dash-meta">{meta}</p>
      </div>
      <div className="desk-dash-kpis" role="list">
        {tiles.map((t) => (
          <div key={t.label} className={'desk-dash-kpi' + (t.tone ? ' tone-' + t.tone : '')} role="listitem">
            <span>{t.label}</span>
            <strong>{t.value}</strong>
          </div>
        ))}
      </div>
      {sources.length > 0 ? (
        <details className="desk-dash-more">
          <summary>Sources</summary>
          <ul>
            {sources.map((s) => (
              <li key={s.id}>
                <strong>{s.name}</strong>
                <span> — {s.ref}</span>
                {s.url ? (
                  <>
                    {' '}
                    <a href={s.url} target="_blank" rel="noreferrer">
                      ref
                    </a>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  )
}
