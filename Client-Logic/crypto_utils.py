"""
crypto_utils.py — Client-Side Zero-Knowledge Encryption Utilities
Handles PBKDF2-HMAC-SHA256 key derivation and AES-256-GCM authenticated encryption.

Wire format per encrypted chunk: [12-byte nonce][16-byte tag][ciphertext]
"""

import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ── Constants ────────────────────────────────────────────────────────────────

NONCE_SIZE = 12   # 96-bit nonce (recommended for AES-GCM)
TAG_SIZE   = 16   # 128-bit authentication tag
HEADER_SIZE = NONCE_SIZE + TAG_SIZE  # 28 bytes of overhead per encrypted chunk


def derive_key(passphrase: str, email: str) -> bytes:
    """
    Derive a 256-bit AES key from a user passphrase and email using PBKDF2.

    The email is hashed to produce a deterministic salt, allowing the same
    key to be reconstructed on any device given the same passphrase + email
    without syncing salt material.
    """
    salt = hashlib.sha256(email.lower().strip().encode("utf-8")).digest()
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations=100_000,
        dklen=32,
    )


def encrypt_chunk(key: bytes, plaintext: bytes, nonce: bytes | None = None) -> tuple[bytes, bytes, bytes]:
    """
    Encrypt *plaintext* with AES-256-GCM.

    Args:
        key:       32-byte AES key.
        plaintext: Arbitrary-length plaintext bytes.
        nonce:     12-byte nonce.  A fresh random nonce is generated when None.

    Returns:
        (nonce, tag, ciphertext)  — all as raw ``bytes``.
    """
    if nonce is None:
        nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(key)
    # cryptography's encrypt() returns ciphertext || 16-byte tag
    ct_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    ciphertext = ct_with_tag[:-TAG_SIZE]
    tag = ct_with_tag[-TAG_SIZE:]
    return nonce, tag, ciphertext


def decrypt_chunk(key: bytes, nonce: bytes, tag: bytes, ciphertext: bytes) -> bytes:
    """
    Decrypt and authenticate an AES-GCM chunk.

    Raises ``cryptography.exceptions.InvalidTag`` if the ciphertext or tag
    has been tampered with.
    """
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext + tag, None)


def pack_encrypted(nonce: bytes, tag: bytes, ciphertext: bytes) -> bytes:
    """Serialize an encrypted chunk into the wire format: nonce‖tag‖ciphertext."""
    return nonce + tag + ciphertext


def unpack_encrypted(data: bytes) -> tuple[bytes, bytes, bytes]:
    """Deserialize the wire format back into (nonce, tag, ciphertext)."""
    return data[:NONCE_SIZE], data[NONCE_SIZE:HEADER_SIZE], data[HEADER_SIZE:]
