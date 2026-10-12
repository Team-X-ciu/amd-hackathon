// Day-1 integration screen: proves frontend -> backend -> ML service works.
// Replace with the real operator dashboard (see docs/TASKS.md).
import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

const API = import.meta.env.VITE_API_URL ?? '/api'

type Health = { status: string; ml_service: string; ml_device?: string }

// Shape returned by the backend's day-1 spike (raw ML result). The final
// endpoint returns the `Inspection` type from src/api/client.ts.
type SpikeResult = {
  vision: {
    anomaly_score: number
    is_defective: boolean
    defect_type: string | null
    defect_confidence: number | null
    severity: 'none' | 'low' | 'medium' | 'high'
    defect_area_ratio: number | null
    mask_png_base64: string | null
    latency_ms: number
  }
}

const severityStyle: Record<string, string> = {
  none: 'bg-ok/15 text-ok border-ok/40',
  low: 'bg-review/15 text-review border-review/40',
  medium: 'bg-review/15 text-review border-review/40',
  high: 'bg-defect/15 text-defect border-defect/40',
}

export default function App() {
  const [preview, setPreview] = useState<string | null>(null)

  const health = useQuery({
    queryKey: ['health'],
    queryFn: async (): Promise<Health> => (await fetch(`${API}/health`)).json(),
    refetchInterval: 10_000,
  })

  const inspect = useMutation({
    mutationFn: async (file: File): Promise<SpikeResult> => {
      const form = new FormData()
      form.append('image', file)
      const res = await fetch(`${API}/inspections`, { method: 'POST', body: form })
      if (!res.ok) throw new Error((await res.json()).error ?? res.statusText)
      return res.json()
    },
  })

  const v = inspect.data?.vision

  return (
    <main className="mx-auto max-w-5xl p-4 sm:p-8">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Defect Copilot</h1>
        <span className="rounded border border-zinc-700 px-3 py-1 font-mono text-sm text-zinc-400">
          backend: {health.data?.status ?? '…'} · ml: {health.data?.ml_service ?? '…'}
          {health.data?.ml_device ? ` · ${health.data.ml_device}` : ''}
        </span>
      </header>

      <label className="mb-6 flex cursor-pointer items-center justify-center rounded-lg border-2 border-dashed border-zinc-700 p-8 text-zinc-400 hover:border-zinc-500">
        <input
          type="file"
          accept="image/png,image/jpeg"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (!file) return
            setPreview(URL.createObjectURL(file))
            inspect.mutate(file)
          }}
        />
        Drop or choose a part image
      </label>

      {inspect.isError && <p className="mb-4 text-defect">{inspect.error.message}</p>}

      {preview && (
        <section className="grid gap-6 md:grid-cols-2">
          <div className="relative overflow-hidden rounded-lg border border-zinc-800">
            <img src={preview} alt="Inspected part" className="block w-full" />
            {v?.mask_png_base64 && (
              // Mask is white-on-black: use it as a luminance mask over a red layer,
              // so only the defect area turns red
              <div
                aria-label="Defect mask"
                className="absolute inset-0 bg-defect/55"
                style={{
                  maskImage: `url(data:image/png;base64,${v.mask_png_base64})`,
                  maskMode: 'luminance',
                  maskSize: '100% 100%',
                }}
              />
            )}
          </div>

          <div className="space-y-3">
            {inspect.isPending && <p className="text-zinc-400">Inspecting…</p>}
            {v && (
              <>
                <span className={`inline-block rounded border px-3 py-1 text-lg font-semibold ${severityStyle[v.severity]}`}>
                  {v.is_defective ? `${v.defect_type} · ${v.severity}` : 'OK'}
                </span>
                <dl className="grid grid-cols-2 gap-2 font-mono text-sm">
                  <dt className="text-zinc-500">anomaly score</dt>
                  <dd>{v.anomaly_score.toFixed(3)}</dd>
                  <dt className="text-zinc-500">confidence</dt>
                  <dd>{v.defect_confidence?.toFixed(3) ?? '—'}</dd>
                  <dt className="text-zinc-500">defect area</dt>
                  <dd>{v.defect_area_ratio != null ? `${(v.defect_area_ratio * 100).toFixed(1)}%` : '—'}</dd>
                  <dt className="text-zinc-500">latency</dt>
                  <dd>{v.latency_ms} ms</dd>
                </dl>
              </>
            )}
          </div>
        </section>
      )}
    </main>
  )
}
