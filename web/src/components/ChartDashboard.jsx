import { useDesk } from '../store'

export default function ChartDashboard() {
  const board = useDesk((s) => s.board)
  if (!board || board.desk !== 'chart') return null

  const dash = board.dashboard || {}
  const sources = board.chart_sources || []
  const toc = board.toc || 'https://chartschool.stockcharts.com/table-of-contents/chart-analysis'
  const meta = [board.universe_label, board.timeframe_label, board.scanned != null ? `${board.scanned}` : null]
    .filter(Boolean)
    .join(' · ')

  const tiles = [
    { label: 'Near S', value: dash.near_support ?? 0, tone: 'pos' },
    { label: 'Near R', value: dash.near_resistance ?? 0, tone: 'neg' },
    { label: 'Break↑', value: dash.breakout ?? 0, tone: 'pos' },
    { label: 'Break↓', value: dash.breakdown ?? 0, tone: 'neg' },
    { label: 'Trend↑', value: dash.trend_up ?? 0, tone: 'pos' },
    { label: 'Trend↓', value: dash.trend_down ?? 0, tone: 'neg' },
    { label: 'Gaps', value: dash.gaps ?? 0, tone: '' },
    { label: 'Patterns', value: dash.patterns ?? 0, tone: '' },
    { label: 'Fib', value: dash.fib_zone ?? 0, tone: '' },
    { label: 'Candles', value: dash.candles ?? 0, tone: '' },
  ]

  return (
    <section className="desk-dash" aria-label="Chart dashboard">
      <div className="desk-dash-head">
        <h2 className="desk-dash-title">Chart</h2>
        <p className="desk-dash-meta">
          {meta}
          {' · '}
          <a href={toc} target="_blank" rel="noreferrer">
            ChartSchool
          </a>
        </p>
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
