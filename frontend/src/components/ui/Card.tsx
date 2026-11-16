import type { HTMLAttributes, ReactNode } from 'react'

export function Card({
  neon,
  children,
  className = '',
  ...props
}: HTMLAttributes<HTMLDivElement> & { neon?: boolean; children: ReactNode }) {
  return (
    <div className={`card ${neon ? 'card--neon' : ''} ${className}`} {...props}>
      {children}
    </div>
  )
}
