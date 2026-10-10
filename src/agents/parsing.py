"""Strict parsers for model output contracts."""

from __future__ import annotations

import json
import re
from typing import Any

from src.workflow.models import ArtifactLanguage


class AgentOutputError(ValueError):
    """Raised when a model response does not meet an agent output contract."""


_CODE_BLOCK_PATTERN = re.compile(
    r"```(?P<language>[a-zA-Z0-9_+-]+)?\s*\n(?P<code>.*?)```",
    re.DOTALL,
)


def parse_json_object(response: str) -> dict[str, Any]:
    """Extract one JSON object from a response that may include a Markdown fence."""
    candidate = response.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        if candidate.endswith("```"):
            candidate = candidate[:-3]
    start = candidate.find("{")
    if start < 0:
        raise AgentOutputError("Expected a JSON object in the agent response")
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(candidate[start:])
    except json.JSONDecodeError as error:
        raise AgentOutputError("Agent response contained invalid JSON") from error
    if not isinstance(payload, dict):
        raise AgentOutputError("Agent response must contain a JSON object")
    return payload


def extract_code_block(response: str) -> tuple[ArtifactLanguage, str]:
    """Extract exactly one supported fenced code block."""
    matches = list(_CODE_BLOCK_PATTERN.finditer(response))
    if len(matches) != 1:
        raise AgentOutputError("Coder response must contain exactly one fenced code block")
    language = _parse_language(matches[0].group("language") or "")
    code = matches[0].group("code").strip()
    if not code:
        raise AgentOutputError("Coder response contained an empty code block")
    return language, code


def _parse_language(value: str) -> ArtifactLanguage:
    normalized = value.lower().strip()
    if normalized in {"py", "python"}:
        return ArtifactLanguage.PYTHON
    if normalized in {"hcl", "terraform", "tf"}:
        return ArtifactLanguage.TERRAFORM
    raise AgentOutputError(f"Unsupported generated code language: {value or 'missing'}")
