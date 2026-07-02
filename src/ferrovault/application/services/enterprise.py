"""Enterprise identity, RBAC, device-trust, and posture services.

The project remains local-first, but this module models the same control-plane
concepts used by enterprise secret managers: identity claims, team vaults,
least-privilege roles, trusted devices, high-sensitivity controls, and
break-glass override.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Any


OWNER = "owner"
ADMIN = "admin"
AUDITOR = "auditor"
MEMBER = "member"
READONLY = "readonly"

SENSITIVE_ACTIONS = {
    "reveal_secret",
    "copy_secret",
    "share_secret",
    "export_audit",
    "purge_secret",
    "rotate_secret",
}

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    OWNER: frozenset({"*"}),
    ADMIN: frozenset({
        "list_entries", "view_metadata", "reveal_secret", "copy_secret",
        "share_secret", "export_audit", "view_audit", "verify_integrity",
        "health_report", "rotate_secret", "manage_team_vaults",
        "manage_members", "manage_device_trust", "manage_policy",
    }),
    AUDITOR: frozenset({
        "list_entries", "view_metadata", "export_audit", "view_audit",
        "verify_integrity", "health_report", "view_enterprise_posture",
    }),
    MEMBER: frozenset({
        "list_entries", "view_metadata", "reveal_secret", "copy_secret",
        "share_secret", "health_report",
    }),
    READONLY: frozenset({"list_entries", "view_metadata", "health_report"}),
}


@dataclass(frozen=True)
class EnterpriseIdentity:
    """Identity context normally supplied by SSO/OIDC or a local admin profile."""

    user_id: str = "local-admin"
    display_name: str = "Local Admin"
    email: str = ""
    role: str = OWNER
    groups: tuple[str, ...] = ()
    device_id: str = "local-device"
    device_trusted: bool = True
    mfa_verified: bool = True
    break_glass: bool = False
    claims: Mapping[str, Any] = field(default_factory=dict)

    def normalized(self) -> "EnterpriseIdentity":
        role = self.role if self.role in ROLE_PERMISSIONS else READONLY
        return EnterpriseIdentity(
            user_id=(self.user_id or "local-admin").strip(),
            display_name=(self.display_name or self.user_id or "Local Admin").strip(),
            email=(self.email or "").strip().lower(),
            role=role,
            groups=tuple(g.strip() for g in self.groups if str(g).strip()),
            device_id=(self.device_id or "local-device").strip(),
            device_trusted=bool(self.device_trusted),
            mfa_verified=bool(self.mfa_verified),
            break_glass=bool(self.break_glass),
            claims=dict(self.claims or {}),
        )


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str = ""
    code: str = "ok"
    audit_detail: str = ""

    @staticmethod
    def allow(audit_detail: str = "") -> "AccessDecision":
        return AccessDecision(True, audit_detail=audit_detail)

    @staticmethod
    def deny(code: str, reason: str) -> "AccessDecision":
        return AccessDecision(False, reason, code)


class RbacEngine:
    """Least-privilege role evaluator for enterprise actions."""

    def evaluate(
        self,
        action: str,
        identity: EnterpriseIdentity | None = None,
        resource: Mapping[str, Any] | None = None,
    ) -> AccessDecision:
        identity = (identity or EnterpriseIdentity()).normalized()
        resource = resource or {}

        if identity.break_glass:
            if not identity.mfa_verified:
                return AccessDecision.deny(
                    "break_glass_mfa_required",
                    "Break-glass access requires verified MFA.",
                )
            return AccessDecision.allow(f"break-glass:{identity.user_id}:{action}")

        permissions = ROLE_PERMISSIONS.get(identity.role, ROLE_PERMISSIONS[READONLY])
        if "*" not in permissions and action not in permissions:
            return AccessDecision.deny(
                "role_forbidden",
                f"Role '{identity.role}' is not allowed to perform '{action}'.",
            )

        if action in SENSITIVE_ACTIONS and not identity.device_trusted:
            return AccessDecision.deny(
                "untrusted_device",
                "Sensitive enterprise actions require a trusted device.",
            )

        sensitivity = str(resource.get("sensitivity", "standard")).lower()
        if sensitivity in {"high", "critical"} and action in {"reveal_secret", "copy_secret", "share_secret"}:
            if not identity.mfa_verified:
                return AccessDecision.deny(
                    "mfa_required",
                    "High-sensitivity secrets require verified MFA before access.",
                )

        allowed_groups = tuple(resource.get("allowed_groups") or ())
        if allowed_groups and not set(allowed_groups).intersection(identity.groups):
            return AccessDecision.deny(
                "group_forbidden",
                "This secret is restricted to another team or group.",
            )

        return AccessDecision.allow(f"{identity.user_id}:{identity.role}:{action}")


@dataclass(frozen=True)
class TeamVaultSummary:
    name: str
    entries: int
    high_sensitivity: int
    shared: int
    twofa: int


@dataclass(frozen=True)
class EnterprisePosture:
    entries: int
    team_vaults: int
    high_sensitivity: int
    shared_entries: int
    twofa_coverage_percent: int
    rotation_overdue: int
    trusted_device: bool
    role: str
    teams: tuple[TeamVaultSummary, ...]


class EnterprisePostureAnalyzer:
    """Build dashboard-ready enterprise posture from entry read models."""

    def summarize(self, entries, identity: EnterpriseIdentity, rotation_findings=()) -> EnterprisePosture:
        active = [e for e in entries if not getattr(e, "deleted", False)]
        teams: dict[str, dict[str, int]] = {}
        for e in active:
            team = getattr(e, "team_vault", "") or getattr(e, "category", "") or "Personal"
            item = teams.setdefault(team, {"entries": 0, "high": 0, "shared": 0, "twofa": 0})
            item["entries"] += 1
            item["high"] += 1 if getattr(e, "sensitivity", "standard") in {"high", "critical"} else 0
            item["shared"] += 1 if getattr(e, "shared_with", ()) else 0
            item["twofa"] += 1 if getattr(e, "has_totp", False) else 0
        total = len(active)
        twofa = sum(1 for e in active if getattr(e, "has_totp", False))
        shared = sum(1 for e in active if getattr(e, "shared_with", ()))
        high = sum(1 for e in active if getattr(e, "sensitivity", "standard") in {"high", "critical"})
        team_summaries = tuple(
            TeamVaultSummary(name, data["entries"], data["high"], data["shared"], data["twofa"])
            for name, data in sorted(teams.items(), key=lambda kv: (-kv[1]["entries"], kv[0].lower()))
        )
        overdue = sum(1 for f in rotation_findings if getattr(f, "status", "") == "overdue")
        return EnterprisePosture(
            entries=total,
            team_vaults=len(team_summaries),
            high_sensitivity=high,
            shared_entries=shared,
            twofa_coverage_percent=round((twofa / total) * 100) if total else 100,
            rotation_overdue=overdue,
            trusted_device=identity.normalized().device_trusted,
            role=identity.normalized().role,
            teams=team_summaries,
        )
