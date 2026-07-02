"""VaultSession: an unlocked, in-memory view of the vault for interactive UIs.

Holds the decrypted Vault, its AuditLedger, and the (unwrapped) DEK in memory,
so reads are instant and mutations re-seal without re-deriving from the
password. Also drives recovery enrolment and password rotation in-memory.
"""
from __future__ import annotations

import secrets

from ...domain.model.audit import AuditLedger
from ...domain.model.vault import Entry, Vault
from ...domain.services.shamir import split_secret
from ...domain.value_objects.entry_id import EntryId
from ...domain.value_objects.password_policy import PasswordPolicy
from ...domain.value_objects.secret import Secret
from ...domain.value_objects.totp_secret import TotpSecret, generate_base32_seed
from .dto import EntryView
from .vault_service import RECOVERY_AAD, _b64, fingerprint
from .sharing import create_share_grant, revoke_matching_grants, shared_labels


class VaultSession:
    def __init__(self, service, password, vault, ledger, dek, params, recovery=None):
        self._service = service
        self._password = password
        self._vault = vault
        self._ledger = ledger
        self._dek = dek
        self._params = params
        self._recovery = recovery
        self._clock = service._clock

    # ---- reads ----------------------------------------------------------
    def entries(self, include_deleted: bool = True):
        return [self._view(e) for e in self._vault.list(include_deleted=include_deleted)]

    def _view(self, e):
        return EntryView(
            name=e.name, username=e.username, url=e.url, tags=e.tags,
            category=getattr(e, "category", ""), has_totp=e.totp is not None,
            favorite=bool(getattr(e, "favorite", False)),
            deleted=bool(getattr(e, "deleted_at", "")),
            shared_with=shared_labels(getattr(e, "sharing_grants", ()), getattr(e, "shared_with", ())),
            sharing_grants=tuple(getattr(e, "sharing_grants", ())),
            team_vault=getattr(e, "team_vault", "Personal"),
            sensitivity=getattr(e, "sensitivity", "standard"),
            owner=getattr(e, "owner", "local-admin"),
            allowed_groups=tuple(getattr(e, "allowed_groups", ())),
            rotation_interval_days=int(getattr(e, "rotation_interval_days", 90) or 90),
            last_rotated_at=getattr(e, "last_rotated_at", ""),
            expires_at=getattr(e, "expires_at", ""),
            created_at=getattr(e, "created_at", ""),
            updated_at=getattr(e, "updated_at", ""),
        )

    def reveal(self, name):
        return self._vault.get(name).secret.reveal()

    def current_code(self, name):
        entry = self._vault.get(name)
        if entry.totp is None:
            return None
        ts = self._clock.now_unix()
        return entry.totp.code_at(ts), entry.totp.seconds_remaining(ts)

    def generate(self, policy=None):
        return self._service.generate_password(policy)

    def generate_totp_seed(self):
        return generate_base32_seed()

    def audit_log(self):
        return list(self._ledger.blocks)

    def verify_integrity(self):
        return self._ledger.verify(), fingerprint(self._vault), self._ledger.head_hash

    def export_audit(self, exporter):
        return exporter.export(self._ledger.blocks)

    def health_report(self, breach_checker=None):
        from ...domain.services.health import HealthAnalyzer
        entries = self._vault.list()
        breached = None
        if breach_checker is not None:
            breached = breach_checker.check(
                {e.name: e.secret.reveal() for e in entries})
        return HealthAnalyzer(self._service._strength).analyze(entries, breached)

    @property
    def has_recovery(self):
        return self._recovery is not None

    # ---- mutations ------------------------------------------------------
    def add(self, name, username, secret, url="", notes="", tags=(), category="", totp=None,
            team_vault="Personal", sensitivity="standard", owner="local-admin",
            allowed_groups=(), rotation_interval_days=90):
        now = self._clock.now_iso()
        self._vault.add(Entry(id=EntryId.new(), name=name, username=username,
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
                              created_at=now, updated_at=now))
        self._ledger.append("add", name, now)
        self._persist()

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


    def share_public_key(self, name, recipient_label, recipient_public_key, actor=None):
        """Create a structured Zero Trust share grant and return the sealed blob."""
        entry = self._vault.get(name)
        now = self._clock.now_iso()
        grant = create_share_grant(
            entry_name=name,
            plaintext_secret=entry.secret.reveal(),
            recipient_public_key=recipient_public_key,
            recipient=recipient_label,
            created_at=now,
            created_by=actor or "local-admin",
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
        recovery_key = secrets.token_bytes(32)
        rnonce, rblob = self._service._cipher.encrypt(
            recovery_key, self._dek, RECOVERY_AAD)
        self._recovery = {"nonce": _b64(rnonce), "blob": _b64(rblob),
                          "n": shares_n, "k": threshold_k}
        self._ledger.append("recovery-enroll", f"{threshold_k}-of-{shares_n}",
                            self._clock.now_iso())
        self._persist()
        return split_secret(recovery_key, shares_n, threshold_k)

    def rotate(self, new_password):
        self._ledger.append("rotate", "master password changed",
                            self._clock.now_iso())
        self._password = new_password
        self._params = self._service._kdf_factory()
        self._persist()


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
        """Replace the local encrypted vault from a bundle and lock this session."""
        self._service.import_sync_bundle(bundle_payload)
        self.lock()

    def _persist(self):
        artifact = self._service._seal(self._vault, self._ledger, self._password,
                                       self._params, self._dek, self._recovery)
        self._service._repo.save(artifact)

    def lock(self):
        self._password = None
        self._vault = Vault()
        self._ledger = AuditLedger()
        self._dek = b""
