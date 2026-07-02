"""Application DTOs - the boundary contract."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EncryptedVault:
    """The on-disk artifact: header (authenticated) + nonce + ciphertext."""

    header: dict
    nonce: bytes
    ciphertext: bytes


@dataclass(frozen=True)
class EntryView:
    """A read model for listing - never carries the secret."""

    name: str
    username: str
    url: str = ""
    tags: tuple = field(default_factory=tuple)
    category: str = ""
    has_totp: bool = False
    favorite: bool = False
    deleted: bool = False
    shared_with: tuple = field(default_factory=tuple)
    sharing_grants: tuple = field(default_factory=tuple)
    team_vault: str = "Personal"
    sensitivity: str = "standard"
    owner: str = "local-admin"
    allowed_groups: tuple = field(default_factory=tuple)
    rotation_interval_days: int = 90
    last_rotated_at: str = ""
    expires_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def active_share_count(self) -> int:
        return sum(1 for g in self.sharing_grants if not g.get("revoked_at"))

    @property
    def revoked_share_count(self) -> int:
        return sum(1 for g in self.sharing_grants if g.get("revoked_at"))
