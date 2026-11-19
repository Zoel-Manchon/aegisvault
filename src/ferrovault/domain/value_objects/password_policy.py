"""PasswordPolicy value object: the rules a generated password must satisfy."""
from __future__ import annotations

from dataclasses import dataclass

AMBIGUOUS = frozenset("0OoIl1|`'\"")


@dataclass(frozen=True)
class PasswordPolicy:
    length: int = 20
    lower: bool = True
    upper: bool = True
    digits: bool = True
    symbols: bool = True
    avoid_ambiguous: bool = False   # drop 0 O o I l 1 | and quote marks

    def __post_init__(self):
        if self.length < 8:
            raise ValueError("password length must be >= 8")
        if self.length > 256:
            raise ValueError("password length must be <= 256")
        if not (self.lower or self.upper or self.digits or self.symbols):
            raise ValueError("at least one character class is required")

    @staticmethod
    def strong() -> "PasswordPolicy":
        return PasswordPolicy()


@dataclass(frozen=True)
class PassphrasePolicy:
    words: int = 6
    separator: str = "-"
    capitalize: bool = True
    add_digit: bool = True

    def __post_init__(self):
        if not 4 <= self.words <= 12:
            raise ValueError("a passphrase needs 4 to 12 words")
