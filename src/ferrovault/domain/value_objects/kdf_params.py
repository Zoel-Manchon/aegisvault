"""KdfParams value object: how the master key is derived (algo + salt + cost)."""
from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass, field


@dataclass(frozen=True)
class KdfParams:
    algorithm: str                     # "scrypt" | "argon2id"
    salt: bytes
    params: dict = field(default_factory=dict)
    length: int = 32

    @staticmethod
    def scrypt() -> "KdfParams":
        return KdfParams("scrypt", secrets.token_bytes(16),
                         {"n": 1 << 14, "r": 8, "p": 1})

    @staticmethod
    def argon2id() -> "KdfParams":
        # t=time cost, m=memory KiB, p=parallelism
        return KdfParams("argon2id", secrets.token_bytes(16),
                         {"t": 3, "m": 1 << 16, "p": 4})

    def to_dict(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "salt": base64.b64encode(self.salt).decode(),
            "params": self.params,
            "length": self.length,
        }

    @staticmethod
    def from_dict(d: dict) -> "KdfParams":
        return KdfParams(
            algorithm=d["algorithm"],
            salt=base64.b64decode(d["salt"]),
            params=d.get("params", {}),
            length=d.get("length", 32),
        )
