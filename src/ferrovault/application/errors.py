"""Application-level errors (boundary failures, not domain rule violations)."""
from __future__ import annotations


class VaultAlreadyExists(Exception):
    pass


class VaultDoesNotExist(Exception):
    pass


class AuthenticationError(Exception):
    """Wrong master password or tampered vault (AEAD verification failed)."""
