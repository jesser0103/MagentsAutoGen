import os
import unittest

from src.integrations.github_exporter import (
    GitHubExporter,
    GitHubExportError,
    build_pull_request_body,
)
from src.workflow.models import ArtifactLanguage, GeneratedArtifact, ScanReport, WorkflowRun


class GitHubExporterTests(unittest.TestCase):
    def test_environment_requires_token_and_repository(self) -> None:
        previous_token = os.environ.pop("GITHUB_TOKEN", None)
        previous_repo = os.environ.pop("GITHUB_REPO", None)
        try:
            with self.assertRaises(GitHubExportError):
                GitHubExporter.from_environment()
        finally:
            if previous_token is not None:
                os.environ["GITHUB_TOKEN"] = previous_token
            if previous_repo is not None:
                os.environ["GITHUB_REPO"] = previous_repo

    def test_pull_request_body_includes_artifacts_and_scan_summary(self) -> None:
        run = WorkflowRun(user_request="Create a secure helper.")
        run.artifacts.append(
            GeneratedArtifact(
                language=ArtifactLanguage.PYTHON,
                filename="main.py",
                content="def health() -> str:\n    return 'ok'\n",
            )
        )
        run.scans.append(ScanReport(tool="bandit", succeeded=True))

        body = build_pull_request_body(run)

        self.assertIn(f"`{run.run_id}`", body)
        self.assertIn("`main.py` (python)", body)
        self.assertIn("bandit: completed; 0 finding(s)", body)

    def test_export_rejects_run_without_artifacts_before_github_client_is_used(self) -> None:
        exporter = GitHubExporter(token="test-token", repository="owner/repository")

        with self.assertRaisesRegex(GitHubExportError, "no generated artifacts"):
            exporter.export(WorkflowRun(user_request="Nothing generated."))
