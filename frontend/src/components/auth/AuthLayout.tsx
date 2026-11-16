import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ThemeToggle } from '../ui/ThemeToggle'
import { FloatingChips } from './FloatingChips'

export function AuthLayout({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="auth-split" style={{ display: 'grid', gridTemplateColumns: '55% 45%', minHeight: '100vh' }}>
      <section className="auth-bg auth-left" style={{ minHeight: '100vh', position: 'relative', padding: '3rem' }}>
        <div className="logo" style={{ position: 'relative', zIndex: 1 }}>
          <span className="logo-dot" />
          Travel Planner
        </div>
        <h1
          className="display"
          style={{
            position: 'relative',
            zIndex: 1,
            fontSize: 'var(--text-hero)',
            maxWidth: '12ch',
            marginTop: '18vh',
            color: 'var(--text-primary)',
          }}
        >
          {title}
        </h1>
        <p
          className="body"
          style={{
            position: 'relative',
            zIndex: 1,
            color: 'var(--text-secondary)',
            maxWidth: '36ch',
            marginTop: '1rem',
          }}
        >
          A precise multi-agent planner. Live research, no brochure filler.
        </p>
        <FloatingChips />
      </section>
      <aside className="auth-form-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2.5rem' }}>
          <Link to="/" className="logo">
            <span className="logo-dot" />
            Travel Planner
          </Link>
          <ThemeToggle />
        </div>
        {children}
      </aside>
    </div>
  )
}
