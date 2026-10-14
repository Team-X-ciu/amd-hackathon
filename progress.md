# Frontend Progress & Changelog
**Last Updated:** `2026-10-14 19:39:00 +03:00`

## Overview
Tracking frontend progress for **Factory Defect Copilot** (AMD Developer Hackathon: ACT III).
The frontend is built with **React 19, Vite, TypeScript, Tailwind CSS v4, shadcn/ui (Vega preset), TanStack Query, and React Router**.

---

## Completed Tasks

### 1. Environment & Mock Setup
- Evaluated system dependencies and established that Frontend development can proceed without local Docker setup by running against contract mocks.
- Spun up API mock server using `@stoplight/prism-cli` based on `contracts/backend.openapi.yaml` at `http://localhost:4010`.
- Connected Vite dev server with `VITE_API_URL="http://localhost:4010"` and verified backend/ML service health checks (`backend: ok · ml: ok`).

### 2. UI Foundation & Design System (shadcn/ui)
- Initialized shadcn/ui with the **Vega** preset (`Base UI` engine, `Inter Variable` typography, and `Lucide` icon set).
- Installed core reusable UI primitives under `src/components/ui/`:
  - `button.tsx`
  - `card.tsx`
  - `table.tsx`
  - `badge.tsx`
  - `dialog.tsx`
  - `tabs.tsx`
- Enforced dark mode by default (`class="dark"` on `<html>` in `index.html`).
- Defined centralized status logic and coloring rules in `src/lib/status.ts` and `src/components/status.tsx`:
  - Strictly adhering to the project design rule: **Green (OK), Amber (Review), Red (Defect)** are strictly reserved for status indication.

### 3. Application Layout & Navigation
- Integrated `react-router-dom` in `src/main.tsx`.
- Built `AppShell` (`src/components/layout/AppShell.tsx`):
  - Sticky glassmorphic top header.
  - Active route navigation (`Live line`, `History & stats`, `Upload`).
  - Real-time Backend and AMD ML health status pill (`/health`).
- Configured declarative routes in `src/App.tsx`.

### 4. Implementation of the Three Primary Screens (Issue #29)

#### A. Live Line Screen (`/live`)
- File: `src/pages/LiveLinePage.tsx`
- **Shift KPI Cards:** Total inspected, defect rate, awaiting decisions, and average inspection latency.
- **Latest Board View:** Large view of the most recent board with luminance-based defect mask overlay, anomaly metrics, and direct CTA to open the inspection.
- **Recent Feed:** Clickable sidebar feed of incoming boards with live status dots and relative timestamps.
- **Simulator Controls:** Status badge and pause/resume button hooks.

#### B. Inspection Detail Screen (`/inspections/:id`)
- File: `src/pages/InspectionDetailPage.tsx`
- **Machine Vision Section:**
  - High-res PCB image view with interactive toggle for the defect mask overlay.
  - Anomaly score, threshold, confidence, defect area ratio, and inference latency.
- **Agent Explanation Panel (LLM + RAG):**
  - Summary and root cause analysis.
  - Recommended factory action box.
  - Cited QC manual sources (document, section, snippet).
  - Human review alert indicator and skeleton loading state for pending explanations.
- **Operator Decision Panel:**
  - Fast-action buttons: **Accept** (green), **Rework** (amber), **Reject** (red).
  - Decided state preview with operator identity and decision latency.
- **Interactive Chat Panel:** Follow-up Q&A input with the AI Copilot.

#### C. History & Stats Screen (`/history`)
- File: `src/pages/HistoryPage.tsx`
- **Key Performance Indicators:** Pitch metrics including average time-to-decision and recommendation follow rate.
- **Analytics Visualizations:**
  - Horizontal bar chart: *Defects by Type* (scratch, missing, bent, melt, unknown).
  - Vertical bar chart: *Defects by Severity* with custom color fills.
- **Inspection Data Table:**
  - Filter tabs: All, Defective, Good, Awaiting Decision.
  - Interactive rows with click-through navigation to inspection details.

#### D. Manual Upload Screen (`/upload`)
- File: `src/pages/UploadPage.tsx`
- Preserved the Day-1 manual upload integration pipeline for direct drag-and-drop end-to-end testing with backend/ML teams.

### 5. Mock Assets & Data Modeling
- Created contract-compliant mock datasets in `src/mocks/sample-data.ts` using types from `src/api/client.ts`.
- Generated realistic machine-vision sample image (`public/samples/pcb-scratch.jpg`) and matching luminance defect mask SVG (`public/samples/pcb-scratch-mask.svg`).
- Created formatting utilities in `src/lib/format.ts` (`formatPercent`, `formatMs`, `formatTime`, `timeAgo`, `shortId`).

### 6. Typed API Client & Contract Integration (Issue #29 Completed)
- File: `src/api/queries.ts`
- Implemented typed React Query hooks using `api` from `src/api/client.ts` (`openapi-fetch`):
  - `useHealthQuery()`: Queries `GET /health` with automatic background health monitoring.
  - `useInspectionsQuery()`: Queries `GET /inspections` with automatic feed polling.
  - `useInspectionQuery(id)`: Queries `GET /inspections/{id}` with conditional polling while in `explaining` state.
  - `useStatsQuery()`: Queries `GET /stats` for real-time shift analytics.
  - `useDecisionMutation()`: Posts to `POST /inspections/{id}/decision` with optimistic UI feedback.
  - `useChatMutation()`: Posts follow-up operator queries to `POST /inspections/{id}/chat`.
  - `useRetryExplainMutation()`: Retries agent explanation via `POST /inspections/{id}/explain`.
- Wired all hooks into `AppShell`, `LiveLinePage`, `InspectionDetailPage`, and `HistoryPage`.
- Added resilient fallbacks ensuring smooth UI display and realistic machine-vision overlays even when the mock server returns dynamic dummy data.

### 7. Issue #30 Completed: Inspection Detail Screen with Heatmap & Mask Overlay
- File: `src/pages/InspectionDetailPage.tsx` and `src/components/InspectionImage.tsx`
- **Mask & Heatmap Switcher:**
  - Added segmented view modes: `[ Raw | Mask | Heatmap ]`.
  - Implemented continuous PatchCore activation heatmap (`public/samples/pcb-scratch-heatmap.svg`) with CSS `mix-blend-screen` overlay mode.
  - Implemented binary defect mask with luminance masking.
  - Visual mode indicator badge directly on the image viewport.
- **Anomaly Score Gauge:**
  - Added dynamic progress bar comparing `anomaly_score` against `anomaly_threshold` with a distinct rejection threshold marker.
- **Four Clear Inspection States:**
  - **OK:** Green success banner, sub-threshold gauge, ready for next production stage.
  - **Defect:** Red/amber defect badge, anomaly alert banner, active mask/heatmap, and action recommendations.
  - **Unknown:** Amber human-review banner when anomaly is detected but classifier confidence is low.
  - **Failed:** Red pipeline failure alert with explicit error messaging and retry action.
- **Tablet Optimization:**
  - Large touch targets (72px+ decision buttons, 44px+ inputs) for touchscreens and factory workbench tablets.
  - Responsive layout transitioning smoothly from desktop 5-column grid to tablet-friendly stacked views.

### 8. Session Audit, Proxy Fix & Live Testing Log
**Timestamp:** `2026-10-14 19:39:00 +03:00`
- **502 Bad Gateway Fix:**
  - Resolved Vite proxy failure by creating `frontend/.env.local` (`VITE_API_URL=http://localhost:4010`).
  - Updated `vite.config.ts` proxy to automatically route `/api/*` to the Prism mock server on port 4010 and strip the `/api` prefix.
  - Verified endpoint responses: `/api/health` and `/api/inspections?limit=20` now reliably return **`200 OK`**.
- **Factory Conveyor Stream Accumulation:**
  - Upgraded `LiveLinePage.tsx` so incoming polling data does not replace the entire list.
  - New incoming boards are prepended to the top of the feed while previous boards slide down, maintaining an in-memory buffer of up to 15 historical boards.
  - Added an interactive **Pause / Resume** toggle allowing operators to freeze the live feed for inspection.
- **Overlay & Heatmap Implementation (Issue #30):**
  - Added multi-mode toggle: `Raw` (unfiltered camera), `Mask` (binary red silhouette), and `Heatmap` (PatchCore continuous Jet activation gradient).
  - Built real-time visual `AnomalyGauge` bar comparing scores against rejection thresholds.
  - Created dedicated UI state banners for `OK`, `Defect`, `Unknown`, and `Failed`.
  - Tablet optimization: minimum 72px touch targets for decision buttons and responsive grid behavior.
- **Final Build & Lint Check:**
  - Production build: `tsc -b && vite build` completed in **648ms** with **0 TypeScript errors** and **0 lint errors**.
  - All routes (`/live`, `/inspections/:id`, `/history`, `/upload`) verified functional.
  - **Issue #29 and Issue #30 are both 100% COMPLETE.**

---

## Next Steps
1. **Live Updates via Server-Sent Events (SSE):**
   - Hook up `GET /events` to stream real-time events (`inspection.created`, `inspection.explained`, `inspection.decided`) as boards arrive from the backend line simulator.
2. **Backend/ML Team Integration:**
   - Coordinate with backend teammates on `POST /inspections` full payload transition and testing against the real AMD ROCm ML service.

