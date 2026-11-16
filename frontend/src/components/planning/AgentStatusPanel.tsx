import type { AgentStatus } from '../../services/api'
import { AGENT_ORDER } from '../../hooks/useAgentStream'
import { AgentRow } from './AgentRow'

export function AgentStatusPanel({
  status,
}: {
  status: Record<string, AgentStatus>
}) {
  return (
    <section>
      <h2 className="heading" style={{ fontSize: 'var(--text-lg)', marginBottom: '1rem' }}>
        Agents
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {AGENT_ORDER.map((agent) => (
          <AgentRow key={agent.id} name={agent.label} status={status[agent.id] ?? 'pending'} />
        ))}
      </div>
    </section>
  )
}
