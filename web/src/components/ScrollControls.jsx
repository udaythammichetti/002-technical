import { useEffect, useState } from 'react'

export default function ScrollControls({ targetRef }) {
  const [canUp, setCanUp] = useState(false)
  const [canDown, setCanDown] = useState(false)

  useEffect(() => {
    const el = targetRef?.current
    if (!el) return undefined

    function sync() {
      const top = el.scrollTop
      const max = el.scrollHeight - el.clientHeight
      setCanUp(top > 4)
      setCanDown(max > 8 && top < max - 4)
    }

    sync()
    el.addEventListener('scroll', sync, { passive: true })
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(sync) : null
    ro?.observe(el)
    window.addEventListener('resize', sync)
    return () => {
      el.removeEventListener('scroll', sync)
      ro?.disconnect()
      window.removeEventListener('resize', sync)
    }
  }, [targetRef])

  if (!canUp && !canDown) return null

  return (
    <div className="scroll-controls" aria-label="Scroll board">
      <button
        type="button"
        title="Scroll up"
        aria-label="Scroll up"
        disabled={!canUp}
        onClick={() => {
          const el = targetRef.current
          if (!el) return
          el.scrollBy({ top: -Math.max(240, el.clientHeight * 0.75), behavior: 'smooth' })
        }}
      >
        ↑
      </button>
      <button
        type="button"
        title="Scroll down"
        aria-label="Scroll down"
        disabled={!canDown}
        onClick={() => {
          const el = targetRef.current
          if (!el) return
          el.scrollBy({ top: Math.max(240, el.clientHeight * 0.75), behavior: 'smooth' })
        }}
      >
        ↓
      </button>
    </div>
  )
}
