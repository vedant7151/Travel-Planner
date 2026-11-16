import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Toast } from '../components/ui/Toast'
import { api } from '../services/api'
import { getUser, type SessionUser } from '../services/session'

export function PlanTrip() {
  const navigate = useNavigate()
  const [user, setUser] = useState<SessionUser | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [form, setForm] = useState({
    origin: '',
    destination: '',
    start_date: '',
    end_date: '',
    budget_usd: '1500',
    travellers: '1',
  })

  useEffect(() => {
    getUser().then(setUser).catch(() => setUser(null))
  }, [])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    setPending(true)
    setError(null)
    try {
      const trip = await api.plan({
        user_id: user.id,
        origin: form.origin || null,
        destination: form.destination,
        start_date: form.start_date,
        end_date: form.end_date,
        budget_usd: Number(form.budget_usd),
        travellers: Number(form.travellers),
      })
      navigate(`/app/trips/${trip.trip_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create trip')
    } finally {
      setPending(false)
    }
  }

  return (
    <div>
      <h1 className="display" style={{ fontSize: 'var(--text-3xl)', marginBottom: 'var(--space-8)' }}>
        Plan a trip
      </h1>
      {error ? <Toast tone="error" title="Request failed" message={error} /> : null}
      <Card>
        <form onSubmit={onSubmit} style={{ display: 'grid', gap: 'var(--space-5)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
            <Input
              id="origin"
              label="Origin"
              value={form.origin}
              onChange={(e) => setForm({ ...form, origin: e.target.value })}
            />
            <Input
              id="destination"
              label="Destination"
              required
              value={form.destination}
              onChange={(e) => setForm({ ...form, destination: e.target.value })}
            />
            <Input
              id="start_date"
              label="Start date"
              type="date"
              required
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            />
            <Input
              id="end_date"
              label="End date"
              type="date"
              required
              value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            />
            <Input
              id="budget"
              label="Budget (USD)"
              type="number"
              min={0}
              required
              value={form.budget_usd}
              onChange={(e) => setForm({ ...form, budget_usd: e.target.value })}
            />
            <Input
              id="travellers"
              label="Travellers"
              type="number"
              min={1}
              max={20}
              required
              value={form.travellers}
              onChange={(e) => setForm({ ...form, travellers: e.target.value })}
            />
          </div>
          <Button type="submit" disabled={pending}>
            {pending ? 'Submitting…' : 'Plan my trip'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
