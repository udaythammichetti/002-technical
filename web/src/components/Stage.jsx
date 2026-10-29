import { useRef } from 'react'
import { FOOT, TABS } from '../constants'
import { useDesk } from '../store'
import { filterRows } from '../utils'
import BoardMeta from './BoardMeta'
import LabDashboard from './LabDashboard'
import ScrollControls from './ScrollControls'
import SpurtsDashboard from './SpurtsDashboard'
import SpurtsTable from './SpurtsTable'
import CombinedDossier from './CombinedDossier'
import ScanTable from './ScanTable'

export default function Stage() {
  const panelRef = useRef(null)
  const desk = useDesk((s) => s.desk)
  const mode = useDesk((s) => s.mode)
  const tab = useDesk((s) => s.tab)
  const board = useDesk((s) => s.board)
  const loading = useDesk((s) => s.loading)
  const setTab = useDesk((s) => s.setTab)

  const tabs = TABS[desk] || TABS.volume

  // Common search → one combined page (Volume · Technical · Lab · Chart). Spurts excluded.
  if (mode === 'symbol') {
    return (
      <main className="stage">
        <div className="panel" ref={panelRef}>
          <CombinedDossier />
        </div>
        <ScrollControls targetRef={panelRef} />
        <footer className="foot">
          <p>Combined signal · Volume · Technical · Lab · Chart · Spurts · research only</p>
        </footer>
      </main>
    )
  }

  const rows = board?.rows || []
  const filtered = filterRows(rows, desk, tab)

  return (
    <main className="stage">
      <div className="stage-chrome">
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
      </div>
      <div className="panel" ref={panelRef} aria-live="polite">
        {loading && !board && (
          <p className="empty">
            {desk === 'spurts' ? 'Loading live NSE / BSE volume spurts…' : 'Running model…'}
          </p>
        )}
        {!loading && !board && (
          <p className="empty">No scan yet · pick timeframe / book, then hit Refresh.</p>
        )}
        {board && <BoardMeta />}
        {board && desk === 'sci' && <LabDashboard />}
        {desk === 'spurts' && <SpurtsDashboard />}
        {board &&
          (filtered.length ? (
            desk === 'spurts' ? (
              <SpurtsTable rows={filtered} />
            ) : (
              <ScanTable rows={filtered} />
            )
          ) : (
            <p className="empty">No names in this view.</p>
          ))}
      </div>
      <ScrollControls targetRef={panelRef} />
      <footer className="foot">
        <p>{FOOT[desk] || FOOT.volume}</p>
      </footer>
    </main>
  )
}
