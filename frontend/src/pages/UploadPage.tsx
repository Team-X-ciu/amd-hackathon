// Upload a board image by hand. Started as the day-1 integration screen
// (frontend -> backend -> ML service); it still reads the backend spike's `{ vision }`
// shape. Switch to the `Inspection` type when the backend returns it.
import { useMutation } from '@tanstack/react-query'
import { UploadCloud } from 'lucide-react'
import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const API = import.meta.env.VITE_API_URL ?? '/api'

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

export function UploadPage() {
  const [preview, setPreview] = useState<string | null>(null)

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
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Upload</h1>
        <p className="mt-1 text-muted-foreground">Inspect a single board image by hand.</p>
      </div>

      <label
        id="upload-dropzone"
        className="flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-border bg-card/40 p-10 text-muted-foreground transition-colors hover:border-ring hover:bg-card/70"
      >
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
        <UploadCloud className="size-10" />
        <span className="text-base">Drop or choose a board image (PNG or JPEG)</span>
      </label>

      {inspect.isError && <p className="text-destructive">{inspect.error.message}</p>}

      {preview && (
        <section className="grid gap-6 md:grid-cols-2">
          <div className="relative overflow-hidden rounded-lg border border-border">
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

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Result</CardTitle>
            </CardHeader>
            <CardContent>
              {inspect.isPending && <p className="text-muted-foreground">Inspecting…</p>}
              {v && (
                <>
                  <span
                    className={cn(
                      'inline-block self-start rounded-md border px-3 py-1 text-lg font-semibold capitalize',
                      severityStyle[v.severity],
                    )}
                  >
                    {v.is_defective ? `${v.defect_type} · ${v.severity}` : 'OK'}
                  </span>
                  <dl className="grid grid-cols-2 gap-2 font-mono text-sm">
                    <dt className="text-muted-foreground">anomaly score</dt>
                    <dd>{v.anomaly_score.toFixed(3)}</dd>
                    <dt className="text-muted-foreground">confidence</dt>
                    <dd>{v.defect_confidence?.toFixed(3) ?? '—'}</dd>
                    <dt className="text-muted-foreground">defect area</dt>
                    <dd>{v.defect_area_ratio != null ? `${(v.defect_area_ratio * 100).toFixed(1)}%` : '—'}</dd>
                    <dt className="text-muted-foreground">latency</dt>
                    <dd>{v.latency_ms} ms</dd>
                  </dl>
                </>
              )}
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  )
}
