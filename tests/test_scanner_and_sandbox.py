import json
import subprocess
import unittest

from src.security.sandbox import DockerSandboxRunner, SandboxWorkerClient, _parse_infracost_json
from src.security.sandbox_worker import _normalize_infracost_json, validate_payload
from src.security.scanners import CliSecurityScanner
from src.workflow.models import ArtifactLanguage, FindingSeverity, GeneratedArtifact


class CliSecurityScannerTests(unittest.TestCase):
    def test_missing_bandit_is_a_failed_required_scan(self) -> None:
        scanner = CliSecurityScanner(executable_finder=lambda _: None)
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="main.py",
            content="print('safe')\n",
        )

        reports = scanner.scan(artifact)

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].tool, "bandit")
        self.assertFalse(reports[0].succeeded)
        self.assertIn("unavailable", reports[0].error or "")

    def test_bandit_json_is_normalized_into_a_security_finding(self) -> None:
        def runner(command, timeout):
            payload = {
                "results": [
                    {
                        "test_id": "B605",
                        "issue_severity": "HIGH",
                        "issue_text": "Start process with a shell",
                        "filename": "main.py",
                        "line_number": 4,
                        "code": "subprocess.run(command, shell=True)",
                    }
                ]
            }
            return subprocess.CompletedProcess(command, 1, json.dumps(payload), "")

        scanner = CliSecurityScanner(
            executable_finder=lambda _: "bandit",
            command_runner=runner,
        )
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="main.py",
            content="import subprocess\n",
        )

        reports = scanner.scan(artifact)

        self.assertTrue(reports[0].succeeded)
        finding = reports[0].findings[0]
        self.assertEqual(finding.tool, "bandit")
        self.assertEqual(finding.rule_id, "B605")
        self.assertEqual(finding.severity, FindingSeverity.HIGH)
        self.assertEqual(finding.location, "main.py:4")

    def test_retries_transient_scanner_start_failure(self) -> None:
        calls = []

        def runner(command, timeout):
            calls.append((command, timeout))
            if len(calls) == 1:
                raise OSError("scanner service is starting")
            return subprocess.CompletedProcess(command, 0, '{"results": []}', "")

        scanner = CliSecurityScanner(
            executable_finder=lambda _: "bandit",
            command_runner=runner,
            retry_max_attempts=2,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
        )
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="main.py",
            content="print('safe')\n",
        )

        reports = scanner.scan(artifact)

        self.assertTrue(reports[0].succeeded)
        self.assertEqual(len(calls), 2)

    def test_terraform_runs_tfsec_and_checkov(self) -> None:
        commands = []

        def runner(command, timeout):
            commands.append(command)
            executable = command[0]
            if executable == "tfsec":
                return subprocess.CompletedProcess(command, 0, '{"results": []}', "")
            return subprocess.CompletedProcess(
                command,
                0,
                '{"results": {"failed_checks": []}}',
                "",
            )

        scanner = CliSecurityScanner(
            executable_finder=lambda tool: tool,
            command_runner=runner,
        )
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.TERRAFORM,
            filename="main.tf",
            content='resource "azurerm_resource_group" "main" {}\n',
        )

        reports = scanner.scan(artifact)

        # Three reports: tfsec, checkov, and the local tag-policy check (MA-402).
        self.assertEqual([report.tool for report in reports], ["tfsec", "checkov", "tag-policy"])
        # tfsec and checkov both succeeded (mocked to return no findings).
        self.assertTrue(reports[0].succeeded)
        self.assertTrue(reports[1].succeeded)
        # tag-policy also succeeded (it ran), but it found a CRITICAL finding
        # because the test artifact has no tags block.
        self.assertTrue(reports[2].succeeded)
        from src.workflow.models import FindingSeverity
        self.assertTrue(
            any(f.severity is FindingSeverity.CRITICAL for f in reports[2].findings),
            "Expected a CRITICAL finding for the untagged azurerm_resource_group resource",
        )
        # Only the two CLI tools were actually invoked as subprocesses.
        self.assertEqual([command[0] for command in commands], ["tfsec", "checkov"])


class DockerSandboxRunnerTests(unittest.TestCase):
    def test_missing_docker_does_not_fall_back_to_host_execution(self) -> None:
        runner = DockerSandboxRunner(executable_finder=lambda _: None)
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="main.py",
            content="raise RuntimeError('must not run on the host')\n",
        )

        result = runner.validate(artifact)

        self.assertFalse(result.succeeded)
        self.assertIn("host execution", result.summary)

    def test_python_validation_command_is_network_isolated_and_read_only(self) -> None:
        commands = []

        def runner(command, timeout):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        sandbox = DockerSandboxRunner(
            executable_finder=lambda _: "docker",
            command_runner=runner,
        )
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="main.py",
            content="print('this is compiled, not host-executed')\n",
        )

        result = sandbox.validate(artifact)
        command = commands[0]

        self.assertTrue(result.succeeded)
        self.assertEqual(command[:3], ("docker", "run", "--rm"))
        self.assertIn("none", command)
        self.assertIn("--read-only", command)
        self.assertIn("--pids-limit", command)
        self.assertIn("py_compile", " ".join(command))
        self.assertNotIn("terraform apply", " ".join(command))

    def test_retries_transient_docker_failure(self) -> None:
        calls = []

        def runner(command, timeout):
            calls.append((command, timeout))
            if len(calls) == 1:
                raise OSError("Docker daemon is starting")
            return subprocess.CompletedProcess(command, 0, "", "")

        sandbox = DockerSandboxRunner(
            executable_finder=lambda _: "docker",
            command_runner=runner,
            retry_max_attempts=2,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
        )

        result = sandbox.validate(
            GeneratedArtifact(
                language=ArtifactLanguage.PYTHON,
                filename="main.py",
                content="x = 1\n",
            )
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(len(calls), 2)

    def test_terraform_pricing_uses_fixed_infracost_command(self) -> None:
        commands = []

        def runner(command, timeout):
            commands.append(command)
            if "infracost" not in command:
                return subprocess.CompletedProcess(command, 0, "", "")
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {
                        "currency": "USD",
                        "projects": [
                            {
                                "breakdown": {
                                    "totalMonthlyCost": "14.50",
                                    "resources": [
                                        {
                                            "name": "azurerm_storage_account.main",
                                            "resourceType": "azurerm_storage_account",
                                            "monthlyCost": "14.50",
                                        }
                                    ],
                                }
                            }
                        ],
                    }
                ),
                "",
            )

        sandbox = DockerSandboxRunner(
            executable_finder=lambda _: "docker",
            command_runner=runner,
        )
        result = sandbox.validate(
            GeneratedArtifact(
                language=ArtifactLanguage.TERRAFORM,
                filename="main.tf",
                content='resource "azurerm_storage_account" "main" {}\n',
            )
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(len(commands), 2)
        self.assertIn("none", commands[0])
        self.assertIn("infracost", commands[1])
        self.assertIn("breakdown", commands[1])
        self.assertNotIn("terraform apply", " ".join(commands[1]))
        self.assertIsNotNone(result.infracost_breakdown)
        self.assertEqual(result.infracost_breakdown.total_monthly_usd, 14.50)


class SandboxWorkerClientTests(unittest.TestCase):
    def test_returns_worker_validation_result(self) -> None:
        requests = []

        def sender(endpoint, payload, timeout):
            requests.append((endpoint, payload, timeout))
            return {
                "succeeded": True,
                "summary": "validated in worker",
                "output": "",
                "infracost_breakdown": {
                    "total_monthly_usd": 3.65,
                    "currency": "USD",
                    "resources": [],
                    "error": None,
                },
            }

        client = SandboxWorkerClient(
            endpoint="http://sandbox:8081",
            timeout_seconds=12,
            request_sender=sender,
        )
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="main.py",
            content="x = 1\n",
        )

        result = client.validate(artifact)

        self.assertTrue(result.succeeded)
        self.assertEqual(result.summary, "validated in worker")
        self.assertEqual(requests[0][0], "http://sandbox:8081")
        self.assertEqual(requests[0][1]["language"], "python")
        self.assertEqual(requests[0][2], 12)
        self.assertIsNotNone(result.infracost_breakdown)
        self.assertEqual(result.infracost_breakdown.total_monthly_usd, 3.65)

    def test_invalid_worker_response_fails_closed(self) -> None:
        client = SandboxWorkerClient(
            endpoint="http://sandbox:8081",
            request_sender=lambda endpoint, payload, timeout: {"unexpected": True},
        )
        artifact = GeneratedArtifact(
            language=ArtifactLanguage.PYTHON,
            filename="main.py",
            content="x = 1\n",
        )

        result = client.validate(artifact)

        self.assertFalse(result.succeeded)
        self.assertIn("invalid result", result.summary)

    def test_retries_transient_worker_transport_failure(self) -> None:
        calls = []

        def sender(endpoint, payload, timeout):
            calls.append((endpoint, payload, timeout))
            if len(calls) == 1:
                raise OSError("connection refused")
            return {"succeeded": True, "summary": "validated"}

        client = SandboxWorkerClient(
            endpoint="http://sandbox:8081",
            request_sender=sender,
            retry_max_attempts=2,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
        )

        result = client.validate(
            GeneratedArtifact(
                language=ArtifactLanguage.PYTHON,
                filename="main.py",
                content="x = 1\n",
            )
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(len(calls), 2)


class SandboxWorkerValidationTests(unittest.TestCase):
    def test_valid_python_is_compiled_but_not_executed(self) -> None:
        result = validate_payload(
            {
                "language": "python",
                "filename": "main.py",
                "content": "raise RuntimeError('must never execute')\n",
            }
        )

        self.assertTrue(result["succeeded"], msg=str(result))

    def test_invalid_python_fails_validation(self) -> None:
        result = validate_payload(
            {
                "language": "python",
                "filename": "main.py",
                "content": "def broken(\n",
            }
        )

        self.assertFalse(result["succeeded"])

    def test_directory_traversal_filename_is_rejected(self) -> None:
        result = validate_payload(
            {
                "language": "python",
                "filename": "../main.py",
                "content": "x = 1\n",
            }
        )

        self.assertFalse(result["succeeded"])
        self.assertIn("plain file name", str(result["summary"]))


class InfracostNormalizationTests(unittest.TestCase):
    def test_cli_json_becomes_resource_level_monthly_costs(self) -> None:
        payload = json.dumps(
            {
                "currency": "USD",
                "projects": [
                    {
                        "breakdown": {
                            "totalMonthlyCost": "21.90",
                            "resources": [
                                {
                                    "name": "azurerm_key_vault.main",
                                    "resourceType": "azurerm_key_vault",
                                    "monthlyCost": "21.90",
                                }
                            ],
                        }
                    }
                ],
            }
        )

        local = _parse_infracost_json(payload)
        worker = _normalize_infracost_json(payload)

        self.assertEqual(local.total_monthly_usd, 21.90)
        self.assertEqual(local.resources[0].resource_type, "azurerm_key_vault")
        self.assertEqual(worker["total_monthly_usd"], 21.90)
        self.assertEqual(worker["resources"][0]["name"], "azurerm_key_vault.main")
