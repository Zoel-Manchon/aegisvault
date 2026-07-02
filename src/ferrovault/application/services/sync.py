"""Encrypted local sync bundle support.

AegisVault vault files are already envelope-encrypted. A sync bundle therefore
ships the encrypted artifact plus an authenticated-looking manifest with no
plaintext secrets. It is a foundation for multi-device/team sync: future servers
should only ever see this encrypted payload and policy metadata.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .dto import EncryptedVault

FORMAT = "aegisvault.sync.bundle.v1"


@dataclass(frozen=True)
class SyncManifest:
    format: str
    created_at: str
    created_by: str
    device_id: str
    vault_fingerprint: str
    audit_head: str
    entry_count: int
    note: str = "encrypted-vault-artifact-no-plaintext-secrets"


@dataclass(frozen=True)
class SyncBundle:
    manifest: SyncManifest
    artifact: EncryptedVault

    def to_json(self) -> str:
        doc = {
            "manifest": self.manifest.__dict__,
            "artifact": artifact_to_dict(self.artifact),
        }
        return json.dumps(doc, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "SyncBundle":
        doc = json.loads(payload)
        manifest = SyncManifest(**doc["manifest"])
        if manifest.format != FORMAT:
            raise ValueError(f"unsupported sync bundle format: {manifest.format}")
        return cls(manifest=manifest, artifact=artifact_from_dict(doc["artifact"]))


def create_sync_bundle(
    *,
    artifact: EncryptedVault,
    created_at: str,
    created_by: str,
    device_id: str,
    vault_fingerprint: str,
    audit_head: str,
    entry_count: int,
) -> SyncBundle:
    return SyncBundle(
        manifest=SyncManifest(
            format=FORMAT,
            created_at=created_at,
            created_by=created_by or "local-admin",
            device_id=device_id or "local-device",
            vault_fingerprint=vault_fingerprint,
            audit_head=audit_head,
            entry_count=int(entry_count),
        ),
        artifact=artifact,
    )


def artifact_to_dict(artifact: EncryptedVault) -> dict[str, Any]:
    return {
        "header": artifact.header,
        "nonce": base64.b64encode(artifact.nonce).decode("ascii"),
        "ciphertext": base64.b64encode(artifact.ciphertext).decode("ascii"),
    }


def artifact_from_dict(doc: Mapping[str, Any]) -> EncryptedVault:
    return EncryptedVault(
        header=dict(doc["header"]),
        nonce=base64.b64decode(doc["nonce"]),
        ciphertext=base64.b64decode(doc["ciphertext"]),
    )
