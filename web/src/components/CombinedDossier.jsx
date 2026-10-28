import { displayStock, fmtNum, fmtVol, tradingViewUrl } from '../utils'
import { useDesk } from '../store'
import Sparkline from './Sparkline'

/** Volume in thousands (matches exchange volume tables). */
function fmtVolK(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const n = Number(value)
  if (n >= 1e5) return (n / 1e5).toFixed(2) + ' L'
  if (n >= 1e3) return (n / 1e3).toFixed(2)
  return String(Math.round(n))
}

function fmtPct(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return Number(value).toFixed(digits) + '%'
}

function fmtSignedPct(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const n = Number(value)
  return (n > 0 ? '+' : '') + n.toFixed(digits) + '%'
}

/** Prefer server KPIs; fill gaps client-side so older caches still compare. */
function withVolumeKpis(rows, rvolWindow = 10) {
  const list = Array.isArray(rows) ? rows : []
  const totals = []
  const nseHist = []
  const bseHist = []
  return list.map((bar) => {
    const nse = Number(bar.nse_volume) || 0
    const bse = Number(bar.bse_volume) || 0
    const total =
      bar.total_volume != null && !Number.isNaN(Number(bar.total_volume))
        ? Number(bar.total_volume)
        : nse + bse || null

    let volChg = bar.vol_chg_pct
    let nseChg = bar.nse_chg_pct
    let bseChg = bar.bse_chg_pct
    const prevTot = totals.length ? totals[totals.length - 1] : null
    const prevNse = nseHist.length ? nseHist[nseHist.length - 1] : null
    const prevBse = bseHist.length ? bseHist[bseHist.length - 1] : null
    if (volChg == null && total && prevTot) volChg = +(((total - prevTot) / prevTot) * 100).toFixed(2)
    if (nseChg == null && nse && prevNse) nseChg = +(((nse - prevNse) / prevNse) * 100).toFixed(2)
    if (bseChg == null && bse && prevBse) bseChg = +(((bse - prevBse) / prevBse) * 100).toFixed(2)

    let avgVol = bar.avg_volume
    let rvol = bar.rvol
    const lookback = totals.slice(-rvolWindow).filter((t) => t > 0)
    if (lookback.length) {
      const avg = lookback.reduce((a, b) => a + b, 0) / lookback.length
      if (avgVol == null && avg > 0) avgVol = Math.round(avg)
      if (rvol == null && total && avg > 0) rvol = +(total / avg).toFixed(2)
    }
    const spike = bar.spike != null ? Boolean(bar.spike) : rvol != null && rvol >= 1.5

    let ratio = bar.nse_bse_ratio
    if (ratio == null && nse > 0 && bse > 0) ratio = +(nse / bse).toFixed(2)

    let delPct = bar.delivery_pct
    const delivery = bar.delivery != null ? Number(bar.delivery) : null
    const base = nse || total
    if (delPct == null && delivery != null && base) delPct = +((delivery / base) * 100).toFixed(1)

    if (total) totals.push(total)
    if (nse) nseHist.push(nse)
    if (bse) bseHist.push(bse)
    return {
      ...bar,
      total_volume: total || null,
      avg_volume: avgVol ?? null,
      vol_chg_pct: volChg,
      nse_chg_pct: nseChg,
      bse_chg_pct: bseChg,
      rvol,
      spike,
      nse_bse_ratio: ratio,
      delivery_pct: delPct,
    }
  })
}

function Metric({ label, value, tone }) {
  return (
    <div className={tone ? 'tone-' + tone : ''}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function scoreTone(score, mid = 0) {
  if (score == null || Number.isNaN(Number(score))) return ''
  const n = Number(score)
  if (n > mid) return 'pos'
  if (n < mid) return 'neg'
  return ''
}

function DeskPanel({ title, children, empty }) {
  return (
    <section className="dossier-panel">
      <header className="dossier-panel-head">
        <h3>{title}</h3>
      </header>
      {empty ? <p className="empty dossier-empty">{empty}</p> : <dl className="stock-box-metrics cols-3">{children}</dl>}
    </section>
  )
}

export default function CombinedDossier() {
  const dossier = useDesk((s) => s.dossier)
  const loading = useDesk((s) => s.loading)
  const symbol = useDesk((s) => s.symbol)

  if (loading && !dossier) return <p className="empty">Loading combined signal · {symbol || 'symbol'}…</p>
  if (!dossier) return <p className="empty">No combined signal for this symbol.</p>

  const meta = dossier.symbol || {}
  const row = {
    nse: meta.nse || symbol,
    name: meta.name || '',
    exchange: meta.exchange || 'NSE',
  }
  const { sym, name, title } = displayStock(row, { short: false })
  const tv = tradingViewUrl(sym, row.exchange)
  const vol = dossier.volume || {}
  const stats = vol.stats || {}
  const study = vol.study || {}
  const xvol = Array.isArray(dossier.exchange_volume) ? dossier.exchange_volume : []
  const tech = dossier.tech || null
  const sci = dossier.sci || null
  const chart = dossier.chart || null

  return (
    <div className="dossier">
      <p className="board-note stock-headline" title={title}>
        <strong className="stock-sym">{sym}</strong>
        {name ? <span className="stock-name"> · {name}</span> : null}
        {' · '}
        {dossier.timeframe_label || ''}
        {meta.sector ? ` · ${meta.sector}` : ''}
        {tv ? (
          <>
            {' · '}
            <a className="stock-link" href={tv} target="_blank" rel="noreferrer">
              TradingView
            </a>
          </>
        ) : null}
        {dossier.cached ? ' · cached' : ' · fresh'}
      </p>
      <p className="dossier-blurb">Combined Volume · Technical · Lab · Chart (Spurts excluded)</p>

      <div className="dossier-grid">
        <DeskPanel title="Volume" empty={dossier.volume_error || (!vol.stats && !vol.study ? 'No volume data.' : null)}>
          <Metric label="Score" value={stats.score != null ? String(stats.score) : '—'} tone={scoreTone(stats.score)} />
          <Metric label="Bias" value={stats.bias || study.bias || '—'} />
          <Metric
            label="RVOL"
            value={stats.rvol != null ? stats.rvol.toFixed(2) + '×' : '—'}
            tone={stats.rvol != null && stats.rvol >= 1.5 ? 'pos' : ''}
          />
          <Metric label="CMF" value={stats.cmf != null ? stats.cmf.toFixed(2) : '—'} tone={scoreTone(stats.cmf)} />
          <Metric label="MFI" value={stats.mfi != null ? stats.mfi.toFixed(0) : '—'} />
          <Metric
            label="OBV"
            value={stats.obv_rising === true ? '↑' : stats.obv_rising === false ? '↓' : '—'}
            tone={stats.obv_rising === true ? 'pos' : stats.obv_rising === false ? 'neg' : ''}
          />
          <Metric
            label="NSE Vol"
            value={
              xvol.length && xvol[xvol.length - 1]?.nse_volume != null
                ? fmtVol(xvol[xvol.length - 1].nse_volume)
                : fmtVol(stats.last_volume)
            }
          />
          <Metric
            label="BSE Vol"
            value={
              xvol.length && xvol[xvol.length - 1]?.bse_volume != null
                ? fmtVol(xvol[xvol.length - 1].bse_volume)
                : '—'
            }
          />
          <Metric
            label="Delivery"
            value={
              xvol.length && xvol[xvol.length - 1]?.delivery != null
                ? fmtVol(xvol[xvol.length - 1].delivery)
                : stats.delivery_qty != null
                  ? fmtVol(stats.delivery_qty)
                  : '—'
            }
          />
        </DeskPanel>

        <DeskPanel title="Technical" empty={!tech ? 'No technical reading for this TF.' : null}>
          {tech ? (
            <>
              <Metric label="Score" value={tech.score != null ? String(tech.score) : '—'} tone={scoreTone(tech.score)} />
              <Metric label="Bias" value={tech.bias || '—'} />
              <Metric label="RSI" value={tech.rsi != null ? tech.rsi.toFixed(0) : '—'} tone={tech.rsi != null && tech.rsi >= 55 ? 'pos' : tech.rsi != null && tech.rsi <= 45 ? 'neg' : ''} />
              <Metric label="MACD" value={tech.macd_hist != null ? tech.macd_hist.toFixed(2) : '—'} tone={scoreTone(tech.macd_hist)} />
              <Metric label="SMA20" value={tech.sma20 != null ? fmtNum(tech.sma20) : '—'} />
              <Metric label="SMA50" value={tech.sma50 != null ? fmtNum(tech.sma50) : '—'} />
              <Metric label="EMA20" value={tech.ema20 != null ? fmtNum(tech.ema20) : '—'} />
              <Metric label="Stoch" value={tech.stoch_k != null ? tech.stoch_k.toFixed(0) : '—'} />
            </>
          ) : null}
        </DeskPanel>

        <DeskPanel title="Lab" empty={!sci ? 'No lab pattern for this TF.' : null}>
          {sci ? (
            <>
              <Metric label="Pattern" value={(sci.pattern || 'none').replace(/_/g, ' ')} />
              <Metric label="Score" value={sci.score != null ? String(sci.score) : '—'} tone={scoreTone(sci.score)} />
              <Metric label="Bull" value={sci.bull_score != null ? Number(sci.bull_score).toFixed(0) : '—'} />
              <Metric label="Coil" value={sci.consol_score != null ? Number(sci.consol_score).toFixed(0) : '—'} />
              <Metric label="Range%" value={sci.range_pct != null ? sci.range_pct.toFixed(1) : '—'} />
              <Metric label="RVOL" value={sci.rvol != null ? sci.rvol.toFixed(1) + '×' : '—'} />
              <Metric label="CMF" value={sci.cmf != null ? sci.cmf.toFixed(2) : '—'} tone={scoreTone(sci.cmf)} />
              {sci.spark?.length > 1 ? (
                <div className="dossier-spark">
                  <Sparkline points={sci.spark} up={sci.spark_up !== false} />
                </div>
              ) : null}
            </>
          ) : null}
        </DeskPanel>

        <DeskPanel title="Chart" empty={!chart ? 'No chart reading for this TF.' : null}>
          {chart ? (
            <>
              <Metric label="Setup" value={(chart.setup || '—').replace(/_/g, ' ')} />
              <Metric label="Score" value={chart.score != null ? String(chart.score) : '—'} tone={scoreTone(chart.score, 50)} />
              <Metric label="Trend" value={chart.trend || '—'} tone={chart.trend === 'up' ? 'pos' : chart.trend === 'down' ? 'neg' : ''} />
              <Metric label="Pattern" value={(chart.pattern || 'none').replace(/_/g, ' ')} />
              <Metric label="Support" value={chart.support != null ? fmtNum(chart.support) : '—'} />
              <Metric label="Resist" value={chart.resistance != null ? fmtNum(chart.resistance) : '—'} />
              <Metric label="Fib" value={chart.fib_nearest ? chart.fib_nearest + '%' : '—'} tone={chart.fib_zone ? 'pos' : ''} />
              <Metric label="Candle" value={(chart.candle || 'none').replace(/_/g, ' ')} />
              {chart.spark?.length > 1 ? (
                <div className="dossier-spark">
                  <Sparkline points={chart.spark} up={chart.spark_up !== false} />
                </div>
              ) : null}
            </>
          ) : null}
        </DeskPanel>
      </div>

      <div className="dossier-bars">
        <header className="dossier-panel-head">
          <h3>NSE · BSE volume</h3>
          <p className="dossier-xvol-note">
            Last 15 · Avg10 · Δ Tot/NSE/BSE · RVOL · Mix · Spike (≥1.5×) · Delivery
          </p>
        </header>
        {!xvol.length ? (
          <p className="empty">No NSE/BSE volume history for this symbol / timeframe.</p>
        ) : (
          <div className="tape dossier-xvol-tape">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>NSE</th>
                  <th>BSE</th>
                  <th>Total</th>
                  <th title="Average total volume of prior 10 sessions">Avg10</th>
                  <th title="Total volume vs prior session">Δ Tot</th>
                  <th title="NSE volume vs prior session">Δ NSE</th>
                  <th title="BSE volume vs prior session">Δ BSE</th>
                  <th title="Total ÷ Avg10">RVOL</th>
                  <th title="NSE volume ÷ BSE volume">Mix</th>
                  <th title="RVOL ≥ 1.5×">Spike</th>
                  <th>Delivery</th>
                  <th title="Delivery ÷ NSE volume">Del %</th>
                </tr>
              </thead>
              <tbody>
                {[...withVolumeKpis(xvol)]
                  .reverse()
                  .slice(0, 15)
                  .map((bar, i) => (
                    <tr key={(bar.date || bar.label || 'd') + '-' + i} className={bar.spike ? 'is-vol-spike' : ''}>
                      <td>{bar.label || bar.date}</td>
                      <td>{fmtVolK(bar.nse_volume)}</td>
                      <td>{fmtVolK(bar.bse_volume)}</td>
                      <td>{fmtVolK(bar.total_volume)}</td>
                      <td>{fmtVolK(bar.avg_volume)}</td>
                      <td className={scoreTone(bar.vol_chg_pct) ? 'tone-' + scoreTone(bar.vol_chg_pct) : ''}>
                        {fmtSignedPct(bar.vol_chg_pct, 1)}
                      </td>
                      <td className={scoreTone(bar.nse_chg_pct) ? 'tone-' + scoreTone(bar.nse_chg_pct) : ''}>
                        {fmtSignedPct(bar.nse_chg_pct, 1)}
                      </td>
                      <td className={scoreTone(bar.bse_chg_pct) ? 'tone-' + scoreTone(bar.bse_chg_pct) : ''}>
                        {fmtSignedPct(bar.bse_chg_pct, 1)}
                      </td>
                      <td className={bar.rvol != null && bar.rvol >= 1.5 ? 'tone-pos' : ''}>
                        {bar.rvol != null ? bar.rvol.toFixed(2) + '×' : '—'}
                      </td>
                      <td>{bar.nse_bse_ratio != null ? bar.nse_bse_ratio.toFixed(1) + '×' : '—'}</td>
                      <td>{bar.spike ? 'Yes' : '—'}</td>
                      <td>{fmtVolK(bar.delivery)}</td>
                      <td>{fmtPct(bar.delivery_pct, 1)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
