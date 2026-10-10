"""Non-secret Azure OpenAI readiness checks."""

from __future__ import annotations

import argparse
import shutil
from collections.abc import Callable
from dataclasses import dataclass

from openai import AzureOpenAI, OpenAI

from src.config.settings import ApplicationSettings, SettingsError


@dataclass(frozen=True)
class HealthCheckResult:
    connected: bool
    message: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


LOCAL_VALIDATION_TOOLS = ("bandit", "tfsec", "checkov", "docker")


def validate_configuration(settings: ApplicationSettings) -> HealthCheckResult:
    settings.azure_openai.require_chat_settings()
    return HealthCheckResult(connected=True, message="Azure OpenAI configuration is complete.")


def check_azure_openai(settings: ApplicationSettings) -> HealthCheckResult:
    settings.azure_openai.require_chat_settings()
    azure_settings = settings.azure_openai
    if azure_settings.uses_openai_compatible_base_url:
        client = OpenAI(
            api_key=azure_settings.api_key,
            base_url=azure_settings.openai_compatible_base_url,
            timeout=20.0,
        )
    else:
        client = AzureOpenAI(
            api_key=azure_settings.api_key,
            azure_endpoint=azure_settings.endpoint,
            api_version=azure_settings.api_version,
            timeout=20.0,
        )
    response = client.chat.completions.create(
        model=azure_settings.deployment_name,
        messages=[{"role": "user", "content": "Reply only with CONNECTED."}],
        max_tokens=10,
    )
    text = response.choices[0].message.content or ""
    if text.strip().upper() != "CONNECTED":
        return HealthCheckResult(
            connected=False,
            message="Unexpected Azure OpenAI health-check response.",
        )
    usage = response.usage
    return HealthCheckResult(
        connected=True,
        message="Azure OpenAI connection succeeded.",
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
    )


def check_local_validation(
    executable_finder: Callable[[str], str | None] = shutil.which,
) -> HealthCheckResult:
    """Verify required local security tools without contacting Azure."""
    missing = tuple(tool for tool in LOCAL_VALIDATION_TOOLS if executable_finder(tool) is None)
    if missing:
        return HealthCheckResult(
            connected=False,
            message=(
                "Local validation is not ready. Install or expose on PATH: "
                f"{', '.join(missing)}."
            ),
        )
    return HealthCheckResult(
        connected=True,
        message="Local validation tools are ready: Bandit, tfsec, Checkov, and Docker.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate MagentAutoGen local and Azure readiness."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--live",
        action="store_true",
        help="Make a minimal Azure OpenAI request after validating local configuration.",
    )
    mode.add_argument(
        "--local",
        action="store_true",
        help="Check Bandit, tfsec, Checkov, and Docker without contacting Azure.",
    )
    arguments = parser.parse_args()
    try:
        if arguments.local:
            result = check_local_validation()
        else:
            settings = ApplicationSettings.from_environment()
            result = (
                check_azure_openai(settings) if arguments.live else validate_configuration(settings)
            )
    except SettingsError as error:
        print(f"Configuration check failed: {error}")
        return 2
    except Exception as error:
        print(f"Azure OpenAI health check failed: {error}")
        return 1

    print(result.message)
    if result.prompt_tokens is not None:
        print(f"Token usage: prompt={result.prompt_tokens}, completion={result.completion_tokens}")
    return 0 if result.connected else 1


if __name__ == "__main__":
    raise SystemExit(main())
