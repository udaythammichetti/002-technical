import { useMemo, useState } from 'react'
import { displayStock, fmtNum, fmtVol, sortRowsBy, tradingViewUrl } from '../utils'
import { useDesk } from '../store'
import Sparkline from './Sparkline'

function xvolCols(rvolN) {
  const n = rvolN != null && Number(rvolN) > 0 ? Number(rvolN) : 50
  return [
    { key: 'date', label: 'Date', type: 'text' },
    { key: 'nse_volume', label: 'NSE', type: 'num' },
    { key: 'bse_volume', label: 'BSE', type: 'num' },
    { key: 'total_volume', label: 'Total', type: 'num' },
    { key: 'avg_volume', label: `Avg${n}`, type: 'num' },
    { key: 'vol_chg_pct', label: 'Δ Tot', type: 'num' },
    { key: 'nse_chg_pct', label: 'Δ NSE', type: 'num' },
    { key: 'bse_chg_pct', label: 'Δ BSE', type: 'num' },
    { key: 'rvol', label: 'RVOL', type: 'num' },
    { key: 'nse_bse_ratio', label: 'Mix', type: 'num' },
    { key: 'spike', label: 'Spike', type: 'num' },
    { key: 'delivery', label: 'Delivery', type: 'num' },
    { key: 'delivery_pct', label: 'Del %', type: 'num' },
  ]
}

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
function withVolumeKpis(rows, rvolWindow = 50) {
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
  const spurtsBoard = useDesk((s) => s.boardsByDesk?.spurts?.board)
  const horizon = useDesk((s) => s.dossierHorizon)
  const setDossierHorizon = useDesk((s) => s.setDossierHorizon)
  const [xvolSort, setXvolSort] = useState({ key: 'date', dir: 'desc', type: 'text' })

  const rvolN = dossier?.tf_meta?.rvol_window ?? 50
  const xvolColsList = useMemo(() => xvolCols(rvolN), [rvolN])
  const xvolRaw = Array.isArray(dossier?.exchange_volume) ? dossier.exchange_volume : []
  const xvolRows = useMemo(() => {
    const enriched = withVolumeKpis(xvolRaw, rvolN).slice(-15)
    return sortRowsBy(enriched, xvolSort.key, xvolSort.dir, (bar) => {
      if (xvolSort.key === 'date') return bar.date || bar.label || ''
      if (xvolSort.key === 'spike') return bar.spike ? 1 : 0
      const v = bar[xvolSort.key]
      return v == null || Number.isNaN(Number(v)) ? null : Number(v)
    })
  }, [xvolRaw, xvolSort, rvolN])

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
  const xvol = xvolRaw
  const tech = dossier.tech || null
  const sci = dossier.sci || null
  const chart = dossier.chart || null
  const spurtsHits = (spurtsBoard?.rows || []).filter((row) => {
    const id = String(row.nse || row.id || '').toUpperCase()
    return id && id === String(sym || symbol || '').toUpperCase()
  })

  function toggleXvolSort(key, type) {
    setXvolSort((prev) =>
      prev.key === key
        ? { ...prev, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: type === 'text' ? 'asc' : 'desc', type },
    )
  }

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
      <div className="view-toggle dossier-horizon" role="group" aria-label="Trader horizon">
        <button type="button" className={horizon !== 'long' ? 'is-on' : ''} onClick={() => setDossierHorizon('day')}>
          Day
        </button>
        <button type="button" className={horizon === 'long' ? 'is-on' : ''} onClick={() => setDossierHorizon('long')}>
          Long
        </button>
        <span>
          {horizon === 'long'
            ? '5-year daily · 50/200 · trend · demand and supply · ADX'
            : '1-day window · RVOL · gap · candle · near support · Spurts'}
        </span>
      </div>
      <p className="dossier-blurb">
        {[
          chart?.at_demand
            ? 'Chart Demand'
            : chart?.at_supply
              ? 'Chart Supply'
              : chart?.range_pos_pct != null
                ? `Chart mid ${Number(chart.range_pos_pct).toFixed(0)}%`
                : null,
          chart?.score != null ? `Chart ${chart.score}` : null,
          stats.rvol != null ? `RVOL ${Number(stats.rvol).toFixed(2)}×` : null,
          tech?.bias ? `Tech ${tech.bias}` : null,
          spurtsHits.length
            ? 'Spurts ' +
              spurtsHits
                .map((hit) => `${hit.exchange} ${hit.vol_x != null ? Number(hit.vol_x).toFixed(1) + '×' : '—'}`)
                .join(' · ')
            : null,
        ]
          .filter(Boolean)
          .join(' · ') || 'Volume · Technical · Lab · Chart · Spurts'}
      </p>

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
            label="VolZ"
            value={stats.vol_z != null ? ((stats.vol_z >= 0 ? '+' : '') + Number(stats.vol_z).toFixed(1) + 'σ') : '—'}
            tone={stats.vol_z != null && stats.vol_z >= 2 ? 'pos' : stats.vol_z != null && stats.vol_z <= -1 ? 'neg' : ''}
          />
          <Metric
            label="Force"
            value={stats.force != null ? fmtNum(stats.force) : '—'}
            tone={scoreTone(stats.force)}
          />
          <Metric
            label="EMV"
            value={stats.emv != null ? Number(stats.emv).toFixed(2) : '—'}
            tone={scoreTone(stats.emv)}
          />
          <Metric
            label="VOsc"
            value={stats.vol_osc != null ? Number(stats.vol_osc).toFixed(1) + '%' : '—'}
            tone={scoreTone(stats.vol_osc)}
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
              <Metric label="PPO" value={tech.ppo_hist != null ? tech.ppo_hist.toFixed(3) : '—'} tone={scoreTone(tech.ppo_hist)} />
              <Metric label="SMA20" value={tech.sma20 != null ? fmtNum(tech.sma20) : '—'} />
              <Metric label="50/200" value={tech.sma50 != null && tech.sma200 != null ? (tech.sma50 > tech.sma200 ? 'Gold' : tech.sma50 < tech.sma200 ? 'Death' : 'flat') : '—'} tone={tech.sma50 != null && tech.sma200 != null ? (tech.sma50 > tech.sma200 ? 'pos' : tech.sma50 < tech.sma200 ? 'neg' : '') : ''} />
              <Metric label="Aroon" value={tech.aroon_osc != null ? tech.aroon_osc.toFixed(0) : '—'} tone={tech.aroon_osc != null && tech.aroon_osc >= 50 ? 'pos' : tech.aroon_osc != null && tech.aroon_osc <= -50 ? 'neg' : ''} />
              <Metric label="ADX" value={tech.adx != null ? Number(tech.adx).toFixed(0) : '—'} tone={tech.adx != null && tech.adx >= 25 ? 'pos' : ''} />
              <Metric label="EMA20" value={tech.ema20 != null ? fmtNum(tech.ema20) : '—'} />
              <Metric label="Stoch" value={tech.stoch_k != null ? tech.stoch_k.toFixed(0) : '—'} />
            </>
          ) : null}
        </DeskPanel>

        <DeskPanel title="Lab" empty={!sci ? 'No lab pattern for this TF.' : null}>
          {sci ? (
            <>
              <Metric
                label="Pattern"
                value={
                  sci.pattern === 'bull_breakout'
                    ? 'Breakout'
                    : sci.pattern === 'bull_base'
                      ? 'Bull base'
                      : sci.pattern === 'consolidating'
                        ? 'Coil'
                        : (sci.pattern || 'none').replace(/_/g, ' ')
                }
              />
              <Metric label="Score" value={sci.score != null ? String(sci.score) : '—'} tone={scoreTone(sci.score)} />
              <Metric
                label="Bullish"
                value={sci.bull_score != null ? Number(sci.bull_score).toFixed(0) : '—'}
              />
              <Metric
                label="Coil"
                value={sci.consol_score != null ? Number(sci.consol_score).toFixed(0) : '—'}
              />
              <Metric label="Range%" value={sci.range_pct != null ? sci.range_pct.toFixed(1) : '—'} />
              <Metric label="RVOL" value={sci.rvol != null ? sci.rvol.toFixed(1) + '×' : '—'} />
              <Metric label="CMF" value={sci.cmf != null ? sci.cmf.toFixed(2) : '—'} tone={scoreTone(sci.cmf)} />
              <Metric label="ATR%" value={sci.atr_pct != null ? sci.atr_pct.toFixed(2) + '%' : '—'} />
              <Metric label="Squeeze" value={sci.squeeze === true ? 'Yes' : sci.squeeze === false ? 'No' : '—'} />
              <Metric
                label="Lookback"
                value={
                  sci.periods
                    ? `D${sci.periods.donchian} · R${sci.periods.rvol} · CMF${sci.periods.cmf} · BB(${sci.periods.bb}) · ATR${sci.periods.atr}`
                    : sci.history || '—'
                }
              />
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
              <Metric
                label="Score"
                value={chart.score != null ? String(chart.score) : '—'}
                tone={
                  chart.score == null
                    ? ''
                    : chart.score >= 60
                      ? 'pos'
                      : chart.score <= 40
                        ? 'neg'
                        : ''
                }
              />
              <Metric label="Edge" value={chart.high_edge ? 'High' : '—'} tone={chart.high_edge ? 'pos' : ''} />
              <Metric
                label="Conf"
                value={
                  chart.confluence != null
                    ? (chart.confluence > 0 ? '+' : '') + String(chart.confluence)
                    : '—'
                }
                tone={chart.confluence != null && chart.confluence >= 2 ? 'pos' : chart.confluence != null && chart.confluence <= -2 ? 'neg' : ''}
              />
              <Metric label="Bias" value={chart.bias || '—'} />
              {Array.isArray(chart.edges) && chart.edges.length ? (
                <Metric label="Edges" value={chart.edges.slice(0, 6).join(' · ')} />
              ) : null}
              <Metric label="Trend" value={chart.trend || '—'} tone={chart.trend === 'up' ? 'pos' : chart.trend === 'down' ? 'neg' : ''} />
              <Metric
                label="Touches"
                value={
                  chart.trend_touches != null
                    ? `${chart.trend_touches}${chart.trend_valid ? ' ✓' : ''}`
                    : '—'
                }
              />
              <Metric
                label="Pattern"
                value={
                  (chart.pattern && chart.pattern !== 'none'
                    ? String(chart.pattern).replace(/_/g, ' ') + (chart.pattern_confirmed ? ' ✓' : '')
                    : '—')
                }
                tone={
                  chart.pattern_confirmed && String(chart.pattern || '').match(/bull|asc|bottom/)
                    ? 'pos'
                    : chart.pattern_confirmed && String(chart.pattern || '').match(/bear|desc|top/)
                      ? 'neg'
                      : ''
                }
              />
              <Metric
                label="Gap"
                value={
                  !chart.gap || chart.gap === 'none'
                    ? '—'
                    : String(chart.gap).replace(/_/g, ' ') + (chart.gap_pct != null ? ` ${Number(chart.gap_pct).toFixed(1)}%` : '')
                }
                tone={String(chart.gap || '').startsWith('up') ? 'pos' : String(chart.gap || '').startsWith('down') ? 'neg' : ''}
              />
              <Metric
                label="HL / LH"
                value={[chart.higher_lows ? 'HL' : null, chart.lower_highs ? 'LH' : null].filter(Boolean).join(' · ') || '—'}
                tone={chart.higher_lows ? 'pos' : chart.lower_highs ? 'neg' : ''}
              />
              <Metric label="Close" value={chart.close != null ? fmtNum(chart.close) : '—'} />
              <Metric label="Support" value={chart.support != null ? fmtNum(chart.support) : '—'} />
              <Metric label="Resist" value={chart.resistance != null ? fmtNum(chart.resistance) : '—'} />
              <Metric
                label="Demand"
                value={
                  chart.demand_lo != null && chart.demand_hi != null
                    ? `${fmtNum(chart.demand_lo)}–${fmtNum(chart.demand_hi)}`
                    : '—'
                }
                tone={chart.at_demand ? 'pos' : ''}
              />
              <Metric
                label="Supply"
                value={
                  chart.supply_lo != null && chart.supply_hi != null
                    ? `${fmtNum(chart.supply_lo)}–${fmtNum(chart.supply_hi)}`
                    : '—'
                }
                tone={chart.at_supply ? 'neg' : ''}
              />
              <Metric
                label="Loc"
                value={
                  chart.at_demand
                    ? 'Demand'
                    : chart.at_supply
                      ? 'Supply'
                      : chart.range_pos_pct != null
                        ? `Mid ${Number(chart.range_pos_pct).toFixed(0)}%`
                        : '—'
                }
                tone={chart.at_demand ? 'pos' : chart.at_supply ? 'neg' : ''}
              />
              <Metric
                label="Dist S%"
                value={chart.dist_support_pct != null ? chart.dist_support_pct.toFixed(2) + '%' : '—'}
                tone={chart.near_support ? 'pos' : ''}
              />
              <Metric
                label="Dist R%"
                value={chart.dist_resistance_pct != null ? chart.dist_resistance_pct.toFixed(2) + '%' : '—'}
                tone={chart.near_resistance ? 'neg' : ''}
              />
              <Metric
                label="S/R%"
                value={chart.range_width_pct != null ? Number(chart.range_width_pct).toFixed(1) : '—'}
              />
              <Metric label="Fib" value={chart.fib_nearest ? chart.fib_nearest + '%' : '—'} tone={chart.fib_zone ? 'pos' : ''} />
              <Metric label="Candle" value={(chart.candle || 'none').replace(/_/g, ' ')} />
              <Metric label="RVOL" value={chart.rvol != null ? chart.rvol.toFixed(1) + '×' : '—'} />
              <Metric
                label="Lookback"
                value={
                  [
                    chart.periods
                      ? `${chart.periods.sr_look || chart.periods.available || '—'} bars`
                      : null,
                    chart.history && chart.history !== 'full' ? chart.history : null,
                    chart.periods ? `RVOL ${chart.periods.rvol}` : null,
                  ]
                    .filter(Boolean)
                    .join(' · ') || '—'
                }
              />
              {chart.spark?.length > 1 ? (
                <div className="dossier-spark">
                  <Sparkline points={chart.spark} up={chart.spark_up !== false} />
                </div>
              ) : null}
            </>
          ) : null}
        </DeskPanel>

        <DeskPanel
          title="Spurts"
          empty={
            spurtsHits.length
              ? null
              : 'Not on the loaded Spurts list. Refresh Spurts to check today’s NSE and BSE gainers.'
          }
        >
          {spurtsHits.map((hit) => (
            <span key={(hit.exchange || '') + (hit.nse || hit.id || '')} style={{ display: 'contents' }}>
              <Metric
                label={`${hit.exchange || 'Vol'} ×`}
                value={hit.vol_x != null ? Number(hit.vol_x).toFixed(2) + '×' : '—'}
                tone={hit.vol_x != null && hit.vol_x >= 3 ? 'pos' : ''}
              />
              <Metric
                label="2W×"
                value={hit.exchange === 'BSE' ? '—' : hit.vol_x_2w != null ? Number(hit.vol_x_2w).toFixed(2) + '×' : '—'}
              />
              <Metric
                label="Chg"
                value={hit.change_pct != null ? (hit.change_pct >= 0 ? '+' : '') + Number(hit.change_pct).toFixed(1) + '%' : '—'}
                tone={hit.change_pct == null ? '' : hit.change_pct >= 0 ? 'pos' : 'neg'}
              />
              <Metric label="Score" value={hit.score != null ? String(hit.score) : '—'} tone={scoreTone(hit.score)} />
            </span>
          ))}
        </DeskPanel>
      </div>

      <div className="dossier-bars">
        <header className="dossier-panel-head">
          <h3>NSE · BSE volume</h3>
          <p className="dossier-xvol-note">
            Last 15 · Avg{rvolN} (ChartSchool RVOL) · Δ Tot/NSE/BSE · Mix · Spike ≥1.5× · Delivery
          </p>
        </header>
        {!xvol.length ? (
          <p className="empty">No NSE/BSE volume history for this symbol / timeframe.</p>
        ) : (
          <div className="tape dossier-xvol-tape">
            <table>
              <thead>
                <tr>
                  {xvolColsList.map((c) => (
                    <th key={c.key} title={c.label}>
                      <button
                        type="button"
                        className={'sort-btn' + (xvolSort.key === c.key ? ' is-on' : '')}
                        onClick={() => toggleXvolSort(c.key, c.type)}
                      >
                        {c.label}
                        {xvolSort.key === c.key ? (xvolSort.dir === 'asc' ? ' ↑' : ' ↓') : ''}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {xvolRows.map((bar, i) => (
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
