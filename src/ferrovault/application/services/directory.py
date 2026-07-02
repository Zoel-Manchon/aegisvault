"""Local user/device key directory for Zero Trust sharing.

This is intentionally local-first. Public keys, device IDs, roles, and groups are
stored in settings; no secret material is required. The sharing center and future
SCIM/SSO integrations can use the same model.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable, Mapping, Any

from .sharing import public_key_fingerprint


@dataclass(frozen=True)
class DirectoryPrincipal:
    label: str
    email: str = ""
    public_key: str = ""
    role: str = "member"
    groups: tuple[str, ...] = field(default_factory=tuple)
    trusted_devices: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""
    active: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "DirectoryPrincipal":
        data = dict(data or {})
        data.setdefault("label", data.get("email", "recipient"))
        data.setdefault("email", "")
        data.setdefault("public_key", "")
        data.setdefault("role", "member")
        data.setdefault("groups", ())
        data.setdefault("trusted_devices", ())
        data.setdefault("notes", "")
        data.setdefault("active", True)
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data}).normalized()

    def normalized(self) -> "DirectoryPrincipal":
        valid_roles = {"owner", "admin", "auditor", "member", "readonly"}
        role = self.role if self.role in valid_roles else "member"
        return DirectoryPrincipal(
            label=(self.label or self.email or "recipient").strip(),
            email=(self.email or "").strip().lower(),
            public_key=(self.public_key or "").strip(),
            role=role,
            groups=_tuple(self.groups),
            trusted_devices=_tuple(self.trusted_devices),
            notes=(self.notes or "").strip(),
            active=bool(self.active),
        )

    @property
    def fingerprint(self) -> str:
        if not self.public_key:
            return ""
        try:
            return public_key_fingerprint(self.public_key)
        except Exception:
            return "invalid"

    def to_dict(self) -> dict:
        return asdict(self.normalized())


class IdentityDirectory:
    def __init__(self, principals: Iterable[Mapping[str, Any] | DirectoryPrincipal] | None = None):
        self._items = tuple((p if isinstance(p, DirectoryPrincipal) else DirectoryPrincipal.from_dict(p)).normalized()
                            for p in (principals or ()))

    def list(self, include_inactive: bool = True) -> tuple[DirectoryPrincipal, ...]:
        items = self._items if include_inactive else tuple(p for p in self._items if p.active)
        return tuple(sorted(items, key=lambda p: ((not p.active), p.label.lower(), p.email)))

    def upsert(self, principal: DirectoryPrincipal) -> "IdentityDirectory":
        normalized = principal.normalized()
        key = _key(normalized)
        items = [p for p in self._items if _key(p) != key]
        items.append(normalized)
        return IdentityDirectory(items)

    def deactivate(self, label_or_email: str) -> "IdentityDirectory":
        needle = label_or_email.strip().lower()
        items = []
        for p in self._items:
            if p.label.lower() == needle or p.email.lower() == needle:
                p = DirectoryPrincipal(**{**p.to_dict(), "active": False})
            items.append(p)
        return IdentityDirectory(items)

    def trusted_device_ids(self) -> tuple[str, ...]:
        ids = []
        for p in self._items:
            if p.active:
                ids.extend(p.trusted_devices)
        return tuple(dict.fromkeys(x for x in ids if x))

    def to_list(self) -> list[dict]:
        return [p.to_dict() for p in self.list(include_inactive=True)]


def _key(p: DirectoryPrincipal) -> str:
    return (p.email or p.label).lower()


def _tuple(value) -> tuple[str, ...]:
    if isinstance(value, str):
        value = value.split(",")
    return tuple(dict.fromkeys(str(x).strip() for x in (value or ()) if str(x).strip()))
