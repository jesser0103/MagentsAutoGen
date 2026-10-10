"""Fail-closed CLI adapters for required static-analysis tools."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.security.tag_checker import check_required_tags
from src.utils.retry import RetryExhaustedError, retry_sync
from src.workflow.models import (
    ArtifactLanguage,
    FindingSeverity,
    GeneratedArtifact,
    ScanReport,
    SecurityFinding,
)

CommandRunner = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]
ExecutableFinder = Callable[[str], str | None]


class ArtifactScanner(Protocol):
    """Run the required static-analysis tools for a generated artifact."""

    def scan(self, artifact: GeneratedArtifact) -> tuple[ScanReport, ...]:
        """Return one report for every required scanner."""


def _run_command(command: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@dataclass
class CliSecurityScanner:
    """Execute Bandit, tfsec, and Checkov without running generated code."""

    timeout_seconds: float = 60
    retry_max_attempts: int = 2
    retry_base_delay_seconds: float = 0.5
    retry_max_delay_seconds: float = 5
    executable_finder: ExecutableFinder = shutil.which
    command_runner: CommandRunner = _run_command

    def scan(self, artifact: GeneratedArtifact) -> tuple[ScanReport, ...]:
        filename = Path(artifact.filename)
        if filename.name != artifact.filename:
            return (
                ScanReport(
                    tool="artifact-materialization",
                    succeeded=False,
                    error="Artifact filename must not contain a directory path.",
                ),
            )

        with tempfile.TemporaryDirectory(prefix="magent-scan-") as directory:
            workspace = Path(directory)
            (workspace / filename.name).write_text(artifact.content, encoding="utf-8")
            if artifact.language is ArtifactLanguage.PYTHON:
                return (self._scan_bandit(workspace),)
            # Terraform: run tfsec + Checkov + local tag-policy check (MA-402)
            return (
                self._scan_tfsec(workspace),
                self._scan_checkov(workspace),
                check_required_tags(artifact),
            )

    def _scan_bandit(self, workspace: Path) -> ScanReport:
        return self._run_tool(
            tool="bandit",
            arguments=("-r", str(workspace), "-f", "json", "-q"),
            parser=_parse_bandit,
        )

    def _scan_tfsec(self, workspace: Path) -> ScanReport:
        return self._run_tool(
            tool="tfsec",
            arguments=("--format", "json", str(workspace)),
            parser=_parse_tfsec,
        )

    def _scan_checkov(self, workspace: Path) -> ScanReport:
        return self._run_tool(
            tool="checkov",
            arguments=("-d", str(workspace), "-o", "json", "--quiet"),
            parser=_parse_checkov,
        )

    def _run_tool(
        self,
        *,
        tool: str,
        arguments: Sequence[str],
        parser: Callable[[dict[str, Any]], tuple[SecurityFinding, ...]],
    ) -> ScanReport:
        executable = self.executable_finder(tool)
        if executable is None:
            return ScanReport(
                tool=tool,
                succeeded=False,
                error=(
                    f"Required scanner '{tool}' is unavailable. "
                    "Install it or run the scanner image "
                    "before approving generated artifacts."
                ),
            )

        try:
            result = retry_sync(
                self.command_runner,
                (executable, *arguments),
                self.timeout_seconds,
                source=f"scanner:{tool}",
                max_attempts=self.retry_max_attempts,
                base_delay=self.retry_base_delay_seconds,
                max_delay=self.retry_max_delay_seconds,
                retryable_exceptions=(subprocess.TimeoutExpired, OSError),
            )
        except RetryExhaustedError as error:
            return ScanReport(
                tool=tool,
                succeeded=False,
                error=(
                    f"Required scanner '{tool}' failed after {error.attempts} attempt(s): "
                    f"{error.envelope.message}"
                ),
            )

        payload = _decode_json_object(result.stdout)
        if payload is None:
            detail = _compact_error(result.stderr)
            return ScanReport(
                tool=tool,
                succeeded=False,
                error=(
                    f"Required scanner '{tool}' returned exit code {result.returncode} without "
                    f"machine-readable JSON.{detail}"
                ),
            )

        try:
            findings = parser(payload)
        except (KeyError, TypeError, ValueError) as error:
            return ScanReport(
                tool=tool,
                succeeded=False,
                error=f"Required scanner '{tool}' returned an unsupported JSON schema: {error}",
            )

        if result.returncode != 0 and not findings:
            detail = _compact_error(result.stderr)
            return ScanReport(
                tool=tool,
                succeeded=False,
                error=(
                    f"Required scanner '{tool}' exited with {result.returncode} and reported no "
                    f"findings.{detail}"
                ),
            )
        return ScanReport(tool=tool, succeeded=True, findings=findings)


def _decode_json_object(output: str) -> dict[str, Any] | None:
    candidate = output.strip()
    start = candidate.find("{")
    if start < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(candidate[start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _compact_error(stderr: str) -> str:
    cleaned = " ".join(stderr.split())
    return f" Details: {cleaned[:300]}" if cleaned else ""


def _parse_bandit(payload: dict[str, Any]) -> tuple[SecurityFinding, ...]:
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise TypeError("results must be a list")
    return tuple(
        SecurityFinding(
            tool="bandit",
            rule_id=str(item.get("test_id") or "BANDIT-UNKNOWN"),
            severity=_severity(item.get("issue_severity")),
            message=str(item.get("issue_text") or "Bandit reported a Python security issue."),
            remediation="Resolve the Bandit finding before continuing to Docker validation.",
            location=_line_location(item.get("filename"), item.get("line_number")),
            evidence=_optional_text(item.get("code")),
        )
        for item in results
        if isinstance(item, dict)
    )


def _parse_tfsec(payload: dict[str, Any]) -> tuple[SecurityFinding, ...]:
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise TypeError("results must be a list")
    findings = []
    for item in results:
        if not isinstance(item, dict):
            continue
        location = item.get("location")
        findings.append(
            SecurityFinding(
                tool="tfsec",
                rule_id=str(item.get("long_id") or item.get("rule_id") or "TFSEC-UNKNOWN"),
                severity=_severity(item.get("severity")),
                message=str(
                    item.get("description")
                    or item.get("rule_description")
                    or "tfsec reported a Terraform security issue."
                ),
                remediation=str(
                    item.get("resolution")
                    or "Resolve the tfsec finding before continuing to Docker validation."
                ),
                location=_tfsec_location(location),
                evidence=_optional_text(item.get("expression")),
            )
        )
    return tuple(findings)


def _parse_checkov(payload: dict[str, Any]) -> tuple[SecurityFinding, ...]:
    results = payload.get("results", {})
    if not isinstance(results, dict):
        raise TypeError("results must be an object")
    failed_checks = results.get("failed_checks", [])
    if not isinstance(failed_checks, list):
        raise TypeError("failed_checks must be a list")
    findings = []
    for item in failed_checks:
        if not isinstance(item, dict):
            continue
        line_range = item.get("file_line_range")
        start_line = line_range[0] if isinstance(line_range, list) and line_range else None
        findings.append(
            SecurityFinding(
                tool="checkov",
                rule_id=str(item.get("check_id") or "CHECKOV-UNKNOWN"),
                severity=_severity(item.get("severity")),
                message=str(
                    item.get("check_name") or "Checkov reported a Terraform security issue."
                ),
                remediation="Resolve the Checkov finding before continuing to Docker validation.",
                location=_line_location(item.get("file_path"), start_line),
                evidence=_optional_text(item.get("resource")),
            )
        )
    return tuple(findings)


def _severity(value: object) -> FindingSeverity:
    normalized = str(value or "medium").lower()
    values = {
        "critical": FindingSeverity.CRITICAL,
        "high": FindingSeverity.HIGH,
        "medium": FindingSeverity.MEDIUM,
        "low": FindingSeverity.LOW,
    }
    return values.get(normalized, FindingSeverity.MEDIUM)


def _line_location(filename: object, line: object) -> str | None:
    path = _optional_text(filename)
    if path is None:
        return None
    try:
        line_number = int(line) if line is not None else None
    except (TypeError, ValueError):
        line_number = None
    return f"{path}:{line_number}" if line_number else path


def _tfsec_location(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    start_line = value.get("start_line")
    if start_line is None and isinstance(value.get("start"), dict):
        start_line = value["start"].get("line")
    return _line_location(value.get("filename"), start_line)


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
