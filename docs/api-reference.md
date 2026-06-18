# API Reference

## Endpoint Map

```mermaid
graph LR
    subgraph FastAPI["FastAPI :8000"]
        H1[GET /health]
        H2[GET /ready]
        C1[POST /chat]
        C2[POST /chat/stream]
        A1[GET /actions/pending]
        A2[POST /actions/approve]
        A3[POST /actions/decline]
        I1[GET /incidents]
        I2["GET /incidents/{id}"]
    end

    subgraph NextProxy["Next.js Proxy /api/*"]
        N1[POST /api/chat/stream]
        N2[GET /api/actions/pending]
        N3[POST /api/actions/approve]
        N4[POST /api/actions/decline]
        N5[GET /api/incidents]
    end

    Browser --> N1 & N2 & N3 & N4 & N5
    N1 --> C2
    N2 --> A1
    N3 --> A2
    N4 --> A3
    N5 --> I1
```

---

## Diagnostic Query Flow (SSE)

```mermaid
sequenceDiagram
    participant Browser
    participant Proxy as Next.js /api/chat/stream
    participant API as FastAPI /chat/stream
    participant Graph as LangGraph

    Browser->>Proxy: POST {content, session_id}
    Proxy->>API: POST (proxy)
    API->>Graph: ainvoke OpsState
    Graph-->>API: SSE events
    API-->>Proxy: text/event-stream
    Proxy-->>Browser: streamed pass-through

    Note over Browser,Proxy: data: {"type":"token","content":"..."}
    Note over Browser,Proxy: data: {"type":"agent_start","agent":"sales"}
    Note over Browser,Proxy: data: {"type":"final_response","response":{...}}
```

---

## HITL Action Flow

```mermaid
sequenceDiagram
    participant Browser
    participant Proxy as Next.js
    participant API as FastAPI
    participant Graph as LangGraph

    Browser->>Proxy: POST /api/chat/stream {content:"Fix it"}
    Proxy->>API: POST /chat/stream
    API->>Graph: ainvoke
    Graph-->>API: SSE {type:"approval_pending", actions:[...]}
    API-->>Browser: approval_pending event

    Note over Browser: ApprovalPanel rendered

    Browser->>Proxy: POST /api/actions/approve {request_id, approved_action_ids}
    Proxy->>API: POST /actions/approve
    API->>Graph: ainvoke Command(resume=...)
    Graph-->>API: {status:"executed", results:[...]}
    API-->>Browser: execution result
```

---

## Endpoints

### Health

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/health` | No | `{"status":"ok"}` |
| GET | `/ready` | No | `{"status":"ready"\|"degraded","checks":{postgres,redis,qdrant}}` |

### Chat

| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| POST | `/chat` | Bearer | `{content, session_id?}` | `{session_id, turn_id, response}` |
| POST | `/chat/stream` | Bearer | `{content, session_id?}` | SSE stream |

### Actions

| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| POST | `/actions/approve` | Bearer | `{request_id, approved_action_ids}` | `{status:"executed", results}` |
| POST | `/actions/decline` | Bearer | `{request_id}` | `{status:"declined"}` |

### Incidents

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/incidents` | Bearer | `{incidents:[IncidentSummary]}` max 20 |
| GET | `/incidents/{id}` | Bearer | `{incident:{...actions:[]}}` or 404 |

---

## Auth Flow

```mermaid
flowchart LR
    req([Request]) --> chk{API_SECRET_KEY\n== change-me?}
    chk -- yes --> skip[skip — dev mode]
    chk -- no --> hdr{Authorization\n== Bearer KEY?}
    hdr -- yes --> ok[200 / handler]
    hdr -- no --> err[401 Unauthorized]
    skip --> ok
```

---

## SSE Event Types

```mermaid
classDiagram
    class TokenEvent {
        +str type = "token"
        +str content
        Note: only emitted by synthesize_findings node
    }
    class AgentEvent {
        +str type = "agent_start" | "agent_done"
        +str agent
    }
    class ApprovalEvent {
        +str type = "approval_request"
        +list actions
        +str thread_id
    }
    class FinalResponseEvent {
        +str type = "final_response"
        +dict response
    }
    class ErrorEvent {
        +str type = "error"
        +str message
    }
```

