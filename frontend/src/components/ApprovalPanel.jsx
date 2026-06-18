'use client'

import { useState } from 'react'
import useStore from '@/lib/store'
import { approveActions, fetchPendingActions } from '@/lib/api'

const XIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
)

const CheckIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
)

function ActionCard({ workflowItem, onApprove }) {
  const [selected, setSelected] = useState(new Set())
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  const getActionId = (action, i) =>
    action.action_id || action.id || String(i)

  const toggleAction = (actionId) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(actionId)) next.delete(actionId)
      else next.add(actionId)
      return next
    })
  }

  const selectAll = () =>
    setSelected(new Set((workflowItem.actions ?? []).map((a, i) => getActionId(a, i))))

  const clearAll = () => setSelected(new Set())

  const handleApprove = async () => {
    if (selected.size === 0) return
    setSubmitting(true)
    try {
      await onApprove(workflowItem.workflow_id, [...selected])
      setDone(true)
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <div
        className="flex items-center gap-3 px-4 py-3.5 rounded-2xl text-sm text-[#3d9e6a]"
        style={{ background: '#141e17', border: '1px solid #1e3826' }}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
        Decision submitted
      </div>
    )
  }

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: '#1e1f21', border: '1px solid #2a2c2e' }}
    >
      {/* Card header */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{ borderBottom: '1px solid #2a2c2e' }}
      >
        <div>
          <p className="text-xs font-mono text-[#6b6e72]">
            {workflowItem.workflow_id.slice(0, 12)}…
          </p>
          {workflowItem.expires_at && (
            <p className="text-xs text-[#4a4d50] mt-0.5">
              Expires{' '}
              {new Date(workflowItem.expires_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={selectAll}
            className="text-xs text-[#4f80f0] hover:text-[#7aa0f7] transition-colors"
          >
            All
          </button>
          <span className="text-[#2e3032]">·</span>
          <button
            onClick={clearAll}
            className="text-xs text-[#6b6e72] hover:text-[#9a9da0] transition-colors"
          >
            None
          </button>
        </div>
      </div>

      {/* Actions list */}
      <div className="px-4 py-3" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {(workflowItem.actions ?? []).map((action, i) => {
          const actionId = getActionId(action, i)
          const isSelected = selected.has(actionId)
          const label = action.action_type || action.description || `Action ${i + 1}`
          const detail =
            action.description && action.action_type ? action.description : null
          return (
            <button
              key={actionId}
              onClick={() => toggleAction(actionId)}
              className="w-full flex items-start gap-3 p-3 rounded-xl text-left transition-colors"
              style={{
                background: isSelected ? '#141e17' : '#17181a',
                border: `1px solid ${isSelected ? '#1e3826' : '#2a2c2e'}`,
              }}
            >
              <div
                className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0 transition-all"
                style={{
                  marginTop: 2,
                  border: `1.5px solid ${isSelected ? '#3d9e6a' : '#3e4144'}`,
                  background: isSelected ? '#3d9e6a' : 'transparent',
                }}
              >
                {isSelected && <CheckIcon />}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p className={`text-sm ${isSelected ? 'text-[#e4e4e4]' : 'text-[#9a9da0]'}`}>
                  {label}
                </p>
                {detail && (
                  <p className="text-xs text-[#4a4d50] mt-0.5">{detail}</p>
                )}
                {action.parameters && Object.keys(action.parameters).length > 0 && (
                  <p className="text-xs font-mono text-[#4a4d50] mt-1">
                    {JSON.stringify(action.parameters)}
                  </p>
                )}
              </div>
            </button>
          )
        })}
      </div>

      {/* Approve button */}
      <div className="px-4 pb-4">
        <button
          onClick={handleApprove}
          disabled={selected.size === 0 || submitting}
          className="w-full py-2.5 rounded-xl text-sm font-medium transition-all"
          style={{
            background: selected.size > 0 && !submitting ? '#3d9e6a' : '#1e1f21',
            color:      selected.size > 0 && !submitting ? '#fff'     : '#4a4d50',
            border:     `1px solid ${selected.size > 0 && !submitting ? '#3d9e6a' : '#2e3032'}`,
            cursor:     selected.size === 0 || submitting ? 'not-allowed' : 'pointer',
          }}
        >
          {submitting
            ? 'Submitting…'
            : selected.size > 0
            ? `Approve ${selected.size} action${selected.size > 1 ? 's' : ''}`
            : 'Select actions to approve'}
        </button>
      </div>
    </div>
  )
}

export default function ApprovalPanel() {
  const pendingActions = useStore((s) => s.pendingActions)
  const setPendingActions = useStore((s) => s.setPendingActions)
  const toggleApprovalPanel = useStore((s) => s.toggleApprovalPanel)

  const handleApprove = async (workflowId, actionIds) => {
    await approveActions(workflowId, actionIds)
    const data = await fetchPendingActions()
    setPendingActions(data.pending || [])
  }

  return (
    <div
      className="flex flex-col h-full animate-slide-in-right"
      style={{ width: 380, background: '#141516', borderLeft: '1px solid #2a2c2e', flexShrink: 0 }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-5"
        style={{ borderBottom: '1px solid #2a2c2e' }}
      >
        <div>
          <h2 className="text-sm font-semibold text-[#e4e4e4]">Approval Queue</h2>
          <p className="text-xs text-[#7a7d80] mt-0.5">
            {pendingActions.length} pending workflow
            {pendingActions.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={toggleApprovalPanel}
          className="w-8 h-8 flex items-center justify-center rounded-lg text-[#6b6e72] hover:bg-[#1e1f21] hover:text-[#c8cacb] transition-colors"
        >
          <XIcon />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-5 flex flex-col gap-4">
        {pendingActions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center"
              style={{ background: '#1e1f21' }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3d9e6a" strokeWidth="2.5" strokeLinecap="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <p className="text-sm text-[#7a7d80]">No pending approvals</p>
            <p className="text-xs text-[#4a4d50] max-w-[220px] leading-relaxed">
              Actions proposed by the AI will appear here for your review.
            </p>
          </div>
        ) : (
          pendingActions.map((item) => (
            <ActionCard
              key={item.workflow_id}
              workflowItem={item}
              onApprove={handleApprove}
            />
          ))
        )}
      </div>
    </div>
  )
}
