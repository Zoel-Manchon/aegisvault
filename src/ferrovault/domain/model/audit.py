"""Tamper-evident audit ledger - a hash-chain of vault operations.

Each block stores the SHA-256 hash of the previous block, so the entire history
is cryptographically linked: change, reorder, or delete any past record and
every hash downstream stops matching. This is the core data structure of a
blockchain, applied where it genuinely helps - an append-only, verifiable audit
trail of who did what to the vault. The ledger is stored *inside* the encrypted
vault, so it is confidential as well as tamper-evident.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

GENESIS_PREV = "0" * 64


def _block_hash(index: int, timestamp: str, action: str, detail: str,
                prev_hash: str) -> str:
    payload = json.dumps([index, timestamp, action, detail, prev_hash],
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuditBlock:
    index: int
    timestamp: str
    action: str          # init | add | remove | reveal | unlock
    detail: str          # e.g. the entry name - never the secret
    prev_hash: str
    hash: str

    @staticmethod
    def create(index, timestamp, action, detail, prev_hash) -> "AuditBlock":
        h = _block_hash(index, timestamp, action, detail, prev_hash)
        return AuditBlock(index, timestamp, action, detail, prev_hash, h)

    def recompute(self) -> str:
        return _block_hash(self.index, self.timestamp, self.action,
                           self.detail, self.prev_hash)


@dataclass(frozen=True)
class Verification:
    ok: bool
    broken_index: int | None = None
    reason: str | None = None


@dataclass
class AuditLedger:
    """Aggregate: the append-only hash-chained history of the vault."""

    blocks: list = field(default_factory=list)

    @property
    def head_hash(self) -> str:
        return self.blocks[-1].hash if self.blocks else GENESIS_PREV

    def append(self, action: str, detail: str, timestamp: str) -> AuditBlock:
        block = AuditBlock.create(len(self.blocks), timestamp, action, detail,
                                  self.head_hash)
        self.blocks.append(block)
        return block

    def verify(self) -> Verification:
        prev = GENESIS_PREV
        for i, b in enumerate(self.blocks):
            if b.index != i:
                return Verification(False, i, "block index out of order")
            if b.prev_hash != prev:
                return Verification(False, i, "broken chain link")
            if b.recompute() != b.hash:
                return Verification(False, i, "block content was tampered")
            prev = b.hash
        return Verification(True)

    def __len__(self) -> int:
        return len(self.blocks)
