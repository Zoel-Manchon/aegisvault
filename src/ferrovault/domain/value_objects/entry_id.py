"""EntryId value object."""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class EntryId:
    value: str

    @staticmethod
    def new() -> "EntryId":
        return EntryId(str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value
