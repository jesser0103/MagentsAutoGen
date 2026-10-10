"""Azure AI Content Safety Prompt Shields integration (MA-601 / MA-602)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from src.config.settings import SettingsError
from src.security.content_safety import InputScreen, LocalInputGuard, SafetyDecision

log = logging.getLogger(__name__)

PROMPT_SHIELD_API_VERSION = "2024-09-01"
PromptShieldRequestSender = Callable[[str, str, str, float], dict[str, object]]


def _send_prompt_shield_request(
    endpoint: str,
    api_key: str,
    user_prompt: str,
    timeout_seconds: float,
) -> dict[str, object]:
    """Call Azure's supported Prompt Shields REST endpoint."""
    request = Request(
        (
            f"{endpoint.rstrip('/')}/contentsafety/text:shieldPrompt"
            f"?api-version={PROMPT_SHIELD_API_VERSION}"
        ),
        data=json.dumps({"userPrompt": user_prompt, "documents": []}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Ocp-Apim-Subscription-Key": api_key,
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - configured Azure endpoint
        body = response.read(64_000)
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Azure Prompt Shields returned a non-object response")
    return payload


@dataclass
class AzurePromptShieldGuard:
    """Fail-closed input screen backed by Azure AI Content Safety Prompt Shields."""

    endpoint: str
    api_key: str
    max_characters: int = 4000
    timeout_seconds: float = 15
    request_sender: PromptShieldRequestSender = _send_prompt_shield_request

    async def screen(self, user_request: str) -> SafetyDecision:
        """Block direct injection, service failures, and malformed responses."""
        if not user_request.strip():
            return SafetyDecision(allowed=False, reason="A request is required.")
        if len(user_request) > self.max_characters:
            return SafetyDecision(
                allowed=False,
                reason=(
                    f"Request exceeds the configured input limit of "
                    f"{self.max_characters} characters."
                ),
            )

        try:
            response = await asyncio.to_thread(
                self.request_sender,
                self.endpoint,
                self.api_key,
                user_request,
                self.timeout_seconds,
            )
            return _decision_from_prompt_shield_response(response, len(user_request))
        except Exception as exc:  # noqa: BLE001 - required fail-closed boundary
            log.error(
                "Azure Prompt Shields call failed; request blocked. error=%s",
                exc,
            )
            return SafetyDecision(
                allowed=False,
                reason=(
                    "Request blocked: Azure AI Content Safety is unavailable "
                    "(fail-closed). Please try again later."
                ),
            )


def _decision_from_prompt_shield_response(
    response: dict[str, object],
    input_length: int,
) -> SafetyDecision:
    """Interpret Azure's ``userPromptAnalysis.attackDetected`` response."""
    analysis = response.get("userPromptAnalysis")
    if not isinstance(analysis, dict) or not isinstance(analysis.get("attackDetected"), bool):
        return SafetyDecision(
            allowed=False,
            reason=(
                "Request blocked: Azure Prompt Shields returned an invalid response "
                "(fail-closed)."
            ),
        )
    if analysis["attackDetected"]:
        log.warning("Prompt Shields blocked a user prompt input_length=%d", input_length)
        return SafetyDecision(
            allowed=False,
            reason=(
                "Request blocked by Azure Prompt Shields: a prompt injection or "
                "jailbreak attempt was detected."
            ),
        )
    return SafetyDecision(
        allowed=True,
        reason="Request cleared by Azure AI Content Safety Prompt Shields.",
    )


def build_input_guard(
    *,
    content_safety_endpoint: str | None,
    content_safety_key: str | None,
    max_characters: int = 4000,
    timeout_seconds: float = 15,
    require_azure: bool = False,
) -> InputScreen:
    """Build the Azure guard, or a labelled local-development guard.

    Azure application mode sets ``require_azure=True`` so a deployment cannot
    silently start with prompt-injection protection downgraded to regex checks.
    """
    if content_safety_endpoint and content_safety_key:
        return AzurePromptShieldGuard(
            endpoint=content_safety_endpoint,
            api_key=content_safety_key,
            max_characters=max_characters,
            timeout_seconds=timeout_seconds,
        )
    if require_azure:
        raise SettingsError(
            "Azure Prompt Shields requires CONTENT_SAFETY_ENDPOINT and CONTENT_SAFETY_KEY."
        )
    log.warning(
        "Azure Prompt Shields is not configured; using LocalInputGuard for development only."
    )
    return LocalInputGuard(max_characters=max_characters)
