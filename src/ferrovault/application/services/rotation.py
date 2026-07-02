"""Secret rotation and expiration planning."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RotationFinding:
    entry_name: str
    status: str
    age_days: int
    interval_days: int
    days_overdue: int = 0
    severity: str = "info"


class RotationPlanner:
    """Compute rotation posture without revealing secret values."""

    def analyze(self, entries, now_iso: str | None = None) -> tuple[RotationFinding, ...]:
        now = _parse(now_iso) if now_iso else datetime.now(timezone.utc)
        findings: list[RotationFinding] = []
        for e in entries:
            if getattr(e, "deleted", False):
                continue
            interval = int(getattr(e, "rotation_interval_days", 90) or 90)
            baseline = getattr(e, "last_rotated_at", "") or getattr(e, "updated_at", "") or getattr(e, "created_at", "")
            if not baseline:
                findings.append(RotationFinding(e.name, "unknown", 0, interval, severity="medium"))
                continue
            age = max(0, (now - _parse(baseline)).days)
            if age > interval:
                overdue = age - interval
                severity = "critical" if overdue >= 30 or getattr(e, "sensitivity", "standard") == "critical" else "high"
                findings.append(RotationFinding(e.name, "overdue", age, interval, overdue, severity))
            elif age >= int(interval * 0.8):
                findings.append(RotationFinding(e.name, "due_soon", age, interval, 0, "medium"))
            else:
                findings.append(RotationFinding(e.name, "ok", age, interval, 0, "info"))
        return tuple(findings)


def _parse(value: str) -> datetime:
    text = str(value).strip()
    if not text:
        return datetime.now(timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
