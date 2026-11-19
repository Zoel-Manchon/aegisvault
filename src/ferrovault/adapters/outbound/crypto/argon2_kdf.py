"""KeyDerivation adapter: Argon2id from the `cryptography` library (OpenSSL 3.2+).

Gives the pure-Python build the same memory-hard KDF as the Rust core, so a
vault created without a Rust toolchain is not stuck with scrypt. Both follow
RFC 9106 (Argon2id, version 0x13, no secret or associated data), so for the
same password, salt and costs they derive the same key: a vault sealed by one
can be unlocked by the other.
"""
from __future__ import annotations

from ....domain.value_objects.kdf_params import KdfParams
from ....domain.value_objects.master_key import MasterKey

try:
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id as _Argon2id
    AVAILABLE = True
except ImportError:  # cryptography < 44
    _Argon2id = None
    AVAILABLE = False


class Argon2idKeyDerivation:
    ALGORITHMS = frozenset({"argon2id"})

    def derive(self, password: str, params: KdfParams) -> MasterKey:
        if _Argon2id is None:
            raise RuntimeError("Argon2id needs cryptography >= 44")
        p = params.params
        kdf = _Argon2id(
            salt=params.salt,
            length=params.length,
            iterations=p.get("t", 3),
            lanes=p.get("p", 4),
            memory_cost=p.get("m", 1 << 16),
        )
        return MasterKey(kdf.derive(password.encode("utf-8")))
