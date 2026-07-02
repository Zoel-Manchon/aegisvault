"""VaultRepository adapter: store the encrypted artifact as a single JSON file.

Knows nothing about crypto - it persists opaque bytes (base64) plus the
authenticated header. Atomic write via temp-file + replace.
"""
from __future__ import annotations

import base64
import json
import os

from ....application.services.dto import EncryptedVault


class FileVaultRepository:
    def __init__(self, path: str):
        self._path = path

    def exists(self) -> bool:
        return os.path.exists(self._path)

    def load(self) -> EncryptedVault:
        with open(self._path, encoding="utf-8") as fh:
            doc = json.load(fh)
        return EncryptedVault(
            header=doc["header"],
            nonce=base64.b64decode(doc["nonce"]),
            ciphertext=base64.b64decode(doc["ciphertext"]),
        )

    def save(self, artifact: EncryptedVault) -> None:
        doc = {
            "header": artifact.header,
            "nonce": base64.b64encode(artifact.nonce).decode(),
            "ciphertext": base64.b64encode(artifact.ciphertext).decode(),
        }
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
        os.replace(tmp, self._path)
