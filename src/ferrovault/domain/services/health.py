"""Vault health analysis: weak, reused, breached, old and 2FA-less entries.

Pure domain logic. Breach data (which needs the network) is computed by an
adapter and passed in, so this service stays deterministic and testable. The
report holds entry *names* only — never secrets.

Score: start at 100 and subtract per finding, weighted by severity and by how
many entries it affects (a breached password costs more than a missing 2FA).
It never drops just because the vault is large.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .password_strength import PasswordStrength

WEAK_BITS = 50
OLD_AFTER_DAYS = 365
# Points lost per affected entry.
PENALTY = {"breached": 12, "weak": 8, "reused": 6, "old": 2, "no_totp": 1}
_SECRET_KINDS = ("login", "api_key")


def _days_since(iso: str, now: datetime) -> int | None:
    if not iso:
        return None
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return max(0, (now - then).days)


@dataclass(frozen=True)
class HealthReport:
    total: int
    score: int
    weak: tuple = field(default_factory=tuple)
    reused: tuple = field(default_factory=tuple)        # tuple[tuple[str, ...]]
    breached: tuple = field(default_factory=tuple)      # tuple[tuple[str, int]]
    no_totp: tuple = field(default_factory=tuple)
    old: tuple = field(default_factory=tuple)           # tuple[tuple[str, int days]]
    weak_bits: tuple = field(default_factory=tuple)     # tuple[tuple[str, int bits]]

    @property
    def is_healthy(self) -> bool:
        return not (self.weak or self.reused or self.breached)

    @property
    def issue_count(self) -> int:
        return len(self.weak) + len(self.reused) + len(self.breached)

    @property
    def warning_count(self) -> int:
        """Everything worth a look, including old passwords and missing 2FA."""
        return self.issue_count + len(self.old) + len(self.no_totp)


class HealthAnalyzer:
    def __init__(self, strength: PasswordStrength | None = None):
        self._strength = strength or PasswordStrength()

    def analyze(self, entries, breached: dict | None = None, now_iso: str | None = None,
                old_after_days: int = OLD_AFTER_DAYS) -> HealthReport:
        breached = breached or {}
        now = datetime.now(timezone.utc)
        if now_iso:
            try:
                now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
                if now.tzinfo is None:
                    now = now.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        weak, weak_bits, no_totp, old = [], [], [], []
        by_secret: dict = {}

        for e in entries:
            kind = getattr(e, "kind", "login") or "login"
            if kind not in _SECRET_KINDS:
                continue
            pw = e.secret.reveal()
            bits = self._strength.bits(pw)
            if bits < WEAK_BITS:
                weak.append(e.name)
                weak_bits.append((e.name, int(round(bits))))
            if kind == "login" and e.totp is None:
                no_totp.append(e.name)
            age = _days_since(getattr(e, "password_changed_at", "") or getattr(e, "created_at", ""), now)
            if age is not None and age > old_after_days:
                old.append((e.name, age))
            by_secret.setdefault(pw, []).append(e.name)

        reused = tuple(tuple(sorted(names)) for names in by_secret.values()
                       if len(names) > 1)
        breached_list = tuple(sorted(
            ((name, count) for name, count in breached.items() if count > 0),
            key=lambda x: -x[1]))

        total = len(entries)
        penalty = (PENALTY["breached"] * len(breached_list) + PENALTY["weak"] * len(weak)
                   + PENALTY["reused"] * sum(len(g) for g in reused)
                   + PENALTY["old"] * len(old) + PENALTY["no_totp"] * len(no_totp))
        score = max(0, 100 - penalty) if total else 100

        return HealthReport(
            total=total, score=score, weak=tuple(weak), reused=reused,
            breached=breached_list, no_totp=tuple(no_totp),
            old=tuple(sorted(old, key=lambda x: -x[1])), weak_bits=tuple(weak_bits))
