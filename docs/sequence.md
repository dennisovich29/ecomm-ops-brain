# Sequence Diagrams — Ecomm Ops Brain

## 1. Diagnostic Query (full pipeline)

```mermaid
sequenceDiagram
    actor Operator
    participant FE as Next.js
    participant API as FastAPI
    participant LG as LangGraph
    participant PG as PostgreSQL
    participant QD as Qdrant
    participant AZ as Azure OpenAI

    Operator->>FE: types query
    FE->>API: POST /api/chat/stream
    API->>PG: load prior OpsState from AsyncPostgresSaver (thread_id=session_id)
    API->>LG: astream(OpsState, stream_mode=[values,messages])

    LG->>AZ: classify intent (GPT-4o structured output)
    AZ-->>LG: {query_type, domains, time_range, action_requested}

    par parallel dispatch
        LG->>PG: Sales Agent — SQL queries
        LG->>PG: Inventory Agent — SQL queries
        LG->>PG: Marketing Agent — SQL queries
        LG->>PG: Support Agent — SQL queries
    end

    PG-->>LG: domain findings × 4

    LG->>LG: reflect() — score confidence, detect gaps

    alt confidence < 0.70 AND gaps exist AND passes < 3
        LG->>LG: route_intent → dispatch missing domain agents only
        LG->>PG: missing domain agent SQL queries
        PG-->>LG: supplemental findings
        LG->>LG: reflect() again
    end

    LG->>QD: embed current state, search top-3 similar incidents (score ≥ 0.5)
    QD-->>LG: similar_incidents[]

    LG->>AZ: synthesize_findings (GPT-4o, streams tokens)

    loop token stream
        AZ-->>LG: partial token
        LG-->>API: message event (langgraph_node=synthesize_findings)
        API-->>FE: SSE data: {"type":"token","content":"..."}
        FE-->>Operator: live typewriter text
    end

    AZ-->>LG: full RCA text

    LG->>QD: embed + upsert incident (store_incident)
    LG->>PG: mirror incident to incidents table

    LG->>LG: format_response (DIAGNOSTIC)
    LG-->>API: final OpsState
    API->>PG: checkpoint full OpsState (AsyncPostgresSaver)
    API-->>FE: SSE data: {"type":"final_response","response":{...}}
    FE-->>Operator: rendered markdown response + confidence + domains
```

---

## 2. Action / HITL Query

```mermaid
sequenceDiagram
    actor Operator
    participant FE as Next.js
    participant API as FastAPI
    participant LG as LangGraph
    participant PG as PostgreSQL
    participant QD as Qdrant
    participant AZ as Azure OpenAI

    Note over Operator,AZ: Same pipeline as Diagnostic up through store_incident

    Operator->>FE: "Restock products and resume the paused campaign"
    FE->>API: POST /api/chat/stream
    API->>LG: astream(OpsState)

    LG->>AZ: classify intent → HYBRID, action_requested=true
    LG->>PG: parallel agent SQL queries (all 4 domains)
    LG->>LG: reflect, retrieve memory, synthesize, store incident

    LG->>PG: fetch valid product IDs + campaign IDs (grounding)
    PG-->>LG: products[], campaigns[]

    LG->>AZ: propose_actions (GPT-4o, grounded in real IDs)
    AZ-->>LG: proposed_actions[]

    LG->>LG: hitl_checkpoint — interrupt({"proposed_actions": [...]})
    Note over LG: Graph pauses — state saved to PostgreSQL checkpointer

    LG-->>API: interrupt signal
    API-->>FE: SSE data: {"type":"final_response","response":{"type":"approval_pending","proposed_actions":[...],"workflow_id":"<session_id>"}}
    FE-->>Operator: InlineApprovalCard — checkboxes per action

    Operator->>FE: selects actions, clicks Approve
    FE->>API: POST /api/actions/approve {request_id: session_id, approved_action_ids:[...]}
    API->>LG: ainvoke(Command(resume={"approved_action_ids":[...]}))

    LG->>LG: hitl_checkpoint resumes — filters approved_actions

    loop for each approved action
        LG->>PG: execute_action (restock / pause / resume / ticket)
        PG-->>LG: {success, message}
    end

    LG->>LG: format_response (action_executed)
    API->>PG: checkpoint updated OpsState
    API-->>FE: {"type":"final_response","response":{"type":"action_executed","executed_actions":[...]}}
    FE-->>Operator: execution summary
```

---

## 3. Memory Query

```mermaid
sequenceDiagram
    actor Operator
    participant FE as Next.js
    participant API as FastAPI
    participant LG as LangGraph
    participant PG as PostgreSQL
    participant QD as Qdrant
    participant AZ as Azure OpenAI

    Operator->>FE: "Have we had stockout-driven revenue drops before?"
    FE->>API: POST /api/chat/stream
    API->>PG: load prior OpsState
    API->>LG: astream(OpsState)

    LG->>AZ: classify intent → MEMORY, domains=[sales, inventory]
    LG->>PG: Sales + Inventory agent SQL queries (parallel)
    PG-->>LG: findings

    LG->>LG: reflect() → confidence sufficient → synthesize

    LG->>QD: embed("Have we had stockout-driven revenue drops before? | sales:... | inventory:...")
    Note over QD: Cosine similarity search, threshold=0.5, top_k=3
    QD-->>LG: [{incident_id, date, query, root_cause, domains, similarity_score}×N]

    LG->>AZ: synthesize_findings — prompt includes similar_incidents as context
    AZ-->>LG: answer referencing past incidents (streams tokens)

    loop token stream
        LG-->>API: token event
        API-->>FE: SSE token
        FE-->>Operator: typewriter text
    end

    LG->>QD: store_incident (this memory query itself becomes an incident)
    LG->>PG: mirror to incidents table

    LG->>LG: format_response (MEMORY)
    API-->>FE: final_response with similar_incidents[] + summary
    FE-->>Operator: "Found N similar past incidents: ..."
```

---

## 4. HITL Decline Flow

```mermaid
sequenceDiagram
    actor Operator
    participant FE as Next.js
    participant API as FastAPI
    participant LG as LangGraph
    participant PG as PostgreSQL

    Note over Operator,PG: After propose_actions, graph is paused at hitl_checkpoint

    FE-->>Operator: InlineApprovalCard rendered
    Operator->>FE: clicks Decline All
    FE->>API: POST /api/actions/decline {request_id: session_id}
    API->>LG: ainvoke(Command(resume={"approved_action_ids":[]}))

    LG->>LG: hitl_checkpoint resumes — approved_actions = []
    LG->>LG: edge_after_hitl → "format_response" (no approved actions)
    LG->>LG: format_response → diagnostic response (no execution)

    API->>PG: checkpoint OpsState
    API-->>FE: final_response (type=diagnostic, no executed_actions)
    FE-->>Operator: analysis summary only, actions skipped
```

---

## 5. SUMMARY Query (short path)

```mermaid
sequenceDiagram
    actor Operator
    participant FE as Next.js
    participant API as FastAPI
    participant LG as LangGraph
    participant PG as PostgreSQL
    participant AZ as Azure OpenAI

    Operator->>FE: "Give me a dashboard overview of today"
    FE->>API: POST /api/chat/stream
    API->>LG: astream(OpsState)

    LG->>AZ: classify intent → SUMMARY, all domains
    LG->>PG: all 4 agents in parallel
    PG-->>LG: raw domain findings

    LG->>LG: reflect() → query_type=SUMMARY → edge returns "format_response" directly
    Note over LG: Skips retrieve_memory, synthesize_findings, store_incident entirely

    LG->>LG: format_response (_format_summary_response) — builds tables from raw findings
    API-->>FE: final_response (type=summary, structured findings tables)
    FE-->>Operator: Inventory / Sales / Marketing / Support tables
```

Note: SUMMARY queries do **not** write to Qdrant (no `store_incident` call) and do not invoke the LLM for synthesis.
