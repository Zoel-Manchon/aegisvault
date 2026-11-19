"""KeyDerivation adapter using stdlib scrypt (zero-dependency reference).

New vaults use Argon2id (Rust core or `cryptography`); scrypt stays for vaults
that were sealed with it and as the last fallback. Same KeyDerivation port.
"""
from __future__ import annotations

import hashlib

from ....domain.value_objects.kdf_params import KdfParams
from ....domain.value_objects.master_key import MasterKey


class ScryptKeyDerivation:
    ALGORITHMS = frozenset({"scrypt"})

    def derive(self, password: str, params: KdfParams) -> MasterKey:
        p = params.params
        n, r, par = p.get("n", 1 << 14), p.get("r", 8), p.get("p", 1)
        # OpenSSL refuses anything over 32 MiB unless maxmem says otherwise;
        # scrypt needs 128*r*N bytes for V plus 128*r*p for B.
        maxmem = 128 * r * (n + par + 2) + (1 << 20)
        key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=params.salt,
            n=n,
            r=r,
            p=par,
            dklen=params.length,
            maxmem=maxmem,
        )
        return MasterKey(key)
