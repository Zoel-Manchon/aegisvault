"""Vault <-> bytes serialization (the plaintext that gets encrypted).

Pure, deterministic, no I/O. Lives in the application layer because it defines
the wire shape of the decrypted vault; the bytes it produces are handed to the
Cipher port, never written to disk directly.
"""
from __future__ import annotations

import base64
import json

from ...domain.model.audit import AuditBlock, AuditLedger
from ...domain.model.vault import Entry, Vault
from ...domain.value_objects.entry_id import EntryId
from ...domain.value_objects.secret import Secret
from ...domain.value_objects.totp_secret import TotpSecret
from .sharing import normalize_grants, shared_labels

VAULT_VERSION = 3


def _entry_to_dict(e: Entry) -> dict:
    return {
        "id": e.id.value,
        "name": e.name,
        "username": e.username,
        "secret": base64.b64encode(e.secret.reveal_bytes()).decode(),
        "url": e.url,
        "notes": e.notes,
        "tags": list(e.tags),
        "category": getattr(e, "category", ""),
        "totp": (
            {"secret": e.totp.secret, "digits": e.totp.digits,
             "period": e.totp.period, "algorithm": e.totp.algorithm}
            if e.totp else None
        ),
        "favorite": getattr(e, "favorite", False),
        "deleted_at": getattr(e, "deleted_at", ""),
        "shared_with": list(shared_labels(getattr(e, "sharing_grants", ()), getattr(e, "shared_with", ()))),
        "sharing_grants": [g.to_dict() for g in normalize_grants(getattr(e, "sharing_grants", ()))],
        "team_vault": getattr(e, "team_vault", "Personal"),
        "sensitivity": getattr(e, "sensitivity", "standard"),
        "owner": getattr(e, "owner", "local-admin"),
        "allowed_groups": list(getattr(e, "allowed_groups", ())),
        "rotation_interval_days": int(getattr(e, "rotation_interval_days", 90) or 90),
        "last_rotated_at": getattr(e, "last_rotated_at", ""),
        "expires_at": getattr(e, "expires_at", ""),
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


def _entry_from_dict(d: dict) -> Entry:
    totp = d.get("totp")
    return Entry(
        id=EntryId(d["id"]),
        name=d["name"],
        username=d.get("username", ""),
        secret=Secret(base64.b64decode(d["secret"])),
        url=d.get("url", ""),
        notes=d.get("notes", ""),
        tags=tuple(d.get("tags", [])),
        category=d.get("category", ""),
        totp=(TotpSecret(**totp) if totp else None),
        favorite=bool(d.get("favorite", False)),
        deleted_at=d.get("deleted_at", ""),
        shared_with=tuple(d.get("shared_with", [])),
        sharing_grants=tuple(d.get("sharing_grants", [])),
        team_vault=d.get("team_vault", d.get("category", "Personal") or "Personal"),
        sensitivity=d.get("sensitivity", "standard"),
        owner=d.get("owner", "local-admin"),
        allowed_groups=tuple(d.get("allowed_groups", [])),
        rotation_interval_days=int(d.get("rotation_interval_days", 90) or 90),
        last_rotated_at=d.get("last_rotated_at", ""),
        expires_at=d.get("expires_at", ""),
        created_at=d.get("created_at", ""),
        updated_at=d.get("updated_at", ""),
    )


def _block_to_dict(b: AuditBlock) -> dict:
    return {"index": b.index, "timestamp": b.timestamp, "action": b.action,
            "detail": b.detail, "prev_hash": b.prev_hash, "hash": b.hash}


def _block_from_dict(d: dict) -> AuditBlock:
    return AuditBlock(d["index"], d["timestamp"], d["action"], d["detail"],
                      d["prev_hash"], d["hash"])


def serialize(vault: Vault, ledger: AuditLedger) -> bytes:
    payload = {
        "version": VAULT_VERSION,
        "entries": [_entry_to_dict(e) for e in vault.list()],
        "audit": [_block_to_dict(b) for b in ledger.blocks],
    }
    return json.dumps(payload).encode("utf-8")


def deserialize(data: bytes) -> tuple:
    payload = json.loads(data.decode("utf-8"))
    vault = Vault()
    for d in payload.get("entries", []):
        vault.add(_entry_from_dict(d))
    ledger = AuditLedger(
        [_block_from_dict(b) for b in payload.get("audit", [])])
    return vault, ledger
