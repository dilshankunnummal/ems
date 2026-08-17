"""
Password hashing and verification.

Uses the `bcrypt` library directly rather than through passlib's
`CryptContext`. passlib 1.7.x detects the bcrypt backend by reading
`bcrypt.__about__.__version__`, an attribute removed in bcrypt>=4.1.0 —
pairing passlib with a modern bcrypt raises a version-detection error
at hash time. Calling bcrypt directly avoids that incompatibility
entirely while keeping the same cost-factor control.

Centralized here so no feature hashes passwords itself — one hashing
policy (algorithm, work factor) enforced everywhere, upgradeable in a
single place later.
"""
import bcrypt

from app.shared.exceptions import BadRequestException

_BCRYPT_ROUNDS = 12
# bcrypt silently truncates input beyond 72 bytes; we reject instead so a
# very long password never gets silently weakened.
_BCRYPT_MAX_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > _BCRYPT_MAX_BYTES:
        raise BadRequestException(
            "Password must not exceed 72 bytes.", error_code="PASSWORD_TOO_LONG"
        )
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Returns False (never raises) on malformed hashes or oversized input
    so callers can treat every failure path identically without leaking
    why verification failed.
    """
    try:
        password_bytes = plain_password.encode("utf-8")
        if len(password_bytes) > _BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """True if the stored hash's cost factor no longer matches the
    configured `_BCRYPT_ROUNDS`, so it should be re-hashed on next
    successful login (e.g. after raising the work factor over time).
    """
    try:
        # bcrypt hash format: $2b$<cost>$<22-char-salt><31-char-hash>
        cost = int(hashed_password.split("$")[2])
        return cost != _BCRYPT_ROUNDS
    except (IndexError, ValueError):
        return True
