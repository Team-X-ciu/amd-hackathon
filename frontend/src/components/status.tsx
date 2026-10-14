// Status display components. Logic and colours live in src/lib/status.ts.
import { cn } from '@/lib/utils'
import { levelOf, levelStyles, verdictLabel, type Level } from '@/lib/status'
import type { Inspection, VisionResult } from '@/api/client'

export function StatusDot({ level, pulse, className }: { level: Level; pulse?: boolean; className?: string }) {
  return (
    <span className={cn('relative inline-flex size-2.5 shrink-0', className)} aria-hidden>
      {pulse && <span className={cn('absolute inset-0 animate-ping rounded-full opacity-60', levelStyles[level].dot)} />}
      <span className={cn('relative inline-flex size-2.5 rounded-full', levelStyles[level].dot)} />
    </span>
  )
}

export function VerdictBadge({
  vision,
  size = 'md',
  className,
}: {
  vision: VisionResult | null | undefined
  size?: 'md' | 'lg'
  className?: string
}) {
  const level = levelOf(vision)
  const s = levelStyles[level]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-md border font-semibold capitalize',
        s.soft,
        s.text,
        s.border,
        size === 'lg' ? 'px-4 py-2 text-xl' : 'px-2 py-0.5 text-sm',
        className,
      )}
    >
      <StatusDot level={level} />
      {verdictLabel(vision)}
    </span>
  )
}

const statusLabels: Record<Inspection['status'], string> = {
  inspected: 'Inspected',
  explaining: 'Agent analysing…',
  explained: 'Awaiting decision',
  explain_failed: 'Agent failed',
  decided: 'Decided',
  failed: 'Vision failed',
}

/** Workflow status: neutral styling, it is not a quality verdict. */
export function StatusBadge({ status, className }: { status: Inspection['status']; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2 py-0.5 text-xs font-medium text-muted-foreground',
        status === 'explaining' && 'animate-pulse',
        className,
      )}
    >
      {statusLabels[status]}
    </span>
  )
}
