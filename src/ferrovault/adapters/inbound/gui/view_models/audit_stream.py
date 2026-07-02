"""Incremental audit stream view-model for live SIEM panels and QML."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .....application.services.siem import normalize_blocks


@dataclass(frozen=True)
class AuditStreamSnapshot:
    events: tuple[Any, ...]
    latest_index: int
    new_count: int

    def as_dicts(self) -> tuple[dict, ...]:
        return tuple(asdict(e) for e in self.events)


class IncrementalAuditStream:
    """Cache normalized events and only append blocks that are new."""

    def __init__(self):
        self._latest_index = -1
        self._events: list[Any] = []

    @property
    def latest_index(self) -> int:
        return self._latest_index

    def update(self, blocks: Iterable[Any]) -> AuditStreamSnapshot:
        new_blocks = [b for b in blocks if int(getattr(b, "index", -1)) > self._latest_index]
        new_events = normalize_blocks(new_blocks)
        if new_events:
            self._events.extend(new_events)
            self._latest_index = max(int(e.index) for e in self._events)
        return AuditStreamSnapshot(tuple(self._events), self._latest_index, len(new_events))
