import { useEffect, useState } from 'react'

function horizHost(panel) {
  if (!panel) return null
  return (
    panel.querySelector('.scan-tape') ||
    panel.querySelector('.spurts-tape') ||
    panel.querySelector('.tape')
  )
}

export default function ScrollControls({ targetRef }) {
  const [canLeft, setCanLeft] = useState(false)
  const [canRight, setCanRight] = useState(false)

  useEffect(() => {
    const panel = targetRef?.current
    if (!panel) return undefined

    function sync() {
      const tape = horizHost(panel)
      if (!tape) {
        setCanLeft(false)
        setCanRight(false)
        return
      }
      const left = tape.scrollLeft
      const maxX = tape.scrollWidth - tape.clientWidth
      setCanLeft(left > 4)
      setCanRight(maxX > 8 && left < maxX - 4)
    }

    sync()
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(sync) : null
    ro?.observe(panel)

    let tapeRo = null
    let tapeEl = null
    function bindTape() {
      const next = horizHost(panel)
      if (next === tapeEl) return
      if (tapeEl) {
        tapeEl.removeEventListener('scroll', sync)
        tapeRo?.disconnect()
      }
      tapeEl = next
      if (tapeEl) {
        tapeEl.addEventListener('scroll', sync, { passive: true })
        tapeRo = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(sync) : null
        tapeRo?.observe(tapeEl)
        if (tapeEl.firstElementChild) tapeRo?.observe(tapeEl.firstElementChild)
      }
      sync()
    }
    bindTape()
    const mo = typeof MutationObserver !== 'undefined' ? new MutationObserver(bindTape) : null
    mo?.observe(panel, { childList: true, subtree: true })

    window.addEventListener('resize', sync)
    return () => {
      ro?.disconnect()
      mo?.disconnect()
      if (tapeEl) tapeEl.removeEventListener('scroll', sync)
      tapeRo?.disconnect()
      window.removeEventListener('resize', sync)
    }
  }, [targetRef])

  if (!canLeft && !canRight) return null

  const stepX = () => {
    const tape = horizHost(targetRef.current)
    return tape ? Math.max(180, tape.clientWidth * 0.7) : 220
  }

  return (
    <div className="scroll-controls" aria-label="Scroll columns">
      <button
        type="button"
        title="Scroll left"
        aria-label="Scroll left"
        disabled={!canLeft}
        onClick={() => {
          const tape = horizHost(targetRef.current)
          tape?.scrollBy({ left: -stepX(), behavior: 'smooth' })
        }}
      >
        ←
      </button>
      <button
        type="button"
        title="Scroll right"
        aria-label="Scroll right"
        disabled={!canRight}
        onClick={() => {
          const tape = horizHost(targetRef.current)
          tape?.scrollBy({ left: stepX(), behavior: 'smooth' })
        }}
      >
        →
      </button>
    </div>
  )
}
