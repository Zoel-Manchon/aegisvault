"""Crypto adapters backed by the Rust core (ferrocrypto, built via maturin).

Argon2id KDF + XChaCha20-Poly1305 AEAD + memory zeroization, all in Rust.
Import is optional: if the extension isn't built, the composition root falls
back to the pure-Python adapters. Both implement the same ports.
"""
from __future__ import annotations

from ....domain.value_objects.kdf_params import KdfParams
from ....domain.value_objects.master_key import MasterKey

try:
    import ferrocrypto  # built with `maturin develop` in ../rust
    # A bare namespace dir can satisfy the import without the functions, so
    # confirm the real extension is loaded before trusting it.
    AVAILABLE = hasattr(ferrocrypto, "derive_key") and hasattr(ferrocrypto, "encrypt")
except ImportError:
    ferrocrypto = None
    AVAILABLE = False


class RustKeyDerivation:
    def derive(self, password: str, params: KdfParams) -> MasterKey:
        p = params.params
        key = ferrocrypto.derive_key(
            password.encode("utf-8"), params.salt,
            p.get("t", 3), p.get("m", 1 << 16), p.get("p", 4), params.length)
        return MasterKey(key)


class RustCipher:
    def encrypt(self, key: bytes, plaintext: bytes, aad: bytes) -> tuple:
        return ferrocrypto.encrypt(key, plaintext, aad)

    def decrypt(self, key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
        return ferrocrypto.decrypt(key, nonce, ciphertext, aad)
