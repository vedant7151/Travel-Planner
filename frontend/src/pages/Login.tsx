import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthLayout } from '../components/auth/AuthLayout'
import { NeonInput } from '../components/auth/NeonInput'
import { signIn } from '../services/session'

export function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await signIn(email.trim(), password)
      navigate('/app')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in')
    }
  }

  return (
    <AuthLayout title="Sign in to the planner.">
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: '1.25rem', maxWidth: 360 }}>
        <NeonInput
          id="email"
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        <NeonInput
          id="password"
          label="Password"
          type="password"
          required
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error ? <p style={{ color: 'var(--agent-error)' }}>{error}</p> : null}
        <button type="submit" className="auth-btn-primary">
          Continue
        </button>
        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
          Sign in with your Supabase account.{' '}
          <Link to="/signup" style={{ color: 'var(--neon)' }}>
            Create a session
          </Link>
        </p>
      </form>
    </AuthLayout>
  )
}
