import { displayStock, tradingViewUrlForRow } from '../utils'

/** Symbol + company name cell / inline link. */
export default function StockLink({
  row,
  as = 'inline',
  showName = true,
  short = true,
  onClick,
}) {
  const { sym, name, full, title } = displayStock(row, { short })
  const tv = tradingViewUrlForRow(row)
  const href = tv || row?.source_url || ''

  const nameNode =
    showName && name ? <span className="stock-name">{name}</span> : null

  const body = (
    <>
      <span className="stock-sym">{sym || '—'}</span>
      {nameNode}
    </>
  )

  if (as === 'cell') {
    return (
      <td className="stock-cell" title={tv ? `${title} · TradingView` : title}>
        {href ? (
          <a
            className="stock-link"
            href={href}
            target="_blank"
            rel="noreferrer"
            title="Open on TradingView"
            onClick={(e) => e.stopPropagation()}
          >
            {body}
          </a>
        ) : (
          <span className="stock-link is-plain">{body}</span>
        )}
        {!short && full && full !== name ? <span className="stock-name-full"> · {full}</span> : null}
      </td>
    )
  }

  if (href) {
    return (
      <a
        className="stock-link"
        href={href}
        target="_blank"
        rel="noreferrer"
        title={title}
        onClick={(e) => {
          e.stopPropagation()
          onClick?.(e)
        }}
      >
        {body}
      </a>
    )
  }

  return (
    <span className="stock-link is-plain" title={title}>
      {body}
    </span>
  )
}
