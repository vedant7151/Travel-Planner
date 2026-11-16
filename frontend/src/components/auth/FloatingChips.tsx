import { motion } from 'framer-motion'

const chips = [
  { label: 'Supervisor Agent', icon: '🧠', delay: 0, top: '18%', left: '12%' },
  { label: 'Itinerary Planner', icon: '🗓️', delay: 1.2, top: '38%', left: '28%' },
  { label: 'Flight Search', icon: '✈️', delay: 2.4, top: '58%', left: '16%' },
  { label: 'Accommodation Agent', icon: '🏨', delay: 0.8, top: '28%', left: '48%' },
  { label: 'Response Aggregator', icon: '📋', delay: 1.8, top: '68%', left: '40%' },
]

export function FloatingChips() {
  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      {chips.map((chip) => (
        <motion.div
          key={chip.label}
          className="agent-chip"
          style={{ position: 'absolute', top: chip.top, left: chip.left }}
          animate={{ y: [0, -12, 0], opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: chip.delay }}
        >
          <span>{chip.icon}</span>
          {chip.label}
        </motion.div>
      ))}
    </div>
  )
}
