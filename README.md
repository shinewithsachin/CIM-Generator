CIM Generation Engine (Fresher-Friendly Product-Style Build)

Overview
- This project generates Confidential Information Memorandum sections from uploaded company documents.
- The codebase is intentionally scoped for fresher interview readiness: strong backend patterns, local reproducibility, and clear architecture without expensive cloud deployment.

Current Tech Stack
- Backend: FastAPI
- LLM Orchestration: LangChain, LlamaIndex
- LLM Providers: OpenAI, Anthropic, Groq (Llama)
- Embeddings: HuggingFaceEmbeddings (default BAAI/bge-m3)
- Vector DB: Chroma (default) or PostgreSQL pgvector
- Metadata/Auth Store: SQLite (lightweight local default)
- Cache-ready runtime dependency: Redis (via Docker Compose)

Architecture Highlights
- Strategy pattern for dynamic LLM routing.
- Runtime provider selection endpoint for cost-aware provider switching.
- Multi-tenant isolation using tenant_id propagation, query filters, and PostgreSQL RLS policy.
- Resilience patterns on external LLM calls: exponential backoff retries and circuit breaker.

Architecture Diagram
```mermaid
flowchart LR
   U[User / Frontend] --> API[FastAPI Backend]
   API --> GW[LLM Gateway Strategy]
   GW --> OAI[OpenAI]
   GW --> ANT[Anthropic]
   GW --> GRQ[Groq Llama]

   API --> DP[Document Processor]
   DP --> VS[(Vector Store)]
   VS -->|default| CH[(Chroma)]
   VS -->|production-mode| PG[(PostgreSQL + pgvector)]

   API --> AUTH[(SQLite Auth + Session Ownership)]
   API --> PDF[PDF Generator]
   PDF --> OUT[(Local Outputs)]

   API -. tenant_id .-> PG
```

Run Locally (Docker Compose)
1. Install Docker Desktop.
2. From repository root, run:
   docker compose up --build
3. API becomes available at:
   http://localhost:8000
4. API docs:
   http://localhost:8000/docs

Notes
- Docker setup uses Python 3.12 for package compatibility.
- If running outside Docker, prefer Python 3.11/3.12 instead of 3.14.

Run Locally (without Docker)
1. Backend:
   - cd backend
   - python -m venv .venv
   - .venv\\Scripts\\activate  (Windows)
   - pip install -r requirements.txt
   - uvicorn main:app --reload --port 8000
2. Frontend:
   - cd frontend
   - npm install
   - npm run dev

Switch to pgvector
- Set configuration values:
  - vector_backend = pgvector
  - postgres_dsn = postgresql://cim:cim@localhost:5432/cim
- Apply SQL policy/schema from:
  - backend/sql/pgvector_rls.sql

AWS Design-Ready (Not Deployed)
- Current implementation is local-first by design to avoid cloud costs.
- Migration path is documented and straightforward:
  - Local uploads/outputs -> Amazon S3
  - Local/Compose PostgreSQL -> Amazon RDS PostgreSQL with pgvector
  - Local FastAPI container -> ECS/Fargate or Lambda + API Gateway
- Core app logic remains portable because infrastructure concerns are configuration-driven.

Tests
- Basic tests are in backend/tests.
- Run:
  - cd backend
  - pytest -q

What to say in interviews
- Built a multi-tenant CIM engine with FastAPI, pgvector, and pluggable LLM provider strategy.
- Enforced tenant isolation with request-level tenant context, filtered retrieval, and DB-level RLS policy.
- Added resilience with exponential backoff and circuit breaker for handling provider rate limits and downtime.
- Kept architecture cloud-portable while shipping a practical local-first implementation.
