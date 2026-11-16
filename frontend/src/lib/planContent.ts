export type DayPlan = {
  label: string
  morning?: string
  afternoon?: string
  evening?: string
  notes?: string
  body?: string
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function stringify(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function field(rec: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const match = Object.keys(rec).find((k) => k.toLowerCase() === key.toLowerCase())
    if (!match) continue
    const val = rec[match]
    if (val == null || val === '') continue
    return stringify(val)
  }
  return undefined
}

function looksLikeDay(value: unknown): value is Record<string, unknown> {
  const rec = asRecord(value)
  if (!rec) return false
  return Boolean(
    field(rec, 'morning', 'afternoon', 'evening', 'notes', 'activities', 'plan', 'title', 'day'),
  )
}

function toDay(value: unknown, index: number): DayPlan {
  if (typeof value === 'string') {
    return { label: `Day ${index + 1}`, body: value }
  }
  const rec = asRecord(value) ?? {}
  const label =
    field(rec, 'label', 'title', 'day', 'name') ?? `Day ${index + 1}`
  const body = field(rec, 'activities', 'plan', 'content', 'description', 'text', 'body')
  return {
    label: String(label),
    morning: field(rec, 'morning'),
    afternoon: field(rec, 'afternoon'),
    evening: field(rec, 'evening'),
    notes: field(rec, 'notes'),
    body,
  }
}

export function extractDays(itinerary: unknown): DayPlan[] {
  if (!itinerary) return []
  if (Array.isArray(itinerary)) {
    return itinerary.map((item, i) => toDay(item, i))
  }
  if (typeof itinerary === 'string') {
    return itinerary.trim() ? [{ label: 'Plan', body: itinerary }] : []
  }
  const rec = asRecord(itinerary)
  if (!rec) return []

  const nestedKeys = ['days', 'day_by_day', 'schedule', 'itinerary', 'plan']
  for (const key of nestedKeys) {
    const nested = rec[key]
    if (Array.isArray(nested) && nested.length) return extractDays(nested)
    if (typeof nested === 'string' && nested.trim()) return extractDays(nested)
    if (asRecord(nested) && key !== 'itinerary') {
      const inner = extractDays(nested)
      if (inner.length) return inner
    }
  }

  const numbered = Object.entries(rec).filter(([k]) => /^day\s*\d+/i.test(k) || /^d\d+$/i.test(k))
  if (numbered.length) {
    return numbered.map(([, v], i) => toDay(v, i))
  }

  if (looksLikeDay(rec) && !Array.isArray(rec.days)) {
    return [toDay(rec, 0)]
  }
  return []
}

export function extractNarrative(itinerary: unknown, finalText?: string | null): string | null {
  if (typeof itinerary === 'string' && itinerary.trim()) return itinerary
  const rec = asRecord(itinerary)
  if (rec) {
    const text = field(rec, 'text', 'raw_text', 'value', 'summary', 'narrative', 'error')
    if (text) return text
  }
  if (finalText && finalText.trim()) return finalText
  return null
}

export function extractIssues(
  plan:
    | {
        structured?: Record<string, unknown> | null
        source_errors?: string[]
      }
    | null
    | undefined,
): string[] {
  const out: string[] = []
  if (Array.isArray(plan?.source_errors)) {
    for (const item of plan.source_errors) {
      if (typeof item === 'string' && item.trim()) out.push(item)
    }
  }
  const warnings = plan?.structured?.warnings
  if (Array.isArray(warnings)) {
    for (const item of warnings) {
      if (typeof item === 'string' && item.trim()) out.push(item)
    }
  }
  return [...new Set(out)]
}

export function extractListings(value: unknown): Array<Record<string, unknown>> {
  if (!value) return []
  if (Array.isArray(value)) {
    return value.filter((item) => item && typeof item === 'object') as Array<Record<string, unknown>>
  }
  const rec = asRecord(value)
  if (!rec) return []
  for (const key of ['options', 'results', 'items', 'hotels', 'listings', 'accommodation', 'transport']) {
    if (Array.isArray(rec[key])) return extractListings(rec[key])
  }
  return [rec]
}
