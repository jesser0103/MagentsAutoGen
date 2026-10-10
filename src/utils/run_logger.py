"""Structured run-log exporter for MagentAutoGen (MA-207).

Writes each WorkflowRun snapshot to a timestamped JSON file under
``data/runs/`` so that every execution can be reconstructed from its
persisted log.  All string values are passed through :mod:`src.utils.redaction`
before being written to disk so that API keys and bearer tokens never appear
in the audit trail.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.redaction import redact_mapping, redact_text
from src.workflow.models import WorkflowRun

logger = logging.getLogger(__name__)

_DEFAULT_RUNS_DIR = Path("data/runs")


def _deep_redact(value: Any) -> Any:
    """Recursively redact a JSON-serialisable structure."""
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, list):
        return [_deep_redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


@dataclass
class RunLogger:
    """Persist a :class:`~src.workflow.models.WorkflowRun` snapshot to disk.

    Parameters
    ----------
    runs_dir:
        Directory under which per-run JSON files are written.  Created
        automatically if it does not already exist.
    """

    runs_dir: Path = _DEFAULT_RUNS_DIR

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, run: WorkflowRun) -> Path:
        """Serialise *run* to a redacted JSON file and return its path.

        The file is named ``<run_id>_<iso-timestamp>.json`` so that
        successive snapshots of the same run can coexist and are ordered
        lexicographically by creation time.

        Parameters
        ----------
        run:
            The workflow run to persist.

        Returns
        -------
        Path
            Absolute path of the written log file.
        """
        self.runs_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{run.run_id}_{timestamp}.json"
        log_path = self.runs_dir / filename

        payload = self._build_payload(run)
        log_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Run log written to %s", log_path)
        return log_path

    def load(self, run_id: str) -> list[dict[str, Any]]:
        """Return all saved snapshots for *run_id*, ordered by timestamp.

        Parameters
        ----------
        run_id:
            The UUID of the workflow run to look up.

        Returns
        -------
        list[dict]
            Each element is the raw (already-redacted) JSON payload from
            one log file.  Returns an empty list when no files match.
        """
        pattern = f"{run_id}_*.json"
        snapshots: list[dict[str, Any]] = []
        for path in sorted(self.runs_dir.glob(pattern)):
            try:
                snapshots.append(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read run log %s: %s", path, exc)
        return snapshots

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_payload(self, run: WorkflowRun) -> dict[str, Any]:
        """Convert *run* to a redacted, JSON-serialisable dict."""
        raw = run.to_dict()
        redacted = _deep_redact(raw)
        # Attach logger metadata so the file is self-describing.
        redacted["_log_schema"] = "magent-run-log/v1"
        redacted["_written_at"] = datetime.now(timezone.utc).isoformat()
        return redacted
