// Typed API client. Types come from contracts/backend.openapi.yaml (npm run gen:types).
import createClient from 'openapi-fetch'
import type { components, paths } from './types'

export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? '/api',
})

export type Inspection = components['schemas']['Inspection']
export type VisionResult = components['schemas']['VisionResult']
export type Explanation = components['schemas']['Explanation']
export type Stats = components['schemas']['Stats']
