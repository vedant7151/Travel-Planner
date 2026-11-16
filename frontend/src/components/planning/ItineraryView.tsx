import { useState } from 'react'
import { extractDays, extractNarrative, type DayPlan } from '../../lib/planContent'
import { Card } from '../ui/Card'

function DayBody({ day }: { day: DayPlan }) {
  return (
    <div className="body" style={{ color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
      {day.morning ? (
        <p>
          <span className="heading" style={{ fontSize: 'var(--text-sm)' }}>
            Morning
          </span>{' '}
          — {day.morning}
        </p>
      ) : null}
      {day.afternoon ? (
        <p>
          <span className="heading" style={{ fontSize: 'var(--text-sm)' }}>
            Afternoon
          </span>{' '}
          — {day.afternoon}
        </p>
      ) : null}
      {day.evening ? (
        <p>
          <span className="heading" style={{ fontSize: 'var(--text-sm)' }}>
            Evening
          </span>{' '}
          — {day.evening}
        </p>
      ) : null}
      {day.notes ? <p>{day.notes}</p> : null}
      {day.body ? <p>{day.body}</p> : null}
    </div>
  )
}

export function ItineraryView({
  itinerary,
  fallbackText,
  issues,
  unavailable,
}: {
  itinerary: unknown
  fallbackText?: string | null
  issues?: string[]
  unavailable?: boolean
}) {
  const days = extractDays(itinerary)
  const narrative = extractNarrative(itinerary, fallbackText)
  const [active, setActive] = useState(0)
  const problem = issues?.find(Boolean)
  const unavailableNotice = unavailable ? (
    <p style={{ color: 'var(--text-error, #e5484d)', marginBottom: 12 }}>
      Itinerary data unavailable for this trip.
    </p>
  ) : null

  if (days.length) {
    const day = days[Math.min(active, days.length - 1)]
    return (
      <Card>
        <h2 className="heading" style={{ fontSize: 'var(--text-lg)', marginBottom: '1rem' }}>
          Itinerary
        </h2>
        {unavailableNotice}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1rem' }}>
          {days.map((item, i) => (
            <button
              key={item.label + i}
              type="button"
              className={`btn ${i === active ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActive(i)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <DayBody day={day} />
      </Card>
    )
  }

  if (narrative || problem) {
    return (
      <Card>
        <h2 className="heading" style={{ fontSize: 'var(--text-lg)', marginBottom: '1rem' }}>
          Itinerary
        </h2>
        {unavailableNotice}
        <p className="body" style={{ color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
          {narrative ?? problem}
        </p>
      </Card>
    )
  }

  return (
    <Card>
      <h2 className="heading" style={{ fontSize: 'var(--text-lg)' }}>
        Itinerary
      </h2>
      {unavailableNotice}
      <p style={{ color: 'var(--text-muted)' }}>No itinerary in the saved plan yet.</p>
    </Card>
  )
}
