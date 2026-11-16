import { useMemo } from 'react'
import type { AgentId, AgentStatus, TripResponse, WsEvent } from '../services/api'

export const AGENT_ORDER: { id: AgentId; label: string }[] = [
  { id: 'supervisor', label: 'Supervisor' },
  { id: 'destination', label: 'Destination research' },
  { id: 'itinerary', label: 'Itinerary planner' },
  { id: 'accommodation', label: 'Accommodation' },
  { id: 'transport', label: 'Transport' },
  { id: 'aggregator', label: 'Response aggregator' },
]

const NODE_MAP: Record<string, AgentId> = {
  supervisor: 'supervisor',
  destination: 'destination',
  itinerary: 'itinerary',
  accommodation: 'accommodation',
  transport: 'transport',
  aggregator: 'aggregator',
}

type PlanStatus = 'completed' | 'partial' | 'failed'

function applyPlanOutcome(
  status: Record<AgentId, AgentStatus>,
  finalPlan: WsEvent['final_plan'],
) {
  const issues = [
    ...(finalPlan?.source_errors ?? []),
    ...((finalPlan?.structured?.warnings as string[] | undefined) ?? []),
  ].filter((item) => typeof item === 'string' && item.trim())
  const degradedSections = finalPlan?.degraded_sections ?? []
  let lastError: string | null = issues.length ? issues[0] : null
  if (issues.length || degradedSections.length) {
    const prefixes: Array<[AgentId, string]> = [
      ['destination', 'destination'],
      ['itinerary', 'itinerary'],
      ['accommodation', 'accommodation'],
      ['transport', 'transport'],
      ['aggregator', 'aggregator'],
    ]
    for (const [id, prefix] of prefixes) {
      const flagged =
        degradedSections.includes(prefix) ||
        issues.some((msg) => msg.toLowerCase().startsWith(prefix))
      if (flagged) status[id] = 'error'
    }
  }
  ;(Object.keys(status) as AgentId[]).forEach((k) => {
    if (status[k] !== 'error') status[k] = 'done'
  })
  // Backend status (completed/partial/failed) is derived from explicit
  // degraded-section markers; only trust the "any issue => failed" heuristic
  // when older/cached plans don't carry that field yet.
  const planStatus: PlanStatus =
    finalPlan?.status ?? (issues.length || degradedSections.length ? 'partial' : 'completed')
  return { failed: planStatus === 'failed', lastError, issues, planStatus, degradedSections }
}

export function useAgentStream(events: WsEvent[], saved?: TripResponse | null) {
  return useMemo(() => {
    const status: Record<AgentId, AgentStatus> = {
      supervisor: 'pending',
      destination: 'pending',
      itinerary: 'pending',
      accommodation: 'pending',
      transport: 'pending',
      aggregator: 'pending',
    }
    let failed = false
    let done = false
    let finalPlan: WsEvent['final_plan'] = null
    let lastError: string | null = null
    let planStatus: PlanStatus | null = null
    let degradedSections: string[] = []

    for (const ev of events) {
      if (ev.event === 'status' && ev.status === 'running') {
        status.supervisor = 'running'
      }
      if (ev.event === 'node' && ev.node) {
        const id = NODE_MAP[ev.node]
        if (!id) continue
        for (const agent of AGENT_ORDER) {
          if (agent.id === id) break
          if (status[agent.id] === 'running' || status[agent.id] === 'pending') {
            status[agent.id] = 'done'
          }
        }
        status[id] = 'running'
      }
      if (ev.event === 'done') {
        done = true
        finalPlan = ev.final_plan ?? finalPlan
        const outcome = applyPlanOutcome(status, finalPlan)
        failed = outcome.failed
        lastError = outcome.lastError
        planStatus = outcome.planStatus
        degradedSections = outcome.degradedSections
      }
      if (ev.event === 'error') {
        failed = true
        planStatus = 'failed'
        lastError = ev.message ?? 'Planning failed'
        ;(Object.keys(status) as AgentId[]).forEach((k) => {
          if (status[k] === 'running') status[k] = 'error'
        })
      }
    }

    if (
      !events.length &&
      saved?.final_plan &&
      (saved.status === 'completed' || saved.status === 'partial' || saved.status === 'failed')
    ) {
      done = true
      finalPlan = saved.final_plan
      const outcome = applyPlanOutcome(status, saved.final_plan)
      planStatus = (saved.status as PlanStatus) ?? outcome.planStatus
      failed = planStatus === 'failed'
      degradedSections = saved.degraded_sections ?? outcome.degradedSections
      lastError = outcome.lastError ?? saved.error ?? lastError
    }

    return { status, failed, done, finalPlan, lastError, planStatus, degradedSections }
  }, [events, saved])
}
