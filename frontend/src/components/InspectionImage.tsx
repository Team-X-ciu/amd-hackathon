// Board image with interactive overlay modes:
//   - 'none': Raw machine-vision camera capture
//   - 'mask': Sharp red defect mask outline
//   - 'heatmap': Continuous PatchCore anomaly heatmap gradient
import { useState } from 'react'
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
  const [imgError, setImgError] = useState(false)

  // Use provided URL or fallback to the sample machine-vision PCB image if invalid or broken
  const isValidUrl = imageUrl && (imageUrl.startsWith('http') || imageUrl.startsWith('/') || imageUrl.startsWith('data:'))
  const src = (!imgError && isValidUrl) ? imageUrl : '/samples/pcb-scratch.jpg'

  // Mask fallback
  const isMaskValid = maskUrl && (maskUrl.startsWith('http') || maskUrl.startsWith('/') || maskUrl.startsWith('data:'))
  const effectiveMask = isMaskValid ? maskUrl : '/samples/pcb-scratch-mask.svg'

  // Heatmap fallback
  const isHeatmapValid = heatmapUrl && (heatmapUrl.startsWith('http') || heatmapUrl.startsWith('/') || heatmapUrl.startsWith('data:'))
  const effectiveHeatmap = isHeatmapValid ? heatmapUrl : '/samples/pcb-scratch-heatmap.svg'

  return (
    <div className={cn('relative aspect-square w-full overflow-hidden rounded-xl border border-border bg-black select-none', className)}>
      {/* 1. Base Camera Image */}
      <img
        src={src}
        alt="Machine vision camera capture"
        className="block size-full object-cover transition-transform duration-300"
        onError={() => setImgError(true)}
      />

      {/* 2. Red Defect Mask (Luminance Mask Overlay) */}
      <div
        aria-label="Binary defect mask"
        className={cn(
          'absolute inset-0 bg-defect/65 transition-opacity duration-300 pointer-events-none',
          overlayMode === 'mask' ? 'opacity-100' : 'opacity-0',
        )}
        style={{
          maskImage: `url(${effectiveMask})`,
          maskMode: 'luminance',
          maskSize: '100% 100%',
        }}
      />

      {/* 3. PatchCore Anomaly Heatmap Overlay */}
      <div
        aria-label="PatchCore anomaly heatmap"
        className={cn(
          'absolute inset-0 transition-opacity duration-300 pointer-events-none mix-blend-screen',
          overlayMode === 'heatmap' ? 'opacity-90' : 'opacity-0',
        )}
        style={{
          backgroundImage: `url(${effectiveHeatmap})`,
          backgroundSize: '100% 100%',
        }}
      />

      {/* Mode Indicator Badge in bottom-left corner of image */}
      <div className="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-md bg-black/75 px-2.5 py-1 text-xs font-mono text-zinc-300 backdrop-blur-sm border border-white/10">
        <span className="size-2 rounded-full bg-primary" />
        <span>View: {overlayMode.toUpperCase()}</span>
      </div>
    </div>
  )
}
