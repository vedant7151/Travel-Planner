import { Navigate } from 'react-router-dom'
import { useEffect, useState, type ReactNode } from 'react'
import { getUser, onAuthStateChange } from '../../services/session'

export function RequireAuth({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    let active = true
    getUser().then((user) => {
      if (active) setAuthenticated(Boolean(user))
    }).catch(() => {
      if (active) setAuthenticated(false)
    })
    const { data } = onAuthStateChange((session) => setAuthenticated(Boolean(session)))
    return () => {
      active = false
      data.subscription.unsubscribe()
    }
  }, [])

  if (authenticated === null) return null
  if (!authenticated) return <Navigate to="/login" replace />
  return children
}
