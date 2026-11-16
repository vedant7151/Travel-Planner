import { History, Map, Plus } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { Navbar } from './Navbar'
import { Sidebar } from './Sidebar'

export function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <Navbar />
      <main className="main-content">
        <div className="content-container">
          <Outlet />
        </div>
      </main>
      <nav className="bottom-nav">
        <NavLink to="/app" end className="nav-link">
          <Map size={18} />
        </NavLink>
        <NavLink to="/app/plan" className="nav-link">
          <Plus size={18} />
        </NavLink>
        <NavLink to="/app/history" className="nav-link">
          <History size={18} />
        </NavLink>
      </nav>
    </div>
  )
}
