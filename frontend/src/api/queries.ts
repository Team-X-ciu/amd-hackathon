// Typed React Query hooks for the backend contract.
// Uses `api` from src/api/client.ts (openapi-fetch) generated from backend.openapi.yaml.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Inspection, type Stats } from './client'
import type { components, paths } from './types'

export type DecisionInput = components['schemas']['DecisionInput']
export type ChatMessage = components['schemas']['ChatMessage']
export type Health = paths['/health']['get']['responses']['200']['content']['application/json']

/** A non-2xx answer from the backend, with its HTTP status and the contract's `Error.error` text. */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function apiError(response: Response, body: unknown): ApiError {
  const text = (body as { error?: unknown } | undefined)?.error
  return new ApiError(response.status, typeof text === 'string' ? text : `HTTP ${response.status}`)
}

/** Retry network blips and 5xx, but not answers that won't change (404, 400, 501). */
const retryUnlessFinal = (count: number, err: unknown) =>
  !(err instanceof ApiError && (err.status < 500 || err.status === 501)) && count < 2

/** System health indicator (/health) */
export function useHealthQuery() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const { data, error } = await api.GET('/health')
      if (error) throw error
      return data
    },
    refetchInterval: 10_000,
  })
}

/** List inspections (/inspections) */
export function useInspectionsQuery(
  params?: {
    status?: Inspection['status']
    defective_only?: boolean
    limit?: number
  },
  options?: {
    enabled?: boolean
    refetchInterval?: number | false
  },
) {
  return useQuery({
    queryKey: ['inspections', params],
    queryFn: async () => {
      const { data, error, response } = await api.GET('/inspections', {
        params: { query: params },
      })
      if (error || !response.ok) throw apiError(response, error)
      return data?.items ?? []
    },
    retry: retryUnlessFinal,
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval ?? 5_000,
  })
}

/** Get a single inspection (/inspections/{id}) */
export function useInspectionQuery(id: string | undefined) {
  return useQuery({
    queryKey: ['inspection', id],
    queryFn: async () => {
      if (!id) throw new Error('Missing inspection ID')
      const { data, error, response } = await api.GET('/inspections/{id}', {
        params: { path: { id } },
      })
      if (error || !response.ok) throw apiError(response, error)
      return data
    },
    retry: retryUnlessFinal,
    enabled: Boolean(id),
    // If the board is still being explained by the agent, poll every 2s until resolved
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'explaining' ? 2_000 : false
    },
  })
}

/** Shift and quality statistics (/stats) */
export function useStatsQuery() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      const { data, error, response } = await api.GET('/stats')
      if (error || !response.ok) throw apiError(response, error)
      return data as Stats
    },
    retry: retryUnlessFinal,
    refetchInterval: 10_000,
  })
}

/** Operator accepts, rejects, or sends board to rework (/inspections/{id}/decision) */
export function useDecisionMutation(inspectionId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: DecisionInput) => {
      if (!inspectionId) throw new Error('Missing inspection ID')
      const { data, error, response } = await api.POST('/inspections/{id}/decision', {
        params: { path: { id: inspectionId } },
        body,
      })
      if (error || !response.ok) throw apiError(response, error)
      return data
    },
    onSuccess: (inspection) => {
      // The answer is the updated Inspection: show the server's decision, not a guess
      if (inspection) queryClient.setQueryData(['inspection', inspection.id], inspection)
      queryClient.invalidateQueries({ queryKey: ['inspections'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })
}

/** Operator chats with the AI agent (/inspections/{id}/chat) */
export function useChatMutation(inspectionId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (message: string) => {
      if (!inspectionId) throw new Error('Missing inspection ID')
      const { data, error } = await api.POST('/inspections/{id}/chat', {
        params: { path: { id: inspectionId } },
        body: { message },
      })
      if (error) throw error
      return data
    },
    onSuccess: () => {
      if (inspectionId) {
        queryClient.invalidateQueries({ queryKey: ['inspection', inspectionId] })
      }
    },
  })
}

/** Retry agent explanation if it failed or timed out (/inspections/{id}/explain) */
export function useRetryExplainMutation(inspectionId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      if (!inspectionId) throw new Error('Missing inspection ID')
      const { data, error } = await api.POST('/inspections/{id}/explain', {
        params: { path: { id: inspectionId } },
      })
      if (error) throw error
      return data
    },
    onSuccess: () => {
      if (inspectionId) {
        queryClient.invalidateQueries({ queryKey: ['inspection', inspectionId] })
      }
    },
  })
}
