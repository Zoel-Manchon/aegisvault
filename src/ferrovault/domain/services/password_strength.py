"""PasswordStrength domain service: an entropy estimate that discounts patterns.

The base estimate is length x log2(alphabet), which is what a brute-force
attacker faces against a truly random string. Human passwords are not random,
so before applying it we remove what a guessing attack tries first:

* well-known passwords ("123456", "password", "qwerty"...) score near zero;
* runs of one character ("aaaa") and keyboard or alphabet sequences
  ("abcd", "4321", "qwer") count as a single character;
* a trailing or leading year counts as two characters.

It is still a heuristic, not zxcvbn, and it errs on the side of scoring low.
"""
from __future__ import annotations

import math
import re
import string
from dataclasses import dataclass

_SYMBOLS = set("!@#$%^&*()-_=+[]{};:,.?/\\|<>\"'`~")

# Passwords at the top of every breach list, plus Spanish favourites.
_COMMON = frozenset("""
123456 1234567 12345678 123456789 1234567890 12345 1234 111111 000000 123123 654321 112233
password password1 passw0rd p@ssw0rd qwerty qwerty123 qwertyuiop asdf asdfgh asdfghjkl zxcvbn
abc123 abcdef iloveyou admin admin123 administrator root toor letmein welcome welcome1 monkey
dragon football baseball master shadow sunshine princess superman batman trustno1 starwars
login guest test test123 secret changeme default hello hello123 freedom whatever michael
contraseña contrasena clave clave123 hola hola123 hola1234 teamo tequiero amor amor123 barcelona
madrid realmadrid futbol españa espana mexico argentina colombia peru chile 1q2w3e4r 1qaz2wsx
zaq12wsx q1w2e3r4 aa123456 a123456 123qwe qwe123 pokemon naruto minecraft
""".split())

_SEQUENCES = (
    string.ascii_lowercase,
    string.digits,
    "qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890",
    "qwertzuiop", "azertyuiop",
)
_LEET = str.maketrans({"@": "a", "4": "a", "3": "e", "1": "i", "!": "i", "0": "o", "$": "s", "5": "s", "7": "t"})
_YEAR = re.compile(r"(19|20)\d{2}")


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
    if any(ord(c) > 127 for c in pw):
        size += 64          # accented letters, ñ, other scripts
    return size or 1


def _in_sequence(a: str, b: str) -> bool:
    a, b = a.lower(), b.lower()
    for seq in _SEQUENCES:
        i = seq.find(a)
        if i != -1 and i + 1 < len(seq) and seq[i + 1] == b:
            return True
        j = seq.find(b)
        if j != -1 and j + 1 < len(seq) and seq[j + 1] == a:
            return True
    return False


def _effective_length(pw: str) -> float:
    """Length after collapsing repeats, sequences and years."""
    if not pw:
        return 0.0
    length = 1.0
    run = 1
    for prev, cur in zip(pw, pw[1:]):
        if cur == prev or _in_sequence(prev, cur):
            run += 1
            # the first two characters of a run carry information, the rest little
            length += 0.0 if run > 2 else 1.0
        else:
            run = 1
            length += 1.0
    for match in _YEAR.finditer(pw):
        length -= 2.0       # a 4-digit year is about as guessable as 2 random digits
    return max(1.0, length)


@dataclass(frozen=True)
class StrengthAssessment:
    bits: int
    label: str                   # weak | fair | strong | very strong
    level: int                   # 0..4, one per meter segment filled
    pool: int
    length: int
    common: bool = False
    pattern_penalty: bool = False


class PasswordStrength:
    @staticmethod
    def _is_common(password: str) -> bool:
        lowered = password.lower()
        stripped = lowered.rstrip("0123456789!.*_-")      # "Barcelona2024!" -> "barcelona"
        candidates = {lowered, stripped, lowered.translate(_LEET), stripped.translate(_LEET)}
        return any(c in _COMMON for c in candidates if c)

    def bits(self, password: str) -> float:
        if not password:
            return 0.0
        if self._is_common(password):
            # a dictionary word plus a suffix: a few thousand guesses at most
            return min(20.0, 8.0 + len(password))
        return _effective_length(password) * math.log2(_pool_size(password))

    def label(self, password: str) -> str:
        return self._label_for(self.bits(password))

    @staticmethod
    def _label_for(b: float) -> str:
        if b < 40:
            return "weak"
        if b < 60:
            return "fair"
        if b < 80:
            return "strong"
        return "very strong"

    def assess(self, password: str) -> StrengthAssessment:
        b = self.bits(password)
        raw = len(password) * math.log2(_pool_size(password)) if password else 0.0
        level = 0 if not password else 1 if b < 40 else 2 if b < 60 else 3 if b < 80 else 4
        return StrengthAssessment(
            bits=int(round(b)),
            label=self._label_for(b),
            level=level,
            pool=_pool_size(password),
            length=len(password),
            common=bool(password) and self._is_common(password),
            pattern_penalty=bool(password) and b + 0.5 < raw,
        )
