"""Application-level errors (boundary failures, not domain rule violations)."""
from __future__ import annotations


class VaultAlreadyExists(Exception):
    pass


class VaultDoesNotExist(Exception):
    pass


class AuthenticationError(Exception):
    """Wrong master password or tampered vault (AEAD verification failed)."""


class UnsupportedVaultFormat(Exception):
    """The vault needs a cipher or KDF this build cannot run, or its header is unsafe.

    Raised instead of ``AuthenticationError`` so a missing crypto backend is
    never reported to the user as a wrong password.
    """


class VaultConflictError(Exception):
    """The vault file changed on disk after this session loaded it.

    Another window, process or sync client wrote it. Saving now would silently
    discard that change, so the session refuses and asks to reopen the vault.
    """


class WeakMasterPassword(ValueError):
    """The proposed master password does not meet the minimum policy."""
