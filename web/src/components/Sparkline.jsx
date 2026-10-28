/** Tiny SVG close sparkline from normalized 0…1 points. */
export default function Sparkline({ points, up = true, width = 120, height = 28 }) {
  const pts = Array.isArray(points) ? points.filter((n) => Number.isFinite(Number(n))) : []
  if (pts.length < 2) return null

  const pad = 1
  const w = width - pad * 2
  const h = height - pad * 2
  const step = w / (pts.length - 1)
  const coords = pts.map((y, i) => {
    const x = pad + i * step
    const yy = pad + (1 - Number(y)) * h
    return `${x.toFixed(1)},${yy.toFixed(1)}`
  })
  const line = coords.join(' ')
  const area = `${pad},${pad + h} ${line} ${pad + w},${pad + h}`

  return (
    <svg
      className={'sparkline' + (up ? ' is-up' : ' is-down')}
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      aria-hidden="true"
    >
      <polygon className="spark-area" points={area} />
      <polyline className="spark-line" points={line} fill="none" />
    </svg>
  )
}
