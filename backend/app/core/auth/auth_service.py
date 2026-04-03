"""
GrimmGear Mediarr — Authentication Service
JWT-based auth with local accounts and role-based access control.
"""

import hashlib
import hmac
import json
import logging
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Optional

from fastapi import Depends, HTTPException, Request

from app.core.config import settings

logger = logging.getLogger("grimmgear.auth")


def _b64_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    return urlsafe_b64decode(data + "=" * padding)


class AuthService:
    """Simple JWT auth without external dependencies."""

    def __init__(self):
        self._secret = settings.server.secret_key
        self._setup_done = False

    def hash_password(self, password: str) -> str:
        salt = hashlib.sha256(self._secret.encode()).hexdigest()[:16]
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()

    def verify_password(self, password: str, hashed: str) -> bool:
        return self.hash_password(password) == hashed

    def create_token(self, user_id: int, username: str, role: str, expires_hours: int = 24) -> str:
        """Create a simple JWT-like token."""
        header = _b64_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload_data = {
            "sub": user_id,
            "username": username,
            "role": role,
            "exp": int(time.time()) + expires_hours * 3600,
        }
        payload = _b64_encode(json.dumps(payload_data).encode())
        sig = hmac.new(self._secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
        return f"{header}.{payload}.{sig}"

    def decode_token(self, token: str) -> Optional[dict]:
        """Decode and verify a token."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header, payload, sig = parts
            expected_sig = hmac.new(self._secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None
            data = json.loads(_b64_decode(payload))
            if data.get("exp", 0) < time.time():
                return None
            return data
        except Exception:
            return None

    @property
    def is_setup(self) -> bool:
        return self._setup_done

    @is_setup.setter
    def is_setup(self, value: bool):
        self._setup_done = value


# Singleton
auth_service = AuthService()


async def get_current_user(request: Request) -> Optional[dict]:
    """Extract user from Authorization header. Returns None if no auth."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    user = auth_service.decode_token(token)
    if not user:
        raise HTTPException(401, "Invalid or expired token")
    return user


async def get_optional_user(request: Request) -> Optional[dict]:
    """Like get_current_user but doesn't raise on missing auth."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    return auth_service.decode_token(token)
