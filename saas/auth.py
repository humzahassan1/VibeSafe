"""Authentication — password hashing, API keys, and session tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Optional

import bcrypt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from saas.config import load_settings
from saas.database import ApiKey, User, get_session

_settings = load_settings()

_SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

# bcrypt hashes at most 72 bytes of input; longer passwords are truncated.
_BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    """Encode a password to bytes, truncated to bcrypt's 72-byte limit.

    Args:
        password: The plaintext password.

    Returns:
        UTF-8 bytes, at most 72 bytes long.
    """
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt.

    Args:
        password: The plaintext password.

    Returns:
        A bcrypt hash string.
    """
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Args:
        password: The plaintext password.
        password_hash: The stored bcrypt hash.

    Returns:
        True if the password matches.
    """
    try:
        return bcrypt.checkpw(_password_bytes(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        A tuple of (full_key, key_hash, key_prefix). The full key is shown
        to the user once; only the hash is stored.
    """
    raw = secrets.token_urlsafe(32)
    full_key = f"vsk_{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:12]
    return full_key, key_hash, key_prefix


def hash_api_key(full_key: str) -> str:
    """Hash an API key for lookup.

    Args:
        full_key: The full API key string.

    Returns:
        The SHA-256 hex digest.
    """
    return hashlib.sha256(full_key.encode()).hexdigest()


def create_session_token(user_id: int) -> str:
    """Create a signed session token.

    Args:
        user_id: The user's ID.

    Returns:
        A signed token of the form "<user_id>.<expiry>.<signature>".
    """
    expiry = int(time.time()) + _SESSION_MAX_AGE
    payload = f"{user_id}.{expiry}"
    signature = _sign(payload)
    return f"{payload}.{signature}"


def verify_session_token(token: str) -> Optional[int]:
    """Verify a session token and return the user ID.

    Args:
        token: The signed session token.

    Returns:
        The user ID if valid and unexpired, else None.
    """
    try:
        user_id_str, expiry_str, signature = token.rsplit(".", 2)
    except ValueError:
        return None

    payload = f"{user_id_str}.{expiry_str}"
    if not hmac.compare_digest(signature, _sign(payload)):
        return None

    try:
        expiry = int(expiry_str)
        user_id = int(user_id_str)
    except ValueError:
        return None

    if expiry < int(time.time()):
        return None

    return user_id


def _sign(payload: str) -> str:
    """Compute an HMAC signature for a payload.

    Args:
        payload: The string to sign.

    Returns:
        Hex-encoded HMAC-SHA256 signature.
    """
    return hmac.new(
        _settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    """Resolve the current user from the session cookie.

    Args:
        request: The incoming request.
        session: Database session.

    Returns:
        The authenticated User.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    token = request.cookies.get("vibesafe_session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    user_id = verify_session_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session"
        )

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


def get_user_by_api_key(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    """Resolve the current user from an API key in the Authorization header.

    Args:
        authorization: The Authorization header ("Bearer vsk_...").
        session: Database session.

    Returns:
        The authenticated User.

    Raises:
        HTTPException: 401 if the key is missing, malformed, or revoked.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Use 'Authorization: Bearer vsk_...'",
        )

    full_key = authorization.split(" ", 1)[1].strip()
    key_hash = hash_api_key(full_key)

    api_key = session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked.is_(False))
    ).scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    user = session.get(User, api_key.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user
