import type { InputHTMLAttributes } from 'react'

export function NeonInput({
  label,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; id: string }) {
  return (
    <div>
      <label className="field-label" htmlFor={id} style={{ color: 'var(--text-secondary)' }}>
        {label}
      </label>
      <input id={id} className="auth-input" {...props} />
    </div>
  )
}
