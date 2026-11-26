import { useEffect, useRef, useState } from 'react'
import { DESKS } from '../constants'
import { useDesk } from '../store'
import { shortCompany } from '../utils'
import { DESK_ICONS, MarkIcon, PlayIcon } from './Icons'

export default function TopBar() {
  const desk = useDesk((s) => s.desk)
  const setDesk = useDesk((s) => s.setDesk)
  const mode = useDesk((s) => s.mode)
  const symbol = useDesk((s) => s.symbol)
  const query = useDesk((s) => s.query)
  const suggestions = useDesk((s) => s.suggestions)
  const sources = useDesk((s) => s.sources)
  const board = useDesk((s) => s.board)
  const setQuery = useDesk((s) => s.setQuery)
  const search = useDesk((s) => s.search)
  const openSymbol = useDesk((s) => s.openSymbol)
  const clearAllCache = useDesk((s) => s.clearAllCache)
  const cacheCount = useDesk((s) => Object.keys(s.boardsByDesk || {}).length)
  const timer = useRef(null)
  const inputRef = useRef(null)
  const searchWrap = useRef(null)
  const [focused, setFocused] = useState(false)
  const session = board?.session || sources?.session
  const sessionOpen = session?.state === 'open'
  const selectedQuery =
    mode === 'symbol' && query.trim().toUpperCase() === String(symbol || '').toUpperCase()

  useEffect(() => {
    clearTimeout(timer.current)
    if (!focused || selectedQuery) {
      return () => clearTimeout(timer.current)
    }
    timer.current = setTimeout(() => search(query), 220)
    return () => clearTimeout(timer.current)
  }, [query, search, focused, selectedQuery])

  function pick(item) {
    openSymbol(item)
    setFocused(false)
    inputRef.current?.blur()
  }

  function onSubmit(e) {
    e.preventDefault()
    const q = query.trim().toUpperCase()
    if (!q) return
    if (suggestions[0]) pick(suggestions[0])
    else pick({ nse: q, sc_id: '', name: '' })
  }

  const showSuggestions = focused && !selectedQuery && suggestions.length > 0 && query.trim()

  return (
    <header className="topbar">
      <h1 className="wordmark" title="Signal Desk">
        <span className="wordmark-ico" aria-hidden="true">
          <MarkIcon />
        </span>
        <span className="wordmark-title">Signal Desk</span>
        {session ? (
          <span
            className={'session-dot' + (sessionOpen ? ' open' : '')}
            title={session.detail || session.label}
          >
            {sessionOpen ? 'Live' : 'Closed'}
          </span>
        ) : null}
      </h1>

      <nav className="desk-nav" aria-label="Desks">
        {DESKS.map((d) => {
              const Icon = DESK_ICONS[d.id] || MarkIcon
              return (
            <button
              key={d.id}
              type="button"
              className={'desk-nav-link' + (desk === d.id ? ' is-on' : '')}
              aria-current={desk === d.id ? 'page' : undefined}
              aria-label={d.label}
              title={d.title || d.label}
              onClick={() => setDesk(d.id)}
            >
              <Icon />
              <span>{d.label}</span>
            </button>
          )
        })}
      </nav>

      <div className="topbar-actions">
        <div className="topbar-search" ref={searchWrap}>
          <form className="command" onSubmit={onSubmit} role="search">
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => {
                setTimeout(() => setFocused(false), 150)
              }}
              placeholder="Search all desks…"
              autoComplete="off"
              aria-label="Search symbol across Volume, Technical, Lab, Chart"
              aria-expanded={showSuggestions ? 'true' : 'false'}
              aria-autocomplete="list"
              title="Common search · opens combined Volume · Technical · Lab · Chart"
            />
            <button type="submit" title="Open combined signal" aria-label="Search">
              <PlayIcon />
            </button>
          </form>

          {showSuggestions ? (
            <div className="suggestions" role="listbox">
              {suggestions.slice(0, 8).map((item) => {
                const sym = (item.nse || '').toUpperCase()
                const name = shortCompany(item.name || '')
                return (
                  <button
                    key={(item.nse || '') + (item.sc_id || '')}
                    type="button"
                    role="option"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => pick(item)}
                  >
                    <span className="sug-sym">{sym}</span>
                    {name ? <span className="sug-name">{name}</span> : null}
                  </button>
                )
              })}
            </div>
          ) : null}
        </div>

        <button
          type="button"
          className="chip-btn topbar-cache-btn"
          onClick={() => {
            if (
              typeof window !== 'undefined' &&
              !window.confirm(
                cacheCount
                  ? `Clear all ${cacheCount} dashboard caches on this machine (and server)?`
                  : 'Clear all dashboard caches (machine + server)?',
              )
            ) {
              return
            }
            clearAllCache()
          }}
          title="Clear every dashboard cache (Volume · Technical · Lab · Chart · Candles)"
        >
          Clear all caches
          {cacheCount > 0 ? <span className="cache-count">{cacheCount}</span> : null}
        </button>
      </div>
    </header>
  )
}
