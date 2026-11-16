import { Link } from 'react-router-dom'
import { ThemeToggle } from '../ui/ThemeToggle'

export function Navbar() {
  return (
    <header className="navbar">
      <Link to="/app" className="logo">
        <span className="logo-dot" />
        Travel Planner
      </Link>
      <ThemeToggle />
    </header>
  )
}
