import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthLayout } from '../components/auth/AuthLayout'
import { NeonInput } from '../components/auth/NeonInput'
import { signUp } from '../services/session'

export function SignUp() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const { session } = await signUp(email.trim(), password, name.trim())
      if (session) {
        navigate('/app')
      } else {
        setError('Check your email to confirm your account, then sign in.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create account')
    }
  }

  return (
    <AuthLayout title="Start planning.">
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: '1.25rem', maxWidth: 360 }}>
        <NeonInput
          id="name"
          label="Name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <NeonInput
          id="email"
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <NeonInput
          id="password"
          label="Password"
          type="password"
          required
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
        />
        {error ? <p style={{ color: 'var(--agent-error)' }}>{error}</p> : null}
        <button type="submit" className="auth-btn-primary">
          Create account
        </button>
        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
          Already have a session?{' '}
          <Link to="/login" style={{ color: 'var(--neon)' }}>
            Sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  )
}
