"""VaultSession: an unlocked, in-memory view of the vault for interactive UIs.

Holds the decrypted Vault, its AuditLedger, the data key (DEK) and the
key-encryption key (KEK) derived at unlock. Mutations re-seal with the KEK, so
the session never keeps the master password and saving does not re-run the
KDF. Both keys live in bytearrays that ``lock()`` overwrites with zeros
(best effort in Python: the interpreter may have copied them, see secret.py).

Before every save the session checks that the file on disk is still the one it
last read or wrote; if another window or a sync client changed it in between,
the save is refused with ``VaultConflictError`` instead of silently discarding
that change.
"""
from __future__ import annotations

import hmac
import secrets
import threading
from datetime import datetime

from ...domain.model.audit import AuditLedger
from ...domain.model.vault import ENTRY_KINDS, PASSWORD_HISTORY_LIMIT, Entry, Vault
from ...domain.services.shamir import split_secret, validate_split
from ...domain.value_objects.entry_id import EntryId
from ...domain.value_objects.secret import Secret
from ...domain.value_objects.totp_secret import TotpSecret, generate_base32_seed
from ..errors import AuthenticationError, VaultConflictError
from .vault_service import RECOVERY_AAD, _b64, _wipe, entry_view, fingerprint
from .sharing import create_share_grant, revoke_matching_grants, shared_labels

_UNSET = object()


class VaultSession:
    def __init__(self, service, opened):
        self._service = service
        self._vault: Vault = opened.vault
        self._ledger: AuditLedger = opened.ledger
        self._dek = bytearray(opened.dek)
        self._kek = opened.kek                    # MasterKey (bytearray inside)
        self._params = opened.params
        self._recovery = opened.recovery
        self._cipher_name = opened.cipher_name
        self._disk_nonce = opened.nonce           # body nonce of the file we last saw
        self.upgraded_from = opened.upgraded_from
        self._clock = service._clock
        self._locked = False
        # rotate() may run on a worker thread: lock() must wait for it rather than
        # wipe the keys while the file is being re-sealed.
        self._mutex = threading.RLock()
        _wipe(opened.dek)

    # ---- reads ----------------------------------------------------------
    @property
    def is_locked(self) -> bool:
        return self._locked

    @property
    def location(self) -> str:
        return str(getattr(self._service._repo, "path", "") or getattr(self._service._repo, "_path", ""))

    def crypto_summary(self) -> dict:
        return {"kdf": self._params.describe(), "algorithm": self._params.algorithm,
                "cipher": self._cipher_name, "upgraded_from": self.upgraded_from}

    def entries(self, include_deleted: bool = True):
        return [self._view(e) for e in self._vault.list(include_deleted=include_deleted)]

    def _view(self, e):
        return entry_view(e)

    def reveal(self, name):
        return self._vault.get(name).secret.reveal()

    def notes(self, name) -> str:
        return self._vault.get(name).notes

    def totp_seed(self, name) -> str:
        entry = self._vault.get(name)
        return entry.totp.secret if entry.totp else ""

    def password_history(self, name) -> list[str]:
        """Dates of previous secrets, newest first (the secrets stay sealed)."""
        return [h.get("changed_at", "") for h in self._vault.get(name).password_history]

    def current_code(self, name):
        entry = self._vault.get(name)
        if entry.totp is None:
            return None
        ts = self._clock.now_unix()
        return entry.totp.code_at(ts), entry.totp.seconds_remaining(ts)

    def generate(self, policy=None):
        return self._service.generate_password(policy)

    def generate_passphrase(self, policy=None) -> str:
        return self._service._gen.passphrase(policy)

    def assess(self, password: str):
        """Strength of a candidate password (nothing is stored or logged)."""
        return self._service.password_strength(password)

    def generate_totp_seed(self):
        return generate_base32_seed()

    def audit_log(self):
        return list(self._ledger.blocks)

    def verify_integrity(self):
        return self._ledger.verify(), fingerprint(self._vault), self._ledger.head_hash

    def export_audit(self, exporter):
        return exporter.export(self._ledger.blocks)

    def health_report(self, breach_checker=None, old_after_days: int | None = None):
        from ...domain.services.health import OLD_AFTER_DAYS, HealthAnalyzer
        entries = list(self._vault.list())
        breached = None
        if breach_checker is not None:
            breached = breach_checker.check(
                {e.name: e.secret.reveal() for e in entries if e.kind in ("login", "api_key")})
        return HealthAnalyzer(self._service._strength).analyze(
            entries, breached, now_iso=self._clock.now_iso(),
            old_after_days=int(old_after_days or OLD_AFTER_DAYS))

    def strength(self, name):
        return self._service._strength.assess(self._vault.get(name).secret.reveal())

    def reused_with(self, name) -> tuple[str, ...]:
        """Other live entries that share this entry's secret."""
        target = self._vault.get(name)
        secret = target.secret
        return tuple(e.name for e in self._vault.list()
                     if e is not target and e.kind in ("login", "api_key") and e.secret == secret)

    def entries_with_secret(self, secret: str, exclude: str | None = None) -> tuple[str, ...]:
        """Live login/API-key entries already using ``secret`` (to warn before reusing it)."""
        if not secret:
            return ()
        candidate = Secret(secret)
        return tuple(e.name for e in self._vault.list()
                     if e.name != exclude and e.kind in ("login", "api_key") and e.secret == candidate)

    @property
    def has_recovery(self):
        return self._recovery is not None

    @property
    def recovery_policy(self) -> tuple[int, int] | None:
        if not self._recovery:
            return None
        return int(self._recovery.get("k", 0)), int(self._recovery.get("n", 0))

    def verify_password(self, password: str) -> bool:
        """Constant-time check of ``password`` against the unlocked vault."""
        if self._locked:
            return False
        candidate = self._service._derive(password, self._params)
        try:
            return hmac.compare_digest(candidate.bytes, self._kek.bytes)
        finally:
            candidate.wipe()

    # ---- mutations ------------------------------------------------------
    def add(self, name, username, secret, url="", notes="", tags=(), category="", totp=None,
            team_vault="Personal", sensitivity="standard", owner="local-admin",
            allowed_groups=(), rotation_interval_days=90, kind="login"):
        now = self._clock.now_iso()
        self._vault.add(Entry(id=EntryId.new(), name=name.strip(), username=username,
                              secret=Secret(secret), url=url, notes=notes,
                              tags=tuple(tags), category=category,
                              totp=(TotpSecret(totp) if totp else None),
                              favorite=False, deleted_at="", shared_with=(), sharing_grants=(),
                              team_vault=team_vault or category or "Personal",
                              sensitivity=sensitivity or "standard",
                              owner=owner or "local-admin",
                              allowed_groups=tuple(allowed_groups or ()),
                              rotation_interval_days=int(rotation_interval_days or 90),
                              last_rotated_at=now,
                              kind=kind if kind in ENTRY_KINDS else "login",
                              password_changed_at=now,
                              created_at=now, updated_at=now))
        self._ledger.append("add", name, now)
        self._persist()

    def import_entries(self, records) -> tuple[int, int]:
        """Add parsed records (see adapters.outbound.importers) to this vault.

        Duplicated names and records without a name or secret are skipped. The
        file on disk is snapshotted first, so the import can be undone from
        the backups. Returns ``(added, skipped)``.
        """
        from ...domain.model.vault import EntryNameTaken
        added = skipped = 0
        now = self._clock.now_iso()
        for record in records:
            name = (record.get("name") or "").strip()
            secret = record.get("secret") or ""
            if not name or not secret:
                skipped += 1
                continue
            category = (record.get("category") or "").strip()
            try:
                self._vault.add(Entry(id=EntryId.new(), name=name, username=record.get("username", "") or "",
                                      secret=Secret(secret), url=record.get("url", "") or "",
                                      notes=record.get("notes", "") or "", tags=(), category=category,
                                      totp=None, favorite=False, deleted_at="", shared_with=(), sharing_grants=(),
                                      team_vault=category or "Personal", sensitivity="standard",
                                      owner="local-admin", allowed_groups=(), rotation_interval_days=90,
                                      last_rotated_at=now, kind="login", password_changed_at=now,
                                      created_at=now, updated_at=now))
            except (EntryNameTaken, ValueError):
                skipped += 1
                continue
            added += 1
        if added:
            self._service._snapshot("pre-import")
            self._ledger.append("import", f"{added} entries", now)
            self._persist()
        return added, skipped

    def log_access_decision(self, entry_name: str, requester: str, action: str, approved: bool) -> None:
        """Record an approved or denied access request in the audit chain."""
        detail = f"{entry_name} · {requester} · {action}"
        self._ledger.append("access-approve" if approved else "access-deny", detail, self._clock.now_iso())
        self._persist()

    def update(self, name, *, new_name=None, username=None, secret=None, url=None,
               notes=None, tags=None, category=None, totp=_UNSET, kind=None,
               team_vault=None, sensitivity=None, allowed_groups=None,
               rotation_interval_days=None):
        """Edit an entry. A changed secret pushes the old one into its history."""
        entry = self._vault.get(name)
        now = self._clock.now_iso()
        changed = []
        if new_name is not None and new_name.strip() and new_name.strip() != entry.name:
            self._vault.rename(entry.name, new_name.strip())
            changed.append("nombre")
        if secret is not None and Secret(secret) != entry.secret:
            history = ({"secret": entry.secret, "changed_at": entry.password_changed_at or entry.created_at},)
            entry.password_history = (history + tuple(entry.password_history))[:PASSWORD_HISTORY_LIMIT]
            entry.secret = Secret(secret)
            entry.password_changed_at = now
            entry.last_rotated_at = now
            changed.append("secreto")
        for field, value in (("username", username), ("url", url), ("notes", notes),
                             ("category", category), ("team_vault", team_vault),
                             ("sensitivity", sensitivity)):
            if value is not None and value != getattr(entry, field):
                setattr(entry, field, value)
                changed.append(field)
        if tags is not None:
            entry.tags = tuple(dict.fromkeys(t.strip() for t in tags if t.strip()))
        if allowed_groups is not None:
            entry.allowed_groups = tuple(dict.fromkeys(g.strip() for g in allowed_groups if g.strip()))
        if rotation_interval_days is not None:
            entry.rotation_interval_days = int(rotation_interval_days or 90)
        if kind is not None and kind in ENTRY_KINDS:
            entry.kind = kind
        if totp is not _UNSET:
            entry.totp = TotpSecret(totp) if totp else None
            changed.append("2FA")
        entry.updated_at = now
        detail = entry.name if not changed else f"{entry.name} ({', '.join(dict.fromkeys(changed))})"
        self._ledger.append("edit", detail, now)
        self._persist()
        return entry.name

    def remove(self, name):
        entry = self._vault.get(name)
        entry.deleted_at = self._clock.now_iso()
        entry.updated_at = entry.deleted_at
        self._ledger.append("trash", name, entry.deleted_at)
        self._persist()

    def restore(self, name):
        entry = self._vault.get(name)
        entry.deleted_at = ""
        entry.updated_at = self._clock.now_iso()
        self._ledger.append("restore", name, entry.updated_at)
        self._persist()

    def purge(self, name):
        self._vault.remove(name)
        self._ledger.append("purge", name, self._clock.now_iso())
        self._persist()

    def toggle_favorite(self, name):
        entry = self._vault.get(name)
        entry.favorite = not bool(getattr(entry, "favorite", False))
        entry.updated_at = self._clock.now_iso()
        self._ledger.append("favorite" if entry.favorite else "unfavorite", name, entry.updated_at)
        self._persist()
        return entry.favorite

    def set_enterprise_metadata(self, name, team_vault=None, sensitivity=None, allowed_groups=None, rotation_interval_days=None):
        entry = self._vault.get(name)
        if team_vault is not None:
            entry.team_vault = team_vault or "Personal"
        if sensitivity is not None:
            entry.sensitivity = sensitivity or "standard"
        if allowed_groups is not None:
            entry.allowed_groups = tuple(dict.fromkeys(g.strip() for g in allowed_groups if g.strip()))
        if rotation_interval_days is not None:
            entry.rotation_interval_days = int(rotation_interval_days or 90)
        entry.updated_at = self._clock.now_iso()
        self._ledger.append("enterprise-meta", name, entry.updated_at)
        self._persist()

    def mark_rotated(self, name):
        entry = self._vault.get(name)
        now = self._clock.now_iso()
        entry.last_rotated_at = now
        entry.updated_at = now
        self._ledger.append("rotate-secret", name, now)
        self._persist()

    def rotation_report(self):
        from .rotation import RotationPlanner
        return RotationPlanner().analyze(self.entries(), self._clock.now_iso())

    def enterprise_posture(self, identity=None):
        from .enterprise import EnterpriseIdentity, EnterprisePostureAnalyzer
        return EnterprisePostureAnalyzer().summarize(
            self.entries(), identity or EnterpriseIdentity(), self.rotation_report()
        )

    def stream_audit(self, sink):
        from .siem import SiemStreamer
        return SiemStreamer(sink).stream(self._ledger.blocks)

    def set_shared_with(self, name, recipients):
        entry = self._vault.get(name)
        cleaned = tuple(dict.fromkeys([r.strip() for r in recipients if r.strip()]))
        entry.shared_with = cleaned
        entry.updated_at = self._clock.now_iso()
        self._ledger.append("share" if cleaned else "unshare", name, entry.updated_at)
        self._persist()
        return cleaned

    def share_public_key(self, name, recipient_label, recipient_public_key, actor=None, *,
                         expires_in=None, include_login=False):
        """Create a structured Zero Trust share grant and return it (with the sealed blob).

        ``expires_in`` (a timedelta) records when the grant stops being
        delivered; ``include_login`` also seals the user name and URL.
        """
        entry = self._vault.get(name)
        now = self._clock.now_iso()
        expires_at = ""
        if expires_in:
            expires_at = (datetime.fromisoformat(now) + expires_in).isoformat()
        grant = create_share_grant(
            entry_name=name,
            plaintext_secret=entry.secret.reveal(),
            recipient_public_key=recipient_public_key,
            recipient=recipient_label,
            created_at=now,
            created_by=actor or "local-admin",
            expires_at=expires_at,
            username=getattr(entry, "username", "") or "",
            url=getattr(entry, "url", "") or "",
            include_login=bool(include_login),
        )
        entry.sharing_grants = tuple(getattr(entry, "sharing_grants", ())) + (grant.to_dict(),)
        entry.shared_with = shared_labels(entry.sharing_grants, getattr(entry, "shared_with", ()))
        entry.updated_at = now
        self._ledger.append("share", f"{name} -> {grant.recipient} ({grant.public_key_fingerprint})", now)
        self._persist()
        return grant.to_dict()

    def revoke_share(self, name, match, reason="", actor=None):
        """Revoke active grant(s) by recipient label, fingerprint, or grant id."""
        entry = self._vault.get(name)
        now = self._clock.now_iso()
        grants, revoked = revoke_matching_grants(
            getattr(entry, "sharing_grants", ()),
            match=match,
            revoked_at=now,
            revoked_by=actor or "local-admin",
            reason=reason,
        )
        if not revoked:
            raise ValueError(f"no active share grant matched '{match}'")
        entry.sharing_grants = grants
        entry.shared_with = shared_labels(entry.sharing_grants, ())
        entry.updated_at = now
        self._ledger.append("revoke-share", f"{name} -> {match} ({revoked} grant(s))", now)
        self._persist()
        return revoked

    def enroll_recovery(self, shares_n, threshold_k):
        validate_split(shares_n, threshold_k)
        recovery_key = secrets.token_bytes(32)
        cipher = self._service._cipher_by_name(self._cipher_name)
        rnonce, rblob = cipher.encrypt(recovery_key, bytes(self._dek), RECOVERY_AAD)
        self._recovery = {"nonce": _b64(rnonce), "blob": _b64(rblob),
                          "n": shares_n, "k": threshold_k}
        self._ledger.append("recovery-enroll", f"{threshold_k}-of-{shares_n}",
                            self._clock.now_iso())
        self._persist()
        return split_secret(recovery_key, shares_n, threshold_k)

    def rotate(self, new_password, current_password=None):
        """Re-wrap the DEK under a new password (fresh salt and default KDF cost).

        Pass ``current_password`` to re-authenticate first: an unattended
        unlocked window must not be enough to take over the vault.
        """
        with self._mutex:
            if current_password is not None and not self.verify_password(current_password):
                raise AuthenticationError("la contraseña actual no es correcta")
            params = self._service._kdf_factory()
            new_kek = self._service._derive(new_password, params)
            old_kek, old_params = self._kek, self._params
            self._kek, self._params = new_kek, params
            self._ledger.append("rotate", "master password changed", self._clock.now_iso())
            self._service._snapshot("pre-rotate")
            try:
                self._persist()
            except Exception:
                self._kek, self._params = old_kek, old_params
                new_kek.wipe()
                raise
            old_kek.wipe()

    def export_sync_bundle(self, created_by="local-admin", device_id="local-device") -> str:
        """Export the current encrypted artifact as a zero-plaintext sync bundle."""
        self._persist()
        artifact = self._service._repo.load()
        from .sync import create_sync_bundle
        bundle = create_sync_bundle(
            artifact=artifact,
            created_at=self._clock.now_iso(),
            created_by=created_by,
            device_id=device_id,
            vault_fingerprint=fingerprint(self._vault),
            audit_head=self._ledger.head_hash,
            entry_count=len(self._vault.list()),
        )
        return bundle.to_json()

    def import_sync_bundle(self, bundle_payload: str) -> None:
        """Replace the local vault from a bundle of *this* vault, then lock.

        The bundle must decrypt with this session's data key, so a bundle from
        another vault (or a crafted one) is rejected before anything is
        written; the current file is snapshotted first.
        """
        from .sync import SyncBundle
        bundle = SyncBundle.from_json(bundle_payload)
        self._service.verify_same_vault(bundle.artifact, self._dek)
        self._service._snapshot("pre-sync-import")
        self._service._repo.save(bundle.artifact)
        self.lock()

    def log_access(self, action: str, name: str) -> None:
        """Record a read of a secret (copy, reveal) in the audit chain.

        Only the entry name and the action are written - never the secret.
        """
        if action not in ("copy", "copy-user", "copy-totp", "reveal"):
            raise ValueError(f"unknown access action {action!r}")
        self._vault.get(name)                      # must exist
        self._ledger.append(action, name, self._clock.now_iso())
        self._persist()

    def purge_expired_trash(self, days: int) -> list[str]:
        """Remove for good the entries that have been in the trash longer than ``days``."""
        if days <= 0:
            return []
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        expired = []
        for entry in self._vault.list(include_deleted=True):
            if not entry.deleted_at:
                continue
            try:
                deleted = datetime.fromisoformat(entry.deleted_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if deleted.tzinfo is None:
                deleted = deleted.replace(tzinfo=timezone.utc)
            if (now - deleted).days >= days:
                expired.append(entry.name)
        if not expired:
            return []
        stamp = self._clock.now_iso()
        for name in expired:
            self._vault.remove(name)
            self._ledger.append("purge", f"{name} (papelera, {days} días)", stamp)
        self._persist()
        return expired

    def backups(self) -> list[dict]:
        """Backup copies of this vault, newest first, each opened read-only with
        this session's data key so the UI can say which ones have an intact
        audit chain. Nothing is written."""
        repo = self._service._repo
        lister, reader = getattr(repo, "snapshots", None), getattr(repo, "read", None)
        if lister is None or reader is None:
            return []
        import os
        from datetime import datetime, timezone
        out = []
        for path in lister():
            info = {"path": str(path), "name": os.path.basename(str(path)), "entries": None, "blocks": None,
                    "chain_ok": None, "last_event": "", "readable": False,
                    "modified": datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()}
            try:
                vault, ledger = self._service._decrypt_body(reader(path), self._dek)
                info.update(readable=True, entries=len(vault.list()), blocks=len(ledger.blocks),
                            chain_ok=ledger.verify().ok,
                            last_event=ledger.blocks[-1].timestamp if ledger.blocks else "")
            except Exception:
                pass
            out.append(info)
        return out

    def restore_backup(self, path) -> None:
        """Replace the vault with one of its backup copies, then lock.

        The copy must decrypt with this session's data key (it is the same
        vault); the current file is snapshotted first ("pre-restore") so the
        restore itself can be undone.
        """
        artifact = self._service._repo.read(path)
        self._service.verify_same_vault(artifact, self._dek)
        self._service._snapshot("pre-restore")
        self._service._repo.save(artifact)
        self.lock()

    def snapshot(self, label: str = "manual") -> str | None:
        """Copy the sealed vault file to the backup folder now."""
        snapshot = getattr(self._service._repo, "snapshot", None)
        return snapshot(label) if snapshot else None

    def _persist(self):
        with self._mutex:
            if self._locked:
                raise AuthenticationError("la bóveda está bloqueada")
            repo = self._service._repo
            if self._disk_nonce is not None and repo.exists():
                on_disk = repo.load()
                if on_disk.nonce != self._disk_nonce:
                    raise VaultConflictError(
                        "El archivo de la bóveda cambió en disco (otra ventana o una "
                        "sincronización). Ciérrala y vuelve a abrirla para no perder esos cambios.")
            artifact = self._service._seal_with_kek(self._vault, self._ledger, self._kek.bytes,
                                                    self._params, self._dek, self._recovery,
                                                    self._cipher_name)
            repo.save(artifact)
            self._disk_nonce = artifact.nonce

    def lock(self):
        """Forget the plaintext vault and overwrite both keys."""
        with self._mutex:
            if self._kek is not None:
                self._kek.wipe()
            _wipe(self._dek)
            self._dek = bytearray()
            self._vault = Vault()
            self._ledger = AuditLedger()
            self._locked = True
