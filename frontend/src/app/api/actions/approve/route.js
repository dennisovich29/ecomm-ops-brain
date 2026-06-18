import { NextResponse } from 'next/server'

const BACKEND = process.env.API_URL || 'http://localhost:8000'

export async function POST(request) {
  try {
    const body = await request.json()
    const res = await fetch(`${BACKEND}/actions/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (err) {
    return NextResponse.json(
      { error: err.message || 'Backend unreachable' },
      { status: 502 }
    )
  }
}
