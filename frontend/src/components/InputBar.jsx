'use client'

import { useState, useRef, useCallback } from 'react'
import useStore from '@/lib/store'
import { useChat } from '@/hooks/useChat'

function IconSend() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

export default function InputBar() {
  const [text, setText] = useState('')
  const isLoading       = useStore((s) => s.loadingBySession[s.activeSessionId]) ?? false
  const { sendMessage } = useChat()
  const textareaRef     = useRef(null)

  const handleSend = useCallback(async () => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return
    setText('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    await sendMessage(trimmed)
  }, [text, isLoading, sendMessage])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e) => {
    const ta = e.target
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 180) + 'px'
    setText(ta.value)
  }

  const canSend = !!text.trim() && !isLoading

  return (
    <div className="px-6 pb-6 pt-3" style={{ background: '#1a1b1d' }}>
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <div
          className="flex items-end gap-3 rounded-2xl px-5 py-3.5 transition-colors"
          style={{ background: '#222426', border: '1px solid #2e3032' }}
          onFocusCapture={(e) => (e.currentTarget.style.borderColor = '#3e4144')}
          onBlurCapture={(e)  => (e.currentTarget.style.borderColor = '#2e3032')}
        >
          <textarea
            ref={textareaRef}
            value={text}
            onInput={handleInput}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your operations…"
            rows={1}
            disabled={isLoading}
            className="flex-1 bg-transparent resize-none outline-none text-sm text-[#e4e4e4] leading-relaxed placeholder:text-[#4a4d50]"
            style={{ maxHeight: 180, overflowY: 'auto', padding: '2px 0', caretColor: '#4f80f0' }}
          />
          <button
            onClick={handleSend}
            disabled={!canSend}
            className="w-9 h-9 flex items-center justify-center rounded-xl flex-shrink-0 transition-all"
            style={{
              background: canSend ? '#4f80f0' : '#252628',
              color:      canSend ? '#fff'     : '#4a4d50',
              cursor:     canSend ? 'pointer'  : 'not-allowed',
            }}
            aria-label="Send message"
          >
            <IconSend />
          </button>
        </div>
        <p className="text-center text-xs text-[#3e4144] mt-2.5">
          Ops Brain may make mistakes — always verify critical decisions.
        </p>
      </div>
    </div>
  )
}

