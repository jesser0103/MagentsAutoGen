# MagentAutoGen — AI Multi-Agent Control Plane for Azure

> **v1.0 — Complete** · Full-stack AI pipeline with Azure OpenAI, FastAPI backend, Next.js dashboard, Docker sandbox, RAG, FinOps, and CI/CD — all delivered.

A secure, human-governed multi-agent system that generates reviewed **Python** and **Terraform** cloud infrastructure artifacts through a controlled, auditable pipeline — powered by **Azure OpenAI**, **Microsoft Agent Framework**, and a **Next.js** control-plane dashboard.

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

**Nothing runs on the host machine. Generated code never executes before a human approves the plan.**


## Architecture

| Layer | Technology | Port |
|-------|-----------|------|
| Frontend dashboard | Next.js 14 (React / TypeScript / Tailwind) | `3000` |
| Backend API + SSE | FastAPI + Uvicorn | `8000` |
| Auth database | Postgres 16 (Better Auth) | `5432` |
| Validation sandbox | Locked-down Python / Terraform worker | Internal `8081` |
| Orchestration | Microsoft Agent Framework — typed FSM | — |
| Policy memory | ChromaDB + Azure OpenAI embeddings | — |
| Containers | Docker Compose | — |

---

## ✅ Features

### 1 · Multi-agent orchestration (Microsoft Agent Framework)

The workflow is a **typed finite-state machine** — not an open-ended chat loop. Every transition is gated and logged.

| Agent | Responsibility |
|-------|---------------|
| **Planner** | Decomposes the request into a structured plan with step type (Python/Terraform), assumptions, and open questions. Blocks downstream if required questions are unresolved. |
| **Coder** | Consumes the approved plan + retrieved policy rules. Generates a single Python or Terraform artifact. Injects mandatory governance tags on every Azure resource. Never self-executes. |
| **Reviewer** | Reads real scanner findings (tfsec, Checkov, Bandit). Issues `APPROVE` or `REJECT` with a required-changes list. Runs up to 5 rounds before escalating to `needs_manual_intervention`. |
| **FinOps Agent** | Captures token usage after every model call (prompt + completion). Calculates per-agent and per-stage cost estimates using external price tables. Never hardcodes prices. |
| **Security Agent** | Normalises findings from all static-analysis tools into a common `SecurityFinding` model (tool, rule ID, severity, location, evidence, remediation). |

**Approval gate:** the Coder cannot start until the operator explicitly approves the plan. The checkpoint is file-persisted and survives a backend restart.

---

### 2 · Security pipeline (fail-closed)

- **Azure AI Content Safety — Prompt Shields:** every user input is screened for direct and indirect prompt injection before any agent sees it. If the service is unreachable, the request is blocked — no fallthrough.
- **tfsec:** Terraform HCL static analysis. Public SSH, public storage, missing encryption, over-broad RBAC — all caught before review.
- **Checkov:** second-pass Terraform/Python policy check. CRITICAL and HIGH findings are **blocking**; the Reviewer cannot approve until they are resolved.
- **Bandit:** Python AST security analysis. Detects shell injection, hardcoded secrets, unsafe deserialisation.
- **Tag governance engine:** post-generation regex/AST check that every Azure resource carries `environment`, `owner`, and `cost_center` tags. Missing tags are raised as a CRITICAL finding.
- **Docker validation sandbox:** the approved artifact runs in a locked-down Linux container — no network egress, read-only root filesystem, CPU/memory/process limits, and no Docker socket. `terraform apply` is explicitly prohibited.
- **Missing scanner = blocked:** if a required scanner binary is absent or crashes, the scan is treated as failed, not passed.

---

### 3 · Policy RAG (ChromaDB + Azure OpenAI embeddings)

- Corporate policy documents (Terraform standards, cloud security baselines, compliance rules, FinOps tagging) are chunked, embedded, and stored in a **ChromaDB persistent collection**.
- Each ingestion records a SHA-256 content hash and a manifest entry so policy drift is traceable.
- Before code generation the Coder retrieves only rules whose similarity score exceeds a **configurable relevance threshold** — no weak matches are injected into the prompt.
- **Context bounding:** conversation history is summarised when it approaches the token limit. Omitted content is recorded in an audit trail.
- **Ingestion CLI:** `python -m src.rag.ingest <file>` — works locally with sentence-transformers, switches to Azure OpenAI embeddings when credentials are present.

---

### 4 · FastAPI backend + SSE event stream

- **REST API:** `POST /api/runs` to submit a request, `GET /api/runs/{id}` for state, `POST /api/runs/{id}/approve` / `/reject`, `GET /api/runs/{id}/artifact` for download.
- **Server-Sent Events:** `/api/runs/{id}/events/stream` pushes every workflow event (screening, planning, approval, retrieval, coding, scanning, review, sandbox, cost, completion) to the browser in real time.
- **Versioned event taxonomy:** every event carries a schema version, timestamp, run ID, component name, and redacted payload.
- **File-backed run store:** `WorkflowRun` state is persisted to JSON on every transition. Paused approval checkpoints survive a full service restart.
- **Structured logging:** JSON log handler with OpenTelemetry-compatible fields. Secrets are redacted at the log layer — keys, tokens, and endpoints never appear in output.
- **Retry + error envelopes:** bounded exponential backoff for Azure OpenAI, ChromaDB, scanner subprocesses, and Docker calls. Every error is wrapped in a typed `ErrorEnvelope` (source, message, retryable, timestamp).

---

### 5 · Next.js control-plane dashboard

| Screen | What it shows |
|--------|---------------|
| **New Mission** | Request input form with template picker and example prompts |
| **Live Run** | Real-time agent graph (React Flow) — active node highlighted, approval gate shown as pause state, terminal states colour-coded |
| **Event Console** | SSE-driven terminal that prints every workflow event with timestamp and component label |
| **Plan Editor** | Structured plan view with approve / reject + feedback text box |
| **Code Viewer** | Syntax-highlighted artifact diff, copy and download buttons |
| **Scan Dashboard** | Per-tool finding list, severity badges, block/pass summary |
| **FinOps Panel** | Per-agent token counts, cost estimate with disclaimer, session total |
| **Run History** | Searchable list of all runs; click any to reload full state |
| **Agent Inspector** | Drill into any agent node to see its input, output, and timing |
| **Red Team Panel** | Built-in prompt injection fixtures; submit and confirm block without leaving the UI |
| **Admin Panel** | User management, role assignment, bootstrap admin configuration |

All dashboard state is derived from the FastAPI SSE event stream and persisted run state — no client-side polling state machine.

---

### 6 · Authentication & multi-user

- **Better Auth** — production-grade auth library running against **Postgres 16**. Handles session lifecycle, token rotation, and credential hashing out of the box.
- **Session model:** server-side sessions stored in Postgres; the browser holds a signed, HTTP-only session cookie. No JWTs stored client-side.
- **CSRF protection:** built-in double-submit cookie pattern on all mutating endpoints.
- **Secure cookies:** `HttpOnly`, `SameSite=Strict`, `Secure` in production.
- **Register / Login flow:** `/register` and `/login` pages in Next.js; credentials validated server-side before session creation.
- **Bootstrap admin:** on first Docker Compose start, a seed job reads `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` from `.env` and creates the first administrator account — no manual DB access needed.
- **Role-based access:** `admin` vs. `operator` roles stored in Postgres and checked in the Next.js middleware on every protected route and in FastAPI on every API call.
- **Protected routes:** all `/agents`, `/runs`, `/finops`, `/security`, `/admin` routes require an active session; unauthenticated requests are redirected to `/login`.

---

### 7 · Storage & persistence

The system uses **three separate storage layers**, each purpose-built:

| Layer | Technology | What it stores |
|-------|-----------|----------------|
| **Auth & users** | Postgres 16 | User accounts, sessions, roles, CSRF tokens |
| **Workflow state** | File-backed JSON store | `WorkflowRun` objects — plan, artifact, scan results, approval status, event history, cost records |
| **Policy vectors** | ChromaDB (on-disk) | Chunked policy document embeddings with SHA-256 content hashes and manifest metadata |

**Workflow run store detail:**
- Every state transition (created → planning → awaiting_approval → coding → reviewing → done) is persisted immediately to disk as a JSON file under `data/checkpoints/`.
- A run paused at the human approval gate survives a full API restart — the operator can refresh the browser and continue from exactly where they left off.
- Run files include the full event history, agent messages (secrets redacted), cost records, and final artifact — enabling complete post-hoc audit.
- Runs are indexed by UUID and listed in the Run History dashboard screen.

**ChromaDB policy store detail:**
- Policies are stored in a named collection (`magent_policies`) in a persistent on-disk ChromaDB instance at `data/chroma/`.
- Each document chunk carries metadata: `rule_id`, `source_file`, `source_hash`, `ingested_at`.
- Re-running ingestion after editing a policy file updates only changed chunks (detected by SHA-256 hash diff).

---

### 8 · FinOps & cost observability

- Every model call (Planner, Coder, Reviewer, FinOps Agent) records `prompt_tokens` and `completion_tokens` from the Azure OpenAI response.
- Prices are loaded from `config/pricing.json` — never hardcoded. Supports per-model input/output/embedding rates.
- The dashboard FinOps panel shows: session total, per-agent breakdown, per-stage breakdown, and an estimate disclaimer (*"These are estimates. See Azure Cost Management for actual billing."*).
- Token, context, scanner timeout, sandbox timeout, and iteration limits are all explicit configuration values — no magic numbers in code.

---

### 9 · Infrastructure & CI/CD

- **Docker Compose:** five-service stack — FastAPI API, Next.js frontend, Postgres, isolated sandbox worker, and first-admin seed job. Services communicate over a private Docker network; the sandbox has no internet egress.
- **GitHub Actions CI:** on every push — `ruff` lint, `bandit` security scan, full Python test suite, Next.js type-check + build, and Docker build validation for API + sandbox images. Integration tests are automatically skipped when Azure credentials are absent.
- **Makefile:** `make run-api`, `make run-frontend`, `make compose-up`, `make compose-down`, `make test`, `make lint`, `make ingest`.
- **104 tests across 19 files** — agents, workflow FSM, scanner normalisation, sandbox runner, RAG ingestion/retrieval, context bounding, secret redaction, prompt injection fixtures, healthcheck, and UI integration.

---

## 🔵 Azure live acceptance (credentials required)

The following are fully implemented and fail-closed locally. They require live Azure resources to complete acceptance testing:

| Item | What's done | What's needed |
|------|-------------|--------------|
| **Azure AI Content Safety Prompt Shields** | Adapter + fail-closed logic implemented | Live `CONTENT_SAFETY_ENDPOINT` + key |
| **Azure OpenAI embedding deployment** | Local sentence-transformers fallback active | Deploy `text-embedding-3-small`, set `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` |
| **Azure Cost Management reconciliation** | Estimate calculation and UI complete | Run a live Azure session, compare with billing |
| **Full E2E evidence capture** | Local demo runbook complete | Live run to record all 6 acceptance scenarios |

---

## Environment variables

Copy [`.env.example`](.env.example) to `.env`. The full file is documented inline — here are the variables you need to set to run the app.

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
| `BETTER_AUTH_SECRET` | ✅ | — | Min 32-char secret — `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | — | `magent` | Change before any shared deploy |
| `DATABASE_URL` | — | `postgres://magent:magent@localhost:5432/magent_auth` | Compose sets this automatically |
| `BOOTSTRAP_ADMIN_EMAIL` | ✅ | `admin@localhost` | First admin account email |
| `BOOTSTRAP_ADMIN_PASSWORD` | ✅ | `ChangeMe_Admin8` | First admin password — change before deploy |
| `GITHUB_TOKEN` | — | _(empty)_ | PAT for pull-request artifact export |
| `INFRACOST_CLI_AUTHENTICATION_TOKEN` | — | _(empty)_ | Terraform cost estimates in the sandbox |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | _(empty)_ | OpenTelemetry collector — leave empty to disable |

> All other variables (timeouts, storage paths, retry limits, OAuth providers) have sensible defaults and are documented in [`.env.example`](.env.example).

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
pip install -r requirements.txt

# 2. Frontend
cd frontend && npm ci && cd ..

# 3. Configure environment
cp .env.example .env
# Edit .env:
#   - Set BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD
#   - For Azure mode: add AZURE_OPENAI_*, CONTENT_SAFETY_*, BETTER_AUTH_SECRET

# 4. Run
make run-api          # Terminal 1 — FastAPI on :8000
make run-frontend     # Terminal 2 — Next.js on :3000

# Or start everything at once
make compose-up
```

Open [http://localhost:3000](http://localhost:3000) and sign in with the bootstrap admin from `.env`.

### Tests

```bash
make test                                        # All unit tests
python -m pytest tests/ -v -m "not integration"  # Exclude Docker/Azure tests
```

### Ingest policy documents

```bash
python -m src.rag.ingest data/internal_rules.txt --output data/chroma/policy_manifest.json
```

### Health check

```bash
python -m src.healthcheck          # Validate config (no network call)
python -m src.healthcheck --live   # Minimal live Azure request
```

---

## Required Azure resources

| Resource | Purpose |
|----------|---------|
| Azure OpenAI — chat deployment | Planner, Coder, Reviewer, FinOps agents |
| Azure OpenAI — embedding deployment | Policy RAG vector store |
| Azure AI Content Safety (Prompt Shields) | Input screening before agent ingestion |

All values are read from environment variables only. See [`.env.example`](.env.example) for the full list.

---

## Safety guarantees

| Guarantee | How it is enforced |
|-----------|--------------------|
| No host execution | Docker is the only runtime; sandbox has no Docker socket |
| No code before approval | Workflow FSM blocks Coder until human approves |
| No `terraform apply` | Sandbox validates syntax only |
| Scanner outage = failure | All scanners fail-closed; missing tool = blocked |
| No secrets in logs | Central redaction applied to all log output |
| No secrets in source | `.env` is git-ignored; `.env.example` only |

---

## Documentation

See [`docs/architecture.md`](docs/architecture.md) for the full system architecture, C4 component diagrams, agent design, security pipeline, trust boundaries, and deployment model.

---

## Tech stack

**Backend:** Python 3.11 · FastAPI · Microsoft Agent Framework · ChromaDB · Bandit · Checkov · tfsec · Docker SDK  
**Frontend:** Next.js 14 · React · TypeScript · Tailwind CSS · React Flow · Better Auth  
**Azure:** Azure OpenAI · Azure AI Content Safety · Postgres 16  
**DevOps:** Docker Compose · GitHub Actions · Makefile · ruff · pytest

