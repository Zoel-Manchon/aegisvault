"""KdfParams value object: how the master key is derived (algo + salt + cost).

The header that carries these parameters is read *before* anything can be
authenticated, so ``from_dict`` treats it as untrusted input: unknown
algorithms, short salts and absurd costs are rejected instead of being handed
to the KDF (a crafted header could otherwise ask scrypt or Argon2 for many
gigabytes of memory).
"""
from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass, field

# RFC 9106 Argon2id with more memory than its "second recommended" profile
# (64 MiB): 256 MiB, 3 passes, 4 lanes. About 0.3 s on a desktop CPU.
ARGON2ID_DEFAULT = {"t": 3, "m": 1 << 18, "p": 4}
# OWASP floor for scrypt is N=2^17, r=8, p=1 (128 MiB). Only used when the
# installed `cryptography` has no Argon2id.
SCRYPT_STRONG = {"n": 1 << 17, "r": 8, "p": 1}
# The original default. Kept so existing vaults and fast tests keep working;
# a vault sealed with it is re-sealed with stronger parameters on unlock.
SCRYPT_LEGACY = {"n": 1 << 14, "r": 8, "p": 1}

MIN_SALT_LEN = 16
KEY_LEN = 32

# Inclusive bounds accepted from a vault header.
_BOUNDS = {
    "argon2id": {"t": (1, 64), "m": (8 * 1024, 4 * 1024 * 1024), "p": (1, 64)},  # m in KiB, up to 4 GiB
    "scrypt": {"n": (2, 1 << 22), "r": (1, 32), "p": (1, 16)},
}


@dataclass(frozen=True)
class KdfParams:
    algorithm: str                     # "scrypt" | "argon2id"
    salt: bytes
    params: dict = field(default_factory=dict)
    length: int = KEY_LEN

    @staticmethod
    def scrypt(strong: bool = False) -> "KdfParams":
        cost = SCRYPT_STRONG if strong else SCRYPT_LEGACY
        return KdfParams("scrypt", secrets.token_bytes(MIN_SALT_LEN), dict(cost))

    @staticmethod
    def scrypt_strong() -> "KdfParams":
        return KdfParams.scrypt(strong=True)

    @staticmethod
    def argon2id() -> "KdfParams":
        # t=time cost, m=memory KiB, p=parallelism
        return KdfParams("argon2id", secrets.token_bytes(MIN_SALT_LEN), dict(ARGON2ID_DEFAULT))

    def to_dict(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "salt": base64.b64encode(self.salt).decode(),
            "params": self.params,
            "length": self.length,
        }

    @staticmethod
    def from_dict(d: dict) -> "KdfParams":
        try:
            algorithm = str(d["algorithm"])
            salt = base64.b64decode(d["salt"], validate=True)
            raw = d.get("params", {}) or {}
            length = int(d.get("length", KEY_LEN))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("malformed KDF parameters in the vault header") from exc
        bounds = _BOUNDS.get(algorithm)
        if bounds is None:
            raise ValueError(f"unsupported key derivation algorithm: {algorithm!r}")
        if len(salt) < MIN_SALT_LEN:
            raise ValueError("the vault header carries a salt shorter than 16 bytes")
        if length != KEY_LEN:
            raise ValueError("the vault header asks for a key that is not 32 bytes")
        params: dict = {}
        for name, (low, high) in bounds.items():
            value = raw.get(name, _default_for(algorithm, name))
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"unsafe {algorithm} parameter {name}={value!r} in the vault header")
            params[name] = value
        if algorithm == "scrypt" and params["n"] & (params["n"] - 1):
            raise ValueError("scrypt N must be a power of two")
        return KdfParams(algorithm=algorithm, salt=salt, params=params, length=length)

    def weaker_than(self, target: "KdfParams") -> bool:
        """True when these parameters should be replaced by ``target``'s.

        A different algorithm counts as weaker only when the target is Argon2id
        (the preferred KDF); within one algorithm any lower cost counts.
        """
        if self.algorithm != target.algorithm:
            return target.algorithm == "argon2id"
        mine, theirs = self.params, target.params
        if self.algorithm == "argon2id":
            return mine.get("m", 0) < theirs.get("m", 0) or mine.get("t", 0) < theirs.get("t", 0)
        return mine.get("n", 0) < theirs.get("n", 0) or mine.get("r", 0) < theirs.get("r", 0)

    def describe(self) -> str:
        """Short human summary, e.g. ``Argon2id · m=256 MiB · t=3 · p=4``."""
        p = self.params
        if self.algorithm == "argon2id":
            return f"Argon2id · m={p.get('m', 0) // 1024} MiB · t={p.get('t')} · p={p.get('p')}"
        n = p.get("n", 0)
        return f"scrypt · N=2^{max(n, 1).bit_length() - 1} · r={p.get('r')} · p={p.get('p')}"


# What the original adapters assumed when a header omitted a cost field, so an
# old vault with a sparse header still derives the same key.
_ARGON2ID_LEGACY = {"t": 3, "m": 1 << 16, "p": 4}


def _default_for(algorithm: str, name: str) -> int:
    source = _ARGON2ID_LEGACY if algorithm == "argon2id" else SCRYPT_LEGACY
    return source[name]
