import { useDesk } from '../store'

/** Compact status line for Volume / Technical (no KPI dashboard). */
export default function BoardMeta() {
  const board = useDesk((s) => s.board)
  const desk = useDesk((s) => s.desk)
  if (!board || (desk !== 'volume' && desk !== 'tech')) return null

  const counts = board.counts || {}
  const parts = [
    board.universe_label,
    board.timeframe_label,
    board.scanned != null
      ? `${board.scanned}${board.universe_size ? `/${board.universe_size}` : ''}`
      : null,
    counts.bullish != null ? `${counts.bullish}↑` : null,
    counts.bearish != null ? `${counts.bearish}↓` : null,
    board.cached ? 'cached' : null,
  ].filter(Boolean)

  if (!parts.length) return null
  return <p className="board-meta">{parts.join(' · ')}</p>
}
