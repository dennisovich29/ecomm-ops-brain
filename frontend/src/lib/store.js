import { create } from 'zustand'

const useStore = create((set) => ({
  // Sessions
  sessions: [],
  activeSessionId: null,

  // Messages stored per-session so switching never loses an in-flight stream
  messagesBySession: {},   // { [sessionId]: Message[] }

  // Loading state per-session so a background stream does not block a new chat
  loadingBySession: {},    // { [sessionId]: boolean }

  // UI state
  sidebarOpen: true,

  // Data
  incidents: [],

  // Actions

  // Start a new blank chat (does not touch any other session's messages)
  newChat: () => {
    const id = crypto.randomUUID()
    set({ activeSessionId: id })
  },

  // Switch to an existing session (its messages are preserved in messagesBySession)
  setActiveSession: (id) => set({ activeSessionId: id }),

  addSession: (session) =>
    set((state) => ({
      sessions: [session, ...state.sessions.filter((s) => s.id !== session.id)],
    })),

  // Always scoped to a specific session - safe to call from background streams
  addMessage: (sessionId, msg) =>
    set((state) => ({
      messagesBySession: {
        ...state.messagesBySession,
        [sessionId]: [...(state.messagesBySession[sessionId] || []), msg],
      },
    })),

  updateMessage: (sessionId, id, changes) =>
    set((state) => ({
      messagesBySession: {
        ...state.messagesBySession,
        [sessionId]: (state.messagesBySession[sessionId] || []).map(
          (m) => (m.id === id ? { ...m, ...changes } : m)
        ),
      },
    })),

  setLoading: (sessionId, v) =>
    set((state) => ({
      loadingBySession: { ...state.loadingBySession, [sessionId]: v },
    })),

  setIncidents: (incidents) => set({ incidents }),

  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}))

export default useStore