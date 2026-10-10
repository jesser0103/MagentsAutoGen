"""Structured, redacted conversation history for model calls.

Each successful model call is appended as one JSON object to a per-run JSONL
file.  JSONL keeps writes append-only and makes partially written histories
recoverable while still being straightforward to analyse line by line.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.redaction import redact_text

logger = logging.getLogger(__name__)

CONVERSATION_SCHEMA = "magent-conversation/v1"
_DEFAULT_CONVERSATIONS_DIR = Path("data/conversations")
_UNSAFE_FILENAME_CHARACTERS = re.compile(r"[^a-zA-Z0-9_.-]")


@dataclass(frozen=True)
class ConversationExchange:
    """One request/response exchange with a specialized agent."""

    run_id: str
    agent: str
    stage: str
    instructions: str
    prompt: str
    response: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    max_tokens: int | None = None
    finish_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CONVERSATION_SCHEMA,
            "timestamp": self.created_at.isoformat(),
            "run_id": self.run_id,
            "agent": self.agent,
            "stage": self.stage,
            "model": self.model,
            "request": {
                "messages": [
                    {"role": "system", "content": redact_text(self.instructions)},
                    {"role": "user", "content": redact_text(self.prompt)},
                ],
                "max_tokens": self.max_tokens,
            },
            "response": {
                "role": "assistant",
                "content": redact_text(self.response),
                "finish_reason": self.finish_reason,
            },
            "usage": {
                "prompt_tokens": max(0, self.prompt_tokens),
                "completion_tokens": max(0, self.completion_tokens),
                "total_tokens": max(0, self.prompt_tokens) + max(0, self.completion_tokens),
            },
        }


class ConversationLogger:
    """Append and retrieve structured model exchanges grouped by run ID."""

    def __init__(self, directory: Path = _DEFAULT_CONVERSATIONS_DIR) -> None:
        self.directory = directory
        self._lock = threading.Lock()

    def log_exchange(self, exchange: ConversationExchange) -> Path:
        """Append *exchange* as one JSON line and return the history path."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path_for_run(exchange.run_id)
        line = json.dumps(exchange.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with self._lock, path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{line}\n")
        logger.info(
            "Conversation exchange recorded: run=%s agent=%s stage=%s",
            exchange.run_id,
            exchange.agent,
            exchange.stage,
        )
        return path

    def load(self, run_id: str) -> list[dict[str, Any]]:
        """Load all valid exchanges for *run_id* in append order."""
        path = self._path_for_run(run_id)
        if not path.exists():
            return []
        exchanges: list[dict[str, Any]] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "Skipping invalid conversation log line %s:%d: %s",
                    path,
                    line_number,
                    exc,
                )
                continue
            if isinstance(value, dict):
                exchanges.append(value)
        return exchanges

    def _path_for_run(self, run_id: str) -> Path:
        safe_run_id = _UNSAFE_FILENAME_CHARACTERS.sub("_", run_id.strip()) or "unscoped"
        return self.directory / f"{safe_run_id}.jsonl"
