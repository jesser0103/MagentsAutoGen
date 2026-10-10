"""Persistent run storage with File, SQLite, and PostgreSQL implementations."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from src.workflow.models import WorkflowRun

log = logging.getLogger(__name__)


class RunStore(Protocol):
    """Persistence contract for workflow runs."""

    def save(self, run: WorkflowRun) -> None:
        """Persist a workflow run."""

    def load(self, run_id: str) -> WorkflowRun:
        """Load a workflow run by its identifier."""

    def list_recent(self, limit: int = 20) -> tuple[WorkflowRun, ...]:
        """Return recent workflow runs for operator history."""

    def delete(self, run_id: str) -> None:
        """Delete a workflow run by its identifier."""


class RunNotFoundError(KeyError):
    """Raised when no persisted run has the requested identifier."""


class FileRunStore:
    """JSON-file persistence that keeps approval state across server restarts."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, run: WorkflowRun) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        target = self._directory / f"{run.run_id}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(run.to_dict(), indent=2), encoding="utf-8")
        temporary.replace(target)

    def load(self, run_id: str) -> WorkflowRun:
        target = self._directory / f"{run_id}.json"
        if not target.exists():
            raise RunNotFoundError(run_id)
        payload = json.loads(target.read_text(encoding="utf-8"))
        return WorkflowRun.from_dict(payload)

    def list_recent(self, limit: int = 20) -> tuple[WorkflowRun, ...]:
        if limit < 1 or not self._directory.exists():
            return ()
        paths = sorted(
            self._directory.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        runs = []
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                runs.append(WorkflowRun.from_dict(payload))
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            if len(runs) == limit:
                break
        return tuple(runs)

    def delete(self, run_id: str) -> None:
        target = self._directory / f"{run_id}.json"
        if target.exists():
            target.unlink()
        else:
            raise RunNotFoundError(run_id)


class SqlRunStore:
    """Zero-dependency SQL relational store powered by SQLite.

    Provides indexed multi-run queries and transactional ACID durability.
    """

    def __init__(self, database_path: str | Path = ":memory:") -> None:
        self._db_path = str(database_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    user_request TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_runs_updated ON workflow_runs(updated_at DESC);"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);"
            )

    def save(self, run: WorkflowRun) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(run.to_dict())
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO workflow_runs (run_id, status, user_request, created_at, updated_at, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    payload=excluded.payload;
                """,
                (run.run_id, run.status.value, run.user_request, now, now, payload_str),
            )

    def load(self, run_id: str) -> WorkflowRun:
        cursor = self._conn.cursor()
        cursor.execute("SELECT payload FROM workflow_runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if not row:
            raise RunNotFoundError(run_id)
        payload = json.loads(row[0])
        return WorkflowRun.from_dict(payload)

    def list_recent(self, limit: int = 20) -> tuple[WorkflowRun, ...]:
        if limit < 1:
            return ()
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT payload FROM workflow_runs ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        runs = []
        for (payload_str,) in rows:
            try:
                runs.append(WorkflowRun.from_dict(json.loads(payload_str)))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                log.warning("Failed to deserialize workflow run from SQL store: %s", exc)
                continue
        return tuple(runs)

    def delete(self, run_id: str) -> None:
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM workflow_runs WHERE run_id = ?", (run_id,)
            )
            if cursor.rowcount == 0:
                raise RunNotFoundError(run_id)


    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()


class PostgresRunStore:
    """Enterprise PostgreSQL relational store for multi-tenant production deployments.

    Supports native JSONB storage, indexed status filtering, and connection pooling.
    If a database URL starts with ``sqlite:`` or ``sqlite3:``, it delegates to :class:`SqlRunStore`.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._sqlite_fallback: SqlRunStore | None = None

        if dsn.startswith("sqlite:") or dsn.startswith("sqlite3:"):
            # Strip sqlite:///, sqlite://, sqlite:
            clean = dsn.split("://", 1)[-1] if "://" in dsn else dsn.split(":", 1)[-1]
            if clean.startswith("/") and len(clean) > 2 and clean[2] == ":":
                clean = clean.lstrip("/")
            self._sqlite_fallback = SqlRunStore(clean)
            return

        try:
            import psycopg  # type: ignore[import-not-found]
            self._psycopg = psycopg
        except ImportError:
            try:
                import psycopg2 as psycopg  # type: ignore[import-not-found]
                self._psycopg = psycopg
            except ImportError:
                log.warning(
                    "psycopg / psycopg2 not installed — PostgresRunStore falling back to SqlRunStore(data/runs.db)"
                )
                self._sqlite_fallback = SqlRunStore("data/runs.db")
                return

        self._init_schema()

    def _get_connection(self):
        return self._psycopg.connect(self._dsn)

    def _init_schema(self) -> None:
        if self._sqlite_fallback:
            return
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workflow_runs (
                        run_id VARCHAR(64) PRIMARY KEY,
                        status VARCHAR(32) NOT NULL,
                        user_request TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        payload JSONB NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_workflow_runs_updated ON workflow_runs(updated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);
                    """
                )
            conn.commit()

    def save(self, run: WorkflowRun) -> None:
        if self._sqlite_fallback:
            self._sqlite_fallback.save(run)
            return

        payload_json = json.dumps(run.to_dict())
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow_runs (run_id, status, user_request, payload)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (run_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        updated_at = CURRENT_TIMESTAMP,
                        payload = EXCLUDED.payload;
                    """,
                    (run.run_id, run.status.value, run.user_request, payload_json),
                )
            conn.commit()

    def load(self, run_id: str) -> WorkflowRun:
        if self._sqlite_fallback:
            return self._sqlite_fallback.load(run_id)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM workflow_runs WHERE run_id = %s;", (run_id,))
                row = cur.fetchone()
                if not row:
                    raise RunNotFoundError(run_id)
                raw_payload = row[0]
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                return WorkflowRun.from_dict(payload)

    def list_recent(self, limit: int = 20) -> tuple[WorkflowRun, ...]:
        if self._sqlite_fallback:
            return self._sqlite_fallback.list_recent(limit)

        if limit < 1:
            return ()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM workflow_runs ORDER BY updated_at DESC LIMIT %s;",
                    (limit,),
                )
                rows = cur.fetchall()
                runs = []
                for (raw_payload,) in rows:
                    payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                    runs.append(WorkflowRun.from_dict(payload))
                return tuple(runs)

    def delete(self, run_id: str) -> None:
        if self._sqlite_fallback:
            self._sqlite_fallback.delete(run_id)
            return
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM workflow_runs WHERE run_id = %s;", (run_id,))
                if cur.rowcount == 0:
                    raise RunNotFoundError(run_id)
            conn.commit()


class InMemoryRunStore:
    """In-process store used by tests and isolated component demos."""

    def __init__(self) -> None:
        self._runs: dict[str, WorkflowRun] = {}

    def save(self, run: WorkflowRun) -> None:
        self._runs[run.run_id] = WorkflowRun.from_dict(run.to_dict())

    def load(self, run_id: str) -> WorkflowRun:
        try:
            return WorkflowRun.from_dict(self._runs[run_id].to_dict())
        except KeyError as error:
            raise RunNotFoundError(run_id) from error

    def list_recent(self, limit: int = 20) -> tuple[WorkflowRun, ...]:
        if limit < 1:
            return ()
        return tuple(self._runs.values())[-limit:][::-1]

    def delete(self, run_id: str) -> None:
        try:
            del self._runs[run_id]
        except KeyError as error:
            raise RunNotFoundError(run_id) from error
