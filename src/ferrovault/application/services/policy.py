"""Local + enterprise policy engine for sensitive vault actions.

This is now a real policy decision point: local desktop preferences, RBAC,
device trust, MFA context, and audit-chain safety are evaluated before copy,
reveal, share, purge, or SIEM export operations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any

from .enterprise import EnterpriseIdentity, RbacEngine
from .settings import VaultSettings
from .policy_pack import PolicyPack


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""
    code: str = "ok"

    @staticmethod
    def allow() -> "PolicyDecision":
        return PolicyDecision(True)

    @staticmethod
    def deny(code: str, reason: str) -> "PolicyDecision":
        return PolicyDecision(False, reason, code)


_ACTION_MAP = {
    "copy_secret": "copy_secret",
    "reveal_secret": "reveal_secret",
    "share_secret": "share_secret",
    "export_audit": "export_audit",
    "purge_secret": "purge_secret",
    "rotate_secret": "rotate_secret",
    "manage_policy": "manage_policy",
    "manage_members": "manage_members",
}


class PolicyEngine:
    """Evaluate local and enterprise security policy for desktop and CLI actions."""

    def __init__(self, settings: VaultSettings, rbac: RbacEngine | None = None):
        self.settings = settings.normalized()
        self._rbac = rbac or RbacEngine()

    def evaluate(self, action: str, context: Mapping[str, Any] | None = None) -> PolicyDecision:
        context = context or {}
        if not self.settings.policy_enforcement_enabled:
            return PolicyDecision.allow()

        if action == "copy_secret":
            if self.settings.require_reveal_before_copy and not context.get("revealed"):
                return PolicyDecision.deny(
                    "reveal_required",
                    "Policy requires revealing the secret before copying it.",
                )

        if action == "share_secret":
            if self.settings.require_totp_for_shared and not context.get("has_totp"):
                return PolicyDecision.deny(
                    "totp_required",
                    "Policy blocks sharing entries without a 2FA/TOTP seed.",
                )

        if action == "export_audit":
            if self.settings.block_export_when_audit_broken and not context.get("audit_ok", True):
                return PolicyDecision.deny(
                    "audit_chain_broken",
                    "Policy blocks audit export because the local audit chain is not verified.",
                )

        identity = self._identity(context)
        if self.settings.require_trusted_device:
            identity = EnterpriseIdentity(**{**identity.__dict__, "device_trusted": self._is_trusted(identity)})

        resource = {
            "sensitivity": context.get("sensitivity", "standard"),
            "allowed_groups": context.get("allowed_groups", ()),
        }
        mapped = _ACTION_MAP.get(action)
        if mapped:
            rbac_decision = self._rbac.evaluate(mapped, identity, resource)
            if not rbac_decision.allowed:
                return PolicyDecision.deny(rbac_decision.code, rbac_decision.reason)

        if (
            self.settings.require_mfa_for_high_sensitivity
            and str(resource["sensitivity"]).lower() in {"high", "critical"}
            and action in {"copy_secret", "reveal_secret", "share_secret"}
            and not identity.mfa_verified
        ):
            return PolicyDecision.deny(
                "mfa_required",
                "High-sensitivity secrets require verified MFA.",
            )

        pack_context = {
            **dict(context),
            "sensitivity": resource["sensitivity"],
            "allowed_groups": resource["allowed_groups"],
            "device_trusted": identity.device_trusted,
            "device_id": identity.device_id,
            "mfa_verified": identity.mfa_verified,
            "role": identity.role,
        }
        pack_decision = PolicyPack.from_iterable(self.settings.policy_rules).evaluate(action, pack_context)
        if not pack_decision.allowed:
            return PolicyDecision.deny(pack_decision.code, pack_decision.reason)

        return PolicyDecision.allow()

    def _identity(self, context: Mapping[str, Any]) -> EnterpriseIdentity:
        supplied = context.get("identity")
        if isinstance(supplied, EnterpriseIdentity):
            return supplied.normalized()
        return EnterpriseIdentity(
            user_id=str(context.get("user_id") or self.settings.enterprise_user_id),
            display_name=str(context.get("display_name") or self.settings.enterprise_display_name),
            role=str(context.get("role") or self.settings.enterprise_role),
            groups=tuple(context.get("groups") or ()),
            device_id=str(context.get("device_id") or self.settings.local_device_id),
            device_trusted=bool(context.get("device_trusted", self.settings.local_device_id in self.settings.trusted_device_ids)),
            mfa_verified=bool(context.get("mfa_verified", True)),
            break_glass=bool(context.get("break_glass", False)),
        ).normalized()

    def _is_trusted(self, identity: EnterpriseIdentity) -> bool:
        return identity.device_trusted and identity.device_id in self.settings.trusted_device_ids
