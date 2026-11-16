import { supabase } from './session'

export type AgentStatus = 'pending' | 'running' | 'done' | 'error'

export type AgentId =
  | 'supervisor'
  | 'destination'
  | 'itinerary'
  | 'accommodation'
  | 'transport'
  | 'aggregator'

export interface TripRequest {
  user_id: string
  origin?: string | null
  destination: string
  start_date: string
  end_date: string
  budget_usd: number
  travellers: number
  preferences?: Record<string, unknown>
}

export interface TripResponse {
  trip_id: string
  status: string
  user_id?: string | null
  request?: TripRequest | null
  itinerary?: Record<string, unknown> | null
  accommodation?: unknown[] | null
  transport?: unknown[] | null
  final_plan?: {
    text?: string
    structured?: Record<string, unknown> | null
    source_errors?: string[]
    status?: 'completed' | 'partial' | 'failed'
    degraded_sections?: string[]
  } | null
  degraded_sections?: string[] | null
  error?: string | null
  created_at?: string | null
}

export interface WsEvent {
  event: string
  node?: string
  updated?: string[]
  status?: string
  message?: string
  final_plan?: TripResponse['final_plan']
}

const jsonHeaders = { 'Content-Type': 'application/json' }

async function authFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const { data, error } = await supabase.auth.getSession()
  if (error) throw error
  const headers = new Headers(init.headers)
  if (data.session?.access_token) {
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }
  return fetch(input, { ...init, headers })
}

async function parse<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (body as { detail?: unknown }).detail
    throw new Error(typeof detail === 'string' ? detail : res.statusText)
  }
  return body as T
}

export const api = {
  plan: (payload: TripRequest) =>
    authFetch('/api/v1/trips/plan', {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify(payload),
    }).then((r) => parse<TripResponse>(r)),

  get: (tripId: string) =>
    authFetch(`/api/v1/trips/${tripId}`).then((r) => parse<TripResponse>(r)),

  history: (userId: string) =>
    authFetch(`/api/v1/trips/history?user_id=${encodeURIComponent(userId)}`).then((r) =>
      parse<TripResponse[]>(r),
    ),

  events: (tripId: string) =>
    authFetch(`/api/v1/trips/${tripId}/events`).then((r) =>
      parse<{ trip_id: string; events: unknown[] }>(r),
    ),
}

export function wsUrl(tripId: string, accessToken: string) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/plan/${tripId}?access_token=${encodeURIComponent(accessToken)}`
}
