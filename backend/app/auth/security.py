"""Minimal, non-production-grade RBAC for the PoC: two hardcoded demo users
(viewer / author) issuing JWTs. Viewer can query the knowledge base; author
can additionally generate documents, ingest files, and approve re-ingestion.
Not a substitute for enterprise IAM/SSO (explicitly out of scope per the
scope doc).
"""
import time

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)

ROLE_VIEWER = "viewer"
ROLE_AUTHOR = "author"


def _demo_users(settings: Settings) -> dict[str, dict]:
    return {
        settings.demo_viewer_username: {
            "password": settings.demo_viewer_password,
            "role": ROLE_VIEWER,
        },
        settings.demo_author_username: {
            "password": settings.demo_author_password,
            "role": ROLE_AUTHOR,
        },
    }


def authenticate(username: str, password: str, settings: Settings) -> str | None:
    """Returns the user's role if credentials are valid, else None."""
    user = _demo_users(settings).get(username)
    if user and user["password"] == password:
        return user["role"]
    return None


def create_access_token(username: str, role: str, settings: Settings) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": int(time.time()) + settings.jwt_expires_minutes * 60,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    payload = decode_token(credentials.credentials, settings)
    return {"username": payload["sub"], "role": payload["role"]}


def require_role(*allowed_roles: str):
    def _dependency(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user['role']}' not permitted; requires one of {allowed_roles}",
            )
        return user

    return _dependency
