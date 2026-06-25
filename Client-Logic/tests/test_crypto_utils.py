import os

import pytest
from cryptography.exceptions import InvalidTag

from crypto_utils import (
    COMPRESSION_NONE,
    COMPRESSION_ZLIB,
    NONCE_SIZE,
    TAG_SIZE,
    compress_before_encrypt,
    decrypt_chunk,
    decompress_after_decrypt,
    derive_key,
    encrypt_chunk,
    pack_encrypted,
    unpack_encrypted,
)


class TestKeyDerivation:
    def test_derive_key_returns_32_bytes(self):
        key = derive_key("mypassphrase", "user@example.com")
        assert isinstance(key, bytes)
        assert len(key) == 32

    def test_derive_key_is_deterministic(self):
        k1 = derive_key("mypassphrase", "user@example.com")
        k2 = derive_key("mypassphrase", "user@example.com")
        assert k1 == k2

    def test_different_passphrases_produce_different_keys(self):
        k1 = derive_key("pass1", "user@example.com")
        k2 = derive_key("pass2", "user@example.com")
        assert k1 != k2

    def test_different_emails_produce_different_keys(self):
        k1 = derive_key("mypassphrase", "alice@example.com")
        k2 = derive_key("mypassphrase", "bob@example.com")
        assert k1 != k2


class TestEncryptDecrypt:
    def test_roundtrip(self):
        key = derive_key("testpass", "test@example.com")
        plaintext = b"Hello ShadowDrive!"
        nonce, tag, ciphertext = encrypt_chunk(key, plaintext)
        decrypted = decrypt_chunk(key, nonce, tag, ciphertext)
        assert decrypted == plaintext

    def test_encrypt_produces_unique_nonces(self):
        key = derive_key("testpass", "test@example.com")
        plaintext = b"Hello ShadowDrive!"
        n1, _, _ = encrypt_chunk(key, plaintext)
        n2, _, _ = encrypt_chunk(key, plaintext)
        assert n1 != n2

    def test_wrong_key_fails(self):
        key = derive_key("correctpass", "test@example.com")
        wrong_key = derive_key("wrongpass", "test@example.com")
        plaintext = b"secret data"
        nonce, tag, ciphertext = encrypt_chunk(key, plaintext)
        with pytest.raises(InvalidTag):
            decrypt_chunk(wrong_key, nonce, tag, ciphertext)

    def test_wrong_nonce_fails(self):
        key = derive_key("testpass", "test@example.com")
        plaintext = b"secret data"
        nonce, tag, ciphertext = encrypt_chunk(key, plaintext)
        bad_nonce = b"\x00" * NONCE_SIZE
        with pytest.raises(InvalidTag):
            decrypt_chunk(key, bad_nonce, tag, ciphertext)

    def test_empty_plaintext_roundtrip(self):
        key = derive_key("testpass", "test@example.com")
        nonce, tag, ciphertext = encrypt_chunk(key, b"")
        decrypted = decrypt_chunk(key, nonce, tag, ciphertext)
        assert decrypted == b""

    def test_large_plaintext_roundtrip(self):
        key = derive_key("testpass", "test@example.com")
        plaintext = os.urandom(1024 * 1024)
        nonce, tag, ciphertext = encrypt_chunk(key, plaintext)
        decrypted = decrypt_chunk(key, nonce, tag, ciphertext)
        assert decrypted == plaintext


class TestPackUnpack:
    def test_pack_unpack_roundtrip(self):
        nonce = os.urandom(NONCE_SIZE)
        tag = os.urandom(TAG_SIZE)
        ciphertext = b"\x01\x02\x03\x04"
        packed = pack_encrypted(nonce, tag, ciphertext)
        assert len(packed) == NONCE_SIZE + TAG_SIZE + len(ciphertext)
        n, t, c = unpack_encrypted(packed)
        assert n == nonce
        assert t == tag
        assert c == ciphertext

    def test_pack_short_data_does_not_raise(self):
        short = b"\x00" * 5
        n, t, c = unpack_encrypted(short)
        assert len(n) <= NONCE_SIZE


class TestCompression:
    def test_compress_decompress_roundtrip(self):
        data = b"Hello ShadowDrive! " * 100
        compressed = compress_before_encrypt(data)
        decompressed = decompress_after_decrypt(compressed)
        assert decompressed == data

    def test_compress_small_data_returns_uncompressed(self):
        data = b"small"
        compressed = compress_before_encrypt(data)
        assert compressed[0] == COMPRESSION_NONE
        assert compressed[1:] == data

    def test_compress_repetitive_data_returns_compressed(self):
        data = b"A" * 1000
        compressed = compress_before_encrypt(data)
        assert compressed[0] == COMPRESSION_ZLIB

    def test_decompress_after_decrypt_none_flag_returns_as_is(self):
        data = bytes([COMPRESSION_NONE]) + b"raw data"
        result = decompress_after_decrypt(data)
        assert result == b"raw data"

    def test_decompress_empty_data_returns_empty(self):
        assert decompress_after_decrypt(b"") == b""

    def test_encrypt_compressed_roundtrip(self):
        key = derive_key("testpass", "test@example.com")
        original = b"Hello ShadowDrive! " * 100
        compressed = compress_before_encrypt(original)
        nonce, tag, ciphertext = encrypt_chunk(key, compressed)
        decrypted_compressed = decrypt_chunk(key, nonce, tag, ciphertext)
        result = decompress_after_decrypt(decrypted_compressed)
        assert result == original
