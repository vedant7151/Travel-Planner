import { useEffect, useRef, useState } from 'react'
import { getSession } from '../services/session'
import type { WsEvent } from '../services/api'
import { wsUrl } from '../services/api'

export function useTripWebSocket(tripId: string | undefined) {
  const [events, setEvents] = useState<WsEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!tripId) return
    let active = true
    let gotMessage = false
    let ws: WebSocket | null = null
    getSession().then((session) => {
      if (!active || !session) {
        if (active) setError('Your session has expired')
        return
      }
      ws = new WebSocket(wsUrl(tripId, session.access_token))
      socketRef.current = ws
      ws.onopen = () => {
        setConnected(true)
        setError(null)
      }
      ws.onmessage = (e) => {
        gotMessage = true
        try {
          setEvents((prev) => [...prev, JSON.parse(e.data) as WsEvent])
        } catch {
          setError('Could not parse agent update')
        }
      }
      ws.onclose = () => {
        setConnected(false)
        if (!gotMessage) {
          setError('WebSocket closed before any agent updates')
        }
      }
    }).catch(() => setError('Could not load your session'))
    return () => {
      active = false
      ws?.close()
    }
  }, [tripId])

  return { events, connected, error }
}
