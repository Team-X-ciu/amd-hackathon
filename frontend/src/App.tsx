// Routes. Every screen renders inside AppShell (top bar + navigation).
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { HistoryPage } from '@/pages/HistoryPage'
import { InspectionDetailPage } from '@/pages/InspectionDetailPage'
import { LiveLinePage } from '@/pages/LiveLinePage'
import { UploadPage } from '@/pages/UploadPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/live" replace />} />
        <Route path="live" element={<LiveLinePage />} />
        <Route path="inspections/:id" element={<InspectionDetailPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="*" element={<Navigate to="/live" replace />} />
      </Route>
    </Routes>
  )
}
