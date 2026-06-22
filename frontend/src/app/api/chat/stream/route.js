export const dynamic = 'force-dynamic'
export const maxDuration = 300 // 5 min — allows long LLM streams

const BACKEND = process.env.API_URL || 'http://localhost:8000'

export async function POST(request) {
  let body
  try {
    body = await request.json()
  } catch {
    return new Response(
      `data: ${JSON.stringify({ type: 'error', message: 'Invalid request body' })}\n\n`,
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
    )
  }

  let res
  try {
    res = await fetch(`${BACKEND}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    })
  } catch (err) {
    return new Response(
      `data: ${JSON.stringify({ type: 'error', message: `Backend unreachable: ${err.message}` })}\n\n`,
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
    )
  }

  if (!res.ok || !res.body) {
    return new Response(
      `data: ${JSON.stringify({ type: 'error', message: `Backend error (${res.status})` })}\n\n`,
      { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
    )
  }

  return new Response(res.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'X-Accel-Buffering': 'no',
      'Connection': 'keep-alive',
    },
  })
}
