"""Cipher adapter using AES-256-GCM from the `cryptography` library.

Vetted primitive, never hand-rolled. The Rust adapter uses XChaCha20-Poly1305;
both satisfy the same Cipher port, and the vault header records ``NAME`` so a
vault is always opened with the cipher that sealed it.

Nonces are 96-bit random values. Each save draws a fresh one, and a vault is
re-sealed far fewer than the 2^32 times after which random GCM nonces start to
risk a collision.
"""
from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AesGcmCipher:
    NAME = "AES-256-GCM"
    NONCE_LEN = 12
    KEY_LEN = 32

    def _check_key(self, key) -> None:
        if len(key) != self.KEY_LEN:
            raise ValueError("AES-256-GCM needs a 32-byte key")

    def encrypt(self, key: bytes, plaintext: bytes, aad: bytes) -> tuple:
        self._check_key(key)
        nonce = os.urandom(self.NONCE_LEN)
        ct = AESGCM(bytes(key)).encrypt(nonce, plaintext, aad)
        return nonce, ct

    def decrypt(self, key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
        self._check_key(key)
        if len(nonce) != self.NONCE_LEN:
            raise ValueError("AES-256-GCM needs a 12-byte nonce")
        return AESGCM(bytes(key)).decrypt(nonce, ciphertext, aad)
