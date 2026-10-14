// App frame: top bar with brand, navigation and system health; the page renders below.
import { Activity, History, ScanLine, Upload } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { StatusDot } from '@/components/status'
import type { Level } from '@/lib/status'
import { useHealthQuery, type Health } from '@/api/queries'

const nav = [
  { to: '/live', label: 'Live line', icon: Activity },
  { to: '/history', label: 'History & stats', icon: History },
  { to: '/upload', label: 'Upload', icon: Upload },
]

function healthLevel(h: Health | undefined, isError: boolean): Level {
  if (isError) return 'defect'
  if (!h) return 'unknown'
  if (h.status === 'ok' && h.ml_service === 'ok') return 'ok'
  return h.ml_service === 'down' ? 'defect' : 'review'
}

function HealthIndicator() {
  const health = useHealthQuery()
  const level = healthLevel(health.data as Health | undefined, health.isError)
  const text = health.isError
    ? 'Backend unreachable'
    : health.data
      ? `ML ${health.data.ml_service}${health.data.ml_device ? ` · ${health.data.ml_device}` : ''}`
      : 'Connecting…'

  return (
    <div
      id="system-health"
      className="flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1.5 text-xs text-muted-foreground"
      title="Backend and ML service health"
    >
      <StatusDot level={level} pulse={level === 'ok'} />
      <span className="max-w-48 truncate">{text}</span>
    </div>
  )
}

export function AppShell() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6">
          <NavLink to="/live" className="flex shrink-0 items-center gap-2.5" id="brand-link">
            <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ScanLine className="size-5" />
            </span>
            <span className="leading-tight">
              <span className="block text-base font-semibold tracking-tight">Defect Copilot</span>
              <span className="block text-xs text-muted-foreground">Line 1 · PCB inspection</span>
            </span>
          </NavLink>

          <nav className="flex flex-1 items-center gap-1 overflow-x-auto" aria-label="Main">
            {nav.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                id={`nav-${to.slice(1)}`}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors',
                    isActive
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                  )
                }
              >
                <Icon className="size-4" />
                {label}
              </NavLink>
            ))}
          </nav>

          <HealthIndicator />
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}
