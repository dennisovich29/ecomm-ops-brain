'use client'

import { useEffect, useRef } from 'react'
import useStore from '@/lib/store'
import MessageBubble from './MessageBubble'
import InputBar from './InputBar'
import LoadingDots from './LoadingDots'
import { useChat } from '@/hooks/useChat'

const CHIPS = [
  { label: 'Diagnose',   text: 'Why did sales drop yesterday?' },
  { label: 'Inventory',  text: "What's the current inventory status?" },
  { label: 'Summary',    text: "Summarize yesterday's operations" },
  { label: 'Marketing',  text: 'Any marketing campaigns underperforming?' },
  { label: 'Support',    text: 'Show me recent support ticket trends' },
  { label: 'Actions',    text: 'What actions should I take today?' },
]

export default function ChatArea() {
  const messages = useStore((s) => s.messagesBySession[s.activeSessionId]) ?? []
  const isLoading = useStore((s) => s.loadingBySession[s.activeSessionId]) ?? false
  const { sendMessage } = useChat()
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    <div className="flex flex-col h-full" style={{ background: '#1a1b1d' }}>
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          /* ── Empty state ──────────────────────────────────────────────────── */
          <div className="flex flex-col items-center justify-center h-full px-6 gap-10 animate-fade-in">
            <div className="flex flex-col items-center gap-3 text-center">
              <h1 className="text-[32px] font-light tracking-tight text-[#e4e4e4]">
                Hello, Operator
              </h1>
              <p className="text-base text-[#7a7d80] max-w-sm leading-relaxed">
                Ask about sales, inventory, support, or marketing — or request a full operations diagnosis.
              </p>
            </div>

            <div
              className="grid gap-3 w-full"
              style={{ maxWidth: 680, gridTemplateColumns: '1fr 1fr' }}
            >
              {CHIPS.map((chip) => (
                <button
                  key={chip.text}
                  onClick={() => sendMessage(chip.text)}
                  className="flex flex-col gap-1.5 px-5 py-4 rounded-2xl text-left transition-colors"
                  style={{ background: '#222426', border: '1px solid #2e3032' }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = '#28292c'
                    e.currentTarget.style.borderColor = '#3a3c3e'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = '#222426'
                    e.currentTarget.style.borderColor = '#2e3032'
                  }}
                >
                  <span className="text-[11px] font-semibold uppercase tracking-widest text-[#4f80f0]">
                    {chip.label}
                  </span>
                  <span className="text-sm text-[#9a9da0] leading-snug">{chip.text}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* ── Message thread ───────────────────────────────────────────────── */
          <div
            className="mx-auto w-full px-6 py-8"
            style={{ maxWidth: 720, display: 'flex', flexDirection: 'column', gap: '2rem' }}
          >
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {isLoading && !messages.some((m) => m.role === 'streaming') && (
              <div className="flex items-start gap-4">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: '#252628', marginTop: 2 }}
                >
                  <span style={{ color: '#8a8d90', fontSize: 10, fontWeight: 700 }}>OB</span>
                </div>
                <div style={{ paddingTop: 8 }}>
                  <LoadingDots />
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <InputBar />
    </div>
  )
}
