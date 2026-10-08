/** Line icons drawn for this app: one stroke weight, currentColor. */

const PATHS = {
  shelf: 'M3 4v16M21 4v16M3 10h18M3 18h18M7 10V6.5M10 10V7.5M15 18v-4M18 18v-3',
  glass: 'M5 4h14l-7 8zM12 12v7M8 20h8',
  list: 'M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01',
  scan: 'M4 8V5h3M20 8V5h-3M4 16v3h3M20 16v3h-3M8 9v6M11 9v6M14 9v6M17 9v6',
  search: 'M11 17.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM20 20l-4.2-4.2',
  bottle:
    'M10 2.5h4v4.2c0 .6.3 1.1.8 1.5 1.3 1 2.2 2.2 2.2 4V20a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 7 20v-7.8c0-1.8.9-3 2.2-4 .5-.4.8-.9.8-1.5z',
  plus: 'M12 5v14M5 12h14',
  camera: 'M4 8h3l1.5-2.5h7L17 8h3v11H4zM12 16.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z',
  chevron: 'M9 6l6 6-6 6',
  up: 'M12 19V5M6 11l6-6 6 6',
  down: 'M12 5v14M6 13l6 6 6-6',
  close: 'M6 6l12 12M18 6L6 18',
}

export default function Icon({ name, className = 'icon' }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
