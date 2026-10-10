import asyncio
import unittest
from pathlib import Path

from src.security.content_safety import LocalInputGuard


class LocalInputGuardTests(unittest.TestCase):
    def test_blocks_every_prompt_injection_fixture(self) -> None:
        fixtures_path = Path(__file__).parent / "fixtures" / "prompt_injections.txt"
        fixtures = fixtures_path.read_text(encoding="utf-8").splitlines()
        guard = LocalInputGuard()

        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                decision = asyncio.run(guard.screen(fixture))

                self.assertFalse(decision.allowed)

    def test_allows_a_normal_cloud_request(self) -> None:
        decision = asyncio.run(
            LocalInputGuard().screen("Create a private Azure storage account with required tags.")
        )

        self.assertTrue(decision.allowed)

    def test_blocks_requests_over_the_configured_character_limit(self) -> None:
        decision = asyncio.run(LocalInputGuard(max_characters=10).screen("x" * 11))

        self.assertFalse(decision.allowed)
        self.assertIn("10 characters", decision.reason)
