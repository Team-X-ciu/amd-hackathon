# Frontend

React 19 + Vite + TypeScript + TanStack Query + Tailwind CSS v4.
Talks only to the backend. Contract: [`../contracts/backend.openapi.yaml`](../contracts/backend.openapi.yaml).

```bash
npm install
npm run dev        # http://localhost:5173, /api is proxied to the backend on :3000
npm run gen:types  # regenerate src/api/types.ts after a contract change
```

`src/App.tsx` is a day-1 integration screen (upload → mask overlay → result).
Replace it with the operator dashboard.

## Next setup steps

```bash
npx shadcn@latest init                       # the @/ alias is already configured
npx shadcn@latest add card table badge dialog tabs button
```

Without the backend, mock the API from the contract:

```bash
npx @stoplight/prism-cli mock ../contracts/backend.openapi.yaml -p 4010
VITE_API_URL=http://localhost:4010 npm run dev
```

## Screens

1. **Live line** — feed from the simulator (`GET /events`), newest inspection large, status colours.
2. **Inspection detail** — image + mask overlay, defect type, severity, agent explanation with
   cited manual sections, accept / reject / rework, follow-up chat.
3. **History & stats** — table with filters, defects by type, time to decision (Recharts).

Design: dark theme, large text, readable at a glance on a tablet. Green / amber / red only for status.
