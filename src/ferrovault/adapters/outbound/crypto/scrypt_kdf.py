"""KeyDerivation adapter using stdlib scrypt (zero-dependency reference).

The Rust adapter uses Argon2id; this stdlib scrypt path keeps the project
runnable and CI-green without the compiled extension. Same KeyDerivation port.
"""
from __future__ import annotations

import hashlib

from ....domain.value_objects.kdf_params import KdfParams
from ....domain.value_objects.master_key import MasterKey


class ScryptKeyDerivation:
    def derive(self, password: str, params: KdfParams) -> MasterKey:
        p = params.params
        key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=params.salt,
            n=p.get("n", 1 << 14),
            r=p.get("r", 8),
            p=p.get("p", 1),
            dklen=params.length,
            maxmem=0,
        )
        return MasterKey(key)
