"""Composition root: the single place adapters are bound to ports.

Crypto selection, strongest first:

* KDF for new vaults: Argon2id - from the Rust core when it is built
  (maturin), otherwise from `cryptography` (OpenSSL 3.2+). scrypt with the
  OWASP cost is the last resort for an old `cryptography`.
* AEAD for new vaults: XChaCha20-Poly1305 (Rust) or AES-256-GCM.

Existing vaults are opened with whatever their header names, so a vault made
by the pure-Python build still opens once the Rust core is installed, and a
weak legacy KDF is upgraded on the next unlock. Nothing above this file knows
which adapters are active.
"""
from __future__ import annotations

from .adapters.outbound.clock.system_clock import SystemClock
from .adapters.outbound.crypto import argon2_kdf, rust_backend
from .adapters.outbound.crypto.aesgcm_cipher import AesGcmCipher
from .adapters.outbound.crypto.kdf_router import KeyDerivationRouter
from .adapters.outbound.crypto.scrypt_kdf import ScryptKeyDerivation
from .adapters.outbound.storage.file_repository import FileVaultRepository
from .application.services.vault_service import VaultService
from .domain.value_objects.kdf_params import KdfParams


def crypto_profile() -> dict:
    """What this build will use for a new vault (shown on the unlock screen)."""
    if rust_backend.AVAILABLE:
        backend, kdf = "Rust", "argon2id"
    elif argon2_kdf.AVAILABLE:
        backend, kdf = "Python", "argon2id"
    else:
        backend, kdf = "Python", "scrypt"
    params = KdfParams.argon2id() if kdf == "argon2id" else KdfParams.scrypt_strong()
    return {
        "backend": backend,
        "kdf": "Argon2id" if kdf == "argon2id" else "scrypt",
        "params": params.describe(),
        "cipher": "XChaCha20-Poly1305" if rust_backend.AVAILABLE else "AES-256-GCM",
    }


def build_vault_service(vault_path: str, backup_dir: str | None = None, keep_backups: int = 10) -> VaultService:
    if vault_path.endswith((".db", ".sqlite")):
        from .adapters.outbound.storage.sqlite_repository import SqliteVaultRepository
        repository = SqliteVaultRepository(vault_path, backup_dir=backup_dir, keep=keep_backups)
    else:
        repository = FileVaultRepository(vault_path, backup_dir=backup_dir, keep=keep_backups)

    aes = AesGcmCipher()
    if rust_backend.AVAILABLE:
        argon = rust_backend.RustKeyDerivation()
        cipher, extra = rust_backend.RustCipher(), (aes,)
    else:
        argon = argon2_kdf.Argon2idKeyDerivation() if argon2_kdf.AVAILABLE else None
        cipher, extra = aes, ()

    adapters = [a for a in (argon, ScryptKeyDerivation()) if a is not None]
    kdf_factory = KdfParams.argon2id if argon is not None else KdfParams.scrypt_strong

    return VaultService(
        repository=repository,
        key_derivation=KeyDerivationRouter(*adapters),
        cipher=cipher,
        clock=SystemClock(),
        kdf_factory=kdf_factory,
        extra_ciphers=extra,
    )


def build_breach_checker(online: bool = False):
    """Return a BreachChecker: HIBP (network) when online, else offline null."""
    if online:
        from .adapters.outbound.breach.hibp import HibpBreachChecker
        return HibpBreachChecker()
    from .adapters.outbound.breach.null import NullBreachChecker
    return NullBreachChecker()
