// Small display helpers shared by the screens.

export function formatPercent(ratio: number | null | undefined, digits = 1) {
  return ratio == null ? '—' : `${(ratio * 100).toFixed(digits)}%`
}

export function formatMs(ms: number | null | undefined) {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  return `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`
}

export function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function timeAgo(iso: string, now = Date.now()) {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  return `${Math.floor(s / 3600)} h ago`
}

/** First 8 characters of a UUID, enough to tell boards apart on screen. */
export function shortId(id: string) {
  return id.slice(0, 8)
}
