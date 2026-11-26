export function MarkIcon() {
  return (
    <svg viewBox="0 0 32 32" width="18" height="18" aria-hidden="true">
      <rect x="4" y="18" width="5" height="10" rx="1.5" fill="currentColor" opacity="0.45" />
      <rect x="11" y="11" width="5" height="17" rx="1.5" fill="currentColor" opacity="0.7" />
      <rect x="18" y="6" width="5" height="22" rx="1.5" fill="currentColor" />
      <rect x="25" y="13" width="5" height="15" rx="1.5" fill="currentColor" opacity="0.55" />
    </svg>
  )
}

export function VolumeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path
        d="M3 12h2.5l2-6 3 12 2.5-8L16 14h5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function TechIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path d="M5 18V9M10 18V6M15 18v-7M20 18V4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M4 20h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.35" />
    </svg>
  )
}

export function LabIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path
        d="M9 3h6M10 3v5.2L5.8 18.2A2.4 2.4 0 0 0 8 21.5h8a2.4 2.4 0 0 0 2.2-3.3L13.9 8.2V3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M8.2 14.5h7.6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.55" />
    </svg>
  )
}

export function ChartIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path
        d="M4 18V7M4 18h16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <path
        d="M7 14l3.5-4 3 2.5L18 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M7 7h.01M18 14h.01" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  )
}

export function CandleIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path d="M7 5v3M7 16v3M12 3v4M12 17v4M17 6v3M17 15v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.55" />
      <rect x="5" y="8" width="4" height="8" rx="1" fill="currentColor" />
      <rect x="10" y="7" width="4" height="10" rx="1" fill="currentColor" opacity="0.7" />
      <rect x="15" y="9" width="4" height="6" rx="1" fill="currentColor" opacity="0.45" />
    </svg>
  )
}

export function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path d="M8 5.5v13l11-6.5-11-6.5z" fill="currentColor" />
    </svg>
  )
}

export const DESK_ICONS = {
  volume: VolumeIcon,
  tech: TechIcon,
  sci: LabIcon,
  chart: ChartIcon,
  candle: CandleIcon,
}
