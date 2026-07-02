"""PasswordPolicy value object: the rules a generated password must satisfy."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PasswordPolicy:
    length: int = 20
    lower: bool = True
    upper: bool = True
    digits: bool = True
    symbols: bool = True

    def __post_init__(self):
        if self.length < 8:
            raise ValueError("password length must be >= 8")
        if not (self.lower or self.upper or self.digits or self.symbols):
            raise ValueError("at least one character class is required")

    @staticmethod
    def strong() -> "PasswordPolicy":
        return PasswordPolicy()
