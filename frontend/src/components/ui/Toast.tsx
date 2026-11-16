import { AlertCircle, CheckCircle2, Info } from 'lucide-react'

export function Toast({
  tone = 'info',
  title,
  message,
}: {
  tone?: 'success' | 'error' | 'info'
  title: string
  message?: string
}) {
  const Icon = tone === 'success' ? CheckCircle2 : tone === 'error' ? AlertCircle : Info
  return (
    <div className={`toast toast-${tone}`} role="status">
      <Icon size={16} />
      <div>
        <div className="heading" style={{ fontSize: 'var(--text-sm)' }}>
          {title}
        </div>
        {message ? (
          <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
            {message}
          </p>
        ) : null}
      </div>
    </div>
  )
}
