"""Legacy password policy and session-bound JWTs with explicit revocation."""

import hashlib
import secrets
import time
import unicodedata
from dataclasses import dataclass

import bcrypt
import jwt

from app.core.errors import AuthenticationFailed, InvalidInput


def valid_password(password: str) -> bool:
    letters = 0
    number = upper = special = False
    for char in password:
        category = unicodedata.category(char)
        if category.startswith("N"):
            number = True
        elif category == "Lu":
            upper = True
            letters += 1
        elif category[0] in {"P", "S"}:
            special = True
        elif category.startswith("L") or char == " ":
            letters += 1
        else:
            return False
    return letters >= 7 and number and upper and special


def hash_password(password: str) -> bytes:
    if len(password.encode()) > 72:
        raise InvalidInput("Password must be at most 72 UTF-8 bytes")
    try:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10))
    except ValueError as error:
        raise InvalidInput("Invalid password") from error


def verify_password(password: str, stored: bytes | str) -> bool:
    encoded = stored.encode() if isinstance(stored, str) else stored
    try:
        if len(password.encode()) > 72:
            raise InvalidInput("Password must be at most 72 UTF-8 bytes")
        return bcrypt.checkpw(password.encode(), encoded)
    except ValueError:
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class AccessClaims:
    user_id: int
    session_id: str


class TokenService:
    def __init__(self, secret: str, ttl_seconds: int = 900):
        if not secret or ttl_seconds <= 0:
            raise ValueError("JWT secret and positive TTL are required")
        self.secret = secret
        self.ttl_seconds = ttl_seconds

    def create(self, user_id: int, username: str, session_id: str) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "ID": user_id,
                "Username": username,
                "iat": now,
                "exp": now + self.ttl_seconds,
                "sid": session_id,
                "type": "access",
            },
            self.secret,
            algorithm="HS256",
        )

    def verify(self, token: str) -> AccessClaims:
        try:
            claims = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                options={"require": ["ID", "Username", "iat", "exp", "sid", "type"]},
            )
            user_id, session_id = claims["ID"], claims["sid"]
            if type(user_id) is not int or not 0 < user_id < 2**63:
                raise ValueError("Invalid user ID")
            if (
                not isinstance(claims["Username"], str)
                or not isinstance(session_id, str)
                or not session_id
                or claims["type"] != "access"
                or type(claims["exp"]) is not int
                or type(claims["iat"]) is not int
                or claims["exp"] <= claims["iat"]
            ):
                raise ValueError("Invalid access claims")
            return AccessClaims(user_id, session_id)
        except (jwt.InvalidTokenError, ValueError, TypeError) as error:
            raise AuthenticationFailed("Invalid JWT token") from error
