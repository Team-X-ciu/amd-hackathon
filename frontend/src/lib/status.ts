// Status logic (no components here, so Vite fast refresh keeps working).
// Design rule: green / amber / red are used ONLY for board status
// (OK / review / defect), never for decoration.
import type { VisionResult } from '@/api/client'

export type Level = 'ok' | 'review' | 'defect' | 'unknown'

/** Severity -> status level: none = OK, low/medium = needs review, high = defect. */
export function levelOf(vision: VisionResult | null | undefined): Level {
  if (!vision) return 'unknown'
  if (vision.severity === 'none') return 'ok'
  if (vision.severity === 'high') return 'defect'
  return 'review'
}

export function verdictLabel(vision: VisionResult | null | undefined) {
  if (!vision) return 'No result'
  if (!vision.is_defective) return 'OK'
  return `${vision.defect_type ?? 'unknown'} · ${vision.severity}`
}

// Full class names so Tailwind can find them.
export const levelStyles: Record<Level, { text: string; soft: string; border: string; dot: string }> = {
  ok: { text: 'text-ok', soft: 'bg-ok/15', border: 'border-ok/40', dot: 'bg-ok' },
  review: { text: 'text-review', soft: 'bg-review/15', border: 'border-review/40', dot: 'bg-review' },
  defect: { text: 'text-defect', soft: 'bg-defect/15', border: 'border-defect/40', dot: 'bg-defect' },
  unknown: { text: 'text-muted-foreground', soft: 'bg-muted', border: 'border-border', dot: 'bg-muted-foreground' },
}
