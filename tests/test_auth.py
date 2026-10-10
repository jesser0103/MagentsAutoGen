"""Unit tests for API Key, JWT, and Entra ID authentication middleware."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.api.auth import (
    AuthenticatedUser,
    get_current_user,
    is_auth_enabled,
    require_role,
    require_separate_approver,
    user_roles,
    verify_auth,
)


def _mock_request(headers: dict[str, str] | None = None) -> MagicMock:
    req = MagicMock()
    req.headers = headers or {}
    return req


def test_auth_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAGENT_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("MAGENT_API_KEY", raising=False)

    assert not is_auth_enabled()
    user = asyncio.run(get_current_user(request=_mock_request()))
    assert user.auth_type == "local_dev"
    assert asyncio.run(verify_auth(user)) is True


def test_auth_enforced_rejects_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAGENT_AUTH_ENABLED", "true")
    monkeypatch.setenv("MAGENT_API_KEY", "prod-secret-api-key-999")

    assert is_auth_enabled()
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_user(request=_mock_request()))
    assert exc_info.value.status_code == 401


def test_auth_enforced_rejects_invalid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAGENT_AUTH_ENABLED", "true")
    monkeypatch.setenv("MAGENT_API_KEY", "prod-secret-api-key-999")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_user(request=_mock_request(), api_key="wrong-key"))
    assert exc_info.value.status_code == 401


def test_auth_enforced_accepts_valid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAGENT_AUTH_ENABLED", "true")
    monkeypatch.setenv("MAGENT_API_KEY", "prod-secret-api-key-999")

    user = asyncio.run(get_current_user(request=_mock_request(), api_key="prod-secret-api-key-999"))
    assert user.auth_type == "api_key"
    assert asyncio.run(verify_auth(user)) is True


def test_auth_enforced_accepts_valid_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAGENT_AUTH_ENABLED", "true")
    monkeypatch.setenv("MAGENT_API_KEY", "prod-secret-api-key-999")

    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials="prod-secret-api-key-999")
    user = asyncio.run(get_current_user(request=_mock_request(), bearer=bearer))
    assert user.auth_type == "bearer_token"
    assert asyncio.run(verify_auth(user)) is True


def test_auth_enforced_accepts_valid_jwt_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAGENT_AUTH_ENABLED", "true")
    monkeypatch.setenv("MAGENT_API_KEY", "prod-secret-api-key-999")

    jwt_token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signature"
    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials=jwt_token)
    user = asyncio.run(get_current_user(request=_mock_request(), bearer=bearer))
    assert user.auth_type == "jwt_bearer"
    assert asyncio.run(verify_auth(user)) is True


def test_entra_id_easyauth_header_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAGENT_AUTH_ENABLED", "true")
    monkeypatch.setenv("MAGENT_API_KEY", "prod-secret-api-key-999")

    user = asyncio.run(
        get_current_user(
            request=_mock_request(),
            x_ms_client_principal_name="jasser@contoso.com",
            x_ms_client_principal_id="guid-12345",
        )
    )
    assert user.auth_type == "entra_id"
    assert user.username == "jasser@contoso.com"
    assert user.user_id == "guid-12345"
    assert asyncio.run(verify_auth(user)) is True


def test_approver_role_is_required_for_plan_decisions() -> None:
    operator = AuthenticatedUser("operator-1", "operator", "jwt", {"role": "operator"})
    approver = AuthenticatedUser("approver-1", "approver", "jwt", {"role": "approver"})
    dependency = require_role("approver")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependency(operator))
    assert exc_info.value.status_code == 403
    assert asyncio.run(dependency(approver)) == approver


def test_entra_role_list_and_administrator_are_authorized() -> None:
    user = AuthenticatedUser(
        "admin-1",
        "admin",
        "entra_id",
        {"roles": ["reader", "administrator"]},
    )

    assert user_roles(user) == frozenset({"reader", "administrator"})
    assert asyncio.run(require_role("approver")(user)) == user


def test_submitter_cannot_approve_own_mission_when_auth_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAGENT_AUTH_ENABLED", "true")
    approver = AuthenticatedUser("user-1", "alice", "jwt", {"role": "approver"})

    with pytest.raises(HTTPException) as exc_info:
        require_separate_approver(approver, "user-1")
    assert exc_info.value.status_code == 403

    require_separate_approver(approver, "user-2")
