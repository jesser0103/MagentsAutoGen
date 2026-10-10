"""Input-screen contracts with a local guard for development and tests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str


class InputScreen(Protocol):
    """Screen an untrusted user request before it reaches an agent."""

    async def screen(self, user_request: str) -> SafetyDecision:
        """Return the safety decision for one user request."""


@dataclass
class LocalInputGuard:
    """A development-only prompt-injection guard, not a Prompt Shields replacement."""

    max_characters: int = 4000

    _attack_patterns = (
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"reveal\s+(?:(?:the|your)\s+)?system\s+prompt", re.IGNORECASE),
        re.compile(r"bypass\s+(the\s+)?(safety|security|guardrails)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(dan|unrestricted)", re.IGNORECASE),
    )

    async def screen(self, user_request: str) -> SafetyDecision:
        if not user_request.strip():
            return SafetyDecision(allowed=False, reason="A request is required.")
        if len(user_request) > self.max_characters:
            return SafetyDecision(
                allowed=False,
                reason=(
                    "Request exceeds the configured input limit of "
                    f"{self.max_characters} characters."
                ),
            )
        if any(pattern.search(user_request) for pattern in self._attack_patterns):
            return SafetyDecision(
                allowed=False,
                reason="Request blocked by the local development input guard.",
            )
        return SafetyDecision(
            allowed=True,
            reason="Request passed the local development input guard.",
        )
