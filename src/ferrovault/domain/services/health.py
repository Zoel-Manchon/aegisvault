"""Vault health analysis: weak, reused, breached, and 2FA-less entries.

Pure domain logic. Breach data (which needs the network) is computed by an
adapter and passed in, so this service stays deterministic and testable. The
report holds entry *names* only — never secrets.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .password_strength import PasswordStrength

WEAK_BITS = 50


@dataclass(frozen=True)
class HealthReport:
    total: int
    score: int
    weak: tuple = field(default_factory=tuple)
    reused: tuple = field(default_factory=tuple)        # tuple[tuple[str, ...]]
    breached: tuple = field(default_factory=tuple)      # tuple[tuple[str, int]]
    no_totp: tuple = field(default_factory=tuple)

    @property
    def is_healthy(self) -> bool:
        return not (self.weak or self.reused or self.breached)

    @property
    def issue_count(self) -> int:
        return len(self.weak) + len(self.reused) + len(self.breached)


class HealthAnalyzer:
    def __init__(self, strength: PasswordStrength | None = None):
        self._strength = strength or PasswordStrength()

    def analyze(self, entries, breached: dict | None = None) -> HealthReport:
        breached = breached or {}
        weak, no_totp = [], []
        by_secret: dict = {}

        for e in entries:
            pw = e.secret.reveal()
            if self._strength.bits(pw) < WEAK_BITS:
                weak.append(e.name)
            if e.totp is None:
                no_totp.append(e.name)
            by_secret.setdefault(pw, []).append(e.name)

        reused = tuple(tuple(sorted(names)) for names in by_secret.values()
                       if len(names) > 1)
        breached_list = tuple(sorted(
            ((name, count) for name, count in breached.items() if count > 0),
            key=lambda x: -x[1]))

        total = len(entries)
        penalty = (12 * len(breached_list) + 8 * len(weak)
                   + 6 * sum(len(g) for g in reused) + 1 * len(no_totp))
        score = max(0, 100 - penalty) if total else 100

        return HealthReport(
            total=total, score=score, weak=tuple(weak), reused=reused,
            breached=breached_list, no_totp=tuple(no_totp))
