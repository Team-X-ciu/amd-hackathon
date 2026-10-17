// Inspection detail: image + mask/heatmap overlay, vision metrics,
// clear state designs for [OK | Defect | Unknown | Failed], and tablet-optimized controls.
import { useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  Bot,
  Check,
  CheckCircle2,
  Flame,
  HelpCircle,
  Layers,
  Loader2,
  RotateCcw,
  Scan,
  Send,
  Wrench,
  X,
  XCircle,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import type { Inspection } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { InspectionImage, type OverlayMode } from '@/components/InspectionImage'
import { StatusBadge, VerdictBadge } from '@/components/status'
import { levelStyles, type Level } from '@/lib/status'
import { formatMs, formatPercent, formatTime, shortId } from '@/lib/format'
import { cn } from '@/lib/utils'
import {
  ApiError,
  useInspectionQuery,
  useDecisionMutation,
  useChatMutation,
  useRetryExplainMutation,
} from '@/api/queries'

export function InspectionDetailPage() {
  const { id } = useParams()
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('mask')

  const query = useInspectionQuery(id)

  if (query.isPending) return <DetailSkeleton />

  if (query.isError) {
    const notFound = query.error instanceof ApiError && query.error.status === 404
    return (
      <div className="flex flex-col items-center gap-4 py-24 text-center">
        <h1 className="text-2xl font-semibold">{notFound ? 'Inspection not found' : 'Could not load this inspection'}</h1>
        <p className="text-muted-foreground">
          {notFound ? 'The board record does not exist or may have expired.' : String((query.error as Error)?.message ?? query.error)}
        </p>
        <div className="flex gap-3">
          {!notFound && (
            <Button variant="outline" onClick={() => query.refetch()}>
              <RotateCcw /> Retry
            </Button>
          )}
          <Button variant="outline" nativeButton={false} render={<Link to="/live" />}>
            <ArrowLeft /> Back to live line
          </Button>
        </div>
      </div>
    )
  }

  const inspection = query.data
  const v = inspection.vision

  // Determine state category: 'failed' | 'ok' | 'unknown' | 'defect'
  const isFailed = inspection.status === 'failed' || (!v && Boolean(inspection.error))
  const isOk = v ? (!v.is_defective || v.severity === 'none') : false
  const isUnknown = v ? (v.is_defective && (v.defect_type === 'unknown' || !v.defect_type)) : false
  const isDefect = v ? (v.is_defective && !isUnknown && !isOk) : false

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Title */}
      <div className="space-y-3">
        <Link
          to="/live"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Return to live line
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
                Board #{shortId(inspection.id)}
              </h1>
              <span className="font-mono text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                {inspection.id}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Inspected at {formatTime(inspection.created_at)}
              {inspection.line_id && ` · ${inspection.line_id}`} ·{' '}
              {inspection.source === 'upload' ? 'Manual Upload' : 'Automated Line Camera'}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={inspection.status} className="px-3 py-1 text-sm" />
            <VerdictBadge vision={v} size="lg" />
          </div>
        </div>
      </div>

      {/* State Banner: OK, Defect, Unknown, or Failed */}
      <StateBanner isOk={isOk} isDefect={isDefect} isUnknown={isUnknown} isFailed={isFailed} inspection={inspection} />

      {/* Main Grid: Tablet-Optimized (Single column on mobile, 5-col split on desktop/tablet-landscape) */}
      <div className="grid gap-6 lg:grid-cols-5">
        {/* Left Column: Image with Mask/Heatmap switcher + Metrics */}
        <Card className="lg:col-span-3">
          <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
            <div>
              <CardTitle className="text-lg">Machine Vision Inspection</CardTitle>
              <CardDescription>
                {overlayMode === 'mask' && 'Red silhouette highlights anomalous area.'}
                {overlayMode === 'heatmap' && 'Continuous PatchCore activation heatmap (Jet gradient).'}
                {overlayMode === 'none' && 'Raw unaltered optical camera capture.'}
              </CardDescription>
            </div>

            {/* Mode Switcher: Raw | Mask | Heatmap */}
            <div className="inline-flex rounded-lg border border-border bg-muted/60 p-1">
              <button
                type="button"
                id="view-mode-none"
                onClick={() => setOverlayMode('none')}
                className={cn(
                  'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer',
                  overlayMode === 'none' ? 'bg-background text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Scan className="size-3.5" /> Raw
              </button>
              <button
                type="button"
                id="view-mode-mask"
                disabled={!v?.mask_url}
                onClick={() => setOverlayMode('mask')}
                className={cn(
                  'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-40',
                  overlayMode === 'mask' ? 'bg-background text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Layers className="size-3.5" /> Mask
              </button>
              <button
                type="button"
                id="view-mode-heatmap"
                disabled={!v?.heatmap_url}
                onClick={() => setOverlayMode('heatmap')}
                className={cn(
                  'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-40',
                  overlayMode === 'heatmap' ? 'bg-background text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Flame className="size-3.5 text-review" /> Heatmap
              </button>
            </div>
          </CardHeader>

          <CardContent className="space-y-6">
            <InspectionImage
              key={inspection.id}
              imageUrl={inspection.image_url}
              maskUrl={v?.mask_url}
              heatmapUrl={v?.heatmap_url}
              overlayMode={overlayMode}
            />

            {/* Anomaly Gauge & Numerical Metrics */}
            {v ? (
              <div className="space-y-4">
                <AnomalyGauge score={v.anomaly_score} threshold={v.anomaly_threshold} />

                <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <MetricCard
                    label="Anomaly Score"
                    value={v.anomaly_score.toFixed(3)}
                    hint={`Gate: ${v.anomaly_threshold.toFixed(2)}`}
                    highlight={v.anomaly_score >= v.anomaly_threshold}
                  />
                  <MetricCard
                    label="Confidence"
                    value={formatPercent(v.defect_confidence, 0)}
                    hint="Classifier certainty"
                  />
                  <MetricCard
                    label="Defect Area"
                    value={formatPercent(v.defect_area_ratio)}
                    hint="Area coverage"
                  />
                  <MetricCard
                    label="Inference Latency"
                    value={formatMs(v.latency_ms)}
                    hint="AMD ROCm GPU"
                  />
                </dl>
              </div>
            ) : (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
                No vision metrics available for this inspection.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Column: AI Agent RAG Analysis + Operator Decision + Chat */}
        <div className="flex flex-col gap-6 lg:col-span-2">
          <AgentPanel inspection={inspection} />
          <DecisionPanel inspection={inspection} />
          <ChatPanel inspection={inspection} />
        </div>
      </div>
    </div>
  )
}

/** Same layout as the page while the inspection loads, so nothing jumps and no fake data shows. */
function DetailSkeleton() {
  const bar = 'animate-pulse rounded bg-muted'
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading inspection">
      <div className="space-y-3">
        <div className={cn(bar, 'h-4 w-32')} />
        <div className={cn(bar, 'h-8 w-72')} />
        <div className={cn(bar, 'h-4 w-56')} />
      </div>
      <div className={cn(bar, 'h-16 w-full rounded-xl')} />
      <div className="grid gap-6 lg:grid-cols-5">
        <div className={cn(bar, 'aspect-square rounded-xl lg:col-span-3')} />
        <div className="flex flex-col gap-6 lg:col-span-2">
          <div className={cn(bar, 'h-48 rounded-xl')} />
          <div className={cn(bar, 'h-40 rounded-xl')} />
        </div>
      </div>
    </div>
  )
}

/** Visual State Banners for OK / Defect / Unknown / Failed */
function StateBanner({
  isOk,
  isDefect,
  isUnknown,
  isFailed,
  inspection,
}: {
  isOk: boolean
  isDefect: boolean
  isUnknown: boolean
  isFailed: boolean
  inspection: Inspection
}) {
  if (isFailed) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-destructive/40 bg-destructive/15 p-4 text-sm text-destructive">
        <XCircle className="size-6 shrink-0" />
        <div>
          <h2 className="font-semibold text-base">Inspection Processing Failed</h2>
          <p className="text-zinc-300">
            {inspection.error ?? 'Vision model failed or timed out. Check ML service ROCm connection.'}
          </p>
        </div>
      </div>
    )
  }

  if (isOk) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-ok/40 bg-ok/10 p-4 text-sm text-ok">
        <CheckCircle2 className="size-6 shrink-0 text-ok" />
        <div>
          <h2 className="font-semibold text-base">Quality Gate Passed — No Defect Found</h2>
          <p className="text-zinc-300">
            Anomaly score is well below rejection threshold. Board meets IPC-A-610 standards.
          </p>
        </div>
      </div>
    )
  }

  if (isUnknown) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-review/40 bg-review/15 p-4 text-sm text-review">
        <HelpCircle className="size-6 shrink-0 text-review" />
        <div>
          <h2 className="font-semibold text-base">Unclassified Anomaly — Human Review Required</h2>
          <p className="text-zinc-300">
            PatchCore detected an anomalous pixel cluster, but classifier confidence is low. Please manually verify with the heatmap.
          </p>
        </div>
      </div>
    )
  }

  if (isDefect) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-defect/40 bg-defect/10 p-4 text-sm text-defect">
        <AlertTriangle className="size-6 shrink-0 text-defect" />
        <div>
          <h2 className="font-semibold text-base">
            Defect Detected: {inspection.vision?.defect_type?.toUpperCase()} ({inspection.vision?.severity} severity)
          </h2>
          <p className="text-zinc-300">
            Anomaly exceeds threshold. Review the agent's QC manual recommendation below before acting.
          </p>
        </div>
      </div>
    )
  }

  return null
}

/** Visual Anomaly Score vs Threshold Gauge Bar */
function AnomalyGauge({ score, threshold }: { score: number; threshold: number }) {
  const percent = Math.min(100, Math.max(0, score * 100))
  const threshPercent = Math.min(100, Math.max(0, threshold * 100))
  const isExceeded = score >= threshold

  return (
    <div className="space-y-1.5 rounded-lg border border-border bg-card/60 p-3">
      <div className="flex justify-between text-xs font-mono">
        <span className="flex items-center gap-1.5">
          <span className="text-muted-foreground">Anomaly Score:</span>
          <span className={cn('font-bold', isExceeded ? 'text-defect' : 'text-ok')}>
            {score.toFixed(3)}
          </span>
        </span>
        <span className="text-muted-foreground">Threshold Limit: {threshold.toFixed(2)}</span>
      </div>

      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            isExceeded ? 'bg-defect' : 'bg-ok',
          )}
          style={{ width: `${percent}%` }}
        />
        {/* White marker for threshold line */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-white shadow-xs z-10"
          style={{ left: `${threshPercent}%` }}
          title={`Rejection threshold at ${threshold}`}
        />
      </div>
    </div>
  )
}

function MetricCard({
  label,
  value,
  hint,
  highlight = false,
}: {
  label: string
  value: string
  hint?: string
  highlight?: boolean
}) {
  return (
    <div className={cn('rounded-lg border p-3', highlight ? 'border-defect/40 bg-defect/10' : 'border-border bg-muted/20')}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn('mt-0.5 font-mono text-lg font-semibold tabular-nums', highlight && 'text-defect')}>{value}</dd>
      {hint && <dd className="text-xs text-muted-foreground truncate">{hint}</dd>}
    </div>
  )
}

function AgentPanel({ inspection }: { inspection: Inspection }) {
  const e = inspection.explanation
  const retryMutation = useRetryExplainMutation(inspection.id)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Bot className="size-5 text-primary" /> Agent Explanation (QC Manual)
        </CardTitle>
        {e?.model && <CardDescription className="font-mono text-xs">{e.model}</CardDescription>}
        {e && (
          <CardAction>
            <span className="rounded-md border border-border px-2 py-0.5 text-xs font-medium uppercase text-muted-foreground">
              Priority: {e.priority.replace('_', ' ')}
            </span>
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="gap-4">
        {inspection.status === 'explaining' && (
          <div className="space-y-3" aria-live="polite">
            <p className="text-sm text-muted-foreground">Reading the QC manual and analysing the defect…</p>
            <div className="h-4 w-full animate-pulse rounded bg-muted" />
            <div className="h-4 w-5/6 animate-pulse rounded bg-muted" />
            <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
          </div>
        )}

        {inspection.status === 'explain_failed' && (
          <>
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              <span className="font-medium">Could not generate explanation:</span> {inspection.error ?? 'Agent timed out'}
            </div>
            <Button
              id="retry-explain"
              variant="outline"
              disabled={retryMutation.isPending}
              onClick={() => retryMutation.mutate()}
            >
              {retryMutation.isPending ? <Loader2 className="animate-spin" /> : <RotateCcw />}
              {retryMutation.isPending ? 'Retrying…' : 'Try again'}
            </Button>
          </>
        )}

        {!e && inspection.vision && !inspection.vision.is_defective && (
          <p className="text-muted-foreground text-sm">No anomaly detected. Quality criteria satisfied.</p>
        )}

        {e && (
          <>
            <p className="text-sm leading-relaxed">{e.summary}</p>

            {e.likely_causes && e.likely_causes.length > 0 && (
              <div>
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Likely Root Causes
                </h3>
                <ul className="list-disc space-y-1 pl-5 text-sm">
                  {e.likely_causes.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="rounded-lg border border-border bg-muted/40 p-3.5">
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Recommended Action
              </h3>
              <p className="font-medium text-sm">{e.recommended_action}</p>
            </div>

            {e.sources && e.sources.length > 0 && (
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Cited QC Manual References
                </h3>
                <ul className="space-y-2">
                  {e.sources.map((s) => (
                    <li key={s.document + s.section} className="flex gap-2 text-xs">
                      <BookOpen className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                      <div>
                        <span className="font-medium text-zinc-200">
                          {s.document}, §{s.section}
                        </span>
                        {s.snippet && <p className="mt-0.5 text-muted-foreground italic">“{s.snippet}”</p>}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {e.needs_human_review && (
              <p className="flex items-center gap-2 text-xs text-review font-medium">
                <AlertTriangle className="size-4" /> AI recommends second technician inspection.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

const decisions: { value: 'accept' | 'rework' | 'reject'; label: string; icon: typeof Check; level: Level }[] = [
  { value: 'accept', label: 'Accept', icon: Check, level: 'ok' },
  { value: 'rework', label: 'Rework', icon: Wrench, level: 'review' },
  { value: 'reject', label: 'Reject', icon: X, level: 'defect' },
]

function DecisionPanel({ inspection }: { inspection: Inspection }) {
  const [localDecision, setLocalDecision] = useState<Inspection['decision']>(inspection.decision)
  const decisionMutation = useDecisionMutation(inspection.id)

  const d = localDecision ?? inspection.decision

  if (d) {
    const chosen = decisions.find((x) => x.value === d.decision) ?? decisions[0]
    const s = levelStyles[chosen.level]
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recorded Decision</CardTitle>
        </CardHeader>
        <CardContent>
          <div className={cn('flex items-center gap-3 rounded-lg border p-4', s.soft, s.border)}>
            <chosen.icon className={cn('size-6', s.text)} />
            <div>
              <div className={cn('text-lg font-semibold', s.text)}>{chosen.label}</div>
              <div className="text-sm text-muted-foreground">
                {d.operator ?? 'Operator'} · {formatTime(d.decided_at)} · in {formatMs(d.time_to_decision_ms)}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  const handleDecision = (value: 'accept' | 'rework' | 'reject') => {
    const optimistic: Inspection['decision'] = {
      decision: value,
      followed_recommendation: true,
      operator: 'operator-1',
      decided_at: new Date().toISOString(),
      time_to_decision_ms: 12_400,
    }
    setLocalDecision(optimistic)

    decisionMutation.mutate({
      decision: value,
      followed_recommendation: true,
      operator: 'operator-1',
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Operator Decision</CardTitle>
        <CardDescription>Touch or click to route board. Ready anytime.</CardDescription>
      </CardHeader>
      <CardContent>
        {/* Tablet-friendly large buttons (min 64-80px tall) */}
        <div className="grid grid-cols-3 gap-3">
          {decisions.map(({ value, label, icon: Icon, level }) => {
            const s = levelStyles[level]
            return (
              <button
                key={value}
                id={`decision-${value}`}
                type="button"
                disabled={decisionMutation.isPending}
                onClick={() => handleDecision(value)}
                className={cn(
                  'flex h-20 min-h-[72px] flex-col items-center justify-center gap-1.5 rounded-xl border text-base font-semibold transition-all',
                  'hover:brightness-125 active:scale-[0.97] focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                  'disabled:opacity-50 cursor-pointer shadow-xs',
                  s.soft,
                  s.text,
                  s.border,
                )}
              >
                <Icon className="size-6" />
                {label}
              </button>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

function ChatPanel({ inspection }: { inspection: Inspection }) {
  const [input, setInput] = useState('')
  const [localChat, setLocalChat] = useState<Inspection['chat']>(inspection.chat ?? [])
  const chatMutation = useChatMutation(inspection.id)

  const messages = localChat && localChat.length > 0 ? localChat : (inspection.chat ?? [])
  const canChat = inspection.explanation != null

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || chatMutation.isPending) return

    const userMsg = {
      role: 'operator' as const,
      content: input.trim(),
      created_at: new Date().toISOString(),
    }
    setLocalChat((prev) => [...(prev ?? []), userMsg])
    const prompt = input.trim()
    setInput('')

    chatMutation.mutate(prompt, {
      onSuccess: (reply) => {
        if (reply) {
          setLocalChat((prev) => [...(prev ?? []), reply])
        }
      },
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Copilot Assistant</CardTitle>
        <CardDescription>Ask follow-up questions about this board defect</CardDescription>
      </CardHeader>
      <CardContent className="gap-4">
        {messages.length > 0 ? (
          <ul className="flex max-h-56 flex-col gap-2 overflow-y-auto pr-1">
            {messages.map((m, idx) => (
              <li
                key={m.created_at ?? idx}
                className={cn(
                  'max-w-[85%] rounded-lg px-3 py-2 text-sm',
                  m.role === 'operator' ? 'self-end bg-primary text-primary-foreground' : 'self-start bg-muted',
                )}
              >
                {m.content}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            {canChat ? 'Ask: “Does IPC class 2 allow rework on this trace?”' : 'Available once explanation completes.'}
          </p>
        )}

        <form className="flex gap-2" onSubmit={handleSend}>
          <input
            id="chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!canChat || chatMutation.isPending}
            placeholder="Ask about this defect…"
            className="h-11 min-w-0 flex-1 rounded-lg border border-input bg-input/30 px-3.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
          />
          <Button
            id="chat-send"
            type="submit"
            size="icon-lg"
            disabled={!canChat || chatMutation.isPending || !input.trim()}
            aria-label="Send"
            className="h-11 w-11"
          >
            {chatMutation.isPending ? <Loader2 className="animate-spin" /> : <Send />}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
