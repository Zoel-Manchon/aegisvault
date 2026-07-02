"""Zero-plaintext sync gateway decision layer.

This is not a hosted server yet. It is the enforcement core a hosted/team sync
service would call before delivering encrypted grant material. The important
security boundary is preserved: it evaluates metadata and grant state only; it
never receives or reveals plaintext secrets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any

from .directory import DirectoryPrincipal, IdentityDirectory
from .sharing import ShareGrant


@dataclass(frozen=True)
class SyncDeliveryDecision:
    entry_name: str
    recipient: str
    fingerprint: str
    grant_id: str
    allowed: bool
    reason: str
    sealed_blob: str = ""


class ZeroTrustSyncGateway:
    """Evaluate whether encrypted grants may be delivered to a device."""

    def __init__(self, directory: IdentityDirectory, *, require_trusted_device: bool = True):
        self._directory = directory
        self._require_trusted_device = bool(require_trusted_device)

    def evaluate(self, entries: Iterable[Any], *, device_id: str = "") -> tuple[SyncDeliveryDecision, ...]:
        decisions: list[SyncDeliveryDecision] = []
        principals = self._principals_by_fingerprint()
        for entry in entries:
            entry_name = getattr(entry, "name", "")
            for raw_grant in getattr(entry, "sharing_grants", ()) or ():
                grant = ShareGrant.from_dict(raw_grant)
                principal = principals.get(grant.public_key_fingerprint)
                allowed, reason = self._allowed(grant, principal, device_id)
                decisions.append(SyncDeliveryDecision(
                    entry_name=entry_name,
                    recipient=grant.recipient,
                    fingerprint=grant.public_key_fingerprint,
                    grant_id=grant.grant_id,
                    allowed=allowed,
                    reason=reason,
                    sealed_blob=grant.sealed_blob if allowed else "",
                ))
        return tuple(decisions)

    def _principals_by_fingerprint(self) -> dict[str, DirectoryPrincipal]:
        out: dict[str, DirectoryPrincipal] = {}
        for principal in self._directory.list(include_inactive=True):
            fp = principal.fingerprint
            if fp and fp != "invalid":
                out[fp] = principal
        return out

    def _allowed(self, grant: ShareGrant, principal: DirectoryPrincipal | None, device_id: str) -> tuple[bool, str]:
        if not grant.active:
            return False, "grant revoked"
        if principal is None:
            return False, "recipient is not in the user/device directory"
        if not principal.active:
            return False, "recipient is inactive"
        if self._require_trusted_device and principal.trusted_devices:
            if not device_id or device_id not in principal.trusted_devices:
                return False, "recipient device is not trusted for sync delivery"
        return True, "deliver encrypted grant"
