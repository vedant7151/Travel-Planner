import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AccommodationCards } from '../components/planning/AccommodationCards'
import { AgentStatusPanel } from '../components/planning/AgentStatusPanel'
import { ItineraryView } from '../components/planning/ItineraryView'
import { TransportOptions } from '../components/planning/TransportOptions'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'
import { Toast } from '../components/ui/Toast'
import { useAgentStream } from '../hooks/useAgentStream'
import { useTripWebSocket } from '../hooks/useTripWebSocket'
import { extractDays, extractIssues, extractNarrative } from '../lib/planContent'
import { api, type TripResponse } from '../services/api'

export function TripResult() {
  const { tripId } = useParams()
  const { events, error: wsError } = useTripWebSocket(tripId)
  const [trip, setTrip] = useState<TripResponse | null>(null)
  const stream = useAgentStream(events, trip)
  const [tab, setTab] = useState<'overview' | 'itinerary' | 'stay' | 'move'>('overview')

  useEffect(() => {
    if (!tripId) return
    api.get(tripId).then(setTrip).catch(() => undefined)
  }, [tripId, stream.done])

  const structured = stream.finalPlan?.structured ?? trip?.final_plan?.structured ?? null
  const itinerary = structured?.itinerary ?? trip?.itinerary
  const accommodation = structured?.accommodation ?? trip?.accommodation
  const transport = structured?.transport ?? trip?.transport
  const summary = typeof structured?.summary === 'string' ? structured.summary : null
  const planText = stream.finalPlan?.text ?? trip?.final_plan?.text ?? null
  const issues = extractIssues(stream.finalPlan ?? trip?.final_plan)
  const degradedSections = stream.degradedSections?.length
    ? stream.degradedSections
    : trip?.degraded_sections ?? []
  const planStatus = stream.planStatus ?? (trip?.status as 'completed' | 'partial' | 'failed' | undefined)
  const emptyPlan =
    !extractDays(itinerary).length &&
    !extractNarrative(itinerary, planText) &&
    issues.length > 0

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-8)' }}>
        <div>
          <h1 className="display" style={{ fontSize: 'var(--text-3xl)' }}>
            {trip?.request?.destination ?? 'Live plan'}
          </h1>
          <div className="mono">{tripId}</div>
        </div>
        <Badge
          tone={
            planStatus === 'failed' || emptyPlan
              ? 'error'
              : planStatus === 'partial'
                ? 'muted'
                : stream.done
                  ? 'success'
                  : 'neon'
          }
        >
          {planStatus === 'failed' || emptyPlan
            ? 'failed'
            : planStatus === 'partial'
              ? 'partial'
              : stream.done
                ? 'completed'
                : 'running'}
        </Badge>
      </div>
      {wsError ? <Toast tone="error" title="Stream error" message={wsError} /> : null}
      {stream.lastError ? <Toast tone="error" title="Planning error" message={stream.lastError} /> : null}
      {issues.length && !stream.lastError ? (
        <Toast tone="error" title="Planning error" message={issues[0]} />
      ) : null}
      {planStatus === 'partial' && degradedSections.length ? (
        <Toast
          tone="error"
          title="Partial plan"
          message={`Some sections are unavailable: ${degradedSections.join(', ')}.`}
        />
      ) : null}

      <div className="planning-tabs" style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['overview', 'itinerary', 'stay', 'move'] as const).map((id) => (
          <button
            key={id}
            type="button"
            className={`btn ${tab === id ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setTab(id)}
          >
            {id}
          </button>
        ))}
      </div>

      <motion.div
        className="planning-grid"
        variants={{ animate: { transition: { staggerChildren: 0.08 } } }}
        initial="initial"
        animate="animate"
      >
        <motion.div
          variants={{ initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 } }}
          style={{ display: tab === 'overview' ? 'block' : 'none' }}
        >
          <AgentStatusPanel status={stream.status} />
          {summary ? (
            <Card style={{ marginTop: 16 }}>
              <h2 className="heading" style={{ fontSize: 'var(--text-lg)' }}>
                Summary
              </h2>
              <p className="body" style={{ color: 'var(--text-secondary)' }}>
                {summary}
              </p>
            </Card>
          ) : null}
        </motion.div>
        <motion.div
          variants={{ initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 } }}
          style={{ display: tab === 'itinerary' || tab === 'overview' ? 'block' : 'none' }}
        >
          <ItineraryView
            itinerary={itinerary}
            fallbackText={planText}
            issues={issues}
            unavailable={degradedSections.includes('itinerary')}
          />
        </motion.div>
        <motion.div variants={{ initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 } }}>
          {(tab === 'stay' || tab === 'overview') && (
            <AccommodationCards
              options={accommodation}
              unavailable={degradedSections.includes('accommodation')}
            />
          )}
          <div style={{ height: 16 }} />
          {(tab === 'move' || tab === 'overview') && (
            <TransportOptions options={transport} unavailable={degradedSections.includes('transport')} />
          )}
        </motion.div>
      </motion.div>
    </div>
  )
}
