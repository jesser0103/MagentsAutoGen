"""Composition root for local development and Azure-backed application modes."""

from __future__ import annotations

from pathlib import Path

from src.agents.coder_agent import CoderAgent
from src.agents.demo_provider import DemoModelProvider
from src.agents.finops_agent import FinOpsAgent
from src.agents.model_provider import AgentFrameworkProvider, ModelProvider
from src.agents.planner_agent import PlannerAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.agents.security_agent import SecurityRedTeamAgent
from src.config.llm_config import get_llm_client
from src.config.settings import ApplicationSettings, SettingsError
from src.rag.vector_store import (
    AzureOpenAIEmbeddingFunction,
    ChromaRuleStore,
    LocalRuleStore,
    azure_embedding_collection_name,
)
from src.security.content_safety import LocalInputGuard
from src.security.content_safety_azure import build_input_guard
from src.security.local_policy import LocalPolicyGuard
from src.security.sandbox import DockerSandboxRunner, SandboxWorkerClient
from src.security.scanners import CliSecurityScanner
from src.utils.context_manager import BoundedContextManager
from src.utils.conversation_logger import ConversationLogger
from src.utils.cost_tracker import CostTracker
from src.workflow.orchestrator import WorkflowOrchestrator
from src.workflow.store import FileRunStore, PostgresRunStore, RunStore


def create_orchestrator(
    provider: ModelProvider | None = None,
    settings: ApplicationSettings | None = None,
    cost_tracker: CostTracker | None = None,
) -> WorkflowOrchestrator:
    """Build a local/demo orchestrator (no Azure credentials required)."""
    app_settings = settings or ApplicationSettings.from_environment()
    repository_root = Path(__file__).resolve().parent.parent
    pricing_path = _resolve_from_root(repository_root, app_settings.pricing_file)
    conversation_dir = _resolve_from_root(repository_root, app_settings.conversation_log_dir)

    provider_tracker = getattr(provider, "cost_tracker", None)
    selected_tracker = (
        cost_tracker
        or (provider_tracker if isinstance(provider_tracker, CostTracker) else None)
        or CostTracker(pricing_path=pricing_path)
    )
    selected_provider = provider or DemoModelProvider(
        max_tokens=app_settings.max_tokens,
        cost_tracker=selected_tracker,
        conversation_logger=ConversationLogger(conversation_dir),
    )
    manifest_path = repository_root / app_settings.chroma_dir / "policy_manifest.json"
    rules = (
        LocalRuleStore.from_manifest(manifest_path, app_settings.rag_relevance_threshold)
        if manifest_path.exists()
        else LocalRuleStore.from_markdown(
            repository_root / "data" / "internal_rules.txt",
            app_settings.rag_relevance_threshold,
        )
    )
    sandbox = (
        SandboxWorkerClient(
            endpoint=app_settings.sandbox_url,
            timeout_seconds=app_settings.sandbox_timeout_seconds,
            retry_max_attempts=app_settings.adapter_retry_max_attempts,
            retry_base_delay_seconds=app_settings.adapter_retry_base_delay_seconds,
            retry_max_delay_seconds=app_settings.adapter_retry_max_delay_seconds,
        )
        if app_settings.sandbox_url
        else DockerSandboxRunner(
            timeout_seconds=app_settings.sandbox_timeout_seconds,
            retry_max_attempts=app_settings.adapter_retry_max_attempts,
            retry_base_delay_seconds=app_settings.adapter_retry_base_delay_seconds,
            retry_max_delay_seconds=app_settings.adapter_retry_max_delay_seconds,
        )
    )
    return WorkflowOrchestrator(
        planner=PlannerAgent(selected_provider),
        coder=CoderAgent(selected_provider),
        reviewer=ReviewerAgent(selected_provider),
        input_screen=LocalInputGuard(max_characters=app_settings.max_input_characters),
        rule_retriever=rules,
        policy_guard=LocalPolicyGuard(),
        scanner=CliSecurityScanner(
            timeout_seconds=app_settings.scanner_timeout_seconds,
            retry_max_attempts=app_settings.adapter_retry_max_attempts,
            retry_base_delay_seconds=app_settings.adapter_retry_base_delay_seconds,
            retry_max_delay_seconds=app_settings.adapter_retry_max_delay_seconds,
        ),
        sandbox=sandbox,
        run_store=_create_run_store(app_settings, repository_root),
        context_manager=BoundedContextManager(app_settings.max_context_characters),
        cost_tracker=selected_tracker,
        finops_agent=FinOpsAgent(selected_provider),
        security_red_team=SecurityRedTeamAgent(selected_provider),
        max_review_rounds=app_settings.max_review_rounds,
    )


def create_azure_orchestrator(settings: ApplicationSettings | None = None) -> WorkflowOrchestrator:
    """Build a production orchestrator wired to live Azure AI services.

    Upgrades over the dev factory:
    - Azure Prompt Shields, required in Azure mode and fail-closed on outages.
    - ``ChromaRuleStore`` with a required Azure OpenAI embedding deployment.
    - ``FinOpsAgent`` for non-blocking monthly cloud cost projection.
    """
    app_settings = settings or ApplicationSettings.from_environment()
    repository_root = Path(__file__).resolve().parent.parent
    tracker = CostTracker(
        pricing_path=_resolve_from_root(repository_root, app_settings.pricing_file)
    )

    # ── LLM provider ────────────────────────────────────────────────────────
    provider = AgentFrameworkProvider(
        get_llm_client(app_settings),
        max_tokens=app_settings.max_tokens,
        model=app_settings.azure_openai.deployment_name,
        cost_tracker=tracker,
        conversation_logger=ConversationLogger(
            _resolve_from_root(repository_root, app_settings.conversation_log_dir)
        ),
        retry_max_attempts=app_settings.llm_retry_max_attempts,
        retry_base_delay_seconds=app_settings.llm_retry_base_delay_seconds,
        retry_max_delay_seconds=app_settings.llm_retry_max_delay_seconds,
    )

    # ── Input guard: Prompt Shields is mandatory in Azure mode ───────────────
    input_screen = build_input_guard(
        content_safety_endpoint=app_settings.content_safety_endpoint,
        content_safety_key=app_settings.content_safety_key,
        max_characters=app_settings.max_input_characters,
        timeout_seconds=app_settings.content_safety_timeout_seconds,
        require_azure=True,
    )

    # ── RAG: Azure OpenAI embeddings or local lexical fallback ───────────────
    chroma_path = _resolve_from_root(repository_root, app_settings.chroma_dir)
    app_settings.require_embedding_settings()
    azure_settings = app_settings.azure_openai
    embedding_fn = AzureOpenAIEmbeddingFunction(
        endpoint=azure_settings.endpoint or "",
        api_key=azure_settings.api_key or "",
        deployment_name=app_settings.embedding_deployment or "",
        api_version=azure_settings.api_version or "2024-02-01",
        retry_max_attempts=app_settings.adapter_retry_max_attempts,
        retry_base_delay_seconds=app_settings.adapter_retry_base_delay_seconds,
        retry_max_delay_seconds=app_settings.adapter_retry_max_delay_seconds,
    )
    rule_retriever: ChromaRuleStore | LocalRuleStore = ChromaRuleStore(
        chroma_path=chroma_path,
        relevance_threshold=app_settings.rag_relevance_threshold,
        collection_name=azure_embedding_collection_name(app_settings.embedding_deployment or ""),
        embedding_function=embedding_fn,
        retry_max_attempts=app_settings.adapter_retry_max_attempts,
        retry_base_delay_seconds=app_settings.adapter_retry_base_delay_seconds,
        retry_max_delay_seconds=app_settings.adapter_retry_max_delay_seconds,
    )
    if rule_retriever.count == 0:
        raise SettingsError(
            "The Azure policy index is empty. Run `python -m src.rag.ingest "
            "--azure-embeddings` before starting the Azure provider."
        )

    # ── FinOps agent (non-blocking cost projector) ────────────────────────
    finops_agent = FinOpsAgent(provider=provider)

    # ── Sandbox ───────────────────────────────────────────────────────────────
    sandbox = (
        SandboxWorkerClient(
            endpoint=app_settings.sandbox_url,
            timeout_seconds=app_settings.sandbox_timeout_seconds,
            retry_max_attempts=app_settings.adapter_retry_max_attempts,
            retry_base_delay_seconds=app_settings.adapter_retry_base_delay_seconds,
            retry_max_delay_seconds=app_settings.adapter_retry_max_delay_seconds,
        )
        if app_settings.sandbox_url
        else DockerSandboxRunner(
            timeout_seconds=app_settings.sandbox_timeout_seconds,
            retry_max_attempts=app_settings.adapter_retry_max_attempts,
            retry_base_delay_seconds=app_settings.adapter_retry_base_delay_seconds,
            retry_max_delay_seconds=app_settings.adapter_retry_max_delay_seconds,
        )
    )

    return WorkflowOrchestrator(
        planner=PlannerAgent(provider),
        coder=CoderAgent(provider),
        reviewer=ReviewerAgent(provider),
        input_screen=input_screen,
        rule_retriever=rule_retriever,
        policy_guard=LocalPolicyGuard(),
        scanner=CliSecurityScanner(
            timeout_seconds=app_settings.scanner_timeout_seconds,
            retry_max_attempts=app_settings.adapter_retry_max_attempts,
            retry_base_delay_seconds=app_settings.adapter_retry_base_delay_seconds,
            retry_max_delay_seconds=app_settings.adapter_retry_max_delay_seconds,
        ),
        sandbox=sandbox,
        run_store=_create_run_store(app_settings, repository_root),
        context_manager=BoundedContextManager(app_settings.max_context_characters),
        cost_tracker=tracker,
        finops_agent=finops_agent,
        security_red_team=SecurityRedTeamAgent(provider),
        max_review_rounds=app_settings.max_review_rounds,
    )


def _create_run_store(app_settings: ApplicationSettings, repository_root: Path) -> RunStore:
    if app_settings.database_url:
        return PostgresRunStore(app_settings.database_url)
    return FileRunStore(repository_root / app_settings.checkpoint_dir.parent / "runs")


def _resolve_from_root(repository_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repository_root / path
