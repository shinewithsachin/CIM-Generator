# CIM Generator

[![CI](https://github.com/shinewithsachin/CIM-Generator/actions/workflows/ci.yml/badge.svg)](https://github.com/shinewithsachin/CIM-Generator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An AI-powered platform that turns a folder of company documents — financials, contracts,
decks, spreadsheets, scanned PDFs — into a complete, professionally formatted Confidential
Information Memorandum (CIM): 10 structured sections, embedded charts, and a
password-protected PDF export, grounded in retrieval over your own uploaded documents.

Try the full workflow with zero setup cost using **Demo Mode** — no API key required (see
[Quickstart](#quickstart)).

## Features

- **Multi-format ingestion** — PDF, DOCX, XLSX, CSV, XML, JSON, TXT, HTML, images (OCR), and URLs
- **Retrieval-augmented generation** — documents are chunked, embedded locally (no API key
  needed for indexing), and retrieved per-section so generated content is grounded in what
  you actually uploaded
- **10-section CIM generation** — executive summary, investment thesis, market overview,
  company overview, products & services, revenue profile, employee profile, customer
  profile, financials, management structure — generate one at a time or all at once, then
  edit any section by hand
- **Chat over your knowledge base** — ask free-form questions about the uploaded documents
- **Pluggable LLM providers** — OpenAI, Anthropic, or Groq, selected per request with
  cost-aware auto-routing; swap providers without touching the pipeline
- **Demo Mode** — an offline, zero-cost provider that returns instantly so the full
  workflow, screenshots, and demos never depend on a live API key or incur API cost
- **Password-protected PDF export** — the output is a confidential memo, so it's encrypted
  with a one-time password shown once in the UI
- **Multi-tenant by construction** — every document, embedding, and generated section is
  scoped to the owning user; enforced at the retrieval-filter level and, in the pgvector
  configuration, at the database row-level security level too
- **Audit trail** — every login, upload, config change, and PDF download is logged and
  viewable by the acting user via the Activity panel

## Architecture

```mermaid
flowchart LR
    U[User / React frontend] -->|JWT| API[FastAPI backend]

    API --> AUTH[(SQLite: users, sessions,\nper-user LLM config, audit log)]
    API --> ENC[encryption.py\nFernet at rest]
    API --> GW[LLM Gateway\nStrategy pattern]
    GW --> OAI[OpenAI]
    GW --> ANT[Anthropic]
    GW --> GRQ[Groq]
    GW --> DEMO[Demo Provider\noffline, zero-cost]

    API --> DP[Document Processor]
    DP --> VS[(Vector store)]
    VS -->|default| CH[(Chroma)]
    VS -->|pgvector mode| PG[(PostgreSQL + pgvector\n+ row-level security)]

    API --> PDF[PDF Generator]
    PDF --> CHART[Chart Generator]
    PDF --> OUT[(Password-protected PDF)]
```

Backend: FastAPI, LangChain/LlamaIndex for orchestration, ChromaDB or pgvector for
retrieval, ReportLab + Matplotlib for PDF/chart output, SQLite for users/sessions/config/audit.
Frontend: React + Vite + Tailwind.

## Security & compliance controls

Built handling confidential financial documents in mind:

| Control | Implementation |
|---|---|
| Authentication | JWT (72h TTL), bcrypt password hashing, account lockout after 5 failed attempts (15 min) |
| Per-user isolation | LLM config, API keys, documents, and generated sections are scoped per user — never a shared global config |
| Encryption at rest | Uploaded documents are Fernet-encrypted on disk; per-user API keys are Fernet-encrypted in the database |
| Encrypted export | Generated CIM PDFs are password-protected (128-bit); the password is shown once, never logged |
| Secrets management | JWT signing key and encryption key are read from environment variables, or auto-generated and persisted locally if unset — never hardcoded |
| Transport control | CORS is restricted to an explicit allowlist (`ALLOWED_ORIGINS`), not wildcarded |
| Input validation | Uploads are validated for file type and size at the API boundary; filenames are sanitized against path traversal |
| Rate limiting | Per-IP limits on auth endpoints, per-user limits on generation/chat endpoints, to bound cost and abuse exposure |
| Data retention | Session deletion removes uploads, the generated PDF, and (in pgvector mode) the tenant's vector rows; `scripts/purge_expired_sessions.py` sweeps anything past `RETENTION_DAYS` on a schedule |
| Audit trail | Login, upload, config change, and PDF download are logged per user and viewable via `GET /api/audit/me` |
| Tenant isolation (pgvector mode) | Enforced both at the query-filter level and via PostgreSQL row-level security (`backend/sql/pgvector_rls.sql`) |

**Deliberately deferred** (documented here rather than half-implemented): full-disk
encryption of the SQLite/Chroma files themselves (e.g. SQLCipher), multi-factor
authentication, and a hosted cloud deployment. The architecture is cloud-portable
(uploads/outputs → S3, Postgres → RDS, FastAPI → ECS/Fargate) but intentionally
runs local-first to avoid cloud cost for this stage of the project.

## Quickstart

```bash
git clone https://github.com/shinewithsachin/CIM-Generator.git
cd CIM-Generator
```

### Option A — Docker Compose

```bash
docker compose up --build
```
API: `http://localhost:8000` — Docs: `http://localhost:8000/docs`

### Option B — Manual

```bash
# Backend (Python 3.12 recommended)
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend, in a second terminal
cd frontend
npm install
npm run dev
```

Then open the frontend, register an account, and in **AI Configuration** pick
**Demo / Offline** — no API key needed. Upload a document, generate all sections, export
the PDF, and download it. Switch to a real provider (OpenAI/Anthropic/Groq) any time for
content grounded in your actual documents instead of placeholder text.

### Environment variables

See `backend/.env.example` for the full list with defaults and explanations — LLM
provider keys, embedding model, vector backend, storage paths, and the security settings
(`JWT_SECRET_KEY`, `APP_ENCRYPTION_KEY`, `ALLOWED_ORIGINS`, `MAX_UPLOAD_MB`,
`RETENTION_DAYS`). Every value has a working default; nothing needs to be set to run in
Demo Mode.

### Switching to pgvector

```
VECTOR_BACKEND=pgvector
POSTGRES_DSN=postgresql://cim:cim@localhost:5432/cim
```
Apply `backend/sql/pgvector_rls.sql` to the target database first.

## Testing & CI

```bash
cd backend
pytest -q
```

Tests run fully offline: LLM calls go through Demo Mode or a stubbed gateway, embeddings
are faked (no model download), and everything runs against isolated temp directories — no
real API keys, no network calls, no shared state with your local dev environment. Coverage
includes auth/session ownership, login lockout, encryption round-trips, per-user config
isolation (the regression test for a real bug found in an earlier audit — LLM config used
to leak across users via a global dict), upload validation, document parsing, standalone
PDF generation, and a full upload-to-PDF pipeline integration test.

`.github/workflows/ci.yml` runs the backend test suite + lint (`ruff`) and a frontend
production build on every push/PR.

## Data retention

Deleting a session removes its uploads, generated PDF, and (in pgvector mode) its vector
rows immediately. `backend/scripts/purge_expired_sessions.py` additionally sweeps sessions
and orphaned chart images older than `RETENTION_DAYS` — schedule it via cron or Windows
Task Scheduler:

```bash
cd backend && python scripts/purge_expired_sessions.py
```

## License

MIT — see [LICENSE](LICENSE).
