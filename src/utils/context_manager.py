"""Bounded prompt-context preparation with an auditable omission record."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ContextSnapshot:
    """The exact bounded text sent to an agent and omission evidence."""

    content: str
    original_characters: int
    omitted_characters: int = 0
    omitted_sha256: str | None = None

    @property
    def truncated(self) -> bool:
        return self.omitted_characters > 0


class ContextManager(Protocol):
    """Prepare untrusted workflow text for a bounded model prompt."""

    def prepare(self, content: str) -> ContextSnapshot:
        """Return prompt content that fits the configured character budget."""


@dataclass(frozen=True)
class BoundedContextManager:
    """Keep the beginning and latest details while hashing omitted middle content."""

    max_characters: int = 6000

    def __post_init__(self) -> None:
        if self.max_characters < 256:
            raise ValueError("max_characters must be at least 256")

    def prepare(self, content: str) -> ContextSnapshot:
        normalized = content.strip()
        original_characters = len(normalized)
        if original_characters <= self.max_characters:
            return ContextSnapshot(
                content=normalized,
                original_characters=original_characters,
            )

        marker_template = (
            "\n\n[Middle context omitted to fit the configured budget; "
            "omitted-content sha256={digest}]\n\n"
        )
        marker_size = len(marker_template.format(digest="0" * 64))
        retained_characters = self.max_characters - marker_size
        prefix_characters = retained_characters // 3
        suffix_characters = retained_characters - prefix_characters
        omitted_content = normalized[prefix_characters:-suffix_characters]
        omitted_sha256 = hashlib.sha256(omitted_content.encode("utf-8")).hexdigest()
        marker = marker_template.format(digest=omitted_sha256)
        omitted_characters = original_characters - retained_characters
        bounded = f"{normalized[:prefix_characters]}{marker}{normalized[-suffix_characters:]}"
        return ContextSnapshot(
            content=bounded,
            original_characters=original_characters,
            omitted_characters=omitted_characters,
            omitted_sha256=omitted_sha256,
        )
