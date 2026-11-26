import { useDesk } from '../store'

/** Compact status line for Volume / Technical / Lab / Chart. */
export default function BoardMeta() {
  const board = useDesk((s) => s.board)
  const desk = useDesk((s) => s.desk)
  if (!board || (desk !== 'volume' && desk !== 'tech' && desk !== 'sci' && desk !== 'chart' && desk !== 'candle')) return null

  const counts = board.counts || {}
  const vol = board.tf_meta?.volume
  const tech = board.tf_meta?.tech
  const lab = board.tf_meta?.lab
  const chart = board.tf_meta?.chart
  const cmfN = vol?.cmf ?? board.tf_meta?.avg_window
  const rvolN = vol?.rvol ?? board.tf_meta?.rvol_window
  const parts = [
    board.universe_label,
    board.timeframe_label,
    desk === 'volume' && rvolN != null ? `RVOL=${rvolN}` : null,
    desk === 'volume' && cmfN != null ? `CMF=${cmfN}` : null,
    desk === 'volume' && vol?.mfi != null ? `MFI=${vol.mfi}` : null,
    desk === 'volume' && vol?.chaikin != null ? `ChOsc=${vol.chaikin}` : null,
    desk === 'volume' && vol?.pvo != null ? `PVO=${vol.pvo}` : null,
    desk === 'tech' && tech?.rsi != null ? `RSI=${tech.rsi}` : null,
    desk === 'tech' && tech?.ppo != null ? `PPO=${tech.ppo}` : null,
    desk === 'tech' && tech?.sma200 != null ? `50/200=${tech.sma200}` : null,
    desk === 'tech' && tech?.aroon != null ? `Aroon=${tech.aroon}` : null,
    desk === 'tech' && tech?.adx != null ? `ADX=${tech.adx}` : null,
    desk === 'sci' && lab?.donchian != null ? `Donchian=${lab.donchian}` : null,
    desk === 'sci' && lab?.rvol != null ? `RVOL=${lab.rvol}` : null,
    desk === 'sci' && lab?.cmf != null ? `CMF=${lab.cmf}` : null,
    desk === 'sci' && lab?.bb != null ? `BB=${lab.bb}` : null,
    desk === 'sci' && lab?.atr != null ? `ATR=${lab.atr}` : null,
    desk === 'sci' && lab?.break_rvol != null ? `break≥${lab.break_rvol}×` : null,
    desk === 'chart' && chart?.sr != null ? `S/R=${chart.sr}` : null,
    desk === 'chart' && chart?.rvol != null ? `RVOL=${chart.rvol}` : null,
    desk === 'chart' && chart?.near_pct != null ? `near≤${chart.near_pct}%` : null,
    desk === 'chart' && chart?.gap_rvol != null ? `gap≥${chart.gap_rvol}×` : null,
    desk === 'chart' && chart?.trend_touches != null ? `trend≥${chart.trend_touches}` : null,
    desk === 'candle' && board.dashboard?.avg_score != null
      ? `avg ${(board.dashboard.avg_score > 0 ? '+' : '') + board.dashboard.avg_score}/9`
      : null,
    desk === 'candle' && counts.aligned != null ? `${counts.aligned} aligned` : null,
    desk === 'candle' && counts.turn_bull != null ? `${counts.turn_bull} turn↑` : null,
    desk === 'candle' && counts.turn_bear != null ? `${counts.turn_bear} turn↓` : null,
    board.scanned != null
      ? `${board.scanned}/${board.universe_size || board.universe_scanable || board.scanned}`
      : null,
    board.errors != null && board.errors > 0 ? `${board.errors} miss` : null,
    counts.bullish != null ? `${counts.bullish}↑` : null,
    counts.bearish != null ? `${counts.bearish}↓` : null,
    desk === 'candle' && counts.neutral != null ? `${counts.neutral} flat` : null,
    board.cached ? 'cached' : null,
  ].filter(Boolean)

  if (!parts.length) return null
  return <p className="board-meta">{parts.join(' · ')}</p>
}
