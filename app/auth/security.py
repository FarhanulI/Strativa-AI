"""Password hashing and opaque-token hashing helpers.

Password hashing uses Argon2id (the `argon2-cffi` default profile) rather
than bcrypt: it is the OWASP-recommended default for new systems, memory-
hard (bcrypt is not), and requires no extra "pepper" scheme to resist
GPU/ASIC cracking. `PasswordHasher()` defaults to Argon2id with
time_cost=3, memory_cost=64 MiB, parallelism=4 -- documented here as the
cost factor per the day's Definition of Done, not overridden.
"""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification via argon2's own comparison.

    Never raises on a wrong password -- callers must not be able to
    distinguish "wrong password" from "hash comparison failed" by
    exception type/timing.
    """
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed/legacy hash, etc. -- treat as a failed verification
        # rather than leaking an internal error to the caller.
        return False


def generate_opaque_token() -> str:
    """A high-entropy, URL-safe random token for refresh/reset tokens.

    Not a JWT: these are opaque, server-validated-only credentials whose
    hash (never the plaintext) is persisted, per the day's spec.
    """
    return secrets.token_urlsafe(48)


def hash_opaque_token(raw_token: str) -> str:
    """SHA-256 of a high-entropy opaque token, for indexed DB lookup.

    Argon2 is deliberately not used here: these tokens are already
    cryptographically random (not user-chosen, no brute-force risk), so a
    fast, deterministic hash that supports an equality-indexed lookup is
    the right tool -- an intentionally slow KDF would only add latency to
    every refresh/reset request.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def constant_time_hash_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
