import { useState } from 'react'
import { BOOK_GROUPS, TECH_CORE_IDS, TECH_INDICATORS, TF_GROUPS } from '../constants'
import { useDesk } from '../store'

function bookOptions(universes) {
  const list = (universes || []).filter((u) => u.id !== 'live' && u.id !== 'all')
  const byGroup = new Map()
  for (const u of list) {
    const g = u.group || 'Nifty'
    if (!byGroup.has(g)) byGroup.set(g, [])
    byGroup.get(g).push(u)
  }
  const ordered = []
  for (const g of BOOK_GROUPS) {
    const items = byGroup.get(g.id)
    if (items?.length) ordered.push({ group: g.label, items })
    byGroup.delete(g.id)
  }
  for (const [group, items] of byGroup) {
    if (items.length) ordered.push({ group, items })
  }
  return ordered
}

export default function Toolbar() {
  const desk = useDesk((s) => s.desk)
  const tf = useDesk((s) => s.tf)
  const boardTf = useDesk((s) => s.board?.timeframe)
  const universe = useDesk((s) => s.universe)
  const universes = useDesk((s) => s.universes)
  const techIndicators = useDesk((s) => s.techIndicators)
  const setTf = useDesk((s) => s.setTf)
  const setUniverse = useDesk((s) => s.setUniverse)
  const setTechIndicators = useDesk((s) => s.setTechIndicators)
  const applyTechFilter = useDesk((s) => s.applyTechFilter)
  const loadBoard = useDesk((s) => s.loadBoard)
  const loading = useDesk((s) => s.loading)
  const backToScan = useDesk((s) => s.backToScan)
  const mode = useDesk((s) => s.mode)
  const spurtsDate = useDesk((s) => s.spurtsDate)
  const spurtsArchives = useDesk((s) => s.spurtsArchives)
  const setSpurtsDate = useDesk((s) => s.setSpurtsDate)
  const archiveSpurtsToday = useDesk((s) => s.archiveSpurtsToday)
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(techIndicators)

  const hideTf = desk === 'spurts'
  // Highlight the TF the board actually returned (guards against stale/race UI).
  const activeTf =
    !hideTf && boardTf && String(boardTf).toLowerCase() === String(tf).toLowerCase()
      ? String(boardTf).toLowerCase()
      : String(tf || '1d').toLowerCase()
  return (
    <div className="chrome-bar">
      {!hideTf && (
        <div className="tf-panel" aria-label="Timeframe">
          {TF_GROUPS.map((group) => (
            <div key={group.id} className="tf-group">
              <span className="tf-group-label">{group.label}</span>
              <div className="tf-chips" role="group" aria-label={group.label}>
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={activeTf === item.id ? 'is-on' : ''}
                    title={item.label}
                    onClick={() => setTf(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="chrome-actions">
        {mode === 'symbol' && (
          <button type="button" className="chip-btn" onClick={backToScan} title="Back to dashboard">
            ← Dashboard
          </button>
        )}
        {desk === 'tech' && (
          <details
            className="ind-filter"
            open={open}
            onToggle={(e) => {
              setOpen(e.target.open)
              if (e.target.open) setDraft(techIndicators)
            }}
          >
            <summary title="Default: RSI · MACD · SMA 20/50 · EMA 20">
              Signals {techIndicators.length}/{TECH_INDICATORS.length}
            </summary>
            <div className="ind-filter-panel">
              <div className="ind-filter-list">
                {TECH_INDICATORS.map((item) => (
                  <label key={item.id}>
                    <input
                      type="checkbox"
                      checked={draft.includes(item.id)}
                      onChange={(e) => {
                        setDraft((prev) =>
                          e.target.checked ? [...prev, item.id] : prev.filter((id) => id !== item.id),
                        )
                      }}
                    />
                    {item.label}
                  </label>
                ))}
              </div>
              <div className="ind-filter-actions">
                <button type="button" onClick={() => setDraft([...TECH_CORE_IDS])} title="RSI · MACD · SMA · EMA">
                  Core
                </button>
                <button type="button" onClick={() => setDraft(TECH_INDICATORS.map((i) => i.id))}>
                  All
                </button>
                <button type="button" onClick={() => setDraft([])}>
                  None
                </button>
                <button
                  type="button"
                  className="is-primary"
                  onClick={() => {
                    setTechIndicators(draft)
                    setOpen(false)
                    applyTechFilter()
                  }}
                >
                  Apply
                </button>
              </div>
            </div>
          </details>
        )}
        {desk !== 'spurts' && (
          <label
            className="universe-label"
            title="Nifty · Cap · BSE Group A/B · NSE/BSE All · refreshed Monday 07:00 IST"
          >
            <span className="universe-tag">Book</span>
            <select value={universe} onChange={(e) => setUniverse(e.target.value)} aria-label="Book">
              {bookOptions(universes).map((block) => (
                <optgroup key={block.group} label={block.group}>
                  {block.items.map((u) => (
                    <option
                      key={u.id}
                      value={u.id}
                      title={
                        u.size != null
                          ? `${u.label} · ${u.size} names` +
                            (u.scanable != null ? ` · ${u.scanable} scanable` : '')
                          : u.label
                      }
                    >
                      {u.label}
                      {u.size != null ? ` · ${u.size}` : ''}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
        )}
        {desk === 'spurts' && (
          <label
            className="universe-label spurts-date-label"
            title="Live today, or an archived day from data/spurts_history/"
          >
            <span className="universe-tag">Date</span>
            <select
              value={spurtsDate || 'live'}
              onChange={(e) => setSpurtsDate(e.target.value)}
              aria-label="Spurts date"
            >
              <option value="live">Live · today</option>
              {(spurtsArchives || []).map((a) => (
                <option key={a.date} value={a.date}>
                  {a.date} · {a.count}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          type="button"
          className="chip-btn"
          onClick={() => loadBoard(true)}
          title="Rebuild this dashboard only and replace its cache"
        >
          {loading ? 'Running…' : 'Refresh'}
        </button>
        {desk === 'spurts' && spurtsDate === 'live' ? (
          <button
            type="button"
            className="chip-btn"
            onClick={() => archiveSpurtsToday(true)}
            title="Save today’s list as a flat file"
          >
            Save day
          </button>
        ) : null}
      </div>
    </div>
  )
}
