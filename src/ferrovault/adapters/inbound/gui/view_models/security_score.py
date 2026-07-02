"""Fast metadata-first security score for live dashboards.

The full domain health report has to reveal secrets to detect weak/reused
passwords.  That is valuable, but too expensive and sensitive for every startup
or section switch.  This model uses only already-decrypted entry metadata and
rotation findings, so it is safe to calculate live and animate in QML.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class SecurityScoreSnapshot:
    score: int
    total: int
    twofa_percent: int
    high_sensitivity: int
    active_grants: int
    overdue_rotations: int
    deleted: int
    warnings: tuple[str, ...]

    @property
    def grade(self) -> str:
        if self.score >= 90:
            return "Excellent"
        if self.score >= 75:
            return "Good"
        if self.score >= 55:
            return "Watch"
        return "At risk"


def build_security_score(entries: Iterable[Any], rotation_findings: Iterable[Any] = ()) -> SecurityScoreSnapshot:
    active = [e for e in entries if not getattr(e, "deleted", False)]
    total = len(active)
    if total == 0:
        return SecurityScoreSnapshot(100, 0, 100, 0, 0, 0, 0, ("Vault is empty",))

    with_2fa = sum(1 for e in active if getattr(e, "has_totp", False))
    twofa_percent = round((with_2fa / total) * 100)
    high = sum(1 for e in active if getattr(e, "sensitivity", "standard") in {"high", "critical"})
    grants = sum(int(getattr(e, "active_share_count", 0)) for e in active)
    deleted = sum(1 for e in entries if getattr(e, "deleted", False))
    overdue = sum(1 for f in rotation_findings or () if getattr(f, "status", "") == "overdue")
    unknown = sum(1 for f in rotation_findings or () if getattr(f, "status", "") == "unknown")

    penalty = 0
    penalty += max(0, total - with_2fa) * 3
    penalty += high * 2 if twofa_percent < 100 else 0
    penalty += grants
    penalty += overdue * 8
    penalty += unknown * 2
    penalty += min(10, deleted)
    score = max(0, min(100, 100 - penalty))

    warnings: list[str] = []
    if twofa_percent < 100:
        warnings.append(f"{total - with_2fa} active entr{'y lacks' if total - with_2fa == 1 else 'ies lack'} 2FA metadata")
    if overdue:
        warnings.append(f"{overdue} secret{' is' if overdue == 1 else 's are'} overdue for rotation")
    if grants:
        warnings.append(f"{grants} active encrypted share grant{' exists' if grants == 1 else 's exist'}")
    if not warnings:
        warnings.append("No urgent metadata findings")

    return SecurityScoreSnapshot(score, total, twofa_percent, high, grants, overdue, deleted, tuple(warnings))
