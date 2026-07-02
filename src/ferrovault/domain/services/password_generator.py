"""PasswordGenerator domain service.

Generates passwords satisfying a PasswordPolicy using a CSPRNG. Pure domain
logic: no I/O. Uses `secrets` for cryptographic randomness.
"""
from __future__ import annotations

import secrets
import string

from ..value_objects.password_policy import PasswordPolicy

_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"


class PasswordGenerator:
    def generate(self, policy: PasswordPolicy) -> str:
        pools = []
        if policy.lower:
            pools.append(string.ascii_lowercase)
        if policy.upper:
            pools.append(string.ascii_uppercase)
        if policy.digits:
            pools.append(string.digits)
        if policy.symbols:
            pools.append(_SYMBOLS)

        alphabet = "".join(pools)
        # Reject samples that miss a required class (rare at length >= 8).
        while True:
            pw = "".join(secrets.choice(alphabet) for _ in range(policy.length))
            if all(any(c in pool for c in pw) for pool in pools):
                return pw
