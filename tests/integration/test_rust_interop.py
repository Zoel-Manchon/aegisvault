"""Verifies the Rust crypto core when it's been built (skips otherwise).

Run `cd rust && maturin develop --release` first, then `pytest`. Proves the
Argon2id + XChaCha20-Poly1305 core round-trips and rejects tampering - the
contract the RustCipher/RustKeyDerivation adapters rely on.
"""
import os

import pytest

from ferrovault.adapters.outbound.crypto import rust_backend

pytestmark = pytest.mark.skipif(
    not rust_backend.AVAILABLE, reason="ferrocrypto extension not built")


def test_rust_aead_roundtrip():
    fc = rust_backend.ferrocrypto
    key = os.urandom(32)
    nonce, ct = fc.encrypt(key, b"top secret payload", b"header-aad")
    assert fc.decrypt(key, nonce, ct, b"header-aad") == b"top secret payload"


def test_rust_aead_rejects_wrong_aad():
    fc = rust_backend.ferrocrypto
    key = os.urandom(32)
    nonce, ct = fc.encrypt(key, b"payload", b"aad-A")
    with pytest.raises(Exception):
        fc.decrypt(key, nonce, ct, b"aad-B")


def test_rust_argon2_is_deterministic():
    fc = rust_backend.ferrocrypto
    salt = os.urandom(16)
    k1 = fc.derive_key(b"password", salt, 3, 1 << 16, 4, 32)
    k2 = fc.derive_key(b"password", salt, 3, 1 << 16, 4, 32)
    assert k1 == k2 and len(k1) == 32
