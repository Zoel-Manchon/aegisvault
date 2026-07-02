"""Local Zero Trust access-request workflow.

Enterprise vaults should not only block sensitive actions; they should also give
users a governed path to request temporary access. This module keeps the first
implementation deliberately local, serializable, and deterministic: requests are
plain metadata persisted in desktop settings, while actual secret access still
passes through the policy engine and audit ledger.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


VALID_ACTIONS = ("reveal_secret", "copy_secret", "share_secret", "export_audit", "rotate_secret", "purge_secret")
VALID_STATES = ("pending", "approved", "denied", "expired")


@dataclass(frozen=True)
class AccessRequest:
    request_id: str
    entry_name: str
    requester: str
    action: str = "reveal_secret"
    reason: str = ""
    status: str = "pending"
    created_at: str = ""
    decided_by: str = ""
    decided_at: str = ""
    decision_reason: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "AccessRequest":
        data = dict(data or {})
        data.setdefault("request_id", uuid.uuid4().hex[:12])
        data.setdefault("entry_name", "")
        data.setdefault("requester", "")
        data.setdefault("action", "reveal_secret")
        data.setdefault("reason", "")
        data.setdefault("status", "pending")
        data.setdefault("created_at", "")
        data.setdefault("decided_by", "")
        data.setdefault("decided_at", "")
        data.setdefault("decision_reason", "")
        clean = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**clean).normalized()

    def normalized(self) -> "AccessRequest":
        action = self.action if self.action in VALID_ACTIONS else "reveal_secret"
        status = self.status if self.status in VALID_STATES else "pending"
        return AccessRequest(
            request_id=(self.request_id or uuid.uuid4().hex[:12]).strip(),
            entry_name=(self.entry_name or "").strip(),
            requester=(self.requester or "").strip(),
            action=action,
            reason=(self.reason or "").strip(),
            status=status,
            created_at=(self.created_at or "").strip(),
            decided_by=(self.decided_by or "").strip(),
            decided_at=(self.decided_at or "").strip(),
            decision_reason=(self.decision_reason or "").strip(),
        )

    @property
    def is_open(self) -> bool:
        return self.status == "pending"

    def to_dict(self) -> dict:
        return asdict(self.normalized())


class AccessRequestQueue:
    """Immutable-style queue for local approval metadata."""

    def __init__(self, requests: Iterable[Mapping[str, Any] | AccessRequest] | None = None):
        self._items = tuple((r if isinstance(r, AccessRequest) else AccessRequest.from_dict(r)).normalized()
                            for r in (requests or ()))

    def list(self, include_closed: bool = True) -> tuple[AccessRequest, ...]:
        items = self._items if include_closed else tuple(r for r in self._items if r.is_open)
        return tuple(sorted(items, key=lambda r: ((r.status != "pending"), r.created_at, r.entry_name, r.requester)))

    def create(self, *, entry_name: str, requester: str, action: str, reason: str, created_at: str) -> "AccessRequestQueue":
        request = AccessRequest(
            request_id=uuid.uuid4().hex[:12],
            entry_name=entry_name,
            requester=requester,
            action=action,
            reason=reason,
            status="pending",
            created_at=created_at,
        ).normalized()
        return AccessRequestQueue((*self._items, request))

    def decide(self, request_id: str, *, approved: bool, decided_by: str, decided_at: str, reason: str = "") -> "AccessRequestQueue":
        needle = (request_id or "").strip()
        if not needle:
            raise ValueError("request id is required")
        updated = []
        matched = False
        for item in self._items:
            if item.request_id != needle:
                updated.append(item)
                continue
            matched = True
            if item.status != "pending":
                raise ValueError(f"request '{needle}' is already {item.status}")
            updated.append(AccessRequest(**{
                **item.to_dict(),
                "status": "approved" if approved else "denied",
                "decided_by": decided_by,
                "decided_at": decided_at,
                "decision_reason": reason,
            }).normalized())
        if not matched:
            raise ValueError(f"request '{needle}' was not found")
        return AccessRequestQueue(updated)

    def pending_count(self) -> int:
        return sum(1 for r in self._items if r.status == "pending")

    def pending_for_entry(self, entry_name: str) -> tuple[AccessRequest, ...]:
        needle = (entry_name or "").strip().lower()
        return tuple(r for r in self.list(include_closed=False) if r.entry_name.lower() == needle)

    def to_list(self) -> list[dict]:
        return [r.to_dict() for r in self.list(include_closed=True)]
