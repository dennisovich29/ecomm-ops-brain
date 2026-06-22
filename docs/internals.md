# System Internals — Ecomm Ops Brain

Visual deep-dive into every runtime layer. Each section is a standalone diagram for demo use.

---

## 1. Request Lifecycle — Browser to Response

Every user message passes through five distinct runtime layers before the response is streamed back.

```mermaid
sequenceDiagram
    participant B  as Browser
    participant FE as Next.js :3000
    participant API as FastAPI :8000
    participant LG as LangGraph
    participant AZ as Azure OpenAI
    participant QD as Qdrant
    participant PG as PostgreSQL

    B  ->> FE  : POST /api/chat/stream
    FE ->> API : POST /chat/stream  (proxy — browser never hits FastAPI directly)

    API ->> LG : graph.astream(OpsState, thread_config)

    LG  ->> AZ : classify intent   (GPT-4o structured output)
    AZ -->> LG : { query_type, domains, time_range, entities, action_requested }

    par Parallel Agent Dispatch
        LG ->> AZ : sales agent   — tool calls
    and
        LG ->> AZ : inventory agent — tool calls
    and
        LG ->> AZ : marketing agent — tool calls
    and
        LG ->> AZ : support agent — tool calls
    end

    LG ->> LG  : run_reflection  (pure Python — no LLM)

    LG ->> AZ  : embed incident text   (text-embedding-3-small-1)
    LG ->> QD  : search similar incidents  top_k=3, score_threshold=0.5
    QD -->> LG : similar_incidents[]

    LG ->> AZ  : synthesize_findings  (GPT-4o RCA)
    AZ -->> LG : root_cause_analysis, recommendations

    LG ->> QD  : upsert incident vector
    LG ->> PG  : INSERT INTO incidents  (best-effort mirror)

    LG -->> API : SSE token stream
    API -->> FE  : SSE token stream
    FE -->> B   : rendered response
```

---

## 2. Complete LangGraph Workflow

All 13 nodes and every conditional edge in one view.

```mermaid
flowchart TD

    START(["User Query"])

    subgraph ROUTE ["① Intent Routing"]
        RI["route_intent\nGPT-4o structured output"]
    end

    subgraph AGENTS ["② Parallel Agent Dispatch"]
        SA["run_sales_agent"]
        IA["run_inventory_agent"]
        MA["run_marketing_agent"]
        SUA["run_support_agent"]
    end

    subgraph REFLECT ["③ Reflection Gate"]
        RF["run_reflection\nPure Python — no LLM\nconfidence scoring + gap detection"]
    end

    subgraph MEMORY ["④ Memory Retrieval"]
        MEM["retrieve_memory\nQdrant similarity search"]
    end

    subgraph SYNTHESIS ["⑤ Synthesis + Storage"]
        SY["synthesize_findings\nGPT-4o root cause analysis"]
        SI["store_incident\nQdrant upsert + Postgres mirror"]
    end

    subgraph ACTIONS ["⑥ Action Pipeline"]
        PA["propose_actions\nGPT-4o grounded generation\n(real IDs fetched from DB first)"]
        HC["hitl_checkpoint\nLangGraph interrupt()\nfreezes graph — waits for operator"]
        EA["execute_actions\nSQL writes to Postgres"]
    end

    subgraph FINAL ["⑦ Format + Stream"]
        FR["format_response\nassembles final_response dict"]
        END_NODE(["SSE Response"])
    end

    START --> RI

    RI -->|"GENERAL or no domains"| FR
    RI -->|"has domains"| SA & IA & MA & SUA

    SA --> RF
    IA --> RF
    MA --> RF
    SUA --> RF

    RF -->|"query_type == SUMMARY"| FR
    RF -->|"gaps non-empty\nAND confidence < 0.70\nAND passes < 3"| RI
    RF -->|"else — synthesize"| MEM

    MEM --> SY
    SY --> SI

    SI -->|"ACTION\nor HYBRID + action_requested"| PA
    SI -->|"else"| FR

    PA --> HC

    HC -->|"operator approved"| EA
    HC -->|"operator declined"| FR

    EA --> FR
    FR --> END_NODE
```

---

## 3. Intent Classification — What the Router Produces

The intent router makes a single GPT-4o structured output call. Everything downstream depends on the result.

```mermaid
flowchart LR

    Q["User Query"] --> CHAIN["ChatPromptTemplate\n→ GPT-4o.with_structured_output(IntentOutput)"]

    CHAIN --> OUT["IntentOutput\n─────────────────\nquery_type  : str\ndomains     : list[str]\ntime_range  : { start, end }\nentities    : list[str]\naction_requested : bool"]

    OUT --> QT{"query_type"}

    QT -->|"GENERAL"| G["skip agents\n→ format_response directly"]

    QT -->|"SUMMARY"| S["run agents\n→ reflection\n→ format_response\n(skips synthesis)"]

    QT -->|"DIAGNOSTIC"| D["run agents\n→ reflection\n→ memory → synthesis\n→ format_response"]

    QT -->|"MEMORY"| M["run agents\n→ reflection\n→ memory → synthesis\n→ format_response"]

    QT -->|"ACTION"| A["run agents\n→ reflection\n→ synthesis\n→ propose_actions → HITL"]

    QT -->|"HYBRID"| H["full pipeline\npropose_actions only if\naction_requested = true"]
```

---

## 4. Parallel Agent Dispatch — Fan-Out / Fan-In

`edge_dispatch_agents` returns a list of node names — LangGraph executes all of them concurrently in the same graph step.

```mermaid
flowchart TD

    RI["route_intent"]

    RI --> EDGE{"edge_dispatch_agents\n─────────────────────\nreturns list of node names\n→ LangGraph runs all in parallel"}

    subgraph PARALLEL ["Runs concurrently"]
        SA["run_sales_agent\ntools: get_daily_revenue\nget_product_sales_breakdown\nget_regional_sales\ndetect_sales_anomaly\ncompare_sales_periods"]

        IA["run_inventory_agent\ntools: get_stock_levels\nget_stockout_events\nget_restock_recommendations\nget_views_vs_purchases"]

        MA["run_marketing_agent\ntools: get_campaign_metrics\nget_channel_performance\nget_active_promotions"]

        SUA["run_support_agent\ntools: get_ticket_volume\nget_refund_rates\nget_complaint_themes"]
    end

    EDGE --> SA
    EDGE --> IA
    EDGE --> MA
    EDGE --> SUA

    SA  --> RF["run_reflection\n(all agents converge here)"]
    IA  --> RF
    MA  --> RF
    SUA --> RF

    subgraph REQUERY ["On Re-query (reflection_passes > 0)"]
        NOTE["Only domains in gaps_identified are re-dispatched\nExisting findings from other domains are preserved"]
    end
```

---

## 5. Reflection Confidence Gate

The only node with zero LLM calls. Runs after every agent dispatch.

```mermaid
flowchart TD

    IN["run_reflection\nreceives all agent findings from state"]

    IN --> BASE["base_score = populated_domains ÷ total_domains"]

    BASE --> CORR["Corroboration Boosts  +0.10 each  capped at +0.30\n───────────────────────────────────────────────\n• inventory.stockout_events  AND  sales.revenue_summary\n• marketing.campaign_issues  AND  sales.revenue_summary\n• support.top_complaint_themes  AND  inventory.stockout_events"]

    CORR --> CONF["confidence = min(base_score + boost,  1.0)"]

    CONF --> GAPS["Identify gaps_identified\nformat:  'missing_{domain}_data'\ne.g.  ['missing_inventory_data', 'missing_support_data']"]

    GAPS --> INC["reflection_passes  +=  1"]

    INC --> DEC{"should_re_query?\n─────────────────────────────────\nAll 3 must be true to re-query"}

    DEC -->|"gaps non-empty\nAND passes < 3\nAND confidence < 0.70"| REQUERY["re_query\n→ route_intent\n(filtered to missing domains only)"]

    DEC -->|"query_type == SUMMARY\n(checked first in edge_after_reflection)"| FORMAT["format_response\nskips synthesis entirely"]

    DEC -->|"any condition false\n(enough confidence, no gaps,\nor max passes reached)"| SYNTH["synthesize\n→ retrieve_memory"]
```

---

## 6. Memory Layer — Store and Retrieve

Both operations use the same `_build_incident_text()` function so query and storage vectors are in the same semantic space.

```mermaid
flowchart LR

    subgraph STORE ["Store Incident  —  after synthesize_findings"]
        direction TB
        ST1["_build_incident_text(state)\n──────────────────────────────────────────\nuser_query\n| root_cause: root_cause_analysis[:400]\n| sales_findings: json.dumps(val)[:200]\n| inventory_findings: json.dumps(val)[:200]\n| marketing_findings: json.dumps(val)[:200]\n| support_findings: json.dumps(val)[:200]"]

        ST2["text-embedding-3-small-1\n1536-dimensional vector"]

        ST3[("Qdrant  —  collection: incidents\n────────────────────────────────\nPointStruct\n  id: uuid\n  vector: 1536-dim\n  payload:\n    incident_id, date, query\n    root_cause, domains\n    confidence, actions_taken")]

        ST4[("Postgres  —  table: incidents\n──────────────────────────────\nid, query, root_cause\ndomains, confidence, embedding_id\nON CONFLICT DO NOTHING\n(best-effort — failure is swallowed)")]

        ST1 --> ST2
        ST2 --> ST3
        ST2 --> ST4
    end

    subgraph RETRIEVE ["Retrieve Memory  —  before synthesize_findings"]
        direction TB
        RT1["_build_incident_text(state)\nsame function — same vector space"]

        RT2["text-embedding-3-small-1\nembed the current state"]

        RT3[("Qdrant search\ntop_k = 3\nscore_threshold = 0.5  cosine")]

        RT4["similar_incidents[]  →  stored in OpsState\n──────────────────────────────────────────\nincident_id  date  query\nroot_cause  domains  confidence\nactions_taken  similarity_score"]

        RT1 --> RT2
        RT2 --> RT3
        RT3 --> RT4
    end
```

---

## 7. Human-in-the-Loop — Suspend, Approve, Resume

LangGraph `interrupt()` freezes the graph. `AsyncPostgresSaver` persists the frozen state so it survives server restarts and arbitrary operator delays.

```mermaid
sequenceDiagram
    participant OP as Operator
    participant FE as Frontend
    participant API as FastAPI
    participant LG as LangGraph
    participant PG as PostgreSQL

    FE ->> API : POST /chat/stream

    API ->> LG : graph.astream(OpsState)
    LG ->> LG  : ... route → agents → reflect → memory → synthesize ...
    LG ->> LG  : propose_actions  (GPT-4o, grounded on real DB IDs)

    LG -->> API : SSE — proposed_actions[]
    API -->> FE  : SSE — proposed_actions[]
    FE -->> OP   : Inline Approval Card rendered

    LG ->> LG   : hitl_checkpoint — interrupt()
    LG ->> PG   : AsyncPostgresSaver — persist full frozen state

    Note over LG, PG : Graph is suspended. Server can restart. State is safe.

    alt Operator Approves
        OP  ->> FE  : clicks Approve
        FE  ->> API : POST /actions/approve  { session_id, turn_id, approved_actions }
        API ->> LG  : graph.aupdate_state(thread_config, { approved_actions: [...] })
        API ->> LG  : graph.astream(None, thread_config)  — resume from checkpoint

        LG ->> LG   : edge_after_hitl  →  execute_actions
        LG ->> PG   : SQL writes  (restock / discount / pause / resume / ticket)
        LG -->> API : SSE — executed_actions + final response
        API -->> FE  : SSE — action_executed response
        FE -->> OP   : result shown

    else Operator Declines
        OP  ->> FE  : clicks Decline
        FE  ->> API : POST /actions/decline  { session_id, turn_id }
        API ->> LG  : graph.aupdate_state(thread_config, { approved_actions: [] })
        API ->> LG  : graph.astream(None, thread_config)  — resume from checkpoint

        LG ->> LG   : edge_after_hitl  →  format_response
        LG -->> API : SSE — diagnostic response  (no actions taken)
        API -->> FE  : SSE — response
        FE -->> OP   : result shown
    end
```

---

## 8. Action Execution Pipeline

Each approved action maps to a specific SQL operation. Actions are executed independently — one failure does not abort the rest.

```mermaid
flowchart TD

    IN["approved_actions  list of dicts"]

    IN --> LOOP["iterate — execute_action(action) per item"]

    LOOP --> AT{"action_type"}

    AT -->|"restock_product"| RS["UPDATE products\nSET stock_quantity = stock_quantity + :qty\nWHERE id = :product_id"]

    AT -->|"apply_discount"| AD["UPDATE products\nSET discount_pct = :pct\nWHERE id = :product_id"]

    AT -->|"pause_campaign"| PC["UPDATE campaigns\nSET status = 'paused'\nWHERE id = :campaign_id"]

    AT -->|"resume_campaign"| RC["UPDATE campaigns\nSET status = 'active'\nWHERE id = :campaign_id"]

    AT -->|"create_support_ticket"| CT["INSERT INTO support_tickets\n( id, created_at, category, sentiment, resolved )"]

    RS & AD & PC & RC & CT --> RES["ActionResult\n─────────────────────────\naction_id    : str\naction_type  : str\nsuccess      : bool\nmessage      : str\nexecuted_at  : datetime"]

    RES --> COLL["executed_actions  →  stored in OpsState"]

    COLL --> FR["format_response\nresponse_type = 'action_executed'"]
```

---

## 9. OpsState — Full Field Map

Every field in the shared state, grouped by the node that writes it.

```mermaid
flowchart LR

    subgraph INPUT ["Input  (set by API on entry)"]
        F1["user_query : str"]
        F2["session_id : str"]
        F3["turn_id    : str"]
        F4["prior_context : Optional[str]"]
        F5["messages : Annotated[list, add_messages]"]
    end

    subgraph ROUTING ["Written by  route_intent"]
        F6["intent : Optional[Intent]\n  query_type, domains,\n  time_range, entities,\n  action_requested"]
        F7["active_agents : list[str]"]
    end

    subgraph FINDINGS ["Written by agent nodes"]
        F8["sales_findings     : Optional[dict]"]
        F9["inventory_findings : Optional[dict]"]
        F10["marketing_findings : Optional[dict]"]
        F11["support_findings   : Optional[dict]"]
    end

    subgraph REFL ["Written by  run_reflection"]
        F12["reflection_notes  : list[str]"]
        F13["confidence_score  : float"]
        F14["gaps_identified   : list[str]"]
        F15["reflection_passes : int"]
    end

    subgraph MEM ["Written by  retrieve_memory  /  store_incident"]
        F16["similar_incidents    : list[dict]"]
        F17["current_incident_id  : Optional[str]"]
    end

    subgraph SYNTH ["Written by  synthesize_findings"]
        F18["root_cause_analysis : Optional[str]"]
        F19["recommendations     : list[str]"]
    end

    subgraph ACT ["Written by  propose / hitl / execute"]
        F20["proposed_actions : list[dict]"]
        F21["approved_actions : list[dict]"]
        F22["executed_actions : list[dict]"]
    end

    subgraph RESP ["Written by  format_response"]
        F23["final_response : Optional[dict]\n  response_type, message,\n  root_cause_analysis,\n  recommendations,\n  similar_incidents,\n  executed_actions,\n  proposed_actions,\n  confidence_score"]
    end
```

---

## 10. Response Types — What format_response Emits

```mermaid
flowchart TD

    FR["format_response"]

    FR --> RT{"response_type\ndetermined by query path"}

    RT -->|"GENERAL query type"| GEN["general\n─────────────────────────\nmessage only\n(no domain data involved)"]

    RT -->|"SUMMARY query type"| SUM["summary\n─────────────────────────\nrecommendations list\n(the report — no RCA)"]

    RT -->|"DIAGNOSTIC or HYBRID\nno actions taken"| DIAG["diagnostic\n─────────────────────────\nroot_cause_analysis\nrecommendations\nsimilar_incidents"]

    RT -->|"MEMORY query type"| MEMR["memory_recall\n─────────────────────────\nsimilar_incidents\noriginal query"]

    RT -->|"actions were executed"| ACT["action_executed\n─────────────────────────\nexecuted_actions\nroot_cause_analysis\nrecommendations"]
```

---

## 11. Startup and Dependency Order

```mermaid
flowchart TD

    subgraph COMPOSE ["Docker Compose — depends_on chain"]
        PG_SVC["postgres\nhealthcheck: pg_isready -U postgres"]
        QD_SVC["qdrant\ncondition: service_started"]
        BE_SVC["backend\nhealthcheck: GET /health"]
        FE_SVC["frontend\n(no healthcheck)"]

        PG_SVC -->|"condition: service_healthy"| BE_SVC
        QD_SVC -->|"condition: service_started"| BE_SVC
        BE_SVC -->|"condition: service_healthy"| FE_SVC
    end

    subgraph LIFESPAN ["Backend lifespan()  —  runs once at startup"]
        L1["create_tables()\nDDL for all tables  idempotent"]
        L2["seed_data()\ninsert fixture rows if tables are empty"]
        L3["init_checkpointer(postgres_url_plain)\nAsyncPostgresSaver\n↳ fallback: MemorySaver if Postgres down"]
        L4["init_compiled_graph(checkpointer)\nbuild_graph().compile(checkpointer=...)"]
        L5["ensure_collection()\nQdrant  'incidents'  collection\n↳ skipped gracefully if Qdrant down"]
        L6(["App Ready\nGET /health returns 200"])

        L1 --> L2 --> L3 --> L4 --> L5 --> L6
    end
```

---

## 12. Observability — Langfuse Tracing

Tracing is opt-in. If `LANGFUSE_PUBLIC_KEY` is empty, no callbacks are attached and there is zero overhead.

```mermaid
flowchart LR

    subgraph CONF ["Configuration"]
        ENV["LANGFUSE_PUBLIC_KEY set?\n(checked at runtime by _langfuse_configured())"]
    end

    ENV -->|"no  —  empty string"| NONE["get_callbacks() returns []\nget_root_handler() returns None\nno overhead"]

    ENV -->|"yes"| ROOT["get_root_handler(session_id, user_query)\nCallbackHandler  —  top-level trace\ncovers entire chat turn"]

    ROOT --> PER["get_callbacks(session_id, agent_name)\nCallbackHandler  —  per-node\ncreated for each agent invocation"]

    PER --> ATTACH["passed via\nconfig={'callbacks': [handler]}\nto every LangChain chain / agent call"]

    ATTACH --> CAP["Langfuse captures per-span:\n─────────────────────────\nprompt text + completion text\ntoken counts  latency\nmodel name  session_id  agent_name"]
```
