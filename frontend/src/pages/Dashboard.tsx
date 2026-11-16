import { Map } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { api, type TripResponse } from '../services/api'
import { getUser, type SessionUser } from '../services/session'

export function Dashboard() {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [trips, setTrips] = useState<TripResponse[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getUser().then(setUser).catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!user) return
    api.history(user.id).then(setTrips).catch((e: Error) => setError(e.message))
  }, [user?.id])

  return (
    <div>
      <h1 className="display" style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-4)' }}>
        Plans
      </h1>
      <p className="body" style={{ color: 'var(--text-secondary)', maxWidth: '42ch', marginBottom: 'var(--space-8)' }}>
        Recent trips stored for {user?.email}. Nothing here is invented — only what the agents saved.
      </p>
      <Link to="/app/plan">
        <Button>Plan a trip</Button>
      </Link>
      {error ? <p style={{ color: 'var(--agent-error)' }}>{error}</p> : null}
      <div style={{ display: 'grid', gap: 16, marginTop: 'var(--space-12)' }}>
        {trips.length === 0 ? (
          <Card>
            <Map size={40} />
            <p style={{ color: 'var(--text-muted)' }}>No trips yet. Start a plan to populate this list.</p>
          </Card>
        ) : (
          trips.map((trip) => (
            <Link key={trip.trip_id} to={`/app/trips/${trip.trip_id}`}>
              <Card neon>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <div>
                    <div className="heading">{trip.request?.destination ?? 'Trip'}</div>
                    <div className="mono">{trip.trip_id}</div>
                  </div>
                  <Badge tone={trip.status === 'completed' ? 'success' : trip.status === 'failed' ? 'error' : 'neon'}>
                    {trip.status}
                  </Badge>
                </div>
              </Card>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}
