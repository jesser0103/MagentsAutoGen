# MagentAutoGen — Automated Cloud Code Generation with Human Oversight

> **v1.0 — Complete** · Full-stack AI pipeline: Azure OpenAI · FastAPI · Next.js · Docker sandbox · RAG · FinOps · GitHub PR export · CI/CD

A secure, human-governed multi-agent system that accepts a plain-language cloud automation request and produces security-reviewed, policy-compliant **Python** and **Terraform** artifacts — powered by **Azure OpenAI**, **Microsoft Agent Framework**, and a **Next.js** control-plane dashboard.

No code reaches a human-readable output without passing prompt injection screening, plan approval, multi-tool static analysis, an evidence-based reviewer, and a locked-down Docker sandbox.

---

## Table of contents

1. [Workflow](#workflow)
2. [Architecture](#architecture)
3. [Features](#-features)
   - [1 · Multi-agent orchestration](#1--multi-agent-orchestration)
   - [2 · Security pipeline](#2--security-pipeline-fail-closed)
   - [3 · Policy RAG](#3--policy-rag)
   - [4 · FastAPI backend & SSE](#4--fastapi-backend--sse-event-stream)
   - [5 · Next.js dashboard](#5--nextjs-control-plane-dashboard)
   - [6 · GitHub PR export](#6--github-pull-request-export)
   - [7 · Authentication & multi-user](#7--authentication--multi-user)
   - [8 · Storage & persistence](#8--storage--persistence)
   - [9 · Observability & reliability](#9--observability--reliability)
   - [10 · FinOps & cost tracking](#10--finops--cost-tracking)
   - [11 · Infrastructure & CI/CD](#11--infrastructure--cicd)
4. [Azure live acceptance](#-azure-live-acceptance)
5. [Environment variables](#environment-variables)
6. [Quick start](#quick-start)
7. [Project structure](#project-structure)
8. [Safety guarantees](#safety-guarantees)
9. [Required Azure resources](#required-azure-resources)
10. [Documentation](#documentation)
11. [Tech stack](#tech-stack)

---

## Workflow

```mermaid
flowchart LR
    subgraph INPUT["🔐  Input & Screening"]
        A(["👤 Operator\nsubmits request"])
        B{{"🛡️ Azure AI Content Safety\nPrompt Shields"}}
        BLOCK(["🚫 Request Blocked\nno agent receives it"])
        A --> B
        B -->|Injection detected| BLOCK
    end

    subgraph PLAN["📋  Planning & Approval"]
        C["📋 Planner Agent\nStructured plan · open questions\nstep type · assumptions"]
        D{"Unresolved\nquestions?"}
        E(["⏸️ Human Approval Checkpoint\npersisted · survives restart"])
        C --> D
        D -->|Yes| C
        D -->|No| E
    end

    subgraph GEN["⚙️  Code Generation"]
        F["📚 RAG Policy Retrieval\nChromaDB · relevance threshold\nAzure OpenAI embeddings"]
        G["⚙️ Coder Agent\nPython / Terraform artifact\ngovernance tags injected"]
        F --> G
    end

    subgraph SEC["🔍  Security Review"]
        H["🔍 Static Analysis\ntfsec · Checkov · Bandit\nTag governance engine"]
        I["🤖 Reviewer Agent\nevidence-based verdict"]
        K{"Round ≤ 5?"}
        ESC(["⚠️ needs_manual_intervention"])
        H --> I
        I -->|REJECT| K
        K -->|Yes → revise| G
        K -->|No| ESC
    end

    subgraph VAL["🐳  Validation & Delivery"]
        J["🐳 Docker Sandbox\nno network · read-only FS\nno terraform apply"]
        DONE(["✅ Artifact Delivered\nFinOps summary · audit trail\nSSE event stream"])
        J -->|Failed| I
        J -->|Passed| DONE
    end

    B -->|Safe| C
    E -->|Reject + feedback| C
    E -->|Approve| F
    G --> H
    I -->|APPROVE| J

    style BLOCK fill:#c0392b,color:#fff,stroke:none
    style ESC   fill:#e67e22,color:#fff,stroke:none
    style DONE  fill:#27ae60,color:#fff,stroke:none
    style E     fill:#2980b9,color:#fff,stroke:none
    style INPUT fill:#0d1117,stroke:#30363d,color:#e6edf3
    style PLAN  fill:#0d1117,stroke:#30363d,color:#e6edf3
    style GEN   fill:#0d1117,stroke:#30363d,color:#e6edf3
    style SEC   fill:#0d1117,stroke:#30363d,color:#e6edf3
    style VAL   fill:#0d1117,stroke:#30363d,color:#e6edf3
```

> **Nothing runs on the host machine. Generated code never executes before a human approves the plan.**

---

## Architecture

| Layer | Technology | Port |
|-------|-----------|------|
| Frontend dashboard | Next.js 14 — React / TypeScript / Tailwind CSS | `3000` |
| Backend API + SSE | FastAPI + Uvicorn | `8000` |
| Auth & user database | Postgres 16 (Better Auth) | `5432` |
| Validation sandbox worker | Locked-down Python / Terraform container | Internal `8081` |
| Agent orchestration | Microsoft Agent Framework — typed FSM | — |
| Policy vector store | ChromaDB (on-disk) + Azure OpenAI embeddings | — |
| Containers | Docker Compose (5-service stack) | — |

---

## ✅ Features

### 1 · Multi-agent orchestration

The workflow is a **typed finite-state machine** implemented with Microsoft Agent Framework — not an open-ended chat loop. Every state transition is gated, logged, and persisted.

| Agent | Role | Key behaviour |
|-------|------|--------------|
| **Planner** | Decomposes the request | Produces a structured plan with step type (Python/Terraform), assumptions, open questions. Blocks if required questions are unresolved. |
| **Coder** | Generates the artifact | Consumes approved plan + retrieved policy rules. Injects mandatory governance tags on every Azure resource. Never self-executes. |
| **Reviewer** | Evidence-based verdict | Reads real scanner findings. Issues `APPROVE` or `REJECT` with a required-changes list. Hard cap of 5 rounds before escalation to `needs_manual_intervention`. |
| **FinOps Agent** | Cost accounting | Captures `prompt_tokens` + `completion_tokens` after every model call. Calculates per-agent cost estimates from external price tables. Never hardcodes prices. |
| **Security Agent** | Finding normalisation | Aggregates and normalises findings from all static-analysis tools into a common `SecurityFinding` model: tool, rule ID, severity, location, evidence, remediation. |

**Human approval gate:** the Coder FSM state is unreachable until the operator explicitly approves the plan. The approval is file-persisted — a backend restart does not lose the paused state.

**Self-healing loop:** when the Reviewer rejects, the Coder receives the required-changes list and re-generates. The `SelfHealingPanel` in the dashboard visualises the current round, the delta between versions, and the escalation threshold.

---

### 2 · Security pipeline (fail-closed)

Every security control is **fail-closed**: an outage or missing binary is a blocking failure, not a pass.

| Control | What it catches |
|---------|----------------|
| **Azure AI Content Safety — Prompt Shields** | Direct and indirect prompt injection in the operator's input. Blocks before any agent sees the request. Unreachable service = request blocked. |
| **tfsec** | Terraform HCL: public SSH ports, public storage buckets, missing encryption, over-broad RBAC, unencrypted secrets. |
| **Checkov** | Second-pass Terraform + Python policy check. CRITICAL and HIGH findings are blocking; Reviewer cannot issue APPROVE until they are resolved. |
| **Bandit** | Python AST analysis: shell injection, hardcoded credentials, unsafe `pickle`, `subprocess` with `shell=True`. |
| **Tag governance engine** | Post-generation check that every `azurerm_*` resource block carries `environment`, `owner`, and `cost_center` tags. Missing tags → CRITICAL finding. |
| **Local policy fallback** | `local_policy.py` provides rule-based injection detection when Content Safety is unavailable — maintains fail-closed behaviour locally. |
| **Docker validation sandbox** | Generated artifact executes in a locked-down Linux container: no network egress, read-only root filesystem, CPU/memory/PID limits, no Docker socket mounted. `terraform apply` is explicitly blocked. |

---

### 3 · Policy RAG

Corporate policy documents (Terraform standards, cloud security baselines, compliance rules, FinOps tagging requirements) are ingested, embedded, and used to ground Coder output.

- **Storage:** ChromaDB persistent collection at `data/chroma/`. Each chunk carries `rule_id`, `source_file`, `source_hash` (SHA-256), and `ingested_at` metadata.
- **Incremental ingestion:** re-running the ingestion CLI after editing a policy file updates only changed chunks (detected by SHA-256 diff). A manifest JSON records the full ingestion history.
- **Relevance gate:** the Coder retrieves only rules whose cosine similarity score exceeds `MAGENT_RAG_RELEVANCE_THRESHOLD`. Weak matches are never injected into the prompt.
- **Local / Azure dual mode:** works locally with `sentence-transformers` (no Azure credential required); switches to Azure OpenAI `text-embedding-3-small` when `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` is set.
- **Context bounding:** conversation history is summarised before it hits `MAGENT_MAX_CONTEXT_TOKENS`. Omitted content is recorded in the structured conversation audit log.
- **Ingestion CLI:**
  ```bash
  python -m src.rag.ingest <file> --output data/chroma/policy_manifest.json
  ```

---

### 4 · FastAPI backend + SSE event stream

#### REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/runs` | Submit a new automation request |
| `GET` | `/api/runs/{id}` | Get full run state |
| `POST` | `/api/runs/{id}/approve` | Approve the Planner's plan |
| `POST` | `/api/runs/{id}/reject` | Reject the plan with feedback |
| `GET` | `/api/runs/{id}/artifact` | Download the generated artifact |
| `GET` | `/api/runs/{id}/events/stream` | SSE stream of all workflow events |
| `POST` | `/api/runs/{id}/export-pr` | Export artifact as a GitHub Pull Request |

#### Server-Sent Events

Every workflow stage emits a typed event: `screening`, `planning`, `awaiting_approval`, `policy_retrieval`, `coding`, `scanning`, `reviewing`, `sandbox`, `cost_summary`, `completed`, `failed`, `escalated`. Each event carries: schema version, timestamp, run ID, component name, stage, severity, and a secrets-redacted payload.

#### Reliability

- **File-backed run store:** `WorkflowRun` state is serialised to JSON on every transition under `data/checkpoints/`. A full API restart does not lose paused runs.
- **Retry + error envelopes:** bounded exponential backoff for Azure OpenAI, ChromaDB, scanner subprocesses, and Docker calls. Every error is wrapped in a typed `ErrorEnvelope` (source, message, retryable flag, timestamp).
- **Structured JSON logs:** OpenTelemetry-compatible fields on every log record. Secrets (API keys, tokens, endpoints) are stripped at the log layer by `src/utils/redaction.py` before any handler sees the record.

---

### 5 · Next.js control-plane dashboard

All dashboard state is driven by the FastAPI SSE event stream and the persisted run state — there is no client-side polling state machine.

| Component | Description |
|-----------|-------------|
| **`RequestForm`** | Mission input with template picker (`TemplatePanel`) and example request library |
| **`TemplatePanel`** | Pre-built request templates for common cloud automation tasks (storage account, VNet, AKS, Function App) |
| **`AgentGraph`** | React Flow graph of the full workflow — active node highlighted, paused state visualised, terminal states colour-coded |
| **`StageProgress`** | Linear stage progress bar showing the current FSM state across the 7 pipeline stages |
| **`TerminalConsole`** | SSE-driven event terminal with timestamp, component label, and severity colouring |
| **`PlanEditor`** | Structured plan view with approve / reject radio and feedback text area |
| **`SelfHealingPanel`** | Tracks the Coder ↔ Reviewer revision loop: current round, diff of changes, escalation threshold indicator |
| **`CodeViewer`** | Syntax-highlighted artifact with diff view, copy, download, and Export to PR buttons |
| **`ScanDashboard`** | Per-tool finding list with severity badges (CRITICAL / HIGH / MEDIUM / LOW), block/pass summary, and remediation hints |
| **`AgentInspector`** | Drill-in panel for any graph node: agent input, output, token count, duration, and cost |
| **`FinOpsCharts`** | Per-agent and per-stage token count charts, session cost estimate, and billing disclaimer |
| **`KPIMetrics`** | Top-level KPI bar: total runs, pass rate, average cost, average duration |
| **`DashboardOverview`** | Summary landing page combining KPIs, recent run list, and system health indicators |
| **`TabbedDashboard`** | Tab container that orchestrates all live-run panels (graph, terminal, plan, code, scans, FinOps) |
| **`RunHistory`** | Searchable, paginated list of all completed and paused runs — click any to reload full state |
| **`RedTeamPanel`** | Built-in prompt injection test fixtures; submit and verify the block without leaving the dashboard |
| **`UserManagement`** | Admin panel for listing users, changing roles (`admin` / `operator`), and revoking sessions |

---

### 6 · GitHub Pull Request export

When a run completes, the **Export to PR** button in `CodeViewer` calls `src/integrations/github_exporter.py`, which:

1. Creates a new branch in `GITHUB_REPO` named `magent/<run-id>`
2. Commits the generated Python or Terraform artifact to that branch
3. Opens a **draft Pull Request** whose description includes: run ID, plan summary, scanner finding counts by severity, and the FinOps cost estimate
4. Returns the PR URL — the dashboard renders it as a direct link

**Requirements:** `GITHUB_TOKEN` (PAT with `repo` scope) and `GITHUB_REPO` (`owner/repository`) in `.env`.

---

### 7 · Authentication & multi-user

- **Better Auth** running against Postgres 16 — production-grade library handling session lifecycle, token rotation, and credential hashing.
- **Session model:** server-side sessions in Postgres; browser holds a signed, `HttpOnly`, `SameSite=Strict` cookie. No JWTs client-side.
- **CSRF protection:** double-submit cookie pattern on all mutating endpoints.
- **Register / Login:** `/register` and `/login` Next.js pages with server-side credential validation.
- **Bootstrap admin:** on first Compose start, a seed job reads `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` and creates the first admin — no manual DB access needed.
- **Role-based access:** `admin` vs `operator` roles stored in Postgres, checked in Next.js middleware (frontend) and FastAPI dependency (backend).
- **Optional social login:** GitHub OAuth and Microsoft/Entra OAuth — enabled by setting `GITHUB_CLIENT_ID` / `MICROSOFT_CLIENT_ID` in `.env`.
- **Protected routes:** `/agents`, `/runs`, `/finops`, `/security`, `/admin` all require an active session; unauthenticated requests redirect to `/login`.

---

### 8 · Storage & persistence

The system uses three purpose-built storage layers with no cross-contamination:

| Layer | Technology | Data |
|-------|-----------|------|
| **Auth & users** | Postgres 16 | Accounts, sessions, roles, CSRF tokens, OAuth tokens |
| **Workflow state** | File-backed JSON | `WorkflowRun`: FSM state, plan, artifact, scan results, approval, event log, cost records |
| **Conversation audit** | File-backed JSONL | Per-run structured conversation log with redacted agent messages |
| **Policy vectors** | ChromaDB (on-disk) | Document chunk embeddings, SHA-256 hashes, ingestion manifest |

**Run checkpoint detail:**
- State is written to `data/checkpoints/<run-id>.json` on every FSM transition.
- A run paused at the approval gate survives a full API restart — operator refreshes and continues.
- Audit log includes full event history with secrets stripped.

**Conversation log detail:**
- `src/utils/conversation_logger.py` writes a JSONL file per run to `data/conversations/`.
- Each line records: timestamp, agent role, token counts, and the redacted message content.
- `src/utils/run_logger.py` tracks structured per-run metadata (start time, end state, cost total, artifact hash).

---

### 9 · Observability & reliability

#### Logging

- `src/utils/structured_logging.py` installs a JSON log handler on the root logger with OpenTelemetry-compatible fields: `trace_id`, `span_id`, `service.name`, `timestamp`, `level`, `component`.
- `src/utils/redaction.py` runs before any handler receives a record. It strips API keys, bearer tokens, connection strings, and endpoint URLs using a configurable pattern list.
- `src/utils/audit_log.py` writes an append-only audit log to `data/audit/` — separate from application logs — recording operator actions (submit, approve, reject, export).

#### Telemetry

- `src/utils/telemetry.py` configures an OpenTelemetry tracer and meter. When `OTEL_EXPORTER_OTLP_ENDPOINT` is set, traces and metrics are exported to the configured collector.
- `OTEL_SERVICE_NAME` labels all telemetry as `magent-autogen` by default.

#### Retry

- `src/utils/retry.py` provides two bounded exponential-backoff decorators:
  - `@llm_retry` — wraps Azure OpenAI calls (configurable attempts, base delay, cap).
  - `@adapter_retry` — wraps scanner subprocesses, Docker calls, and ChromaDB operations.
- All retry parameters are environment variables — no hardcoded values.

#### Health check

```bash
python -m src.healthcheck           # Config validation only — no network call
python -m src.healthcheck --local   # Validates local tools (tfsec, checkov, bandit, docker)
python -m src.healthcheck --live    # Minimal live Azure OpenAI request
```

---

### 10 · FinOps & cost tracking

- `src/utils/cost_tracker.py` captures `prompt_tokens` and `completion_tokens` from every Azure OpenAI response object.
- Prices are loaded from `config/pricing.json` at startup — never hardcoded. The file supports per-model input, output, and embedding rates.
- The `FinOpsCharts` dashboard component shows: per-agent token breakdown, per-stage cost, session total, and an estimate disclaimer (*"Estimates only. See Azure Cost Management for actual billing."*).
- `KPIMetrics` shows the session cost alongside run count, pass rate, and duration.
- The GitHub PR export includes the session FinOps estimate in the PR description body.

---

### 11 · Infrastructure & CI/CD

#### Docker Compose stack

| Service | Image | Role |
|---------|-------|------|
| `api` | `docker/Dockerfile.api` | FastAPI backend |
| `frontend` | `frontend/Dockerfile` | Next.js dashboard |
| `postgres` | `postgres:16-alpine` | Auth + user database |
| `sandbox` | `docker/Dockerfile.sandbox` | Isolated validation worker |
| `bootstrap` | (seed job) | Creates first admin on first start |

Services communicate over a private Docker bridge network. The sandbox has no internet egress and no access to the Docker socket.

#### GitHub Actions CI

On every push and pull request:

| Step | Tool | What it checks |
|------|------|---------------|
| Lint | `ruff` | Python style and imports |
| Security scan | `bandit` | Python AST security |
| Tests | `pytest` | 104 tests — Azure/Docker tests auto-skipped without credentials |
| Frontend build | `tsc` + `next build` | TypeScript type-check and production build |
| Docker build | `docker build` | API and sandbox image build validation |

#### Makefile targets

| Target | Description |
|--------|-------------|
| `make run-api` | Start FastAPI dev server on `:8000` |
| `make run-frontend` | Start Next.js dev server on `:3000` |
| `make compose-up` | Start full 5-service Docker Compose stack |
| `make compose-down` | Stop and remove Compose containers |
| `make test` | Run full Python test suite |
| `make lint` | Run `ruff` + `bandit` |
| `make ingest` | Ingest default policy documents into ChromaDB |

---

## 🔵 Azure live acceptance

The following features are fully implemented and fail-closed locally. They require live Azure resources to complete acceptance testing:

| Item | What's done | What's needed |
|------|-------------|--------------|
| **Azure AI Content Safety Prompt Shields** | Adapter + fail-closed logic complete | Live `CONTENT_SAFETY_ENDPOINT` + key |
| **Azure OpenAI embedding deployment** | Local `sentence-transformers` fallback active | Deploy `text-embedding-3-small`, set `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` |
| **Azure Cost Management reconciliation** | Estimate calculation and dashboard UI complete | Live Azure session to compare estimates with actual billing |
| **Full E2E evidence capture** | Local demo runbook complete | Live run to record all 6 acceptance scenarios |

---

## Environment variables

Copy [`.env.example`](.env.example) to `.env`. The example file is fully documented inline. The table below covers every variable you need to set to run the app.

| Variable | Required | Default | Notes |
|----------|:--------:|---------|-------|
| `AZURE_OPENAI_ENDPOINT` | ✅ | — | `https://<resource>.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | ✅ | — | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | ✅ | — | Chat model deployment, e.g. `gpt-4o` |
| `AZURE_OPENAI_API_VERSION` | ✅ | `2024-10-21` | API version |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | ⚠️ Azure | — | Embedding model, e.g. `text-embedding-3-small` |
| `CONTENT_SAFETY_ENDPOINT` | ⚠️ Azure | — | Azure AI Content Safety endpoint |
| `CONTENT_SAFETY_KEY` | ⚠️ Azure | — | Content Safety API key |
| `MAGENT_PROVIDER` | — | `demo` | `demo` = no Azure calls · `azure` = live mode |
| `MAGENT_MAX_REVIEW_ROUNDS` | — | `5` | Hard cap on Coder ↔ Reviewer iterations |
| `BETTER_AUTH_SECRET` | ✅ | — | Min 32-char secret — `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | — | `magent` | Change before any shared deploy |
| `DATABASE_URL` | — | `postgres://magent:magent@localhost:5432/magent_auth` | Compose overrides this automatically |
| `BOOTSTRAP_ADMIN_EMAIL` | ✅ | `admin@localhost` | First admin account email |
| `BOOTSTRAP_ADMIN_PASSWORD` | ✅ | `ChangeMe_Admin8` | First admin password — change before deploy |
| `GITHUB_TOKEN` | — | _(empty)_ | PAT with `repo` scope — enables Export to PR |
| `GITHUB_REPO` | — | _(empty)_ | Target repo for PR export (`owner/repository`) |
| `INFRACOST_CLI_AUTHENTICATION_TOKEN` | — | _(empty)_ | Terraform cost estimates inside the sandbox |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | _(empty)_ | OTLP collector endpoint — leave empty to disable |

> All remaining variables (storage paths, timeouts, retry limits, OAuth providers) have sensible defaults and are documented in [`.env.example`](.env.example).

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop (Linux containers mode)

### Setup

```bash
# 1. Python environment
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt

# 2. Frontend
cd frontend && npm ci && cd ..

# 3. Configure environment
cp .env.example .env
# Minimum required edits:
#   BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD, BETTER_AUTH_SECRET
#   For Azure mode: AZURE_OPENAI_*, CONTENT_SAFETY_*

# 4a. Run locally (two terminals)
make run-api          # Terminal 1 — FastAPI on :8000
make run-frontend     # Terminal 2 — Next.js on :3000

# 4b. Or run the full stack with Docker Compose
make compose-up
```

Open [http://localhost:3000](http://localhost:3000) and sign in with the bootstrap admin credentials from `.env`.

### Run tests

```bash
make test                                         # Full suite (Azure/Docker tests auto-skipped)
python -m pytest tests/ -v -m "not integration"  # Exclude integration tests explicitly
```

### Ingest policy documents

```bash
python -m src.rag.ingest data/internal_rules.txt --output data/chroma/policy_manifest.json
```

### Health check

```bash
python -m src.healthcheck           # Config validation — no network call
python -m src.healthcheck --local   # Validates local tools (tfsec, checkov, bandit, docker)
python -m src.healthcheck --live    # Minimal live Azure request
```

---

## Project structure

```
MagentsAutoGen/
├── src/
│   ├── agents/              # Planner, Coder, Reviewer, FinOps, Security agents
│   ├── api/                 # FastAPI server, SSE, auth middleware
│   ├── config/              # Typed settings (Pydantic), LLM config
│   ├── integrations/        # GitHub PR exporter
│   ├── rag/                 # ChromaDB ingestion, vector store, retrieval
│   ├── security/            # Content Safety, scanners, sandbox, tag checker, local policy
│   ├── utils/               # Audit log, context manager, cost tracker, redaction,
│   │                        #   retry, run logger, conversation logger, telemetry
│   ├── workflow/            # FSM models, orchestrator, run store
│   ├── app_factory.py       # FastAPI app factory
│   └── healthcheck.py       # CLI health check
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js app router pages (runs, agents, finops, security, admin)
│   │   ├── components/      # All dashboard UI components (see §5)
│   │   ├── hooks/           # useEventStream, useFinops
│   │   ├── lib/             # API client, auth client, event types, run history, templates
│   │   └── middleware.ts    # Session-based route protection
│   └── scripts/
│       └── bootstrap-admin.ts  # First-admin seed script
├── tests/                   # 104 tests across 19 files
├── config/
│   └── pricing.json         # Per-model token pricing (never hardcoded)
├── data/
│   └── internal_rules.txt   # Default policy source document
├── deploy/                  # Bicep IaC, Azure deploy scripts
├── docker/                  # Dockerfile.api, Dockerfile.sandbox
├── docs/
│   └── architecture.md      # Full C4 architecture and component spec
├── .github/workflows/ci.yml # GitHub Actions CI pipeline
├── docker-compose.yml       # 5-service Compose stack
├── Makefile                 # Developer task runner
└── .env.example             # Fully documented environment variable template
```

---

## Safety guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| No host code execution | Docker is the only runtime; sandbox has no Docker socket |
| No code before approval | FSM state machine blocks Coder until human explicitly approves |
| No `terraform apply` | Sandbox validates syntax only — `apply` is blocked at the entrypoint |
| Scanner outage = failure | All scanners fail-closed; absent or crashed tool = blocked |
| No secrets in logs | `src/utils/redaction.py` strips keys and tokens before any log handler |
| No secrets in source | `.env` is git-ignored; only `.env.example` is committed |
| Prompt injection blocked | Azure AI Content Safety screens every request; local fallback when offline |
| Audit trail | Append-only audit log in `data/audit/` records every operator action |

---

## Required Azure resources

| Resource | Used by |
|----------|---------|
| Azure OpenAI — chat deployment | Planner, Coder, Reviewer, FinOps agents |
| Azure OpenAI — embedding deployment | Policy RAG vector store |
| Azure AI Content Safety (Prompt Shields) | Input screening before any agent receives the request |

All credentials are read from environment variables only. No Azure resource is provisioned by the application at runtime.

---

## Documentation

See [`docs/architecture.md`](docs/architecture.md) for the full C4 architecture diagrams, component specifications, agent design decisions, security pipeline design, trust boundaries, and Azure production deployment model.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| **Agent orchestration** | Python 3.11 · Microsoft Agent Framework |
| **Backend** | FastAPI · Uvicorn · Pydantic v2 |
| **Security analysis** | Bandit · Checkov · tfsec · Docker SDK |
| **Vector store** | ChromaDB · sentence-transformers · Azure OpenAI embeddings |
| **Frontend** | Next.js 14 · React 18 · TypeScript · Tailwind CSS · React Flow |
| **Auth** | Better Auth · Postgres 16 |
| **Observability** | OpenTelemetry · structured JSON logging |
| **DevOps** | Docker Compose · GitHub Actions · Makefile · ruff · pytest |
| **Azure** | Azure OpenAI · Azure AI Content Safety |
