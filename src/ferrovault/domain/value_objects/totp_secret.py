"""TotpSecret value object: a 2FA seed that knows how to produce its code.

Implements RFC 6238 (TOTP) over RFC 4226 (HOTP). A value object with intrinsic
behaviour - given a timestamp it yields the current one-time code. Pure: the
*timestamp* is supplied by the application via the Clock port, so the domain
stays deterministic and testable.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from dataclasses import dataclass

_ALGORITHMS = {
    "SHA1": hashlib.sha1,
    "SHA256": hashlib.sha256,
    "SHA512": hashlib.sha512,
}


def generate_base32_seed(num_bytes: int = 20) -> str:
    """A fresh random base32 TOTP seed (160-bit default, RFC-recommended)."""
    return base64.b32encode(secrets.token_bytes(num_bytes)).decode("ascii").rstrip("=")


@dataclass(frozen=True)
class TotpSecret:
    secret: str               # base32-encoded seed
    digits: int = 6
    period: int = 30
    algorithm: str = "SHA1"

    def __post_init__(self):
        if self.algorithm not in _ALGORITHMS:
            raise ValueError(f"unsupported TOTP algorithm: {self.algorithm}")
        try:
            base64.b32decode(self._normalized())
        except Exception as exc:
            raise ValueError("invalid base32 TOTP secret") from exc

    def _normalized(self) -> str:
        s = self.secret.strip().replace(" ", "").upper()
        return s + "=" * ((-len(s)) % 8)        # pad to a multiple of 8

    def code_at(self, timestamp: int) -> str:
        counter = int(timestamp) // self.period
        key = base64.b32decode(self._normalized())
        digest = hmac.new(key, struct.pack(">Q", counter),
                          _ALGORITHMS[self.algorithm]).digest()
        offset = digest[-1] & 0x0F
        truncated = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
        return str(truncated % (10 ** self.digits)).zfill(self.digits)

    def seconds_remaining(self, timestamp: int) -> int:
        return self.period - (int(timestamp) % self.period)

    @classmethod
    def generate(cls, num_bytes: int = 20) -> "TotpSecret":
        return cls(generate_base32_seed(num_bytes))
