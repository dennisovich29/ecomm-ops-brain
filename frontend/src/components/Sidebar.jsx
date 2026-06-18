'use client'

import useStore from '@/lib/store'

// ─── Icons ───────────────────────────────────────────────────────────────────

function IconMenu() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  )
}

function IconPlus() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

function IconClock() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}


function SectionLabel({ children }) {
  return (
    <p className="px-3 pt-5 pb-1.5 text-[11px] font-semibold uppercase tracking-widest text-[#4a4d50]">
      {children}
    </p>
  )
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function Sidebar() {
  const sessions         = useStore((s) => s.sessions)
  const activeSessionId  = useStore((s) => s.activeSessionId)
  const setActiveSession = useStore((s) => s.setActiveSession)
  const newChat          = useStore((s) => s.newChat)
  const incidents        = useStore((s) => s.incidents)
  const sidebarOpen      = useStore((s) => s.sidebarOpen)
  const toggleSidebar    = useStore((s) => s.toggleSidebar)

  // ── Collapsed rail ─────────────────────────────────────────────────────────
  if (!sidebarOpen) {
    return (
      <div
        className="flex flex-col items-center py-5 gap-2"
        style={{ width: 68, background: '#141516', borderRight: '1px solid #2a2c2e', flexShrink: 0 }}
      >
        <button
          onClick={toggleSidebar}
          className="w-10 h-10 flex items-center justify-center rounded-xl text-[#6b6e72] hover:bg-[#222426] hover:text-[#e4e4e4] transition-colors"
          aria-label="Open sidebar"
        >
          <IconMenu />
        </button>
        <button
          onClick={newChat}
          className="w-10 h-10 flex items-center justify-center rounded-xl text-[#6b6e72] hover:bg-[#222426] hover:text-[#e4e4e4] transition-colors"
          aria-label="New chat"
        >
          <IconPlus />
        </button>
      </div>
    )
  }

  // ── Full sidebar ───────────────────────────────────────────────────────────
  return (
    <div
      className="flex flex-col h-full"
      style={{ width: 264, background: '#141516', borderRight: '1px solid #2a2c2e', flexShrink: 0 }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-5">
        <button
          onClick={toggleSidebar}
          className="w-9 h-9 flex items-center justify-center rounded-xl text-[#6b6e72] hover:bg-[#222426] hover:text-[#e4e4e4] transition-colors flex-shrink-0"
          aria-label="Close sidebar"
        >
          <IconMenu />
        </button>
        <div className="flex items-center gap-2.5 ml-1">
          <div
            className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
            style={{ background: '#252628' }}
          >
            <span style={{ color: '#8a8d90', fontSize: 9, fontWeight: 700 }}>OB</span>
          </div>
          <span className="text-sm font-medium text-[#d0d2d4]">Ops Brain</span>
        </div>
      </div>

      {/* New chat */}
      <div className="px-3 mb-1">
        <button
          onClick={newChat}
          className="w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm text-[#b0b3b6] hover:bg-[#1e1f21] hover:text-[#e4e4e4] transition-colors"
        >
          <IconPlus />
          New chat
        </button>
      </div>


      {/* Scrollable history */}
      <div className="flex-1 overflow-y-auto">
        {sessions.length > 0 && (
          <div>
            <SectionLabel>Recent</SectionLabel>
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveSession(s.id)}
                className="w-full flex items-center gap-2.5 px-6 py-2.5 text-sm text-left transition-colors"
                style={{
                  color:      s.id === activeSessionId ? '#e4e4e4' : '#7a7d80',
                  background: s.id === activeSessionId ? '#1e1f21' : 'transparent',
                }}
                onMouseEnter={(e) => {
                  if (s.id !== activeSessionId) e.currentTarget.style.background = '#191a1c'
                }}
                onMouseLeave={(e) => {
                  if (s.id !== activeSessionId) e.currentTarget.style.background = 'transparent'
                }}
              >
                <IconClock />
                <span className="truncate flex-1">{s.title || 'New conversation'}</span>
              </button>
            ))}
          </div>
        )}

        {incidents.length > 0 && (
          <div>
            <SectionLabel>Past Incidents</SectionLabel>
            {incidents.slice(0, 10).map((inc) => (
              <div
                key={inc.id}
                className="flex items-center gap-2.5 px-6 py-2.5 text-sm text-[#7a7d80] hover:bg-[#191a1c] transition-colors cursor-default"
              >
                <span
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: inc.resolved ? '#3d9e6a' : '#cc4444' }}
                />
                <span className="truncate">{inc.query || 'Incident'}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-3 py-4" style={{ borderTop: '1px solid #2a2c2e' }}>
        <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#1e1f21] transition-colors cursor-pointer">
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-semibold"
            style={{ background: '#252628', color: '#8a8d90' }}
          >
            U
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-[#c8cacb] truncate">Operations Team</p>
            <p className="text-xs text-[#505356] truncate">ops@company.com</p>
          </div>
        </div>
      </div>
    </div>
  )
}

