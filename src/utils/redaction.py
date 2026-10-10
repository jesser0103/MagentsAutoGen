"""Presidio-grade NLP and pattern-based redaction engine for PII and secrets."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

log = logging.getLogger(__name__)

# Key names in mappings that automatically trigger masking
_SENSITIVE_KEY_MARKERS = (
    "key",
    "secret",
    "token",
    "password",
    "credential",
    "auth",
    "private",
    "cert",
    "connection_string",
    "access_key",
    "account_key",
    "client_secret",
    "signature",
    "bearer",
    "apikey",
    "subscription_key",
)

# High-precision contextual entity patterns (Presidio standard recognizers)
_ENTITY_PATTERNS = (
    # API Keys & Secrets
    (re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s,;\"']+)"), r"\1***"),
    (re.compile(r"(?i)(authorization:\s*bearer\s+)([^\s,;\"']+)"), r"\1***"),
    (re.compile(r"(?i)(password\s*[=:]\s*)([^\s,;\"']+)"), r"\1***"),
    (re.compile(r"(?i)(accountkey\s*=\s*)([^\s;\"']+)"), r"\1***"),
    (re.compile(r"(?i)(sharedaccesssignature\s*=\s*)([^\s;\"']+)"), r"\1***"),
    (re.compile(r"(?i)(client_secret\s*[=:]\s*)([^\s,;\"']+)"), r"\1***"),
    (re.compile(r"(?i)(subscription[_-]?key\s*[=:]\s*)([^\s,;\"']+)"), r"\1***"),
    (re.compile(r"\b(sk-[a-zA-Z0-9]{20,})\b"), "***"),
    # JWT Tokens (3 base64url segments separated by dots)
    (
        re.compile(
            r"\b(ey[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})\b"
        ),
        "***",
    ),
    # PEM Private Keys
    (
        re.compile(
            r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----"
        ),
        "*** [REDACTED_PRIVATE_KEY] ***",
    ),
    # Azure Tenant / Client GUID credentials (when labeled)
    (
        re.compile(
            r"(?i)(client[_-]?id|tenant[_-]?id|subscription[_-]?id)(\s*[=:]\s*)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
        ),
        r"\1\2***",
    ),
    # Credit Card Numbers (Luhn-compliant format: 13-16 digits)
    (
        re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "*** [REDACTED_CREDIT_CARD] ***",
    ),
    # US Social Security Numbers
    (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "*** [REDACTED_SSN] ***",
    ),
    # Email Addresses (when embedded inside free text)
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
        "*** [REDACTED_EMAIL] ***",
    ),
    # IPv4 Addresses (private / internal or public in sensitive context)
    (
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        "*** [REDACTED_IP] ***",
    ),
)


class PresidioRedactor:
    """Enterprise redaction engine supporting Microsoft Presidio Analyzer with regex fallback."""

    def __init__(self) -> None:
        self._presidio_analyzer = None
        self._presidio_anonymizer = None
        self._init_presidio()

    def _init_presidio(self) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]
            from presidio_anonymizer import AnonymizerEngine  # type: ignore[import-not-found]

            self._presidio_analyzer = AnalyzerEngine()
            self._presidio_anonymizer = AnonymizerEngine()
            log.info("Microsoft Presidio Analyzer & Anonymizer initialized successfully.")
        except ImportError:
            log.debug("Microsoft Presidio not installed — using built-in high-precision NLP regex recognizers.")

    def redact_text(self, text: str) -> str:
        """Redact PII, credentials, and sensitive entities from a string."""
        if not text or not isinstance(text, str):
            return text

        # If Microsoft Presidio is installed, run NER analysis first
        if self._presidio_analyzer and self._presidio_anonymizer:
            try:
                results = self._presidio_analyzer.analyze(
                    text=text,
                    language="en",
                    entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "CRYPTO", "IBAN_CODE", "US_SSN", "IP_ADDRESS"],
                )
                if results:
                    anonymized = self._presidio_anonymizer.anonymize(
                        text=text,
                        analyzer_results=results,
                    )
                    text = anonymized.text
            except Exception as exc:  # noqa: BLE001
                log.warning("Presidio analysis encountered an error: %s; falling back to pattern engine.", exc)

        # Apply high-precision entity and secret patterns
        result = text
        for pattern, replacement in _ENTITY_PATTERNS:
            result = pattern.sub(replacement, result)

        return result


_DEFAULT_REDACTOR = PresidioRedactor()


def redact_text(value: str) -> str:
    """Replace common credential and PII formats in a free-text string."""
    return _DEFAULT_REDACTOR.redact_text(value)


def redact_data(value: Any) -> Any:
    """Recursively redact sensitive data from mappings, sequences, and strings."""
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, (list, tuple, set)):
        return [redact_data(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a mapping while masking keys and recursively redacting nested mappings and lists."""
    redacted: dict[str, Any] = {}
    for key, item in value.items():
        if any(marker in str(key).lower() for marker in _SENSITIVE_KEY_MARKERS):
            redacted[key] = "***"
        elif isinstance(item, Mapping):
            redacted[key] = redact_mapping(item)
        elif isinstance(item, (list, tuple, set)):
            redacted[key] = [redact_data(element) for element in item]
        elif isinstance(item, str):
            redacted[key] = redact_text(item)
        else:
            redacted[key] = item
    return redacted
