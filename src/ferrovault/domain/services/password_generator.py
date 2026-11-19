"""PasswordGenerator domain service.

Generates passwords and passphrases with a CSPRNG (`secrets`). Pure domain
logic, no I/O. ``secrets.choice`` draws without modulo bias, and the
rejection loop below only re-draws whole passwords, so every accepted
password is uniform over the ones that satisfy the policy.
"""
from __future__ import annotations

import math
import secrets
import string

from ..value_objects.password_policy import AMBIGUOUS, PassphrasePolicy, PasswordPolicy
from .wordlist import WORDS

_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"


def _pools(policy: PasswordPolicy) -> list[str]:
    pools = []
    if policy.lower:
        pools.append(string.ascii_lowercase)
    if policy.upper:
        pools.append(string.ascii_uppercase)
    if policy.digits:
        pools.append(string.digits)
    if policy.symbols:
        pools.append(_SYMBOLS)
    if policy.avoid_ambiguous:
        pools = ["".join(c for c in pool if c not in AMBIGUOUS) for pool in pools]
    return [p for p in pools if p]


class PasswordGenerator:
    def generate(self, policy: PasswordPolicy) -> str:
        pools = _pools(policy)
        alphabet = "".join(pools)
        # Reject samples that miss a required class (rare at length >= 8).
        while True:
            pw = "".join(secrets.choice(alphabet) for _ in range(policy.length))
            if all(any(c in pool for c in pw) for pool in pools):
                return pw

    @staticmethod
    def entropy_bits(policy: PasswordPolicy) -> float:
        """Entropy of a password drawn under ``policy`` (alphabet ** length)."""
        return policy.length * math.log2(len("".join(_pools(policy))))

    def passphrase(self, policy: PassphrasePolicy | None = None) -> str:
        policy = policy or PassphrasePolicy()
        words = [secrets.choice(WORDS) for _ in range(policy.words)]
        if policy.capitalize:
            words = [w.capitalize() for w in words]
        if policy.add_digit:
            i = secrets.randbelow(len(words))
            words[i] = words[i] + str(secrets.randbelow(10))
        return policy.separator.join(words)

    @staticmethod
    def passphrase_bits(policy: PassphrasePolicy | None = None) -> float:
        policy = policy or PassphrasePolicy()
        bits = policy.words * math.log2(len(WORDS))
        if policy.add_digit:
            bits += math.log2(10 * policy.words)
        return bits
