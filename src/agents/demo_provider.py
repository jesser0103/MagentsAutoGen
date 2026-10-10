"""Clearly labelled local provider for exercising the UI without cloud credentials."""

from __future__ import annotations

import json
from dataclasses import dataclass

from src.agents.model_provider import get_model_call_context
from src.utils.conversation_logger import ConversationExchange, ConversationLogger
from src.utils.cost_tracker import CostTracker


@dataclass
class DemoModelProvider:
    """Produce deterministic, safe sample outputs for development only."""

    max_tokens: int = 2048
    cost_tracker: CostTracker | None = None
    conversation_logger: ConversationLogger | None = None
    model: str = "demo-model"

    async def generate(self, name: str, instructions: str, prompt: str) -> str:
        lowered_prompt = prompt.lower()
        if name == "planner":
            response = self._plan(lowered_prompt)
        elif name == "coder":
            response = self._code(lowered_prompt)
        elif name == "reviewer":
            response = json.dumps(
                {
                    "verdict": "approve",
                    "assessment": (
                        "Demo provider returned a safe sample artifact. "
                        "External scanners are pending."
                    ),
                    "required_changes": [],
                }
            )
        else:
            raise ValueError(f"Unsupported demo agent: {name}")

        context = get_model_call_context()
        run_id = context.run_id if context else "unscoped"
        stage = context.stage if context else name
        prompt_tokens = _estimated_tokens(instructions) + _estimated_tokens(prompt)
        completion_tokens = min(self.max_tokens, _estimated_tokens(response))
        if self.cost_tracker is not None:
            self.cost_tracker.record(
                run_id=run_id,
                agent=name,
                stage=stage,
                model=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                max_tokens=self.max_tokens,
            )
        if self.conversation_logger is not None:
            self.conversation_logger.log_exchange(
                ConversationExchange(
                    run_id=run_id,
                    agent=name,
                    stage=stage,
                    instructions=instructions,
                    prompt=prompt,
                    response=response,
                    model=self.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    max_tokens=self.max_tokens,
                    finish_reason="stop",
                )
            )
        return response

    def _plan(self, prompt: str) -> str:
        language = "python" if "python" in prompt or "script" in prompt else "terraform"
        steps = [
            {
                "language": language,
                "description": "Create a secure implementation with required governance controls.",
            },
            {
                "language": language,
                "description": "Add logging, error handling, and a clear output contract.",
            },
        ]
        return json.dumps(
            {
                "summary": "Local development demonstration plan",
                "steps": steps,
                "open_questions": [],
            }
        )

    def _code(self, prompt: str) -> str:
        if "required language: python" in prompt:
            return """```python
import logging


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.info("MagentAutoGen local development artifact completed")


if __name__ == "__main__":
    main()
```"""
        return """```terraform
terraform {
  required_version = ">= 1.6.0"
}

resource "azurerm_resource_group" "main" {
  name     = "rg-magent-demo"
  location = "westeurope"

  tags = {
    environment = "dev"
    owner       = "platform"
    cost_center = "engineering"
  }
}
```"""


def _estimated_tokens(value: str) -> int:
    """Return a deterministic local-only estimate for demo observability."""
    return max(1, (len(value) + 3) // 4)
