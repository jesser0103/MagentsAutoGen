"""Export completed workflow artifacts to a pull request in GitHub."""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.workflow.models import WorkflowRun


class GitHubExportError(RuntimeError):
    """Raised when a GitHub export cannot be created safely."""


@dataclass(frozen=True)
class GitHubExportResult:
    branch: str
    pull_request_number: int
    pull_request_url: str

    def to_dict(self) -> dict[str, str | int]:
        return {
            "branch": self.branch,
            "pull_request_number": self.pull_request_number,
            "pull_request_url": self.pull_request_url,
        }


@dataclass(frozen=True)
class GitHubExporter:
    token: str
    repository: str

    @classmethod
    def from_environment(cls) -> "GitHubExporter":
        token = os.getenv("GITHUB_TOKEN", "").strip()
        repository = os.getenv("GITHUB_REPO", "").strip()
        if not token or not repository:
            raise GitHubExportError(
                "GITHUB_TOKEN and GITHUB_REPO must be configured before export."
            )
        return cls(token=token, repository=repository)

    def export(self, run: WorkflowRun) -> GitHubExportResult:
        if not run.artifacts:
            raise GitHubExportError("This completed run has no generated artifacts to export.")
        try:
            from github import Auth, Github
            from github.GithubException import GithubException
        except ImportError as exc:
            raise GitHubExportError(
                "PyGithub is not installed; install project requirements first."
            ) from exc

        branch = f"magent/run-{run.run_id[:8]}"
        try:
            client = Github(auth=Auth.Token(self.token))
            repository = client.get_repo(self.repository)
            base_branch = repository.default_branch
            base_sha = repository.get_branch(base_branch).commit.sha
            repository.create_git_ref(ref=f"refs/heads/{branch}", sha=base_sha)

            for artifact in run.artifacts:
                path = f"generated/magent/{run.run_id}/{artifact.filename}"
                repository.create_file(
                    path=path,
                    message=f"magent: add {artifact.filename} for run {run.run_id[:8]}",
                    content=artifact.content,
                    branch=branch,
                )

            pull_request = repository.create_pull(
                title=f"Magent: generated artifacts for run {run.run_id[:8]}",
                body=build_pull_request_body(run),
                head=branch,
                base=base_branch,
            )
        except GithubException as exc:
            detail = exc.data.get("message", str(exc)) if isinstance(exc.data, dict) else str(exc)
            raise GitHubExportError(f"GitHub rejected the export: {detail}") from exc

        return GitHubExportResult(
            branch=branch,
            pull_request_number=pull_request.number,
            pull_request_url=pull_request.html_url,
        )


def build_pull_request_body(run: WorkflowRun) -> str:
    """Create a concise PR description from persisted, non-secret run evidence."""
    artifacts = "\n".join(
        f"- `{artifact.filename}` ({artifact.language.value})" for artifact in run.artifacts
    )
    scans = "\n".join(
        f"- {report.tool}: {'completed' if report.succeeded else 'failed'}; "
        f"{len(report.findings)} finding(s)"
        for report in run.scans
    ) or "- No scanner reports were recorded."
    return (
        "## Magent Control Plane export\n\n"
        f"Workflow run: `{run.run_id}`\n\n"
        "### Generated artifacts\n"
        f"{artifacts}\n\n"
        "### Security scan summary\n"
        f"{scans}\n\n"
        "This pull request was created after the workflow completed its configured review "
        "and sandbox validation. Review the generated code before merging."
    )
