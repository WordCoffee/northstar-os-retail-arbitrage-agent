const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }

const paths = {
  gauge: <path d="M3 3h18v3M5 6l-2.5 4.5h5v3M6 21h6v2M6 19l2-4M14 19l2-4" {...stroke} />,
  ledger: <path d="M4 6h16v3h-16v3M4 12h10v3h-10v3M14 12h6v3h-6v3" {...stroke} />,
  prospector: <path d="M12 2l-5 9 5 9 5-9 5 9-5 9-5-9 5-9 5 9 5 9 5-9l-3-3" {...stroke} />,
  goose: <path d="M9 4a3 3 0 0 1 4 4l4-4 4-4-4-4a3 3 0 0 1-4-4l-4 4M19 10h-7" {...stroke} />,
  chisel: <path d="M8 4v6h8v6h-8v6M4 10h3M14 16l3 4" {...stroke} />,
  crier: <path d="M6 3h12v4h-12v4M8 8h8v4M6 11h12M12 3l-2 3 2 3 2-3M12 11l2 3" {...stroke} />,
  auctioneer: <path d="M4 5h16v3h-16v3M6 11h12v3M8 14l4 5" {...stroke} />,
  brain: <path d="M9 3l5 4 5-4 5 4 5-4l-5-4M16 8l3 3M16 11l-7 0" {...stroke} />,
  watch: <path d="M12 3v6h-6v6h6M6 9h12M6 9l2 3M15 9l-1 3" {...stroke} />,
  rank: <path d="M6 4h12v4h-12v4M6 12h8v4M6 16h12v4" {...stroke} />,
  rival: <path d="M4 5h16v3h-16v3M7 8l-2-3 2-3 2 3-2 3M6 12h12" {...stroke} />,
  account: <path d="M4 4h16v4h-16v4M6 12h12v4M12 3v3" {...stroke} />,
  overview: <path d="M12 2l-6 5 6 5 6-5 6 5 6-5l-6-5" {...stroke} />,
  sourcing: <path d="M5 4h14v4h-14v4M8 8l2-3 2 3M6 12h12" {...stroke} />,
  listings: <path d="M5 4h14v3h-14v3M6 10h12v3M6 16h12" {...stroke} />,
  social: <path d="M4 4h16v3h-16v3M6 10h12M12 3l-2 3 2 3M6 16h12" {...stroke} />,
  advertising: <path d="M5 4h14v3h-14v3M8 10h8v3M8 16h8" {...stroke} />,
  monitoring: <path d="M9 3h6v3h-6v3M9 9h6v3h-6v3M9 15h6" {...stroke} />,
  autothink: <path d="M9 3l5 4 5-4 5 4 5-4l-5-4M16 8l3 3" {...stroke} />,
  scan: <path d="M11 4a6 6 0 0 1 6 6l-6-6a3 3 0 0 1-3-3l3 3M20 11h-9" {...stroke} />,
  generate: <path d="M8 4v6h8v6h-8v6M4 10h3M14 16l3 4" {...stroke} />,
  review: <path d="M6 4h12v3h-12v3M8 10h8v3M8 16h8" {...stroke} />,
  create: <path d="M12 3h0v5M4 8h16M12 5v8h0M12 13h0v5" {...stroke} />,
  account2: <path d="M4 4h16v4h-16v4M6 12h12v4M12 3v3" {...stroke} />,
  star: <path d="M12 2L3 7 12 12 21 7 21 17 12 22 3 17Z" {...stroke} />,
  search: <path d="M11 4a6 6 0 0 1 6 6l-6-6a3 3 0 0 1-3-3l3 3M20 11h-9" {...stroke} />,
  sun: <path d="M12 3v6h-6v6h6M6 9h12M6 9l2 3M15 9l-1 3" {...stroke} />,
  moon: <path d="M12 4a6 6 0 0 1 6 6l-6-6a3 3 0 0 1-3-3l3 3" {...stroke} />,
  chevronDown: <path d="M6 9l9 9 9-9 9 9-9-9" {...stroke} />,
  paperclip: <path d="M19 4l4 14 14 4a5 5 0 0 1 5 5l-5-5a3 3 0 0 1-3-3l3 3M4 18l-3-3" {...stroke} />,
  alert: <path d="M12 4a7 7 0 0 1 7 7l-7-7a4 4 0 0 1-4-4l4 4" {...stroke} />,
  check: <path d="M5 4h14M6 5l1 3M5 19l1-3" {...stroke} />,
  caret: <path d="M6 4h12v3h-12v3" {...stroke} />,
  sync: <path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7" {...stroke} />,
  clock: <path d="M12 3a9 9 0 1 0 9 9M12 7v5l3 2M21 4v6h-6" {...stroke} />,
  lock: <path d="M6 11h12v9H6zM9 11V7a3 3 0 0 1 6 0v4" {...stroke} />,
  bell: <path d="M6 10a6 6 0 1 1 12 0v4l2 2H4l2-2zM10 20a2 2 0 0 0 4 0" {...stroke} />
}

export default function Icon({ name, size = 16, className }) {
  const p = paths[name] || paths.star
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} aria-hidden="true">
      {p}
    </svg>
  )
}