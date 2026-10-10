"""Integration tests for the Docker sandbox using Docker Desktop.

Each test is skipped when Docker is not available so the suite stays green
on machines without Docker Desktop installed.

Run with:
    python -m pytest tests/test_sandbox_integration.py -v

Requirements:
    - Docker Desktop running in Linux containers mode
    - Images will be pulled on first run if not cached locally
"""

from __future__ import annotations

import shutil
import unittest

from src.security.sandbox import DockerSandboxRunner, readiness_check
from src.workflow.models import ArtifactLanguage, GeneratedArtifact

_DOCKER_AVAILABLE = shutil.which("docker") is not None


class DockerReadinessTests(unittest.TestCase):
    """Verify the readiness_check() helper surfaces Docker availability."""

    def test_readiness_check_returns_a_string(self) -> None:
        """readiness_check() must always return a string, never raise."""
        status = readiness_check()
        self.assertIsInstance(status, str)
        self.assertTrue(status, "readiness_check() must return a non-empty string")

    @unittest.skipIf(not _DOCKER_AVAILABLE, "docker not in PATH")
    def test_readiness_check_says_ready_when_docker_is_running(self) -> None:
        """readiness_check() should start with 'ready' when Docker Engine is up."""
        status = readiness_check()
        # Only assert 'ready' prefix when Docker is actually responding
        if "not running" in status or "timed out" in status:
            self.skipTest(f"Docker present but not responding: {status}")
        self.assertTrue(
            status.startswith("ready"),
            msg=f"Expected 'ready ...' but got: {status!r}",
        )


class DockerSandboxRunnerIntegrationTests(unittest.TestCase):
    """Run the DockerSandboxRunner against real Docker — Linux containers mode required."""

    @classmethod
    def _docker_responding(cls) -> bool:
        if not _DOCKER_AVAILABLE:
            return False
        status = readiness_check()
        return status.startswith("ready")

    @unittest.skipIf(not _DOCKER_AVAILABLE, "docker not in PATH")
    def setUp(self) -> None:
        status = readiness_check()
        if not status.startswith("ready"):
            self.skipTest(f"Docker is not responding: {status}")

    def test_valid_python_passes_sandbox_validation(self) -> None:
        """A syntactically correct Python artifact must produce succeeded=True."""
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="safe_module.py",
            content="def hello():\n    return 'world'\n",
        )
        runner = DockerSandboxRunner()
        result = runner.validate(artifact)

        self.assertTrue(
            result.succeeded,
            msg=(
                "Expected succeeded=True for valid Python.\n"
                f"summary={result.summary}\noutput={result.output}"
            ),
        )
        self.assertIn("network disabled", result.summary)

    def test_invalid_python_fails_sandbox_validation(self) -> None:
        """A syntactically broken Python artifact must produce succeeded=False."""
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="broken_module.py",
            content="def hello(\n    return 'missing closing paren'\n",
        )
        runner = DockerSandboxRunner()
        result = runner.validate(artifact)

        self.assertFalse(
            result.succeeded,
            msg=f"Expected succeeded=False for invalid Python.\nsummary={result.summary}",
        )

    def test_sandbox_command_is_network_isolated_and_read_only(self) -> None:
        """Verify the sandbox flags are in the command built for a Python artifact."""
        import subprocess

        commands_seen: list[tuple[str, ...]] = []

        def recording_runner(
            command: tuple[str, ...], timeout: float
        ) -> subprocess.CompletedProcess[str]:
            commands_seen.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="main.py",
            content="x = 1\n",
        )
        runner = DockerSandboxRunner(
            executable_finder=lambda _: "docker",
            command_runner=recording_runner,
        )
        runner.validate(artifact)

        self.assertEqual(len(commands_seen), 1)
        cmd = commands_seen[0]
        self.assertIn("--network", cmd)
        self.assertIn("none", cmd)
        self.assertIn("--read-only", cmd)
        self.assertIn("--pids-limit", cmd)
        self.assertNotIn("terraform apply", " ".join(cmd))
        self.assertIn("py_compile", " ".join(cmd))
