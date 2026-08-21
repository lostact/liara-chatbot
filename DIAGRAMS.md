# DIAGRAMS.md — Liara Docs Chatbot

Companion to [`DESIGN.md`](DESIGN.md). All diagrams are Mermaid and render on GitHub.

| # | Diagram | Referenced from |
|---|---|---|
| 1 | System architecture | DESIGN §2 |
| 2 | Ingestion & indexing pipeline | DESIGN §4–§7 |
| 3 | Agent graph (LangGraph) | DESIGN §8 |
| 4 | Retrieval & answer sequence | DESIGN §7, §13 |
| 5 | Data model (ER) | DESIGN §6 |
| 6 | Production deployment on Liara | DESIGN §21 |
| 7 | Local Docker Compose topology | DESIGN §20 |
| 8 | Blue/green revision switch | DESIGN §2.2, §4.4 |
| 9 | Degradation / failure paths | DESIGN §17 |
| 10 | Widget state machine | DESIGN §14 |

---

## 1. System architecture

```mermaid
flowchart LR
  subgraph Browser["Host website (docs / landing / console)"]
    W["Widget<br/>&lt;script&gt; · Shadow DOM · SSE"]
  end

  subgraph Liara["Liara platform"]
    subgraph Public["Public route"]
      CA["chat-api<br/>FastAPI + LangGraph<br/>1–3 instances"]
    end
    subgraph Private["Private network"]
      IX["indexer<br/>FastAPI + arq worker + arq cron<br/>1 instance"]
      PG[("PostgreSQL 16<br/>pgvector · pg_trgm<br/>docs · chunks · vectors<br/>conversations · state")]
      RD[("Redis<br/>cache · rate limits<br/>queue · budgets")]
      OS[("Object Storage<br/>snapshots · eval artifacts")]
    end
    CDN["CDN /widget/v1/*"]
  end

  subgraph Ext["External"]
    OR["OpenRouter<br/>chat + embeddings"]
    GH["GitHub<br/>liara-cloud/docs"]
    OBS["Langfuse · Sentry · Grafana"]
  end

  W -->|"HTTPS + site key<br/>SSE"| CA
  W -.->|"bundle"| CDN
  CA -->|"POST /internal/search<br/>X-Internal-Token"| IX
  CA --> PG
  CA --> RD
  CA --> OR
  CA --> OBS
  IX --> PG
  IX --> RD
  IX --> OR
  IX --> OS
  IX -->|"git fetch (cron poll)"| GH
  IX --> OBS
```

---

## 2. Ingestion & indexing pipeline

```mermaid
flowchart TD
  T1["Trigger: cron */30m repo poll"] --> Q
  T2["Trigger: manual POST /admin/sync"] --> Q
  Q{{"arq queue (Redis)"}} --> DISC

  DISC["Discover<br/>git diff sha..HEAD"] --> FETCH
  FETCH["Fetch<br/>MDX from repo clone"] --> HASH

  HASH{"sha256(normalized)<br/>== current revision?"}
  HASH -->|yes| SKIP["Skip page<br/>update last_seen_at<br/>(zero LLM cost)"]
  HASH -->|no| EXTRACT

  EXTRACT["Extract<br/>frontmatter · strip JSX (keep whitelisted components)<br/>preserve code fences"] --> CLEAN
  CLEAN["Clean & normalize<br/>NFC · fa char folding · ZWNJ · absolute links · anchors"] --> MAP
  MAP{"repo path → public URL<br/>deterministic mapping"}
  MAP -->|mismatch| ISSUE["url_mapping_issues + alert<br/>(never guess a citation URL)"]
  MAP -->|ok| DEDUP

  DEDUP["Dedupe<br/>1 exact page hash<br/>2 SimHash ≤3 → alias_of<br/>3 chunk hash → chunk_occurrences"] --> REV
  REV["New document_revision<br/>(immutable, git_sha, doc_version)"] --> CHUNK
  CHUNK["Chunk<br/>H2/H3-aware · ~450 tok · 80 overlap<br/>code fences intact · contextual header"] --> ECACHE

  ECACHE{"text_hash in<br/>embedding_cache?"}
  ECACHE -->|hit| WRITE
  ECACHE -->|miss| EMBED["Embed via OpenRouter<br/>batches of 96 · retry/backoff · budget check"] --> WRITE

  WRITE["Insert chunks + vectors<br/>(new revision, not yet live)"] --> SWITCH
  SWITCH["Atomic switch<br/>documents.current_revision_id"] --> POST
  POST["Post-steps<br/>invalidate answer cache for changed docs<br/>warm top-200 cache · sync_runs metrics"]
```

---

## 3. Agent graph (LangGraph)

```mermaid
stateDiagram-v2
  [*] --> guard
  guard --> blocked: abuse / injection / over-limit
  blocked --> [*]
  guard --> cache_check

  cache_check --> stream_cached: exact or semantic hit (fresh)
  stream_cached --> [*]
  cache_check --> shortcut: greeting / off-topic / product index
  shortcut --> finalize
  cache_check --> hydrate: normal

  hydrate --> route: last 8 msgs + summary + profile + page context

  route --> clarify: action = clarify
  route --> answer_from_context: prior context sufficient
  route --> retrieve: action = search
  route --> plan: action = multi_step
  route --> refuse: out of scope

  clarify --> finalize
  refuse --> finalize
  answer_from_context --> synthesize

  plan --> retrieve: per step (max 4)
  retrieve --> grade
  grade --> expand: insufficient and loops < 2
  expand --> retrieve
  grade --> synthesize: sufficient
  grade --> refuse: insufficient / out of scope

  synthesize --> verify
  verify --> repair: unsupported claim / bad citation
  repair --> verify: once
  verify --> hedge: still unsupported
  hedge --> finalize
  verify --> finalize: ok

  finalize --> [*]

  note right of route
    cheap model, structured output
    budget: MAX_TOOL_CALLS=6
    MAX_TOKENS_PER_TURN=12000
  end note
  note right of synthesize
    strong model, temperature 0.1
    numbered context blocks only
  end note
```

---

## 4. Retrieval & answer sequence

```mermaid
sequenceDiagram
  autonumber
  participant U as User (widget)
  participant C as chat-api
  participant R as Redis
  participant I as indexer
  participant P as Postgres
  participant O as OpenRouter

  U->>C: POST /v1/chat (SSE, site key, page context)
  C->>C: guard · rate limit · PII scrub
  C->>R: answer cache lookup (exact → semantic)
  alt cache hit
    C-->>U: event: token* (replay) + citations + done
  else miss
    C->>P: load history + summary + profile
    C-->>U: event: status {stage:"thinking"}
    C->>O: route (cheap, structured)
    O-->>C: {action:"search", queries[3], service_tags[]}
    C-->>U: event: status {stage:"searching"}
    C->>I: POST /internal/search (queries, filters)
    I->>R: query-expansion / result cache
    I->>P: HNSW dense top40 × queries
    I->>P: tsvector + trgm lexical top40
    I->>I: RRF fuse → top20
    I->>P: neighbour chunk expansion
    I-->>C: top 6–8 results (url#anchor, heading_path, text, score)
    C->>O: grade sufficiency (cheap)
    opt insufficient (≤2 loops)
      C->>I: expand / re-search with missing terms
    end
    C-->>U: event: status {stage:"reading", sources:N}
    C->>O: synthesize (strong, streamed, ≤6000 tok context)
    O-->>C: token stream
    C-->>U: event: token* (streamed)
    C->>O: verify (cheap, extractive + attribution)
    C-->>U: event: citations / actions / done {confidence, cost}
    C->>P: persist message, tokens, cost, trace_id
    C->>R: store answer in cache (24h, doc-keyed invalidation)
  end
```

---

## 5. Data model (ER)

```mermaid
erDiagram
  DOCUMENTS ||--o{ DOCUMENT_REVISIONS : "has"
  DOCUMENTS ||--o| DOCUMENTS : "alias_of"
  DOCUMENT_REVISIONS ||--o{ CHUNKS : "contains"
  DOCUMENTS ||--o{ CHUNK_OCCURRENCES : "reuses"
  CHUNKS ||--o{ CHUNK_OCCURRENCES : "appears_in"
  CONVERSATIONS ||--o{ MESSAGES : "has"
  MESSAGES ||--o{ FEEDBACK : "rated_by"
  CONVERSATIONS ||--o{ QUERY_LOG : "logs"

  DOCUMENTS {
    bigint id PK
    text url UK
    text repo_path
    text title
    text_array nav_path
    text service_tag
    text lang
    text source "repo|web"
    bigint alias_of FK
    bigint current_revision_id
    bigint simhash
    text status
    timestamptz last_seen_at
  }
  DOCUMENT_REVISIONS {
    bigint id PK
    bigint document_id FK
    text content_hash
    text markdown
    jsonb frontmatter
    text git_sha
    text doc_version
    timestamptz indexed_at
  }
  CHUNKS {
    bigint id PK
    bigint revision_id FK
    bigint document_id FK
    int ordinal
    text anchor
    text_array heading_path
    text text
    text embed_text
    text text_hash
    int token_count
    bool has_code
    text lang
    text service_tag
    vector embedding "1024"
    tsvector tsv
  }
  CHUNK_OCCURRENCES {
    bigint chunk_id PK
    bigint document_id PK
    text anchor
  }
  EMBEDDING_CACHE {
    text text_hash PK
    text model
    vector embedding
  }
  SYNC_RUNS {
    bigint id PK
    text trigger
    text status
    text from_git_sha
    text to_git_sha
    int pages_changed
    int embed_tokens
    numeric cost_usd
  }
  CONVERSATIONS {
    uuid id PK
    text site_key
    text visitor_hash
    text lang
    jsonb profile
    text summary
    int token_spend
  }
  MESSAGES {
    bigint id PK
    uuid conversation_id FK
    int seq
    text role
    text content
    jsonb citations
    text route
    numeric confidence
    text model
    int prompt_tokens
    int completion_tokens
    numeric cost_usd
    text trace_id
  }
  FEEDBACK {
    bigint id PK
    bigint message_id FK
    smallint rating
    text reason
  }
  QUERY_LOG {
    bigint id PK
    text query_norm
    text lang
    text route
    real top_score
    bool answered
  }
```

---

## 6. Production deployment on Liara

```mermaid
flowchart TB
  subgraph CI["GitHub Actions"]
    L["lint · mypy · unit + integration tests"] --> S["pip-audit · npm audit · Trivy · SBOM"]
    S --> B["build images · build widget (size budget)"]
    B --> E["golden-set eval gate on staging"]
    E --> M["alembic upgrade head (release step)"]
    M --> D1["liara deploy indexer"] --> D2["liara deploy chat-api"] --> SM["smoke: /healthz · search · chat"]
    SM -->|fail| RB["liara rollback + index_generation rollback"]
  end

  subgraph PROD["Liara — production"]
    LB["Liara load balancer<br/>chat.liara.ir · HTTPS/HSTS"]
    A1["liarabot-chat #1"]
    A2["liarabot-chat #2..3 (autoscale)"]
    IXP["liarabot-indexer ×1<br/>web + worker + cron<br/>no public route except /hooks/github"]
    PGM[("Managed PostgreSQL + pgvector<br/>daily backup · PITR · private only")]
    RDM[("Managed Redis<br/>allkeys-lru")]
    OSM[("Object Storage")]
    CDNP["CDN → /widget/v1/*"]
  end

  D2 --> LB
  LB --> A1
  LB --> A2
  A1 --> PGM
  A2 --> PGM
  A1 --> RDM
  A2 --> RDM
  A1 -->|private HTTP| IXP
  A2 -->|private HTTP| IXP
  IXP --> PGM
  IXP --> RDM
  IXP --> OSM
  LB --> CDNP

  subgraph STG["Liara — staging (same images)"]
    SA["liarabot-chat-staging"]
    SI["liarabot-indexer-staging"]
  end
  E --> SA
```

---

## 7. Local Docker Compose topology

```mermaid
flowchart LR
  DEV["Developer<br/>make dev / make seed / make eval"]
  subgraph compose["docker-compose"]
    DB[("db<br/>pgvector/pgvector:pg16<br/>:5432")]
    RS[("redis:7-alpine<br/>:6379")]
    IXD["indexer (dev target)<br/>honcho: web+worker+cron<br/>:8001 · hot reload"]
    CAD["chat-api (dev target)<br/>uvicorn --reload · :8000"]
    WD["widget-dev<br/>vite :5173 + demo.html"]
  end
  FAKE["EMBEDDINGS_PROVIDER=fake<br/>+ VCR cassettes → offline, deterministic"]

  DEV --> WD --> CAD --> IXD
  CAD --> DB
  CAD --> RS
  IXD --> DB
  IXD --> RS
  IXD -.-> FAKE
  CAD -.-> FAKE
  IXD -.->|"make sync-real"| GH["GitHub + docs.liara.ir"]
```

---

## 8. Blue/green revision switch (indexing never breaks reads)

```mermaid
gantt
  title Per-document blue/green write (readers always consistent)
  dateFormat  HH:mm
  axisFormat  %H:%M
  section Readers
  Serve revision N (current_revision_id = N)      :done, r1, 00:00, 12min
  Serve revision N+1                              :active, r2, 00:12, 8min
  section Writer (indexer)
  Extract · clean · chunk                          :w1, 00:02, 4min
  Embed (cache-gated, throttled)                   :w2, 00:06, 5min
  Insert chunks+vectors for revision N+1 (invisible):w3, 00:11, 1min
  Atomic UPDATE current_revision_id → N+1          :milestone, w4, 00:12, 0min
  Invalidate answer cache · warm top-200           :w5, 00:12, 3min
  Prune revision N-3 (after 90 days)               :w6, 00:15, 2min
```

Rollback = one `UPDATE documents SET current_revision_id = N`. A corpus-wide change (new chunker or embedding model) uses the same idea one level up, via `index_generation`.

---

## 9. Degradation & failure paths

```mermaid
flowchart TD
  REQ["User turn"] --> RL{"rate limit / budget ok?"}
  RL -->|no| R429["429 + Retry-After<br/>widget shows countdown"]
  RL -->|yes| SR{"indexer /search healthy?<br/>(circuit breaker)"}

  SR -->|open/timeout| RC{"retrieval cache hit?"}
  RC -->|yes| SYN
  RC -->|no| MSG1["'Search temporarily unavailable'<br/>+ ticket link (chat stays up)"]
  SR -->|ok| SYN{"OpenRouter synthesis"}

  SYN -->|5xx / timeout| RETRY["2 retries with jitter"] --> ALT{"fallback model in chain"}
  ALT -->|ok| VER
  ALT -->|all fail| MSG2["explicit error event<br/>+ ticket link (never a silent empty reply)"]
  SYN -->|ok| VER{"verify passes?"}

  VER -->|no| REP["1 repair pass"] --> VER2{"passes?"}
  VER2 -->|no| HEDGE["hedged low-confidence answer<br/>what we found + what is uncertain + support"]
  VER2 -->|yes| OK
  VER -->|yes| OK["cited answer + confidence + next steps"]

  subgraph infra["Infrastructure degradation"]
    PGX["Postgres down"] --> PGD["stateless single-turn mode<br/>history endpoints 503<br/>indexer paused"]
    RDX["Redis down"] --> RDD["in-process rate limits (lower cap)<br/>caches bypassed · queue paused"]
    WSX["Web search down"] --> WSD["skip fallback, state docs did not cover it"]
    JOBX["Poison-pill job"] --> JOBD["3 attempts → dead-letter + alert"]
  end
```

---

## 10. Widget state machine

```mermaid
stateDiagram-v2
  [*] --> Boot: script defer loads, no panel mounted
  Boot --> Idle: GET /v1/config (theme, locale, features, turnstile)
  Idle --> Open: launcher click / LiaraChat.open() / ?liarachat=1
  Open --> Restored: sessionStorage conversation_id found
  Open --> Fresh: no session → greeting + page-aware suggestion chips
  Fresh --> Composing
  Restored --> Composing
  Composing --> Streaming: submit (Enter) → SSE open
  Streaming --> Streaming: token / status events (stage indicator, caret)
  Streaming --> Answered: done event (citations, actions, confidence)
  Streaming --> Stopped: user presses Stop → abort SSE + server run
  Streaming --> Retry: network error / heartbeat timeout
  Retry --> Streaming: backoff retry
  Retry --> Fallback: streaming blocked → POST /v1/chat/sync
  Fallback --> Answered
  Streaming --> Limited: 429 → countdown message
  Limited --> Composing
  Answered --> Composing: follow-up / suggestion chip
  Answered --> Feedback: 👍 / 👎 (👎 → reason picker + ticket link)
  Feedback --> Composing
  Answered --> Clarifying: assistant asked a question
  Clarifying --> Streaming: user taps a choice button
  Composing --> Minimized: close (state kept in sessionStorage)
  Minimized --> Open: unread badge click
  Answered --> Reset: "new chat" → clears conversation_id
  Reset --> Fresh
```
