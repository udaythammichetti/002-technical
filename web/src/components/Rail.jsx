import { DESKS } from '../constants'
import { useDesk } from '../store'
import { DESK_ICONS, MarkIcon } from './Icons'

export default function Rail() {
  const desk = useDesk((s) => s.desk)
  const setDesk = useDesk((s) => s.setDesk)

  return (
    <aside className="rail" aria-label="Workspaces">
      <div className="rail-mark" title="Signal Desk">
        <MarkIcon />
      </div>
      <nav className="rail-nav">
        {DESKS.map((d) => {
          const Icon = DESK_ICONS[d.id]
          return (
            <button
              key={d.id}
              type="button"
              className={'rail-link' + (desk === d.id ? ' is-on' : '')}
              title={d.label}
              aria-label={d.label}
              onClick={() => setDesk(d.id)}
            >
              <Icon />
            </button>
          )
        })}
      </nav>
      <div className="rail-foot" aria-hidden="true">SD</div>
    </aside>
  )
}
