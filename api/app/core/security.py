import hashlib
import secrets

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()  # argon2
# Verified against when the username doesn't exist, so a wrong username takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    return _hasher.verify(password, password_hash or _DUMMY_HASH) and password_hash is not None


def new_session_token() -> tuple[str, str]:
    """Returns (token for the cookie, hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
