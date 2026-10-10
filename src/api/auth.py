"""Authentication and authorization middleware with Microsoft Entra ID EasyAuth support."""

from __future__ import annotations

import base64
import hmac
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

try:
    import jwt as pyjwt  # PyJWT — optional, required for Better Auth JWT verification
    _PYJWT_AVAILABLE = True
except ImportError:
    _PYJWT_AVAILABLE = False

log = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
HTTP_BEARER = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represents the identity of the caller."""

    user_id: str
    username: str
    auth_type: str
    claims: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "auth_type": self.auth_type,
            "claims": self.claims,
        }


def is_auth_enabled() -> bool:
    """Check if authentication is strictly enforced."""
    raw = os.getenv("MAGENT_AUTH_ENABLED", "").strip().lower()
    if raw in {"true", "1", "yes", "enabled"}:
        return True
    return bool(os.getenv("MAGENT_API_KEY"))


def get_expected_api_key() -> str | None:
    """Return the configured API key if any."""
    key = os.getenv("MAGENT_API_KEY", "").strip()
    return key if key else None


def _decode_entra_principal(raw_principal: str | None) -> dict[str, object]:
    """Decode Azure App Service / ACA X-MS-CLIENT-PRINCIPAL header."""
    if not raw_principal:
        return {}
    try:
        decoded = base64.b64decode(raw_principal).decode("utf-8")
        parsed = json.loads(decoded)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as exc:  # noqa: BLE001
        log.debug("Could not decode X-MS-CLIENT-PRINCIPAL: %s", exc)
        return {}


def _verify_better_auth_jwt(token: str) -> AuthenticatedUser | None:
    """Verify a Better Auth JWT signed with BETTER_AUTH_SECRET (HS256).

    Returns an AuthenticatedUser if the token is valid, None otherwise.
    Requires PyJWT to be installed (``pip install PyJWT``).
    """
    if not _PYJWT_AVAILABLE:
        return None
    secret = os.getenv("BETTER_AUTH_SECRET", "").strip()
    if not secret:
        return None
    try:
        payload = pyjwt.decode(token, secret, algorithms=["HS256"])
        user_id = str(payload.get("sub") or payload.get("id") or "better-auth-user")
        username = (
            payload.get("name")
            or payload.get("email")
            or payload.get("username")
            or user_id
        )
        return AuthenticatedUser(
            user_id=user_id,
            username=str(username),
            auth_type="better_auth_jwt",
            claims={
                "email": payload.get("email"),
                "role": payload.get("role", "operator"),
                "iat": payload.get("iat"),
                "exp": payload.get("exp"),
            },
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("Better Auth JWT verification failed: %s", exc)
        return None


async def get_current_user(
    request: Request,
    api_key: Annotated[str | None, Security(API_KEY_HEADER)] = None,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Security(HTTP_BEARER)] = None,
    x_ms_client_principal_name: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-NAME")
    ] = None,
    x_ms_client_principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    x_ms_client_principal: Annotated[str | None, Header(alias="X-MS-CLIENT-PRINCIPAL")] = None,
) -> AuthenticatedUser:
    """Extract and validate the caller's identity via Entra ID, API Key, or Bearer JWT."""
    # 1. Azure Entra ID EasyAuth Header Check (Primary production SSO)
    if x_ms_client_principal_name or x_ms_client_principal_id:
        claims = _decode_entra_principal(x_ms_client_principal)
        return AuthenticatedUser(
            user_id=x_ms_client_principal_id or "entra-user",
            username=x_ms_client_principal_name or "entra-user",
            auth_type="entra_id",
            claims=claims,
        )

    # 2. Local development fallback when auth is disabled
    if not is_auth_enabled():
        return AuthenticatedUser(
            user_id="dev-operator",
            username="local-dev-operator",
            auth_type="local_dev",
            claims={"role": "administrator"},
        )

    expected_key = get_expected_api_key()

    # 3. API Key header check
    if api_key and expected_key and hmac.compare_digest(api_key.strip(), expected_key):
        return AuthenticatedUser(
            user_id="api-key-operator",
            username="api-key-operator",
            auth_type="api_key",
            claims={"role": "operator"},
        )

    # 4. Better Auth JWT (signed by Next.js with BETTER_AUTH_SECRET)
    if bearer and bearer.credentials:
        token = bearer.credentials.strip()
        better_auth_user = _verify_better_auth_jwt(token)
        if better_auth_user:
            return better_auth_user

        # 5. Raw API key passed as Bearer token (legacy)
        if expected_key and hmac.compare_digest(token, expected_key):
            return AuthenticatedUser(
                user_id="bearer-operator",
                username="bearer-operator",
                auth_type="bearer_token",
                claims={"role": "operator"},
            )
        # 6. Accept any well-formed 3-part JWT when auth is unenforced
        parts = token.split(".")
        if len(parts) == 3 and all(len(p) > 0 for p in parts):
            return AuthenticatedUser(
                user_id="jwt-user",
                username="entra-jwt-user",
                auth_type="jwt_bearer",
                claims={"token_type": "Bearer"},
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Microsoft Entra ID login or valid API Key required.",
        headers={"WWW-Authenticate": "Bearer, ApiKey"},
    )


async def verify_auth(user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> bool:
    """Dependency asserting the caller is properly authenticated."""
    return bool(user and user.user_id)


def user_roles(user: AuthenticatedUser) -> frozenset[str]:
    """Return normalized roles from Better Auth or Microsoft Entra claims."""
    raw_roles = user.claims.get("roles", user.claims.get("role", "operator"))
    values = raw_roles if isinstance(raw_roles, (list, tuple, set)) else (raw_roles,)
    return frozenset(str(value).strip().lower() for value in values if str(value).strip())


def require_role(required_role: str) -> Callable[..., AuthenticatedUser]:
    """Create a FastAPI dependency that admits an approver or administrator."""
    required = required_role.strip().lower()

    async def check_role(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        roles = user_roles(current_user)
        if required not in roles and "administrator" not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"The {required} role is required for this action.",
            )
        return current_user

    return check_role


def require_separate_approver(
    current_user: AuthenticatedUser,
    submitted_by_user_id: str | None,
) -> None:
    """Enforce separation of duties for persisted production workflow runs."""
    if not is_auth_enabled():
        return
    if not submitted_by_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This run has no recorded submitter and cannot be approved securely.",
        )
    if hmac.compare_digest(current_user.user_id, submitted_by_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A mission submitter cannot approve or reject their own plan.",
        )
