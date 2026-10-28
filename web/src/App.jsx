import { useEffect } from 'react'
import { BOARD_POLL_MS, SPURT_POLL_MS } from './constants'
import DeskGuide from './components/DeskGuide'
import Rail from './components/Rail'
import Stage from './components/Stage'
import Toolbar from './components/Toolbar'
import TopBar from './components/TopBar'
import { useDesk } from './store'

export default function App() {
  const desk = useDesk((s) => s.desk)
  const mode = useDesk((s) => s.mode)
  const spurtsDate = useDesk((s) => s.spurtsDate)
  const loadSources = useDesk((s) => s.loadSources)
  const loadBoard = useDesk((s) => s.loadBoard)
  const loadSpurtsHistory = useDesk((s) => s.loadSpurtsHistory)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      await loadSources(false)
      if (cancelled) return
      // Machine cache already restored by persist merge — only fetch if empty.
      const state = useDesk.getState()
      if (!state.board) await loadBoard(false)
    })()
    return () => {
      cancelled = true
    }
    // boot once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (desk !== 'spurts') return undefined
    loadSpurtsHistory()
    return undefined
  }, [desk, loadSpurtsHistory])

  useEffect(() => {
    // Soft polls only when this report is not already saved on the machine.
    // Refresh / Clear cache are the only ways to rebuild.
    if (mode !== 'scan') return undefined
    if (desk === 'spurts' && spurtsDate !== 'live') return undefined
    const ms = desk === 'spurts' ? SPURT_POLL_MS : BOARD_POLL_MS
    const id = setInterval(() => {
      if (document.hidden) return
      loadBoard(false, { silent: true })
    }, ms)
    return () => clearInterval(id)
  }, [desk, mode, spurtsDate, loadBoard])

  return (
    <div className="shell">
      <Rail />
      <div className="app">
        <TopBar />
        <Toolbar />
        <DeskGuide />
        <Stage />
      </div>
    </div>
  )
}
