'use client'

import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { approveActions, declineActions } from '@/lib/api'

const MD_COMPONENTS = {
  // Wrap every table in a horizontally-scrollable container
  table: ({ node, ...props }) => (
    <div style={{ overflowX: 'auto', marginBottom: '0.75rem' }}>
      <table {...props} />
    </div>
  ),
}

function MarkdownText({ text }) {
  // Guard: react-markdown crashes if text is not a non-empty string
  if (typeof text !== 'string' || !text) return null
  return (
    <div className="md-content text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>{text}</ReactMarkdown>
    </div>
  )
}

function SectionBlock({ label, labelColor, children }) {
  return (
    <div className="pl-4" style={{ borderLeft: `2px solid ${labelColor}` }}>
      <p
        className="text-[11px] font-semibold uppercase tracking-widest mb-2"
        style={{ color: labelColor }}
      >
        {label}
      </p>
      {children}
    </div>
  )
}

function AssistantResponse({ content }) {
  // Plain string — most common case
  if (typeof content === 'string') {
    return <MarkdownText text={content} />
  }

  // If content is not an object (null, number, array, etc.) render nothing
  if (!content || typeof content !== 'object' || Array.isArray(content)) {
    return null
  }

  const {
    summary,
    message,
    root_cause_analysis,
    recommendations,
    proposed_actions,
    domains_investigated,
    confidence_score,
  } = content

  const mainText = summary || message

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {mainText && <MarkdownText text={mainText} />}

      {Array.isArray(recommendations) && recommendations.length > 0 && (
        <SectionBlock label="Recommendations" labelColor="#3d9e6a">
          <ul className="flex flex-col gap-2">
            {recommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-[#c8cacb]">
                <span className="text-[#3d9e6a] mt-0.5 flex-shrink-0">–</span>
                <span>{typeof rec === 'string' ? rec : rec.description || JSON.stringify(rec)}</span>
              </li>
            ))}
          </ul>
        </SectionBlock>
      )}

      {Array.isArray(proposed_actions) && proposed_actions.length > 0 && (
        <SectionBlock label="Proposed Actions" labelColor="#6b6e72">
          <ul className="flex flex-col gap-2">
            {proposed_actions.map((action, i) => {
              const label =
                typeof action === 'string'
                  ? action
                  : action.description || action.action_type || `Action ${i + 1}`
              return (
                <li key={i} className="flex items-start gap-2 text-sm text-[#c8cacb]">
                  <span className="text-[#505356] mt-0.5 flex-shrink-0">→</span>
                  <span>{label}</span>
                </li>
              )
            })}
          </ul>
        </SectionBlock>
      )}


      {(Array.isArray(domains_investigated) && domains_investigated.length > 0 || (confidence_score !== undefined && confidence_score !== null)) && (
        <div className="flex items-center gap-2 flex-wrap pt-1">
          {Array.isArray(domains_investigated) && domains_investigated.length > 0 && (
            <>
              <span className="text-xs text-[#4a4d50]">Analyzed:</span>
              {domains_investigated.map((d) => (
                <span
                  key={d}
                  className="text-xs px-2.5 py-1 rounded-full"
                  style={{ background: '#222426', color: '#7a7d80', border: '1px solid #2e3032' }}
                >
                  {d}
                </span>
              ))}
            </>
          )}
          {confidence_score !== undefined && confidence_score !== null && (
            <span className="text-xs text-[#4a4d50]">
              {Math.round(Number(confidence_score) * 100)}% confidence
            </span>
          )}
        </div>
      )}
    </div>
  )
}

// ── Inline HITL approval card ─────────────────────────────────────────────────

const APPROVAL_TIMEOUT_MS = 10 * 60 * 1000 // 10 minutes

function ActionCheckbox({ checked }) {
  return (
    <div
      style={{
        width: 16, height: 16, flexShrink: 0, marginTop: 2,
        border: `1.5px solid ${checked ? '#3d9e6a' : '#3e4144'}`,
        background: checked ? '#3d9e6a' : 'transparent',
        borderRadius: 4,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        transition: 'all 0.15s',
      }}
    >
      {checked && (
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )}
    </div>
  )
}

function InlineApprovalCard({ message }) {
  const content    = typeof message.content === 'object' ? message.content : {}
  const actions    = content.proposed_actions || []
  const workflowId = content.workflow_id

  const [selected,      setSelected]      = useState(new Set())
  const [submitting,    setSubmitting]    = useState(false)
  const [status,        setStatus]        = useState('pending') // pending | approved | declined | expired
  const [approvedCount, setApprovedCount] = useState(0)
  const [results,       setResults]       = useState([])

  // Auto-expire after timeout
  useEffect(() => {
    const timer = setTimeout(() => setStatus((s) => s === 'pending' ? 'expired' : s), APPROVAL_TIMEOUT_MS)
    return () => clearTimeout(timer)
  }, [])

  const getId = (a, i) => a.action_id || a.id || String(i)

  const toggle = (id) =>
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const handleApprove = async () => {
    if (selected.size === 0 || !workflowId) return
    setSubmitting(true)
    try {
      const data = await approveActions(workflowId, [...selected])
      setApprovedCount(selected.size)
      setResults(data.results || [])
      setStatus('approved')
    } catch {
      // keep pending state on error so user can retry
    } finally {
      setSubmitting(false)
    }
  }

  const handleDecline = async () => {
    if (workflowId) {
      try { await declineActions(workflowId) } catch { /* fire-and-forget */ }
    }
    setStatus('declined')
  }

  // ── Resolved states ───────────────────────────────────────────────────────
  if (status !== 'pending') {
    const cfgMap = {
      declined: { text: 'Request declined — no actions taken', color: '#9a9da0', bg: '#1e1f21', border: '#2a2c2e',
        icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg> },
      expired:  { text: 'Request expired — no actions taken', color: '#505356', bg: '#1a1b1c', border: '#232426',
        icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> },
    }
    const cfg = cfgMap[status]

    return (
      <div className="flex items-start gap-4 animate-slide-up">
        <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: '#252628', marginTop: 2 }}>
          <span style={{ color: '#8a8d90', fontSize: 10, fontWeight: 700 }}>OB</span>
        </div>
        <div className="flex-1 min-w-0" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <p className="text-sm text-[#c8cacb]">{content.summary || 'Actions were proposed.'}</p>

          {status === 'approved' ? (
            <div className="rounded-xl overflow-hidden" style={{ border: '1px solid #1e3826', background: '#141e17' }}>
              <div className="px-4 py-3 flex items-center gap-2.5 text-sm text-[#3d9e6a]" style={{ borderBottom: results.length ? '1px solid #1e3826' : 'none' }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="20 6 9 17 4 12" /></svg>
                {approvedCount} action{approvedCount !== 1 ? 's' : ''} executed
              </div>
              {results.length > 0 && (
                <div className="px-4 py-3" style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                  {results.map((r, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span style={{ color: r.success ? '#3d9e6a' : '#cc6666', flexShrink: 0, marginTop: 1 }}>
                        {r.success ? '✓' : '✕'}
                      </span>
                      <span style={{ color: r.success ? '#9a9da0' : '#cc6666' }}>{r.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl text-sm" style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color }}>
              {cfg.icon}
              {cfg.text}
            </div>
          )}

          <p className="text-xs text-[#4a4d50]">{new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
        </div>
      </div>
    )
  }

  // ── Pending state ─────────────────────────────────────────────────────────
  return (
    <div className="flex items-start gap-4 animate-slide-up">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ background: '#252628', marginTop: 2 }}
      >
        <span style={{ color: '#8a8d90', fontSize: 10, fontWeight: 700 }}>OB</span>
      </div>

      <div className="flex-1 min-w-0" style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
        <p className="text-sm text-[#c8cacb] leading-relaxed">
          {content.summary || 'Review and approve the actions you\'d like to execute.'}
        </p>

        <div className="rounded-2xl overflow-hidden" style={{ border: '1px solid #2a2c2e', background: '#1e1f21' }}>
          {/* Header */}
          <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid #2a2c2e' }}>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-[#6b6e72]">
              {actions.length} proposed action{actions.length !== 1 ? 's' : ''}
            </p>
            {actions.length > 1 && (
              <div className="flex items-center gap-3">
                <button onClick={() => setSelected(new Set(actions.map(getId)))} className="text-xs text-[#4f80f0] hover:text-[#7aa0f7] transition-colors">All</button>
                <span className="text-[#2e3032]">·</span>
                <button onClick={() => setSelected(new Set())} className="text-xs text-[#6b6e72] hover:text-[#9a9da0] transition-colors">None</button>
              </div>
            )}
          </div>

          {/* Action list */}
          <div className="px-4 py-3" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {actions.map((action, i) => {
              const id  = getId(action, i)
              const sel = selected.has(id)
              return (
                <button
                  key={id}
                  onClick={() => toggle(id)}
                  className="w-full flex items-start gap-3 p-3 rounded-xl text-left transition-colors"
                  style={{ background: sel ? '#141e17' : '#17181a', border: `1px solid ${sel ? '#1e3826' : '#2a2c2e'}` }}
                >
                  <ActionCheckbox checked={sel} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p className={`text-sm font-medium ${sel ? 'text-[#e4e4e4]' : 'text-[#9a9da0]'}`}>
                      {action.action_type?.replace(/_/g, ' ') || `Action ${i + 1}`}
                    </p>
                    {action.justification && (
                      <p className="text-xs text-[#4a4d50] mt-0.5 leading-relaxed">{action.justification}</p>
                    )}
                    {action.parameters && Object.keys(action.parameters).length > 0 && (
                      <p className="text-xs font-mono text-[#4a4d50] mt-1">{JSON.stringify(action.parameters)}</p>
                    )}
                    {action.impact_estimate && (
                      <p className="text-xs text-[#3d9e6a] mt-1">{action.impact_estimate}</p>
                    )}
                  </div>
                  {action.reversible === false && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0" style={{ background: '#2e1a1a', color: '#cc6666', border: '1px solid #3a2020' }}>
                      irreversible
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Footer buttons */}
          <div className="px-4 pb-4 flex gap-2">
            <button
              onClick={handleDecline}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all"
              style={{ background: '#17181a', color: '#6b6e72', border: '1px solid #2a2c2e' }}
              onMouseEnter={(e) => { e.currentTarget.style.background = '#1e1f21'; e.currentTarget.style.color = '#9a9da0' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = '#17181a'; e.currentTarget.style.color = '#6b6e72' }}
            >
              Decline
            </button>
            <button
              onClick={handleApprove}
              disabled={selected.size === 0 || submitting || !workflowId}
              className="flex-[2] py-2.5 rounded-xl text-sm font-medium transition-all"
              style={{
                background: selected.size > 0 && !submitting && workflowId ? '#3d9e6a' : '#1e1f21',
                color:      selected.size > 0 && !submitting && workflowId ? '#fff'     : '#4a4d50',
                border:     `1px solid ${selected.size > 0 && !submitting && workflowId ? '#3d9e6a' : '#2e3032'}`,
                cursor:     selected.size === 0 || submitting || !workflowId ? 'not-allowed' : 'pointer',
              }}
            >
              {submitting ? 'Submitting…' : selected.size > 0 ? `Approve ${selected.size}` : 'Select to approve'}
            </button>
          </div>
        </div>

        <p className="text-xs text-[#4a4d50]">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  )
}

// ── Streaming bubble (tokens arriving) ───────────────────────────────────────

function StreamingBubble({ message }) {
  // Count words to give a sense of progress without showing raw half-rendered markdown
  const wordCount = message.content ? message.content.trim().split(/\s+/).length : 0
  const stage = wordCount === 0 ? 'Thinking…'
    : wordCount < 30  ? 'Gathering data…'
    : wordCount < 80  ? 'Analyzing findings…'
    : wordCount < 150 ? 'Synthesizing…'
    : 'Preparing response…'

  return (
    <div className="flex items-start gap-4 animate-slide-up">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ background: '#252628', marginTop: 2 }}
      >
        <span style={{ color: '#8a8d90', fontSize: 10, fontWeight: 700 }}>OB</span>
      </div>
      <div className="flex-1 min-w-0 pt-2">
        <div className="flex items-center gap-2.5">
          <div className="flex gap-1.5">
            {[0, 150, 300].map((delay) => (
              <span
                key={delay}
                className="w-1.5 h-1.5 rounded-full animate-bounce"
                style={{ background: '#505356', animationDelay: `${delay}ms` }}
              />
            ))}
          </div>
          <span className="text-xs text-[#4a4d50]">{stage}</span>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────

export default function MessageBubble({ message }) {
  if (message.role === 'streaming') return <StreamingBubble message={message} />
  if (message.role === 'approval')  return <InlineApprovalCard message={message} />

  const isUser  = message.role === 'user'
  const isError = message.role === 'error'

  if (isUser) {
    return (
      <div className="flex justify-end animate-slide-up">
        <div
          className="rounded-2xl rounded-tr-md px-5 py-3"
          style={{ maxWidth: '72%', background: '#252628' }}
        >
          <p className="text-sm text-[#e4e4e4] leading-relaxed">{message.content}</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex items-start gap-4 animate-slide-up">
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold"
          style={{ background: '#3a1818', color: '#cc6666', marginTop: 2 }}
        >
          !
        </div>
        <div
          className="flex-1 px-4 py-3 rounded-2xl rounded-tl-md text-sm text-[#cc6666]"
          style={{ background: '#1e1414', border: '1px solid #3a2020' }}
        >
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-4 animate-slide-up">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ background: '#252628', marginTop: 2 }}
      >
        <span style={{ color: '#8a8d90', fontSize: 10, fontWeight: 700 }}>OB</span>
      </div>
      <div className="flex-1 min-w-0">
        <AssistantResponse content={message.content} />
        <p className="text-xs text-[#4a4d50] mt-3">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  )
}
