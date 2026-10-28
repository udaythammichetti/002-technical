import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { TECH_CORE_IDS, TECH_INDICATOR_IDS, TIMEFRAMES, UNIVERSES } from './constants'
import * as api from './api'

const defaultIndicators = [...TECH_CORE_IDS]
const TF_SET = new Set(TIMEFRAMES)
const TF_ALIASES = {
  d: '1d',
  day: '1d',
  daily: '1d',
  '1day': '1d',
  '1D': '1d',
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
  return picked.length ? picked : [...TECH_CORE_IDS]
}

function clampTf(tf) {
  const raw = String(tf || '1d')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
  const id = TF_ALIASES[raw] || TF_ALIASES[String(tf || '').trim()] || raw
  return TF_SET.has(id) ? id : '1d'
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
      sortKey: 'score',
      sortDir: 'desc',
      techIndicators: defaultIndicators,
      // Client-side board filters
      nameFilter: '',
      strengthFilter: 'all', // all | strong | moderate
      minRvol: '',
      minVolX: '',
      // Chart desk filters (ChartSchool views)
      chartPattern: 'all',
      chartSetup: 'all',
      chartTrend: 'all',
      chartGap: 'all', // all | any | none | breakaway
      chartFib: 'all', // all | zone
      chartCandle: 'all', // all | signal
      spurtsDate: 'live', // live | YYYY-MM-DD archive
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

      setFilters(patch) {
        set(patch)
      },

      clearFilters() {
        set({
          nameFilter: '',
          strengthFilter: 'all',
          minRvol: '',
          minVolX: '',
          chartPattern: 'all',
          chartSetup: 'all',
          chartTrend: 'all',
          chartGap: 'all',
          chartFib: 'all',
          chartCandle: 'all',
        })
      },

      setDesk(desk) {
        const sortKey =
          desk === 'spurts' ? 'vol_x' : desk === 'sci' || desk === 'chart' ? 'rank' : 'score'
        const sortDir = desk === 'sci' || desk === 'chart' ? 'asc' : desk === 'spurts' ? 'desc' : 'desc'
        const cached = readDeskCache(get().boardsByDesk, desk)
        const tf = cached?.tf ? clampTf(cached.tf) : clampTf(get().tf)
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
          nameFilter: '',
          strengthFilter: 'all',
          minRvol: '',
          minVolX: '',
          chartPattern: 'all',
          chartSetup: 'all',
          chartTrend: 'all',
          chartGap: 'all',
          chartFib: 'all',
          chartCandle: 'all',
          spurtsDate,
          error: null,
          loading: !cached,
          ...(cached ? { status: `Cached · ${desk} dashboard` } : {}),
        })
        if (cached) get()._statusFromBoard(cached.board)
        // One cache per dashboard — only fetch when that desk has no slot yet.
        if (!cached) get().loadBoard(false)
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
        set({
          spurtsDate: next,
          board: null,
          boardsByDesk: dropDeskCache(get().boardsByDesk, 'spurts'),
          boardEpoch: get().boardEpoch + 1,
          loading: true,
          error: null,
          status:
            next === 'live'
              ? 'Fetching live NSE / BSE volume spurts…'
              : `Loading spurts archive · ${next}…`,
        })
        get().loadBoard(false)
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
        const next = clampTf(tf)
        const label = String(next).toUpperCase()
        const desk = get().desk
        const cached = readDeskCache(get().boardsByDesk, desk)
        const same = cached && clampTf(cached.tf || get().tf) === next
        if (same) {
          set({
            tf: next,
            board: cached.board,
            data: null,
            boardEpoch: get().boardEpoch + 1,
            error: null,
            loading: false,
            status: `Cached · ${label}`,
          })
          get()._statusFromBoard(cached.board)
          return
        }
        // One slot per dashboard — TF change replaces that desk cache after load.
        set({
          tf: next,
          board: null,
          data: null,
          boardsByDesk: dropDeskCache(get().boardsByDesk, desk),
          boardEpoch: get().boardEpoch + 1,
          error: null,
          loading: true,
          status: `Loading ${desk} · timeframe ${label}…`,
        })
        const { mode } = get()
        if (mode === 'scan') get().loadBoard(false)
        else get().loadDossier(false)
      },

      setUniverse(universe) {
        const uid = clampUniverse(universe, get().universes)
        const desk = get().desk
        const cached = readDeskCache(get().boardsByDesk, desk)
        const same = cached && clampUniverse(cached.universe || '', get().universes) === uid
        if (same) {
          set({
            universe: uid,
            mode: 'scan',
            tab: 'trend',
            query: '',
            board: cached.board,
            boardEpoch: get().boardEpoch + 1,
            loading: false,
            error: null,
          })
          get()._statusFromBoard(cached.board)
          return
        }
        set({
          universe: uid,
          mode: 'scan',
          tab: 'trend',
          query: '',
          board: null,
          boardsByDesk: dropDeskCache(get().boardsByDesk, desk),
          boardEpoch: get().boardEpoch + 1,
          loading: true,
          error: null,
        })
        get().loadBoard(false)
      },

      setTab(tab) {
        set({ tab: clampDeskTab(get().desk, tab) })
      },

      setTechIndicators(techIndicators) {
        set({ techIndicators: clampTechIndicators(techIndicators) })
      },

      applyTechFilter() {
        set({
          mode: 'scan',
          tab: 'trend',
          board: null,
          boardsByDesk: dropDeskCache(get().boardsByDesk, 'tech'),
          boardEpoch: get().boardEpoch + 1,
          loading: true,
        })
        get().loadBoard(false)
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
          nameFilter: '',
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
          loading: !cached && !get().board,
        })
        if (cached) get()._statusFromBoard(cached.board)
        if (!cached) get().loadBoard(false)
      },

      async clearAllCache() {
        try {
          await api.clearServerCache()
        } catch {
          /* still clear local even if server is down */
        }
        const n = Object.keys(get().boardsByDesk || {}).length
        set({
          boardsByDesk: {},
          board: null,
          data: null,
          dossier: null,
          boardEpoch: get().boardEpoch + 1,
          error: null,
          loading: true,
          status: n ? `Cleared ${n} dashboard caches…` : 'All dashboard caches cleared…',
        })
        if (get().mode === 'symbol') await get().loadDossier(true)
        else await get().loadBoard(true)
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
          tf = get().tf
          universe = get().universe
        } else {
          tf = clampTf(get().tf)
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
        if (!silent || !hasBoard) {
          set({
            loading: !hasBoard,
            boardInFlight: true,
            _boardAbort: abort,
            error: null,
            status:
              desk === 'spurts'
                ? spurtsDate !== 'live'
                  ? `Loading spurts archive · ${spurtsDate}…`
                  : 'Fetching live NSE / BSE volume spurts…'
                : desk === 'tech'
                  ? `Technical · ${tfLabel} · RSI · MACD · SMA · EMA…`
                  : desk === 'sci'
                    ? `Lab · ${tfLabel} · coils · bull bases · breakouts…`
                    : desk === 'chart'
                      ? `Chart · ${tfLabel} · S/R · trends · gaps · Fib…`
                      : `Volume · ${tfLabel}…`,
          })
        } else {
          set({ error: null, boardInFlight: true, _boardAbort: abort })
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
          if (!stillActive) {
            // Finished for a desk the user already left — keep that desk cache.
            set({ boardsByDesk })
            return
          }
          const patch = {
            board,
            boardsByDesk,
            spurtsArchives: archives,
            loading: false,
            boardInFlight: false,
            _boardAbort: null,
          }
          if (!silent && board.timeframe) {
            patch.tf = clampTf(board.timeframe)
          }
          set(patch)
          get()._statusFromBoard(board)
        } catch (err) {
          if (err.name === 'AbortError') {
            if (get().boardEpoch === epoch) set({ boardInFlight: false, _boardAbort: null })
            return
          }
          if (get().boardEpoch !== epoch) {
            return
          }
          if (silent && get().board) {
            set({ loading: false, boardInFlight: false, _boardAbort: null })
            return
          }
          set({
            loading: false,
            boardInFlight: false,
            _boardAbort: null,
            error: err.message,
            status: err.message || 'Model run failed',
          })
        }
      },

      async loadSymbol(fresh = false) {
        // Legacy single-volume path — prefer loadDossier for common search.
        return get().loadDossier(fresh)
      },

      async loadDossier(fresh = false, opts = {}) {
        const epoch = get().boardEpoch
        const { symbol, scId, techIndicators } = get()
        const tf = clampTf(get().tf)
        const exchange = (opts.exchange || 'NSE').toString().toUpperCase()
        if (!symbol) return
        if (tf !== get().tf) set({ tf })
        set({
          loading: true,
          error: null,
          status: `Combined · ${symbol} · ${String(tf).toUpperCase()}…`,
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
          const boardTf = dossier.timeframe ? clampTf(dossier.timeframe) : tf
          const vol = dossier.volume || null
          set({
            dossier,
            data: vol,
            tf: boardTf,
            loading: false,
            status:
              `${symbol} · Volume · Technical · Lab · Chart · ${dossier.timeframe_label || boardTf}` +
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
            `${desk} ready · ${board.universe_label || ''} · ${board.scanned}` +
            (board.universe_size ? `/${board.universe_size}` : '') +
            ` · ${board.timeframe_label || ''} · ${counts.bullish || 0} bull / ${counts.bearish || 0} bear` +
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
        sortKey: s.sortKey,
        sortDir: s.sortDir,
        techIndicators: clampTechIndicators(s.techIndicators),
        boardsByDesk: s.boardsByDesk || {},
        spurtsDate: s.spurtsDate || 'live',
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
