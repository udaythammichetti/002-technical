import { useDesk } from '../store'

const CHART_PATTERNS = [
  ['all', 'All patterns'],
  ['rectangle', 'Rectangle'],
  ['asc_triangle', 'Asc. triangle'],
  ['desc_triangle', 'Desc. triangle'],
  ['sym_triangle', 'Sym. triangle'],
  ['double_bottom', 'Double bottom'],
  ['double_top', 'Double top'],
  ['flag_bull', 'Flag bull'],
  ['flag_bear', 'Flag bear'],
  ['none', 'No pattern'],
]

const CHART_SETUPS = [
  ['all', 'All setups'],
  ['breakout', 'Breakout'],
  ['breakdown', 'Breakdown'],
  ['near_support', 'Near support'],
  ['near_resistance', 'Near resistance'],
  ['fib_zone', 'Fib zone'],
  ['mid_range', 'Mid-range'],
]

export default function BoardFilters({ shown, total }) {
  const desk = useDesk((s) => s.desk)
  const nameFilter = useDesk((s) => s.nameFilter)
  const strengthFilter = useDesk((s) => s.strengthFilter)
  const minRvol = useDesk((s) => s.minRvol)
  const minVolX = useDesk((s) => s.minVolX)
  const chartPattern = useDesk((s) => s.chartPattern)
  const chartSetup = useDesk((s) => s.chartSetup)
  const chartTrend = useDesk((s) => s.chartTrend)
  const chartGap = useDesk((s) => s.chartGap)
  const chartFib = useDesk((s) => s.chartFib)
  const chartCandle = useDesk((s) => s.chartCandle)
  const setFilters = useDesk((s) => s.setFilters)
  const clearFilters = useDesk((s) => s.clearFilters)

  const dirty =
    Boolean(nameFilter) ||
    strengthFilter !== 'all' ||
    String(minRvol) !== '' ||
    String(minVolX) !== '' ||
    chartPattern !== 'all' ||
    chartSetup !== 'all' ||
    chartTrend !== 'all' ||
    chartGap !== 'all' ||
    chartFib !== 'all' ||
    chartCandle !== 'all'

  return (
    <div className="board-filters" aria-label="Board filters">
      <input
        className="filter-input"
        type="search"
        placeholder="Filter symbol or name…"
        value={nameFilter}
        onChange={(e) => setFilters({ nameFilter: e.target.value })}
        aria-label="Filter by symbol or name"
      />

      {desk !== 'spurts' && (
        <select
          className="filter-select"
          value={strengthFilter}
          onChange={(e) => setFilters({ strengthFilter: e.target.value })}
          aria-label="Strength"
          title="Signal strength"
        >
          <option value="all">All strength</option>
          <option value="strong">Strong</option>
          <option value="moderate">Moderate</option>
        </select>
      )}

      {desk === 'chart' && (
        <>
          <select
            className="filter-select"
            value={chartSetup}
            onChange={(e) => setFilters({ chartSetup: e.target.value })}
            aria-label="Setup"
            title="ChartSchool setup"
          >
            {CHART_SETUPS.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
          <select
            className="filter-select"
            value={chartPattern}
            onChange={(e) => setFilters({ chartPattern: e.target.value })}
            aria-label="Pattern"
            title="Chart pattern"
          >
            {CHART_PATTERNS.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
          <select
            className="filter-select"
            value={chartTrend}
            onChange={(e) => setFilters({ chartTrend: e.target.value })}
            aria-label="Trend"
            title="Trend line"
          >
            <option value="all">All trends</option>
            <option value="up">Uptrend</option>
            <option value="down">Downtrend</option>
            <option value="sideways">Sideways</option>
            <option value="valid">Valid (≥3 touches)</option>
          </select>
          <select
            className="filter-select"
            value={chartGap}
            onChange={(e) => setFilters({ chartGap: e.target.value })}
            aria-label="Gap"
            title="Gap filter"
          >
            <option value="all">All gaps</option>
            <option value="any">Has gap</option>
            <option value="breakaway">Breakaway</option>
            <option value="runaway">Runaway</option>
            <option value="exhaustion">Exhaustion</option>
            <option value="none">No gap</option>
          </select>
          <select
            className="filter-select"
            value={chartFib}
            onChange={(e) => setFilters({ chartFib: e.target.value })}
            aria-label="Fibonacci"
            title="Fibonacci alert zone"
          >
            <option value="all">All Fib</option>
            <option value="zone">In Fib zone</option>
            <option value="pullback">Fib pullback</option>
            <option value="bounce">Fib bounce</option>
          </select>
          <select
            className="filter-select"
            value={chartCandle}
            onChange={(e) => setFilters({ chartCandle: e.target.value })}
            aria-label="Candle"
            title="Candlestick signal"
          >
            <option value="all">All candles</option>
            <option value="signal">Has signal</option>
            <option value="bull">Bull candle</option>
            <option value="bear">Bear candle</option>
          </select>
        </>
      )}

      {desk !== 'spurts' && desk !== 'chart' && (
        <label className="filter-num" title="Minimum RVOL">
          <span>RVOL ≥</span>
          <input
            type="number"
            min="0"
            step="0.1"
            placeholder="0"
            value={minRvol}
            onChange={(e) => setFilters({ minRvol: e.target.value })}
          />
        </label>
      )}

      {desk === 'chart' && (
        <label className="filter-num" title="Minimum RVOL (gap/breakout volume)">
          <span>RVOL ≥</span>
          <input
            type="number"
            min="0"
            step="0.1"
            placeholder="0"
            value={minRvol}
            onChange={(e) => setFilters({ minRvol: e.target.value })}
          />
        </label>
      )}

      {desk === 'spurts' && (
        <label className="filter-num" title="Minimum Vol×">
          <span>Vol× ≥</span>
          <input
            type="number"
            min="0"
            step="0.5"
            placeholder="0"
            value={minVolX}
            onChange={(e) => setFilters({ minVolX: e.target.value })}
          />
        </label>
      )}

      <span className="filter-count">
        {shown}
        {total != null ? `/${total}` : ''} names
      </span>

      {dirty && (
        <button type="button" className="chip-btn" onClick={clearFilters}>
          Clear
        </button>
      )}
    </div>
  )
}
