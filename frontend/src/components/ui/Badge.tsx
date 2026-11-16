import type { ReactNode } from 'react'

type Tone = 'neon' | 'success' | 'error' | 'muted'

export function Badge({
  tone = 'muted',
  children,
}: {
  tone?: Tone
  children: ReactNode
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}
