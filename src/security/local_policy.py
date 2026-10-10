"""Deterministic local policy checks used before external scanner integration."""

from __future__ import annotations

import re

from src.workflow.models import (
    ArtifactLanguage,
    FindingSeverity,
    GeneratedArtifact,
    SecurityFinding,
)


class LocalPolicyGuard:
    """Detect a small, explicit set of high-risk patterns without executing code."""

    def scan(self, artifact: GeneratedArtifact) -> tuple[SecurityFinding, ...]:
        if artifact.language is ArtifactLanguage.PYTHON:
            return self._scan_python(artifact.content)
        return self._scan_terraform(artifact.content)

    def _scan_python(self, code: str) -> tuple[SecurityFinding, ...]:
        findings = []
        if re.search(r"\b(os\.system|subprocess\.(run|call|popen|Popen)|shutil\.rmtree)\b", code):
            findings.append(
                SecurityFinding(
                    tool="local-policy",
                    rule_id="LOCAL-PY-001",
                    severity=FindingSeverity.HIGH,
                    message="Generated Python contains a host-command or destructive-file API.",
                    remediation="Remove host command execution and destructive file operations.",
                )
            )
        if re.search(r"(?i)(api[_-]?key|password|secret)\s*=\s*['\"][^'\"]+", code):
            findings.append(
                SecurityFinding(
                    tool="local-policy",
                    rule_id="LOCAL-PY-002",
                    severity=FindingSeverity.HIGH,
                    message="Generated Python appears to contain a plaintext secret.",
                    remediation=(
                        "Use managed identity or a Key Vault reference instead of a literal secret."
                    ),
                )
            )
        return tuple(findings)

    def _scan_terraform(self, code: str) -> tuple[SecurityFinding, ...]:
        findings = []
        if "0.0.0.0/0" in code:
            findings.append(
                SecurityFinding(
                    tool="local-policy",
                    rule_id="LOCAL-TF-001",
                    severity=FindingSeverity.HIGH,
                    message="Terraform permits public access from 0.0.0.0/0.",
                    remediation="Restrict inbound access to an approved private network range.",
                )
            )
        if _has_public_ssh_rule(code):
            findings.append(
                SecurityFinding(
                    tool="local-policy",
                    rule_id="LOCAL-TF-005",
                    severity=FindingSeverity.HIGH,
                    message="Terraform exposes SSH from every network source.",
                    remediation="Remove public SSH and use approved private administration access.",
                )
            )
        if re.search(
            r'role_definition_name\s*=\s*"(?:owner|contributor)"',
            code,
            re.IGNORECASE,
        ):
            findings.append(
                SecurityFinding(
                    tool="local-policy",
                    rule_id="LOCAL-TF-006",
                    severity=FindingSeverity.HIGH,
                    message="Terraform assigns an over-broad Owner or Contributor role.",
                    remediation="Use the least-privileged Azure built-in or custom role.",
                )
            )
        if re.search(r"public_network_access_enabled\s*=\s*true", code, re.IGNORECASE):
            findings.append(
                SecurityFinding(
                    tool="local-policy",
                    rule_id="LOCAL-TF-002",
                    severity=FindingSeverity.HIGH,
                    message="Terraform enables public network access.",
                    remediation="Disable public network access or document an approved exception.",
                )
            )
        if re.search(r"allow_blob_public_access\s*=\s*true", code, re.IGNORECASE):
            findings.append(
                SecurityFinding(
                    tool="local-policy",
                    rule_id="LOCAL-TF-003",
                    severity=FindingSeverity.HIGH,
                    message="Terraform enables public blob access.",
                    remediation="Set allow_blob_public_access to false.",
                )
            )
        tags = {"environment", "owner", "cost_center"}
        missing_tags = sorted(tag for tag in tags if tag not in code)
        if missing_tags:
            findings.append(
                SecurityFinding(
                    tool="local-policy",
                    rule_id="LOCAL-TF-004",
                    severity=FindingSeverity.MEDIUM,
                    message=f"Terraform is missing required tags: {', '.join(missing_tags)}.",
                    remediation=(
                        "Add environment, owner, and cost_center tags to every Azure resource."
                    ),
                )
            )
        return tuple(findings)


def _has_public_ssh_rule(code: str) -> bool:
    has_ssh_port = bool(
        re.search(r'(?:destination_)?port(?:_range)?\s*=\s*"?22"?', code, re.IGNORECASE)
    )
    has_public_source = bool(
        re.search(
            r'(?:source_address_prefix|cidr_blocks)\s*=\s*(?:"\*"|"0\.0\.0\.0/0")',
            code,
            re.IGNORECASE,
        )
    )
    return has_ssh_port and has_public_source
