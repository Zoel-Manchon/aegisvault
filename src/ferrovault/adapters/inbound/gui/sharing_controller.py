"""Qt-free workflow controller for Zero Trust sharing dialogs.

The GUI owns widgets, messages, and file pickers. This controller owns the
sharing workflow state and talks to the unlocked vault session. Keeping this
logic outside QDialog makes the Sharing Center easier to test and easier to
reuse from a future Tauri/QML frontend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from ...outbound.sharing.sealed_box import generate_keypair, open_sealed


AuthorizeShare = Callable[[str], tuple[bool, str]]


@dataclass(frozen=True)
class RecipientKeyPair:
    private_key: str
    public_key: str


@dataclass(frozen=True)
class GrantRegistryRow:
    entry_name: str
    state: str
    recipient: str
    grant_id: str
    public_key_fingerprint: str
    created_at: str
    revoked_at: str
    revoke_reason: str
    grant: dict

    @property
    def table_values(self) -> tuple[str, ...]:
        return (
            self.entry_name,
            self.state,
            self.recipient,
            self.grant_id,
            self.public_key_fingerprint,
            self.created_at,
            self.revoked_at,
            self.revoke_reason,
        )

    @property
    def revoke_match(self) -> str:
        return self.grant_id or self.recipient or self.public_key_fingerprint


@dataclass(frozen=True)
class CreateGrantResult:
    entry_name: str
    grant: dict

    @property
    def sealed_blob(self) -> str:
        return str(self.grant.get("sealed_blob", ""))

    @property
    def display_text(self) -> str:
        return (
            "Encrypted share grant created. Send only the sealed blob below through an approved channel.\n\n"
            f"entry: {self.entry_name}\n"
            f"grant id: {self.grant.get('grant_id')}\n"
            f"recipient: {self.grant.get('recipient')}\n"
            f"fingerprint: {self.grant.get('public_key_fingerprint')}\n\n"
            f"{self.sealed_blob}"
        )


class SharingWorkflowController:
    """Application-facing controller for public-key sharing workflows."""

    def __init__(self, session, *, actor: str = "local-admin", authorize_share: AuthorizeShare | None = None):
        self._session = session
        self.actor = actor or "local-admin"
        self._authorize_share = authorize_share or (lambda _name: (True, ""))
        self.last_private_key = ""
        self.last_public_key = ""
        self.opened_secret = ""

    def entries(self) -> list:
        return [entry for entry in self._session.entries() if not getattr(entry, "deleted", False)]

    def entry_names(self) -> list[str]:
        return [entry.name for entry in self.entries()]

    def entry_by_name(self, name: str):
        return next((entry for entry in self.entries() if entry.name == name), None)

    def grant_rows(self) -> list[GrantRegistryRow]:
        rows: list[GrantRegistryRow] = []
        for entry in self.entries():
            for grant in tuple(getattr(entry, "sharing_grants", ()) or ()):  # tolerate old vaults
                revoked = bool(grant.get("revoked_at"))
                rows.append(
                    GrantRegistryRow(
                        entry_name=entry.name,
                        state="REVOKED" if revoked else "ACTIVE",
                        recipient=str(grant.get("recipient", "")),
                        grant_id=str(grant.get("grant_id", "")),
                        public_key_fingerprint=str(grant.get("public_key_fingerprint", "")),
                        created_at=str(grant.get("created_at", "")),
                        revoked_at=str(grant.get("revoked_at", "")),
                        revoke_reason=str(grant.get("revoke_reason", "")),
                        grant=dict(grant),
                    )
                )
        return rows

    def grant_counts(self) -> tuple[int, int]:
        rows = self.grant_rows()
        active = sum(1 for row in rows if row.state == "ACTIVE")
        return active, len(rows) - active

    def generate_keys(self) -> RecipientKeyPair:
        private_key, public_key = generate_keypair()
        self.last_private_key = private_key
        self.last_public_key = public_key
        return RecipientKeyPair(private_key=private_key, public_key=public_key)

    def create_grant(self, entry_name: str, recipient: str, public_key: str) -> CreateGrantResult:
        name = (entry_name or "").strip()
        if not name or self.entry_by_name(name) is None:
            raise ValueError("Select a secret first.")
        allowed, reason = self._authorize_share(name)
        if not allowed:
            raise PermissionError(reason or "The current Zero Trust policy blocked sharing.")
        pub = (public_key or "").strip()
        if not pub:
            raise ValueError("Paste or generate the recipient public key first.")
        grant = self._session.share_public_key(
            name,
            (recipient or "recipient").strip() or "recipient",
            pub,
            actor=self.actor,
        )
        return CreateGrantResult(entry_name=name, grant=dict(grant))

    def revoke_grant(self, entry_name: str, match: str, reason: str = "") -> int:
        name = (entry_name or "").strip()
        target = (match or "").strip()
        if not name or not target:
            raise ValueError("Select a secret and enter a recipient, fingerprint, or grant id.")
        return int(
            self._session.revoke_share(
                name,
                target,
                reason=(reason or "manual revocation").strip() or "manual revocation",
                actor=self.actor,
            )
        )

    def open_blob(self, private_key: str, sealed_blob: str) -> str:
        priv = (private_key or "").strip()
        blob = (sealed_blob or "").strip()
        if not priv or not blob:
            raise ValueError("Paste both the private key and the sealed blob.")
        self.opened_secret = open_sealed(blob, priv)
        return self.opened_secret

    def save_received_secret(self, *, name: str, username: str, secret: str, url: str = "") -> None:
        entry_name = (name or "").strip()
        value = (secret or self.opened_secret or "").strip()
        if not entry_name or not value:
            raise ValueError("Open a sealed blob and provide a new entry name first.")
        self._session.add(
            name=entry_name,
            username=(username or "").strip(),
            secret=value,
            url=(url or "").strip(),
            category="Received",
            tags=("received", "shared"),
            team_vault="Received",
            sensitivity="standard",
            owner=self.actor,
            allowed_groups=(),
            rotation_interval_days=90,
        )

    @staticmethod
    def sealed_blob_only(text: str) -> str:
        payload = (text or "").strip()
        if "\n\n" in payload:
            return payload.split("\n\n")[-1].strip()
        return payload

    @staticmethod
    def select_combo_text(combo, text: str) -> None:
        """Small Qt adapter kept here so both dialogs share identical selection behavior."""
        if not text:
            return
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
