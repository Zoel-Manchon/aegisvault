"""Zero Trust public-key sharing and revocation primitives.

This module turns the older "shared_with" label into a real access-grant model:

* every share creates a recipient-specific X25519 sealed blob;
* the vault stores only encrypted grant material inside the already encrypted vault;
* revocation is represented as a first-class state transition and audit event.

Important cryptographic boundary: revocation stops future app/sync access to a grant,
but it cannot claw back a sealed blob that was already exported to a recipient. A real
team-sync server must enforce the active/revoked state before delivering grant blobs.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Any

from ...adapters.outbound.sharing.sealed_box import seal


@dataclass(frozen=True)
class ShareGrant:
    """Encrypted access grant for one recipient and one secret."""

    grant_id: str
    recipient: str
    public_key_fingerprint: str
    recipient_public_key: str
    sealed_blob: str
    created_at: str
    created_by: str = "local-admin"
    revoked_at: str = ""
    revoked_by: str = ""
    revoke_reason: str = ""
    algorithm: str = "X25519-HKDF-SHA256-AESGCM"
    version: int = 1

    @property
    def active(self) -> bool:
        return not self.revoked_at

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ShareGrant":
        payload = dict(data or {})
        payload.setdefault("grant_id", "")
        payload.setdefault("recipient", payload.get("label", "recipient"))
        payload.setdefault("public_key_fingerprint", payload.get("fingerprint", ""))
        payload.setdefault("recipient_public_key", payload.get("public_key", ""))
        payload.setdefault("sealed_blob", payload.get("blob", ""))
        payload.setdefault("created_at", "")
        payload.setdefault("created_by", "local-admin")
        payload.setdefault("revoked_at", "")
        payload.setdefault("revoked_by", "")
        payload.setdefault("revoke_reason", "")
        payload.setdefault("algorithm", "X25519-HKDF-SHA256-AESGCM")
        payload.setdefault("version", 1)
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: payload[k] for k in allowed})


def public_key_fingerprint(public_key_b64: str) -> str:
    """Stable, display-safe fingerprint for a recipient public key."""
    raw = base64.b64decode(public_key_b64.strip())
    if len(raw) != 32:
        raise ValueError("recipient public key must be a base64-encoded 32-byte X25519 key")
    return hashlib.sha256(raw).hexdigest()[:16]


def _grant_id(entry_name: str, recipient: str, fingerprint: str, created_at: str, sealed_blob: str) -> str:
    material = "\0".join((entry_name, recipient, fingerprint, created_at, sealed_blob)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:20]


def create_share_grant(
    *,
    entry_name: str,
    plaintext_secret: str,
    recipient_public_key: str,
    recipient: str,
    created_at: str,
    created_by: str = "local-admin",
) -> ShareGrant:
    """Create and encrypt a new recipient-specific grant."""
    recipient = (recipient or "recipient").strip()
    if not recipient:
        recipient = "recipient"
    public_key = recipient_public_key.strip()
    fingerprint = public_key_fingerprint(public_key)
    blob = seal(plaintext_secret, public_key)
    gid = _grant_id(entry_name, recipient, fingerprint, created_at, blob)
    return ShareGrant(
        grant_id=gid,
        recipient=recipient,
        public_key_fingerprint=fingerprint,
        recipient_public_key=public_key,
        sealed_blob=blob,
        created_at=created_at,
        created_by=created_by or "local-admin",
    )


def normalize_grants(grants: Iterable[Mapping[str, Any] | ShareGrant] | None) -> tuple[ShareGrant, ...]:
    out = []
    for grant in grants or ():
        out.append(grant if isinstance(grant, ShareGrant) else ShareGrant.from_dict(grant))
    return tuple(out)


def active_grants(grants: Iterable[Mapping[str, Any] | ShareGrant] | None) -> tuple[ShareGrant, ...]:
    return tuple(g for g in normalize_grants(grants) if g.active)


def shared_labels(grants: Iterable[Mapping[str, Any] | ShareGrant] | None, legacy: Iterable[str] | None = None) -> tuple[str, ...]:
    labels = [g.recipient for g in active_grants(grants)]
    labels.extend(str(x).strip() for x in (legacy or ()) if str(x).strip() and str(x).strip() not in labels)
    return tuple(dict.fromkeys(labels))


def revoke_matching_grants(
    grants: Iterable[Mapping[str, Any] | ShareGrant] | None,
    *,
    match: str,
    revoked_at: str,
    revoked_by: str = "local-admin",
    reason: str = "",
) -> tuple[tuple[dict, ...], int]:
    """Mark active grants as revoked when recipient/fingerprint/grant-id matches."""
    needle = (match or "").strip().lower()
    if not needle:
        raise ValueError("provide a recipient, public-key fingerprint, or grant id to revoke")
    updated = []
    revoked = 0
    for grant in normalize_grants(grants):
        haystack = {
            grant.grant_id.lower(),
            grant.recipient.lower(),
            grant.public_key_fingerprint.lower(),
        }
        if grant.active and needle in haystack:
            grant = ShareGrant(
                **{**grant.to_dict(),
                   "revoked_at": revoked_at,
                   "revoked_by": revoked_by or "local-admin",
                   "revoke_reason": reason or "manual revocation"}
            )
            revoked += 1
        updated.append(grant.to_dict())
    return tuple(updated), revoked
