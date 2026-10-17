// Board image with interactive overlay modes:
//   - 'none': Raw machine-vision camera capture
//   - 'mask': Sharp red defect mask outline
//   - 'heatmap': Continuous PatchCore anomaly heatmap gradient
// Only real files from the API are shown: no sample fallback while loading or on error.
import { useState } from 'react'
import { ImageOff } from 'lucide-react'
import { cn } from '@/lib/utils'

export type OverlayMode = 'none' | 'mask' | 'heatmap'

export function InspectionImage({
  imageUrl,
  maskUrl,
  heatmapUrl,
  overlayMode = 'mask',
  className,
}: {
  imageUrl?: string | null
  maskUrl?: string | null
  heatmapUrl?: string | null
  overlayMode?: OverlayMode
  className?: string
}) {
  const [state, setState] = useState<'loading' | 'loaded' | 'error'>(imageUrl ? 'loading' : 'error')

  return (
    <div className={cn('relative aspect-square w-full overflow-hidden rounded-xl border border-border bg-black select-none', className)}>
      {/* 1. Base Camera Image */}
      {imageUrl && state !== 'error' && (
        <img
          src={imageUrl}
          alt="Machine vision camera capture"
          className={cn('block size-full object-cover transition-opacity duration-300', state === 'loaded' ? 'opacity-100' : 'opacity-0')}
          onLoad={() => setState('loaded')}
          onError={() => setState('error')}
        />
      )}
      {state === 'loading' && <div aria-label="Loading image" className="absolute inset-0 animate-pulse bg-muted" />}
      {state === 'error' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
          <ImageOff className="size-8" />
          Image unavailable
        </div>
      )}

      {/* 2. Red Defect Mask (Luminance Mask Overlay) */}
      {maskUrl && state === 'loaded' && (
        <div
          aria-label="Binary defect mask"
          className={cn(
            'absolute inset-0 bg-defect/65 transition-opacity duration-300 pointer-events-none',
            overlayMode === 'mask' ? 'opacity-100' : 'opacity-0',
          )}
          style={{
            maskImage: `url(${maskUrl})`,
            maskMode: 'luminance',
            maskSize: '100% 100%',
          }}
        />
      )}

      {/* 3. PatchCore Anomaly Heatmap Overlay */}
      {heatmapUrl && state === 'loaded' && (
        <div
          aria-label="PatchCore anomaly heatmap"
          className={cn(
            'absolute inset-0 transition-opacity duration-300 pointer-events-none mix-blend-screen',
            overlayMode === 'heatmap' ? 'opacity-90' : 'opacity-0',
          )}
          style={{
            backgroundImage: `url(${heatmapUrl})`,
            backgroundSize: '100% 100%',
          }}
        />
      )}

      {/* Mode Indicator Badge in bottom-left corner of image */}
      {state === 'loaded' && (
        <div className="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-md bg-black/75 px-2.5 py-1 text-xs font-mono text-zinc-300 backdrop-blur-sm border border-white/10">
          <span className="size-2 rounded-full bg-primary" />
          <span>View: {overlayMode.toUpperCase()}</span>
        </div>
      )}
    </div>
  )
}
