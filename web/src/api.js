async function getJson(url, opts = {}) {
  const res = await fetch(url, opts.signal ? { signal: opts.signal } : undefined)
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`)
  return data
}

export function fetchSources(fresh = false) {
  return getJson(`/api/sources${fresh ? '?fresh=1' : ''}`)
}

export function clearServerCache() {
  return getJson('/api/cache/clear')
}

export function fetchBoard({ desk, tf, universe, indicators, fresh, spurtsDate, signal, job }) {
  const params = new URLSearchParams()
  if (desk !== 'spurts') {
    params.set('tf', String(tf || '1d').trim().toLowerCase())
    params.set('universe', universe || 'nifty50')
  } else {
    // Spurts: full NSE + BSE lists; optional archive date for history view.
    params.set('exchange', 'all')
    params.set('universe', 'live')
    if (spurtsDate && spurtsDate !== 'live') params.set('date', spurtsDate)
  }
  if (fresh) params.set('fresh', '1')
  if (desk === 'tech' && Array.isArray(indicators)) params.set('indicators', indicators.join(','))
  if (job) params.set('job', job)

  const endpoint =
    desk === 'tech'
      ? '/api/tech-board?'
      : desk === 'sci'
        ? '/api/sci-board?'
        : desk === 'chart'
          ? '/api/chart-board?'
          : desk === 'spurts'
            ? '/api/spurts?'
            : '/api/board?'

  return getJson(endpoint + params.toString(), { signal })
}

export function fetchScanProgress(job, signal) {
  if (!job) return Promise.resolve({ state: 'idle', done: 0, total: 0, pct: 0 })
  return getJson('/api/scan-progress?job=' + encodeURIComponent(job), { signal })
}

export function newScanJobId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID().replace(/-/g, '')
  return 'job' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
}

export function fetchSpurtsHistory() {
  return getJson('/api/spurts/history')
}

export function fetchSpurtsDashboard(days = 30) {
  return getJson(`/api/spurts/dashboard?days=${days}`)
}

export function archiveSpurtsToday(force = false) {
  return getJson(`/api/spurts/archive${force ? '?force=1' : ''}`)
}

export function fetchVolume({ symbol, scId, tf, fresh, signal }) {
  const params = new URLSearchParams({
    symbol,
    sc_id: scId || '',
    kind: 'stock',
    tf: String(tf || '1d').trim().toLowerCase(),
  })
  if (fresh) params.set('fresh', '1')
  return getJson('/api/volume?' + params.toString(), { signal })
}

/** Combined Volume + Technical + Lab + Chart for one symbol (no Spurts). */
export function fetchDossier({ symbol, scId, tf, exchange, indicators, fresh, signal }) {
  const params = new URLSearchParams({
    symbol: symbol || '',
    sc_id: scId || '',
    tf: String(tf || '1d').trim().toLowerCase(),
    exchange: exchange || 'NSE',
  })
  if (fresh) params.set('fresh', '1')
  if (Array.isArray(indicators) && indicators.length) {
    params.set('indicators', indicators.join(','))
  }
  return getJson('/api/symbol-dossier?' + params.toString(), { signal })
}

export function searchSymbols(q, signal) {
  return getJson('/api/search?q=' + encodeURIComponent(q), { signal }).then((d) => d.results || [])
}
