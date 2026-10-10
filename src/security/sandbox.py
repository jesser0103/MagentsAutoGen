"""Docker-only validation for approved generated artifacts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from src.utils.retry import RetryExhaustedError, retry_sync
from src.workflow.models import (
    ArtifactLanguage,
    GeneratedArtifact,
    InfracostBreakdown,
    InfracostResource,
    SandboxResult,
)

CommandRunner = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]
ExecutableFinder = Callable[[str], str | None]
SandboxRequestSender = Callable[[str, dict[str, str], float], dict[str, object]]


class ArtifactSandbox(Protocol):
    """Validate an approved artifact without executing generated code."""

    def validate(self, artifact: GeneratedArtifact) -> SandboxResult:
        """Run an isolated syntax or formatting validation command."""


def _send_worker_request(
    endpoint: str,
    payload: dict[str, str],
    timeout: float,
) -> dict[str, object]:
    request = Request(
        f"{endpoint.rstrip('/')}/validate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured internal URL
        body = response.read(1_100_000)
    decoded = json.loads(body.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Sandbox worker returned a non-object response")
    return decoded


@dataclass
class SandboxWorkerClient:
    """Send fixed validation requests to the locked-down sandbox service."""

    endpoint: str
    timeout_seconds: float = 45
    retry_max_attempts: int = 2
    retry_base_delay_seconds: float = 0.5
    retry_max_delay_seconds: float = 5
    request_sender: SandboxRequestSender = _send_worker_request

    def validate(self, artifact: GeneratedArtifact) -> SandboxResult:
        try:
            payload = retry_sync(
                self.request_sender,
                self.endpoint,
                artifact.to_dict(),
                self.timeout_seconds,
                source="sandbox_worker",
                max_attempts=self.retry_max_attempts,
                base_delay=self.retry_base_delay_seconds,
                max_delay=self.retry_max_delay_seconds,
                retryable_exceptions=(OSError, TimeoutError, URLError),
            )
        except RetryExhaustedError as error:
            return SandboxResult(
                succeeded=False,
                summary=(
                    "Sandbox worker is unavailable after "
                    f"{error.attempts} attempt(s): {error.envelope.message}"
                ),
            )
        except (ValueError, json.JSONDecodeError) as error:
            return SandboxResult(
                succeeded=False,
                summary=f"Sandbox worker is unavailable or returned invalid data: {error}",
            )

        succeeded = payload.get("succeeded")
        summary = payload.get("summary")
        output = payload.get("output", "")
        if not isinstance(succeeded, bool) or not isinstance(summary, str):
            return SandboxResult(
                succeeded=False,
                summary="Sandbox worker returned an invalid result.",
            )
        return SandboxResult(
            succeeded=succeeded,
            summary=summary,
            output=output if isinstance(output, str) else "",
            infracost_breakdown=_infracost_breakdown_from_dict(
                payload.get("infracost_breakdown")
            ),
        )


def _run_command(command: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@dataclass
class DockerSandboxRunner:
    """Use Docker for syntax and formatting validation only, never deployment."""

    timeout_seconds: float = 45
    retry_max_attempts: int = 2
    retry_base_delay_seconds: float = 0.5
    retry_max_delay_seconds: float = 5
    python_image: str = "python:3.12-alpine"
    terraform_image: str = "hashicorp/terraform:1.9.8"
    infracost_image: str = "magent-autogen-sandbox:latest"
    executable_finder: ExecutableFinder = shutil.which
    command_runner: CommandRunner = _run_command

    def validate(self, artifact: GeneratedArtifact) -> SandboxResult:
        docker = self.executable_finder("docker")
        if docker is None:
            return SandboxResult(
                succeeded=False,
                summary="Docker is unavailable; host execution is intentionally prohibited.",
            )

        filename = Path(artifact.filename)
        if filename.name != artifact.filename:
            return SandboxResult(
                succeeded=False,
                summary="Artifact filename must not contain a directory path.",
            )

        with tempfile.TemporaryDirectory(prefix="magent-sandbox-") as directory:
            workspace = Path(directory)
            (workspace / filename.name).write_text(artifact.content, encoding="utf-8")
            command = self._command(docker, workspace, artifact)
            try:
                result = retry_sync(
                    self.command_runner,
                    command,
                    self.timeout_seconds,
                    source="docker_sandbox",
                    max_attempts=self.retry_max_attempts,
                    base_delay=self.retry_base_delay_seconds,
                    max_delay=self.retry_max_delay_seconds,
                    retryable_exceptions=(subprocess.TimeoutExpired, OSError),
                )
            except RetryExhaustedError as error:
                return SandboxResult(
                    succeeded=False,
                    summary=(
                        "Docker validation failed after "
                        f"{error.attempts} attempt(s): {error.envelope.message}"
                    ),
                )
            infracost_breakdown = (
                self._estimate_terraform_cost(docker, workspace)
                if result.returncode == 0 and artifact.language is ArtifactLanguage.TERRAFORM
                else None
            )

        output = _combined_output(result)
        if result.returncode != 0:
            return SandboxResult(
                succeeded=False,
                summary=f"Docker validation exited with code {result.returncode}.",
                output=output,
            )
        return SandboxResult(
            succeeded=True,
            summary="Docker validation completed with network disabled and a read-only filesystem.",
            output=output,
            infracost_breakdown=infracost_breakdown,
        )

    def _estimate_terraform_cost(
        self,
        docker: str,
        workspace: Path,
    ) -> InfracostBreakdown:
        """Run the fixed Infracost command after Terraform formatting succeeds.

        This is price calculation only: it never runs ``terraform plan`` or
        ``terraform apply``. Infracost needs HTTPS access to retrieve current
        catalogue prices, unlike the validation command above.
        """
        command = self._infracost_command(docker, workspace)
        try:
            result = retry_sync(
                self.command_runner,
                command,
                self.timeout_seconds,
                source="infracost",
                max_attempts=self.retry_max_attempts,
                base_delay=self.retry_base_delay_seconds,
                max_delay=self.retry_max_delay_seconds,
                retryable_exceptions=(subprocess.TimeoutExpired, OSError),
            )
        except RetryExhaustedError:
            return InfracostBreakdown(
                total_monthly_usd=0,
                error="Infracost pricing failed after bounded retries in the isolated container.",
            )
        if result.returncode != 0:
            return InfracostBreakdown(
                total_monthly_usd=0,
                error="Infracost could not retrieve a Terraform cost estimate.",
            )
        return _parse_infracost_json(result.stdout)

    def _command(
        self,
        docker: str,
        workspace: Path,
        artifact: GeneratedArtifact,
    ) -> tuple[str, ...]:
        command = (
            docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--pids-limit",
            "64",
            "--memory",
            "256m",
            "--cpus",
            "0.5",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65534:65534",
            "--mount",
            f"type=bind,source={workspace},target=/workspace,readonly",
        )
        if artifact.language is ArtifactLanguage.PYTHON:
            return (
                *command,
                "--entrypoint",
                "python",
                self.python_image,
                "-I",
                "-B",
                "-c",
                (
                    "import py_compile,sys; "
                    "py_compile.compile(sys.argv[1], cfile='/tmp/out.pyc', doraise=True)"
                ),
                f"/workspace/{artifact.filename}",
            )
        return (
            *command,
            "--entrypoint",
            "terraform",
            self.terraform_image,
            "fmt",
            "-check",
            "-diff",
            "/workspace",
        )

    def _infracost_command(self, docker: str, workspace: Path) -> tuple[str, ...]:
        command = (
            docker,
            "run",
            "--rm",
            "--network",
            "bridge",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--pids-limit",
            "64",
            "--memory",
            "256m",
            "--cpus",
            "0.5",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "10002:10002",
            "--mount",
            f"type=bind,source={workspace},target=/workspace,readonly",
        )
        if os.getenv("INFRACOST_CLI_AUTHENTICATION_TOKEN"):
            command += ("--env", "INFRACOST_CLI_AUTHENTICATION_TOKEN")
        return (
            *command,
            "--entrypoint",
            "infracost",
            self.infracost_image,
            "breakdown",
            "--path",
            "/workspace",
            "--format",
            "json",
        )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return output[:6000]


def _infracost_breakdown_from_dict(value: object) -> InfracostBreakdown | None:
    if not isinstance(value, dict):
        return None
    try:
        return InfracostBreakdown.from_dict(value)
    except (KeyError, TypeError, ValueError):
        return InfracostBreakdown(
            total_monthly_usd=0,
            error="Sandbox worker returned an invalid Infracost cost estimate.",
        )


def _parse_infracost_json(raw: str) -> InfracostBreakdown:
    """Normalize Infracost's JSON output without retaining raw artifact data."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return InfracostBreakdown(
            total_monthly_usd=0,
            error="Infracost returned an unreadable cost estimate.",
        )
    if not isinstance(payload, dict):
        return InfracostBreakdown(
            total_monthly_usd=0,
            error="Infracost returned an invalid cost estimate.",
        )

    currency = str(payload.get("currency") or "USD")
    resources: list[InfracostResource] = []
    total = 0.0
    for project in payload.get("projects", []):
        if not isinstance(project, dict) or not isinstance(project.get("breakdown"), dict):
            continue
        breakdown = project["breakdown"]
        total += _as_cost(breakdown.get("totalMonthlyCost"))
        for resource in breakdown.get("resources", []):
            if not isinstance(resource, dict):
                continue
            name = str(resource.get("name") or "unknown")
            resources.append(
                InfracostResource(
                    name=name,
                    resource_type=str(resource.get("resourceType") or name.split(".")[0]),
                    monthly_cost_usd=_as_cost(resource.get("monthlyCost")),
                )
            )
    if not resources and total == 0:
        return InfracostBreakdown(
            total_monthly_usd=0,
            currency=currency,
            error="Infracost did not identify priced Terraform resources.",
        )
    return InfracostBreakdown(
        total_monthly_usd=total,
        currency=currency,
        resources=tuple(resources),
    )


def _as_cost(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def readiness_check() -> str:
    """Return a human-readable Docker readiness status for the UI.

    Returns a string starting with 'ready' when Docker is running and usable,
    or a descriptive error string when it is not. Never raises.
    """
    docker = shutil.which("docker")
    if docker is None:
        return "Docker is not installed or not in PATH. Host execution is intentionally prohibited."
    try:
        result = subprocess.run(
            (docker, "info", "--format", "{{.ServerVersion}}"),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        return f"Docker info timed out or could not start: {error}"
    if result.returncode != 0:
        detail = " ".join(result.stderr.split())[:300]
        return f"Docker is not running or returned an error: {detail}"
    version = result.stdout.strip()
    return f"ready (Docker Engine {version})"
