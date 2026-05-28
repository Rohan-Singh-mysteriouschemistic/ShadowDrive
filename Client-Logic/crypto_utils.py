"""
crypto_utils.py — Client-Side Zero-Knowledge Encryption Utilities

This module handles PBKDF2-HMAC-SHA256 password-based key derivation 
and AES-256-GCM authenticated encryption/decryption routines for secure 
file chunking.

Wire format per encrypted chunk:
[ 12-byte nonce ] [ 16-byte tag ] [ Arbitrary ciphertext ]
"""

import hashlib
import os
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ─── Cryptographic Constants ─────────────────────────────────────────────────

NONCE_SIZE: int = 12   # 96-bit nonce (NIST recommended length for GCM)
TAG_SIZE: int = 16     # 128-bit authentication tag
HEADER_SIZE: int = NONCE_SIZE + TAG_SIZE  # 28 bytes of structural overhead


# ─── Key Derivation ──────────────────────────────────────────────────────────

def derive_key(passphrase: str, email: str) -> bytes:
    """
    Derives a cryptographically strong 256-bit AES key from a user passphrase.

    Utilizes the user's normalized email address as a globally unique, 
    deterministic salt via PBKDF2-HMAC-SHA256 stretched over 100,000 iterations.
    This guarantees that identical passphrases generate completely distinct keys 
    across different user accounts without requiring separate salt storage.

    Args:
        passphrase (str): The raw, human-readable user passphrase.
        email (str): The user's account email address used for salt generation.

    Returns:
        bytes: A cryptographically secure 32-byte (256-bit) symmetric key.
    """
    normalized_email = email.lower().strip().encode("utf-8")
    salt = hashlib.sha256(normalized_email).digest()
    
    return hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=passphrase.encode("utf-8"),
        salt=salt,
        iterations=100_000,
        dklen=32,
    )


# ─── Encryption & Decryption Engine ──────────────────────────────────────────

def encrypt_chunk(
    key: bytes, 
    plaintext: bytes, 
    nonce: Optional[bytes] = None
) -> Tuple[bytes, bytes, bytes]:
    """
    Encrypts a raw file chunk using authenticated AES-256-GCM encryption.

    Args:
        key (bytes): The 32-byte symmetric AES key.
        plaintext (bytes): The raw, unencrypted chunk payload.
        nonce (Optional[bytes]): An optional pre-defined 12-byte nonce. If None,
            a unique cryptographic nonce is securely generated using os.urandom.

    Returns:
        Tuple[bytes, bytes, bytes]: A structured tuple containing:
            - nonce (bytes): The 12-byte initialization vector used.
            - tag (bytes): The 16-byte integrity verification tag.
            - ciphertext (bytes): The resulting encrypted chunk payload.
    """
    if nonce is None:
        nonce = os.urandom(NONCE_SIZE)
        
    aesgcm = AESGCM(key)
    # The cryptography library natively appends the tag to the ciphertext
    ct_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    
    ciphertext = ct_with_tag[:-TAG_SIZE]
    tag = ct_with_tag[-TAG_SIZE:]
    
    return nonce, tag, ciphertext


def decrypt_chunk(key: bytes, nonce: bytes, tag: bytes, ciphertext: bytes) -> bytes:
    """
    Decrypts and validates the integrity of an AES-256-GCM ciphertext payload.

    Args:
        key (bytes): The 32-byte symmetric AES key.
        nonce (bytes): The unique 12-byte nonce associated with this chunk.
        tag (bytes): The 16-byte authentication tag generated at encryption.
        ciphertext (bytes): The raw encrypted static payload.

    Raises:
        cryptography.exceptions.InvalidTag: If the cipher text, tag, or nonce 
            fails mathematical verification, indicating corruption or tampering.

    Returns:
        bytes: The successfully authenticated, decrypted raw plaintext chunk.
    """
    aesgcm = AESGCM(key)
    # Re-attach tag to ciphertext payload for underlying cryptographical validation
    return aesgcm.decrypt(nonce, ciphertext + tag, None)


# ─── Serialization & Wire Formatting ─────────────────────────────────────────

def pack_encrypted(nonce: bytes, tag: bytes, ciphertext: bytes) -> bytes:
    """
    Serializes individual cryptographic segments into a unified wire format packet.

    Format: [12 Bytes Nonce] + [16 Bytes Tag] + [Variable Length Ciphertext]

    Args:
        nonce (bytes): The 12-byte initialization vector.
        tag (bytes): The 16-byte authentication signature.
        ciphertext (bytes): The encrypted payload.

    Returns:
        bytes: The packed, sequential byte payload ready for network transit.
    """
    return nonce + tag + ciphertext


def unpack_encrypted(data: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Deserializes a unified wire-format byte packet back into separate components.

    Args:
        data (bytes): The raw byte sequence downloaded from the storage target.

    Returns:
        Tuple[bytes, bytes, bytes]: A structured slice containing:
            - nonce (bytes): Extracted 12-byte initialization vector.
            - tag (bytes): Extracted 16-byte authentication tag.
            - ciphertext (bytes): Extracted raw ciphertext body.
    """
    return data[:NONCE_SIZE], data[NONCE_SIZE:HEADER_SIZE], data[HEADER_SIZE:]