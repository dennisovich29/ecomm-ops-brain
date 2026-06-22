'use client'

import { useCallback } from 'react'
import useStore from '@/lib/store'
import { streamChat } from '@/lib/api'

export function useChat() {
  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return

    const {
      activeSessionId,
      setActiveSession,
      addSession,
      sessions,
      addMessage,
      updateMessage,
      setLoading,
    } = useStore.getState()

    // Capture the session at send-time. All callbacks below always write to
    // THIS session, even if the user switches to a different chat mid-stream.
    let sessionId = activeSessionId
    if (!sessionId) {
      sessionId = crypto.randomUUID()
      setActiveSession(sessionId)
    }

    if (!sessions.find((s) => s.id === sessionId)) {
      addSession({ id: sessionId, title: text.slice(0, 60), createdAt: new Date().toISOString() })
    }

    addMessage(sessionId, { id: crypto.randomUUID(), role: 'user', content: text, timestamp: new Date().toISOString() })
    setLoading(sessionId, true)

    const streamMsgId = crypto.randomUUID()
    let tokenBuffer = ''
    let streamStarted = false

    try {
      for await (const event of streamChat(text, sessionId)) {
        if (!streamStarted) {
          streamStarted = true
          addMessage(sessionId, { id: streamMsgId, role: 'streaming', content: '', timestamp: new Date().toISOString() })
          setLoading(sessionId, false)
        }

        if (event.type === 'token') {
          tokenBuffer += event.content
          updateMessage(sessionId, streamMsgId, { content: tokenBuffer })
        } else if (event.type === 'final_response') {
          const isApproval = event.response?.type === 'approval_pending'
          updateMessage(sessionId, streamMsgId, {
            role: isApproval ? 'approval' : 'assistant',
            content: event.response,
          })
        } else if (event.type === 'error') {
          updateMessage(sessionId, streamMsgId, { role: 'error', content: event.message })
        }
      }
    } catch (err) {
      console.error('[useChat] stream error:', err)
      const msg = err.message || 'Something went wrong. Please try again.'
      if (streamStarted) {
        updateMessage(sessionId, streamMsgId, { role: 'error', content: msg })
      } else {
        addMessage(sessionId, { id: streamMsgId, role: 'error', content: msg, timestamp: new Date().toISOString() })
      }
    } finally {
      setLoading(sessionId, false)
    }
  }, []) // stable — reads latest state via getState()

  return { sendMessage }
}
