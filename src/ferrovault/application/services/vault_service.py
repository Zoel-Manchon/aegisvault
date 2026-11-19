"""VaultService: application use cases over envelope-encrypted storage.

Envelope encryption: a random Data-Encryption-Key (DEK) encrypts the vault. The
master password derives a Key-Encryption-Key (KEK) that *wraps* the DEK. This is
how KMS/Vault-style systems work, and it makes two features clean:

  * rotate  - change the password by re-wrapping the same DEK (data untouched).
  * recover - a Shamir-split recovery key also wraps the DEK, so K-of-N shares
              can rebuild access; those shares survive password changes because
              the DEK never changes.

The header records the KDF (algorithm, salt, cost) and, from format 4 on, the
AEAD that sealed the body, so a vault is always opened with the primitives
that made it. The whole header is the body's associated data: editing any
field of it makes decryption fail.

Nothing here is crypto primitive code - it orchestrates the Cipher /
KeyDerivation ports and the domain (Vault, AuditLedger, Shamir).
"""
from __future__ import annotations

import base64
import binascii
import hmac
import json
import secrets
from contextlib import contextmanager
from dataclasses import dataclass

from ...domain.model.audit import AuditLedger
from ...domain.model.vault import Entry, Vault
from ...domain.services.merkle import merkle_root
from ...domain.services.shamir import combine_shares, split_secret, validate_split
from ...domain.value_objects.entry_id import EntryId
from ...domain.value_objects.kdf_params import KdfParams
from ...domain.value_objects.master_key import MasterKey
from ...domain.value_objects.password_policy import PasswordPolicy
from ...domain.value_objects.secret import Secret
from ...domain.value_objects.totp_secret import TotpSecret
from ...domain.services.password_generator import PasswordGenerator
from ...domain.services.password_strength import PasswordStrength
from ..errors import (AuthenticationError, UnsupportedVaultFormat,
                      VaultAlreadyExists, VaultDoesNotExist)
from .dto import EncryptedVault, EntryView
from .serialization import deserialize, serialize
from .sharing import create_share_grant, revoke_matching_grants, shared_labels

WRAP_AAD = b"ferrovault:wrap"
RECOVERY_AAD = b"ferrovault:recovery"
HEADER_VERSION = 4
# Format <= 3 wrote "AEAD" without naming the cipher. Those builds always
# paired Argon2id with XChaCha20-Poly1305 (Rust) and scrypt with AES-GCM.
LEGACY_CIPHER = "AEAD"
_LEGACY_CIPHER_BY_KDF = {"argon2id": "XChaCha20-Poly1305", "scrypt": "AES-256-GCM"}


def _b64(b: bytes) -> str:
    return base64.b64encode(bytes(b)).decode("ascii")


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


def cipher_name_of(cipher) -> str:
    return str(getattr(cipher, "NAME", type(cipher).__name__))


def _wipe(buf) -> None:
    if isinstance(buf, bytearray):
        for i in range(len(buf)):
            buf[i] = 0


@dataclass
class OpenedVault:
    """Everything a successful unlock yields. Callers wipe ``kek`` and ``dek``."""

    vault: Vault
    ledger: AuditLedger
    dek: bytearray
    kek: MasterKey
    params: KdfParams
    recovery: dict | None
    cipher_name: str
    nonce: bytes
    upgraded_from: str = ""


class VaultService:
    def __init__(self, repository, key_derivation, cipher, clock,
                 kdf_factory=KdfParams.scrypt, generator=None, strength=None,
                 extra_ciphers=()):
        self._repo = repository
        self._kdf = key_derivation
        self._cipher = cipher                      # seals new vaults
        self._ciphers = {}
        for c in (cipher, *extra_ciphers):
            self._ciphers.setdefault(cipher_name_of(c), c)
        self._clock = clock
        self._kdf_factory = kdf_factory
        self._gen = generator or PasswordGenerator()
        self._strength = strength or PasswordStrength()

    # ---- introspection (for the UI) --------------------------------------
    @property
    def default_cipher_name(self) -> str:
        return cipher_name_of(self._cipher)

    def default_kdf_params(self) -> KdfParams:
        return self._kdf_factory()

    def vault_exists(self) -> bool:
        return self._repo.exists()

    def describe_vault(self) -> dict:
        """KDF and cipher of the vault on disk, without unlocking it."""
        header = self._require().header
        params = KdfParams.from_dict(header["kdf"])
        return {"kdf": params.describe(), "algorithm": params.algorithm,
                "cipher": self._cipher_name(header)}

    # ---- cipher selection --------------------------------------------------
    def _cipher_name(self, header: dict) -> str:
        name = str(header.get("cipher") or LEGACY_CIPHER)
        if name != LEGACY_CIPHER:
            return name
        algorithm = (header.get("kdf") or {}).get("algorithm", "")
        inferred = _LEGACY_CIPHER_BY_KDF.get(algorithm)
        # Keep the historical behaviour (the configured cipher) when the
        # inferred one is not registered, e.g. with test doubles.
        return inferred if inferred in self._ciphers else self.default_cipher_name

    def _cipher_by_name(self, name: str):
        cipher = self._ciphers.get(name)
        if cipher is None:
            if name == "XChaCha20-Poly1305":
                raise UnsupportedVaultFormat(
                    "Esta bóveda se selló con XChaCha20-Poly1305 (núcleo Rust). "
                    "Compila el módulo ferrocrypto para abrirla.")
            raise UnsupportedVaultFormat(f"Esta compilación no soporta el cifrado {name}.")
        return cipher

    def _cipher_for(self, header: dict):
        return self._cipher_by_name(self._cipher_name(header))

    # ---- envelope crypto ------------------------------------------------
    def _derive(self, password: str, params: KdfParams) -> MasterKey:
        return self._kdf.derive(password, params)

    def _seal_with_kek(self, vault, ledger, kek: bytes, params, dek, recovery=None,
                       cipher_name: str | None = None) -> EncryptedVault:
        name = cipher_name or self.default_cipher_name
        cipher = self._cipher_by_name(name)
        wnonce, wblob = cipher.encrypt(kek, bytes(dek), WRAP_AAD)
        header = {
            "version": HEADER_VERSION, "cipher": name, "kdf": params.to_dict(),
            "wrap": {"nonce": _b64(wnonce), "blob": _b64(wblob)},
        }
        if recovery:
            header["recovery"] = recovery
        nonce, ct = cipher.encrypt(bytes(dek), serialize(vault, ledger), _canonical(header))
        return EncryptedVault(header=header, nonce=nonce, ciphertext=ct)

    def _seal(self, vault, ledger, password, params, dek, recovery=None, cipher_name=None):
        kek = self._derive(password, params)
        try:
            return self._seal_with_kek(vault, ledger, kek.bytes, params, dek, recovery, cipher_name)
        finally:
            kek.wipe()

    def _unwrap_with_kek(self, header, kek: bytes) -> bytearray:
        wrap = header["wrap"]
        cipher = self._cipher_for(header)
        try:
            return bytearray(cipher.decrypt(kek, _b64d(wrap["nonce"]), _b64d(wrap["blob"]), WRAP_AAD))
        except Exception as exc:
            raise AuthenticationError("could not unlock vault") from exc

    def _unwrap_dek(self, header, password) -> bytearray:
        params = self._params_of(header)
        kek = self._derive(password, params)
        try:
            return self._unwrap_with_kek(header, kek.bytes)
        finally:
            kek.wipe()

    @staticmethod
    def _params_of(header: dict) -> KdfParams:
        try:
            return KdfParams.from_dict(header["kdf"])
        except (KeyError, TypeError, ValueError) as exc:
            raise UnsupportedVaultFormat(f"Cabecera de bóveda no válida: {exc}") from exc

    def _decrypt_body(self, artifact: EncryptedVault, dek) -> tuple:
        cipher = self._cipher_for(artifact.header)
        try:
            plaintext = cipher.decrypt(bytes(dek), artifact.nonce, artifact.ciphertext,
                                       _canonical(artifact.header))
        except Exception as exc:
            raise AuthenticationError("the vault body failed authentication") from exc
        return deserialize(plaintext)

    def _open(self, artifact, password):
        dek = self._unwrap_dek(artifact.header, password)
        vault, ledger = self._decrypt_body(artifact, dek)
        return vault, ledger, dek

    def _open_full(self, artifact: EncryptedVault, password: str) -> OpenedVault:
        params = self._params_of(artifact.header)
        cipher_name = self._cipher_name(artifact.header)
        self._cipher_by_name(cipher_name)          # fail early, before the KDF
        kek = self._derive(password, params)
        try:
            dek = self._unwrap_with_kek(artifact.header, kek.bytes)
            vault, ledger = self._decrypt_body(artifact, dek)
        except Exception:
            kek.wipe()
            raise
        return OpenedVault(vault=vault, ledger=ledger, dek=dek, kek=kek, params=params,
                           recovery=artifact.header.get("recovery"),
                           cipher_name=cipher_name, nonce=artifact.nonce)

    def _require(self) -> EncryptedVault:
        if not self._repo.exists():
            raise VaultDoesNotExist("no vault here; run `init` first")
        return self._repo.load()

    @contextmanager
    def _editing(self, password: str):
        """Read-modify-write: yields the opened vault and re-seals it on a clean exit.

        The KEK and DEK are wiped whatever happens; an exception inside the
        block leaves the file untouched.
        """
        opened = self._open_full(self._require(), password)
        try:
            yield opened
            self._repo.save(self._seal_with_kek(
                opened.vault, opened.ledger, opened.kek.bytes, opened.params,
                opened.dek, opened.recovery, opened.cipher_name))
        finally:
            opened.kek.wipe()
            _wipe(opened.dek)

    def _snapshot(self, label: str) -> None:
        snapshot = getattr(self._repo, "snapshot", None)
        if snapshot is not None and self._repo.exists():
            snapshot(label)

    # ---- use cases ------------------------------------------------------
    def init_vault(self, password: str) -> None:
        if self._repo.exists():
            raise VaultAlreadyExists("vault already exists")
        dek = bytearray(secrets.token_bytes(32))
        ledger = AuditLedger()
        ledger.append("init", "vault created", self._clock.now_iso())
        try:
            self._repo.save(self._seal(Vault(), ledger, password, self._kdf_factory(), dek))
        finally:
            _wipe(dek)

    def add_entry(self, password, name, username, secret,
                  url="", notes="", tags=(), category="", totp=None,
                  team_vault="Personal", sensitivity="standard", owner="local-admin",
                  allowed_groups=(), rotation_interval_days=90, kind="login"):
        with self._editing(password) as opened:
            now = self._clock.now_iso()
            opened.vault.add(Entry(id=EntryId.new(), name=name, username=username,
                                   secret=Secret(secret), url=url, notes=notes,
                                   tags=tuple(tags), category=category,
                                   totp=(TotpSecret(totp) if totp else None),
                                   team_vault=team_vault or category or "Personal",
                                   sensitivity=sensitivity or "standard",
                                   owner=owner or "local-admin",
                                   allowed_groups=tuple(allowed_groups or ()),
                                   rotation_interval_days=int(rotation_interval_days or 90),
                                   last_rotated_at=now, kind=kind or "login",
                                   password_changed_at=now,
                                   created_at=now, updated_at=now))
            opened.ledger.append("add", name, now)

    def get_secret(self, password, name):
        vault, _l, _d = self._open(self._require(), password)
        return vault.get(name).secret.reveal()

    def list_entries(self, password):
        vault, _l, _d = self._open(self._require(), password)
        return [entry_view(e) for e in vault.list(include_deleted=True)]

    def remove_entry(self, password, name):
        with self._editing(password) as opened:
            opened.vault.remove(name)
            opened.ledger.append("remove", name, self._clock.now_iso())

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
        validate_split(shares_n, threshold_k)
        with self._editing(password) as opened:
            recovery_key = secrets.token_bytes(32)
            cipher = self._cipher_by_name(opened.cipher_name)
            rnonce, rblob = cipher.encrypt(recovery_key, bytes(opened.dek), RECOVERY_AAD)
            opened.recovery = {"nonce": _b64(rnonce), "blob": _b64(rblob),
                               "n": shares_n, "k": threshold_k}
            opened.ledger.append("recovery-enroll", f"{threshold_k}-of-{shares_n}",
                                 self._clock.now_iso())
            shares = split_secret(recovery_key, shares_n, threshold_k)
        return shares

    def recover(self, shares, new_password):
        artifact = self._require()
        recovery = artifact.header.get("recovery")
        if not recovery:
            raise ValueError("this vault has no recovery shares enrolled")
        try:
            recovery_key = combine_shares(shares)
        except ValueError as exc:
            raise AuthenticationError(f"shares are malformed: {exc}") from exc
        cipher = self._cipher_for(artifact.header)
        try:
            dek = bytearray(cipher.decrypt(recovery_key, _b64d(recovery["nonce"]),
                                           _b64d(recovery["blob"]), RECOVERY_AAD))
        except Exception as exc:
            raise AuthenticationError("shares did not reconstruct the key") from exc
        try:
            vault, ledger = self._decrypt_body(artifact, dek)
            ledger.append("recover", "master password reset via shares",
                          self._clock.now_iso())
            self._snapshot("pre-recover")
            # keep the same DEK + recovery block, so existing shares stay valid
            self._repo.save(self._seal(vault, ledger, new_password, self._kdf_factory(),
                                       dek, recovery, self._cipher_name(artifact.header)))
        finally:
            _wipe(dek)

    def recovery_policy(self) -> tuple[int, int] | None:
        """``(k, n)`` of the enrolled recovery shares, read from the plaintext
        header so the unlock screen can explain recovery before any password."""
        try:
            artifact = self._require()
        except Exception:  # noqa: BLE001 - missing or unreadable file: no recovery to offer
            return None
        recovery = artifact.header.get("recovery") or {}
        if not recovery:
            return None
        try:
            k, n = int(recovery.get("k") or 0), int(recovery.get("n") or 0)
        except (TypeError, ValueError):
            return None
        return (k, n) if 1 <= k <= n else None  # a damaged header offers no recovery

    def rotate(self, old_password, new_password):
        opened = self._open_full(self._require(), old_password)
        try:
            opened.ledger.append("rotate", "master password changed", self._clock.now_iso())
            self._snapshot("pre-rotate")
            self._repo.save(self._seal(opened.vault, opened.ledger, new_password,
                                       self._kdf_factory(), opened.dek, opened.recovery,
                                       opened.cipher_name))
        finally:
            opened.kek.wipe()
            _wipe(opened.dek)

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
        with self._editing(password) as opened:
            entry = opened.vault.get(name)
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
            opened.ledger.append("share", f"{name} -> {grant.recipient} ({grant.public_key_fingerprint})", now)
        return grant.sealed_blob

    def revoke_share(self, password, name, match, reason="", actor="local-admin"):
        """Revoke active grant(s) by recipient label, fingerprint, or grant id."""
        with self._editing(password) as opened:
            entry = opened.vault.get(name)
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
            opened.ledger.append("revoke-share", f"{name} -> {match} ({revoked} grant(s))", now)
        return revoked

    def import_entries(self, password, records):
        """Bulk-add imported entries; returns (added, skipped) counts."""
        added = skipped = 0
        with self._editing(password) as opened:
            vault = opened.vault
            now = self._clock.now_iso()
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
                                last_rotated_at=now, password_changed_at=now,
                                created_at=now, updated_at=now))
                added += 1
            opened.ledger.append("import", f"{added} entries", now)
            self._snapshot("pre-import")
        return added, skipped

    def mark_rotated(self, password, name):
        with self._editing(password) as opened:
            entry = opened.vault.get(name)
            now = self._clock.now_iso()
            entry.last_rotated_at = now
            entry.updated_at = now
            opened.ledger.append("rotate-secret", name, now)

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

    def import_sync_bundle(self, bundle_payload: str, password: str | None = None) -> None:
        """Replace the local encrypted vault artifact from a sync bundle.

        With ``password`` the bundle is checked before anything is replaced:
        if a local vault exists, the bundle must decrypt with *its* data key
        (the same vault on another device; the DEK survives rotations), and
        otherwise it must open with the password. The current file is
        snapshotted first, so a bad import can be undone.
        """
        from .sync import SyncBundle
        bundle = SyncBundle.from_json(bundle_payload)
        if password is not None:
            if self._repo.exists():
                local = self._open_full(self._require(), password)
                try:
                    self.verify_same_vault(bundle.artifact, local.dek)
                finally:
                    local.kek.wipe()
                    _wipe(local.dek)
            else:
                self._open(bundle.artifact, password)
        self._snapshot("pre-sync-import")
        self._repo.save(bundle.artifact)

    def verify_same_vault(self, artifact: EncryptedVault, dek) -> None:
        """Raise unless ``artifact``'s body decrypts with ``dek``."""
        try:
            self._decrypt_body(artifact, dek)
        except (AuthenticationError, UnsupportedVaultFormat, binascii.Error, ValueError) as exc:
            raise ValueError("el paquete no pertenece a esta bóveda") from exc

    def _resave(self, artifact, vault, ledger, password, dek):
        params = self._params_of(artifact.header)
        recovery = artifact.header.get("recovery")
        self._repo.save(self._seal(vault, ledger, password, params, dek, recovery,
                                   self._cipher_name(artifact.header)))

    def generate_password(self, policy=None):
        pw = self._gen.generate(policy or PasswordPolicy.strong())
        return pw, self._strength.label(pw)

    def password_strength(self, password: str):
        return self._strength.assess(password)

    def unlock(self, password):
        """Open the vault for an interactive session.

        The KEK is derived once and kept (wipeable) by the session, which then
        never needs the password again. A vault whose KDF is weaker than this
        build's default, or that predates the cipher field, is re-sealed with
        fresh parameters right away and the upgrade is written to the ledger.
        """
        from .session import VaultSession
        artifact = self._require()
        opened = self._open_full(artifact, password)
        target = self._kdf_factory()
        legacy_header = artifact.header.get("cipher") in (None, LEGACY_CIPHER) or \
            int(artifact.header.get("version", 0) or 0) < HEADER_VERSION
        if opened.params.weaker_than(target) or legacy_header:
            new_kek = self._derive(password, target)
            before = opened.params.describe()
            opened.kek.wipe()
            opened.kek, opened.params = new_kek, target
            opened.upgraded_from = before
            opened.ledger.append("kdf-upgrade", f"{before} -> {target.describe()}", self._clock.now_iso())
            sealed = self._seal_with_kek(opened.vault, opened.ledger, new_kek.bytes, target,
                                         opened.dek, opened.recovery, opened.cipher_name)
            self._repo.save(sealed)
            opened.nonce = sealed.nonce
        return VaultSession(self, opened)


def entry_view(e) -> EntryView:
    return EntryView(
        name=e.name, username=e.username, url=e.url, tags=e.tags,
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
        updated_at=getattr(e, "updated_at", ""),
        notes=getattr(e, "notes", ""),
        kind=getattr(e, "kind", "login") or "login",
        password_changed_at=getattr(e, "password_changed_at", "") or getattr(e, "created_at", ""),
        deleted_at=getattr(e, "deleted_at", ""),
        history_count=len(getattr(e, "password_history", ()) or ()),
    )


def constant_time_equal(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(bytes(a), bytes(b))
