"""Headless smoke test for the Qt GUI adapter (skips if PySide6 absent).

Runs Qt with the 'offscreen' platform so it needs no display. It can't verify
pixels, but it proves the window builds, the entry list populates from the
session, adding an entry refreshes the list, and the TOTP tick path runs
without error - i.e. the GUI correctly drives the application core.
"""
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("cryptography")

from PySide6.QtWidgets import QApplication                       # noqa: E402
from PySide6.QtCore import Qt                                    # noqa: E402

from ferrovault.adapters.outbound.clock.system_clock import SystemClock      # noqa: E402
from ferrovault.adapters.outbound.crypto.aesgcm_cipher import AesGcmCipher   # noqa: E402
from ferrovault.adapters.outbound.crypto.scrypt_kdf import ScryptKeyDerivation  # noqa: E402
from ferrovault.adapters.outbound.storage.file_repository import FileVaultRepository  # noqa: E402
from ferrovault.application.services.vault_service import VaultService       # noqa: E402
from ferrovault.adapters.inbound.gui.main_window import MainWindow           # noqa: E402

_app = QApplication.instance() or QApplication([])


def _session(path):
    svc = VaultService(FileVaultRepository(path), ScryptKeyDerivation(),
                       AesGcmCipher(), SystemClock())
    svc.init_vault("master")
    return svc.unlock("master")


def test_window_builds_and_lists_entries():
    with tempfile.TemporaryDirectory() as d:
        session = _session(os.path.join(d, "v.fv"))
        session.add("github", "octocat", "s3cr3t", totp="JBSWY3DPEHPK3PXP")
        win = MainWindow(session, _app.clipboard())
        assert win.list.count() == 1

        # add through the session and refresh
        session.add("aws", "root", "AKIA")
        win._reload()
        assert win.list.count() == 2


def test_reveal_and_totp_tick():
    with tempfile.TemporaryDirectory() as d:
        session = _session(os.path.join(d, "v.fv"))
        session.add("github", "octocat", "s3cr3t", totp="JBSWY3DPEHPK3PXP")
        win = MainWindow(session, _app.clipboard())
        win.list.setCurrentRow(0)
        assert win._current is not None

        win._toggle_reveal()                       # reveals the real secret
        assert win.secret_lbl.text() == "s3cr3t"

        win._tick()                                # live 2FA code, no crash
        assert win.code_lbl.text().replace(" ", "").isdigit()
