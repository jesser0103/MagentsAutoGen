"""Microsoft Agent Framework client construction."""

from __future__ import annotations

from src.config.settings import ApplicationSettings, SettingsError


def get_llm_client(settings: ApplicationSettings | None = None):
    """Create a chat-completions client routed explicitly to Azure OpenAI."""
    app_settings = settings or ApplicationSettings.from_environment()
    azure_settings = app_settings.azure_openai
    azure_settings.require_chat_settings()

    try:
        from agent_framework.openai import OpenAIChatCompletionClient
    except ImportError as error:
        raise SettingsError(
            "Microsoft Agent Framework is not installed. Run: pip install -r requirements.txt"
        ) from error

    if azure_settings.uses_openai_compatible_base_url:
        return OpenAIChatCompletionClient(
            model=azure_settings.deployment_name,
            base_url=azure_settings.openai_compatible_base_url,
            api_key=azure_settings.api_key,
        )

    return OpenAIChatCompletionClient(
        model=azure_settings.deployment_name,
        azure_endpoint=azure_settings.endpoint,
        api_key=azure_settings.api_key,
        api_version=azure_settings.api_version,
    )
