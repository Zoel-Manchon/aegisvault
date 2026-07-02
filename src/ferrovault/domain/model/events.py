"""Domain events."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VaultInitialized:
    pass


@dataclass(frozen=True)
class VaultUnlocked:
    entry_count: int


@dataclass(frozen=True)
class EntryAdded:
    entry_name: str


@dataclass(frozen=True)
class EntryRevealed:
    entry_name: str
