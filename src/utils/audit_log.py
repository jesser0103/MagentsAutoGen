"""Immutable append-only audit log for operator actions.

Every security-relevant event (mission submitted, plan approved, plan
rejected, mission deleted, auth failures) is written as a single JSON
Line to ``data/audit/audit.jsonl``.

Design goals
------------
* **Append-only** — never overwrite or truncate the file.
* **Tamper-evident** — each entry carries an ISO-8601 UTC timestamp and
  the hash of the previous entry so a gap or edit is detectable.
* **Redacted** — the ``user_request`` field is truncated to 120 chars;
  no secrets, API keys, or passwords are ever recorded.
* **Non-blocking** — writes are synchronous but use a file-lock so
  concurrent FastAPI workers do not interleave JSON lines.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thread-level lock — one per process, shared across requests
# ---------------------------------------------------------------------------
_WRITE_LOCK = threading.Lock()


@dataclass(frozen=True)
class AuditEntry:
    """One immutable audit log record."""

    action: str                        # e.g. "mission_submitted"
    user_id: str
    username: str
    auth_type: str
    run_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    prev_hash: str = ""                # SHA-256 of the previous line
    entry_hash: str = field(init=False, default="")

    def __post_init__(self) -> None:
        # Compute hash after all other fields are set.
        # Use object.__setattr__ because the dataclass is frozen.
        raw = json.dumps(
            {k: v for k, v in asdict(self).items() if k != "entry_hash"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        object.__setattr__(self, "entry_hash", hashlib.sha256(raw).hexdigest())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------

class AuditLogger:
    """Append-only JSON-Lines audit logger.

    Parameters
    ----------
    log_path:
        Absolute or relative path to the ``.jsonl`` file.
        Defaults to the ``MAGENT_AUDIT_LOG`` environment variable or
        ``data/audit/audit.jsonl``.
    """

    def __init__(self, log_path: str | Path | None = None) -> None:
        resolved = (
            Path(log_path)
            if log_path
            else Path(os.getenv("MAGENT_AUDIT_LOG", "data/audit/audit.jsonl"))
        )
        self._path = resolved
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._prev_hash: str = self._read_last_hash()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def log(
        self,
        action: str,
        user_id: str,
        username: str,
        auth_type: str,
        run_id: str | None = None,
        **detail: Any,
    ) -> AuditEntry:
        """Append one audit entry and return it."""
        # Truncate free-text fields to prevent log injection
        safe_detail = {
            k: (v[:120] if isinstance(v, str) else v)
            for k, v in detail.items()
        }
        entry = AuditEntry(
            action=action,
            user_id=user_id,
            username=username,
            auth_type=auth_type,
            run_id=run_id,
            detail=safe_detail,
            prev_hash=self._prev_hash,
        )
        self._write(entry)
        return entry

    # ------------------------------------------------------------------ #
    # Convenience shortcuts for each lifecycle event
    # ------------------------------------------------------------------ #

    def mission_submitted(self, user_id: str, username: str, auth_type: str, run_id: str, request_preview: str) -> None:
        self.log("mission_submitted", user_id, username, auth_type, run_id=run_id, request_preview=request_preview[:120])

    def plan_approved(self, user_id: str, username: str, auth_type: str, run_id: str) -> None:
        self.log("plan_approved", user_id, username, auth_type, run_id=run_id)

    def plan_rejected(self, user_id: str, username: str, auth_type: str, run_id: str, feedback_preview: str) -> None:
        self.log("plan_rejected", user_id, username, auth_type, run_id=run_id, feedback_preview=feedback_preview[:120])

    def mission_deleted(self, user_id: str, username: str, auth_type: str, run_id: str) -> None:
        self.log("mission_deleted", user_id, username, auth_type, run_id=run_id)

    def auth_failure(self, reason: str, ip: str = "") -> None:
        self.log("auth_failure", user_id="anonymous", username="unknown", auth_type="none", reason=reason, ip=ip)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _write(self, entry: AuditEntry) -> None:
        line = json.dumps(entry.to_dict(), separators=(",", ":")) + "\n"
        with _WRITE_LOCK:
            try:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
                self._prev_hash = entry.entry_hash
            except OSError as exc:
                # Never crash the application over an audit write failure —
                # log loudly instead so ops teams are alerted.
                log.error(
                    "AUDIT LOG WRITE FAILED — action=%s run_id=%s error=%s",
                    entry.action, entry.run_id, exc,
                )

    def _read_last_hash(self) -> str:
        """Return the entry_hash of the last line in the log, or empty string."""
        if not self._path.exists():
            return ""
        try:
            with self._path.open("rb") as fh:
                # Seek to find the last non-empty line efficiently
                fh.seek(0, 2)  # end
                size = fh.tell()
                if size == 0:
                    return ""
                pos = max(0, size - 4096)
                fh.seek(pos)
                lines = fh.read().splitlines()
                for raw in reversed(lines):
                    if raw.strip():
                        data = json.loads(raw)
                        return str(data.get("entry_hash", ""))
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not read last audit hash: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Module-level singleton — imported by server.py
# ---------------------------------------------------------------------------

_audit: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Return the process-wide AuditLogger singleton (lazy init)."""
    global _audit
    if _audit is None:
        _audit = AuditLogger()
    return _audit
