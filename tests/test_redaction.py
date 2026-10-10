import unittest

from src.utils.redaction import PresidioRedactor, redact_data, redact_mapping, redact_text


class RedactionTests(unittest.TestCase):
    def test_redacts_secret_mapping_values(self) -> None:
        value = redact_mapping({
            "api_key": "secret",
            "nested": {"token": "also-secret", "client_secret": "xyz123"},
            "items": [{"password": "mypassword"}, "plain text"],
        })

        self.assertEqual(value["api_key"], "***")
        self.assertEqual(value["nested"]["token"], "***")
        self.assertEqual(value["nested"]["client_secret"], "***")
        self.assertEqual(value["items"][0]["password"], "***")
        self.assertEqual(value["items"][1], "plain text")

    def test_redacts_credentials_embedded_in_text(self) -> None:
        raw_text = (
            "api_key=secret-value Authorization: Bearer another-secret "
            "AccountKey=superSecretAzureKey123== password=mySuperPassword "
            "sk-abcdef1234567890abcdef123456"
        )
        redacted = redact_text(raw_text)

        self.assertNotIn("secret-value", redacted)
        self.assertNotIn("another-secret", redacted)
        self.assertNotIn("superSecretAzureKey123==", redacted)
        self.assertNotIn("mySuperPassword", redacted)
        self.assertNotIn("sk-abcdef1234567890abcdef123456", redacted)

    def test_redacts_jwt_and_private_keys(self) -> None:
        jwt = (
            "eyJhYmMxMjMiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dozjgN_dummy_signature_value123"
        )
        privkey = (
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n"
            "-----END RSA PRIVATE KEY-----"
        )

        redacted_jwt = redact_text(f"User token: {jwt}")
        self.assertNotIn(jwt, redacted_jwt)

        redacted_key = redact_text(f"Key:\n{privkey}")
        self.assertNotIn("MIIEowIBAAKCAQEA0...", redacted_key)

    def test_redacts_presidio_pii_and_azure_guid(self) -> None:
        text = (
            "Contact admin@contoso.com at IP 192.168.1.100. "
            "SSN: 123-45-6789. "
            "tenant_id: 12345678-abcd-1234-abcd-1234567890ab."
        )
        redacted = redact_text(text)
        self.assertNotIn("admin@contoso.com", redacted)
        self.assertNotIn("192.168.1.100", redacted)
        self.assertNotIn("123-45-6789", redacted)
        self.assertNotIn("12345678-abcd-1234-abcd-1234567890ab", redacted)

    def test_redact_data_helper(self) -> None:
        data = [
            {"connection_string": "AccountKey=abc;DefaultEndpointsProtocol=https"},
            {"auth_token": "token123"},
        ]
        redacted = redact_data(data)
        self.assertEqual(redacted[0]["connection_string"], "***")
        self.assertEqual(redacted[1]["auth_token"], "***")
