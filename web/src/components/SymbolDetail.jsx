import { displayStock, fmtNum, fmtVol, tradingViewUrl } from '../utils'
import { useDesk } from '../store'

export default function SymbolDetail() {
  const data = useDesk((s) => s.data)
  const tab = useDesk((s) => s.tab)
  const setTab = useDesk((s) => s.setTab)
  const loading = useDesk((s) => s.loading)
  const symbol = useDesk((s) => s.symbol)

  if (loading && !data) return <p className="empty">Loading {symbol || 'symbol'}…</p>
  if (!data) return <p className="empty">No symbol data.</p>

  const stats = data.stats || {}
  const bars = data.bars || []
  const meta = data.symbol && typeof data.symbol === 'object' ? data.symbol : {}
  const row = {
    nse: meta.nse || data.nse || (typeof data.symbol === 'string' ? data.symbol : '') || symbol,
    name: meta.name || data.name || data.company || stats.company || '',
    exchange: meta.exchange || data.exchange || 'NSE',
  }
  const { sym, name, title } = displayStock(row, { short: false })
  const tv = tradingViewUrl(sym, row.exchange)

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
                <th>Bar</th>
                <th>Close</th>
                <th>Chg %</th>
                <th>Volume</th>
                <th>RVOL</th>
                <th>CMF</th>
                <th>MFI</th>
                <th>Score</th>
                <th>Bias</th>
              </tr>
            </thead>
            <tbody>
              {[...bars]
                .reverse()
                .slice(0, 50)
                .map((bar, i) => (
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
