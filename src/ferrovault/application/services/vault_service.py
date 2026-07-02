"""VaultService: application use cases over envelope-encrypted storage.

Envelope encryption: a random Data-Encryption-Key (DEK) encrypts the vault. The
master password derives a Key-Encryption-Key (KEK) that *wraps* the DEK. This is
how KMS/Vault-style systems work, and it makes two features clean:

  * rotate  - change the password by re-wrapping the same DEK (data untouched).
  * recover - a Shamir-split recovery key also wraps the DEK, so K-of-N shares
              can rebuild access; those shares survive password changes because
              the DEK never changes.

Nothing here is crypto primitive code - it orchestrates the Cipher /
KeyDerivation ports and the domain (Vault, AuditLedger, Shamir).
"""
from __future__ import annotations

import base64
import json
import secrets

from ...domain.model.audit import AuditLedger
from ...domain.model.vault import Entry, Vault
from ...domain.services.merkle import merkle_root
from ...domain.services.shamir import combine_shares, split_secret
from ...domain.value_objects.entry_id import EntryId
from ...domain.value_objects.kdf_params import KdfParams
from ...domain.value_objects.password_policy import PasswordPolicy
from ...domain.value_objects.secret import Secret
from ...domain.value_objects.totp_secret import TotpSecret
from ...domain.services.password_generator import PasswordGenerator
from ...domain.services.password_strength import PasswordStrength
from ..errors import AuthenticationError, VaultAlreadyExists, VaultDoesNotExist
from .dto import EncryptedVault, EntryView
from .serialization import deserialize, serialize
from .sharing import create_share_grant, revoke_matching_grants, shared_labels

WRAP_AAD = b"ferrovault:wrap"
RECOVERY_AAD = b"ferrovault:recovery"


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s)


def _canonical(header: dict) -> bytes:
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode()


def _env_name(name: str, prefix: str = "") -> str:
    safe = "".join(c if c.isalnum() else "_" for c in name).upper().strip("_")
    if safe and safe[0].isdigit():
        safe = "_" + safe
    return f"{prefix}{safe}" if prefix else safe


def fingerprint(vault: Vault) -> str:
    leaves = sorted(f"{e.name}:{e.username}" for e in vault.list())
    return merkle_root(leaves)


class VaultService:
    def __init__(self, repository, key_derivation, cipher, clock,
                 kdf_factory=KdfParams.scrypt, generator=None, strength=None):
        self._repo = repository
        self._kdf = key_derivation
        self._cipher = cipher
        self._clock = clock
        self._kdf_factory = kdf_factory
        self._gen = generator or PasswordGenerator()
        self._strength = strength or PasswordStrength()

    # ---- envelope crypto ------------------------------------------------
    def _seal(self, vault, ledger, password, params, dek, recovery=None):
        kek = self._kdf.derive(password, params)
        try:
            wnonce, wblob = self._cipher.encrypt(kek.bytes, dek, WRAP_AAD)
        finally:
            kek.wipe()
        header = {
            "version": 3, "cipher": "AEAD", "kdf": params.to_dict(),
            "wrap": {"nonce": _b64(wnonce), "blob": _b64(wblob)},
        }
        if recovery:
            header["recovery"] = recovery
        nonce, ct = self._cipher.encrypt(dek, serialize(vault, ledger),
                                         _canonical(header))
        return EncryptedVault(header=header, nonce=nonce, ciphertext=ct)

    def _unwrap_dek(self, header, password) -> bytes:
        params = KdfParams.from_dict(header["kdf"])
        kek = self._kdf.derive(password, params)
        wrap = header["wrap"]
        try:
            return self._cipher.decrypt(
                kek.bytes, _b64d(wrap["nonce"]), _b64d(wrap["blob"]), WRAP_AAD)
        except Exception as exc:
            raise AuthenticationError("could not unlock vault") from exc
        finally:
            kek.wipe()

    def _open(self, artifact, password):
        dek = self._unwrap_dek(artifact.header, password)
        plaintext = self._cipher.decrypt(
            dek, artifact.nonce, artifact.ciphertext, _canonical(artifact.header))
        vault, ledger = deserialize(plaintext)
        return vault, ledger, dek

    def _require(self) -> EncryptedVault:
        if not self._repo.exists():
            raise VaultDoesNotExist("no vault here; run `init` first")
        return self._repo.load()

    # ---- use cases ------------------------------------------------------
    def init_vault(self, password: str) -> None:
        if self._repo.exists():
            raise VaultAlreadyExists("vault already exists")
        dek = secrets.token_bytes(32)
        ledger = AuditLedger()
        ledger.append("init", "vault created", self._clock.now_iso())
        self._repo.save(self._seal(Vault(), ledger, password,
                                   self._kdf_factory(), dek))

    def add_entry(self, password, name, username, secret,
                  url="", notes="", tags=(), category="", totp=None,
                  team_vault="Personal", sensitivity="standard", owner="local-admin",
                  allowed_groups=(), rotation_interval_days=90):
        artifact = self._require()
        vault, ledger, dek = self._open(artifact, password)
        now = self._clock.now_iso()
        vault.add(Entry(id=EntryId.new(), name=name, username=username,
                        secret=Secret(secret), url=url, notes=notes,
                        tags=tuple(tags), category=category,
                        totp=(TotpSecret(totp) if totp else None),
                        team_vault=team_vault or category or "Personal",
                        sensitivity=sensitivity or "standard",
                        owner=owner or "local-admin",
                        allowed_groups=tuple(allowed_groups or ()),
                        rotation_interval_days=int(rotation_interval_days or 90),
                        last_rotated_at=now,
                        created_at=now, updated_at=now))
        ledger.append("add", name, now)
        self._resave(artifact, vault, ledger, password, dek)

    def get_secret(self, password, name):
        vault, _l, _d = self._open(self._require(), password)
        return vault.get(name).secret.reveal()

    def list_entries(self, password):
        vault, _l, _d = self._open(self._require(), password)
        return [EntryView(name=e.name, username=e.username, url=e.url, tags=e.tags,
                          category=getattr(e, "category", ""),
                          has_totp=e.totp is not None,
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
                          updated_at=getattr(e, "updated_at", ""))
                for e in vault.list(include_deleted=True)]

    def remove_entry(self, password, name):
        artifact = self._require()
        vault, ledger, dek = self._open(artifact, password)
        vault.remove(name)
        ledger.append("remove", name, self._clock.now_iso())
        self._resave(artifact, vault, ledger, password, dek)

    def current_code(self, password, name):
        vault, _l, _d = self._open(self._require(), password)
        entry = vault.get(name)
        if entry.totp is None:
            raise ValueError(f"entry '{name}' has no TOTP configured")
        ts = self._clock.now_unix()
        return entry.totp.code_at(ts), entry.totp.seconds_remaining(ts)

    def audit_log(self, password):
        _v, ledger, _d = self._open(self._require(), password)
        return list(ledger.blocks)

    def verify_integrity(self, password):
        vault, ledger, _d = self._open(self._require(), password)
        return ledger.verify(), fingerprint(vault), ledger.head_hash

    def export_audit(self, password, exporter):
        _v, ledger, _d = self._open(self._require(), password)
        return exporter.export(ledger.blocks)

    def health_report(self, password, breach_checker=None):
        from ...domain.services.health import HealthAnalyzer
        vault, _l, _d = self._open(self._require(), password)
        entries = vault.list()
        breached = None
        if breach_checker is not None:
            breached = breach_checker.check(
                {e.name: e.secret.reveal() for e in entries})
        return HealthAnalyzer(self._strength).analyze(entries, breached)

    # ---- recovery + rotation -------------------------------------------
    def enroll_recovery(self, password, shares_n, threshold_k):
        artifact = self._require()
        vault, ledger, dek = self._open(artifact, password)
        recovery_key = secrets.token_bytes(32)
        rnonce, rblob = self._cipher.encrypt(recovery_key, dek, RECOVERY_AAD)
        recovery = {"nonce": _b64(rnonce), "blob": _b64(rblob),
                    "n": shares_n, "k": threshold_k}
        ledger.append("recovery-enroll", f"{threshold_k}-of-{shares_n}",
                      self._clock.now_iso())
        params = KdfParams.from_dict(artifact.header["kdf"])
        self._repo.save(self._seal(vault, ledger, password, params, dek, recovery))
        return split_secret(recovery_key, shares_n, threshold_k)

    def recover(self, shares, new_password):
        artifact = self._require()
        recovery = artifact.header.get("recovery")
        if not recovery:
            raise ValueError("this vault has no recovery shares enrolled")
        recovery_key = combine_shares(shares)
        try:
            dek = self._cipher.decrypt(recovery_key, _b64d(recovery["nonce"]),
                                       _b64d(recovery["blob"]), RECOVERY_AAD)
        except Exception as exc:
            raise AuthenticationError("shares did not reconstruct the key") from exc
        plaintext = self._cipher.decrypt(
            dek, artifact.nonce, artifact.ciphertext, _canonical(artifact.header))
        vault, ledger = deserialize(plaintext)
        ledger.append("recover", "master password reset via shares",
                      self._clock.now_iso())
        # keep the same DEK + recovery block, so existing shares stay valid
        self._repo.save(self._seal(vault, ledger, new_password,
                                   self._kdf_factory(), dek, recovery))

    def rotate(self, old_password, new_password):
        artifact = self._require()
        vault, ledger, dek = self._open(artifact, old_password)
        ledger.append("rotate", "master password changed", self._clock.now_iso())
        recovery = artifact.header.get("recovery")
        self._repo.save(self._seal(vault, ledger, new_password,
                                   self._kdf_factory(), dek, recovery))

    # ---- helpers --------------------------------------------------------
    def secret_env(self, password, prefix=""):
        """Map entries to environment variables for secret injection."""
        vault, _l, _d = self._open(self._require(), password)
        return {_env_name(e.name, prefix): e.secret.reveal() for e in vault.list()}

    def share_secret(self, password, name, recipient_pub_b64, recipient_label=None, actor="local-admin"):
        """Seal an entry's secret to a recipient's X25519 public key.

        Returns the recipient-specific sealed blob for compatibility with the
        existing CLI/tests, while storing a structured grant inside the encrypted
        vault so GUI and future sync code can list/revoke access.
        """
        artifact = self._require()
        vault, ledger, dek = self._open(artifact, password)
        entry = vault.get(name)
        now = self._clock.now_iso()
        grant = create_share_grant(
            entry_name=name,
            plaintext_secret=entry.secret.reveal(),
            recipient_public_key=recipient_pub_b64,
            recipient=recipient_label or recipient_pub_b64[:12],
            created_at=now,
            created_by=actor or "local-admin",
        )
        entry.sharing_grants = tuple(getattr(entry, "sharing_grants", ())) + (grant.to_dict(),)
        entry.shared_with = shared_labels(entry.sharing_grants, getattr(entry, "shared_with", ()))
        entry.updated_at = now
        ledger.append("share", f"{name} -> {grant.recipient} ({grant.public_key_fingerprint})", now)
        self._resave(artifact, vault, ledger, password, dek)
        return grant.sealed_blob

    def revoke_share(self, password, name, match, reason="", actor="local-admin"):
        """Revoke active grant(s) by recipient label, fingerprint, or grant id."""
        artifact = self._require()
        vault, ledger, dek = self._open(artifact, password)
        entry = vault.get(name)
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
        ledger.append("revoke-share", f"{name} -> {match} ({revoked} grant(s))", now)
        self._resave(artifact, vault, ledger, password, dek)
        return revoked

    def import_entries(self, password, records):
        """Bulk-add imported entries; returns (added, skipped) counts."""
        artifact = self._require()
        vault, ledger, dek = self._open(artifact, password)
        now = self._clock.now_iso()
        added = skipped = 0
        for r in records:
            name = (r.get("name") or "").strip()
            if not name or name.lower() in vault._names:
                skipped += 1
                continue
            vault.add(Entry(id=EntryId.new(), name=name,
                            username=r.get("username", ""),
                            secret=Secret(r.get("secret", "")),
                            url=r.get("url", ""), notes=r.get("notes", ""),
                            category=r.get("category", ""),
                            team_vault=r.get("team_vault", r.get("category", "") or "Personal"),
                            sensitivity=r.get("sensitivity", "standard"),
                            owner=r.get("owner", "local-admin"),
                            allowed_groups=tuple(r.get("allowed_groups", ())),
                            rotation_interval_days=int(r.get("rotation_interval_days", 90) or 90),
                            last_rotated_at=now,
                            created_at=now, updated_at=now))
            added += 1
        ledger.append("import", f"{added} entries", now)
        self._resave(artifact, vault, ledger, password, dek)
        return added, skipped

    def mark_rotated(self, password, name):
        artifact = self._require()
        vault, ledger, dek = self._open(artifact, password)
        entry = vault.get(name)
        now = self._clock.now_iso()
        entry.last_rotated_at = now
        entry.updated_at = now
        ledger.append("rotate-secret", name, now)
        self._resave(artifact, vault, ledger, password, dek)

    def enterprise_posture(self, password, identity=None):
        from .enterprise import EnterpriseIdentity, EnterprisePostureAnalyzer
        from .rotation import RotationPlanner
        entries = self.list_entries(password)
        findings = RotationPlanner().analyze(entries, self._clock.now_iso())
        return EnterprisePostureAnalyzer().summarize(entries, identity or EnterpriseIdentity(), findings)

    def rotation_report(self, password):
        from .rotation import RotationPlanner
        return RotationPlanner().analyze(self.list_entries(password), self._clock.now_iso())

    def stream_audit(self, password, sink):
        from .siem import SiemStreamer
        _v, ledger, _d = self._open(self._require(), password)
        return SiemStreamer(sink).stream(ledger.blocks)


    def export_sync_bundle(self, password, created_by="local-admin", device_id="local-device") -> str:
        """Export an encrypted sync bundle with no plaintext secrets."""
        artifact = self._require()
        vault, ledger, _dek = self._open(artifact, password)
        from .sync import create_sync_bundle
        bundle = create_sync_bundle(
            artifact=artifact,
            created_at=self._clock.now_iso(),
            created_by=created_by,
            device_id=device_id,
            vault_fingerprint=fingerprint(vault),
            audit_head=ledger.head_hash,
            entry_count=len(vault.list()),
        )
        return bundle.to_json()

    def import_sync_bundle(self, bundle_payload: str) -> None:
        """Replace the local encrypted vault artifact from a sync bundle."""
        from .sync import SyncBundle
        bundle = SyncBundle.from_json(bundle_payload)
        self._repo.save(bundle.artifact)

    def _resave(self, artifact, vault, ledger, password, dek):
        params = KdfParams.from_dict(artifact.header["kdf"])
        recovery = artifact.header.get("recovery")
        self._repo.save(self._seal(vault, ledger, password, params, dek, recovery))

    def generate_password(self, policy=None):
        pw = self._gen.generate(policy or PasswordPolicy.strong())
        return pw, self._strength.label(pw)

    def unlock(self, password):
        from .session import VaultSession
        artifact = self._require()
        vault, ledger, dek = self._open(artifact, password)
        params = KdfParams.from_dict(artifact.header["kdf"])
        recovery = artifact.header.get("recovery")
        return VaultSession(self, password, vault, ledger, dek, params, recovery)
