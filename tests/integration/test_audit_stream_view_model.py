from __future__ import annotations

from dataclasses import dataclass

from ferrovault.adapters.inbound.gui.view_models.audit_stream import IncrementalAuditStream


@dataclass(frozen=True)
class Block:
    index: int
    action: str = "add"
    detail: str = "demo"
    timestamp: str = "2026-01-01T00:00:00Z"
    hash: str = "abc123456789"
    prev_hash: str = "root"


def test_audit_stream_only_counts_new_blocks():
    stream = IncrementalAuditStream()
    first = stream.update([Block(0), Block(1)])
    assert first.new_count == 2
    second = stream.update([Block(0), Block(1), Block(2, action="share")])
    assert second.new_count == 1
    assert len(second.events) == 3
