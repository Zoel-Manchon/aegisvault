"""Threaded unlock/create workers for the desktop GUI.

Password KDF + vault decryption can take noticeable time on real vaults.  The
widgets GUI must never perform that work on the Qt event loop, otherwise the
unlock dialog looks frozen.  This module keeps the crypto/use-case work in a
QThread and returns the unlocked VaultSession through Qt signals.
"""
from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Signal, Slot

from ....application.errors import AuthenticationError, VaultAlreadyExists


class VaultUnlockWorker(QObject):
    """Run vault creation/unlock away from the GUI thread."""

    succeeded = Signal(object)
    authentication_failed = Signal(str)
    failed = Signal(str, str)

    def __init__(self, service, password: str, *, create: bool = False):
        super().__init__()
        self._service = service
        self._password = password
        self._create = create

    @Slot()
    def run(self) -> None:
        try:
            if self._create:
                self._service.init_vault(self._password)
            session = self._service.unlock(self._password)
        except AuthenticationError:
            self.authentication_failed.emit("Wrong master password.")
        except VaultAlreadyExists:
            self.failed.emit("Vault already exists", "The vault was created by another process before this window finished.")
        except Exception as exc:  # pragma: no cover - defensive GUI boundary
            self.failed.emit(str(exc) or exc.__class__.__name__, traceback.format_exc())
        else:
            self.succeeded.emit(session)
