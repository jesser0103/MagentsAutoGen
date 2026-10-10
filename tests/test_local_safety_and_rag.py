import tempfile
import unittest
from pathlib import Path

from src.rag.vector_store import LocalRuleStore
from src.security.local_policy import LocalPolicyGuard
from src.workflow.models import ArtifactLanguage, GeneratedArtifact


class LocalPolicyGuardTests(unittest.TestCase):
    def test_flags_public_terraform_and_missing_required_tags(self) -> None:
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.TERRAFORM,
            filename="main.tf",
            content=(
                'resource "azurerm_storage_account" "example" {'
                "\n  public_network_access_enabled = true\n}"
            ),
        )

        findings = LocalPolicyGuard().scan(artifact)

        self.assertEqual(
            {finding.rule_id for finding in findings},
            {"LOCAL-TF-002", "LOCAL-TF-004"},
        )

    def test_flags_public_ssh_and_over_broad_rbac(self) -> None:
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.TERRAFORM,
            filename="main.tf",
            content=(
                'resource "azurerm_network_security_rule" "ssh" {\n'
                '  destination_port_range   = "22"\n'
                '  source_address_prefix     = "*"\n'
                "}\n\n"
                'resource "azurerm_role_assignment" "owner" {\n'
                '  role_definition_name = "Owner"\n'
                "}\n"
            ),
        )

        findings = LocalPolicyGuard().scan(artifact)

        self.assertEqual(
            {finding.rule_id for finding in findings},
            {"LOCAL-TF-004", "LOCAL-TF-005", "LOCAL-TF-006"},
        )

    def test_flags_plaintext_python_secret(self) -> None:
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="main.py",
            content='api_key = "plaintext-secret"\n',
        )

        findings = LocalPolicyGuard().scan(artifact)

        self.assertEqual([finding.rule_id for finding in findings], ["LOCAL-PY-002"])


class LocalRuleStoreTests(unittest.TestCase):
    def test_markdown_rules_are_ranked_by_request_relevance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rules_path = Path(directory) / "internal_rules.md"
            rules_path.write_text(
                "# Internal rules\n\n"
                "## SEC-001 Secrets\nUse Key Vault for application secrets.\n\n"
                "## NET-001 Private networking\n"
                "Disable public network access for storage resources.\n",
                encoding="utf-8",
            )
            store = LocalRuleStore.from_markdown(rules_path)

        rules = store.retrieve("Create private storage networking", limit=1)

        self.assertEqual(len(rules), 1)
        self.assertIn("NET-001", rules[0])
