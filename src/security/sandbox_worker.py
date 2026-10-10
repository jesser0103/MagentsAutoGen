"""Minimal HTTP worker for isolated validation and Terraform price estimation.

The worker exposes fixed commands only. It never executes generated Python and
never runs Terraform plan or apply. Terraform pricing uses Infracost after
format validation and does not block the security workflow when unavailable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MAX_REQUEST_BYTES = int(os.getenv("SANDBOX_MAX_REQUEST_BYTES", "1048576"))
VALIDATION_TIMEOUT_SECONDS = float(os.getenv("SANDBOX_VALIDATION_TIMEOUT_SECONDS", "60"))
OUTPUT_LIMIT = 6000


def validate_payload(payload: object) -> dict[str, object]:
    """Validate one artifact using fixed, non-executing commands."""
    if not isinstance(payload, dict):
        return _failure("Sandbox request must be a JSON object.")

    language = payload.get("language")
    filename = payload.get("filename")
    content = payload.get("content")
    if language not in {"python", "terraform"}:
        return _failure("Unsupported artifact language.")
    if not isinstance(filename, str) or not _safe_filename(filename):
        return _failure("Artifact filename must be a plain file name.")
    if not isinstance(content, str):
        return _failure("Artifact content must be text.")
    if len(content.encode("utf-8")) > MAX_REQUEST_BYTES:
        return _failure("Artifact exceeds the sandbox request limit.")
    if language == "python" and not filename.endswith(".py"):
        return _failure("Python artifacts must use a .py filename.")
    if language == "terraform" and not filename.endswith(".tf"):
        return _failure("Terraform artifacts must use a .tf filename.")

    with tempfile.TemporaryDirectory(prefix="magent-sandbox-") as directory:
        workspace = Path(directory)
        artifact_path = workspace / filename
        artifact_path.write_text(content, encoding="utf-8")
        command = _validation_command(language, artifact_path, workspace)
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=VALIDATION_TIMEOUT_SECONDS,
                cwd=workspace,
            )
        except subprocess.TimeoutExpired:
            return _failure(
                f"Sandbox validation exceeded {VALIDATION_TIMEOUT_SECONDS:g} seconds."
            )
        except OSError as error:
            return _failure(f"Sandbox validation could not start: {error}")
        output = _combined_output(result)
        if result.returncode != 0:
            return {
                "succeeded": False,
                "summary": f"Sandbox validation exited with code {result.returncode}.",
                "output": output,
            }
        response: dict[str, object] = {
            "succeeded": True,
            "summary": "Sandbox worker validation completed in its locked-down container.",
            "output": output,
        }
        if language == "terraform":
            response["infracost_breakdown"] = _infracost_breakdown(workspace)
        return response


def _safe_filename(filename: str) -> bool:
    return bool(filename) and len(filename) <= 255 and Path(filename).name == filename


def _validation_command(
    language: str,
    artifact_path: Path,
    workspace: Path,
) -> tuple[str, ...]:
    if language == "python":
        compiled_path = workspace / "validated.pyc"
        return (
            sys.executable,
            "-I",
            "-B",
            "-c",
            (
                "import py_compile,sys; "
                "py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)"
            ),
            str(artifact_path),
            str(compiled_path),
        )
    return ("terraform", "fmt", "-check", "-diff", str(workspace))


def _infracost_breakdown(workspace: Path) -> dict[str, object]:
    """Return normalized prices without returning raw Infracost output.

    A non-interactive worker needs a token injected by Compose. The check avoids
    spawning the CLI when it is absent, and the generic errors keep credentials
    and generated source out of persisted workflow events.
    """
    if not os.getenv("INFRACOST_CLI_AUTHENTICATION_TOKEN"):
        return _empty_infracost(
            "Infracost is not configured for the sandbox worker."
        )
    try:
        result = subprocess.run(
            ("infracost", "breakdown", "--path", str(workspace), "--format", "json"),
            check=False,
            capture_output=True,
            text=True,
            timeout=VALIDATION_TIMEOUT_SECONDS,
            cwd=workspace,
        )
    except (subprocess.TimeoutExpired, OSError):
        return _empty_infracost("Infracost pricing did not complete in time.")
    if result.returncode != 0:
        return _empty_infracost("Infracost could not retrieve a Terraform cost estimate.")
    return _normalize_infracost_json(result.stdout)


def _normalize_infracost_json(raw: str) -> dict[str, object]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _empty_infracost("Infracost returned an unreadable cost estimate.")
    if not isinstance(payload, dict):
        return _empty_infracost("Infracost returned an invalid cost estimate.")

    resources: list[dict[str, object]] = []
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
                {
                    "name": name,
                    "resource_type": str(resource.get("resourceType") or name.split(".")[0]),
                    "monthly_cost_usd": _as_cost(resource.get("monthlyCost")),
                }
            )
    if not resources and total == 0:
        return _empty_infracost("Infracost did not identify priced Terraform resources.")
    return {
        "total_monthly_usd": total,
        "currency": str(payload.get("currency") or "USD"),
        "resources": resources,
        "error": None,
    }


def _empty_infracost(error: str) -> dict[str, object]:
    return {
        "total_monthly_usd": 0.0,
        "currency": "USD",
        "resources": [],
        "error": error,
    }


def _as_cost(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return output[:OUTPUT_LIMIT]


def _failure(summary: str) -> dict[str, object]:
    return {"succeeded": False, "summary": summary, "output": ""}


class SandboxRequestHandler(BaseHTTPRequestHandler):
    """Serve health and validation requests without framework dependencies."""

    server_version = "MagentSandbox/1.0"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/health":
            self._write_json(HTTPStatus.NOT_FOUND, {"detail": "Not found"})
            return
        self._write_json(HTTPStatus.OK, {"status": "ok"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/validate":
            self._write_json(HTTPStatus.NOT_FOUND, {"detail": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"detail": "Invalid Content-Length"})
            return
        if length < 1 or length > MAX_REQUEST_BYTES:
            self._write_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"detail": "Request too large"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._write_json(HTTPStatus.BAD_REQUEST, {"detail": "Invalid JSON"})
            return
        self._write_json(HTTPStatus.OK, validate_payload(payload))

    def log_message(self, format: str, *args: Any) -> None:
        print(f"sandbox-worker: {format % args}", flush=True)

    def _write_json(self, status: HTTPStatus, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = os.getenv("SANDBOX_HOST", "0.0.0.0")
    port = int(os.getenv("SANDBOX_PORT", "8081"))
    server = ThreadingHTTPServer((host, port), SandboxRequestHandler)
    print(f"sandbox-worker: listening on {host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
