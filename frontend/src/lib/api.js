// Stream goes directly to backend to avoid Next.js proxy buffering/timeout issues.
// Other calls use the Next.js proxy (/api/*) for CORS safety.
const DIRECT_BACKEND = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function* streamChat(content, sessionId) {
  const res = await fetch(`${DIRECT_BACKEND}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`Stream request failed (${res.status})`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try { yield JSON.parse(line.slice(6)) } catch { /* skip malformed */ }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function fetchIncidents() {
  const res = await fetch('/api/incidents')
  if (!res.ok) throw new Error(`Failed to fetch incidents (${res.status})`)
  return res.json()
}

export async function approveActions(requestId, approvedActionIds) {
  const res = await fetch('/api/actions/approve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_id: requestId, approved_action_ids: approvedActionIds }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `Approval failed (${res.status})`)
  }
  return res.json()
}

export async function declineActions(requestId) {
  const res = await fetch('/api/actions/decline', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_id: requestId }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `Decline failed (${res.status})`)
  }
  return res.json()
}
