# MagentAutoGen — Makefile
#
# Usage:
#   make test        Run unit tests
#   make test-all    Run all tests (unit + integration)
#   make lint        Run Ruff linter
#   make ingest      Ingest local policy rules into ChromaDB
#   make run-api     Start the FastAPI backend
#   make run-frontend Start the Next.js frontend
#   make run         Start both backend and frontend (requires two terminals)
#   make build       Build the Docker image
#   make clean       Remove generated artefacts

PYTHON       := .venv/Scripts/python.exe
PYTEST       := $(PYTHON) -m pytest
RUFF         := $(PYTHON) -m ruff

# ──────────────────────────────────────────────────────────────────────────────
# Targets
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: test test-all lint ingest ingest-no-chroma run run-api run-frontend build clean help

## Run unit tests (no Azure, no Docker required) ─────────────────────────────
test:
	$(PYTEST) tests/ -v -m "not integration" --tb=short

## Run all tests including integration tests ──────────────────────────────────
test-all:
	$(PYTEST) tests/ -v --tb=short

## Run tests with coverage report ─────────────────────────────────────────────
test-coverage:
	$(PYTEST) tests/ --cov=src --cov-report=term-missing --cov-report=html

## Lint source code with Ruff ─────────────────────────────────────────────────
lint:
	$(RUFF) check src/ tests/

## Auto-fix lint issues ────────────────────────────────────────────────────────
lint-fix:
	$(RUFF) check --fix src/ tests/

## Ingest local policy rules (ChromaDB + manifest) ────────────────────────────
ingest:
	$(PYTHON) -m src.rag.ingest

## Ingest local policy rules (manifest only, no ChromaDB) ────────────────────
ingest-no-chroma:
	$(PYTHON) -m src.rag.ingest --no-chroma

## Start the FastAPI backend ──────────────────────────────────────────────────
run-api:
	$(PYTHON) -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload

## Start the Next.js frontend (requires npm install in frontend/) ─────────────
run-frontend:
	cd frontend && set INTERNAL_API_URL=http://localhost:8000 && npm run dev

## Start both backend and frontend (opens two processes) ──────────────────────
run:
	@echo Starting FastAPI backend and Next.js frontend...
	@echo Run these in separate terminals:
	@echo   make run-api       (FastAPI on :8000)
	@echo   make run-frontend  (Next.js on :3000)
	@echo.
	@echo Or use Docker Compose:
	@echo   make compose-up

## Build the Docker image ─────────────────────────────────────────────────────
build:
	docker build -t magent-autogen-api:latest -f docker/Dockerfile.api .
	docker build -t magent-autogen-frontend:latest -f frontend/Dockerfile frontend/

## Start via Docker Compose ───────────────────────────────────────────────────
compose-up:
	docker compose up --build

## Stop Docker Compose ────────────────────────────────────────────────────────
compose-down:
	docker compose down

## Remove generated artefacts ─────────────────────────────────────────────────
clean:
	if exist .pytest_cache rmdir /s /q .pytest_cache
	if exist .ruff_cache   rmdir /s /q .ruff_cache
	if exist htmlcov       rmdir /s /q htmlcov
	for /r %%i in (__pycache__) do if exist "%%i" rmdir /s /q "%%i"

## Show this help ─────────────────────────────────────────────────────────────
help:
	@echo.
	@echo   MagentAutoGen — available make targets:
	@echo.
	@echo   make test              Unit tests (no Azure, no Docker)
	@echo   make test-all          All tests
	@echo   make test-coverage     Tests with HTML coverage report
	@echo   make lint              Ruff lint check
	@echo   make lint-fix          Ruff auto-fix
	@echo   make ingest            Ingest policy rules (ChromaDB)
	@echo   make ingest-no-chroma  Ingest policy rules (manifest only)
	@echo   make run-api           Start FastAPI backend
	@echo   make run-frontend      Start Next.js frontend
	@echo   make run               Show instructions for running both
	@echo   make build             Build Docker images
	@echo   make compose-up        Start via Docker Compose (API, UI, Postgres, first admin)
	@echo   make compose-down      Stop Docker Compose
	@echo   make clean             Remove generated artefacts
	@echo.
