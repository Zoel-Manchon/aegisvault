"""Ports: the abstractions the application depends on.

The crypto ports are the seam the Rust core slots into - `Cipher` and
`KeyDerivation` have a Python adapter (today) and a Rust/PyO3 adapter
(ferrocrypto), chosen at the composition root. Neither domain nor application
knows which is in use.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.value_objects.kdf_params import KdfParams
from ...domain.value_objects.master_key import MasterKey


@runtime_checkable
class KeyDerivation(Protocol):
    """Derive a MasterKey from a password + KDF parameters."""

    def derive(self, password: str, params: KdfParams) -> MasterKey: ...


@runtime_checkable
class Cipher(Protocol):
    """Authenticated encryption. encrypt returns (nonce, ciphertext)."""

    def encrypt(self, key: bytes, plaintext: bytes, aad: bytes) -> tuple: ...
    def decrypt(self, key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes: ...


@runtime_checkable
class VaultRepository(Protocol):
    """Load/save the encrypted vault artifact (no crypto knowledge)."""

    def exists(self) -> bool: ...
    def load(self): ...                 # -> EncryptedVault
    def save(self, artifact) -> None: ...


@runtime_checkable
class Clock(Protocol):
    def now_iso(self) -> str: ...
    def now_unix(self) -> int: ...


@runtime_checkable
class BreachChecker(Protocol):
    """Outbound: check passwords against a breach corpus (e.g. HIBP)."""

    def check(self, name_to_password: dict) -> dict: ...
