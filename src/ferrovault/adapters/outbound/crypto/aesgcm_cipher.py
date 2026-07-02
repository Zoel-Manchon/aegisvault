"""Cipher adapter using AES-256-GCM from the `cryptography` library.

Vetted primitive, never hand-rolled. The Rust adapter uses XChaCha20-Poly1305;
both satisfy the same Cipher port, which is why the header stores the nonce
rather than assuming a fixed size.
"""
from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AesGcmCipher:
    NONCE_LEN = 12

    def encrypt(self, key: bytes, plaintext: bytes, aad: bytes) -> tuple:
        nonce = os.urandom(self.NONCE_LEN)
        ct = AESGCM(key).encrypt(nonce, plaintext, aad)
        return nonce, ct

    def decrypt(self, key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
