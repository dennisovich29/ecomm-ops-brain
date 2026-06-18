# Frontend Architecture

## Component Tree

```mermaid
graph TD
    Page["page.js\n(app entry)"] --> Sidebar
    Page --> Main["main — ChatArea"]

    Sidebar --> SessionList["session list\n(click → setActiveSession)"]
    Sidebar --> IncidentList["incident list\n(from /api/incidents)"]

    Main --> ChatArea
    ChatArea --> MessageBubble["MessageBubble\n(one per message)"]
    ChatArea --> LoadingDots
    ChatArea --> InputBar

    MessageBubble -- role=approval --> InlineApprovalCard["InlineApprovalCard\n(checkbox list + approve/decline)"]
    MessageBubble -- role=user --> UserBubble["right-aligned bubble"]
    MessageBubble -- role=assistant --> AssistantCard["structured response card"]
    MessageBubble -- role=streaming --> StreamingBubble["animated progress indicator\n(Thinking… / Gathering data… / Analyzing…)"]
    MessageBubble -- role=error --> ErrorBanner["red error banner"]

    InlineApprovalCard --> ApproveBtn["POST /api/actions/approve"]
    InlineApprovalCard --> DeclineBtn["POST /api/actions/decline"]
```

---

## Zustand Store

```mermaid
classDiagram
    class ZustandStore {
        +Session[] sessions
        +string activeSessionId
        +Message[] messages
        +boolean isLoading
        +boolean sidebarOpen
        +Incident[] incidents

        +newChat()
        +setActiveSession(id)
        +addSession(session)
        +addMessage(msg)
        +updateMessage(id, changes)
        +setLoading(v)
        +setIncidents(incidents)
        +toggleSidebar()
    }

    class Session {
        +str id
        +str title
        +str createdAt
    }

    class Message {
        +str id
        +str role
        +any content
        +str timestamp
    }

    ZustandStore --> Session
    ZustandStore --> Message
```

### Message roles

```mermaid
stateDiagram-v2
    [*] --> user : user sends
    user --> streaming : first SSE event arrives
    streaming --> assistant : final_response (non-action)
    streaming --> approval : final_response type==approval_pending
    streaming --> error : error event or exception
```

> **Streaming bubble**: while in `streaming` state the bubble shows an animated stage label
> (`Thinking…` / `Gathering data…` / `Analyzing findings…` / `Synthesizing…` / `Preparing response…`)
> derived from the word-count of buffered tokens — raw tokens are not displayed.

---

## Chat Send Flow (useChat hook)

```mermaid
sequenceDiagram
    participant User
    participant InputBar
    participant useChat
    participant Store as Zustand Store
    participant api as lib/api.js streamChat
    participant Proxy as /api/chat/stream

    User->>InputBar: types + submits
    InputBar->>useChat: sendMessage(text)
    useChat->>Store: addMessage {role:user}
    useChat->>Store: setLoading(true)
    useChat->>api: streamChat(text, sessionId)
    api->>Proxy: POST fetch + ReadableStream

    loop SSE events
        Proxy-->>api: data: {type,...}
        api-->>useChat: yield event

        alt first event
            useChat->>Store: addMessage {role:streaming, id:streamMsgId}
            useChat->>Store: setLoading(false)
        else type==token
            useChat->>Store: updateMessage(streamMsgId, content+=token)
        else type==final_response diagnostic
            useChat->>Store: updateMessage → role:assistant
        else type==final_response approval_pending
            useChat->>Store: updateMessage → role:approval
        else type==error
            useChat->>Store: updateMessage → role:error
        end
    end

    useChat->>Store: setLoading(false)
```

---

## API Proxy Layer

```mermaid
graph LR
    subgraph Browser["Browser (client-side)"]
        A[lib/api.js]
    end

    subgraph NextServer["Next.js Server (server-side only)"]
        B[POST /api/chat/stream]
        C[GET /api/actions/pending]
        D[POST /api/actions/approve]
        E[POST /api/actions/decline]
        F[GET /api/incidents]
    end

    subgraph FastAPI["FastAPI :8000"]
        G[POST /chat/stream]
        H[GET /actions/pending]
        I[POST /actions/approve]
        J[POST /actions/decline]
        K[GET /incidents]
    end

    A --> B & C & D & E & F
    B -- "SSE body passthrough\nContent-Type: text/event-stream" --> G
    C --> H
    D --> I
    E --> J
    F --> K

    note["API_URL env var\ndefault: http://localhost:8000\nDocker: http://backend:8000"] -.- NextServer
```

---

## File Structure

```
frontend/src/
├── app/
│   ├── page.js              entry — Sidebar + ChatArea
│   ├── layout.js            HTML shell
│   ├── globals.css          Tailwind base
│   └── api/
│       ├── chat/stream/route.js      SSE proxy
│       ├── actions/pending/route.js
│       ├── actions/approve/route.js
│       ├── actions/decline/route.js
│       └── incidents/route.js
├── components/
│   ├── Sidebar.jsx
│   ├── ChatArea.jsx
│   ├── MessageBubble.jsx
│   ├── ApprovalPanel.jsx
│   ├── InputBar.jsx
│   └── LoadingDots.jsx
├── hooks/
│   └── useChat.js
└── lib/
    ├── api.js               fetch wrappers + SSE async generator
    └── store.js             Zustand store
```
