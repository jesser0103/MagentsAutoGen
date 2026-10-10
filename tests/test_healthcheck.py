import unittest

from src.healthcheck import LOCAL_VALIDATION_TOOLS, check_local_validation


class LocalValidationHealthCheckTests(unittest.TestCase):
    def test_reports_ready_when_every_tool_is_available(self) -> None:
        result = check_local_validation(lambda tool: f"C:/tools/{tool}.exe")

        self.assertTrue(result.connected)
        self.assertIn("ready", result.message.lower())

    def test_reports_missing_tools_without_contacting_azure(self) -> None:
        result = check_local_validation(lambda tool: None if tool == "tfsec" else tool)

        self.assertFalse(result.connected)
        self.assertIn("tfsec", result.message)
        self.assertEqual(LOCAL_VALIDATION_TOOLS, ("bandit", "tfsec", "checkov", "docker"))
