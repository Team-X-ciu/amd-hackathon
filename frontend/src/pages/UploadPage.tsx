// Upload a board image by hand. On success the backend returns the saved `Inspection`;
// we seed the detail query with it and open the detail page, which shows the vision result
// and follows the explanation while it runs.
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, UploadCloud } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Inspection } from '@/api/client'
import { ApiError } from '@/api/queries'
import { cn } from '@/lib/utils'

const API = import.meta.env.VITE_API_URL ?? '/api'

export function UploadPage() {
  const [preview, setPreview] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const inspect = useMutation({
    mutationFn: async (file: File): Promise<Inspection> => {
      const form = new FormData()
      form.append('image', file)
      const res = await fetch(`${API}/inspections`, { method: 'POST', body: form })
      // Every backend error is the contract's `Error` JSON; guard anyway so a proxy page
      // shows "HTTP 502" instead of a JSON parse error.
      const body = await res.json().catch(() => null)
      if (!res.ok) throw new ApiError(res.status, body?.error ?? `HTTP ${res.status}`)
      return body as Inspection
    },
    onSuccess: (inspection) => {
      queryClient.setQueryData(['inspection', inspection.id], inspection)
      queryClient.invalidateQueries({ queryKey: ['inspections'] })
      navigate(`/inspections/${inspection.id}`)
    },
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Upload</h1>
        <p className="mt-1 text-muted-foreground">Inspect a single board image by hand.</p>
      </div>

      <label
        id="upload-dropzone"
        aria-disabled={inspect.isPending}
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-border bg-card/40 p-10 text-muted-foreground transition-colors',
          inspect.isPending ? 'cursor-wait opacity-60' : 'cursor-pointer hover:border-ring hover:bg-card/70',
        )}
      >
        <input
          type="file"
          accept="image/png,image/jpeg"
          className="hidden"
          disabled={inspect.isPending}
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = '' // the same file can be chosen again after an error
            if (!file) return
            setPreview(URL.createObjectURL(file))
            inspect.mutate(file)
          }}
        />
        {inspect.isPending ? <Loader2 className="size-10 animate-spin" /> : <UploadCloud className="size-10" />}
        <span className="text-base">
          {inspect.isPending ? 'Inspecting…' : 'Drop or choose a board image (PNG or JPEG, up to 10 MB)'}
        </span>
      </label>

      {inspect.isError && (
        <p role="alert" className="text-destructive">
          {inspect.error.message}
        </p>
      )}

      {preview && (
        <div className="max-w-md overflow-hidden rounded-lg border border-border">
          <img src={preview} alt="Selected board" className="block w-full" />
        </div>
      )}
    </div>
  )
}
