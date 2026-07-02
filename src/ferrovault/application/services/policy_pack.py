"""Configurable Zero Trust policy-pack rules.

The fixed local toggles are still useful, but enterprise software needs editable
rules that can be saved, exported, reviewed, and applied consistently from the
GUI and CLI. This module keeps the first implementation intentionally small and
safe: deny rules only, deterministic matching, and no dynamic code execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping


SENSITIVE_ACTIONS = ("reveal_secret", "copy_secret", "share_secret", "export_audit", "purge_secret", "rotate_secret")
ALL_ACTIONS = ("*",) + SENSITIVE_ACTIONS + ("manage_policy", "manage_members")


@dataclass(frozen=True)
class PolicyRule:
    """One saved Zero Trust rule.

    Matching is AND-based across all populated selectors. Empty selectors mean
    "any". The first matching enabled rule denies the action with its message.
    """

    rule_id: str
    name: str
    actions: tuple[str, ...] = ("*",)
    sensitivities: tuple[str, ...] = ()
    team_vaults: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    require_mfa: bool = False
    require_trusted_device: bool = False
    block_export: bool = False
    block_share: bool = False
    enabled: bool = True
    reason: str = "Blocked by Zero Trust policy pack."

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "PolicyRule":
        data = dict(data or {})
        data.setdefault("rule_id", "rule")
        data.setdefault("name", data.get("rule_id", "Rule"))
        data.setdefault("actions", ("*",))
        data.setdefault("sensitivities", ())
        data.setdefault("team_vaults", ())
        data.setdefault("categories", ())
        data.setdefault("require_mfa", False)
        data.setdefault("require_trusted_device", False)
        data.setdefault("block_export", False)
        data.setdefault("block_share", False)
        data.setdefault("enabled", True)
        data.setdefault("reason", "Blocked by Zero Trust policy pack.")
        clean = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**clean).normalized()

    def normalized(self) -> "PolicyRule":
        actions = _clean_tuple(self.actions) or ("*",)
        actions = tuple(a if a in ALL_ACTIONS else "*" for a in actions)
        return PolicyRule(
            rule_id=_slug(self.rule_id or self.name or "rule"),
            name=(self.name or "Policy rule").strip(),
            actions=tuple(dict.fromkeys(actions)),
            sensitivities=tuple(x.lower() for x in _clean_tuple(self.sensitivities)),
            team_vaults=_clean_tuple(self.team_vaults),
            categories=_clean_tuple(self.categories),
            require_mfa=bool(self.require_mfa),
            require_trusted_device=bool(self.require_trusted_device),
            block_export=bool(self.block_export),
            block_share=bool(self.block_share),
            enabled=bool(self.enabled),
            reason=(self.reason or "Blocked by Zero Trust policy pack.").strip(),
        )

    def to_dict(self) -> dict:
        return asdict(self.normalized())

    def matches(self, action: str, context: Mapping[str, Any]) -> bool:
        rule = self.normalized()
        if not rule.enabled:
            return False
        if "*" not in rule.actions and action not in rule.actions:
            return False
        if rule.sensitivities and str(context.get("sensitivity", "standard")).lower() not in set(rule.sensitivities):
            return False
        if rule.team_vaults and _lower(context.get("team_vault", "")) not in {_lower(x) for x in rule.team_vaults}:
            return False
        if rule.categories and _lower(context.get("category", "")) not in {_lower(x) for x in rule.categories}:
            return False
        if rule.require_mfa and bool(context.get("mfa_verified", False)):
            return False
        if rule.require_trusted_device and bool(context.get("device_trusted", False)):
            return False
        if rule.block_export and action != "export_audit":
            return False
        if rule.block_share and action != "share_secret":
            return False
        return True


@dataclass(frozen=True)
class PolicyPackDecision:
    allowed: bool
    reason: str = ""
    code: str = "ok"
    rule_id: str = ""


@dataclass(frozen=True)
class PolicyPack:
    """A small set of editable deny rules."""

    rules: tuple[PolicyRule, ...] = field(default_factory=tuple)

    @classmethod
    def from_iterable(cls, rules: Iterable[Mapping[str, Any] | PolicyRule] | None) -> "PolicyPack":
        return cls(tuple((r if isinstance(r, PolicyRule) else PolicyRule.from_dict(r)).normalized() for r in (rules or ())))

    def to_list(self) -> list[dict]:
        return [r.to_dict() for r in self.rules]

    def evaluate(self, action: str, context: Mapping[str, Any] | None = None) -> PolicyPackDecision:
        context = context or {}
        for rule in self.rules:
            if rule.matches(action, context):
                return PolicyPackDecision(False, rule.reason, "policy_pack_denied", rule.rule_id)
        return PolicyPackDecision(True)


def default_policy_rules() -> tuple[dict, ...]:
    """Enterprise-friendly starter rules shown in the GUI policy editor."""
    return (
        PolicyRule(
            rule_id="critical-mfa-device",
            name="Critical secrets need MFA + trusted device",
            actions=("reveal_secret", "copy_secret", "share_secret"),
            sensitivities=("critical",),
            require_mfa=True,
            require_trusted_device=True,
            reason="Critical secrets require verified MFA and a trusted device.",
        ).to_dict(),
        PolicyRule(
            rule_id="production-share-guard",
            name="Production sharing requires approval context",
            actions=("share_secret",),
            team_vaults=("Production", "Prod"),
            block_share=True,
            reason="Production vault sharing is blocked by the local Zero Trust policy pack.",
            enabled=False,
        ).to_dict(),
        PolicyRule(
            rule_id="critical-no-export",
            name="Critical audit export guard",
            actions=("export_audit",),
            sensitivities=("critical",),
            block_export=True,
            reason="Critical policy blocks this export path.",
            enabled=False,
        ).to_dict(),
    )


def _clean_tuple(value) -> tuple[str, ...]:
    if isinstance(value, str):
        value = value.split(",")
    return tuple(dict.fromkeys(str(x).strip() for x in (value or ()) if str(x).strip()))


def _slug(value: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in str(value).strip())
    out = "-".join(x for x in out.split("-") if x)
    return out or "rule"


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()
