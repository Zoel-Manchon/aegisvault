"""View-model builder for the Zero Trust dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Any

from .....application.services.access_requests import AccessRequestQueue
from .....application.services.enterprise import EnterpriseIdentity
from .....application.services.settings import VaultSettings
from .security_score import build_security_score


@dataclass(frozen=True)
class ZeroTrustDashboardModel:
    score: str
    audit_state: str
    audit_ok: bool
    role: str
    device: str
    device_ok: bool
    overdue: str
    twofa: str
    policy_state: str
    policy_enforced: bool
    grants: int
    pending_requests: int
    team_lines: tuple[str, ...]
    rotation_lines: tuple[str, ...]
    fingerprint: str
    head_hash: str


def build_identity(settings: VaultSettings) -> EnterpriseIdentity:
    trusted = settings.local_device_id in settings.trusted_device_ids
    return EnterpriseIdentity(
        user_id=settings.enterprise_user_id,
        display_name=settings.enterprise_display_name,
        role=settings.enterprise_role,
        device_id=settings.local_device_id,
        device_trusted=trusted,
        mfa_verified=True,
    ).normalized()


def build_zero_trust_dashboard_model(session: Any, settings: VaultSettings, entries: Iterable[Any]) -> ZeroTrustDashboardModel:
    # Performance note: do not call session.health_report() here. The deep health
    # scan reveals every secret to check password strength/reuse, which can make
    # startup and section switching feel slow. The dashboard uses a metadata-only
    # live score and leaves the full health scan behind the explicit Health dialog.
    try:
        verdict, fingerprint, head = session.verify_integrity()
        posture = session.enterprise_posture(build_identity(settings))
        rotation = session.rotation_report()
    except Exception:
        verdict, fingerprint, head, posture, rotation = None, "unavailable", "unavailable", None, ()

    active = [v for v in entries if not getattr(v, "deleted", False)]
    live_score = build_security_score(entries, rotation)
    score = str(live_score.score)
    audit_ok = bool(verdict and verdict.ok)
    audit_state = "Verified" if audit_ok else "Needs review"
    role = getattr(posture, "role", settings.enterprise_role).capitalize()
    device_ok = bool(getattr(posture, "trusted_device", False))
    device = "Trusted" if device_ok else "Untrusted"
    overdue = str(getattr(posture, "rotation_overdue", 0))
    twofa = f"{getattr(posture, 'twofa_coverage_percent', 100)}%"
    policy_state = "Enforced" if settings.policy_enforcement_enabled else "Monitor"
    grants = sum(int(getattr(v, "active_share_count", 0)) for v in active)
    pending_requests = AccessRequestQueue(settings.access_requests).pending_count()

    return ZeroTrustDashboardModel(
        score=score,
        audit_state=audit_state,
        audit_ok=audit_ok,
        role=role,
        device=device,
        device_ok=device_ok,
        overdue=overdue,
        twofa=twofa,
        policy_state=policy_state,
        policy_enforced=settings.policy_enforcement_enabled,
        grants=grants,
        pending_requests=pending_requests,
        team_lines=_team_summary_lines(getattr(posture, "teams", ()) if posture else ()),
        rotation_lines=_rotation_summary_lines(rotation),
        fingerprint=fingerprint,
        head_hash=head,
    )


def _team_summary_lines(teams) -> tuple[str, ...]:
    if not teams:
        return (
            "Personal vault ready",
            "Add team vault metadata when creating secrets",
            "Team cards will appear automatically",
        )
    lines = []
    for team in tuple(teams)[:5]:
        lines.append(f"{team.name}: {team.entries} entries · {team.twofa} 2FA · {team.shared} shared")
    return tuple(lines)


def _rotation_summary_lines(rotation) -> tuple[str, ...]:
    watch = [f for f in (rotation or ()) if f.status in {"overdue", "due_soon", "unknown"}][:5]
    if not watch:
        return (
            "No urgent rotation findings",
            "Default SLA is applied to new entries",
            "Use Rotate after changing external secrets",
        )
    lines = []
    for finding in watch:
        desc = f"{finding.entry_name}: {finding.status.replace('_', ' ')} · age {finding.age_days}d"
        if finding.days_overdue:
            desc += f" · overdue {finding.days_overdue}d"
        lines.append(desc)
    return tuple(lines)
