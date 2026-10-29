import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  CHART_DEFAULT_TF,
  DESKS,
  INTRADAY_TF_IDS,
  TECH_CORE_IDS,
  TECH_INDICATOR_IDS,
  TIMEFRAMES,
  UNIVERSES,
} from './constants'

function deskLabel(id) {
  return (DESKS.find((d) => d.id === id) || {}).label || id
}
import * as api from './api'

const defaultIndicators = [...TECH_CORE_IDS]
/** Pre-upgrade defaults — migrate stale saved sets → current TECH_CORE. */
const LEGACY_TECH_CORES = [
  ['rsi', 'macd', 'sma', 'ema'],
  ['rsi', 'macd', 'sma', 'ema', 'stoch', 'adx', 'bb', 'roc'],
]
const TF_SET = new Set(TIMEFRAMES)
const TF_ALIASES = {
  d: '1d',
  day: '1d',
  daily: '1d',
  '1day': '1d',
  '1D': '1d',
  '1d_full': '1df',
  '1dfull': '1df',
  dfull: '1df',
  daily_full: '1df',
  '1d_2y': '1d2',
  '1d2y': '1d2',
  daily_2y: '1d2',
  '1d_3y': '1d3',
  '1d3y': '1d3',
  daily_3y: '1d3',
  '1d_4y': '1d4',
  '1d4y': '1d4',
  daily_4y: '1d4',
  '1d_5y': '1d5',
  '1d5y': '1d5',
  daily_5y: '1d5',
  w: '1w',
  week: '1w',
  weekly: '1w',
  mo: '1m',
  month: '1m',
  monthly: '1m',
  '60m': '1h',
  '3mo': '3m',
  '6mo': '6m',
  '12m': '1y',
}

function clampTechIndicators(list) {
  const allow = new Set(TECH_INDICATOR_IDS)
  const picked = (list || []).filter((id) => allow.has(id))
  if (!picked.length) return [...TECH_CORE_IDS]
  const key = [...picked].sort().join(',')
  // Old saved defaults — lift to current high-value ChartSchool core
  for (const legacy of LEGACY_TECH_CORES) {
    if (key === [...legacy].sort().join(',')) return [...TECH_CORE_IDS]
  }
  return picked
}

function clampTf(tf) {
  const raw = String(tf || '1d')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
  const id = TF_ALIASES[raw] || TF_ALIASES[String(tf || '').trim()] || raw
  return TF_SET.has(id) ? id : '1d'
}

/** Chart patterns use Swing/Long bars only — snap Intraday → 1D. */
function clampTfForDesk(desk, tf) {
  const id = clampTf(tf)
  if (desk === 'chart' && INTRADAY_TF_IDS.has(id)) return CHART_DEFAULT_TF
  return id
}

function clampUniverse(id, list) {
  const ids = (list || []).map((u) => u.id).filter((x) => x !== 'live')
  if (id === 'all' || id === 'live') return ids.includes('nse_all') ? 'nse_all' : ids[0] || 'nifty50'
  if (ids.includes(id)) return id
  return ids.includes('nifty50') ? 'nifty50' : ids[0] || 'nifty50'
}

function clampDeskTab(desk, tab) {
  const allowed = {
    // `bars` / `chart` = Volume symbol detail (Map / Bars views)
    volume: new Set(['trend', 'bullish', 'bearish', 'spike', 'bars', 'chart']),
    tech: new Set(['trend', 'bullish', 'bearish']),
    sci: new Set(['trend', 'bullish', 'consolidating', 'breakout']),
    chart: new Set(['trend', 'bullish', 'bearish', 'breakout', 'support']),
    spurts: new Set(['trend', 'nse', 'bse', 'spike']),
  }
  const set = allowed[desk] || allowed.volume
  if (set.has(tab)) return tab
  return 'trend'
}

const DESK_CACHE_IDS = new Set(['volume', 'tech', 'sci', 'chart', 'spurts'])

/** One machine-cache slot per dashboard (desk). */
function readDeskCache(map, desk) {
  const hit = map && map[desk]
  if (!hit || !hit.board) return null
  return hit
}

function dropDeskCache(map, desk) {
  const next = { ...(map || {}) }
  delete next[desk]
  return next
}

function migrateBoardsByDesk(raw) {
  if (!raw || typeof raw !== 'object') return {}
  const out = {}
  for (const [k, v] of Object.entries(raw)) {
    if (!v || !v.board) continue
    if (DESK_CACHE_IDS.has(k)) {
      out[k] = v
      continue
    }
    // Legacy keys: "desk|tf|universe|…"
    const desk = String(k).split('|')[0]
    if (DESK_CACHE_IDS.has(desk) && !out[desk]) {
      out[desk] = {
        board: v.board,
        at: v.at || Date.now(),
        tf: v.tf,
        universe: v.universe,
        spurtsDate: v.spurtsDate,
        techIndicators: v.techIndicators,
      }
    }
  }
  return out
}

function stashDeskCache(map, desk, entry) {
  return { ...(map || {}), [desk]: { ...entry, at: Date.now() } }
}

export const useDesk = create(
  persist(
    (set, get) => ({
      desk: 'volume',
      mode: 'scan',
      symbol: '',
      scId: '',
      query: '',
      suggestions: [],
      searchEpoch: 0, // bumps to drop stale autosuggest results
      boardEpoch: 0, // bumps to drop stale board/symbol responses (TF/desk races)
      tf: '1d',
      universe: 'nifty50', // shared across Volume · Technical · Lab · Chart (not Spurts)
      universes: UNIVERSES.map((u) => ({ ...u })).filter((u) => u.id !== 'live'),
      tab: 'trend',
      /** Scan desks: dense table by default (cards optional). */
      boardView: 'table', // table | cards
      sortKey: 'score',
      sortDir: 'desc',
      techIndicators: defaultIndicators,
      spurtsDate: 'live', // live | YYYY-MM-DD archive
      /** Symbol search window. Day = 1D session. Long = 5-year daily. */
      dossierHorizon: 'day',
      spurtsArchives: [],
      sources: null,
      board: null,
      /** One persisted cache slot per dashboard until Refresh (that desk) or Clear all. */
      boardsByDesk: {},
      data: null,
      /** Combined Volume+Tech+Lab+Chart page from common search (no Spurts). */
      dossier: null,
      status: 'Warming engine…',
      loading: false,
      error: null,
      boardInFlight: false,
      _boardAbort: null,
      /** Live Refresh progress from /api/scan-progress. */
      scanProgress: null,
      _progressTimer: null,

      setDesk(desk) {
        const sortKey =
          desk === 'spurts' ? 'vol_x' : desk === 'sci' || desk === 'chart' ? 'rank' : 'score'
        const sortDir = desk === 'sci' || desk === 'chart' ? 'asc' : desk === 'spurts' ? 'desc' : 'desc'
        const cached = readDeskCache(get().boardsByDesk, desk)
        const tf = clampTfForDesk(desk, cached?.tf || get().tf)
        const universe = cached?.universe
          ? clampUniverse(cached.universe, get().universes)
          : get().universe
        const spurtsDate =
          desk === 'spurts' ? cached?.spurtsDate || get().spurtsDate || 'live' : 'live'
        const techIndicators =
          desk === 'tech' && Array.isArray(cached?.techIndicators)
            ? clampTechIndicators(cached.techIndicators)
            : get().techIndicators
        set({
          desk,
          mode: 'scan',
          tab: 'trend',
          tf,
          universe,
          techIndicators,
          sortKey,
          sortDir,
          board: cached ? cached.board : null,
          data: null,
          query: '',
          suggestions: [],
          boardEpoch: get().boardEpoch + 1,
          spurtsDate,
          error: null,
          loading: false,
          status: cached
            ? `Cached · ${deskLabel(desk)} dashboard`
            : `Ready · ${deskLabel(desk)} · hit Refresh to scan`,
        })
        if (cached) get()._statusFromBoard(cached.board)
        if (desk === 'spurts') get().loadSpurtsHistory()
      },

      setSpurtsDate(date) {
        const next = date && date !== 'live' ? String(date) : 'live'
        const cached = readDeskCache(get().boardsByDesk, 'spurts')
        const same = cached && (cached.spurtsDate || 'live') === next
        if (same) {
          set({
            spurtsDate: next,
            board: cached.board,
            boardEpoch: get().boardEpoch + 1,
            loading: false,
            error: null,
          })
          get()._statusFromBoard(cached.board)
          return
        }
        // Selection only — Refresh loads the chosen day.
        set({
          spurtsDate: next,
          board: cached ? cached.board : get().board,
          boardEpoch: get().boardEpoch + 1,
          loading: false,
          error: null,
          status:
            next === 'live'
              ? 'Date · Live today · hit Refresh to load'
              : `Date · ${next} · hit Refresh to load`,
        })
      },

      async loadSpurtsHistory() {
        try {
          const data = await api.fetchSpurtsHistory()
          set({ spurtsArchives: data.archives || [] })
          return data
        } catch {
          return null
        }
      },

      async archiveSpurtsToday(force = false) {
        set({ status: 'Saving today’s spurts archive…', loading: true })
        try {
          const result = await api.archiveSpurtsToday(force)
          await get().loadSpurtsHistory()
          set({
            loading: false,
            status: result.saved
              ? `Archived ${result.count} names · ${result.date}`
              : result.detail || result.reason || 'Archive skipped',
          })
          if (get().spurtsDate === 'live') get().loadBoard(true)
          return result
        } catch (err) {
          set({ loading: false, error: err.message, status: err.message || 'Archive failed' })
          return null
        }
      },

      setTf(tf) {
        const next = clampTfForDesk(get().desk, tf)
        const label = String(next).toUpperCase()
        const desk = get().desk
        const cached = readDeskCache(get().boardsByDesk, desk)
        const same = cached && clampTf(cached.tf || '') === next
        const { mode } = get()
        // Selection only — keep showing current board until Refresh.
        set({
          tf: next,
          data: null,
          error: null,
          loading: false,
          ...(same && cached ? { board: cached.board } : {}),
          status:
            same
              ? `Cached · ${label}`
              : mode === 'symbol'
                ? `Timeframe · ${label} · hit Search to reload`
                : `Timeframe · ${label} · hit Refresh to scan`,
        })
        if (same && cached) get()._statusFromBoard(cached.board)
      },

      setUniverse(universe) {
        const uid = clampUniverse(universe, get().universes)
        const desk = get().desk
        const cached = readDeskCache(get().boardsByDesk, desk)
        const same = cached && clampUniverse(cached.universe || '', get().universes) === uid
        const uLabel =
          (get().universes || []).find((u) => u.id === uid)?.label || uid
        set({
          universe: uid,
          mode: 'scan',
          tab: 'trend',
          query: '',
          error: null,
          loading: false,
          ...(same && cached ? { board: cached.board } : {}),
          status: same
            ? `Cached · ${uLabel}`
            : `Book · ${uLabel} · hit Refresh to scan`,
        })
        if (same && cached) get()._statusFromBoard(cached.board)
      },

      setTab(tab) {
        set({ tab: clampDeskTab(get().desk, tab) })
      },

      setBoardView(view) {
        set({ boardView: view === 'cards' ? 'cards' : 'table' })
      },

      setTechIndicators(techIndicators) {
        set({ techIndicators: clampTechIndicators(techIndicators) })
      },

      applyTechFilter() {
        // Apply only updates the signal set — Refresh runs the scan.
        set({
          mode: 'scan',
          tab: 'trend',
          loading: false,
          error: null,
          status: `Signals · ${get().techIndicators.length} selected · hit Refresh to scan`,
        })
      },

      setSort(key, type) {
        const { sortKey, sortDir } = get()
        if (sortKey === key) {
          set({ sortDir: sortDir === 'asc' ? 'desc' : 'asc' })
        } else {
          set({
            sortKey: key,
            sortDir: type === 'text' || key === 'rank' ? 'asc' : 'desc',
          })
        }
      },

      setQuery(query) {
        set({ query })
      },

      async search(query) {
        if (!query || query.trim().length < 1) {
          set({ suggestions: [] })
          return
        }
        const epoch = get().searchEpoch
        try {
          const results = await api.searchSymbols(query.trim())
          // Drop stale responses (e.g. after a card click / Enter selection).
          if (get().searchEpoch !== epoch) return
          set({ suggestions: results })
        } catch {
          if (get().searchEpoch === epoch) set({ suggestions: [] })
        }
      },

      openSymbol(item) {
        const symbol = (item.nse || item.symbol || get().query || '').toString().trim().toUpperCase()
        const label = item.name || item.label || symbol
        const exchange = (item.exchange || 'NSE').toString().toUpperCase()
        try {
          get()._boardAbort?.abort()
        } catch {
          /* ignore */
        }
        // Common search → combined dossier (all desks except Spurts). Keep current desk.
        set({
          mode: 'symbol',
          symbol,
          scId: item.sc_id || '',
          query: symbol,
          suggestions: [],
          searchEpoch: get().searchEpoch + 1,
          boardEpoch: get().boardEpoch + 1,
          tab: 'trend',
          data: null,
          dossier: null,
          loading: true,
          boardInFlight: false,
          _boardAbort: null,
          error: null,
          status: `Combined signal · ${symbol}${label && label !== symbol ? ' · ' + label : ''}…`,
        })
        get().loadDossier(true, { exchange })
      },

      backToScan() {
        const desk = get().desk === 'spurts' ? 'spurts' : get().desk
        const cached = readDeskCache(get().boardsByDesk, desk)
        set({
          mode: 'scan',
          tab: 'trend',
          data: null,
          dossier: null,
          query: '',
          suggestions: [],
          searchEpoch: get().searchEpoch + 1,
          board: cached ? cached.board : get().board,
          loading: false,
          status: cached
            ? `Cached · ${deskLabel(desk)} dashboard`
            : `Ready · ${deskLabel(desk)} · hit Refresh to scan`,
        })
        if (cached) get()._statusFromBoard(cached.board)
      },

      async clearAllCache() {
        try {
          await api.clearServerCache()
        } catch {
          /* still clear local even if server is down */
        }
        const n = Object.keys(get().boardsByDesk || {}).length
        try {
          get()._boardAbort?.abort()
        } catch {
          /* ignore */
        }
        set({
          boardsByDesk: {},
          board: null,
          data: null,
          dossier: null,
          boardEpoch: get().boardEpoch + 1,
          error: null,
          loading: false,
          boardInFlight: false,
          _boardAbort: null,
          status: n
            ? `Cleared ${n} dashboard caches · hit Refresh to scan`
            : 'All dashboard caches cleared · hit Refresh to scan',
        })
      },

      async loadSources(fresh = false) {
        try {
          const sources = await api.fetchSources(fresh)
          const apiUniverses = Array.isArray(sources?.universes)
            ? sources.universes
                .filter((u) => u?.id && u.id !== 'all')
                .map((u) => {
                  const local = UNIVERSES.find((x) => x.id === u.id) || {}
                  return {
                    id: u.id,
                    short: local.short || u.id,
                    label: u.label || local.label || u.id,
                    group: u.group || local.group || 'Nifty',
                    size: u.size,
                    scanable: u.scanable,
                  }
                })
            : null
          // Prefer canonical Book order from constants when API returns the same set.
          const order = new Map(UNIVERSES.map((u, i) => [u.id, i]))
          const universes = (apiUniverses?.length ? apiUniverses : get().universes)
            .slice()
            .sort((a, b) => (order.get(a.id) ?? 999) - (order.get(b.id) ?? 999))
          const universe = clampUniverse(get().universe, universes)
          set({ sources, universes, universe })
          return sources
        } catch (err) {
          set({ status: err.message || 'Source check failed' })
          return null
        }
      },

      async loadBoard(fresh = false, opts = {}) {
        const silent = Boolean(opts && opts.silent)
        // Soft polls must not stack on an active fetch.
        if (silent && get().boardInFlight) return
        const epoch = get().boardEpoch
        const desk = get().desk
        const spurtsDate = get().spurtsDate || 'live'
        let tf
        let universe
        let indicators = get().techIndicators
        if (silent) {
          tf = clampTfForDesk(desk, get().tf)
          universe = get().universe
        } else {
          tf = clampTfForDesk(desk, get().tf)
          if (tf !== get().tf) set({ tf })
          universe = clampUniverse(get().universe, get().universes)
          if (universe !== get().universe) set({ universe })
          indicators = desk === 'tech' ? clampTechIndicators(get().techIndicators) : get().techIndicators
          if (desk === 'tech' && indicators.join(',') !== get().techIndicators.join(',')) {
            set({ techIndicators: indicators })
          }
        }
        // One cache per dashboard — soft polls skip when that desk is already saved.
        if (silent && readDeskCache(get().boardsByDesk, desk)) return
        if (fresh) {
          set({ boardsByDesk: dropDeskCache(get().boardsByDesk, desk) })
        }
        const tfLabel =
          (get().sources?.timeframes || []).find((t) => t.id === tf)?.label || String(tf).toUpperCase()
        const hasBoard = Boolean(get().board)
        // Cancel prior in-flight board for this UI slot so desk switches aren't blocked.
        try {
          get()._boardAbort?.abort()
        } catch {
          /* ignore */
        }
        const abort = typeof AbortController !== 'undefined' ? new AbortController() : null
        if (get()._progressTimer) {
          clearInterval(get()._progressTimer)
          set({ _progressTimer: null })
        }
        const job = desk === 'spurts' ? null : api.newScanJobId()
        const startStatus =
          desk === 'spurts'
            ? spurtsDate !== 'live'
              ? `Loading spurts archive · ${spurtsDate}…`
              : 'Fetching live NSE / BSE volume spurts…'
            : desk === 'tech'
              ? `Scanning Technical · ${tfLabel}…`
              : desk === 'sci'
                ? `Scanning Lab · ${tfLabel}…`
                : desk === 'chart'
                  ? `Scanning Chart · ${tfLabel}…`
                  : `Scanning Volume · ${tfLabel}…`
        if (!silent) {
          set({
            loading: true,
            boardInFlight: true,
            _boardAbort: abort,
            error: null,
            status: startStatus,
            scanProgress: job
              ? { job, state: 'pending', done: 0, total: 0, pct: 0, phase: 'starting', label: '' }
              : { state: 'running', done: 0, total: 0, pct: 0, phase: 'fetch', label: 'Spurts' },
          })
        } else {
          set({ error: null, boardInFlight: true, _boardAbort: abort })
        }

        let progressTimer = null
        if (!silent && job) {
          progressTimer = setInterval(async () => {
            if (get().boardEpoch !== epoch) return
            try {
              const p = await api.fetchScanProgress(job)
              if (get().boardEpoch !== epoch || get().desk !== desk) return
              const done = Number(p.done) || 0
              const total = Number(p.total) || 0
              const pct = Number(p.pct) || (total ? Math.round((100 * done) / total) : 0)
              const phase = p.phase || 'scan'
              const label = p.label || ''
              const countLabel = total ? `${done}/${total}` : `${done}`
              set({
                scanProgress: { ...p, job, pct },
                status:
                  p.state === 'done'
                    ? `Scan complete · ${countLabel}`
                    : label
                      ? `${label} · ${countLabel}${pct ? ` · ${pct}%` : ''} · ${phase}`
                      : `Scanning · ${countLabel}${pct ? ` · ${pct}%` : ''} · ${phase}`,
              })
            } catch {
              /* ignore poll errors while board request runs */
            }
          }, 350)
          set({ _progressTimer: progressTimer })
        }

        try {
          const board = await api.fetchBoard({
            desk,
            tf,
            universe,
            indicators,
            fresh,
            spurtsDate: desk === 'spurts' ? spurtsDate : 'live',
            signal: abort?.signal,
            job,
          })
          // One slot per dashboard on this machine until Refresh / Clear all.
          const boardsByDesk = stashDeskCache(get().boardsByDesk, desk, {
            board,
            tf,
            universe,
            spurtsDate: desk === 'spurts' ? spurtsDate : undefined,
            techIndicators: desk === 'tech' ? indicators : undefined,
          })
          const archives = board.archives || get().spurtsArchives
          const stillActive = get().boardEpoch === epoch && get().desk === desk
          if (progressTimer) clearInterval(progressTimer)
          if (!stillActive) {
            // Finished for a desk the user already left — keep that desk cache.
            set({ boardsByDesk, _progressTimer: null, scanProgress: null })
            return
          }
          const patch = {
            board,
            boardsByDesk,
            spurtsArchives: archives,
            loading: false,
            boardInFlight: false,
            _boardAbort: null,
            _progressTimer: null,
            scanProgress: null,
          }
          if (!silent && board.timeframe) {
            patch.tf = clampTf(board.timeframe)
          }
          set(patch)
          get()._statusFromBoard(board)
        } catch (err) {
          if (progressTimer) clearInterval(progressTimer)
          if (err.name === 'AbortError') {
            if (get().boardEpoch === epoch)
              set({ boardInFlight: false, _boardAbort: null, _progressTimer: null, scanProgress: null })
            return
          }
          if (get().boardEpoch !== epoch) {
            return
          }
          if (silent && get().board) {
            set({ loading: false, boardInFlight: false, _boardAbort: null, _progressTimer: null, scanProgress: null })
            return
          }
          set({
            loading: false,
            boardInFlight: false,
            _boardAbort: null,
            _progressTimer: null,
            scanProgress: null,
            error: err.message,
            status: err.message || 'Model run failed',
          })
        }
      },

      async loadSymbol(fresh = false) {
        // Legacy single-volume path — prefer loadDossier for common search.
        return get().loadDossier(fresh)
      },

      setDossierHorizon(horizon) {
        const next = horizon === 'long' ? 'long' : 'day'
        set({ dossierHorizon: next })
        if (get().mode === 'symbol' && get().symbol) get().loadDossier(true)
      },

      async loadDossier(fresh = false, opts = {}) {
        const epoch = get().boardEpoch
        const { symbol, scId, techIndicators } = get()
        const horizon = opts.horizon || get().dossierHorizon || 'day'
        const tf = horizon === 'long' ? '1d5' : '1d'
        const exchange = (opts.exchange || 'NSE').toString().toUpperCase()
        if (!symbol) return
        set({
          loading: true,
          error: null,
          status: `Combined · ${symbol} · ${horizon === 'long' ? 'Long 5Y' : 'Day'}…`,
        })
        try {
          const dossier = await api.fetchDossier({
            symbol,
            scId,
            tf,
            exchange,
            indicators: techIndicators,
            fresh,
          })
          if (get().boardEpoch !== epoch) return
          const vol = dossier.volume || null
          set({
            dossier,
            data: vol,
            loading: false,
            status:
              `${symbol} · ${horizon === 'long' ? 'Long 5Y' : 'Day'} · ${dossier.timeframe_label || tf}` +
              (dossier.cached ? ' · cached' : ' · fresh'),
          })
        } catch (err) {
          if (get().boardEpoch !== epoch) return
          set({ loading: false, error: err.message, status: err.message || 'Combined load failed' })
        }
      },

      _statusFromBoard(board) {
        const { desk } = get()
        const counts = board.counts || {}
        if (desk === 'spurts') {
          const nseFeed = (board.feeds || []).find((f) => f.name === 'NSE')
          const shown =
            board.raw_scanned != null && board.raw_scanned !== board.scanned
              ? `${board.scanned}/${board.raw_scanned}`
              : `${board.scanned}`
          const hist = board.history || board.history_date
          set({
            status:
              (hist ? `Spurts archive · ${board.history_date || ''} · ` : 'Spurts · ') +
              `NSE ${counts.nse || 0} · BSE ${counts.bse || 0} · ${shown}` +
              (!hist && board.live_quotes != null ? ` · live LTP ${board.live_quotes}` : '') +
              (nseFeed?.as_of ? ` · list ${nseFeed.as_of}` : '') +
              (board.archive?.saved ? ` · saved ${board.archive.date}` : '') +
              (board.as_of ? ` · ${board.as_of}` : '') +
              (board.cached ? ' · server cache' : ' · fresh') +
              ' · dashboard cached',
          })
          return
        }
        set({
          status:
            `${deskLabel(desk)} ready · ${board.universe_label || ''} · ${board.scanned}` +
            (board.universe_size ? `/${board.universe_size}` : '') +
            ` · ${board.timeframe_label || ''} · ${counts.bullish || 0} bullish / ${counts.bearish || 0} bearish` +
            (board.cached ? ' · server cache' : ' · fresh') +
            ' · dashboard cached',
        })
      },
    }),
    {
      name: 'signal-desk-react-v5',
      partialize: (s) => ({
        desk: s.desk,
        tf: clampTf(s.tf),
        universe: s.universe,
        tab: s.tab,
        boardView: s.boardView === 'cards' ? 'cards' : 'table',
        sortKey: s.sortKey,
        sortDir: s.sortDir,
        techIndicators: clampTechIndicators(s.techIndicators),
        boardsByDesk: s.boardsByDesk || {},
        spurtsDate: s.spurtsDate || 'live',
        dossierHorizon: s.dossierHorizon === 'long' ? 'long' : 'day',
      }),
      merge: (persisted, current) => {
        const rawCache = persisted?.boardsByDesk || persisted?.boardsByKey || {}
        const next = {
          ...current,
          ...(persisted || {}),
          techIndicators: clampTechIndicators(persisted?.techIndicators || current.techIndicators),
          universes: current.universes,
          boardsByDesk: migrateBoardsByDesk(rawCache),
        }
        delete next.boardsByKey
        next.tf = clampTf(next.tf)
        next.universe = clampUniverse(next.universe, next.universes?.length ? next.universes : UNIVERSES)
        if (next.tab === 'chg_up') next.tab = 'bullish'
        if (next.tab === 'chg_down') next.tab = 'bearish'
        next.tab = clampDeskTab(next.desk, next.tab)
        // Restore this dashboard's single cache slot on boot.
        const hit = readDeskCache(next.boardsByDesk, next.desk)
        if (hit) {
          next.board = hit.board
          next.loading = false
          if (hit.tf) next.tf = clampTf(hit.tf)
          if (hit.universe) {
            next.universe = clampUniverse(hit.universe, next.universes?.length ? next.universes : UNIVERSES)
          }
          if (next.desk === 'spurts' && hit.spurtsDate) next.spurtsDate = hit.spurtsDate
          if (next.desk === 'tech' && Array.isArray(hit.techIndicators)) {
            next.techIndicators = clampTechIndicators(hit.techIndicators)
          }
        }
        return next
      },
    },
  ),
)
