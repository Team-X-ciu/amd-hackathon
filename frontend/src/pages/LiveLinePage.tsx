// Live line: the newest board large, a feed of recent boards, and shift counters.
// Keeps historical boards in memory and prepends incoming boards smoothly.
import { useState, useEffect } from 'react'
import { ArrowRight, Pause, Play, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Inspection } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardAction } from '@/components/ui/card'
import { InspectionImage } from '@/components/InspectionImage'
import { StatusBadge, StatusDot, VerdictBadge } from '@/components/status'
import { levelOf, levelStyles, verdictLabel } from '@/lib/status'
import { formatMs, formatPercent, shortId, timeAgo } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useInspectionsQuery, useStatsQuery } from '@/api/queries'

export function LiveLinePage() {
  const [isPaused, setIsPaused] = useState(false)
  const [stream, setStream] = useState<Inspection[]>([])

  const inspectionsQuery = useInspectionsQuery(
    { limit: 10 },
    { refetchInterval: isPaused ? false : 6_000 },
  )
  const statsQuery = useStatsQuery()

  // Real-world factory conveyor logic:
  // When a new board arrives, prepend it to the top of the feed and slide older boards down.
  useEffect(() => {
    if (isPaused || !inspectionsQuery.data || inspectionsQuery.data.length === 0) return

    setStream((prev) => {
      const existingIds = new Set(prev.map((item) => item.id))
      // Filter out boards already in our conveyor stream
      const freshItems = inspectionsQuery.data.filter((item) => !existingIds.has(item.id))

      if (freshItems.length === 0) return prev

      // Prepend the arriving boards (API order: newest first), keep up to 15
      return [...freshItems, ...prev].slice(0, 15)
    })
  }, [inspectionsQuery.data, isPaused])

  // No sample data: "—" and an empty state until /stats and /inspections answer.
  const stats = statsQuery.data
  const [latest, ...recent] = stream
  const awaiting = stream.filter((i) => i.status === 'explained' || i.status === 'explain_failed').length

  return (
    <div className="space-y-6">
      {/* Title + simulator controls */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Live line</h1>
          <p className="mt-1 text-muted-foreground">
            Newest inspected boards at top.
            {!isPaused && (
              <span className="ml-2 inline-flex items-center gap-1 text-xs text-primary">
                <RefreshCw className={cn('size-3', inspectionsQuery.isFetching && 'animate-spin')} />
                Auto-refresh
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-2">
          <StatusDot level={isPaused ? 'unknown' : 'ok'} pulse={!isPaused} />
          <span className="text-sm">
            {isPaused ? (
              <span className="text-muted-foreground">Stream paused</span>
            ) : (
              <>
                {/* True statement: this page polls the list; there is no line simulator yet */}
                Auto-refresh on · <span className="text-muted-foreground">checks for new boards every 6 s</span>
              </>
            )}
          </span>
          <Button
            id="simulator-pause"
            variant="outline"
            size="sm"
            onClick={() => setIsPaused((p) => !p)}
          >
            {isPaused ? <Play /> : <Pause />}
            {isPaused ? 'Resume' : 'Pause'}
          </Button>
        </div>
      </div>

      {/* Shift counters */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Inspected this shift" value={stats ? Math.abs(stats.total).toLocaleString() : '—'} />
        <Kpi label="Defect rate" value={stats ? formatPercent(Math.min(1, Math.max(0, stats.defect_rate))) : '—'} />
        <Kpi label="Awaiting decision" value={String(awaiting)} />
        <Kpi label="Avg inspection time" value={formatMs(stats?.avg_inspection_latency_ms)} />
      </div>

      {!latest ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
            {inspectionsQuery.isPending ? (
              <p>Loading boards…</p>
            ) : inspectionsQuery.isError ? (
              <p className="text-destructive">Could not load boards: {(inspectionsQuery.error as Error).message}</p>
            ) : (
              <>
                <p>No boards yet. Upload one to see it here.</p>
                <Button variant="outline" nativeButton={false} render={<Link to="/upload" />}>
                  Upload a board <ArrowRight />
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      ) : (
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Newest board */}
        <Card className={cn('border-l-4 lg:col-span-2 transition-all duration-300', levelStyles[levelOf(latest.vision)].border)}>
          <CardHeader>
            <CardTitle className="text-lg">Latest board</CardTitle>
            <CardDescription className="font-mono">
              #{shortId(latest.id)} · {timeAgo(latest.created_at)}
            </CardDescription>
            <CardAction>
              <StatusBadge status={latest.status} />
            </CardAction>
          </CardHeader>
          <CardContent className="grid gap-6 md:grid-cols-2">
            <InspectionImage key={latest.id} imageUrl={latest.image_url} maskUrl={latest.vision?.mask_url} />
            <div className="flex flex-col gap-5">
              <VerdictBadge vision={latest.vision} size="lg" className="self-start" />
              {latest.vision && (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <Metric label="Anomaly score" value={latest.vision.anomaly_score.toFixed(3)} />
                  <Metric label="Confidence" value={formatPercent(latest.vision.defect_confidence, 0)} />
                  <Metric label="Defect area" value={formatPercent(latest.vision.defect_area_ratio)} />
                  <Metric label="Inference" value={formatMs(latest.vision.latency_ms)} />
                </dl>
              )}
              {latest.explanation && (
                <p className="line-clamp-3 rounded-md border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
                  {latest.explanation.recommended_action}
                </p>
              )}
              <Button
                id="open-latest"
                size="lg"
                className="mt-auto h-12 text-base"
                nativeButton={false}
                render={<Link to={`/inspections/${latest.id}`} />}
              >
                Open inspection <ArrowRight />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Recent feed */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent boards</CardTitle>
            <CardDescription>Click a board to inspect its history</CardDescription>
          </CardHeader>
          <CardContent className="gap-1 px-2">
            <ul className="flex flex-col max-h-[520px] overflow-y-auto">
              {recent.map((i) => {
                const l = levelOf(i.vision)
                return (
                  <li key={i.id} className="transition-all duration-200">
                    <Link
                      to={`/inspections/${i.id}`}
                      id={`recent-${shortId(i.id)}`}
                      className="flex items-center gap-3 rounded-md px-3 py-3 transition-colors hover:bg-muted/50"
                    >
                      <StatusDot level={l} />
                      <div className="min-w-0 flex-1">
                        <div className={cn('truncate font-medium capitalize', levelStyles[l].text)}>
                          {verdictLabel(i.vision)}
                        </div>
                        <div className="font-mono text-xs text-muted-foreground">
                          #{shortId(i.id)} · {timeAgo(i.created_at)}
                        </div>
                      </div>
                      <StatusBadge status={i.status} className="hidden sm:inline-flex" />
                    </Link>
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>
      </div>
      )}
    </div>
  )
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card size="sm">
      <CardContent>
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      </CardContent>
    </Card>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-mono text-base tabular-nums">{value}</dd>
    </div>
  )
}
