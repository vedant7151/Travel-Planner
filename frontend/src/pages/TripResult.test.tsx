import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { TripResponse } from '../services/api'

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useParams: () => ({ tripId: 'trip-123' }) }
})

vi.mock('../hooks/useTripWebSocket', () => ({
  useTripWebSocket: () => ({ events: [], connected: false, error: null }),
}))

const getMock = vi.fn()
vi.mock('../services/api', () => ({
  api: { get: (...args: unknown[]) => getMock(...args) },
  wsUrl: () => 'ws://example.test',
}))

// TripResult imports TripResult.test's helpers transitively; import after mocks are set.
import { TripResult } from './TripResult'

function partialTrip(): TripResponse {
  return {
    trip_id: 'trip-123',
    status: 'partial',
    request: { user_id: 'u1', destination: 'New York, NY', start_date: '2026-10-10', end_date: '2026-10-12', budget_usd: 1500, travellers: 2 },
    degraded_sections: ['transport'],
    final_plan: {
      text: null,
      source_errors: ['transport: transport failed: 429 rate_limit_exceeded'],
      status: 'partial',
      degraded_sections: ['transport'],
      structured: {
        summary: 'A 3-day New York trip, mostly on track.',
        itinerary: { days: [{ day: 1, morning: 'Central Park' }] },
        accommodation: [{ title: 'Hotel A', snippet: '$130/night' }],
        transport: [],
        budget_notes: 'Within budget.',
        tips: ['Pack layers'],
        warnings: ['transport failed: 429 rate_limit_exceeded'],
      },
    },
  }
}

describe('TripResult', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('renders a partial-status plan with a degraded-section notice instead of a silent empty section', async () => {
    getMock.mockResolvedValue(partialTrip())

    render(<TripResult />)

    expect(await screen.findByText('partial')).toBeInTheDocument()
    expect(await screen.findByText(/A 3-day New York trip, mostly on track\./)).toBeInTheDocument()
    expect(await screen.findByText(/some sections are unavailable: transport/i)).toBeInTheDocument()
    expect(
      await screen.findByText('Transport data unavailable for this trip.'),
    ).toBeInTheDocument()
  })

  it('renders a completed plan without any degraded-section notice', async () => {
    const trip = partialTrip()
    trip.status = 'completed'
    trip.degraded_sections = []
    trip.final_plan!.status = 'completed'
    trip.final_plan!.degraded_sections = []
    trip.final_plan!.structured!.transport = [{ title: 'Flight A' }]
    getMock.mockResolvedValue(trip)

    render(<TripResult />)

    expect(await screen.findByText('completed')).toBeInTheDocument()
    expect(
      screen.queryByText('Transport data unavailable for this trip.'),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/some sections are unavailable/i)).not.toBeInTheDocument()
  })
})
