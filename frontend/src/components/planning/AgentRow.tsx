import { motion } from 'framer-motion'
import type { AgentStatus } from '../../services/api'

const labels: Record<AgentStatus, string> = {
  pending: 'Waiting',
  running: 'Running',
  done: 'Complete',
  error: 'Error',
}

export function AgentRow({
  name,
  status,
}: {
  name: string
  status: AgentStatus
}) {
  return (
    <motion.div
      className={`agent-row ${status}`}
      variants={{
        initial: { opacity: 0, x: -4 },
        animate: { opacity: 1, x: 0, transition: { duration: 0.3, ease: 'easeOut' } },
      }}
      initial="initial"
      animate="animate"
    >
      <span className={`status-dot ${status}`} aria-hidden />
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <span className="heading" style={{ fontSize: 'var(--text-sm)' }}>
            {name}
          </span>
          <span className="badge badge-muted">{labels[status]}</span>
        </div>
        {status === 'running' ? (
          <div className="agent-progress-bar" aria-hidden>
            <div className="agent-progress-fill" />
          </div>
        ) : null}
      </div>
    </motion.div>
  )
}
