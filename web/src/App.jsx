import { useEffect } from 'react'
import DeskGuide from './components/DeskGuide'
import ScanProgress from './components/ScanProgress'
import Stage from './components/Stage'
import Toolbar from './components/Toolbar'
import TopBar from './components/TopBar'
import { useDesk } from './store'

export default function App() {
  const loadSources = useDesk((s) => s.loadSources)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      await loadSources(false)
      if (cancelled) return
      // Restore cached board only — never auto-scan. Refresh starts a run.
      const state = useDesk.getState()
      if (!state.board) {
        useDesk.setState({
          loading: false,
          status: state.boardsByDesk?.[state.desk]?.board
            ? `Cached · ready`
            : 'Ready · hit Refresh to scan',
        })
      }
    })()
    return () => {
      cancelled = true
    }
    // boot once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="shell">
      <div className="app">
        <TopBar />
        <Toolbar />
        <ScanProgress />
        <DeskGuide />
        <Stage />
      </div>
    </div>
  )
}
