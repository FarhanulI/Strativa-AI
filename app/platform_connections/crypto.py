"""Application-level envelope encryption for platform OAuth credentials.

Day 23. Every access/refresh token this module handles is encrypted by the
application before it leaves the process -- both the final token persisted
in Postgres and the short-lived user-level token parked in Redis during the
destination-selection step. A bare database column (or a Postgres-side
`pgcrypto` call) is deliberately not used: the key would then live in, or
travel through, the database itself, so a database backup or a read replica
would carry decryptable credentials.

Scheme
------

Envelope encryption, two layers:

1. A fresh 256-bit **data encryption key (DEK)** is generated per
   encryption call and used to AES-256-GCM the plaintext token.
2. The DEK itself is AES-256-GCM-encrypted ("wrapped") under a
   **key encryption key (KEK)** supplied by the deployment's secrets
   manager through `settings.token_encryption_keys`.

Only wrapped DEKs are ever stored. The KEK never touches the database or
Redis.

Ciphertext format (one opaque ASCII string, safe for a text column):

    v1.<key_id>.<b64url(wrap_nonce || wrapped_dek)>.<b64url(data_nonce || ciphertext)>

`key_id` is carried **inside** the ciphertext rather than in a separate
column, which is what makes this design rotation-compatible:

Key rotation (compatible, though rotation itself is out of scope this day)
--------------------------------------------------------------------------

`settings.token_encryption_keys` is a keyring (`key_id -> base64 32-byte
key`), not a single key, and `settings.token_encryption_active_key_id`
selects which one *new* ciphertext is written under. Because every stored
blob names the `key_id` that wrapped its DEK, a rotation is:

1. Add the new key to the keyring alongside the old one and point
   `token_encryption_active_key_id` at it. Reads keep working immediately --
   old blobs still resolve their old `key_id` from the keyring.
2. Re-encrypt at leisure (a background pass, or lazily on the next token
   refresh, since `decrypt` + `encrypt` already runs on every refresh).
3. Drop the retired key from the keyring once no blob references it.

No column, migration, or table rewrite is involved, and no re-encryption
has to happen inside the rotation window. Only the KEK rotates this way;
DEKs are per-value and already rotate on every write.
"""

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_SCHEME_VERSION = "v1"
_NONCE_BYTES = 12
_DEK_BYTES = 32


class TokenEncryptionError(RuntimeError):
    """Raised when a credential cannot be encrypted or decrypted.

    Deliberately carries no plaintext, no ciphertext, and no key material in
    its message -- it is allowed to reach a log line.
    """


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _load_kek(key_id: str) -> bytes:
    encoded = settings.token_encryption_keys.get(key_id)
    if encoded is None:
        raise TokenEncryptionError(f"No token encryption key configured for key id '{key_id}'")
    try:
        key = _b64d(encoded)
    except (ValueError, TypeError) as error:
        raise TokenEncryptionError(
            f"Token encryption key '{key_id}' is not valid base64"
        ) from error
    if len(key) != _DEK_BYTES:
        raise TokenEncryptionError(
            f"Token encryption key '{key_id}' must be {_DEK_BYTES} bytes, got {len(key)}"
        )
    return key


def encrypt_token(plaintext: str) -> str:
    """Envelope-encrypt `plaintext` under the currently active KEK."""
    if not plaintext:
        raise TokenEncryptionError("Refusing to encrypt an empty credential")

    key_id = settings.token_encryption_active_key_id
    kek = _load_kek(key_id)

    dek = os.urandom(_DEK_BYTES)
    data_nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(dek).encrypt(data_nonce, plaintext.encode("utf-8"), None)

    wrap_nonce = os.urandom(_NONCE_BYTES)
    wrapped_dek = AESGCM(kek).encrypt(wrap_nonce, dek, None)

    return ".".join(
        (
            _SCHEME_VERSION,
            key_id,
            _b64e(wrap_nonce + wrapped_dek),
            _b64e(data_nonce + ciphertext),
        )
    )


def decrypt_token(blob: str) -> str:
    """Reverse `encrypt_token`, resolving the KEK from the blob's own key id."""
    if not blob:
        raise TokenEncryptionError("Refusing to decrypt an empty credential")

    parts = blob.split(".")
    if len(parts) != 4 or parts[0] != _SCHEME_VERSION:
        raise TokenEncryptionError("Stored credential is not in the expected envelope format")

    _, key_id, wrapped, payload = parts
    kek = _load_kek(key_id)

    try:
        wrapped_raw = _b64d(wrapped)
        payload_raw = _b64d(payload)
        dek = AESGCM(kek).decrypt(wrapped_raw[:_NONCE_BYTES], wrapped_raw[_NONCE_BYTES:], None)
        plaintext = AESGCM(dek).decrypt(
            payload_raw[:_NONCE_BYTES], payload_raw[_NONCE_BYTES:], None
        )
    except (InvalidTag, ValueError, TypeError) as error:
        raise TokenEncryptionError("Stored credential could not be decrypted") from error

    return plaintext.decode("utf-8")


def encrypt_optional(plaintext: str | None) -> str | None:
    """`encrypt_token` for a nullable credential (a refresh token that a
    platform simply doesn't issue -- see `app/platform_connections/oauth`
    on the Facebook/Instagram Page-token lifecycle).
    """
    return None if plaintext is None else encrypt_token(plaintext)
