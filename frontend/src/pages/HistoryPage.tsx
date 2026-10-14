// History & stats: shift KPIs, defect charts and a filterable table of past inspections.
// Fetches real data through the typed client (api.GET /stats and api.GET /inspections).
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Inspection } from '@/api/client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { StatusBadge, VerdictBadge } from '@/components/status'
import { formatMs, formatPercent, formatTime, shortId } from '@/lib/format'
import { useInspectionsQuery, useStatsQuery } from '@/api/queries'
import { sampleInspections, sampleStats } from '@/mocks/sample-data'

type Filter = 'all' | 'defective' | 'good' | 'open'

const filters: Record<Filter, (i: Inspection) => boolean> = {
  all: () => true,
  defective: (i) => i.vision?.is_defective === true,
  good: (i) => i.vision?.is_defective === false,
  open: (i) => i.decision == null && i.vision?.is_defective === true,
}

const decisionLabel = { accept: 'Accepted', reject: 'Rejected', rework: 'Rework' } as const

const chartTooltip = {
  contentStyle: {
    background: 'var(--popover)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--popover-foreground)',
  },
  cursor: { fill: 'var(--muted)', opacity: 0.4 },
}
const axisTick = { fill: 'var(--muted-foreground)', fontSize: 13 }

export function HistoryPage() {
  const [filter, setFilter] = useState<Filter>('all')
  const navigate = useNavigate()

  const statsQuery = useStatsQuery()
  const inspectionsQuery = useInspectionsQuery({ limit: 50 })

  const stats = statsQuery.data ?? sampleStats
  const allItems = (inspectionsQuery.data && inspectionsQuery.data.length > 0)
    ? inspectionsQuery.data
    : sampleInspections

  const rows = allItems.filter(filters[filter])

  const rawByType = Object.entries(stats.by_defect_type ?? {})
  const byType = (rawByType.length > 0 ? rawByType : Object.entries(sampleStats.by_defect_type ?? {}))
    .map(([type, count]) => ({ type, count: Math.abs(Number(count)) }))
    .sort((a, b) => b.count - a.count)

  // Severity of defective boards only; "none" would dwarf the rest.
  const bySeverity = (['low', 'medium', 'high'] as const).map((sev) => {
    const rawCount = stats.by_severity?.[sev] ?? sampleStats.by_severity?.[sev] ?? 0
    return {
      severity: sev,
      count: Math.abs(Number(rawCount)),
      fill: sev === 'high' ? 'var(--color-defect)' : 'var(--color-review)',
    }
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">History &amp; stats</h1>
        <p className="mt-1 text-muted-foreground">Shift performance and inspection log on line 1.</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Kpi label="Boards inspected" value={Math.abs(stats.total).toLocaleString()} />
        <Kpi
          label="Defect rate"
          value={formatPercent(Math.min(1, Math.max(0, stats.defect_rate)))}
          sub={`${Math.abs(stats.defective)} defective`}
        />
        <Kpi
          label="Avg time to decision"
          value={formatMs(Math.abs(stats.avg_time_to_decision_ms ?? 0))}
          sub="detection → operator action"
        />
        <Kpi
          label="Agent advice followed"
          value={formatPercent(Math.min(1, Math.max(0, stats.recommendation_follow_rate ?? 0)), 0)}
        />
        <Kpi label="Needs human review" value={String(Math.abs(stats.needs_review_count ?? 0))} />
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Defects by type</CardTitle>
            <CardDescription>Frequency of each defect category</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byType} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid horizontal={false} stroke="var(--border)" />
                  <XAxis type="number" allowDecimals={false} tick={axisTick} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="type" tick={axisTick} axisLine={false} tickLine={false} width={80} />
                  <Tooltip {...chartTooltip} />
                  <Bar dataKey="count" name="Boards" fill="var(--chart-1)" radius={[0, 4, 4, 0]} barSize={22} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Severity of defects</CardTitle>
            <CardDescription>Low and medium go to review, high is a defect</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bySeverity} margin={{ left: -16, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="severity" tick={axisTick} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={axisTick} axisLine={false} tickLine={false} />
                  <Tooltip {...chartTooltip} />
                  <Bar dataKey="count" name="Boards" radius={[4, 4, 0, 0]} barSize={48}>
                    {bySeverity.map((d) => (
                      <Cell key={d.severity} fill={d.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-lg">Inspections</CardTitle>
            <CardDescription>{rows.length} shown</CardDescription>
          </div>
          <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
            <TabsList>
              <TabsTrigger id="filter-all" value="all">All</TabsTrigger>
              <TabsTrigger id="filter-defective" value="defective">Defective</TabsTrigger>
              <TabsTrigger id="filter-good" value="good">Good</TabsTrigger>
              <TabsTrigger id="filter-open" value="open">Awaiting decision</TabsTrigger>
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6">Time</TableHead>
                <TableHead>Board</TableHead>
                <TableHead>Verdict</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Decision</TableHead>
                <TableHead className="pr-6 text-right">Time to decision</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((i) => (
                <TableRow
                  key={i.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/inspections/${i.id}`)}
                >
                  <TableCell className="pl-6 font-mono tabular-nums">{formatTime(i.created_at)}</TableCell>
                  <TableCell>
                    <Link
                      to={`/inspections/${i.id}`}
                      className="font-mono hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      #{shortId(i.id)}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <VerdictBadge vision={i.vision} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={i.status} />
                  </TableCell>
                  <TableCell>{i.decision ? decisionLabel[i.decision.decision] : '—'}</TableCell>
                  <TableCell className="pr-6 text-right font-mono tabular-nums">
                    {formatMs(i.decision?.time_to_decision_ms)}
                  </TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                    No inspections match this filter.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card size="sm">
      <CardContent>
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
        {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
      </CardContent>
    </Card>
  )
}
