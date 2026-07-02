"""Composition root: the single place adapters are bound to ports.

Picks the Rust crypto core when it's been built (maturin), otherwise the
pure-Python reference adapters. Nothing above this file knows which is active.
"""
from __future__ import annotations

from .adapters.outbound.clock.system_clock import SystemClock
from .adapters.outbound.crypto import rust_backend
from .adapters.outbound.crypto.aesgcm_cipher import AesGcmCipher
from .adapters.outbound.crypto.scrypt_kdf import ScryptKeyDerivation
from .adapters.outbound.storage.file_repository import FileVaultRepository
from .application.services.vault_service import VaultService
from .domain.value_objects.kdf_params import KdfParams


def build_vault_service(vault_path: str) -> VaultService:
    if vault_path.endswith((".db", ".sqlite")):
        from .adapters.outbound.storage.sqlite_repository import SqliteVaultRepository
        repository = SqliteVaultRepository(vault_path)
    else:
        repository = FileVaultRepository(vault_path)

    if rust_backend.AVAILABLE:
        key_derivation = rust_backend.RustKeyDerivation()
        cipher = rust_backend.RustCipher()
        kdf_factory = KdfParams.argon2id
    else:
        key_derivation = ScryptKeyDerivation()
        cipher = AesGcmCipher()
        kdf_factory = KdfParams.scrypt

    return VaultService(
        repository=repository,
        key_derivation=key_derivation,
        cipher=cipher,
        clock=SystemClock(),
        kdf_factory=kdf_factory,
    )


def build_breach_checker(online: bool = False):
    """Return a BreachChecker: HIBP (network) when online, else offline null."""
    if online:
        from .adapters.outbound.breach.hibp import HibpBreachChecker
        return HibpBreachChecker()
    from .adapters.outbound.breach.null import NullBreachChecker
    return NullBreachChecker()
