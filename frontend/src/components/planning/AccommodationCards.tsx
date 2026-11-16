import { ExternalLink } from 'lucide-react'
import { extractListings } from '../../lib/planContent'
import { Card } from '../ui/Card'

export function AccommodationCards({
  options,
  unavailable,
}: {
  options: unknown
  unavailable?: boolean
}) {
  const rows = extractListings(options)
  return (
    <Card>
      <h2 className="heading" style={{ fontSize: 'var(--text-lg)', marginBottom: '1rem' }}>
        Accommodation
      </h2>
      {unavailable ? (
        <p style={{ color: 'var(--text-error, #e5484d)', marginBottom: rows.length ? 12 : 0 }}>
          Accommodation data unavailable for this trip.
        </p>
      ) : null}
      {rows.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>No live hotel snippets yet.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {rows.map((row, i) => (
            <article key={i} style={{ borderTop: i ? '1px solid var(--border)' : undefined, paddingTop: i ? 12 : 0 }}>
              <div className="heading" style={{ fontSize: 'var(--text-sm)' }}>
                {row.failed || row.error ? 'Could not load hotels' : String(row.title ?? 'Listing')}
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', margin: '6px 0' }}>
                {String(row.error ?? row.snippet ?? row.text ?? '')}
              </p>
              {typeof row.href === 'string' ? (
                <a href={row.href} target="_blank" rel="noreferrer" className="btn btn-ghost" style={{ padding: 0 }}>
                  Source <ExternalLink size={14} />
                </a>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </Card>
  )
}
