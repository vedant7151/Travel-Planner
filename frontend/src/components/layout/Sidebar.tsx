import { History, LogOut, Map, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { clearUser, getUser, onAuthStateChange, type SessionUser } from '../../services/session'

export function Sidebar() {
  const [user, setUser] = useState<SessionUser | null>(null)

  useEffect(() => {
    getUser().then(setUser).catch(() => setUser(null))
    const { data } = onAuthStateChange((session) => setUser(session?.user ?? null))
    return () => data.subscription.unsubscribe()
  }, [])
  return (
    <aside className="sidebar">
      <LinkMark />
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: '2rem' }}>
        <NavLink to="/app/plan" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Plus size={18} />
          <span className="nav-label">Plan new</span>
        </NavLink>
        <NavLink to="/app" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Map size={18} />
          <span className="nav-label">Dashboard</span>
        </NavLink>
        <NavLink to="/app/history" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <History size={18} />
          <span className="nav-label">History</span>
        </NavLink>
      </nav>
      <div style={{ marginTop: 'auto' }}>
        <div className="user-meta" style={{ padding: '0.75rem', color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
          {user?.name}
          <div className="mono">{user?.email}</div>
        </div>
        <NavLink
          to="/login"
          className="nav-link"
          onClick={() => {
            void clearUser()
          }}
        >
          <LogOut size={18} />
          <span className="nav-label">Sign out</span>
        </NavLink>
      </div>
    </aside>
  )
}

function LinkMark() {
  return (
    <div className="logo">
      <span className="logo-dot" />
      <span className="nav-label">Travel Planner</span>
    </div>
  )
}
