import { useMemo, useState } from 'react'
import { displayStock, fmtNum, fmtVol, sortRowsBy, tradingViewUrl } from '../utils'
import { useDesk } from '../store'

const BAR_COLS = [
  { key: 'label', label: 'Bar', type: 'text' },
  { key: 'close', label: 'Close', type: 'num' },
  { key: 'change_pct', label: 'Chg %', type: 'num' },
  { key: 'volume', label: 'Volume', type: 'num' },
  { key: 'rvol', label: 'RVOL', type: 'num' },
  { key: 'cmf', label: 'CMF', type: 'num' },
  { key: 'mfi', label: 'MFI', type: 'num' },
  { key: 'score', label: 'Score', type: 'num' },
  { key: 'bias', label: 'Bias', type: 'text' },
]

export default function SymbolDetail() {
  const data = useDesk((s) => s.data)
  const tab = useDesk((s) => s.tab)
  const setTab = useDesk((s) => s.setTab)
  const loading = useDesk((s) => s.loading)
  const symbol = useDesk((s) => s.symbol)
  const [barSort, setBarSort] = useState({ key: 'label', dir: 'desc', type: 'text' })

  const bars = data?.bars || []
  const sortedBars = useMemo(() => {
    const recent = bars.slice(-50)
    return sortRowsBy(recent, barSort.key, barSort.dir, (bar) => {
      if (barSort.key === 'label') return bar.label || bar.date || ''
      if (barSort.key === 'bias') return String(bar.bias || '')
      const v = bar[barSort.key]
      return v == null || Number.isNaN(Number(v)) ? null : Number(v)
    })
  }, [bars, barSort])

  if (loading && !data) return <p className="empty">Loading {symbol || 'symbol'}…</p>
  if (!data) return <p className="empty">No symbol data.</p>

  const stats = data.stats || {}
  const meta = data.symbol && typeof data.symbol === 'object' ? data.symbol : {}
  const row = {
    nse: meta.nse || data.nse || (typeof data.symbol === 'string' ? data.symbol : '') || symbol,
    name: meta.name || data.name || data.company || stats.company || '',
    exchange: meta.exchange || data.exchange || 'NSE',
  }
  const { sym, name, title } = displayStock(row, { short: false })
  const tv = tradingViewUrl(sym, row.exchange)

  function toggleBarSort(key, type) {
    setBarSort((prev) =>
      prev.key === key
        ? { ...prev, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: type === 'text' ? 'asc' : 'desc', type },
    )
  }

  return (
    <>
      <div className="tabs" role="tablist">
        {[
          ['trend', 'Map'],
          ['bars', 'Bars'],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={
              (id === 'bars' ? tab === 'bars' || tab === 'chart' : tab === id) ? 'is-on' : ''
            }
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <p className="board-note stock-headline" title={title}>
        <strong className="stock-sym">{sym}</strong>
        {name ? <span className="stock-name"> · {name}</span> : null}
        {' · '}
        {data.timeframe_label}
        {tv ? (
          <>
            {' · '}
            <a className="stock-link" href={tv} target="_blank" rel="noreferrer">
              TradingView
            </a>
          </>
        ) : null}
        {' · score '}
        {stats.score ?? '—'} · {stats.bias || '—'}
      </p>

      {!bars.length ? (
        <p className="empty">No volume bars for this symbol / timeframe.</p>
      ) : tab === 'trend' ? (
        <div className="stock-grid">
          {[...bars]
            .slice(-24)
            .reverse()
            .map((bar) => {
              const bias = bar.bias || 'neutral'
              const tone =
                bias === 'bullish'
                  ? Math.abs(bar.score || 0) >= 60
                    ? 'tone-bull-strong'
                    : 'tone-bull'
                  : bias === 'bearish'
                    ? Math.abs(bar.score || 0) >= 60
                      ? 'tone-bear-strong'
                      : 'tone-bear'
                    : 'tone-neutral'
              return (
                <article key={bar.label || bar.date} className={'stock-box ' + tone}>
                  <header className="stock-box-head">
                    <div className="stock-box-id">
                      <span className="stock-box-sym">{bar.label || bar.date}</span>
                      <span className="stock-box-name">Vol {fmtVol(bar.volume)}</span>
                    </div>
                    <div className={'stock-box-score ' + ((bar.score || 0) >= 0 ? 'pos' : 'neg')}>
                      <em>Score</em>
                      <strong>
                        {bar.score == null
                          ? '—'
                          : (bar.score > 0 ? '+' : '') + Number(bar.score).toFixed(0)}
                      </strong>
                    </div>
                  </header>
                  <div className="stock-box-bias">
                    <span className="bias-pill">{bias}</span>
                  </div>
                  <dl className="stock-box-metrics">
                    <div>
                      <dt>Close</dt>
                      <dd>{fmtNum(bar.close)}</dd>
                    </div>
                    <div>
                      <dt>Chg</dt>
                      <dd>
                        {bar.change_pct != null
                          ? (bar.change_pct >= 0 ? '+' : '') + fmtNum(bar.change_pct) + '%'
                          : '—'}
                      </dd>
                    </div>
                    <div>
                      <dt>RVOL</dt>
                      <dd>{bar.rvol != null ? bar.rvol.toFixed(2) + '×' : '—'}</dd>
                    </div>
                  </dl>
                </article>
              )
            })}
        </div>
      ) : (
        <div className="tape">
          <table>
            <thead>
              <tr>
                {BAR_COLS.map((c) => (
                  <th key={c.key}>
                    <button
                      type="button"
                      className={'sort-btn' + (barSort.key === c.key ? ' is-on' : '')}
                      onClick={() => toggleBarSort(c.key, c.type)}
                    >
                      {c.label}
                      {barSort.key === c.key ? (barSort.dir === 'asc' ? ' ↑' : ' ↓') : ''}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedBars.map((bar, i) => (
                <tr
                  key={(bar.label || bar.date || 'bar') + '-' + i}
                  className={
                    bar.bias === 'bullish' ? 'is-bullish' : bar.bias === 'bearish' ? 'is-bearish' : ''
                  }
                >
                  <td>{bar.label || bar.date}</td>
                  <td>{fmtNum(bar.close)}</td>
                  <td className={bar.up ? 'up' : 'down'}>
                    {bar.change_pct != null
                      ? (bar.change_pct >= 0 ? '+' : '') + fmtNum(bar.change_pct)
                      : '—'}
                  </td>
                  <td>{fmtVol(bar.volume)}</td>
                  <td>{bar.rvol != null ? bar.rvol.toFixed(2) + '×' : '—'}</td>
                  <td>{bar.cmf != null ? bar.cmf.toFixed(3) : '—'}</td>
                  <td>{bar.mfi != null ? bar.mfi.toFixed(1) : '—'}</td>
                  <td>{bar.score != null ? String(bar.score) : '—'}</td>
                  <td>{bar.bias || 'neutral'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
