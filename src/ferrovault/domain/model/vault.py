"""Vault aggregate and Entry entity - the heart of the domain.

A Vault is the *decrypted* collection of entries plus the invariants over them
(unique entry names, lookups). Encryption, key derivation and persistence are
deliberately NOT here - they live behind ports, so the aggregate stays pure and
unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..value_objects.entry_id import EntryId
from ..value_objects.secret import Secret


class EntryNameTaken(Exception):
    pass


class EntryNotFound(Exception):
    pass


@dataclass
class Entry:
    id: EntryId
    name: str
    username: str
    secret: Secret
    url: str = ""
    notes: str = ""
    tags: tuple = ()
    category: str = ""
    totp: object = None          # TotpSecret | None - optional 2FA seed
    favorite: bool = False
    deleted_at: str = ""
    shared_with: tuple = ()
    sharing_grants: tuple = ()
    team_vault: str = "Personal"
    sensitivity: str = "standard"
    owner: str = "local-admin"
    allowed_groups: tuple = ()
    rotation_interval_days: int = 90
    last_rotated_at: str = ""
    expires_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def matches(self, query: str) -> bool:
        q = query.lower()
        return (q in self.name.lower()
                or q in self.username.lower()
                or q in self.url.lower()
                or q in self.category.lower()
                or q in self.team_vault.lower()
                or q in self.sensitivity.lower()
                or any(q in t.lower() for t in self.tags))


@dataclass
class Vault:
    """Aggregate root. Invariant: entry names are unique (case-insensitive)."""

    _entries: dict = field(default_factory=dict)   # id -> Entry
    _names: dict = field(default_factory=dict)     # name.lower -> id

    def add(self, entry: Entry) -> None:
        key = entry.name.lower()
        if key in self._names:
            raise EntryNameTaken(entry.name)
        self._entries[entry.id.value] = entry
        self._names[key] = entry.id.value

    def get(self, name: str) -> Entry:
        eid = self._names.get(name.lower())
        if eid is None:
            raise EntryNotFound(name)
        return self._entries[eid]

    def remove(self, name: str) -> None:
        eid = self._names.pop(name.lower(), None)
        if eid is None:
            raise EntryNotFound(name)
        del self._entries[eid]

    def list(self, include_deleted: bool = False) -> list:
        entries = list(self._entries.values())
        if include_deleted:
            return entries
        return [e for e in entries if not getattr(e, "deleted_at", "")]

    def search(self, query: str, include_deleted: bool = False) -> list:
        return [e for e in self.list(include_deleted=include_deleted) if e.matches(query)]

    def __len__(self) -> int:
        return len(self._entries)
