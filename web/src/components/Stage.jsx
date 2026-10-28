import { useRef } from 'react'
import { FOOT, TABS } from '../constants'
import { useDesk } from '../store'
import { filterRows } from '../utils'
import BoardFilters from './BoardFilters'
import BoardMeta from './BoardMeta'
import ChartDashboard from './ChartDashboard'
import LabDashboard from './LabDashboard'
import ScrollControls from './ScrollControls'
import SpurtsDashboard from './SpurtsDashboard'
import SpurtsTable from './SpurtsTable'
import CombinedDossier from './CombinedDossier'
import StockGrid from './StockGrid'

export default function Stage() {
  const panelRef = useRef(null)
  const desk = useDesk((s) => s.desk)
  const mode = useDesk((s) => s.mode)
  const tab = useDesk((s) => s.tab)
  const board = useDesk((s) => s.board)
  const loading = useDesk((s) => s.loading)
  const setTab = useDesk((s) => s.setTab)
  const nameFilter = useDesk((s) => s.nameFilter)
  const strengthFilter = useDesk((s) => s.strengthFilter)
  const minRvol = useDesk((s) => s.minRvol)
  const minVolX = useDesk((s) => s.minVolX)
  const chartPattern = useDesk((s) => s.chartPattern)
  const chartSetup = useDesk((s) => s.chartSetup)
  const chartTrend = useDesk((s) => s.chartTrend)
  const chartGap = useDesk((s) => s.chartGap)
  const chartFib = useDesk((s) => s.chartFib)
  const chartCandle = useDesk((s) => s.chartCandle)

  const tabs = TABS[desk] || TABS.volume
  const filters = {
    nameFilter,
    strengthFilter,
    minRvol,
    minVolX,
    chartPattern,
    chartSetup,
    chartTrend,
    chartGap,
    chartFib,
    chartCandle,
  }

  // Common search → one combined page (Volume · Technical · Lab · Chart). Spurts excluded.
  if (mode === 'symbol') {
    return (
      <main className="stage">
        <div className="panel" ref={panelRef}>
          <CombinedDossier />
        </div>
        <ScrollControls targetRef={panelRef} />
        <footer className="foot">
          <p>Combined signal · Volume · Technical · Lab · Chart · research only</p>
        </footer>
      </main>
    )
  }

  const rows = board?.rows || []
  const tabFiltered = filterRows(rows, desk, tab, {})
  const filtered = filterRows(rows, desk, tab, filters)

  return (
    <main className="stage">
      <div className="tabs" role="tablist" aria-label="Signal views">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? 'is-on' : ''}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="panel" ref={panelRef} aria-live="polite">
        {loading && !board && (
          <p className="empty">
            {desk === 'spurts' ? 'Loading live NSE / BSE volume spurts…' : 'Running model…'}
          </p>
        )}
        {!loading && !board && <p className="empty">No board data.</p>}
        {board && <BoardMeta />}
        {board && desk === 'sci' && <LabDashboard />}
        {board && desk === 'chart' && <ChartDashboard />}
        {desk === 'spurts' && <SpurtsDashboard />}
        {board && <BoardFilters shown={filtered.length} total={tabFiltered.length} />}
        {board &&
          (filtered.length ? (
            desk === 'spurts' ? (
              <SpurtsTable rows={filtered} />
            ) : (
              <StockGrid rows={filtered} />
            )
          ) : (
            <p className="empty">No names match this filter.</p>
          ))}
      </div>
      <ScrollControls targetRef={panelRef} />
      <footer className="foot">
        <p>{FOOT[desk] || FOOT.volume}</p>
      </footer>
    </main>
  )
}
