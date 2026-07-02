"""SSO/OIDC claim mapping and SCIM-style local directory services.

This is intentionally provider-neutral. Real Entra ID, Okta, Google Workspace,
or Authentik adapters can feed ID-token claims and SCIM payloads into these
classes without changing vault/domain code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Any

from .enterprise import EnterpriseIdentity, OWNER, ADMIN, AUDITOR, MEMBER, READONLY


_ROLE_ALIASES = {
    "owner": OWNER,
    "vault_owner": OWNER,
    "admin": ADMIN,
    "administrator": ADMIN,
    "vault_admin": ADMIN,
    "auditor": AUDITOR,
    "security_auditor": AUDITOR,
    "member": MEMBER,
    "user": MEMBER,
    "readonly": READONLY,
    "read_only": READONLY,
    "viewer": READONLY,
}


class OidcClaimMapper:
    """Map verified OIDC claims to AegisVault's enterprise identity context."""

    def __init__(self, default_role: str = MEMBER, allowed_domains: tuple[str, ...] = ()):
        self.default_role = default_role
        self.allowed_domains = tuple(d.lower().lstrip("@") for d in allowed_domains)

    def map_claims(self, claims: Mapping[str, Any], device_id: str = "local-device", device_trusted: bool = True) -> EnterpriseIdentity:
        email = str(claims.get("email") or claims.get("preferred_username") or "").lower()
        if self.allowed_domains and email:
            domain = email.split("@")[-1]
            if domain not in self.allowed_domains:
                raise ValueError(f"email domain '{domain}' is not allowed for this tenant")

        role = self._role_from_claims(claims)
        groups = claims.get("groups") or claims.get("roles") or ()
        if isinstance(groups, str):
            groups = (groups,)
        mfa = claims.get("amr") or claims.get("acr") or ()
        if isinstance(mfa, str):
            mfa_tokens = {mfa.lower()}
        else:
            mfa_tokens = {str(x).lower() for x in mfa}
        return EnterpriseIdentity(
            user_id=str(claims.get("sub") or email or "oidc-user"),
            display_name=str(claims.get("name") or email or "OIDC User"),
            email=email,
            role=role,
            groups=tuple(str(g) for g in groups),
            device_id=device_id,
            device_trusted=device_trusted,
            mfa_verified=bool({"mfa", "otp", "hwk", "fido", "webauthn"}.intersection(mfa_tokens)),
            claims=dict(claims),
        ).normalized()

    def _role_from_claims(self, claims: Mapping[str, Any]) -> str:
        candidates = []
        for key in ("ferrovault_role", "role", "roles", "groups"):
            value = claims.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                candidates.append(value)
            else:
                candidates.extend(str(v) for v in value)
        for candidate in candidates:
            normalized = candidate.lower().replace("-", "_").replace(" ", "_")
            if normalized in _ROLE_ALIASES:
                return _ROLE_ALIASES[normalized]
        return self.default_role if self.default_role in _ROLE_ALIASES.values() else MEMBER


@dataclass(frozen=True)
class ScimUser:
    id: str
    user_name: str
    display_name: str = ""
    email: str = ""
    active: bool = True
    groups: tuple[str, ...] = ()
    role: str = MEMBER


@dataclass
class ScimDirectory:
    """Small in-memory SCIM directory used by tests, CLI, and future adapters."""

    users: dict[str, ScimUser] = field(default_factory=dict)
    groups: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def upsert_user(self, payload: Mapping[str, Any]) -> ScimUser:
        user_id = str(payload.get("id") or payload.get("userName") or payload.get("user_name") or "").strip()
        if not user_id:
            raise ValueError("SCIM user requires id or userName")
        emails = payload.get("emails") or []
        email = ""
        if isinstance(emails, list) and emails:
            first = emails[0]
            email = str(first.get("value", "") if isinstance(first, Mapping) else first)
        groups = payload.get("groups") or ()
        if isinstance(groups, str):
            groups = (groups,)
        normalized_groups = tuple(str(g.get("display") or g.get("value") or g) if isinstance(g, Mapping) else str(g) for g in groups)
        role = _ROLE_ALIASES.get(str(payload.get("role") or payload.get("ferrovault_role") or MEMBER).lower(), MEMBER)
        user = ScimUser(
            id=user_id,
            user_name=str(payload.get("userName") or payload.get("user_name") or user_id),
            display_name=str(payload.get("displayName") or payload.get("display_name") or ""),
            email=email,
            active=bool(payload.get("active", True)),
            groups=normalized_groups,
            role=role,
        )
        self.users[user.id] = user
        for group in user.groups:
            members = set(self.groups.get(group, ()))
            members.add(user.id)
            self.groups[group] = tuple(sorted(members))
        return user

    def deactivate_user(self, user_id: str) -> ScimUser:
        user = self.users[user_id]
        updated = ScimUser(**{**user.__dict__, "active": False})
        self.users[user_id] = updated
        return updated

    def identity_for(self, user_id: str, device_id: str = "local-device", device_trusted: bool = True) -> EnterpriseIdentity:
        user = self.users[user_id]
        return EnterpriseIdentity(
            user_id=user.id,
            display_name=user.display_name or user.user_name,
            email=user.email,
            role=user.role,
            groups=user.groups,
            device_id=device_id,
            device_trusted=device_trusted,
            mfa_verified=True,
        ).normalized()
