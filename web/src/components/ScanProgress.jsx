import { useDesk } from '../store'

const PHASE_LABEL = {
  starting: 'Starting',
  pending: 'Starting',
  quote: 'Quoting',
  enrich: 'Enriching',
  scan: 'Scanning',
  fetch: 'Fetching',
  done: 'Done',
  error: 'Error',
}

export default function ScanProgress() {
  const loading = useDesk((s) => s.loading)
  const boardInFlight = useDesk((s) => s.boardInFlight)
  const progress = useDesk((s) => s.scanProgress)
  const status = useDesk((s) => s.status)

  if (!loading && !boardInFlight) return null
  if (!progress && !loading) return null

  const done = Number(progress?.done) || 0
  const total = Number(progress?.total) || 0
  const pct = total > 0 ? Math.min(100, Number(progress?.pct) || Math.round((100 * done) / total)) : null
  const phase = PHASE_LABEL[progress?.phase] || progress?.phase || 'Running'
  const label = progress?.label || ''
  const indeterminate = !total

  return (
    <div className="scan-progress" role="status" aria-live="polite" aria-busy="true">
      <div className="scan-progress-row">
        <span className="scan-progress-phase">{phase}</span>
        {label ? <span className="scan-progress-label">{label}</span> : null}
        <span className="scan-progress-count">
          {total > 0 ? `${done} / ${total}` : done > 0 ? `${done}` : '…'}
          {pct != null ? ` · ${pct}%` : ''}
        </span>
      </div>
      <div className={'scan-progress-track' + (indeterminate ? ' is-indeterminate' : '')}>
        <div
          className="scan-progress-fill"
          style={indeterminate ? undefined : { width: `${pct || 0}%` }}
        />
      </div>
      {status ? <p className="scan-progress-status">{status}</p> : null}
    </div>
  )
}
