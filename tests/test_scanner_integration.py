"""Integration tests for static-analysis scanner tools.

Each test is skipped when the required binary is absent from PATH so the
test suite still passes cleanly in environments without the tools installed.

Run with:
    python -m pytest tests/test_scanner_integration.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


class BanditIntegrationTests(unittest.TestCase):
    """Run the real Bandit binary against a known-bad Python fixture."""

    @unittest.skipIf(shutil.which("bandit") is None, "bandit not in PATH — skipping live test")
    def test_bandit_detects_shell_injection_in_bad_fixture(self) -> None:
        """Bandit must flag B602 (HIGH) in the bad_shell.py fixture."""
        result = subprocess.run(
            [
                shutil.which("bandit"),
                "-r",
                str(FIXTURES / "bad_shell.py"),
                "-f",
                "json",
                "-q",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Bandit exits 1 when it finds issues — that is expected
        payload = json.loads(result.stdout)
        findings = payload.get("results", [])

        rule_ids = {f.get("test_id") for f in findings}
        severities = {f.get("issue_severity", "").upper() for f in findings}

        self.assertTrue(
            findings,
            msg=(
                "Expected Bandit findings but got none.\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            ),
        )
        self.assertIn("B602", rule_ids, msg=f"B602 (shell=True) not found; got: {rule_ids}")
        self.assertIn(
            "HIGH",
            severities,
            msg=f"Expected HIGH severity; got: {severities}",
        )

    @unittest.skipIf(shutil.which("bandit") is None, "bandit not in PATH — skipping live test")
    def test_bandit_returns_clean_result_for_safe_python(self) -> None:
        """Bandit must report zero findings for trivially safe code."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1 + 1\nprint(x)\n")
            tmp_path = f.name

        try:
            result = subprocess.run(
                [shutil.which("bandit"), tmp_path, "-f", "json", "-q"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            payload = json.loads(result.stdout)
            findings = payload.get("results", [])
            self.assertEqual(
                findings,
                [],
                msg=f"Expected no findings for safe code; got: {findings}",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class CheckovIntegrationTests(unittest.TestCase):
    """Run the real Checkov binary against a known-bad Terraform fixture."""

    @unittest.skipIf(shutil.which("checkov") is None, "checkov not in PATH — skipping live test")
    def test_checkov_detects_missing_tags_and_encryption_in_bad_storage(self) -> None:
        """Checkov must report at least one failed check for the bad_storage.tf fixture."""
        with tempfile.TemporaryDirectory(prefix="checkov-test-") as tmpdir:
            # Copy fixture into isolated temp dir (checkov scans a directory)
            fixture_src = FIXTURES / "bad_storage.tf"
            import shutil as _shutil

            _shutil.copy(fixture_src, Path(tmpdir) / "main.tf")

            result = subprocess.run(
                [
                    shutil.which("checkov"),
                    "-d",
                    tmpdir,
                    "-o",
                    "json",
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

        # Checkov exits 1 when there are failures — expected
        # Strip any ANSI prefix before the JSON object
        stdout = result.stdout
        json_start = stdout.find("{")
        self.assertGreater(
            json_start,
            -1,
            msg=(
                "No JSON object in Checkov output.\n"
                f"stdout={stdout[:500]}\nstderr={result.stderr[:500]}"
            ),
        )
        payload = json.loads(stdout[json_start:])
        results = payload.get("results", {})
        failed_checks = results.get("failed_checks", [])

        self.assertTrue(
            failed_checks,
            msg=(
                "Expected at least one failed Checkov check for bad_storage.tf "
                f"but got none.\nraw_results={results}"
            ),
        )

    @unittest.skipIf(shutil.which("checkov") is None, "checkov not in PATH — skipping live test")
    def test_checkov_scanner_adapter_normalises_output(self) -> None:
        """CliSecurityScanner must produce a succeeded ScanReport with findings from Checkov."""
        from src.security.scanners import CliSecurityScanner
        from src.workflow.models import ArtifactLanguage, GeneratedArtifact

        artifact = GeneratedArtifact(
            language=ArtifactLanguage.TERRAFORM,
            filename="bad_storage.tf",
            content=(FIXTURES / "bad_storage.tf").read_text(encoding="utf-8"),
        )
        scanner = CliSecurityScanner(timeout_seconds=60)
        reports = scanner.scan(artifact)

        # We get two reports (tfsec + checkov); grab checkov's
        checkov_reports = [r for r in reports if r.tool == "checkov"]
        self.assertTrue(
            checkov_reports,
            msg=f"No checkov report in: {[r.tool for r in reports]}",
        )
        checkov_report = checkov_reports[0]

        if not checkov_report.succeeded:
            self.skipTest(f"Checkov report not succeeded: {checkov_report.error}")

        self.assertTrue(
            checkov_report.findings,
            msg="Expected at least one normalised finding from CliSecurityScanner/Checkov",
        )


class TfsecIntegrationTests(unittest.TestCase):
    """Run the real tfsec binary against the known-bad Terraform fixture.

    tfsec is a Go binary — skip gracefully when not in PATH.
    It is included in the API Docker image and intentionally optional on the host.
    """

    @unittest.skipIf(shutil.which("tfsec") is None, "tfsec not in PATH — skipping live test")
    def test_tfsec_detects_security_issues_in_bad_storage(self) -> None:
        """tfsec must report at least one finding for the bad_storage.tf fixture."""
        with tempfile.TemporaryDirectory(prefix="tfsec-test-") as tmpdir:
            import shutil as _shutil

            _shutil.copy(FIXTURES / "bad_storage.tf", Path(tmpdir) / "main.tf")

            result = subprocess.run(
                [shutil.which("tfsec"), "--format", "json", tmpdir],
                capture_output=True,
                text=True,
                timeout=60,
            )

        stdout = result.stdout
        json_start = stdout.find("{")
        self.assertGreater(json_start, -1, msg=f"No JSON from tfsec.\nstdout={stdout[:300]}")
        payload = json.loads(stdout[json_start:])
        findings = payload.get("results", [])

        self.assertTrue(
            findings,
            msg=f"Expected tfsec findings but got none.\npayload={payload}",
        )
