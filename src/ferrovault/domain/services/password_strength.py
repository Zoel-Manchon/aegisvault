"""PasswordStrength domain service: a quick entropy-based estimate."""
from __future__ import annotations

import math
import string

_SYMBOLS = set("!@#$%^&*()-_=+[]{};:,.?/\\|<>\"'`~")


def _pool_size(pw: str) -> int:
    size = 0
    if any(c in string.ascii_lowercase for c in pw):
        size += 26
    if any(c in string.ascii_uppercase for c in pw):
        size += 26
    if any(c in string.digits for c in pw):
        size += 10
    if any(c in _SYMBOLS for c in pw):
        size += len(_SYMBOLS)
    return size or 1


class PasswordStrength:
    def bits(self, password: str) -> float:
        return len(password) * math.log2(_pool_size(password))

    def label(self, password: str) -> str:
        b = self.bits(password)
        if b < 40:
            return "weak"
        if b < 60:
            return "fair"
        if b < 80:
            return "strong"
        return "very strong"
