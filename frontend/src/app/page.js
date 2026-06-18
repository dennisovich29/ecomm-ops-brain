'use client'

import { useEffect } from 'react'
import Sidebar from '@/components/Sidebar'
import ChatArea from '@/components/ChatArea'
import useStore from '@/lib/store'
import { fetchIncidents } from '@/lib/api'

export default function HomePage() {
  const newChat = useStore((s) => s.newChat)
  const activeSessionId = useStore((s) => s.activeSessionId)
  const setIncidents = useStore((s) => s.setIncidents)

  useEffect(() => {
    if (!activeSessionId) newChat()

    fetchIncidents()
      .then((d) => setIncidents(d.incidents || []))
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: '#1a1b1d' }}>
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 relative overflow-hidden">
        <ChatArea />
      </main>
    </div>
  )
}
