from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, AsyncIterator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import SUPABASE_JWKS_URL, SUPABASE_JWT_SECRET, SUPABASE_URL
from app.core.logging import logger

_bearer = HTTPBearer(auto_error=False)
_request_user: ContextVar["CurrentUser | None"] = ContextVar(
    "request_user", default=None
)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    claims: dict[str, Any]


def get_request_user() -> CurrentUser | None:
    return _request_user.get()


def set_request_user(user: CurrentUser):
    return _request_user.set(user)


def reset_request_user(token) -> None:
    _request_user.reset(token)


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    if not SUPABASE_JWKS_URL:
        raise RuntimeError("SUPABASE_JWKS_URL is not configured")
    return PyJWKClient(SUPABASE_JWKS_URL)


def _issuer() -> str | None:
    return f"{SUPABASE_URL.rstrip('/')}/auth/v1" if SUPABASE_URL else None


def verify_access_token(token: str) -> CurrentUser:
    decode_options: dict[str, Any] = {
        "algorithms": ["HS256"],
        "audience": "authenticated",
    }
    if _issuer():
        decode_options["issuer"] = _issuer()
    if SUPABASE_JWT_SECRET:
        claims = jwt.decode(token, SUPABASE_JWT_SECRET, **decode_options)
    else:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        decode_options["algorithms"] = ["RS256", "ES256"]
        claims = jwt.decode(token, signing_key.key, **decode_options)
    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("JWT subject is missing")
    return CurrentUser(id=user_id, claims=claims)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AsyncIterator[CurrentUser]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        current_user = verify_access_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError, RuntimeError) as exc:
        logger.warning("invalid Supabase JWT: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    logger.info("authenticated request for user %s", current_user.id)
    token = _request_user.set(current_user)
    try:
        yield current_user
    finally:
        _request_user.reset(token)


def require_role(role: str):
    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.claims.get("user_role") != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{role} role is required",
            )
        return current_user

    return dependency
